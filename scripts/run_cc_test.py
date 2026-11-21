"""Runner for the Claude Code test plan (docs/plans/2026-11-21-automem-vs-claude-code-autocompact.md).

Headless Claude Code, one run per (cell, arm, instance). All arms of an instance run each day together, then wait for
the day gap (cold prompt cache) before the next day. Everything is logged raw under --out (git-ignored):

    <out>/rows.jsonl                     one summary row per run (per-day results inside)
    <out>/runs/<run>/config.json         arm, cell, model, seed, Claude Code version, plugin commit, environment
    <out>/runs/<run>/day_NN.stream.jsonl.gz   Claude Code's full event stream for the day
    <out>/runs/<run>/day_NN.calls.jsonl  one line per model call: prompt size, cache reads/writes, uncached, output
    <out>/runs/<run>/transcripts/        Claude Code's own session transcripts (compaction summaries included)
    <out>/runs/<run>/snapshots/day_NN/   memory stores after the day: Claude Code auto memory, AutoMemory store,
                                         the plugin's data, NOTES.md
    <out>/runs/<run>/hook_timing.jsonl   plugin hook calls with their durations (plugin arms)
    <out>/runs/<run>/key.json            the answer key, written only after the run

    python scripts/run_cc_test.py --cell N --arms A A2 A0 Aplus L V2 --instances 2 --days 5 --out results/cc_test/pilot
    python scripts/run_cc_test.py ... --claude-bin scripts/fake_claude.py --gap-min 0     # offline rehearsal

Arms: A (Claude Code defaults, auto memory on), A2 (a copy of A), A0 (auto memory off), Aplus (A + NOTES.md
prompt), L (A + plugin, lean), V2 (A + plugin, full mode + automem-mcp note tools). Cells: N (F1, new session per day,
compaction window 500K), R100 / R500 (F1, one resumed session, 100K / 500K), F2 (SWE-bench workdays, new session per
issue, 500K).
"""

from __future__ import annotations

import argparse
import gzip
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "scripts"))
import cc_ledger as L  # noqa: E402

PLUGIN = ROOT / "plugins" / "automem"
TOOLS = ["Bash", "Read", "Edit", "Write", "Grep", "Glob"]
NOTE_TOOLS = ["mcp__automem__write_note", "mcp__automem__read_notes", "mcp__automem__read_artifact"]
ARMS = {
    "A": {"auto_memory": True},
    "A2": {"auto_memory": True},
    "A0": {"auto_memory": False},
    "Aplus": {"auto_memory": True, "notes_prompt": True},
    "L": {"auto_memory": True, "plugin": "lean"},
    "V2": {"auto_memory": True, "plugin": "full"},
}
CELLS = {
    "N": {"task": "F1", "mode": "new", "window": 500_000},
    "R100": {"task": "F1", "mode": "resume", "window": 100_000},
    "R500": {"task": "F1", "mode": "resume", "window": 500_000},
    "F2": {"task": "F2", "mode": "new", "window": 500_000},
}
# the only variables passed on from this machine: path, home (Claude Code's credentials), proxy and certificates
PASS_ENV = ["PATH", "HOME", "HTTPS_PROXY", "https_proxy", "NO_PROXY", "no_proxy", "NODE_EXTRA_CA_CERTS", "SSL_CERT_FILE"]
SECRET = re.compile(r"(TOKEN|KEY|SECRET|PASSWORD|CREDENTIAL)", re.I)
LOCK = threading.Lock()


