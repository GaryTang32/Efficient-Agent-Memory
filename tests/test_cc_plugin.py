"""The AutoMemory Claude Code plugin: hook scripts driven with the JSON Claude Code sends (no CLI needed)."""

import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1] / "plugins" / "automem"
HOOK = ROOT / "hooks" / "automem_hook.py"


def run(event, payload, tmp_path, **env):
    e = {"AUTOMEM_DATA": str(tmp_path / "data"), "PATH": "/usr/bin:/bin", **{k: str(v) for k, v in env.items()}}
    r = subprocess.run([sys.executable, str(HOOK), event], input=json.dumps(payload), capture_output=True, text=True,
                       env=e, timeout=30)
    assert r.returncode == 0, r.stderr
    return r.stdout.strip()


def test_manifest_and_hooks_are_valid():
    manifest = json.loads((ROOT / ".claude-plugin" / "plugin.json").read_text())
    hooks = json.loads((ROOT / "hooks" / "hooks.json").read_text())["hooks"]
    assert manifest["name"] == "automem"
    assert set(hooks) == {"SessionStart", "PostToolUse", "PreCompact", "Stop"}
    assert (ROOT / "skills" / "automem" / "SKILL.md").read_text().startswith("---\nname: automem")


def test_large_bash_output_becomes_a_preview_with_the_full_text_saved(tmp_path):
    big = "\n".join(f"test_{i} (app.tests.T) ... ok" for i in range(2000)) + "\nFAILED (failures=1)\n"
    payload = {"tool_name": "Bash", "cwd": str(tmp_path), "tool_use_id": "toolu_abc123",
               "tool_input": {"command": "python tests/runtests.py app"},
               "tool_response": {"stdout": "", "stderr": big, "interrupted": False, "isImage": False,
                                 "noOutputExpected": False}}
    out = json.loads(run("post_tool_use", payload, tmp_path))["hookSpecificOutput"]
    assert out["hookEventName"] == "PostToolUse"
    upd = out["updatedToolOutput"]
    assert set(upd) == {"stdout", "stderr", "interrupted", "isImage"} and upd["stdout"] == ""
    assert len(upd["stderr"]) < 3600 and "FAILED (failures=1)" in upd["stderr"] and "test_0 " in upd["stderr"]
    path = upd["stderr"].split("Full output saved to ")[1].split(" - ")[0]
    assert Path(path).read_text().endswith(big) and "python tests/runtests.py app" in Path(path).read_text()


def test_output_claude_code_truncated_is_previewed_from_its_saved_copy(tmp_path):
    full = "OUT-START\n" + "\n".join(f"err {i}" for i in range(12000)) + "\nOUT-END\n"
    saved = tmp_path / "tool-results" / "abc.txt"
    saved.parent.mkdir()
    saved.write_text(full)
    payload = {"tool_name": "Bash", "cwd": str(tmp_path), "tool_input": {"command": "big"},
               "tool_response": {"stdout": full[:30000], "stderr": "", "interrupted": False, "isImage": False,
                                 "persistedOutputPath": str(saved), "persistedOutputSize": len(full)}}
    upd = json.loads(run("post_tool_use", payload, tmp_path))["hookSpecificOutput"]["updatedToolOutput"]
    assert "OUT-START" in upd["stdout"] and "OUT-END" in upd["stdout"] and str(saved) in upd["stdout"]
    assert "persistedOutputPath" not in upd and len(upd["stdout"]) < 3600


def test_small_output_other_tools_and_saved_files_are_left_alone(tmp_path):
    small = {"tool_name": "Bash", "cwd": str(tmp_path), "tool_input": {"command": "ls"},
             "tool_response": {"stdout": "a\nb\n", "stderr": "", "interrupted": False, "isImage": False}}
    assert run("post_tool_use", small, tmp_path) == ""
    other = {**small, "tool_name": "Read", "tool_response": {"stdout": "x" * 50000}}
    assert run("post_tool_use", other, tmp_path) == ""
    rereading = {**small, "tool_input": {"command": f"cat {tmp_path}/data/projects/x/outputs/bash-1.log"},
                 "tool_response": {**small["tool_response"], "stdout": "y\n" * 10000}}
    assert run("post_tool_use", rereading, tmp_path) == ""
    off = {**small, "tool_response": {**small["tool_response"], "stdout": "y\n" * 10000}}
    assert run("post_tool_use", off, tmp_path, AUTOMEM_PREVIEW_CHARS=0) == ""


