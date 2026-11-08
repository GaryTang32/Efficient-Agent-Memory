"""Pilot: Claude Code itself (headless, its own tools and agent loop) on SWE-bench Verified Django issues, with and
without the AutoMemory plugin (plugins/automem). One fresh session per issue in its own git worktree; graded as
SWE-bench grades (eam/bench/tasks/swe_env.py). Same prompt, tools and spending cap for both settings.

    python scripts/run_cc_pilot.py --model haiku --issues 20 --workers 2 --out results/cc_pilot-haiku.jsonl
"""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import tempfile
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from eam.bench.tasks import swe_env as E  # noqa: E402
from eam.bench.tasks.swe_workday import validated  # noqa: E402

PLUGIN = ROOT / "plugins" / "automem"
TOOLS = "Bash Read Edit Write Grep Glob"
PROMPT = """You are working in a checkout of the Django repository at the commit where this issue was reported (your \
current directory). Fix the issue by changing the library code. Do not add or edit tests: hidden tests will check \
your fix.

Run Django's tests with:
    PYTHONPATH=. {py} tests/runtests.py --parallel 1 -v 2 <test labels>
for example `PYTHONPATH=. {py} tests/runtests.py --parallel 1 -v 2 admin_views.tests.AdminViewBasicTest`.

When the fix is done, reply with a short summary of the change.

Issue ({iid}):

{issue}"""


def parse_stream(lines: list[str]) -> dict:
    """Per-call prompt sizes (deduplicated by message id), tool calls, previews, and the final result event."""
    calls, result, tool_calls, am_previews, cc_saved = {}, {}, 0, 0, 0
    for line in lines:
        try:
            ev = json.loads(line)
        except json.JSONDecodeError:
            continue
        if ev.get("type") == "assistant":
            msg = ev.get("message") or {}
            u = msg.get("usage") or {}
            calls[msg.get("id")] = (u.get("input_tokens", 0) + u.get("cache_read_input_tokens", 0)
                                    + u.get("cache_creation_input_tokens", 0))
            tool_calls += sum(1 for b in msg.get("content") or [] if b.get("type") == "tool_use")
        elif ev.get("type") == "user":
            for b in (ev.get("message") or {}).get("content") or []:
                if isinstance(b, dict) and b.get("type") == "tool_result":
                    text = json.dumps(b.get("content"))
                    am_previews += "[AutoMemory:" in text
                    cc_saved += "tool-results/" in text and "[AutoMemory:" not in text
        elif ev.get("type") == "result":
            result = ev
    return {"calls": len(calls), "peak_prompt": max(calls.values(), default=0), "tool_calls": tool_calls,
            "automem_previews": am_previews, "cc_saved_outputs": cc_saved, "result": result}


def run_one(iid: str, setting: str, model: str, budget: float, inst: dict) -> dict:
    d = E.worktree(inst["base_commit"])
    data = Path(tempfile.mkdtemp(prefix="automem-pilot-"))
    t0 = time.time()
    row = {"instance_id": iid, "setting": setting, "model": model}
    try:
        cmd = ["claude", "-p", PROMPT.format(py=E.VENV_PY, iid=iid, issue=inst["problem_statement"].strip()),
               "--model", model, "--output-format", "stream-json", "--verbose", "--allowedTools", TOOLS,
               "--setting-sources", "", "--strict-mcp-config", "--max-budget-usd", str(budget)]
        if setting == "plugin":
            cmd += ["--plugin-dir", str(PLUGIN)]
        env = {**os.environ, "AUTOMEM_DATA": str(data), "PYTHONDONTWRITEBYTECODE": "1"}
        try:
            p = subprocess.run(cmd, cwd=d, capture_output=True, text=True, timeout=2400, env=env)
            out, err = p.stdout, p.stderr
        except subprocess.TimeoutExpired as exc:
            out, err = (exc.stdout or b"").decode() if isinstance(exc.stdout, bytes) else (exc.stdout or ""), "timeout"
            row["error"] = "timeout after 2400s"
        s = parse_stream(out.splitlines())
        res = s.pop("result")
        u = res.get("usage") or {}
        row.update(s, cost_usd=res.get("total_cost_usd", 0.0), turns=res.get("num_turns"),
                   subtype=res.get("subtype"), is_error=res.get("is_error"),
                   uncached=u.get("input_tokens", 0), cache_read=u.get("cache_read_input_tokens", 0),
                   cache_write=u.get("cache_creation_input_tokens", 0), output=u.get("output_tokens", 0),
                   answer=str(res.get("result", ""))[:400], stderr_tail=err[-300:] if not res else "")
        ok, detail = E.resolved(d, inst)
        row.update(resolved=ok, grade_detail="" if ok else detail[:300])
    except Exception as exc:  # recorded, not fatal: one issue never stops the pilot
        row.setdefault("error", f"{type(exc).__name__}: {exc}")
        row.setdefault("resolved", False)
    finally:
        E.drop_worktree(d)
        row["wall_s"] = round(time.time() - t0)
    return row


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--model", default="haiku")
    ap.add_argument("--settings", nargs="+", default=["plain", "plugin"])
    ap.add_argument("--issues", type=int, default=20)
    ap.add_argument("--first", type=int, default=0)
    ap.add_argument("--workers", type=int, default=2)
    ap.add_argument("--budget", type=float, default=None, help="per-session cap in USD (default: 1 Haiku, 3 others)")
    ap.add_argument("--validation", default=str(ROOT / "results" / "swe_validation_wide.jsonl"))
    ap.add_argument("--out", required=True)
    a = ap.parse_args()
    E.ensure_setup()
    inst = E.instances()
    ids = validated(Path(a.validation))[a.first: a.first + a.issues]
    budget = a.budget or (1.0 if "haiku" in a.model else 3.0)
    out = Path(a.out)
    done = set()
    if out.exists():
        done = {(r["instance_id"], r["setting"]) for r in map(json.loads, out.read_text().splitlines())
                if "error" not in r}
    jobs = [(i, s) for i in ids for s in a.settings if (i, s) not in done]
    print(f"{len(jobs)} sessions ({len(ids)} issues x {a.settings}), model {a.model}, cap ${budget}", flush=True)
    with ThreadPoolExecutor(a.workers) as ex, out.open("a") as f:
        futs = {ex.submit(run_one, i, s, a.model, budget, inst[i]): (i, s) for i, s in jobs}
        for fut in as_completed(futs):
            r = fut.result()
            f.write(json.dumps(r) + "\n")
            f.flush()
            print(f"{r['instance_id']:24s} {r['setting']:7s} resolved={r.get('resolved')} ${r.get('cost_usd', 0):.3f} "
                  f"turns={r.get('turns')} peak={r.get('peak_prompt', 0):,} previews={r.get('automem_previews', 0)} "
                  f"{r.get('error', '')}", flush=True)


if __name__ == "__main__":
    main()
