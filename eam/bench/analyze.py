"""Result tables for the documentation: `python -m eam.bench.analyze [--robust] <rows.jsonl>...`.

`--robust` prints the model-normalised comparison (see `robustness`); `--metrics` prints every measured quantity
per task, model and method (see `metrics`); `--summary` prints the compact headline table (see `summary`).

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
    ok = {(r["family"], r["model"], r["instance"], r["spec"]) for r in rows}
    errors = [e for e in errors if (e["family"], e["model"], e["instance"], e["spec"]) not in ok]  # rerun since
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


# Claude Code CLI list rates, USD per 1M tokens: (uncached input, cache read, cache write). Fitted exactly to the
# reported total_cost_usd of every recorded run (Sonnet/Opus: zero residual) and checked with single calls under
# DISABLE_PROMPT_CACHING=1, 2026-10-23. Used only for the "same run without caching" counterfactual below.
CLI_INPUT_RATES = {"cc-haiku": (0.10, 0.01, 0.20), "cc-sonnet": (2.0, 0.10, 4.0), "cc-opus": (4.0, 0.20, 8.0)}

FLOOR = ("naive",)  # no memory, no caching, no offload, same window as the methods
CEILING = ("full@native", "naive@native")  # everything kept, no window pressure: the model's own capability
HEADROOM_MIN = 0.15  # below this the model has nothing to recover on this task: recovery is not defined


def uncached_cost(r: dict[str, Any]) -> float:
    """What the same run would have cost with prompt caching off (caching does not change the model's output)."""
    rates = CLI_INPUT_RATES.get(r["model"])
    if not rates or r.get("prompt_cache") is False:
        return r["cost_usd"]
    p_in, p_read, p_write = rates
    u = r["usage"]
    return r["cost_usd"] + (u["cache_read_tokens"] * (p_in - p_read) + u["cache_write_tokens"] * (p_in - p_write)) / 1e6


def robustness(rows: list[dict[str, Any]]) -> str:
    """Method effect measured against each model's own floor and ceiling, so model strength is factored out.

    For each instance (paired: same seed for every method and model):
      floor F   = score of `naive` (no memory / no optimisation, same window)
      ceiling C = score with everything kept and no window pressure (`full@native` / `naive@native`)
      recovery  = (S − F) / (C − F): the share of the loss caused by the window that the method wins back.
                  0 = no better than doing nothing, 1 = as good as unlimited context; defined only if C − F ≥ 0.15.
      cost ratio = method $ / $ of `naive@native` (what an unoptimised long-context agent pays; if it was not run,
                   the `full@native` run's cost recomputed without caching).
    A method is *model-robust* if it recovers ≥ 0.5 on every model where recovery is defined (at least two).
    """
    out = []
    by_fam: dict[str, list] = defaultdict(list)
    for r in rows:
        by_fam[r["family"]].append(r)
    for family, rs in sorted(by_fam.items()):
        models = sorted({r["model"] for r in rs}, key=lambda m: ("haiku" not in m, "opus" in m, m))
        idx = {(r["model"], r["instance"], r["spec"]): r for r in rs}
        specs = sorted({r["spec"] for r in rs} - set(FLOOR) - set(CEILING))
        out.append(f"\n### {family}: anchors per model (means over instances)\n")
        out.append("| model | instances | floor score (`naive`) | ceiling score (unlimited context) | headroom | "
                   "floor $ | `full@native` $ | `naive@native` $ (cost reference) |")
        out.append("|---|---|---|---|---|---|---|---|")
        anchors: dict[str, dict[str, tuple]] = {}
        for m in models:
            insts = sorted({i for (mm, i, _) in idx if mm == m})
            a = {}
            for i in insts:
                f = idx.get((m, i, "naive"))
                cs = [idx[(m, i, c)] for c in CEILING if (m, i, c) in idx]
                if f and cs:
                    c_score = st.mean(c["score"] for c in cs)
                    # what an unoptimised long-context agent pays: the real `naive@native` run when there is one
                    nn = idx.get((m, i, "naive@native"))
                    c_unc = nn["cost_usd"] if nn else st.mean(uncached_cost(c) for c in cs)
                    c_cached = st.mean(c["cost_usd"] for c in cs if c.get("prompt_cache", True)) if any(
                        c.get("prompt_cache", True) for c in cs) else float("nan")
                    a[i] = (f["score"], c_score, f["cost_usd"], c_cached, c_unc)
            anchors[m] = a
            if a:
                v = list(a.values())
                out.append(f"| {m} | {len(v)} | {st.mean(x[0] for x in v):.2f} | {st.mean(x[1] for x in v):.2f} | "
                           f"{st.mean(x[1] - x[0] for x in v):.2f} | {st.mean(x[2] for x in v):.3f} | "
                           f"{st.mean(x[3] for x in v):.3f} | {st.mean(x[4] for x in v):.3f} |")
        out.append(f"\n### {family}: method effect relative to each model's own floor and ceiling\n")
        head = "| method | " + " | ".join(f"{m}: recovery (Δscore) · success · $ vs `naive@native`" for m in models)
        out.append(head + " | verdict |")
        out.append("|" + "---|" * (len(models) + 2))
        for spec in specs:
            cells, recs = [], []
            for m in models:
                rec, dlt, succ, ratio, n = [], [], 0, [], 0
                for i, (fs, cs, _, _, cu) in anchors.get(m, {}).items():
                    r = idx.get((m, i, spec))
                    if not r:
                        continue
                    n += 1
                    dlt.append(r["score"] - fs)
                    succ += r["success"]
                    ratio.append(r["cost_usd"] / cu if cu else float("nan"))
                    if cs - fs >= HEADROOM_MIN:
                        rec.append((r["score"] - fs) / (cs - fs))
                if not n:
                    cells.append("—")
                    continue
                rtxt = (f"{st.mean(rec):.2f} [{min(rec):.2f}…{max(rec):.2f}]" if len(rec) > 1 else
                        f"{rec[0]:.2f}" if rec else "n/a (no headroom)")
                cells.append(f"{rtxt} ({st.mean(dlt):+.2f}) · {succ}/{n} · {_med(ratio):.0%}")
                if rec:
                    recs.append(st.mean(rec))
            if len(recs) < 2:
                verdict = (("recovers" if recs[0] >= 0.5 else "does not recover") + " (one model only)") if recs \
                    else "not measurable"
            elif all(x >= 0.5 for x in recs):
                verdict = "model-robust"
            elif any(x >= 0.5 for x in recs):
                verdict = "model-dependent"
            elif recs:
                verdict = "not effective"
            else:
                verdict = "not measurable"
            out.append(f"| `{spec}` | " + " | ".join(cells) + f" | {verdict} |")
    return "\n".join(out)


def _fmt_tokens(x: float) -> str:
    return "—" if x != x else f"{x / 1e6:.2f}M" if x >= 1e6 else f"{x / 1e3:.0f}K"


def metrics(rows: list[dict[str, Any]], errors: list[dict[str, Any]] | None = None) -> str:
    """Every measured quantity per (task, model, method), as two tables per task.

    Accuracy & effort: success, accuracy (mean score), agentic rounds = LLM calls made by the agent (summed over
    sessions), tool calls, sessions, all LLM calls including technique side calls and sub-agents, overflows,
    wall-clock and model time. Tokens & cost: prompt tokens split into uncached input / cache read / cache write,
    output tokens, peak context, cache hit rate, cost as billed, the same run's cost without caching, and $ per
    success. Medians over runs unless stated (LLM costs and step counts are heavy-tailed)."""
    errs: dict[tuple, int] = defaultdict(int)
    for e in errors or []:
        errs[(e["family"], e["model"], e["spec"])] += 1
    groups: dict[tuple, list] = defaultdict(list)
    for r in rows:
        groups[(r["family"], r["model"], r["spec"])].append(r)
    order = lambda m: ("haiku" not in m, "opus" in m, m)  # noqa: E731 — cheap → strong
    out = []
    for family in sorted({k[0] for k in groups}):
        keys = sorted((k for k in groups if k[0] == family),
                      key=lambda k: (order(k[1]), -st.mean(r["score"] for r in groups[k]),
                                     _med(r["cost_usd"] for r in groups[k])))
        out.append(f"\n### {family} — accuracy and effort\n")
        out.append("| model | method | runs | success | accuracy (mean score) | agentic rounds | tool calls | sessions | "
                   "LLM calls incl. side calls | overflowed runs | wall-clock (min) | model time (min) |")
        out.append("|" + "---|" * 12)
        for k in keys:
            rs = groups[k]
            n, e = len(rs), errs.get(k, 0)
            tc = [r["tool_calls"] for r in rs if "tool_calls" in r]
            out.append(
                f"| {k[1]} | `{k[2]}` | {n}{f' (+{e} errored)' if e else ''} | {sum(r['success'] for r in rs)}/{n} | "
                f"{st.mean(r['score'] for r in rs):.2f} | {_med(r['steps'] for r in rs):.0f} | "
                f"{(f'{_med(tc):.0f}' if tc else '—')} | {rs[0].get('sessions') or len(rs[0].get('round_scores') or []) or 1} | "
                f"{_med(r['calls'] for r in rs):.0f} | {sum(r.get('overflow', False) for r in rs)}/{n} | "
                f"{_med(r['wall_s'] for r in rs) / 60:.1f} | {_med(r['llm_latency_ms'] for r in rs) / 60000:.1f} |")
        out.append(f"\n### {family} — tokens and cost\n")
        out.append("| model | method | prompt tokens | uncached input | cache read | cache write | output | peak context "
                   "| cache hit | $ per run | $ per run if uncached | $ per success |")
        out.append("|" + "---|" * 12)
        for k in keys:
            rs = groups[k]
            u = lambda f: _med(r["usage"][f] for r in rs)  # noqa: E731
            succ = sum(r["success"] for r in rs)
            per_success = f"{sum(r['cost_usd'] for r in rs) / succ:.3f}" if succ else "∞"
            out.append(
                f"| {k[1]} | `{k[2]}` | {_fmt_tokens(_med(r['prompt_tokens'] for r in rs))} | "
                f"{_fmt_tokens(u('input_tokens'))} | {_fmt_tokens(u('cache_read_tokens'))} | "
                f"{_fmt_tokens(u('cache_write_tokens'))} | {_fmt_tokens(u('output_tokens'))} | "
                f"{_fmt_tokens(_med(r['peak_prompt_tokens'] for r in rs))} | {_med(r['cache_hit_rate'] for r in rs):.0%} | "
                f"{_med(r['cost_usd'] for r in rs):.3f} | {_med(uncached_cost(r) for r in rs):.3f} | {per_success} |")
    return "\n".join(out)


def summary(rows: list[dict[str, Any]]) -> str:
    """One compact table per task: methods × models, with success, accuracy, recovery (vs that model's own
    floor/ceiling), median cost relative to `naive@native`, median agentic rounds and wall-clock minutes."""
    by: dict[tuple, list] = defaultdict(list)
    for r in rows:
        by[(r["family"], r["model"], r["spec"])].append(r)
    out = []
    for family in sorted({k[0] for k in by}):
        models = sorted({k[1] for k in by if k[0] == family}, key=lambda m: ("haiku" not in m, "opus" in m, m))
        idx = {(r["model"], r["instance"], r["spec"]): r for r in rows if r["family"] == family}
        specs = sorted({k[2] for k in by if k[0] == family},
                       key=lambda s: (s not in ("naive", "full", "naive@native", "full@native"),
                                      ["naive", "full", "naive@native", "full@native"].index(s)
                                      if s in ("naive", "full", "naive@native", "full@native") else 0, s))
        out.append(f"\n**{family}** — success · accuracy · recovery · cost vs `naive@native` · rounds · minutes "
                   "(medians; recovery defined only for methods)\n")
        out.append("| method | " + " | ".join(models) + " |")
        out.append("|" + "---|" * (len(models) + 1))
        for spec in specs:
            cells = []
            for m in models:
                rs = by.get((family, m, spec))
                if not rs:
                    cells.append("—")
                    continue
                rec, ratio = [], []
                for r in rs:
                    f = idx.get((m, r["instance"], "naive"))
                    cs = [idx[(m, r["instance"], c)] for c in CEILING if (m, r["instance"], c) in idx]
                    nn = idx.get((m, r["instance"], "naive@native"))
                    if nn and nn["cost_usd"]:
                        ratio.append(r["cost_usd"] / nn["cost_usd"])
                    if f and cs and spec not in FLOOR + CEILING:
                        c = st.mean(x["score"] for x in cs)
                        if c - f["score"] >= HEADROOM_MIN:
                            rec.append((r["score"] - f["score"]) / (c - f["score"]))
                n = len(rs)
                cells.append(f"{sum(r['success'] for r in rs)}/{n} · {st.mean(r['score'] for r in rs):.2f} · "
                             f"{(f'{st.mean(rec):.2f}' if rec else '—')} · "
                             f"{(f'{_med(ratio):.0%}' if ratio else '—')} · {_med(r['steps'] for r in rs):.0f} · "
                             f"{_med(r['wall_s'] for r in rs) / 60:.1f}")
            out.append(f"| `{spec}` | " + " | ".join(cells) + " |")
    return "\n".join(out)


def totals(rows: list[dict[str, Any]]) -> str:
    by_model = defaultdict(float)
    for r in rows:
        by_model[r["model"]] += r["cost_usd"]
    return " · ".join(f"{m}: ${c:.2f}" for m, c in sorted(by_model.items())) + f" · total ${sum(by_model.values()):.2f}"


def main(argv: list[str] | None = None) -> None:
    paths = list(argv if argv is not None else sys.argv[1:])
    modes = ("--robust", "--metrics", "--summary")
    mode = next((p for p in paths if p in modes), None)
    paths = [p for p in paths if p not in modes]
    rows, errors = load(paths)
    print({"--robust": robustness, "--summary": summary}[mode](rows) if mode in ("--robust", "--summary")
          else metrics(rows, errors) if mode == "--metrics" else table(rows, errors))
    print("\nSpend:", totals(rows))


if __name__ == "__main__":
    main()
