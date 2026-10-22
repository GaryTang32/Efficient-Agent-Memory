"""Aggregate result rows into a comparison table."""

from __future__ import annotations

from collections import defaultdict
from statistics import mean
from typing import Any


def aggregate(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    groups: dict[tuple, list[dict[str, Any]]] = defaultdict(list)
    for r in rows:
        groups[(r["family"], r["model"], r["spec"])].append(r)
    out = []
    for (family, model, spec), rs in groups.items():
        succ = sum(r["success"] for r in rs)
        cost = sum(r["cost_usd"] for r in rs)
        out.append({
            "family": family, "model": model, "spec": spec, "n": len(rs),
            "success": succ / len(rs),
            "mean_cost": cost / len(rs),
            "cost_per_success": cost / succ if succ else float("inf"),
            "mean_prompt_tokens": mean(r["prompt_tokens"] for r in rs),
            "mean_peak_ctx": mean(r["peak_prompt_tokens"] for r in rs),
            "cache_hit": mean(r["cache_hit_rate"] for r in rs),
            "rewrites": mean(r["history_rewrites"] for r in rs),
            "steps": mean(r["steps"] for r in rs),
            "latency_s": mean(r["llm_latency_ms"] for r in rs) / 1000,
        })
    return out


def markdown_table(rows: list[dict[str, Any]]) -> str:
    agg = aggregate(rows)
    base: dict[tuple, float] = {}
    for a in agg:
        if a["spec"] == "full":
            base[(a["family"], a["model"])] = a["mean_cost"]
    lines = ["| task | model | techniques | n | success | $/task | vs full | $/success | prompt tok | peak ctx | cache hit | rewrites | steps | LLM s |",
             "|---|---|---|---|---|---|---|---|---|---|---|---|---|---|"]
    for a in sorted(agg, key=lambda a: (a["family"], a["model"], a["mean_cost"])):
        b = base.get((a["family"], a["model"]))
        rel = f"{a['mean_cost'] / b * 100:.0f}%" if b else "–"
        cps = "∞" if a["cost_per_success"] == float("inf") else f"{a['cost_per_success']:.4f}"
        lines.append(
            f"| {a['family']} | {a['model']} | `{a['spec']}` | {a['n']} | {a['success']:.0%} | {a['mean_cost']:.4f} | "
            f"{rel} | {cps} | {a['mean_prompt_tokens']:,.0f} | {a['mean_peak_ctx']:,.0f} | {a['cache_hit']:.0%} | "
            f"{a['rewrites']:.1f} | {a['steps']:.1f} | {a['latency_s']:.1f} |")
    return "\n".join(lines)
