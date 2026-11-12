"""Tables for the validation round (docs/results/2026-11-11-validation-round.md), from the rows in results/.

    python scripts/analyze_validation.py            # markdown on stdout

Sections: same-day Django cells, the repeated lean cell (run-to-run spread), same-day synthetic cells and their
repeat, related-issue Django workdays, SymPy, EoCC under corrected grading, and the earlier (other-day) rows next
to the same-day ones. Costs relative to the ceiling are paired by workday; issue comparisons are paired by issue.
"""

import glob
import json
import statistics as st
import math
import random
from collections import defaultdict
from pathlib import Path

R = Path(__file__).resolve().parents[1] / "results"
L = "automem:workspace=false,ingest=0.1"
NAMES = {"naive@native": "Ceiling", L: "Lean (ReSum)", f"{L},compact=handoff,handoff_variant=swe": "Lean + handoff",
         f"{L},compact=handoff,handoff_variant=brief": "Lean + brief handoff", "automem_v2_adaptive": "Adaptive",
         "automem:ingest=0.1": "v2 (notes)", "eocc:variant=swe": "EoCC alone"}
MODELS = (("haiku", "Haiku"), ("sonnet", "Sonnet"))


def name(spec: str) -> str:
    return NAMES.get(spec.split("#")[0], spec)


def load(pattern: str) -> list[dict]:
    rows = []
    for f in sorted(glob.glob(str(R / pattern))):
        rows += [r for r in (json.loads(x) for x in Path(f).read_text().splitlines() if x.strip()) if "error" not in r]
    return rows


def by_spec(rows: list[dict]) -> dict[str, dict[str, dict]]:
    out: dict[str, dict[str, dict]] = defaultdict(dict)
    for r in rows:
        out[r["spec"].split("#")[0]][r["instance"]] = r
    return out


def issues(runs: dict[str, dict]) -> dict[tuple, float]:
    return {(i, k): s for i, r in runs.items() for k, s in enumerate(r["round_scores"])}


def sign_p(wins: int, losses: int) -> float:
    """Two-sided exact sign test."""
    n, k = wins + losses, min(wins, losses)
    if n == 0:
        return 1.0
    return min(1.0, 2 * sum(math.comb(n, i) for i in range(k + 1)) / 2 ** n)


def paired(a: dict[str, dict], b: dict[str, dict]) -> tuple[int, int, int, float]:
    """Issues only `a` resolved, only `b` resolved, issues compared, sign-test p."""
    ia, ib = issues(a), issues(b)
    common = [k for k in ia if k in ib]
    w = sum(ia[k] > ib[k] for k in common)
    lo = sum(ia[k] < ib[k] for k in common)
    return w, lo, len(common), sign_p(w, lo)


def solve3(a: list[list[float]], b: list[float]) -> list[float]:
    """Solve a 3×3 linear system (normal equations of the fit below)."""
    m = [row[:] + [b[i]] for i, row in enumerate(a)]
    for i in range(3):
        piv = max(range(i, 3), key=lambda r: abs(m[r][i]))
        m[i], m[piv] = m[piv], m[i]
        for r in range(3):
            if r != i:
                f = m[r][i] / m[i][i]
                m[r] = [x - f * y for x, y in zip(m[r], m[i])]
    return [m[i][3] / m[i][i] for i in range(3)]


_PER_RETRY: dict[str, float] = {}


def per_retry(model: str) -> float:
    """Cost of one runaway reply (an `llm_retry`: the model loops to the CLI's output cap): the coefficient of a
    row's retries in a least-squares fit of its cost on retries and calls, over this round's SWE rows of `model`."""
    if model not in _PER_RETRY:
        rows = [r for r in load("sameday_swe*.jsonl") + load("oos_*.jsonl") + load("recheck*.jsonl")
                if r["model"] == model]
        x = [[r["events"].get("llm_retry", 0), r["calls"], 1.0] for r in rows]
        y = [r["cost_usd"] for r in rows]
        xtx = [[sum(u[i] * u[j] for u in x) for j in range(3)] for i in range(3)]
        xty = [sum(u[i] * v for u, v in zip(x, y)) for i in range(3)]
        _PER_RETRY[model] = solve3(xtx, xty)[0] if len(rows) > 5 else 0.0
    return _PER_RETRY[model]


def net(r: dict) -> float:
    """A row's cost without its runaway replies."""
    return r["cost_usd"] - r["events"].get("llm_retry", 0) * per_retry(r["model"])


