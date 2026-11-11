"""Tables for the validation round (docs/results/2026-11-11-validation-round.md), from the rows in results/.

    python scripts/analyze_validation.py            # markdown on stdout

Sections: same-day Django cells, the repeated lean cell (run-to-run spread), same-day synthetic cells and their
repeat, related-issue Django workdays, SymPy, EoCC under corrected grading, and the earlier (other-day) rows next
to the same-day ones. Costs relative to the ceiling are paired by workday; issue comparisons are paired by issue.
"""

import glob
import json
import math
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
                recalls=sum(r["events"].get("automem_recall", 0) for r in runs.values()), days=len(runs))


def fmt(c: dict) -> str:
    return f"{c['res']}/{c['n']} · {c['cost']:.0f}% · {c['per']:.4f}"


def swe_table(title: str, pattern: str, specs: list[str], base: str = L) -> None:
    print(f"\n### {title}\n\nResolved · cost vs ceiling (paired by workday) · $ per resolved issue.\n")
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
    print("\nCompactions · overflows · unfinished sessions · note recalls:\n")
    print("| Setting | " + " | ".join(label for _, label in MODELS) + " |\n|---|" + "---|" * len(MODELS))
    for s in specs:
        cells = []
        for m, _ in MODELS:
            runs = data[m].get(s)
            c = cell(runs, {}) if runs else None
            cells.append(f"{c['rebuilds']} · {c['overflow']} · {c['unfinished']} · {c['recalls']}" if c else "—")
        print(f"| {name(s)} | " + " | ".join(cells) + " |")


def repeat_swe() -> None:
    print("\n### Run-to-run spread on Django (the lean cell run twice, same day)\n")
    print("| | Run A | Run B | Issues that flipped (A only / B only / compared) | Cost difference |\n|---|---|---|---|---|")
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
        print(f"| {label} ({len(days)} workdays) | {ra:.0f} · ${ca:.2f} | {rb:.0f} · ${cb:.2f} | "
              f"{w} / {lo} / {n} | {100 * (cb - ca) / ca:+.0f}% |")
        day = [100 * abs(b[i]["cost_usd"] - a[i]["cost_usd"]) / a[i]["cost_usd"] for i in days]
        print(f"| {label}, per workday | | | | median |Δcost| {sorted(day)[len(day) // 2]:.0f}% |")


TASKS = ("research_corpus", "ops_stream", "ledger_audit", "repo_debug")
SYN = ("naive@native", "automem:ingest=0.1", L, "automem_v2_adaptive")


def synthetic() -> None:
    print("\n### Same-day synthetic tasks (instances 0–3)\n\nMean over the four tasks: score · cost vs ceiling "
          "(paired by instance) · runs fully solved.\n")
    print("| Setting | " + " | ".join(label for _, label in MODELS) + " |\n|---|" + "---|" * len(MODELS))
    table = {}
    for m, _ in MODELS:
        for t in TASKS:
            table[m, t] = by_spec(load(f"sameday_syn-{t}-{m}.jsonl"))
    for s in SYN:
        cells = []
        for m, _ in MODELS:
            scores, costs, solved, n = [], [], 0, 0
            for t in TASKS:
                runs, ref = table[m, t].get(s, {}), table[m, t].get("naive@native", {})
                common = [i for i in runs if i in ref]
                if not common:
                    continue
                scores.append(sum(runs[i]["score"] for i in common) / len(common))
                costs.append(100 * sum(runs[i]["cost_usd"] for i in common) / sum(ref[i]["cost_usd"] for i in common))
                solved += sum(bool(runs[i]["success"]) for i in common)
                n += len(common)
            cells.append(f"{sum(scores) / len(scores):.2f} · {sum(costs) / len(costs):.0f}% · {solved}/{n}"
                         + ("" if len(scores) == 4 else f" ({len(scores)} tasks)") if scores else "—")
        print(f"| {name(s)} | " + " | ".join(cells) + " |")
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
    print("| | Resolved | Overflows | Unfinished sessions | Unfinished but resolved | Cost |\n|---|---|---|---|---|---|")
    if o:
        print(f"| Earlier (unfinished sessions scored 0, over-window recaps allowed) | {o['res']}/{o['n']} | "
              f"{o['overflow']} | not recorded | 0 by rule | ${o['usd']:.2f} |")
    print(f"| Re-check (final state graded, over-window recaps end the session) | {n['res']}/{n['n']} | "
          f"{n['overflow']} | {n['unfinished']} | see note | ${n['usd']:.2f} |")
    lean = by_spec(load("sameday_swe-haiku.jsonl")).get(L, {})
    if lean:
        w, lo, k, p = paired(new, lean)
        print(f"\nPaired by issue against same-day lean: +{w} / −{lo} of {k}, p = {p:.2f}.")


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
    eocc()
    spend()
