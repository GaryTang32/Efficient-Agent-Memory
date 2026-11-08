"""Long-session pilot: one Claude Code session (headless, its own tools and loop) works through a queue of SWE-bench
Verified Django issues, one user turn per issue (`--resume`), so its context accumulates the way a working day does.
Each issue has its own git worktree in a subfolder of the session's directory. The prompt asks for the complete test
module(s) of the changed app before finishing an issue (long logs), and compaction is moved to 100K tokens
(CLAUDE_CODE_AUTO_COMPACT_WINDOW, Claude Code's minimum) so it can fire. Same prompts, tools, window and spending cap
with and without the AutoMemory plugin; graded as SWE-bench grades.

    python scripts/run_cc_long.py --model sonnet --workdays 6 --issues 5 --first 20 --out results/cc_long-sonnet.jsonl
"""

from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import sys
import tempfile
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "scripts"))
from eam.bench.tasks import swe_env as E  # noqa: E402
from eam.bench.tasks.swe_workday import validated  # noqa: E402
from run_cc_pilot import PLUGIN, TOOLS  # noqa: E402

FIRST = """You will work through a queue of {n} Django issues in this session, one at a time; the next one arrives \
when you finish. Each issue has its own checkout of the Django repository, at the commit where it was reported, in a \
subfolder of the current directory. Fix each issue by changing the library code in its checkout. Do not add or edit \
tests: hidden tests will check your fix.

Run Django's tests from inside the issue's checkout:
    cd issueK && PYTHONPATH=. {py} tests/runtests.py --parallel 1 -v 2 <test labels>
Before you finish an issue, run the complete test module(s) of the app you changed (for example `admin_views`, not \
one test class) and check the result. Then reply with a short summary of the change.

Issue 1 of {n}, in ./issue1 ({iid}):

{issue}"""
NEXT = """Next: issue {k} of {n}, in ./issue{k} ({iid}). Same rules as before: library code only in ./issue{k}, run the \
complete test module(s) of the app you changed before finishing, then reply with a short summary.

{issue}"""


def parse(lines: list[str]) -> dict:
    calls, res, tools, am, saved, compacts, sid, cmds, outlen = {}, {}, 0, 0, 0, 0, None, [], []
    for line in lines:
        try:
            ev = json.loads(line)
        except json.JSONDecodeError:
            continue
        t = ev.get("type")
        sid = ev.get("session_id") or sid
        if t == "assistant":
            m = ev.get("message") or {}
            u = m.get("usage") or {}
            calls[m.get("id")] = (u.get("input_tokens", 0) + u.get("cache_read_input_tokens", 0)
                                  + u.get("cache_creation_input_tokens", 0))
            for b in m.get("content") or []:
                if b.get("type") == "tool_use":
                    tools += 1
                    if b.get("name") == "Bash":
                        cmds.append(str((b.get("input") or {}).get("command", ""))[:160])
        elif t == "user":
            for b in (ev.get("message") or {}).get("content") or []:
                if isinstance(b, dict) and b.get("type") == "tool_result":
                    s = json.dumps(b.get("content"))
                    outlen.append(len(s))
                    am += "[AutoMemory:" in s
                    saved += "tool-results/" in s and "[AutoMemory:" not in s
        elif t == "system" and "compact" in str(ev.get("subtype", "")):
            compacts += 1
        elif t == "result":
            res = ev
    return {"calls": len(calls), "peak": max(calls.values(), default=0), "tools": tools, "previews": am,
            "cc_saved": saved, "compactions": compacts, "result": res, "session_id": sid, "bash": cmds,
            "max_tool_result_chars": max(outlen, default=0)}


