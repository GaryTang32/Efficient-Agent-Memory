"""SWE-bench Verified workdays (task swe_workday) through the Claude Code CLI.

    python scripts/run_swe.py --model cc-haiku --specs naive@native automem_v2 --workdays 2 --issues 5 \
        --window 64000 --workers 2 --out results/swe-haiku.jsonl
"""
import argparse
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from eam.bench.runner import run_suite  # noqa: E402

p = argparse.ArgumentParser()
p.add_argument("--model", default="cc-haiku")
p.add_argument("--aux-model", default=None)
p.add_argument("--specs", nargs="+", required=True)
p.add_argument("--workdays", type=int, default=1)
p.add_argument("--first", type=int, default=0)
p.add_argument("--issues", type=int, default=5)
p.add_argument("--window", type=int, default=64000)
p.add_argument("--workers", type=int, default=2)
p.add_argument("--out", required=True)
a = p.parse_args()
os.environ.setdefault("EAM_CLAUDE_TIMEOUT", "900")
run_suite({"swe_workday": a.specs}, backend="claude-cli", model_key=a.model, aux_key=a.aux_model or a.model,
          n=a.workdays, seed=a.first, out=a.out, workers=a.workers, resume=True,
          task_kwargs={"swe_workday": {"n_issues": a.issues, "context_limit": a.window}})