def test_stop_saves_a_note_and_session_start_recalls_it(tmp_path):
    assert run("session_start", {"cwd": str(tmp_path)}, tmp_path) == ""
    msg = "Fixed the ordering bug in django/db/models/query.py; tests in ordering.tests pass."
    run("stop", {"cwd": str(tmp_path), "session_id": "s1", "last_assistant_message": msg}, tmp_path)
    run("stop", {"cwd": str(tmp_path), "last_assistant_message": "ok"}, tmp_path)  # too short to keep
    out = json.loads(run("session_start", {"cwd": str(tmp_path), "source": "compact"}, tmp_path))
    ctx = out["hookSpecificOutput"]["additionalContext"]
    assert out["hookSpecificOutput"]["hookEventName"] == "SessionStart" and msg in ctx and "- ok" not in ctx
    assert run("session_start", {"cwd": str(tmp_path)}, tmp_path, AUTOMEM_NOTES="off") == ""
    other = tmp_path / "other"
    other.mkdir()
    assert run("session_start", {"cwd": str(other)}, tmp_path) == ""  # notes are per project


def test_pre_compact_prints_the_handoff_recap(tmp_path):
    out = run("pre_compact", {"trigger": "auto"}, tmp_path)
    assert "6. Remaining plan" in out and "Dead ends" in out and len(out) < 10_000


def test_bad_input_never_breaks_the_session(tmp_path):
    r = subprocess.run([sys.executable, str(HOOK), "post_tool_use"], input="not json", capture_output=True, text=True,
                       env={"AUTOMEM_DATA": str(tmp_path)}, timeout=30)
    assert r.returncode == 0 and r.stdout == ""