def boot(runs: dict[str, dict], ref: dict[str, dict], n: int = 4000) -> tuple[float, float]:
    """95% bootstrap interval of total cost relative to `ref`, resampling workdays (paired)."""
    days = [i for i in runs if i in ref]
    if len(days) < 3:
        return float("nan"), float("nan")
    rng, out = random.Random(0), []
    for _ in range(n):
        pick = [days[rng.randrange(len(days))] for _ in days]
        out.append(100 * sum(runs[i]["cost_usd"] for i in pick) / sum(ref[i]["cost_usd"] for i in pick))
    out.sort()
    return out[int(0.025 * n)], out[int(0.975 * n)]


def cell(runs: dict[str, dict], ref: dict[str, dict]) -> dict:
    common = [i for i in runs if i in ref]
    res = sum(sum(r["round_scores"]) for r in runs.values())
    n = sum(len(r["round_scores"]) for r in runs.values())
    usd = sum(r["cost_usd"] for r in runs.values())
    return dict(res=round(res), n=n, usd=usd, per=usd / max(res, 1),
                cost=100 * sum(runs[i]["cost_usd"] for i in common) / max(sum(ref[i]["cost_usd"] for i in common), 1e-9),
                rebuilds=sum(v for r in runs.values() for k, v in r["events"].items() if k.endswith("_rebuild")),
                overflow=sum(r["events"].get("context_overflow", 0) for r in runs.values()),
                unfinished=sum(r.get("unfinished_sessions", 0) for r in runs.values()),
                recalls=sum(r["events"].get("automem_recall", 0) for r in runs.values()), days=len(runs),
                out=sum(r["usage"].get("output_tokens", 0) for r in runs.values()), ci=boot(runs, ref) if ref else None,
                retries=sum(r["events"].get("llm_retry", 0) for r in runs.values()),
                net=100 * sum(net(runs[i]) for i in common) / max(sum(net(ref[i]) for i in common), 1e-9),
                net_per=sum(net(r) for r in runs.values()) / max(res, 1))


def fmt(c: dict) -> str:
    same = abs(c["cost"] - 100) < 1e-6
    ci = f" [{c['ci'][0]:.0f}–{c['ci'][1]:.0f}]" if c.get("ci") and not same and c["ci"][0] == c["ci"][0] else ""
    return f"{c['res']}/{c['n']} · {c['cost']:.0f}%{ci} · {c['net']:.0f}% · {c['net_per']:.4f}"


def swe_table(title: str, pattern: str, specs: list[str], base: str = L) -> None:
    print(f"\n### {title}\n\nResolved · cost vs ceiling, paired by workday [95% bootstrap interval over workdays] · "
          "the same net of runaway replies · $ per resolved issue net of runaway replies.\n")
    data = {m: by_spec(load(pattern.format(m=m))) for m, _ in MODELS}
    print("| Setting | " + " | ".join(label for _, label in MODELS) + " |\n|---|" + "---|" * len(MODELS))
    for s in specs:
        cells = []
        for m, _ in MODELS:
            runs = data[m].get(s)
            cells.append(fmt(cell(runs, data[m].get("naive@native", {}))) if runs else "—")
        print(f"| {name(s)} | " + " | ".join(cells) + " |")
    print("\nPaired by issue against " + name(base) + " (only this setting resolved / only "
          + name(base) + " resolved / issues compared, sign-test p):\n")
    print("| Setting | " + " | ".join(label for _, label in MODELS) + " |\n|---|" + "---|" * len(MODELS))
    for s in specs:
        if s == base:
            continue
        cells = []
        for m, _ in MODELS:
            if s in data[m] and base in data[m]:
                w, lo, n, p = paired(data[m][s], data[m][base])
                cells.append(f"+{w} / −{lo} / {n}, p = {p:.2f}")
            else:
                cells.append("—")
        print(f"| {name(s)} | " + " | ".join(cells) + " |")
    print("\nCompactions · overflows · unfinished sessions · note recalls · output tokens · runaway replies:\n")
    print("| Setting | " + " | ".join(label for _, label in MODELS) + " |\n|---|" + "---|" * len(MODELS))
    for s in specs:
        cells = []
        for m, _ in MODELS:
            runs = data[m].get(s)
            c = cell(runs, {}) if runs else None
            cells.append(f"{c['rebuilds']} · {c['overflow']} · {c['unfinished']} · {c['recalls']} · "
                         f"{c['out'] / 1e6:.2f}M · {c['retries']}" if c else "—")
        print(f"| {name(s)} | " + " | ".join(cells) + " |")


