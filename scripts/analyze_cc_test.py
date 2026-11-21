"""Analysis of the Claude Code test (docs/plans/2026-11-21-automem-vs-claude-code-autocompact.md, section 8).

    python scripts/analyze_cc_test.py results/cc_test/N results/cc_test/F2 ...      # verdicts per cell
    python scripts/analyze_cc_test.py results/cc_test/pilot --gates                 # the pilot's go/no-go gates

Unit: one instance (a 10-day run, or a 5-issue workday). Each arm is compared with A on the same instances, with
95% bootstrap intervals over instances (10,000 resamples). Rules (fixed before the main runs):

* accuracy: the lower bound of the paired difference (arm - A, points) above -5
* efficiency: pooled cost per correct answer at most 0.90 of A's, with the interval's upper bound below 1.00
* validity: if A2 (a copy of A) differs from A by more than 10% in pooled cost, the cell is too noisy for a verdict
* F2 no harm: TOST with 90% intervals; issues resolved within +-10 points, cost ratio within 0.85-1.15
* the headline is V2 against A in cell N; every other comparison is secondary and Holm-adjusted

Standard library only. Writes <first dir>/analysis.md and analysis.json.
"""

from __future__ import annotations

import json
import math
import random
import statistics as st
import sys
from collections import defaultdict
from pathlib import Path

B = 10_000
COMPARISONS = [("V2", "A", "the verdict"), ("V2", "Aplus", "beats a notes prompt"), ("V2", "L", "what the notes add"),
               ("L", "A", "what previews and the recap add"), ("A", "A0", "what Claude Code's auto memory adds"),
               ("A2", "A", "noise (identical arms)")]
# estimated cost per run for the cost gate (plan, section 12); the pilot's N runs are half length
ESTIMATE = {"N": 1.50, "R100": 2.40, "R500": 4.60, "F2": 0.40}


def load(dirs: list[str]) -> list[dict]:
    rows = []
    for d in dirs:
        for line in (Path(d) / "rows.jsonl").read_text().splitlines():
            r = json.loads(line)
            if not r.get("discarded"):
                r["_dir"] = d
                rows.append(r)
    return rows


def pooled_cpc(runs: list[dict]) -> float:
    correct = sum(r["correct"] for r in runs)
    return sum(r["cost"] for r in runs) / correct if correct else math.inf


def paired(rows: list[dict], cell: str, x: str, y: str, rng: random.Random, conf: float = 0.95) -> dict | None:
    """Arm x against arm y on the instances both ran: accuracy difference (points) and cost-per-correct ratio."""
    by = {(r["arm"], r["instance"]): r for r in rows if r["cell"] == cell}
    inst = sorted(i for (a, i) in by if a == x and (y, i) in by)
    if not inst:
        return None
    acc = [100 * (by[(x, i)]["accuracy"] - by[(y, i)]["accuracy"]) for i in inst]
    ratio = pooled_cpc([by[(x, i)] for i in inst]) / pooled_cpc([by[(y, i)] for i in inst])
    cost_ratio = sum(by[(x, i)]["cost"] for i in inst) / max(1e-12, sum(by[(y, i)]["cost"] for i in inst))
    boot_acc, boot_ratio, boot_cost = [], [], []
    for _ in range(B):
        s = [rng.choice(inst) for _ in inst]
        boot_acc.append(st.mean(100 * (by[(x, i)]["accuracy"] - by[(y, i)]["accuracy"]) for i in s))
        a, b = pooled_cpc([by[(x, i)] for i in s]), pooled_cpc([by[(y, i)] for i in s])
        boot_ratio.append(a / b if b and b != math.inf else math.inf)
        boot_cost.append(sum(by[(x, i)]["cost"] for i in s) / max(1e-12, sum(by[(y, i)]["cost"] for i in s)))
    lo, hi = (1 - conf) / 2, 1 - (1 - conf) / 2

    def q(v, p):
        v = sorted(v)
        return v[min(len(v) - 1, int(p * len(v)))]

    finite = [r for r in boot_ratio if r != math.inf]
    p_two = 2 * min(sum(r >= 1 for r in boot_ratio), sum(r <= 1 for r in boot_ratio)) / B
    return {"n": len(inst), "acc_diff": st.mean(acc), "acc_ci": (q(boot_acc, lo), q(boot_acc, hi)),
            "cpc_ratio": ratio, "cpc_ci": (q(finite, lo), q(finite, hi)) if finite else (math.inf, math.inf),
            "cost_ratio": cost_ratio, "cost_ci": (q(boot_cost, lo), q(boot_cost, hi)), "p_efficiency": min(1.0, p_two)}


