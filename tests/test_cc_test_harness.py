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

# private mount namespaces need root (this container); elsewhere the rehearsal runs without them
ISOLATION = "namespace" if os.geteuid() == 0 and subprocess.run(
    ["unshare", "--mount", "--propagation", "private", "true"], capture_output=True).returncode == 0 else "none"


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
    # a new system line each day, the same for every arm: yesterday's conversation is not read back from the cache
    day3 = R.command(["claude"], "task", "A", tmp_path, 100_000, "sonnet", 2.0, "sid-1", line=R.system_line("R100", 3))
    assert day3[day3.index("--append-system-prompt") + 1] == "Today is workday 3 of this job."
    assert R.system_line("R100", 3) != R.system_line("R100", 4) and "issue 2" in R.system_line("F2", 2)
    assert R.CELLS["R100"]["inbox_chars"] == 100_000 and "inbox_chars" not in R.CELLS["N"]


def test_isolation_and_behaviour_counters():
    cwd = "/tmp/N-A-i0-abc123/work"
    ev = [{"type": "assistant", "message": {"id": "m1", "content": [
              {"type": "tool_use", "id": "t1", "name": "Bash", "input": {"command": "grep -rl EV-1 / 2>/dev/null"}},
              {"type": "tool_use", "id": "t2", "name": "Read", "input": {"file_path": "/tmp/N-A-i0-abc123/work/inbox/m.txt"}},
              {"type": "tool_use", "id": "t3", "name": "Bash", "input": {"command": "ls ~/.claude/projects/*/"}},
              {"type": "tool_use", "id": "t4", "name": "Bash", "input": {"command": f"cat {R.ROOT}/scripts/cc_ledger.py"}}],
              "usage": {}}},
          {"type": "user", "message": {"content": [
              {"type": "tool_result", "tool_use_id": "t1", "content": "/tmp/N-V2-i0-zz9/work/NOTES.md\n/tmp/N-A-i0-abc123/x"},
              {"type": "tool_result", "tool_use_id": "t3", "content": "-tmp-N-A-i0-abc123-work"}]}}]
    s = R.parse_stream([json.dumps(e) for e in ev], cwd)
    assert R.own_run_name(cwd) == "N-A-i0" and s["isolation_flags"] == ["N-V2-i0"]  # another run's file: a leak
    assert s["disk_searches"] == 1 and s["inbox_reads"] == 1 and s["own_log_reads"] == 1
    assert len(s["hidden_access"]) == 1 and "scripts/cc_ledger.py" in s["hidden_access"][0]


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
    s = R.parse_stream([json.dumps(e) for e in ev], tmp_path / "work")
    assert s["session_id"] == sid and s["turns"] == 2 and s["final_text"] == "answer"
    assert s["compactions"] == [{"trigger": "auto", "pre_tokens": 70000}] and s["microcompacts"] == 1
    assert s["report_kinds"]["audit"] == {"calls": 1, "preview": 0, "cc_cut": 1, "chars": len(
        "head... Output too large. saved to tool-results/x.txt")}
    assert s["calls"][0]["prompt"] == 20005


def test_rehearsal_end_to_end(tmp_path):
    out = tmp_path / "out"  # given relative below: every path handed to a session must still be absolute
    env = {**os.environ, "HOME": str(tmp_path / "home")}
    (tmp_path / "home").mkdir()
    subprocess.run([sys.executable, str(ROOT / "scripts" / "run_cc_test.py"), "--cell", "N", "--arms", "A", "A2", "V2",
                    "--instances", "1", "--days", "2", "--gap-min", "0", "--claude-bin",
                    str(ROOT / "scripts" / "fake_claude.py"), "--fake-mode", "oracle", "--out", "out",
                    "--work-base", str(tmp_path / "base"), "--isolation", ISOLATION],
                   check=True, capture_output=True, text=True, env=env, timeout=300, cwd=tmp_path)
    cfg = json.loads((out / "runs" / "N-V2-i0" / "config.json").read_text())
    assert cfg["isolation"] == ISOLATION
    assert all(Path(cfg["env"][k]).is_absolute() for k in ("AUTOMEM_DATA", "AUTOMEM_STORE", "AUTOMEM_TIMING_LOG"))
    assert not list((tmp_path / "base").iterdir())  # private areas archived and deleted
    rows = [json.loads(line) for line in (out / "rows.jsonl").read_text().splitlines()]
    assert {r["arm"] for r in rows} == {"A", "A2", "V2"} and all(r["correct"] == 14 for r in rows)
    assert not list((tmp_path / "home" / ".claude" / "projects").glob("*cct*"))  # project folders archived, removed
    v2 = out / "runs" / "N-V2-i0"
    assert (v2 / "snapshots" / "day_02" / "store" / "notes.json").exists() and (v2 / "hook_timing.jsonl").exists()
    report = subprocess.run([sys.executable, str(ROOT / "scripts" / "analyze_cc_test.py"), str(out), "--gates"],
                            check=True, capture_output=True, text=True, env=env).stdout
    assert "| V2 vs A | the verdict |" in report and "| G1 logging | PASS |" in report and "| G2 isolation | PASS |" in report


