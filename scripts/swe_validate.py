"""Validate SWE-bench Verified Django 4.2/5.0 instances in this environment: FAIL_TO_PASS must fail without the gold
patch, and FAIL_TO_PASS + PASS_TO_PASS must all pass with it. Writes one JSON line per instance.

    python scripts/swe_validate.py results/swe_validation.jsonl [workers]
"""

import json
import sys
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from eam.bench.tasks import swe_env as E  # noqa: E402

OUT = Path(sys.argv[1] if len(sys.argv) > 1 else "results/swe_validation.jsonl")
WORKERS = int(sys.argv[2]) if len(sys.argv) > 2 else 4
E.ensure_setup()
I = E.instances()
done = {json.loads(l)["instance_id"] for l in OUT.read_text().splitlines()} if OUT.exists() else set()
cand = sorted(i for i, r in I.items() if r["repo"] == "django/django" and r["version"] in ("4.2", "5.0")
              and r["difficulty"] != "1-4 hours" and i not in done)


def check(iid):
    r = I[iid]
    t0 = time.time()
    d = E.worktree(r["base_commit"])
    try:
        E.apply_patch(d, r["test_patch"])
        code0, _ = E.run_tests(d, E.labels(json.loads(r["FAIL_TO_PASS"])))
    finally:
        E.drop_worktree(d)
    d = E.worktree(r["base_commit"])
    try:
        ok_gold = E.apply_patch(d, r["patch"])
        res, out = E.resolved(d, r)
    finally:
        E.drop_worktree(d)
    return {"instance_id": iid, "version": r["version"], "difficulty": r["difficulty"], "fails_before": code0 != 0,
            "passes_with_gold": bool(ok_gold and res), "seconds": round(time.time() - t0),
            "tail": "" if res else out[-400:]}


with ThreadPoolExecutor(WORKERS) as ex, OUT.open("a") as f:
    for row in ex.map(check, cand):
        f.write(json.dumps(row) + "\n")
        f.flush()
        print(row["instance_id"], row["fails_before"], row["passes_with_gold"], row["seconds"], flush=True)