def verdict(c: dict) -> tuple[str, str]:
    acc = "non-inferior" if c["acc_ci"][0] > -5 else "not shown"
    eff = "more efficient" if c["cpc_ratio"] <= 0.90 and c["cpc_ci"][1] < 1.0 else "not shown"
    return acc, eff


def holm(ps: list[float]) -> list[float]:
    order = sorted(range(len(ps)), key=lambda i: ps[i])
    adj, running = [0.0] * len(ps), 0.0
    for rank, i in enumerate(order):
        running = max(running, min(1.0, (len(ps) - rank) * ps[i]))
        adj[i] = running
    return adj


def arm_table(rows: list[dict], cell: str) -> list[str]:
    out = [f"| Arm | Runs | Accuracy | Cost / run | Cost per correct | Tokens per correct | Peak prompt | "
           "Compactions | Microcompacts | Report previews | Claude Code cuts | Note writes | Auto-memory writes | "
           "NOTES.md writes | Cap hits | Timeouts | Isolation flags |", "|" + "---|" * 17]
    by = defaultdict(list)
    for r in rows:
        if r["cell"] == cell:
            by[r["arm"]].append(r)
    for arm in ("A", "A2", "A0", "Aplus", "L", "V2"):
        rs = by.get(arm)
        if not rs:
            continue
        days = [d for r in rs for d in r["days"]]
        tpc = [r["tokens_per_correct"] for r in rs if r["tokens_per_correct"]]
        out.append(f"| {arm} | {len(rs)} | {100 * st.mean(r['accuracy'] for r in rs):.1f}% | "
                   f"${st.mean(r['cost'] for r in rs):.3f} | ${pooled_cpc(rs):.4f} | "
                   f"{st.mean(tpc):,.0f} | {max(r['peak_prompt'] for r in rs):,} | "
                   f"{sum(r['compactions'] for r in rs)} | {sum(r['microcompacts'] for r in rs)} | "
                   f"{sum(d.get('report_previews') or 0 for d in days)} | {sum(d.get('report_cc_cut') or 0 for d in days)} | "
                   f"{sum(d.get('note_writes') or 0 for d in days)} | {sum(d.get('auto_memory_writes') or 0 for d in days)} | "
                   f"{sum(d.get('notes_md_writes') or 0 for d in days)} | {sum(r['cap_hits'] for r in rs)} | "
                   f"{sum(r['timeouts'] for r in rs)} | {sum(len(d.get('isolation_flags') or []) for d in days)} |")
    return out