# ---- environment and command ----------------------------------------------------------------------------------
def child_env(arm: str, cell: str, run_dir: Path, tmp: Path, extra: dict | None = None) -> dict:
    a, c = ARMS[arm], CELLS[cell]
    env = {k: os.environ[k] for k in PASS_ENV if k in os.environ}
    env.update({"LANG": "C.UTF-8", "TERM": "dumb", "TMPDIR": str(tmp), "DISABLE_AUTOUPDATER": "1",
                "PYTHONDONTWRITEBYTECODE": "1", "CLAUDE_CODE_AUTO_COMPACT_WINDOW": str(c["window"]),
                "CLAUDE_CODE_DISABLE_AUTO_MEMORY": "0" if a["auto_memory"] else "1"})
    if a.get("plugin"):
        env.update({"AUTOMEM_DATA": str(run_dir / "automem_data"), "AUTOMEM_TIMING_LOG": str(run_dir / "hook_timing.jsonl")})
        if a["plugin"] == "lean":
            env["AUTOMEM_NOTES"] = "off"
        else:
            env.update({"AUTOMEM_WORKSPACE": "on", "AUTOMEM_STORE": str(run_dir / "store")})
    env.update(extra or {})
    return env


def mcp_config(run_dir: Path, window: int) -> Path:
    path = run_dir / "mcp.json"
    path.write_text(json.dumps({"mcpServers": {"automem": {
        "command": sys.executable, "args": ["-m", "eam.mcp_server"],
        "env": {"EAM_MEMORY_DIR": str(run_dir / "store"), "EAM_MEMORY_WINDOW": str(window), "PYTHONPATH": str(ROOT),
                "EAM_MEMORY_TOOLS": "write_note,read_notes,read_artifact"}}}},
        indent=1))
    return path


def command(claude: list[str], prompt: str, arm: str, run_dir: Path, window: int, model: str, budget: float,
            sid: str | None) -> list[str]:
    tools = TOOLS + (NOTE_TOOLS if ARMS[arm].get("plugin") == "full" else [])
    cmd = [*claude, "-p", prompt, "--model", model, "--output-format", "stream-json", "--verbose",
           "--setting-sources", "", "--strict-mcp-config", "--max-budget-usd", str(budget),
           "--allowedTools", " ".join(tools)]
    if ARMS[arm].get("plugin"):
        cmd += ["--plugin-dir", str(PLUGIN)]
    if ARMS[arm].get("plugin") == "full":
        cmd += ["--mcp-config", str(mcp_config(run_dir, window))]
    if sid:
        cmd += ["--resume", sid]
    return cmd


# ---- reading Claude Code's event stream ----------------------------------------------------------------------
def _text_of(content) -> str:
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        return "".join(b.get("text", "") if isinstance(b, dict) else str(b) for b in content)
    return ""