def repeat_swe() -> None:
    print("\n### Run-to-run spread on Django (the lean cell run twice, same day)\n")
    print("| | Run A: resolved · cost · output tokens | Run B | Issues that flipped (A only / B only / compared) | "
          "Cost B vs A [95% interval] |\n|---|---|---|---|---|")
    for m, label in MODELS:
        a = by_spec(load(f"sameday_swe-{m}.jsonl")).get(L, {})
        b = by_spec(load(f"sameday_swe_rep-{m}.jsonl")).get(L, {})
        days = [i for i in a if i in b]
        if not days:
            continue
        a, b = {i: a[i] for i in days}, {i: b[i] for i in days}
        w, lo, n, _ = paired(a, b)
        ca, cb = sum(r["cost_usd"] for r in a.values()), sum(r["cost_usd"] for r in b.values())
        ra, rb = sum(sum(r["round_scores"]) for r in a.values()), sum(sum(r["round_scores"]) for r in b.values())
        oa, ob = (sum(r["usage"]["output_tokens"] for r in x.values()) / 1e6 for x in (a, b))
        lo95, hi95 = boot(b, a)
        na, nb = sum(net(r) for r in a.values()), sum(net(r) for r in b.values())
        ta, tb = (sum(r["events"].get("llm_retry", 0) for r in x.values()) for x in (a, b))
        print(f"| {label} ({len(days)} workdays) | {ra:.0f} · ${ca:.2f} · {oa:.2f}M | {rb:.0f} · ${cb:.2f} · {ob:.2f}M | "
              f"{w} / {lo} / {n} | {100 * cb / ca:.0f}% [{lo95:.0f}–{hi95:.0f}] |")
        print(f"| {label}, runaway replies {ta} / {tb}; net of them | ${na:.2f} | ${nb:.2f} | | {100 * nb / na:.0f}% |")
        day = sorted(max(b[i]["cost_usd"], a[i]["cost_usd"]) / min(b[i]["cost_usd"], a[i]["cost_usd"]) for i in days)
        print(f"| {label}, one workday | | | | the dearer run costs {day[len(day) // 2]:.1f}× the cheaper (median), "
              f"up to {day[-1]:.1f}× |")


TASKS = ("research_corpus", "ops_stream", "ledger_audit", "repo_debug")
SYN = ("naive@native", "automem:ingest=0.1", L, "automem_v2_adaptive")


def synthetic() -> None:
    print("\n### Same-day synthetic tasks (instances 0–3)\n\nMean over the four tasks: score · cost vs ceiling as the "
          "README computes it (median run per task) · cost vs ceiling in total dollars per task · runs fully solved. "
          "The last row is the repeat of v2.\n")
    print("| Setting | " + " | ".join(label for _, label in MODELS) + " |\n|---|" + "---|" * len(MODELS))
    table = {}
    for m, _ in MODELS:
        for t in TASKS:
            table[m, t] = by_spec(load(f"sameday_syn-{t}-{m}.jsonl"))
            table[m, t]["repeat"] = by_spec(load(f"sameday_syn_rep-{t}-{m}.jsonl")).get("automem:ingest=0.1", {})
    for s in SYN + ("repeat",):
        cells = []
        for m, _ in MODELS:
            scores, costs, medians, solved, n = [], [], [], 0, 0
            for t in TASKS:
                runs, ref = table[m, t].get(s, {}), table[m, t].get("naive@native", {})
                common = [i for i in runs if i in ref]
                if not common:
                    continue
                scores.append(sum(runs[i]["score"] for i in common) / len(common))
                costs.append(100 * sum(runs[i]["cost_usd"] for i in common) / sum(ref[i]["cost_usd"] for i in common))
                medians.append(100 * st.median(runs[i]["cost_usd"] for i in common)
                               / st.median(ref[i]["cost_usd"] for i in common))
                solved += sum(bool(runs[i]["success"]) for i in common)
                n += len(common)
            cells.append(f"{sum(scores) / len(scores):.2f} · {sum(medians) / len(medians):.0f}% · "
                         f"{sum(costs) / len(costs):.0f}% · {solved}/{n}"
                         + ("" if len(scores) == 4 else f" ({len(scores)} tasks)") if scores else "—")
        print(f"| {'v2 (notes), repeat' if s == 'repeat' else name(s)} | " + " | ".join(cells) + " |")
    print("\nPer task (score · cost vs ceiling):\n")
    print("| Task | Setting | " + " | ".join(label for _, label in MODELS) + " |\n|---|---|" + "---|" * len(MODELS))
    for t in TASKS:
        for s in SYN[1:]:
            cells = []
            for m, _ in MODELS:
                runs, ref = table[m, t].get(s, {}), table[m, t].get("naive@native", {})
                common = [i for i in runs if i in ref]
                cells.append(f"{sum(runs[i]['score'] for i in common) / len(common):.2f} · "
                             f"{100 * sum(runs[i]['cost_usd'] for i in common) / sum(ref[i]['cost_usd'] for i in common):.0f}%"
                             f" (n={len(common)})" if common else "—")
            print(f"| `{t}` | {name(s)} | " + " | ".join(cells) + " |")
    print("\n### Run-to-run spread on the synthetic tasks (v2 run twice, same day)\n")
    print("| | Mean score A / B | Cost A / B | Cost difference | Runs solved A / B | Largest per-instance cost gap |"
          "\n|---|---|---|---|---|---|")
    for m, label in MODELS:
        a, b = {}, {}
        for t in TASKS:
            x = table[m, t].get("automem:ingest=0.1", {})
            y = by_spec(load(f"sameday_syn_rep-{t}-{m}.jsonl")).get("automem:ingest=0.1", {})
            for i in x:
                if i in y:
                    a[t, i], b[t, i] = x[i], y[i]
        if not a:
            continue
        ca, cb = sum(r["cost_usd"] for r in a.values()), sum(r["cost_usd"] for r in b.values())
        gap = max(100 * abs(b[k]["cost_usd"] - a[k]["cost_usd"]) / a[k]["cost_usd"] for k in a)
        print(f"| {label} ({len(a)} runs) | {sum(r['score'] for r in a.values()) / len(a):.2f} / "
              f"{sum(r['score'] for r in b.values()) / len(b):.2f} | ${ca:.2f} / ${cb:.2f} | "
              f"{100 * (cb - ca) / ca:+.0f}% | {sum(bool(r['success']) for r in a.values())} / "
              f"{sum(bool(r['success']) for r in b.values())} | {gap:.0f}% |")


