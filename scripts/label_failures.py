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
    esc = html.escape
    short = {"naive@native": "ceiling", "automem:workspace=false,ingest=0.1": "lean",
             "automem:workspace=false,ingest=0.1,compact=handoff,handoff_variant=swe": "lean + handoff",
             "eocc:variant=swe": "EoCC alone"}

    def name(r: dict) -> str:
        return f"{r['model'].removeprefix('cc-').title()} · {short.get(r['spec'], r['spec'])} · {r['issue']} · {r['run']}"

    def evidence_html(r: dict) -> str:
        e = evidence(r)
        parts = [("Harness events", e["events"]), ("Tool calls", e["tools"]), ("Agent patch", e["patch"]),
                 ("Test report", e["report"]), ("Ceiling patch", e["ceiling_patch"])]
        return "<details><summary>Trace evidence</summary>" + "".join(
            f"<h4>{t}</h4><pre>{esc(v or '(none)')}</pre>" for t, v in parts) + "</details>"

    cards = []
    for r in [r for r in rows_ if r["id"] in audit]:
        rid = esc(r["id"])
        cards.append(f"""<article class="case audit"><header><span class="tag t-{esc(r['label'])}">{esc(r['label'])}</span>
<span class="conf">{esc(r.get('confidence', ''))} confidence</span><h3>{esc(name(r))}</h3></header>
<p>{esc(r.get('evidence', ''))}</p>{evidence_html(r)}
<fieldset><legend>Your verdict</legend>
<label><input type="radio" name="{rid}" value="agree"> Agree</label>
<label><input type="radio" name="{rid}" value="disagree"> Disagree</label>
<select class="fix" data-id="{rid}" aria-label="Correct label if you disagree"><option value="">Correct label (if you disagree)</option>
{''.join(f'<option>{k}</option>' for k in RUBRIC)}</select></fieldset></article>""")
    judged_rows = []
    for r in sorted((r for r in rows_ if r["label"] != "noise" and r["id"] not in audit),
                    key=lambda r: (r["label"], r["model"], r["spec"], r["issue"], r["run"])):
        judged_rows.append(f"""<article class="case"><header><span class="tag t-{esc(r['label'])}">{esc(r['label'])}</span>
<span class="conf">{esc(r.get('confidence', ''))} confidence</span><h3>{esc(name(r))}</h3></header>
<p>{esc(r.get('evidence', ''))}</p>{evidence_html(r)}</article>""")
    noise_rows = "".join(f"<tr><td>{esc(r['model'].removeprefix('cc-'))}</td><td>{esc(short.get(r['spec'], r['spec']))}</td>"
                         f"<td>{esc(r['issue'])}</td><td>{esc(r['run'])}</td></tr>"
                         for r in sorted((r for r in rows_ if r["label"] == "noise"),
                                         key=lambda r: (r["model"], r["spec"], r["issue"], r["run"])))
    total = max(1, len(rows_))
    bars = "".join(f'<div class="bar"><span class="k">{esc(k)}</span><span class="track"><span class="fill t-{esc(k)}" '
                   f'style="width:{100 * v / total:.1f}%"></span></span><span class="v">{v}</span></div>'
                   for k, v in sorted(counts.items(), key=lambda kv: -kv[1]))
    rubric = "".join(f"<dt>{esc(k)}</dt><dd>{esc(v)}</dd>" for k, v in {
        "noise": "the setting resolved this issue in another run, so the miss is run-to-run variation", **RUBRIC}.items())
    PAGE.parent.mkdir(parents=True, exist_ok=True)
    PAGE.write_text(f"""<title>Memory Failure Audit</title>
<meta name="claude:viewport-fit-sides" content="cover">
<link rel="stylesheet" href="https://fonts.googleapis.com/css2?family=Inter:wght@400;600&family=JetBrains+Mono:wght@400&display=swap">
<style>
/* layout: one reading column; audit cards first, then the judged cases, then the noise table */
:root{{--bg:#f7f8f9;--card:#fff;--ink:#16202a;--muted:#5a6773;--line:#dde2e7;--accent:#1f6feb;--hi:#fff4d6;
--c-noise:#9aa5b1;--c-wrong:#c2410c;--c-window:#7c3aed;--c-lost:#0f766e;--c-other:#64748b;
--sans:Inter,system-ui,-apple-system,"Segoe UI",sans-serif;--mono:"JetBrains Mono",ui-monospace,Menlo,monospace}}
@media (prefers-color-scheme:dark){{:root:not([data-theme="light"]){{--bg:#0f1418;--card:#161d23;--ink:#e6ebef;--muted:#97a3ae;
--line:#2a343d;--accent:#6ea8fe;--hi:#2b2614;--c-noise:#5f6b76;--c-wrong:#f08a4b;--c-window:#a78bfa;--c-lost:#2dd4bf;
--c-other:#94a3b8;color-scheme:dark}}}}
:root[data-theme="dark"]{{--bg:#0f1418;--card:#161d23;--ink:#e6ebef;--muted:#97a3ae;--line:#2a343d;--accent:#6ea8fe;
--hi:#2b2614;--c-noise:#5f6b76;--c-wrong:#f08a4b;--c-window:#a78bfa;--c-lost:#2dd4bf;--c-other:#94a3b8;color-scheme:dark}}
body{{background:var(--bg);color:var(--ink);font:15px/1.5 var(--sans)}}
main{{max-width:880px;margin:0 auto;padding-block:24px 48px;padding-left:max(16px,env(safe-area-inset-left,0px));
padding-right:max(16px,env(safe-area-inset-right,0px));display:grid;gap:20px}}
h1{{font-size:26px;margin:0;text-wrap:balance}}h2{{font-size:18px;margin:12px 0 0}}h3{{font-size:15px;margin:6px 0 0;
overflow-wrap:anywhere}}h4{{font-size:12px;text-transform:uppercase;letter-spacing:.06em;color:var(--muted);margin:12px 0 4px}}
p{{margin:0;max-width:70ch}}.lede{{color:var(--muted)}}
.bars{{display:grid;gap:6px;font-variant-numeric:tabular-nums}}.bar{{display:grid;grid-template-columns:150px 1fr 32px;
gap:10px;align-items:center;font-size:13px}}.track{{background:var(--line);border-radius:3px;height:10px}}
.fill{{display:block;height:10px;border-radius:3px;background:var(--c-other)}}.v{{text-align:right}}
.case{{background:var(--card);border:1px solid var(--line);border-radius:8px;padding:14px 16px;display:grid;gap:8px;min-width:0}}
.case.audit{{background:var(--hi)}}.tag{{font:12px var(--mono);padding:2px 8px;border-radius:99px;color:#fff;
background:var(--c-other)}}.conf{{font-size:12px;color:var(--muted);margin-left:8px}}
.t-noise{{background:var(--c-noise)}}.t-wrong_fix{{background:var(--c-wrong)}}.t-stopped_at_window{{background:var(--c-window)}}
.t-lost_in_compaction{{background:var(--c-lost)}}
details summary{{cursor:pointer;color:var(--accent);font-size:13px}}
pre{{font:12px/1.45 var(--mono);white-space:pre-wrap;overflow-wrap:anywhere;max-height:280px;overflow:auto;margin:0;
background:var(--bg);border:1px solid var(--line);border-radius:6px;padding:8px}}
fieldset{{border:1px solid var(--line);border-radius:6px;display:flex;flex-wrap:wrap;gap:12px;align-items:center}}
legend{{font-size:12px;color:var(--muted)}}select,button,textarea{{font:inherit;color:inherit;background:var(--card);
border:1px solid var(--line);border-radius:6px;padding:6px 10px}}
button{{background:var(--accent);color:#fff;border:0;cursor:pointer;font-weight:600}}
:focus-visible{{outline:2px solid var(--accent);outline-offset:2px}}
.copy{{display:flex;flex-wrap:wrap;gap:10px;align-items:center}}textarea{{width:100%;font:12px var(--mono);min-height:90px}}
dl{{display:grid;grid-template-columns:max-content 1fr;gap:4px 14px;font-size:13px;margin:0}}dt{{font-family:var(--mono)}}
dd{{margin:0;color:var(--muted)}}.wrap{{overflow-x:auto}}table{{border-collapse:collapse;width:100%;font-size:13px}}
td,th{{border-top:1px solid var(--line);padding:5px 8px;text-align:left}}th{{color:var(--muted);font-weight:600}}
@media (max-width:560px){{.bar{{grid-template-columns:120px 1fr 28px}}dl{{grid-template-columns:1fr}}dd{{margin-bottom:6px}}}}
</style>
<main>
<h1>Memory Failure Audit</h1>
<p class="lede">{len(rows_)} Django sessions where a memory setting missed an issue that the same run's ceiling
(full context) fixed, from the traced re-runs on SWE-bench Verified workdays. A case is labelled noise when the setting
fixed the same issue in another run; a Sonnet judge labelled the rest from the session trace.</p>
<section class="bars" aria-label="Cases by label">{bars}</section>
<h2>Your audit: {len(audit)} cases, 20% of the judged ones</h2>
<p>Open the trace evidence, choose agree or disagree, and pick the right label if you disagree. Then copy your answers
and paste them into the chat.</p>
{''.join(cards)}
<div class="copy"><button id="copy" type="button">Copy my audit</button><span id="status" role="status"></span></div>
<textarea id="out" readonly hidden aria-label="Your audit answers"></textarea>
<h2>The other judged cases ({len(judged_rows)})</h2>
{''.join(judged_rows)}
<h2>Noise ({counts.get('noise', 0)})</h2>
<div class="wrap"><table><tr><th>Model</th><th>Setting</th><th>Issue</th><th>Run</th></tr>{noise_rows}</table></div>
<h2>Labels</h2><dl>{rubric}</dl>
</main>
<script>
document.getElementById('copy').addEventListener('click',()=>{{
 const out={{}};
 document.querySelectorAll('input[type=radio]:checked').forEach(i=>{{out[i.name]={{verdict:i.value}}}});
 document.querySelectorAll('select.fix').forEach(s=>{{if(s.value)(out[s.dataset.id]=out[s.dataset.id]||{{}}).label=s.value}});
 const text=JSON.stringify(out,null,1),box=document.getElementById('out'),st=document.getElementById('status');
 box.value=text;box.hidden=false;
 const n=Object.keys(out).length+' of {len(audit)} answered';
 const fallback=()=>{{box.focus();box.select();st.textContent=n+'. Copy the selected text below.'}};
 try{{navigator.clipboard.writeText(text).then(()=>{{st.textContent=n+', copied. Paste it into the chat.'}},fallback)}}
 catch(e){{fallback()}}
}});
</script>
""")
    summary = " · ".join(f"{k}: {v}" for k, v in sorted(counts.items(), key=lambda kv: -kv[1]))
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
