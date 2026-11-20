"""Step 5: did the targeted fixes help? Each fix against a baseline from the same day.

    scripts/run_step5.sh                      # the runs
    python scripts/step5_report.py            # tables below, also written to results/step5_report.md

Recall fixes (ops_stream, ledger_audit): automem_v2 (step 4's runs, results/recall-*.jsonl) against
recall_results=latest and recall_results=latest + note_ids (results/step5-*.jsonl), paired by task instance.
Test check (SWE-bench Django issues): lean against lean + verify (results/step5_swe-*.jsonl), paired by run and issue.

Standard library only.
"""

from __future__ import annotations

import json
import math
import statistics as st
import sys
from collections import defaultdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import recall_report as R  # noqa: E402

RESULTS = R.RESULTS
ARMS = {"automem:ingest=0.1": "automem_v2 (baseline)",
        "automem:ingest=0.1,recall_results=latest": "+ latest answer only",
        "automem:ingest=0.1,recall_results=latest,note_ids=true": "+ latest answer only + ids in notes"}


def rows(pattern: str) -> list[dict]:
    out = []
    for f in sorted(RESULTS.glob(pattern)):
        for line in f.read_text().splitlines():
            r = json.loads(line)
            if not r.get("error"):
                r["file"] = f.name
                out.append(r)
    return out


def sign_p(wins: int, losses: int) -> float:
    """Two-sided exact sign test."""
    n = wins + losses
    if not n:
        return 1.0
    k = min(wins, losses)
    return min(1.0, 2 * sum(math.comb(n, i) for i in range(k + 1)) / 2 ** n)


def recall_part() -> list[str]:
    data = [r for r in rows("recall-*.jsonl") + rows("step5-*.jsonl")
            if r["family"] in ("ops_stream", "ledger_audit")]
    out = ["## Recall fixes (multi-session tasks)\n",
           "Score: mean over runs (0-1). Solved: runs with every session fully answered. Cost: total, and the mean "
           "paired ratio to the baseline on the same instances. Recall share: median share of the prompt taken by "
           "the notes in the last three sessions. Carried: needed facts present in the notes. Re-opened: earlier "
           "days' files opened again per session (ops_stream).\n",
           "| Model | Task | Setting | Runs | Score | Solved | Cost | Cost vs baseline | Recall share | Carried | Re-opened |",
           "|---|---|---|---|---|---|---|---|---|---|---|"]
    by = defaultdict(list)
    for r in data:
        by[(r["model"].removeprefix("cc-"), r["family"], r["spec"].split("#")[0])].append(r)
    for (m, f) in sorted({(k[0], k[1]) for k in by}):
        base = {r["instance"]: r for r in by.get((m, f, "automem:ingest=0.1"), [])}
        for spec, label in ARMS.items():
            rs = by.get((m, f, spec), [])
            if not rs:
                continue
            sess = [s for r in rs for s in R.sessions_of(r, R.load_trace(r["run_id"]))]
            wr = [s for s in sess if s["recall_tokens"]]
            last = [s for s in wr if s["session"] >= max((x["session"] for x in wr), default=0) - 2]
            need = sum(s["needed"] for s in sess)
            ratios = [r["cost_usd"] / base[r["instance"]]["cost_usd"] for r in rs
                      if r["instance"] in base and base[r["instance"]]["cost_usd"]]
            out.append(
                f"| {m} | {f} | {label} | {len(rs)} | {st.mean(r['score'] for r in rs):.2f} | "
                f"{sum(bool(r.get('success')) for r in rs)}/{len(rs)} | ${sum(r['cost_usd'] for r in rs):.2f} | "
                f"{'—' if spec == 'automem:ingest=0.1' or not ratios else f'{100 * st.mean(ratios):.0f}%'} | "
                f"{R.pct(st.median(s['share'] for s in last)) if last else '—'} | "
                f"{R.pct(sum(s['carried'] for s in sess) / need) if need else '—'} | "
                f"{st.mean(s['reread'] for s in sess):.1f} |")
    return out


def verify_part() -> list[str]:
    data = rows("step5_swe-*.jsonl")
    out = ["\n## Test check on Django issues (lean vs lean + verify, same day)\n",
           "Resolved: issues fixed, summed over runs. Pairs: same run, same issue, one setting resolved it and the "
           "other did not. Checks: final answers sent back because the last test run still failed.\n",
           "| Model | Setting | Workday runs | Resolved | Cost | Cost vs lean | Checks fired | Pairs won / lost | Sign test p |",
           "|---|---|---|---|---|---|---|---|---|"]
    by = defaultdict(list)
    for r in data:
        by[(r["model"].removeprefix("cc-"), "verify" if "verify=true" in r["spec"] else "lean")].append(r)
    for m in sorted({k[0] for k in by}):
        lean = {(r["file"], r["instance"]): r for r in by.get((m, "lean"), [])}
        for arm in ("lean", "verify"):
            rs = by.get((m, arm), [])
            if not rs:
                continue
            resolved = sum(sum(r.get("round_scores") or [r["score"]]) for r in rs)
            cost = sum(r["cost_usd"] for r in rs)
            fired = sum((r.get("events") or {}).get("automem_verify", 0) for r in rs)
            won = lost = 0
            ratio = "—"
            if arm == "verify":
                paired = [(r, lean[(r["file"], r["instance"])]) for r in rs if (r["file"], r["instance"]) in lean]
                for a, b in paired:
                    for x, y in zip(a.get("round_scores") or [], b.get("round_scores") or []):
                        won += x > y
                        lost += x < y
                lc = sum(b["cost_usd"] for _, b in paired)
                ratio = f"{100 * sum(a['cost_usd'] for a, _ in paired) / lc:.0f}%" if lc else "—"
            out.append(f"| {m} | {'lean + verify' if arm == 'verify' else 'lean'} | {len(rs)} | {resolved:.0f} | "
                       f"${cost:.2f} | {ratio} | {fired if arm == 'verify' else '—'} | "
                       f"{f'{won} / {lost}' if arm == 'verify' else '—'} | "
                       f"{f'{sign_p(won, lost):.2f}' if arm == 'verify' else '—'} |")
    return out


def main() -> None:
    text = "# Step 5 results\n\n" + "\n".join(recall_part() + verify_part()) + "\n"
    spend = sum(r["cost_usd"] for r in rows("step5-*.jsonl") + rows("step5_swe-*.jsonl"))
    text += f"\nStep 5 spend so far: ${spend:.2f}\n"
    (RESULTS / "step5_report.md").write_text(text)
    print(text)


if __name__ == "__main__":
    main()
