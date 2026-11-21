"""The Claude Code test harness (scripts/run_cc_test.py, scripts/analyze_cc_test.py) checked offline with the
stand-in `claude` (scripts/fake_claude.py): the environment is explicit, each arm gets only its own switches, the
event stream is read correctly, and a small rehearsal is logged, graded and analysed end to end."""

import json
import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
import run_cc_test as R  # noqa: E402


def test_environment_is_explicit_and_per_arm(tmp_path, monkeypatch):
    for k, v in {"CLAUDE_EFFORT": "xhigh", "MAX_THINKING_TOKENS": "31999", "CLAUDE_AUTOCOMPACT_PCT_OVERRIDE": "92",
                 "CLAUDE_CODE_REMOTE": "true", "GH_TOKEN": "x"}.items():
        monkeypatch.setenv(k, v)
    a = R.child_env("A", "N", tmp_path, tmp_path)
    for leaked in ("CLAUDE_EFFORT", "MAX_THINKING_TOKENS", "CLAUDE_AUTOCOMPACT_PCT_OVERRIDE", "CLAUDE_CODE_REMOTE",
                   "GH_TOKEN"):
        assert leaked not in a
    assert a["CLAUDE_CODE_DISABLE_AUTO_MEMORY"] == "0" and a["CLAUDE_CODE_AUTO_COMPACT_WINDOW"] == "500000"
    assert a["DISABLE_AUTOUPDATER"] == "1" and not any(k.startswith("AUTOMEM_") for k in a)
    assert R.child_env("A0", "N", tmp_path, tmp_path)["CLAUDE_CODE_DISABLE_AUTO_MEMORY"] == "1"
    assert R.child_env("L", "R100", tmp_path, tmp_path)["AUTOMEM_NOTES"] == "off"
    assert R.child_env("L", "R100", tmp_path, tmp_path)["CLAUDE_CODE_AUTO_COMPACT_WINDOW"] == "100000"
    v2 = R.child_env("V2", "N", tmp_path, tmp_path)
    assert v2["AUTOMEM_WORKSPACE"] == "on" and v2["AUTOMEM_STORE"].endswith("store")


def test_commands_differ_only_by_the_arm(tmp_path):
    base = R.command(["claude"], "task", "A", tmp_path, 500_000, "sonnet", 2.0, None)
    assert "--plugin-dir" not in base and "--mcp-config" not in base and "--resume" not in base
    assert base[base.index("--setting-sources") + 1] == "" and "--strict-mcp-config" in base
    lean = R.command(["claude"], "task", "L", tmp_path, 500_000, "sonnet", 2.0, "sid-1")
    assert "--plugin-dir" in lean and "--mcp-config" not in lean and lean[-2:] == ["--resume", "sid-1"]
    full = R.command(["claude"], "task", "V2", tmp_path, 500_000, "sonnet", 2.0, None)
    tools = full[full.index("--allowedTools") + 1]
    assert "mcp__automem__write_note" in tools and "mcp__automem__write_note" not in base[base.index("--allowedTools") + 1]
    cfg = json.loads((tmp_path / "mcp.json").read_text())["mcpServers"]["automem"]
    assert cfg["env"]["EAM_MEMORY_DIR"].endswith("store") and cfg["args"] == ["-m", "eam.mcp_server"]


def test_stream_parsing(tmp_path):
    sid = "s-1"
    ev = [{"type": "system", "subtype": "init", "session_id": sid, "model": "claude-sonnet-5-5", "tools": ["Bash"]},
          {"type": "assistant", "message": {"id": "m1", "content": [
              {"type": "tool_use", "id": "t1", "name": "Bash", "input": {"command": "python tools/report.py audit"}}],
              "usage": {"input_tokens": 5, "cache_read_input_tokens": 0, "cache_creation_input_tokens": 20000,
                        "output_tokens": 50}}},
          {"type": "user", "message": {"content": [{"type": "tool_result", "tool_use_id": "t1",
                                                    "content": "head... Output too large. saved to tool-results/x.txt"}]}},
          {"type": "system", "subtype": "compact_boundary", "compact_metadata": {"trigger": "auto", "pre_tokens": 70000}},
          {"type": "system", "subtype": "microcompact_boundary"},
          {"type": "result", "subtype": "success", "num_turns": 2, "result": "answer", "total_cost_usd": 0.1}]
    s = R.parse_stream([json.dumps(e) for e in ev], tmp_path)
    assert s["session_id"] == sid and s["turns"] == 2 and s["final_text"] == "answer"
    assert s["compactions"] == [{"trigger": "auto", "pre_tokens": 70000}] and s["microcompacts"] == 1
    assert s["report_kinds"]["audit"] == {"calls": 1, "preview": 0, "cc_cut": 1, "chars": len(
        "head... Output too large. saved to tool-results/x.txt")}
    assert s["calls"][0]["prompt"] == 20005


def test_rehearsal_end_to_end(tmp_path):
    out = tmp_path / "out"
    env = {**os.environ, "HOME": str(tmp_path / "home")}
    (tmp_path / "home").mkdir()
    subprocess.run([sys.executable, str(ROOT / "scripts" / "run_cc_test.py"), "--cell", "N", "--arms", "A", "A2", "V2",
                    "--instances", "1", "--days", "2", "--gap-min", "0", "--claude-bin",
                    str(ROOT / "scripts" / "fake_claude.py"), "--fake-mode", "oracle", "--out", str(out)],
                   check=True, capture_output=True, text=True, env=env, timeout=300)
    rows = [json.loads(line) for line in (out / "rows.jsonl").read_text().splitlines()]
    assert {r["arm"] for r in rows} == {"A", "A2", "V2"} and all(r["correct"] == 14 for r in rows)
    assert not list((tmp_path / "home" / ".claude" / "projects").glob("*cct*"))  # project folders archived, removed
    v2 = out / "runs" / "N-V2-i0"
    assert (v2 / "snapshots" / "day_02" / "store" / "notes.json").exists() and (v2 / "hook_timing.jsonl").exists()
    report = subprocess.run([sys.executable, str(ROOT / "scripts" / "analyze_cc_test.py"), str(out), "--gates"],
                            check=True, capture_output=True, text=True, env=env).stdout
    assert "| V2 vs A | the verdict |" in report and "| G1 logging | PASS |" in report and "| G2 isolation | PASS |" in report
