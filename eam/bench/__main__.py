"""Command line: ``python -m eam.bench <command>``.

Examples::

    # one task, a few technique specs, offline
    python -m eam.bench run --task needle_research -t full -t offload -t cache_layout+offload

    # a whole suite on Bedrock (needs AWS credentials and config/models.json)
    python -m eam.bench suite individual --backend bedrock --model sonnet --aux-model haiku --n 3

    # re-print the comparison table
    python -m eam.bench report results/*.jsonl
"""

from __future__ import annotations

import argparse
import time

from eam.bench.experiments import SUITES
from eam.bench.report import markdown_table
from eam.bench.runner import load_rows, run_suite
from eam.llm.routes import ROUTES


def main(argv: list[str] | None = None) -> None:
    ap = argparse.ArgumentParser(prog="eam-bench")
    sub = ap.add_subparsers(dest="cmd", required=True)

    def common(p):
        p.add_argument("--backend", default="mock", choices=[*ROUTES, "bedrock"],
                       help="how to reach the model (see eam/llm/routes.py); bedrock = converse")
        p.add_argument("--model", default="mock-strong")
        p.add_argument("--aux-model", default=None, help="model for summaries/extraction (default: --model)")
        p.add_argument("--n", type=int, default=2, help="task instances per family")
        p.add_argument("--seed", type=int, default=0)
        p.add_argument("--models-config", default=None)
        p.add_argument("--region", default=None)
        p.add_argument("--out", default=None)

    p_run = sub.add_parser("run", help="run technique specs on one task family")
    p_run.add_argument("--task", required=True)
    p_run.add_argument("-t", "--techniques", action="append", required=True)
    common(p_run)

    p_suite = sub.add_parser("suite", help="run a named suite")
    p_suite.add_argument("name", choices=sorted(SUITES))
    p_suite.add_argument("--only", action="append", help="restrict to these task families")
    common(p_suite)

    p_rep = sub.add_parser("report", help="print the comparison table for result files")
    p_rep.add_argument("files", nargs="+")

    args = ap.parse_args(argv)
    if args.cmd == "report":
        print(markdown_table(load_rows(args.files)))
        return

    if args.cmd == "run":
        plan = {args.task: args.techniques}
    else:
        plan = {k: v for k, v in SUITES[args.name].items() if not args.only or k in args.only}
    out = args.out or f"results/{args.cmd}-{args.backend}-{args.model}-{time.strftime('%Y%m%d-%H%M%S')}.jsonl"
    rows = run_suite(plan, backend=args.backend, model_key=args.model, aux_key=args.aux_model, n=args.n,
                     seed=args.seed, out=out, models_path=args.models_config, region=args.region)
    print()
    print(markdown_table(rows))
    print(f"\nrows written to {out}")


if __name__ == "__main__":
    main()
