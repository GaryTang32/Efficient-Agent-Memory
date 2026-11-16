"""Failure taxonomy (step 3 of the weakness hunt): label why a memory setting lost an issue its ceiling resolved.

    python scripts/label_failures.py cases     # list the cases from the traced runs (no model calls)
    python scripts/label_failures.py label     # a judge labels each case with a fixed rubric (Sonnet, about $0.05 each)
    python scripts/label_failures.py page      # docs/results/failure-audit.html: every case, 20% marked for audit

A case is one session of a traced run (results/traced_swe-*.jsonl, traces in results/traces/) where a memory setting
did not resolve an issue that the ceiling of the same run resolved. Cases whose setting resolved the same issue in
another run are pre-labelled `noise` from the data, before any judge sees them. The judge reads the session's
trace: harness events (compaction, previews, guard offloads, overflow), its tool calls, its final patch and test
report, and the ceiling's patch for comparison.
"""

from __future__ import annotations

import argparse
import gzip
import html
import json
import random
import sys
from collections import defaultdict
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

RESULTS = ROOT / "results"
CASES = RESULTS / "failure_cases.jsonl"
LABELS = RESULTS / "failure_labels.jsonl"
PAGE = ROOT / "docs" / "results" / "failure-audit.html"
CEILING = "naive@native"

RUBRIC = {
    "lost_in_compaction": "information the fix needed was in the conversation before a compaction or reset and was "
                          "missing or wrong afterwards (the recap or summary dropped it), and the work went astray",
    "preview_hid_key": "a head/tail preview cut out the part of a tool output that mattered (an error, a failing "
                       "test, a code location) and the agent did not fetch it",
    "stopped_at_window": "the session ended because the context window filled or the step limit was reached, before "
                         "a working fix was in place",
    "guard_offload": "the in-step guard moved an output out of the context and the agent did not read it back",
    "wrong_fix": "the agent had the information it needed but wrote an incorrect or incomplete fix (a model error "
                 "unrelated to memory)",
    "unverified": "the agent stopped without running the relevant tests, or ignored a failing test",
    "other": "none of the above; explain",
}
PROMPT = """You are auditing why an AI coding agent failed a SWE-bench issue under a memory setting, when the same
agent without memory limits (the "ceiling") fixed it in the same run. Choose exactly one label:

{rubric}

Decide from the evidence below, not from guesses. Prefer a memory-related label only when the trace shows the memory
step caused the failure; otherwise use wrong_fix or unverified.

<setting>{spec}</setting>
<issue>{issue}</issue>
<harness_events>
{events}
</harness_events>
<tool_calls>
{tools}
</tool_calls>
<agent_final_answer>
{answer}
</agent_final_answer>
<agent_patch>
{patch}
</agent_patch>
<test_report>
{report}
</test_report>
<ceiling_patch>
{ceiling_patch}
</ceiling_patch>

Reply with JSON only: {{"label": "<one label>", "evidence": "<one or two sentences citing the trace>",
"confidence": "high" | "medium" | "low"}}"""


def rows() -> list[dict]:
    out = []
    for f in sorted(RESULTS.glob("traced_swe-*-r*.jsonl")):
        run = f.stem.rsplit("-", 1)[1]
        for line in f.read_text().splitlines():
            if line.strip():
                out.append({**json.loads(line), "_run": run})
    return out


def trace(run_id: str) -> list[dict]:
    path = RESULTS / "traces" / f"{run_id}.jsonl.gz"
    if not path.exists():
        return []
    with gzip.open(path, "rt") as fh:
        return [json.loads(line) for line in fh]


def find_cases() -> list[dict]:
    rs = [r for r in rows() if r.get("run_id")]
    by = defaultdict(dict)  # (model, run, instance) -> spec -> row
    for r in rs:
        by[(r["model"], r["_run"], r["instance"])][r["spec"].split("#")[0]] = r
    solved = defaultdict(int)  # (model, spec, issue) -> runs that resolved it
    for r in rs:
        for k, s in enumerate(r["round_scores"]):
            solved[(r["model"], r["spec"].split("#")[0], r["gold"].split(", ")[k])] += s == 1.0
    cases = []
    for (model, run, inst), cells in by.items():
        ceil = cells.get(CEILING)
        if not ceil:
            continue
        issues = ceil["gold"].split(", ")
        for spec, r in cells.items():
            if spec == CEILING:
                continue
            for k, issue in enumerate(issues):
                if ceil["round_scores"][k] == 1.0 and r["round_scores"][k] < 1.0:
                    cases.append({"id": f"{model}|{run}|{spec}|{issue}", "model": model, "run": run, "spec": spec,
                                  "issue": issue, "session": k, "run_id": r["run_id"], "ceiling_run_id": ceil["run_id"],
                                  "noise": solved[(model, spec, issue)] > 0})
    return cases


