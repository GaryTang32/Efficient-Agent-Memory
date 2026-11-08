"""Measurement fixes from the 2026-11-08 code audit: side calls on the agent's own history obey the window, folding
branches report their peak and overflows, the CLI backend counts failed attempts, unfinished SWE sessions are graded,
and test files are reset before the test patch."""

import json
import subprocess
from types import SimpleNamespace

from eam.agent.context import Tool
from eam.agent.loop import run_agent
from eam.bench.runner import run_instance
from eam.bench.tasks import swe_env as E
from eam.bench.tasks.common import TaskInstance
from eam.llm import claude_cli as C
from eam.llm.mock import MockLLM, assistant, final, tool_use
from eam.llm.types import Request, ToolSpec
from eam.models import MOCK_MODELS
from eam.techniques import build
from eam.techniques.eocc import HandoffCompaction

M = MOCK_MODELS["mock-strong"]


def big_tool(words=20000):
    return [Tool(ToolSpec("read", "r", {"type": "object", "properties": {}}), lambda a, c: "word " * words)]


def test_agent_written_recap_over_the_window_is_an_overflow():
    def policy(req):
        return assistant(tool_use("read", {}))

    res = run_agent("t", llm=MockLLM(policy, aux_policy=lambda r: final("recap")), model=M, env_tools=big_tool(),
                    techniques=[HandoffCompaction(threshold=0.5, writer="agent")], max_steps=5, context_limit=8000)
    kinds = [(e["kind"], e.get("when")) for e in res.events]
    assert ("context_overflow", "side_call") in kinds and not any(k == "handoff_rebuild" for k, _ in kinds)
    assert not res.finished


def test_folding_branch_peak_and_overflow_reach_the_run():
    def policy(req):
        last = req.messages[-1]["content"]
        text = " ".join(c.get("text", "") for b in last if "toolResult" in b for c in b["toolResult"]["content"])
        if req.tag == "main":
            if "eturned" in text or "finished" in text:
                return final("FINAL ANSWER: done")
            return assistant(tool_use("branch", {"description": "d", "prompt": "read it"}))
        return assistant(tool_use("return", {"message": "found"})) if "word word" in text else \
            assistant(tool_use("read", {}))

    for limit in (None, 16000):
        res = run_agent("task", llm=MockLLM(policy, validate=False), model=M, env_tools=big_tool(),
                        techniques=build("folding"), max_steps=5, context_limit=limit, context_gauge=False)
        branch = max(c.usage.prompt_tokens for c in res.meter.records if c.tag == "subagent")
        if limit is None:
            assert res.peak_prompt_tokens >= branch
        else:
            assert any(e["kind"] == "context_overflow" and e.get("branch") for e in res.events)


def fake_run(results):
    """subprocess.run stand-in that returns one stream-json result per call."""
    calls = iter(results)

    def run(cmd, **kw):
        r = next(calls)
        if r == "timeout":
            raise subprocess.TimeoutExpired(cmd, 1, output=json.dumps(
                {"type": "assistant", "message": {"id": "m1", "usage": {"input_tokens": 1000, "output_tokens": 50}}}
            ).encode())
        lines = [json.dumps({"type": "assistant", "message": {"id": "a", "usage": r["usage"]}}), json.dumps(r)]
        return SimpleNamespace(stdout="\n".join(lines), stderr="", returncode=0)

    return run


def ok(cost=0.01, **extra):
    return {"type": "result", "is_error": False, "result": "hi", "num_turns": 1,
            "usage": {"input_tokens": 100, "output_tokens": 5}, **({"total_cost_usd": cost} if cost is not None
                                                                  else {}), **extra}


def converse(monkeypatch, results):
    monkeypatch.setattr(C.subprocess, "run", fake_run(results))
    monkeypatch.setattr(C.time, "sleep", lambda s: None)
    req = Request(model=M, system=[{"text": "s"}], messages=[{"role": "user", "content": [{"text": "q"}]}],
                  max_tokens=50)
    return C.ClaudeCLIClient(retries=2).converse(req)


def test_cli_counts_the_cost_of_failed_attempts(monkeypatch):
    err = {**ok(0.02), "is_error": True, "result": "API Error: overloaded"}
    resp = converse(monkeypatch, [err, ok(0.01)])
    assert abs(resp.reported_cost_usd - 0.03) < 1e-9 and resp.retries == 1 and resp.usage.output_tokens == 10
    resp = converse(monkeypatch, ["timeout", ok(0.01)])
    assert resp.reported_cost_usd > 0.01 and resp.retries == 1 and resp.usage.input_tokens == 1100


def test_cli_missing_cost_is_priced_from_usage_and_size_comes_from_the_first_request(monkeypatch):
    resp = converse(monkeypatch, [ok(None, num_turns=2)])
    assert resp.reported_cost_usd is None and resp.prompt_size == 100


def test_unfinished_rounds_are_graded_when_the_task_says_so():
    graded = []
    for flag in (False, True):
        inst = TaskInstance(family="t", instance_id="t-0", prompt="p", tools=big_tool(10), check=lambda a: False,
                            gold="g", oracle=lambda: (lambda req: assistant(tool_use("read", {}))), max_steps=2,
                            rounds=["r1", "r2"], round_score=lambda k, a: graded.append(k) or 1.0,
                            grade_unfinished=flag)
        row = run_instance(inst, "naive", backend="mock", model=M, aux_model=M, models=MOCK_MODELS)
        assert row["unfinished_sessions"] == 2 and row["score"] == (1.0 if flag else 0.0)
    assert graded == [0, 1]


def test_test_files_are_reset_before_the_test_patch(tmp_path):
    def git(*a):
        return subprocess.run(["git", "-C", str(tmp_path), *a], check=True, capture_output=True, text=True).stdout

    git("init", "-q")
    (tmp_path / "t.py").write_text("orig\n")
    git("add", ".")
    git("-c", "user.name=x", "-c", "user.email=x@x", "commit", "-qm", "base")
    base = git("rev-parse", "HEAD").strip()
    (tmp_path / "t.py").write_text("agent edit\n")
    (tmp_path / "new.py").write_text("agent file\n")
    patch = "diff --git a/t.py b/t.py\ndiff --git a/new.py b/new.py\n"
    E.reset_test_files(tmp_path, {"test_patch": patch, "base_commit": base})
    assert (tmp_path / "t.py").read_text() == "orig\n" and not (tmp_path / "new.py").exists()