def parse_stream(lines: list[str], cwd: Path) -> dict:
    calls, tool_calls, results = {}, {}, []
    sid, result, compactions, micro, init = None, {}, [], 0, {}
    for line in lines:
        try:
            ev = json.loads(line)
        except (json.JSONDecodeError, ValueError):
            continue
        t = ev.get("type")
        sid = ev.get("session_id") or sid
        if t == "system" and ev.get("subtype") == "init":
            init = {"model": ev.get("model"), "tools": len(ev.get("tools") or []),
                    "mcp_servers": [s.get("name") for s in ev.get("mcp_servers") or [] if isinstance(s, dict)],
                    "plugins": [p.get("name") if isinstance(p, dict) else p for p in ev.get("plugins") or []]}
        elif t == "system" and "compact_boundary" in str(ev.get("subtype", "")):
            meta = ev.get("compact_metadata") or ev.get("compactMetadata") or {}
            if "micro" in str(ev.get("subtype")):
                micro += 1
            else:
                compactions.append({"trigger": meta.get("trigger"), "pre_tokens": meta.get("pre_tokens")})
        elif t == "assistant":
            m = ev.get("message") or {}
            u = m.get("usage") or {}
            calls[m.get("id")] = {"input": u.get("input_tokens", 0), "cache_read": u.get("cache_read_input_tokens", 0),
                                  "cache_write": u.get("cache_creation_input_tokens", 0),
                                  "output": u.get("output_tokens", 0)}
            for b in m.get("content") or []:
                if isinstance(b, dict) and b.get("type") == "tool_use":
                    tool_calls[b.get("id")] = {"name": b.get("name"), "input": b.get("input") or {}}
        elif t == "user":
            for b in (ev.get("message") or {}).get("content") or []:
                if isinstance(b, dict) and b.get("type") == "tool_result":
                    s = _text_of(b.get("content"))
                    results.append({"id": b.get("tool_use_id"), "chars": len(s), "preview": "[AutoMemory:" in s,
                                    "cc_cut": ("tool-results/" in s or "Output too large" in s) and "[AutoMemory:" not in s})
        elif t == "result":
            result = ev
    for c in calls.values():
        c["prompt"] = c["input"] + c["cache_read"] + c["cache_write"]
    by_id = {r["id"]: r for r in results}
    bash = [str(tc["input"].get("command", "")) for tc in tool_calls.values() if tc["name"] == "Bash"]
    paths = [str(tc["input"].get("file_path") or tc["input"].get("path") or "") for tc in tool_calls.values()]
    names = [tc["name"] for tc in tool_calls.values()]
    kinds: dict[str, dict] = {}
    for i, tc in tool_calls.items():
        m = re.search(r"report\.py\s+(\w+)", str(tc["input"].get("command", ""))) if tc["name"] == "Bash" else None
        if m:
            k = kinds.setdefault(m.group(1), {"calls": 0, "preview": 0, "cc_cut": 0, "chars": 0})
            r = by_id.get(i, {})
            k["calls"] += 1
            k["preview"] += bool(r.get("preview"))
            k["cc_cut"] += bool(r.get("cc_cut"))
            k["chars"] += r.get("chars", 0)
    home_projects = str(Path.home() / ".claude" / "projects")
    own_project = project_dir(cwd).name
    outside = [x for x in bash + paths if home_projects in x and own_project not in x]
    return {
        "session_id": sid, "result": result, "init": init, "calls": list(calls.values()),
        "turns": result.get("num_turns"), "subtype": result.get("subtype"), "final_text": result.get("result") or "",
        "compactions": compactions, "microcompacts": micro,
        "tool_calls": len(tool_calls), "tool_names": {n: names.count(n) for n in set(names)},
        "tool_result_chars": [r["chars"] for r in results],
        "previews": sum(r["preview"] for r in results), "cc_cut": sum(r["cc_cut"] for r in results),
        "report_calls": sum("report.py" in b for b in bash),
        "report_previews": sum(by_id.get(i, {}).get("preview", False) for i, tc in tool_calls.items()
                               if tc["name"] == "Bash" and "report.py" in str(tc["input"].get("command", ""))),
        "report_cc_cut": sum(by_id.get(i, {}).get("cc_cut", False) for i, tc in tool_calls.items()
                             if tc["name"] == "Bash" and "report.py" in str(tc["input"].get("command", ""))),
        "report_kinds": kinds,
        "note_writes": names.count("mcp__automem__write_note"), "note_reads": names.count("mcp__automem__read_notes"),
        "notes_md_writes": sum(p.endswith("NOTES.md") for p in paths) + sum("NOTES.md" in b and ">" in b for b in bash),
        "auto_memory_writes": sum("/memory/" in p and home_projects in p for p in paths),
        "isolation_flags": outside,
        "assistant_events": len(calls),
    }


def project_dir(cwd: Path) -> Path:
    """Claude Code's project folder for `cwd`: every character that is not a letter or digit becomes '-'."""
    return Path.home() / ".claude" / "projects" / re.sub(r"[^A-Za-z0-9]", "-", str(cwd))


