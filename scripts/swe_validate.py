"""Validate SWE-bench Verified instances (Django unless SWE_REPO names another repository) in this environment:
FAIL_TO_PASS must fail without the gold patch, and FAIL_TO_PASS + PASS_TO_PASS must all pass with it. Writes one JSON line per instance (appends; instances
already in the file are skipped).

    python scripts/swe_validate.py results/swe_validation.jsonl [workers]
    SWE_VERSIONS=4.0,4.1,4.2,5.0 SWE_DIFFICULTY=all python scripts/swe_validate.py results/swe_validation_wide.jsonl 4

    SWE_REPO=sympy/sympy SWE_VERSIONS=all SWE_DIFFICULTY=all python scripts/swe_validate.py results/swe_validation_sympy.jsonl 4

Defaults: Django 4.2 and 5.0, difficulty below "1-4 hours" (the 40-issue set of 2026-11-05).
"""

import json
import os
import sys
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from eam.bench.tasks import swe_env as E  # noqa: E402

OUT = Path(sys.argv[1] if len(sys.argv) > 1 else "results/swe_validation.jsonl")
WORKERS = int(sys.argv[2]) if len(sys.argv) > 2 else 4
REPO = os.environ.get("SWE_REPO", E.DJANGO)
E.ensure_setup(REPO)
I = E.instances()
done = {json.loads(l)["instance_id"] for l in OUT.read_text().splitlines()} if OUT.exists() else set()
VERSIONS = os.environ.get("SWE_VERSIONS", "4.2,5.0").split(",")
ALL_DIFFICULTIES = os.environ.get("SWE_DIFFICULTY", "") == "all"
cand = sorted(i for i, r in I.items() if r["repo"] == REPO and ("all" in VERSIONS or r["version"] in VERSIONS)
              and (ALL_DIFFICULTIES or r["difficulty"] != "1-4 hours") and i not in done)


def check(iid):
    r = I[iid]
    t0 = time.time()
    d = E.worktree(r["base_commit"], REPO)
    try:
        before = E.evaluate(d, r)  # without the fix: every FAIL_TO_PASS test must fail
    finally:
        E.drop_worktree(d)
    d = E.worktree(r["base_commit"], REPO)
    try:
        ok_gold = E.apply_patch(d, r["patch"])
        res, out = E.resolved(d, r)
    finally:
        E.drop_worktree(d)
    return {"instance_id": iid, "version": r["version"], "difficulty": r["difficulty"], "fails_before": bool(before) and not before["f2p_passed"],
            "passes_with_gold": bool(ok_gold and res), "seconds": round(time.time() - t0),
            "tail": "" if res else out[-400:]}


with ThreadPoolExecutor(WORKERS) as ex, OUT.open("a") as f:
    for fut in as_completed([ex.submit(check, c) for c in cand]):
        row = fut.result()
        f.write(json.dumps(row) + "\n")
        f.flush()
        print(row["instance_id"], row["fails_before"], row["passes_with_gold"], row["seconds"], flush=True)