def position(pattern: str, specs: list[str]) -> None:
    print("\nResolved by position in the workday (session 1 / sessions 2–5), where notes could help later sessions:\n")
    print("| Setting | " + " | ".join(label for _, label in MODELS) + " |\n|---|" + "---|" * len(MODELS))
    for s in specs:
        cells = []
        for m, _ in MODELS:
            runs = by_spec(load(pattern.format(m=m))).get(s, {})
            first = [r["round_scores"][0] for r in runs.values()]
            rest = [x for r in runs.values() for x in r["round_scores"][1:]]
            cells.append(f"{100 * sum(first) / len(first):.0f}% / {100 * sum(rest) / len(rest):.0f}%" if first else "—")
        print(f"| {name(s)} | " + " | ".join(cells) + " |")


def earlier() -> None:
    print("\n### Earlier rows (other days, old grading) next to the same-day rows, Django 100 at 16K\n")
    print("| Setting | Model | Earlier: resolved · cost vs its ceiling | Same day: resolved · cost vs ceiling |\n|---|---|---|---|")
    for m, label in MODELS:
        old = by_spec(load(f"swe_16k-{m}.jsonl") + load(f"swe_16k_brief-{m}.jsonl") + load(f"swe_16k_adaptive-{m}.jsonl"))
        ref_old = by_spec(load(f"swe_wide-{m}.jsonl")).get("naive@native", {})
        new = by_spec(load(f"sameday_swe-{m}.jsonl"))
        for s in (L, f"{L},compact=handoff,handoff_variant=swe", f"{L},compact=handoff,handoff_variant=brief",
                  "automem_v2_adaptive"):
            if s in old and s in new:
                o, n = cell(old[s], ref_old), cell(new[s], new.get("naive@native", {}))
                print(f"| {name(s)} | {label} | {o['res']}/{o['n']} · {o['cost']:.0f}% | {n['res']}/{n['n']} · {n['cost']:.0f}% |")
        if ref_old and "naive@native" in new:
            o, n = cell(ref_old, ref_old), cell(new["naive@native"], new["naive@native"])
            print(f"| Ceiling | {label} | {o['res']}/{o['n']} · ${o['usd']:.2f} | {n['res']}/{n['n']} · ${n['usd']:.2f} |")


