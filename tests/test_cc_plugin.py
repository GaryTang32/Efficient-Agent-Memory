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