def run_workday(w: int, setting: str, model: str, ids: list[str], inst: dict, budget: float) -> dict:
    base = Path(tempfile.mkdtemp(prefix=f"eam-cc-long-{w}-{setting}-"))
    data = Path(tempfile.mkdtemp(prefix="automem-long-"))
    dirs = []
    t0 = time.time()
    row = {"workday": w, "setting": setting, "model": model, "issues": ids, "turns": []}
    try:
        for k, iid in enumerate(ids, 1):
            d = base / f"issue{k}"
            subprocess.run(["git", "-C", str(E.REPO), "worktree", "add", "-q", "--detach", str(d),
                            inst[iid]["base_commit"]], check=True, capture_output=True)
            dirs.append(d)
        env = {**os.environ, "AUTOMEM_DATA": str(data), "PYTHONDONTWRITEBYTECODE": "1",
               "CLAUDE_CODE_AUTO_COMPACT_WINDOW": "100000"}
        sid = None
        for k, iid in enumerate(ids, 1):
            issue = inst[iid]["problem_statement"].strip()
            prompt = (FIRST.format(n=len(ids), py=E.VENV_PY, iid=iid, issue=issue) if k == 1
                      else NEXT.format(k=k, n=len(ids), iid=iid, issue=issue))
            cmd = ["claude", "-p", prompt, "--model", model, "--output-format", "stream-json", "--verbose",
                   "--allowedTools", TOOLS, "--setting-sources", "", "--strict-mcp-config",
                   "--max-budget-usd", str(budget)]
            if sid:
                cmd += ["--resume", sid]
            if setting == "plugin":
                cmd += ["--plugin-dir", str(PLUGIN)]
            try:
                p = subprocess.run(cmd, cwd=base, capture_output=True, text=True, timeout=3600, env=env)
                out = p.stdout
            except subprocess.TimeoutExpired as exc:
                out = exc.stdout.decode() if isinstance(exc.stdout, bytes) else (exc.stdout or "")
                row.setdefault("errors", []).append(f"issue {k}: timeout")
            s = parse(out.splitlines())
            r = s.pop("result")
            sid = s.pop("session_id") or sid
            u = r.get("usage") or {}
            # with --resume, total_cost_usd is the session's running total: a turn's own cost is the increase
            # (a turn without a result event, e.g. a timeout, carries the last total forward and is marked unknown)
            prev = row["turns"][-1]["cum_cost_usd"] if row["turns"] else 0.0
            known = r.get("total_cost_usd") is not None
            cum = float(r["total_cost_usd"]) if known else prev
            row["turns"].append({"issue": iid, **s, "cum_cost_usd": cum, "cost_usd": max(0.0, cum - prev),
                                 "cost_unknown": not known,
                                 "num_turns": r.get("num_turns"), "subtype": r.get("subtype"),
                                 "uncached": u.get("input_tokens", 0), "cache_read": u.get("cache_read_input_tokens", 0),
                                 "cache_write": u.get("cache_creation_input_tokens", 0),
                                 "output": u.get("output_tokens", 0)})
            if not sid:
                row.setdefault("errors", []).append(f"issue {k}: no session id")
                break
        for k, (iid, d) in enumerate(zip(ids, dirs), 1):
            if k > len(row["turns"]):  # the session stopped before this issue
                break
            ok, _ = E.resolved(d, inst[iid])
            row["turns"][k - 1]["resolved"] = ok
    except Exception as exc:
        row.setdefault("errors", []).append(f"{type(exc).__name__}: {exc}")
    finally:
        for d in dirs:
            E.drop_worktree(d)
        shutil.rmtree(base, ignore_errors=True)
        shutil.rmtree(data, ignore_errors=True)
    t = row["turns"]
    row.update(resolved=sum(bool(x.get("resolved")) for x in t), cost_usd=sum(x["cost_usd"] for x in t),
               peak=max((x["peak"] for x in t), default=0), previews=sum(x["previews"] for x in t),
               cc_saved=sum(x["cc_saved"] for x in t), compactions=sum(x["compactions"] for x in t),
               wall_s=round(time.time() - t0))
    return row


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--model", default="haiku")
    ap.add_argument("--settings", nargs="+", default=["plain", "plugin"])
    ap.add_argument("--workdays", type=int, default=6)
    ap.add_argument("--issues", type=int, default=5)
    ap.add_argument("--first", type=int, default=20, help="first issue index in the validated set")
    ap.add_argument("--workers", type=int, default=2)
    ap.add_argument("--budget", type=float, default=None, help="per-turn cap in USD (default 1 Haiku, 3 others)")
    ap.add_argument("--validation", default=str(ROOT / "results" / "swe_validation_wide.jsonl"))
    ap.add_argument("--out", required=True)
    a = ap.parse_args()
    E.ensure_setup()
    inst = E.instances()
    ids = validated(Path(a.validation))
    budget = a.budget or (1.0 if "haiku" in a.model else 3.0)
    out = Path(a.out)
    done = {(r["workday"], r["setting"]) for r in map(json.loads, out.read_text().splitlines())
            if not r.get("errors")} if out.exists() else set()
    jobs = [(w, s) for w in range(a.workdays) for s in a.settings if (w, s) not in done]
    print(f"{len(jobs)} sessions of {a.issues} issues, model {a.model}", flush=True)
    with ThreadPoolExecutor(a.workers) as ex, out.open("a") as f:
        futs = [ex.submit(run_workday, w, s, a.model, ids[a.first + w * a.issues: a.first + (w + 1) * a.issues], inst,
                          budget) for w, s in jobs]
        for fut in as_completed(futs):
            r = fut.result()
            f.write(json.dumps(r) + "\n")
            f.flush()
            print(f"workday {r['workday']} {r['setting']:6s} resolved={r['resolved']}/{len(r['issues'])} "
                  f"${r['cost_usd']:.3f} peak={r['peak']:,} compactions={r['compactions']} previews={r['previews']} "
                  f"cc_saved={r['cc_saved']} {r.get('errors', '')}", flush=True)


if __name__ == "__main__":
    main()
