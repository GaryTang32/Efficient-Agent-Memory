"""Step 4, recall measurement: are AutoMemory's recalled notes worth their tokens?

    scripts/run_recall.sh                     # traced automem_v2 runs on the multi-session tasks
    python scripts/recall_report.py           # tables below, also written to results/recall_report.md

For every session of every traced AutoMemory run with notes (results/recall-*.jsonl, traces in results/traces/):

* **share**: recall tokens over the session's mean prompt (the notes sit in the first message, so every call of the
  session carries them). The decision rule from the plan: selective recall is only worth building if notes take
  more than 15% of the prompt.
* **growth**: recall size by session index, to see whether notes pile up over a ten-day job.
* **carried**: of the facts a session needs from earlier sessions (the tasks' ground truth: closing stock, totals,
  corrected events), the share present in the recalled notes at session start.
* **use**: the session's score when every needed fact was carried against when some were missing, and how often the
  agent re-opened earlier days' files (re-reading instead of using its notes) or called read_notes.

Standard library only.
"""

from __future__ import annotations

import gzip
import json
import re
import statistics as st
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
RESULTS = ROOT / "results"
THRESHOLD = 0.15
NUM = re.compile(r"-?\d[\d,]*(?:\.\d+)?")


def load_runs() -> list[dict]:
    rows = []
    for f in sorted(RESULTS.glob("recall-*.jsonl")):
        for line in f.read_text().splitlines():
            r = json.loads(line)
            if r.get("run_id") and not r.get("error"):
                rows.append(r)
    return rows


def load_trace(run_id: str) -> dict[str, list[dict]]:
    path = RESULTS / "traces" / f"{run_id}.jsonl.gz"
    tables: dict[str, list[dict]] = defaultdict(list)
    if path.exists():
        with gzip.open(path, "rt", encoding="utf-8") as fh:
            for line in fh:
                r = json.loads(line)
                tables[r["table"]].append(r)
    return tables


def entity(dep: dict) -> str:
    if dep.get("event_id"):
        return dep["event_id"]
    m = re.search(r"(?:paid to|spend of|stock of) (.+?)(?: on day \d+)?$", dep["fact"])
    return m.group(1) if m else dep["fact"]


def carried(dep: dict, text: str) -> bool:
    """Is this fact in the recalled notes? A correction needs its event id; a carried figure needs a line naming
    the entity with the right number on it."""
    name = entity(dep)
    if dep["kind"] == "correction":
        return name in text
    value = float(json.loads(dep["value"]))
    for line in text.splitlines():
        if name in line:
            for n in NUM.findall(line):
                try:
                    if abs(float(n.replace(",", "")) - value) < 0.006:
                        return True
                except ValueError:
                    pass
    return False


def earlier_day_opens(tool_calls: list[dict], session: int) -> int:
    """ops_stream: files of earlier days opened again (D01-A ... on day 3 and later)."""
    n = 0
    for c in tool_calls:
        if c["name"] != "open_file":
            continue
        m = re.match(r"D(\d+)-", str((json.loads(c["input"]) if isinstance(c["input"], str) else c["input"] or {})
                                       .get("file_id", "")))
        n += bool(m) and int(m.group(1)) < session + 1
    return n


def sessions_of(row: dict, t: dict[str, list[dict]]) -> list[dict]:
    recall = defaultdict(list)
    for e in t["event"]:
        if e["kind"] == "automem_recall":
            recall[e["session"]].append(json.loads(e["fields"]))
    calls = defaultdict(list)
    for c in t["call"]:
        if c.get("tag") == "main" and c.get("session") is not None:
            calls[c["session"]].append(c["input_tokens"] + c["cache_read_tokens"] + c["cache_write_tokens"])
    deps = defaultdict(list)
    for d in t["dependency"]:
        deps[d["session"]].append(d)
    tools = defaultdict(list)
    for c in t["tool_call"]:
        tools[c["session"]].append(c)
    out = []
    for s in sorted(set(calls)):
        start = [r for r in recall[s] if r.get("when") == "start"]
        text = start[0]["recall_text"] if start else ""
        tokens = start[0]["tokens"] if start else 0
        prompt = st.mean(calls[s]) if calls[s] else 0
        need = deps[s]
        got = [carried(d, text) for d in need]
        out.append({
            "family": row["family"], "model": row["model"].removeprefix("cc-"), "instance": row["instance"],
            "session": s, "recall_tokens": tokens, "resets": sum(r.get("when") == "reset" for r in recall[s]),
            "mean_prompt": prompt, "share": tokens / prompt if prompt else 0.0, "calls": len(calls[s]),
            "needed": len(need), "carried": sum(got),
            "score": (row.get("round_scores") or [row.get("score")])[s] if s < len(row.get("round_scores") or [1]) else None,
            "reread": earlier_day_opens(tools[s], s) if row["family"] == "ops_stream" else 0,
            "read_notes": sum(c["name"] == "read_notes" for c in tools[s]),
            "write_note": sum(c["name"] == "write_note" for c in tools[s]),
        })
    return out