# ---- one day of one run ------------------------------------------------------------------------------------------
def run_day(claude: list[str], run: dict, day: int, prompt: str, sid: str | None, args) -> dict:
    run_dir, cwd = run["dir"], run["cwd"]
    cmd = command(claude, prompt, run["arm"], run_dir, CELLS[run["cell"]]["window"], args.model, args.budget_day, sid)
    t0 = time.time()
    timeout = False
    try:
        p = subprocess.run(cmd, cwd=cwd, env=run["env"], capture_output=True, text=True, timeout=args.timeout_day)
        out, err, code = p.stdout, p.stderr, p.returncode
    except subprocess.TimeoutExpired as exc:
        out = exc.stdout.decode() if isinstance(exc.stdout, bytes) else (exc.stdout or "")
        err, code, timeout = "timeout", None, True
    lines = out.splitlines()
    with gzip.open(run_dir / f"day_{day:02d}.stream.jsonl.gz", "wt", encoding="utf-8") as fh:
        fh.write(out)
    if err.strip():
        (run_dir / f"day_{day:02d}.stderr.txt").write_text(err[-200_000:])
    s = parse_stream(lines, cwd)
    with open(run_dir / f"day_{day:02d}.calls.jsonl", "w") as fh:
        fh.write("".join(json.dumps(c) + "\n" for c in s["calls"]))
    res = s["result"]
    infra = (not timeout and s["assistant_events"] == 0)  # nothing reached the model: an outage or a startup error
    cap = "budget" in str(s["subtype"] or "")
    return {"day": day, "sid": s["session_id"] or sid, "code": code, "timeout": timeout, "cap_hit": cap, "infra": infra,
            "wall_s": round(time.time() - t0, 1), "cum_cost": res.get("total_cost_usd"),
            **{k: v for k, v in s.items() if k not in ("result", "calls", "session_id")},
            "n_calls": len(s["calls"]), "peak_prompt": max((c["prompt"] for c in s["calls"]), default=0),
            "mean_prompt": round(sum(c["prompt"] for c in s["calls"]) / max(1, len(s["calls"]))),
            "tokens": {k: sum(c[k] for c in s["calls"]) for k in ("input", "cache_read", "cache_write", "output")}}


def snapshot(run: dict, day: int, sids: list[str]) -> None:
    snap = run["dir"] / "snapshots" / f"day_{day:02d}"
    snap.mkdir(parents=True, exist_ok=True)
    proj = project_dir(run["cwd"])
    if (proj / "memory").exists():
        shutil.copytree(proj / "memory", snap / "claude_auto_memory", dirs_exist_ok=True)
    for name in ("store", "automem_data"):
        if (run["dir"] / name).exists():
            shutil.copytree(run["dir"] / name, snap / name, dirs_exist_ok=True,
                            ignore=shutil.ignore_patterns("*.lock"))
    if (run["cwd"] / "NOTES.md").exists():
        shutil.copy2(run["cwd"] / "NOTES.md", snap / "NOTES.md")
    tr = run["dir"] / "transcripts"
    tr.mkdir(exist_ok=True)
    for sid in {s for s in sids if s}:
        src = proj / f"{sid}.jsonl"
        if src.exists():
            shutil.copy2(src, tr / src.name)


# ---- F1 runs ---------------------------------------------------------------------------------------------------
def new_run(args, cell: str, arm: str, inst_no: int, seed: int, meta: dict) -> dict:
    name = f"{cell}-{arm}-i{inst_no}"
    run_dir = Path(args.out) / "runs" / name
    if run_dir.exists():
        shutil.rmtree(run_dir)
    run_dir.mkdir(parents=True)
    work_root = Path(tempfile.mkdtemp(prefix="cct-"))  # away from the results: the agent cannot reach other runs' logs
    cwd, tmp = work_root / "work", work_root / "tmp"
    cwd.mkdir()
    tmp.mkdir()
    extra = {}
    if args.fake_mode:
        extra = {"FAKE_MODE": args.fake_mode, "FAKE_KEY": str(Path(args.fake_keys) / f"{name}.json")}
    env = child_env(arm, cell, run_dir, tmp, extra)
    cfg = {"run": name, "cell": cell, "arm": arm, "instance": inst_no, "seed": seed, "model": args.model,
           "days": args.days, "gap_min": args.gap_min, "long_gap": args.long_gap, "budget_day": args.budget_day,
           "timeout_day": args.timeout_day, **CELLS[cell], **ARMS[arm], **meta,
           "env": {k: ("<redacted>" if SECRET.search(k) else v) for k, v in env.items()}}
    (run_dir / "config.json").write_text(json.dumps(cfg, indent=1))
    return {"name": name, "cell": cell, "arm": arm, "instance": inst_no, "seed": seed, "dir": run_dir, "cwd": cwd,
            "work_root": work_root, "env": env, "days": [], "sid": None, "cfg": cfg}