def analyse(rows: list[dict], rng: random.Random) -> tuple[list[str], dict]:
    md, js = ["# Claude Code test: analysis\n"], {"cells": {}}
    for cell in sorted({r["cell"] for r in rows}):
        md += [f"\n## Cell {cell}\n"] + arm_table(rows, cell)
        comps = []
        if cell == "F2":
            for x in ("L", "V2"):
                c = paired(rows, cell, x, "A", rng, conf=0.90)
                if c:
                    eq = (-10 < c["acc_ci"][0] and c["acc_ci"][1] < 10 and 0.85 < c["cost_ci"][0] and c["cost_ci"][1] < 1.15)
                    comps.append({"x": x, "y": "A", "role": "no harm (TOST, 90% intervals)", **c,
                                  "verdict": "equivalent" if eq else "equivalence not shown"})
        else:
            for x, y, role in COMPARISONS:
                c = paired(rows, cell, x, y, rng)
                if c:
                    comps.append({"x": x, "y": y, "role": role, **c})
            noise = next((c for c in comps if c["x"] == "A2"), None)
            valid = noise is None or 0.90 <= noise["cost_ratio"] <= 1.10
            secondary = [c for c in comps if c["x"] != "A2" and not (cell == "N" and c["x"] == "V2" and c["y"] == "A")]
            for c, p in zip(secondary, holm([c["p_efficiency"] for c in secondary])):
                c["p_holm"] = p
            for c in comps:
                if c["x"] == "A2":
                    c["verdict"] = f"noise check: pooled cost ratio {c['cost_ratio']:.2f} ({'ok' if valid else 'TOO NOISY'})"
                elif not valid:
                    c["verdict"] = "no verdict: the cell is too noisy (A2 differs from A by more than 10%)"
                else:
                    acc, eff = verdict(c)
                    c["verdict"] = f"accuracy {acc}; efficiency {eff}"
        md += ["", "| Comparison | Role | Instances | Accuracy difference (points) [CI] | Cost per correct ratio [CI] | "
               "Cost ratio [CI] | Holm p | Verdict |", "|---|---|---|---|---|---|---|---|"]
        for c in comps:
            md.append(f"| {c['x']} vs {c['y']} | {c['role']} | {c['n']} | {c['acc_diff']:+.1f} "
                      f"[{c['acc_ci'][0]:+.1f}, {c['acc_ci'][1]:+.1f}] | {c['cpc_ratio']:.2f} "
                      f"[{c['cpc_ci'][0]:.2f}, {c['cpc_ci'][1]:.2f}] | {c['cost_ratio']:.2f} "
                      f"[{c['cost_ci'][0]:.2f}, {c['cost_ci'][1]:.2f}] | "
                      f"{c['p_holm']:.3f} | " if "p_holm" in c else
                      f"| {c['x']} vs {c['y']} | {c['role']} | {c['n']} | {c['acc_diff']:+.1f} "
                      f"[{c['acc_ci'][0]:+.1f}, {c['acc_ci'][1]:+.1f}] | {c['cpc_ratio']:.2f} "
                      f"[{c['cpc_ci'][0]:.2f}, {c['cpc_ci'][1]:.2f}] | {c['cost_ratio']:.2f} "
                      f"[{c['cost_ci'][0]:.2f}, {c['cost_ci'][1]:.2f}] | — | ")
            md[-1] += f"{c['verdict']} |"
        md += exercised(rows, cell)
        js["cells"][cell] = comps
    return md, js


def exercised(rows: list[dict], cell: str) -> list[str]:
    """Which hypotheses could act in this cell: a hypothesis without its mechanism firing gets no verdict."""
    by = defaultdict(list)
    for r in rows:
        if r["cell"] == cell:
            by[r["arm"]].append(r)
    days = lambda arm: [d for r in by.get(arm, []) for d in r["days"]]  # noqa: E731
    h1 = sum(d.get("auto_memory_writes") or 0 for d in days("A")) + sum(d.get("note_writes") or 0 for d in days("V2"))
    h2 = sum(d.get("report_previews") or 0 for d in days("L") + days("V2"))
    h3 = sum(r["compactions"] for arm in by for r in by[arm])
    line = lambda name, n: f"- {name}: {'exercised' if n else 'NOT exercised'} ({n})"  # noqa: E731
    return ["", "Mechanisms:", line("H1 notes across sessions (auto-memory writes in A + note writes in V2)", h1),
            line("H2 previews (report previews in L and V2)", h2), line("H3 compaction (compactions, all arms)", h3)]


