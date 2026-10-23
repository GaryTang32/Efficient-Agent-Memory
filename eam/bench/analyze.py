"""Result tables for the documentation: `python -m eam.bench.analyze <rows.jsonl>...`.

Groups runs by (task, model, spec) and reports, besides success counts, *medians* (LLM costs are
heavy-tailed: a single run can cost ~7x the usual), per-round scores for multi-round tasks, overflow counts,
the cost split between the agent and technique side calls, and runs that errored (reported, not dropped
silently). Definitions of every column: docs/methodology.md §3.
"""

from __future__ import annotations

import json
import statistics as st
import sys
from collections import defaultdict
from pathlib import Path
from typing import Any


def load(paths: list[str]) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    rows, errors = [], []
    for p in paths:
        for line in Path(p).read_text().splitlines():
            if line.strip():
                r = json.loads(line)
                (errors if "error" in r else rows).append(r)
    return rows, errors


def _med(xs):
    xs = list(xs)
    return st.median(xs) if xs else float("nan")


def table(rows: list[dict[str, Any]], errors: list[dict[str, Any]]) -> str:
    groups: dict[tuple, list] = defaultdict(list)
    for r in rows:
        groups[(r["family"], r["model"], r["spec"])].append(r)
    errs: dict[tuple, int] = defaultdict(int)
    for e in errors:
        errs[(e["family"], e["model"], e["spec"])] += 1
    out = []
    for family in sorted({k[0] for k in groups}):
        n_rounds = max((len(r.get("round_scores") or []) for (f, _, _), rs in groups.items() if f == family
                        for r in rs), default=0)
        multi = n_rounds > 0
        out.append(f"\n### {family}\n")
        head = "| model | method | runs | success | mean score |"
        if multi:
            head += f" score per round (1–{n_rounds}) | overflow |"
        head += (" median $/run | $/success | median prompt tok | median peak ctx | median cache hit | "
                 "median steps | agent $ / side-call $ (median) |")
        out.append(head)
        out.append("|" + "---|" * (head.count("|") - 1))
        base: dict[str, float] = {}  # cost reference per model: `full`, else `naive`
        for ref in ("naive", "full"):
            for (f, m, s), rs in groups.items():
                if f == family and s == ref:
                    base[m] = (_med(r["cost_usd"] for r in rs), ref)
        for (f, m, s), rs in sorted(groups.items(), key=lambda kv: (kv[0][1], -st.mean(r["score"] for r in kv[1]),
                                                                    _med(r["cost_usd"] for r in kv[1]))):
            if f != family:
                continue
            n, succ = len(rs), sum(r["success"] for r in rs)
            cost = sum(r["cost_usd"] for r in rs)
            e = errs.get((f, m, s), 0)
            line = f"| {m} | `{s}` | {n}{f' (+{e} errored)' if e else ''} | {succ}/{n} | {st.mean(r['score'] for r in rs):.2f} |"
            if multi:
                rounds = [st.mean(r["round_scores"][k] for r in rs if len(r["round_scores"]) > k) for k in range(n_rounds)]
                line += f" {' / '.join(f'{x:.2f}' for x in rounds)} | {sum(r['overflow'] for r in rs)}/{n} |"
            elif any("overflow" in r for r in rs):
                line = line[:-1] + f" (overflow {sum(r.get('overflow', False) for r in rs)}/{n}) |"
            main = _med(r["by_tag"].get("main", {}).get("cost", 0) for r in rs)
            side = _med(sum(v["cost"] for t, v in r["by_tag"].items() if t != "main") for r in rs)
            med_cost = _med(r["cost_usd"] for r in rs)
            rel = f" ({med_cost / base[m][0] * 100:.0f}% of {base[m][1]})" if base.get(m) and base[m][0] else ""
            line += (f" {med_cost:.3f}{rel} | {cost / succ:.3f} |" if succ else f" {med_cost:.3f}{rel} | ∞ |")
            line += (f" {_med(r['prompt_tokens'] for r in rs):,.0f} | {_med(r['peak_prompt_tokens'] for r in rs):,.0f} | "
                     f"{_med(r['cache_hit_rate'] for r in rs):.0%} | {_med(r['steps'] for r in rs):.0f} | "
                     f"{main:.3f} / {side:.3f} |")
            out.append(line)
    if errors:
        out.append("\n**Runs that errored (not scored):**\n")
        for e in errors:
            out.append(f"- {e['model']} · `{e['spec']}` · {e['instance']}: {e['error'].splitlines()[0][:160]}")
    return "\n".join(out)


def totals(rows: list[dict[str, Any]]) -> str:
    by_model = defaultdict(float)
    for r in rows:
        by_model[r["model"]] += r["cost_usd"]
    return " · ".join(f"{m}: ${c:.2f}" for m, c in sorted(by_model.items())) + f" · total ${sum(by_model.values()):.2f}"


def main(argv: list[str] | None = None) -> None:
    paths = argv if argv is not None else sys.argv[1:]
    rows, errors = load(paths)
    print(table(rows, errors))
    print("\nSpend:", totals(rows))


if __name__ == "__main__":
    main()