def run_instance_f1(claude: list[str], args, cell: str, arms: list[str], inst_no: int, meta: dict) -> list[dict]:
    seed = args.first_seed + inst_no
    inst = L.generate(seed, days=args.days)
    runs = [new_run(args, cell, arm, inst_no, seed, meta) for arm in arms]
    if args.fake_mode:
        Path(args.fake_keys).mkdir(parents=True, exist_ok=True)
        for r in runs:
            (Path(args.fake_keys) / f"{r['name']}.json").write_text(json.dumps(inst["key"]))
    resume = CELLS[cell]["mode"] == "resume"
    for day in range(1, args.days + 1):
        for r in runs:
            L.release_day(r["cwd"], inst, day)

        def one(r):
            sid = r["sid"] if resume else None
            d = run_day(claude, r, day, L.prompt(inst, day, ARMS[r["arm"]].get("notes_prompt", False)), sid, args)
            d["grade"] = L.grade(d.get("final_text", ""), inst["key"][day - 1])
            prev = r["days"][-1]["cum_cost"] if (resume and r["days"]) else 0.0
            d["cost"] = max(0.0, (d["cum_cost"] or prev or 0.0) - (prev or 0.0)) if resume else (d["cum_cost"] or 0.0)
            r["sid"] = d["sid"]
            r["days"].append(d)
            snapshot(r, day, [x["sid"] for x in r["days"]])
            return d

        with ThreadPoolExecutor(len(runs)) as ex:
            done = list(ex.map(one, runs))
        with LOCK:
            print(f"[{cell} i{inst_no}] day {day}: " + " | ".join(
                f"{r['arm']} {d['grade']['correct']}/7 ${d['cost']:.3f}{' INFRA' if d['infra'] else ''}"
                f"{' CAP' if d['cap_hit'] else ''}{' TIMEOUT' if d['timeout'] else ''}" for r, d in zip(runs, done)),
                flush=True)
        if day < args.days:
            gap = args.gap_min
            if args.long_gap and int(args.long_gap.split(":")[0]) == day:
                gap = float(args.long_gap.split(":")[1])
            time.sleep(gap * 60)
    rows = []
    for r in runs:
        (r["dir"] / "key.json").write_text(json.dumps(inst["key"]))  # only now, after the run
        work = r["dir"] / "work_final"
        shutil.copytree(r["cwd"], work, dirs_exist_ok=True, ignore=shutil.ignore_patterns("today.bin"))
        proj = project_dir(r["cwd"])
        if proj.exists():
            shutil.copytree(proj, r["dir"] / "claude_project", dirs_exist_ok=True)
            shutil.rmtree(proj, ignore_errors=True)
        shutil.rmtree(r["work_root"], ignore_errors=True)
        rows.append(summarize(r))
    return rows


def summarize(r: dict) -> dict:
    days = r["days"]
    correct = sum(d["grade"]["correct"] for d in days)
    total = sum(d["grade"]["total"] for d in days)
    cost = sum(d["cost"] for d in days)
    tok = {k: sum(d["tokens"][k] for d in days) for k in ("input", "cache_read", "cache_write", "output")}
    keep = ("day", "grade", "cost", "wall_s", "turns", "subtype", "timeout", "cap_hit", "infra", "n_calls",
            "peak_prompt", "mean_prompt", "tokens", "compactions", "microcompacts", "previews", "cc_cut",
            "report_calls", "report_previews", "report_cc_cut", "report_kinds", "note_writes", "note_reads", "notes_md_writes",
            "auto_memory_writes", "isolation_flags", "tool_names", "init")
    return {"run": r["name"], "cell": r["cell"], "arm": r["arm"], "instance": r["instance"], "seed": r["seed"],
            "model": r["cfg"]["model"], "claude_version": r["cfg"].get("claude_version"),
            "plugin_commit": r["cfg"].get("plugin_commit"), "correct": correct, "total": total,
            "accuracy": correct / total if total else 0.0, "cost": cost,
            "cost_per_correct": cost / correct if correct else None, "tokens": tok,
            "tokens_per_correct": sum(tok.values()) / correct if correct else None,
            "peak_prompt": max((d["peak_prompt"] for d in days), default=0),
            "compactions": sum(len(d["compactions"]) for d in days),
            "microcompacts": sum(d["microcompacts"] for d in days),
            "infra": any(d["infra"] for d in days), "cap_hits": sum(d["cap_hit"] for d in days),
            "timeouts": sum(d["timeout"] for d in days),
            "days": [{k: d.get(k) for k in keep} for d in days]}