def test_rehearsal_long_session_with_inbox(tmp_path):
    """R100 with the inbox: the stand-in reads every message, the resumed session compacts, the test's own code is
    hidden from the session, and the gates read it."""
    env = {**os.environ, "HOME": str(tmp_path / "home")}
    (tmp_path / "home").mkdir()
    subprocess.run([sys.executable, str(ROOT / "scripts" / "run_cc_test.py"), "--cell", "R100", "--arms", "A", "Aplus",
                    "V2", "--instances", "1", "--days", "3", "--gap-min", "0", "--claude-bin",
                    str(ROOT / "scripts" / "fake_claude.py"), "--fake-mode", "oracle", "--out", str(tmp_path / "out"),
                    "--work-base", str(tmp_path / "base"), "--isolation", ISOLATION, "--cap-usd", "50"],
                   check=True, capture_output=True, text=True, env=env, timeout=300, cwd=tmp_path)
    rows = [json.loads(line) for line in (tmp_path / "out" / "rows.jsonl").read_text().splitlines()]
    assert {r["arm"] for r in rows} == {"A", "Aplus", "V2"} and all(r["correct"] == 21 for r in rows)
    assert all(r["compactions"] >= 1 for r in rows)
    assert all(d["inbox_reads"] >= 10 for r in rows for d in r["days"])
    if ISOLATION == "namespace":  # the stand-in listed the repository's scripts folder: empty inside the session
        import gzip
        with gzip.open(tmp_path / "out" / "runs" / "R100-A-i0" / "day_01.stream.jsonl.gz", "rt") as fh:
            lines = fh.read().splitlines()
        listing = [b["content"] for e in map(json.loads, lines) if e.get("type") == "user"
                   for b in e["message"]["content"] if b.get("tool_use_id", "").endswith("_ls")]
        assert listing == [""]
    report = subprocess.run([sys.executable, str(ROOT / "scripts" / "analyze_cc_test.py"), str(tmp_path / "out"),
                             "--gates"], check=True, capture_output=True, text=True, env=env).stdout
    assert "| G2 isolation | PASS |" in report and "| G6 grader | PASS |" in report and "| G7 noise | N/A |" in report


def test_spending_cap_stops_new_sessions(tmp_path):
    env = {**os.environ, "HOME": str(tmp_path / "home")}
    (tmp_path / "home").mkdir()
    subprocess.run([sys.executable, str(ROOT / "scripts" / "run_cc_test.py"), "--cell", "N", "--arms", "A",
                    "--instances", "2", "--parallel", "1", "--days", "3", "--gap-min", "0", "--claude-bin",
                    str(ROOT / "scripts" / "fake_claude.py"), "--fake-mode", "oracle", "--out", str(tmp_path / "out"),
                    "--work-base", str(tmp_path / "base"), "--isolation", ISOLATION, "--cap-usd", "0.0001"],
                   check=True, capture_output=True, text=True, env=env, timeout=300, cwd=tmp_path)
    rows = [json.loads(line) for line in (tmp_path / "out" / "rows.jsonl").read_text().splitlines()]
    assert len(rows) == 1 and rows[0]["discarded"].startswith("spending cap") and len(rows[0]["days"]) == 1