def test_preview_sizes_in_tokens_and_relative_to_the_compaction_window(tmp_path):
    """AUTOMEM_PREVIEW_TOKENS, AUTOMEM_PREVIEW_SHARE (of CLAUDE_CODE_AUTO_COMPACT_WINDOW, capped by
    AUTOMEM_PREVIEW_MAX_TOKENS) and AUTOMEM_PREVIEW_KEEP_TOKENS set the preview sizes in tokens."""
    def bash(n_chars):
        return {"tool_name": "Bash", "cwd": str(tmp_path), "tool_use_id": "toolu_x", "tool_input": {"command": "t"},
                "tool_response": {"stdout": ("line of output\n" * (n_chars // 15 + 1))[:n_chars], "stderr": "",
                                  "interrupted": False, "isImage": False}}

    assert run("post_tool_use", bash(20_000), tmp_path)                                    # default: 6000 chars
    assert not run("post_tool_use", bash(20_000), tmp_path, AUTOMEM_PREVIEW_TOKENS=8000)    # 32,000 chars
    assert run("post_tool_use", bash(40_000), tmp_path, AUTOMEM_PREVIEW_TOKENS=8000)
    # 2% of a 500K compaction window = 10,000 tokens = 40,000 characters
    w = {"CLAUDE_CODE_AUTO_COMPACT_WINDOW": 500_000, "AUTOMEM_PREVIEW_SHARE": 0.02}
    assert not run("post_tool_use", bash(39_000), tmp_path, **w)
    assert run("post_tool_use", bash(41_000), tmp_path, **w)
    # the cap: 10% of 500K would be 50K tokens; the default cap keeps it at 16K tokens = 64,000 characters
    big = {**w, "AUTOMEM_PREVIEW_SHARE": 0.1}
    assert run("post_tool_use", bash(70_000), tmp_path, **big)
    assert not run("post_tool_use", bash(70_000), tmp_path, **big, AUTOMEM_PREVIEW_MAX_TOKENS=0)
    # head and tail in tokens: 500 tokens each = 2,000 characters
    upd = json.loads(run("post_tool_use", bash(40_000), tmp_path, AUTOMEM_PREVIEW_KEEP_TOKENS=500))
    assert len(upd["hookSpecificOutput"]["updatedToolOutput"]["stdout"]) < 4_400


def test_out_of_range_settings_fall_back_to_the_defaults(tmp_path):
    payload = {"tool_name": "Bash", "cwd": str(tmp_path), "tool_use_id": "toolu_y", "tool_input": {"command": "t"},
               "tool_response": {"stdout": "line of output\n" * 1000, "stderr": "", "interrupted": False,
                                 "isImage": False}}  # 15,000 characters
    for bad in ({"AUTOMEM_PREVIEW_CHARS": "12"}, {"AUTOMEM_PREVIEW_CHARS": "lots"}, {"AUTOMEM_PREVIEW_TOKENS": "-5"},
                {"AUTOMEM_PREVIEW_SHARE": "3", "CLAUDE_CODE_AUTO_COMPACT_WINDOW": "500000"}):
        out = json.loads(run("post_tool_use", payload, tmp_path, **bad))  # the default 6000-character threshold
        assert "[AutoMemory:" in out["hookSpecificOutput"]["updatedToolOutput"]["stdout"], bad
    assert not run("post_tool_use", payload, tmp_path, AUTOMEM_PREVIEW_CHARS="0")  # 0 still turns previews off


def test_full_mode_shares_the_note_store_with_the_library(tmp_path):
    """AUTOMEM_WORKSPACE=on: session start adds the note rule and recalls the store the MCP server writes; stop
    autosaves into it (each answer supersedes the previous one); resume skips recall; the timing log records calls."""
    from eam.automem import JsonStore
    from eam.memory_skill import MemorySkill

    store, log = tmp_path / "store", tmp_path / "timing.jsonl"
    env = {"AUTOMEM_WORKSPACE": "on", "AUTOMEM_STORE": str(store), "AUTOMEM_TIMING_LOG": str(log)}
    first = json.loads(run("session_start", {"cwd": str(tmp_path), "source": "startup"}, tmp_path, **env))
    ctx = first["hookSpecificOutput"]["additionalContext"]
    assert "write_note" in ctx and "<memory>" in ctx and "Your persistent workspace notes" not in ctx  # rule, no notes

    MemorySkill(store).write_note("EV-50012", "RECEIPT of AB-12, qty 40 (day 1)", type="fact")  # as write_note does
    for answer in ("Day 1: AB-12 431, CD-34 220 (long enough to keep)", "Day 2: AB-12 401, CD-34 260 (long enough)"):
        run("stop", {"cwd": str(tmp_path), "session_id": "s1", "last_assistant_message": answer}, tmp_path, **env)
    notes = JsonStore(store).load()  # the library reads what the plugin wrote
    results = [n for n in notes if n.type == "result"]
    assert [n.active for n in results] == [False, True] and results[1].supersedes == results[0].name
    recall = json.loads(run("session_start", {"cwd": str(tmp_path), "source": "startup"}, tmp_path, **env))
    text = recall["hookSpecificOutput"]["additionalContext"]
    assert "EV-50012" in text and "Day 2: AB-12 401" in text and "Day 1: AB-12 431" not in text
    assert not run("session_start", {"cwd": str(tmp_path), "source": "resume"}, tmp_path, **env)
    events = [json.loads(line) for line in log.read_text().splitlines()]
    assert [e["event"] for e in events].count("session_start") == 3 and all(e["ms"] >= 0 for e in events)
    assert any(e.get("recall_chars") for e in events) and any(e.get("skipped") == "resume" for e in events)


def test_full_mode_off_keeps_the_default_behaviour(tmp_path):
    run("stop", {"cwd": str(tmp_path), "last_assistant_message": "a default-mode answer, long enough to keep"},
        tmp_path)
    out = json.loads(run("session_start", {"cwd": str(tmp_path), "source": "startup"}, tmp_path))
    assert "a default-mode answer" in out["hookSpecificOutput"]["additionalContext"]
    assert "write_note" not in out["hookSpecificOutput"]["additionalContext"]