# ---- F2 runs (SWE-bench Verified Django workdays, a new session per issue) ------------------------------------------
F2_PROMPT = """Fix the Django issue below by changing the library code in ./issue{k}, a checkout of the Django \
repository at the commit where the issue was reported. Do not add or edit tests: hidden tests will check your fix. \
Earlier issues of this workday were in the other issue folders here; they are already done.

Run Django's tests from inside the checkout:
    cd issue{k} && PYTHONPATH=. {py} tests/runtests.py --parallel 1 -v 2 <test labels>
Before you finish, run the complete test module(s) of the app you changed and check the result. Then reply with a \
short summary of the change.

Issue ({iid}):

{issue}"""


def run_instance_f2(claude: list[str], args, cell: str, arms: list[str], inst_no: int, meta: dict) -> list[dict]:
    from eam.bench.tasks import swe_env as E
    from eam.bench.tasks.swe_workday import validated

    E.ensure_setup()
    insts = E.instances()
    ids = validated(Path(args.validation))[inst_no * 5: inst_no * 5 + 5]
    runs = [new_run(args, cell, arm, inst_no, inst_no, meta) for arm in arms]
    for r in runs:
        r["dirs"] = []
        for k, iid in enumerate(ids, 1):
            d = r["cwd"] / f"issue{k}"
            subprocess.run(["git", "-C", str(E.REPO), "worktree", "add", "-q", "--detach", str(d),
                            insts[iid]["base_commit"]], check=True, capture_output=True)
            r["dirs"].append(d)
    try:
        for k, iid in enumerate(ids, 1):
            prompt = F2_PROMPT.format(k=k, py=E.VENV_PY, iid=iid, issue=insts[iid]["problem_statement"].strip())

            def one(r):
                d = run_day(claude, r, k, prompt, None, args)
                d["cost"] = d["cum_cost"] or 0.0
                d["issue"] = iid
                r["days"].append(d)
                snapshot(r, k, [x["sid"] for x in r["days"]])
                return d

            with ThreadPoolExecutor(len(runs)) as ex:
                list(ex.map(one, runs))
            time.sleep(args.gap_min * 60 if k < len(ids) else 0)
        for r in runs:
            for d, (iid, wt) in zip(r["days"], zip(ids, r["dirs"])):
                ok, _ = E.resolved(wt, insts[iid])
                d["grade"] = {"parsed": True, "checks": {"resolved": ok}, "correct": int(ok), "total": 1}
    finally:
        rows = []
        for r in runs:
            for wt in r.get("dirs", []):
                E.drop_worktree(wt)
            proj = project_dir(r["cwd"])
            if proj.exists():
                shutil.copytree(proj, r["dir"] / "claude_project", dirs_exist_ok=True)
                shutil.rmtree(proj, ignore_errors=True)
            shutil.rmtree(r["work_root"], ignore_errors=True)
            for d in r["days"]:
                d.setdefault("grade", {"parsed": False, "checks": {"resolved": False}, "correct": 0, "total": 1})
            rows.append(summarize(r))
    return rows