def pct(x: float) -> str:
    return f"{100 * x:.1f}%"


def report(sessions: list[dict]) -> str:
    out = ["# Recall measurement (step 4)\n"]
    groups = defaultdict(list)
    for s in sessions:
        groups[(s["model"], s["family"])].append(s)

    out.append("## Share of the prompt taken by recalled notes\n")
    out.append("| Model | Task | Sessions with recall | Median share | 90th pct | Max | Mean recall tokens | Verdict |")
    out.append("|---|---|---|---|---|---|---|---|")
    over = False
    for (m, f), ss in sorted(groups.items()):
        with_recall = [s for s in ss if s["recall_tokens"]]
        if not with_recall:
            out.append(f"| {m} | {f} | 0 | — | — | — | — | no recall |")
            continue
        shares = sorted(s["share"] for s in with_recall)
        p90 = shares[min(len(shares) - 1, int(0.9 * len(shares)))]
        verdict = "over 15%" if p90 > THRESHOLD else "under 15%"
        over |= p90 > THRESHOLD
        out.append(f"| {m} | {f} | {len(with_recall)} of {len(ss)} | {pct(st.median(shares))} | {pct(p90)} | "
                   f"{pct(shares[-1])} | {st.mean(s['recall_tokens'] for s in with_recall):,.0f} | {verdict} |")

    out.append("\n## Growth: recall tokens by session (median over runs)\n")
    for (m, f), ss in sorted(groups.items()):
        by = defaultdict(list)
        for s in ss:
            by[s["session"]].append(s)
        cells = " · ".join(f"{k + 1}: {st.median(x['recall_tokens'] for x in v):,.0f} ({pct(st.median(x['share'] for x in v))})"
                           for k, v in sorted(by.items()))
        out.append(f"- **{m} {f}**: {cells}")

    out.append("\n## Were the facts each session needed in its notes, and did that matter?\n")
    out.append("| Model | Task | Facts needed | Carried in notes | Score, all carried | Score, some missing | "
               "Earlier files re-opened per session | read_notes per session |")
    out.append("|---|---|---|---|---|---|---|---|")
    for (m, f), ss in sorted(groups.items()):
        need = [s for s in ss if s["needed"]]
        if not need:
            out.append(f"| {m} | {f} | — | — | — | — | — | {st.mean(s['read_notes'] for s in ss):.2f} |")
            continue
        full = [s["score"] for s in need if s["carried"] == s["needed"] and s["score"] is not None]
        part = [s["score"] for s in need if s["carried"] < s["needed"] and s["score"] is not None]
        fmt = lambda xs: f"{st.mean(xs):.2f} (n={len(xs)})" if xs else "—"  # noqa: E731
        out.append(f"| {m} | {f} | {sum(s['needed'] for s in need)} | "
                   f"{pct(sum(s['carried'] for s in need) / sum(s['needed'] for s in need))} | {fmt(full)} | "
                   f"{fmt(part)} | {st.mean(s['reread'] for s in need):.2f} | "
                   f"{st.mean(s['read_notes'] for s in ss):.2f} |")

    out.append("\n## Decision\n")
    out.append("Selective recall **is** worth building: notes exceed 15% of the prompt in at least one cell."
               if over else "Selective recall is **not** needed now: notes stay under 15% of the prompt in every cell "
                            "(90th percentile). Recall stays as it is.")
    return "\n".join(out) + "\n"


def main() -> None:
    rows = load_runs()
    if not rows:
        raise SystemExit("no results/recall-*.jsonl yet: run scripts/run_recall.sh")
    sessions = [s for r in rows for s in sessions_of(r, load_trace(r["run_id"]))]
    text = report(sessions)
    (RESULTS / "recall_report.md").write_text(text)
    (RESULTS / "recall_sessions.jsonl").write_text("".join(json.dumps(s) + "\n" for s in sessions))
    print(text)


if __name__ == "__main__":
    main()