def evidence(case: dict) -> dict:
    t = trace(case["run_id"])
    k = case["session"]
    ev = [r for r in t if r["table"] == "event" and r.get("session") == k]
    tools = [r for r in t if r["table"] == "tool_call" and r.get("session") == k]
    grade = next((r for r in t if r["table"] == "grade" and r.get("session") == k), {})
    sess = next((r for r in t if r["table"] == "session" and r.get("session") == k), {})
    cgrade = next((r for r in trace(case["ceiling_run_id"]) if r["table"] == "grade" and r.get("session") == k), {})
    return {
        "events": "\n".join(f"step {e.get('step')}: {e['kind']} {e.get('fields', '')[:300]}" for e in ev) or "(none)",
        "tools": "\n".join(f"- {c['name']}({c['input'][:200]}) -> {c.get('output_chars')} chars"
                           + (" ERROR" if c.get("error") else "") for c in tools[-40:]) or "(none)",
        "answer": (sess.get("text") or "")[:1500],
        "patch": ((grade.get("patch") or {}).get("text") or "(no patch)")[:6000],
        "report": ((grade.get("report") or {}).get("text") or "")[:2000],
        "ceiling_patch": ((cgrade.get("patch") or {}).get("text") or "(not recorded)")[:4000],
        "stopped": any(e["kind"] in ("context_overflow", "stopped") for e in ev),
        "compactions": sum(e["kind"].endswith("_rebuild") for e in ev),
    }


def label(cases: list[dict], workers: int = 4) -> None:
    from eam.llm.routes import make_client
    from eam.llm.types import Request
    from eam.models import load_models

    done = {json.loads(line)["id"] for line in LABELS.read_text().splitlines()} if LABELS.exists() else set()
    todo = [c for c in cases if c["id"] not in done and not c["noise"]]
    model, client = load_models()["cc-sonnet"], make_client("claude-cli")
    rubric = "\n".join(f"- {k}: {v}" for k, v in RUBRIC.items())

    def one(case):
        e = evidence(case)
        prompt = PROMPT.format(rubric=rubric, spec=case["spec"], issue=case["issue"], **{
            k: e[k] for k in ("events", "tools", "answer", "patch", "report", "ceiling_patch")})
        r = client.converse(Request(model=model, system=[], messages=[{"role": "user", "content": [{"text": prompt}]}],
                                    max_tokens=800))
        try:
            out = json.loads(r.text[r.text.index("{"): r.text.rindex("}") + 1])
        except ValueError:
            out = {"label": "other", "evidence": f"unparsed judge reply: {r.text[:200]}", "confidence": "low"}
        if out.get("label") not in RUBRIC:
            out["label"] = "other"
        return {**case, **out, "stopped": e["stopped"], "compactions": e["compactions"],
                "judge_cost_usd": r.reported_cost_usd or 0.0}

    with ThreadPoolExecutor(workers) as ex, LABELS.open("a") as fh:
        for row in ex.map(one, todo):
            fh.write(json.dumps(row) + "\n")
            fh.flush()
            print(row["id"], row["label"], row["confidence"])