# ---- main ------------------------------------------------------------------------------------------------------------
def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--cell", required=True, choices=list(CELLS))
    ap.add_argument("--arms", nargs="+", required=True, choices=list(ARMS))
    ap.add_argument("--instances", type=int, default=1)
    ap.add_argument("--first-instance", type=int, default=0)
    ap.add_argument("--first-seed", type=int, default=1000)
    ap.add_argument("--days", type=int, default=10)
    ap.add_argument("--gap-min", type=float, default=6.0, help="minutes between days (cold prompt cache)")
    ap.add_argument("--long-gap", default="", help="DAY:MINUTES, e.g. 5:61 for one long gap after day 5")
    ap.add_argument("--model", default="sonnet")
    ap.add_argument("--budget-day", type=float, default=2.0)
    ap.add_argument("--timeout-day", type=int, default=1800)
    ap.add_argument("--parallel", type=int, default=2, help="instances at once (each runs all its arms at once)")
    ap.add_argument("--validation", default=str(ROOT / "results" / "swe_validation_related.jsonl"))
    ap.add_argument("--claude-bin", default="claude")
    ap.add_argument("--fake-mode", default="", help="rehearsal only: oracle | stale (with scripts/fake_claude.py)")
    ap.add_argument("--fake-keys", default="", help="rehearsal only: where the fake reads keys from")
    ap.add_argument("--no-retry", action="store_true", help="do not re-run instances after an infrastructure failure")
    ap.add_argument("--out", required=True)
    a = ap.parse_args()
    a.out = str(Path(a.out).resolve())  # sessions run in their own folders: every path handed to them is absolute
    if a.fake_mode and not a.fake_keys:
        a.fake_keys = str(Path(a.out) / "fake_keys")
    claude = [sys.executable, str(Path(a.claude_bin).resolve())] if a.claude_bin.endswith(".py") else [a.claude_bin]
    version = subprocess.run([*claude, "--version"], capture_output=True, text=True).stdout.strip()
    commit = subprocess.run(["git", "-C", str(ROOT), "rev-parse", "HEAD"], capture_output=True, text=True).stdout.strip()
    dirty = bool(subprocess.run(["git", "-C", str(ROOT), "status", "--porcelain", "plugins", "eam"],
                                capture_output=True, text=True).stdout.strip())
    meta = {"claude_version": version, "plugin_commit": commit + ("+dirty" if dirty else "")}
    Path(a.out).mkdir(parents=True, exist_ok=True)
    runner = run_instance_f2 if CELLS[a.cell]["task"] == "F2" else run_instance_f1
    print(f"{a.cell}: arms {a.arms}, instances {a.first_instance}..{a.first_instance + a.instances - 1}, "
          f"model {a.model}, Claude Code {version}", flush=True)
    def with_retry(i: int) -> list[dict]:
        """The agreed re-run rule: if any session of the instance never reached the model (an outage or a startup
        error), the whole instance is run again for every arm, once; the failed attempt is kept, marked discarded."""
        rows = runner(claude, a, a.cell, a.arms, i, meta)
        if not any(r["infra"] for r in rows) or a.no_retry:
            return rows
        for r in rows:
            src = Path(a.out) / "runs" / r["run"]
            if src.exists():
                src.rename(src.with_name(r["run"] + ".infra-attempt1"))
            r["discarded"] = "infrastructure failure; instance re-run for every arm"
        return rows + runner(claude, a, a.cell, a.arms, i, meta)

    with ThreadPoolExecutor(a.parallel) as ex, open(Path(a.out) / "rows.jsonl", "a") as fh:
        futs = [ex.submit(with_retry, i) for i in range(a.first_instance, a.first_instance + a.instances)]
        for f in futs:
            for row in f.result():
                with LOCK:
                    fh.write(json.dumps(row) + "\n")
                    fh.flush()
                print(f"  {row['run']}: {row['correct']}/{row['total']} ${row['cost']:.3f} compactions "
                      f"{row['compactions']} infra {row['infra']}", flush=True)


if __name__ == "__main__":
    main()
