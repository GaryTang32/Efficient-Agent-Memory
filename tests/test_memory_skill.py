"""MemorySkill (framework-agnostic library) and the MCP server built on it."""

import json
import subprocess
import sys

import pytest

from eam.memory_skill import MemorySkill


def test_notes_persist_and_are_recalled(tmp_path):
    a = MemorySkill(tmp_path)
    assert a.session_preamble() == ""
    a.write_note("totals", "Acme = 10")
    a.save_session("FINAL ANSWER: Acme = 10", label="round 1")
    b = MemorySkill(tmp_path)  # a later session / process
    pre = b.session_preamble()
    assert "Acme = 10" in pre and "round 1" in pre


def test_guard_offloads_only_what_does_not_fit(tmp_path):
    s = MemorySkill(tmp_path, window=10_000, guard=0.9)
    s.start_step(context_tokens=6_000)
    small = s.ingest_tool_output("open", "x " * 400)  # ~ 300 real tokens: fits
    big = s.ingest_tool_output("open", "word " * 4000)  # would exceed 9,000
    assert small.startswith("x ") and big.startswith("[Output of open moved out")
    pointer = big.split("stored at ")[1].split(";")[0]
    assert s.read_artifact(pointer).startswith("word ")
    assert s.end_step() < 9_000


def test_read_artifact_rejects_paths(tmp_path):
    s = MemorySkill(tmp_path)
    with pytest.raises(ValueError):
        s.read_artifact("artifact://../notes")


def test_compaction_uses_resum_and_keeps_notes(tmp_path):
    prompts = []
    s = MemorySkill(tmp_path, window=1000, trigger=0.75, summarize=lambda p: prompts.append(p) or
                    "<summary>found: Acme = 10</summary>")
    s.write_note("progress", "L-01..L-05 done")
    msgs = [{"role": "system", "content": "sys"}, {"role": "user", "content": "q"},
            {"role": "assistant", "content": "reading"}]
    assert s.maybe_compact(msgs, context_tokens=500, question="q") is msgs  # below the trigger
    out = s.maybe_compact(msgs, context_tokens=800, question="totals?")
    assert out[0]["role"] == "system" and len(out) == 2
    assert "found: Acme = 10" in out[1]["content"] and "L-01..L-05 done" in out[1]["content"]
    assert "Conversation History" in prompts[0]  # ReSum's official prompt


def _rpc(proc, mid, method, params=None):
    proc.stdin.write(json.dumps({"jsonrpc": "2.0", "id": mid, "method": method, "params": params or {}}) + "\n")
    proc.stdin.flush()
    return json.loads(proc.stdout.readline())


def test_mcp_server_over_stdio(tmp_path):
    env = {"EAM_MEMORY_DIR": str(tmp_path), "PATH": "", "PYTHONPATH": "."}
    proc = subprocess.Popen([sys.executable, "-m", "eam.mcp_server"], stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                            text=True, env=env)
    try:
        init = _rpc(proc, 1, "initialize", {"protocolVersion": "2024-11-05", "capabilities": {}})
        assert init["result"]["serverInfo"]["name"] == "eam-automem"
        proc.stdin.write(json.dumps({"jsonrpc": "2.0", "method": "notifications/initialized"}) + "\n")
        names = {t["name"] for t in _rpc(proc, 2, "tools/list")["result"]["tools"]}
        assert {"write_note", "read_notes", "recall", "offload", "read_artifact", "compact",
                "context_budget", "save_session"} <= names

        def call(mid, tool, **args):
            r = _rpc(proc, mid, "tools/call", {"name": tool, "arguments": args})["result"]
            return r["content"][0]["text"], r["isError"]

        assert "Saved note" in call(3, "write_note", name="n", content="hello")[0]
        assert "hello" in call(4, "recall")[0]
        ptr, _ = call(5, "offload", text="big " * 100)
        assert call(6, "read_artifact", artifact_id=ptr)[0].startswith("big ")
        budget = json.loads(call(7, "context_budget", context_tokens=160_000, window=200_000)[0])
        assert budget["compact_now"] and budget["next_step_may_add"] == 20_000
        text, err = call(8, "compact", question="q", history="h")
        assert not err and "Conversation History" in text  # no route configured: the prompt is returned
        assert call(9, "nope")[1] is True
    finally:
        proc.stdin.close()
        proc.wait(timeout=5)