def eocc() -> None:
    new = by_spec(load("recheck_eocc16k-haiku.jsonl")).get("eocc:variant=swe", {})
    old = by_spec(load("swe_16k-haiku.jsonl")).get("eocc:variant=swe", {})
    if not new:
        return
    print("\n### EoCC alone under corrected grading (Haiku, Django 100 at 16K)\n")
    n, o = cell(new, {}), cell(old, {}) if old else None
    print("| | Resolved | Overflows | Sessions that ended early | Cost |\n|---|---|---|---|---|")
    if o:
        print(f"| Earlier (sessions that ended early scored 0; over-window recaps allowed) | {o['res']}/{o['n']} | "
              f"{o['overflow']} | not recorded | ${o['usd']:.2f} |")
    print(f"| Re-check (final state graded; over-window recaps end the session) | {n['res']}/{n['n']} | "
          f"{n['overflow']} | {n['unfinished']} | ${n['usd']:.2f} |")
    lean = by_spec(load("sameday_swe-haiku.jsonl")).get(L, {})
    if lean:
        w, lo, k, p = paired(new, lean)
        print(f"\nPaired by issue against same-day lean: +{w} / −{lo} of {k}, p = {p:.2f}.")


def handoff_pooled() -> None:
    """Handoff against ReSum (both lean), paired by issue, over every 16K run set that has both."""
    h = f"{L},compact=handoff,handoff_variant=swe"
    print("\n### Handoff recap against ReSum, all paired evidence at 16K\n")
    print("Only handoff resolved / only ReSum resolved (issues compared).\n")
    print("| Run set | " + " | ".join(label for _, label in MODELS) + " |\n|---|" + "---|" * len(MODELS))
    tot = {m: [0, 0] for m, _ in MODELS}
    for label, pat in (("Django 100, 2026-11-06 (old grading)", "swe_16k-{m}.jsonl"),
                       ("Django 100, same day", "sameday_swe-{m}.jsonl"), ("SymPy", "oos_sympy-{m}.jsonl")):
        cells = []
        for m, _ in MODELS:
            d = by_spec(load(pat.format(m=m)))
            if h in d and L in d:
                w, lo, n, _ = paired(d[h], d[L])
                tot[m][0] += w
                tot[m][1] += lo
                cells.append(f"+{w} / −{lo} ({n})")
            else:
                cells.append("—")
        print(f"| {label} | " + " | ".join(cells) + " |")
    print("| **Pooled** | " + " | ".join(f"**+{w} / −{lo}**, p = {sign_p(w, lo):.2f}" for w, lo in tot.values()) + " |")
    w, lo = sum(v[0] for v in tot.values()), sum(v[1] for v in tot.values())
    print(f"\nBoth models pooled: +{w} / −{lo}, sign-test p = {sign_p(w, lo):.3f}.")


def spend() -> None:
    print("\n### Spend\n\n| Run set | Rows | Cost |\n|---|---|---|")
    total = 0.0
    for label, pat in (("Same-day Django", "sameday_swe-*.jsonl"), ("Django repeat", "sameday_swe_rep-*.jsonl"),
                       ("Same-day synthetic", "sameday_syn-*.jsonl"), ("Synthetic repeat", "sameday_syn_rep-*.jsonl"),
                       ("Related-issue Django", "oos_related-*.jsonl"), ("SymPy", "oos_sympy-*.jsonl"),
                       ("EoCC re-check", "recheck_eocc16k-*.jsonl"), ("Set aside (old grading)", "*.oldgrading")):
        rows = load(pat)
        c = sum(r["cost_usd"] for r in rows)
        total += c
        print(f"| {label} | {len(rows)} | ${c:.2f} |")
    print(f"| **Total** | | **${total:.2f}** |")


if __name__ == "__main__":
    print("Cost of one runaway reply (fitted): " + ", ".join(f"{label} ${per_retry('cc-' + m):.3f}" for m, label in MODELS))
    swe_table("Same-day Django (100 issues, 16K)", "sameday_swe-{m}.jsonl",
              ["naive@native", L, f"{L},compact=handoff,handoff_variant=swe",
               f"{L},compact=handoff,handoff_variant=brief", "automem_v2_adaptive"])
    repeat_swe()
    earlier()
    synthetic()
    rel = ["naive@native", L, "automem:ingest=0.1", "automem_v2_adaptive"]
    swe_table("Related-issue Django workdays (16K)", "oos_related-{m}.jsonl", rel)
    position("oos_related-{m}.jsonl", rel)
    swe_table("SymPy (16K)", "oos_sympy-{m}.jsonl",
              ["naive@native", L, f"{L},compact=handoff,handoff_variant=swe"])
    handoff_pooled()
    eocc()
    spend()