def page(cases: list[dict]) -> None:
    labels = {json.loads(line)["id"]: json.loads(line) for line in LABELS.read_text().splitlines()} \
        if LABELS.exists() else {}
    rows_ = [{**c, **labels.get(c["id"], {}), "label": "noise" if c["noise"] else labels.get(c["id"], {}).get("label",
                                                                                                         "unlabelled")}
             for c in cases]
    judged = [r for r in rows_ if r["label"] not in ("noise", "unlabelled")]
    random.Random(0).shuffle(judged)
    audit = {r["id"] for r in judged[: max(1, round(0.2 * len(judged)))]} if judged else set()
    counts = defaultdict(int)
    for r in rows_:
        counts[r["label"]] += 1
    body = []
    for r in sorted(rows_, key=lambda r: (r["id"] not in audit, r["model"], r["spec"], r["issue"], r["run"])):
        e = evidence(r) if r["id"] in audit else {}
        detail = (f"<details><summary>Trace evidence</summary><h4>Events</h4><pre>{html.escape(e['events'])}</pre>"
                  f"<h4>Tool calls</h4><pre>{html.escape(e['tools'])}</pre><h4>Agent patch</h4>"
                  f"<pre>{html.escape(e['patch'])}</pre><h4>Test report</h4><pre>{html.escape(e['report'])}</pre>"
                  f"<h4>Ceiling patch</h4><pre>{html.escape(e['ceiling_patch'])}</pre></details>") if e else ""
        pick = (f'<label><input type="radio" name="{html.escape(r["id"])}" value="agree"> agree</label> '
                f'<label><input type="radio" name="{html.escape(r["id"])}" value="disagree"> disagree</label> '
                f'<input class="fix" data-id="{html.escape(r["id"])}" placeholder="correct label (if disagree)">'
                ) if r["id"] in audit else ""
        body.append(f'<tr class="{"audit" if r["id"] in audit else ""}"><td>{html.escape(r["model"])}</td>'
                    f'<td>{html.escape(r["spec"])}</td><td>{html.escape(r["issue"])}</td><td>{r["run"]}</td>'
                    f'<td><b>{html.escape(r["label"])}</b> <small>{html.escape(r.get("confidence", ""))}</small></td>'
                    f'<td>{html.escape(r.get("evidence", "solved by this setting in another run"))}{detail}</td>'
                    f'<td>{pick}</td></tr>')
    summary = " · ".join(f"{k}: {v}" for k, v in sorted(counts.items(), key=lambda kv: -kv[1]))
    PAGE.parent.mkdir(parents=True, exist_ok=True)
    PAGE.write_text(f"""<!doctype html><html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1"><title>Failure audit</title><style>
:root{{--bg:#fff;--ink:#111;--muted:#666;--line:#ddd;--hi:#fff8e1}}
@media (prefers-color-scheme:dark){{:root{{--bg:#111;--ink:#eee;--muted:#999;--line:#333;--hi:#2a2410}}}}
body{{background:var(--bg);color:var(--ink);font:14px/1.45 system-ui,sans-serif;margin:16px}}
table{{border-collapse:collapse;width:100%}}td{{border-top:1px solid var(--line);padding:6px;vertical-align:top}}
tr.audit{{background:var(--hi)}}pre{{white-space:pre-wrap;font-size:12px;max-height:300px;overflow:auto}}
small{{color:var(--muted)}}.wrap{{overflow-x:auto}}button{{margin:8px 0}}</style></head><body>
<h1>Failure audit</h1><p>{len(rows_)} cases where a memory setting missed an issue its same-run ceiling resolved.
{summary}.</p><p>Highlighted rows ({len(audit)}, 20% of the judged cases, drawn at random) are for your audit: open the
trace evidence, mark agree or disagree, and press <b>Copy my audit</b>; paste the result back into the chat.</p>
<button id="copy">Copy my audit</button><div class="wrap"><table><tr><td>Model</td><td>Setting</td><td>Issue</td>
<td>Run</td><td>Label</td><td>Judge's evidence</td><td>Audit</td></tr>{''.join(body)}</table></div>
<script>document.getElementById('copy').onclick=()=>{{const out={{}};
document.querySelectorAll('input[type=radio]:checked').forEach(i=>{{out[i.name]={{verdict:i.value}}}});
document.querySelectorAll('input.fix').forEach(i=>{{if(i.value){{(out[i.dataset.id]=out[i.dataset.id]||{{}}).label=i.value}}}});
navigator.clipboard.writeText(JSON.stringify(out,null,1)).then(()=>alert(Object.keys(out).length+' audit answers copied'))}};
</script></body></html>""")
    print(f"wrote {PAGE}: {len(rows_)} cases, {len(audit)} to audit; {summary}")


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("cmd", choices=["cases", "label", "page"])
    ap.add_argument("--workers", type=int, default=4)
    a = ap.parse_args()
    cases = find_cases()
    CASES.write_text("".join(json.dumps(c) + "\n" for c in cases))
    if a.cmd == "cases":
        n = sum(c["noise"] for c in cases)
        print(f"{len(cases)} cases ({n} pre-labelled noise, {len(cases) - n} for the judge) -> {CASES}")
    elif a.cmd == "label":
        label(cases, a.workers)
    else:
        page(cases)


if __name__ == "__main__":
    main()