# ---- pilot gates ---------------------------------------------------------------------------------------------------
def gates(rows: list[dict]) -> list[str]:
    sys.path.insert(0, str(Path(__file__).resolve().parent))
    import cc_ledger as L

    res = []

    def gate(name, ok, detail):
        res.append(f"| {name} | {'PASS' if ok else 'FAIL'} | {detail} |")

    # G1 logging
    missing = []
    for r in rows:
        d = Path(r["_dir"]) / "runs" / r["run"]
        need = ["config.json", "key.json"] + [f"day_{x['day']:02d}.stream.jsonl.gz" for x in r["days"]]
        missing += [f"{r['run']}/{n}" for n in need if not (d / n).exists()]
        if not list((d / "transcripts").glob("*.jsonl")):
            missing.append(f"{r['run']}/transcripts")
    gate("G1 logging", not missing, f"{len(missing)} missing" + (f": {missing[:3]}" if missing else ""))
    # G2 isolation
    flags = [f for r in rows for d in r["days"] for f in d.get("isolation_flags") or []]
    gate("G2 isolation", not flags, f"{len(flags)} accesses outside the run" + (f": {flags[:2]}" if flags else ""))
    # G3 realistic baseline
    a_mem = sum(d.get("auto_memory_writes") or 0 for r in rows if r["arm"] in ("A", "A2") for d in r["days"])
    a0_mem = sum(d.get("auto_memory_writes") or 0 for r in rows if r["arm"] == "A0" for d in r["days"])
    a_snap = all((Path(r["_dir"]) / "runs" / r["run"] / "snapshots" / f"day_{len(r['days']):02d}" /
                  "claude_auto_memory").exists() for r in rows if r["arm"] == "A")
    micro = sum(r["microcompacts"] for r in rows)
    gate("G3 realistic baseline", a_mem > 0 and a0_mem == 0 and a_snap,
         f"auto-memory writes A/A2 {a_mem}, A0 {a0_mem}; A memory folder present {a_snap}; microcompacts logged {micro}")
    # G4 cold days: each day's first call writes at least Claude Code's own prompt to the cache
    cold, total = 0, 0
    for r in rows:
        if r["cell"] not in ("N", "R100", "R500"):
            continue
        for x in r["days"]:
            f = Path(r["_dir"]) / "runs" / r["run"] / f"day_{x['day']:02d}.calls.jsonl"
            first = json.loads(f.read_text().splitlines()[0]) if f.exists() and f.read_text().strip() else {}
            total += 1
            cold += first.get("cache_write", 0) >= 8_000
    gate("G4 cold days", total and cold == total, f"{cold}/{total} days start by writing >= 8K tokens to the cache")
    # G5 mechanisms fire
    def kinds(arm, key):
        out = defaultdict(int)
        for r in rows:
            if r["arm"] == arm:
                for d in r["days"]:
                    for k, v in (d.get("report_kinds") or {}).items():
                        out[k] += v.get(key, 0)
        return out
    a_cut, l_prev, v_prev = kinds("A", "cc_cut"), kinds("L", "preview"), kinds("V2", "preview")
    r100 = [r for r in rows if r["cell"] == "R100" and r["arm"] == "A"]
    v2 = [r for r in rows if r["arm"] == "V2"]
    recall_v2 = 0
    for r in v2:
        f = Path(r["_dir"]) / "runs" / r["run"] / "hook_timing.jsonl"
        if f.exists():
            recall_v2 += sum(1 for line in f.read_text().splitlines() if json.loads(line).get("recall_chars"))
    checks = {
        "A cuts the audit log": a_cut.get("audit", 0) > 0,
        "A gets the 15K reports in full": a_cut.get("receipts", 0) == 0 and a_cut.get("shipments", 0) == 0,
        "L previews all three": all(l_prev.get(k, 0) > 0 for k in ("receipts", "shipments", "audit")),
        "V2 previews all three": all(v_prev.get(k, 0) > 0 for k in ("receipts", "shipments", "audit")),
        "R100 compacts at least twice": bool(r100) and all(r["compactions"] >= 2 for r in r100),
        "V2 writes notes": sum(d.get("note_writes") or 0 for r in v2 for d in r["days"]) > 0,
        "V2 recalls on day >= 2": recall_v2 > 0,
        "A+ writes NOTES.md": sum(d.get("notes_md_writes") or 0 for r in rows if r["arm"] == "Aplus" for d in r["days"]) > 0,
    }
    gate("G5 mechanisms fire", all(checks.values()), "; ".join(f"{k}: {'yes' if v else 'NO'}" for k, v in checks.items()))
    # G6 grader
    seeds = sorted({r["seed"] for r in rows if r["cell"] != "F2"})
    oracle_ok = all(L.solve(L.generate(s, days=max(len(r["days"]) for r in rows if r["seed"] == s))) ==
                    L.generate(s, days=max(len(r["days"]) for r in rows if r["seed"] == s))["key"] for s in seeds)
    parsed = [d["grade"]["parsed"] for r in rows if r["cell"] != "F2" for d in r["days"]]
    gate("G6 grader", oracle_ok and all(parsed), f"key reproducible from reports {oracle_ok}; answers parsed "
         f"{sum(parsed)}/{len(parsed)}")
    # G7 noise: A against A2 on the same instances
    by = {(r["cell"], r["arm"], r["instance"]): r for r in rows}
    pairs = [(by[k], by[(k[0], "A2", k[2])]) for k in by if k[1] == "A" and (k[0], "A2", k[2]) in by]
    spread = max((abs(math.log(b["cost"] / a["cost"])) for a, b in pairs if a["cost"] and b["cost"]), default=math.inf)
    accd = max((abs(100 * (a["accuracy"] - b["accuracy"])) for a, b in pairs), default=math.inf)
    gate("G7 noise", spread <= 0.35 and accd <= 10, f"{len(pairs)} pairs; largest |log cost ratio| {spread:.2f}; "
         f"largest accuracy difference {accd:.1f} points")
    # G8 cost against the estimates (scaled to the planned run length)
    parts, ok = [], True
    for cell in sorted({r["cell"] for r in rows}):
        rs = [r for r in rows if r["cell"] == cell]
        planned = 5 if cell == "F2" else 10
        per_run = st.mean(r["cost"] * planned / max(1, len(r["days"])) for r in rs)
        within = 0.5 * ESTIMATE[cell] <= per_run <= 1.5 * ESTIMATE[cell]
        ok &= within
        parts.append(f"{cell}: ${per_run:.2f} per full run against ${ESTIMATE[cell]:.2f}{'' if within else ' (OUT)'}")
    gate("G8 cost", ok, "; ".join(parts))
    # G9 hooks
    times, errors = [], 0
    for r in rows:
        f = Path(r["_dir"]) / "runs" / r["run"] / "hook_timing.jsonl"
        if f.exists():
            for line in f.read_text().splitlines():
                e = json.loads(line)
                times.append(e["ms"])
                errors += bool(e.get("error"))
    med = st.median(times) if times else 0.0
    gate("G9 hooks", errors == 0 and med < 100, f"{len(times)} hook calls, {errors} errors, median {med:.1f} ms")
    return ["\n## Pilot gates\n", "| Gate | Result | Detail |", "|---|---|---|"] + res


def main() -> None:
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    rows = load(args)
    md, js = analyse(rows, random.Random(20261121))
    if "--gates" in sys.argv:
        md += gates(rows)
    text = "\n".join(md) + "\n"
    out = Path(args[0])
    (out / "analysis.md").write_text(text)
    (out / "analysis.json").write_text(json.dumps(js, indent=1, default=str))
    print(text)


if __name__ == "__main__":
    main()
