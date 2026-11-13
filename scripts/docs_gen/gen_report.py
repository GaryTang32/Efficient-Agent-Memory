"""Generate docs/report.html: the work report (work done, findings, results, the Claude Code plugin and its pilot,
to-do list) in the reference brief's style (assets/ref.css, sprite.svg, navigation script), like docs/overview.html.

    python scripts/docs_gen/gen_report.py

Inputs: scripts/docs_gen/overview_data.json (SWE board, built by build_overview_data.py) and, when present,
results/cc_pilot-*.jsonl (the Claude Code pilot); both are git-ignored, the generated page is committed.
"""

from __future__ import annotations

import html
import json
import statistics as st
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import overview_extras as X  # noqa: E402
import readme_charts as RC  # noqa: E402

ROOT = HERE.parent.parent
ASSETS = HERE / "assets"
OUT = ROOT / "docs" / "report.html"
E = html.escape
D = json.loads((HERE / "overview_data.json").read_text())
SWE = D.get("__swe__", {})


def ic(name, cls="ic"):
    return f'<svg class="{cls}" aria-hidden="true"><use href="#i-{name}"/></svg>'


def lvl(text, kind):
    return f'<span class="lvl lvl-{kind}">{E(text)}</span>'


# ---- the Claude Code pilot ----------------------------------------------------------------------------------
def pilot():
    out = {}
    for m in ("haiku", "sonnet"):
        f = ROOT / "results" / f"cc_pilot-{m}.jsonl"
        if not f.exists():
            continue
        rows = [json.loads(x) for x in f.read_text().splitlines() if x.strip()]
        by = {}
        for r in rows:
            by.setdefault(r["setting"], {})[r["instance_id"]] = r
        common = sorted(set(by.get("plain", {})) & set(by.get("plugin", {})))
        if not common:
            continue
        cell = {}
        for s in ("plain", "plugin"):
            rs = [by[s][i] for i in common]
            cell[s] = dict(n=len(rs), resolved=sum(bool(r.get("resolved")) for r in rs),
                           cost=sum(r.get("cost_usd", 0) for r in rs),
                           peak=st.median(r.get("peak_prompt", 0) for r in rs),
                           turns=st.median((r.get("turns") or 0) for r in rs),
                           tools=sum(r.get("tool_calls", 0) for r in rs),
                           previews=sum(r.get("automem_previews", 0) for r in rs),
                           ccsaved=sum(r.get("cc_saved_outputs", 0) for r in rs),
                           errors=sum(1 for r in rs if r.get("error")))
        both = [(by["plain"][i].get("resolved"), by["plugin"][i].get("resolved")) for i in common]
        cell["only_plugin"] = sum(1 for a, b in both if b and not a)
        cell["only_plain"] = sum(1 for a, b in both if a and not b)
        out[m] = cell
    return out


P = pilot()
TARGET = 20


def long_pilot():
    """Long sessions (12 issues per Claude Code session) and the fresh-session control on the same issues."""
    out = {}
    for m in ("haiku", "sonnet"):
        f, g = ROOT / "results" / f"cc_long-{m}.jsonl", ROOT / "results" / f"cc_short36-{m}.jsonl"
        if not f.exists():
            continue
        rows = [json.loads(x) for x in f.read_text().splitlines() if x.strip()]
        cell = {}
        for s in ("plain", "plugin"):
            rs = [r for r in rows if r["setting"] == s]
            cell[s] = dict(n=sum(len(r["issues"]) for r in rs), resolved=sum(r["resolved"] for r in rs),
                           cost=sum(r["cost_usd"] for r in rs), compactions=sum(r["compactions"] for r in rs),
                           previews=sum(r["previews"] for r in rs), sessions=len(rs))
        if g.exists():
            ids = {i for r in rows for i in r["issues"]}
            sh = [json.loads(x) for x in g.read_text().splitlines() if x.strip()]
            sh = [r for r in sh if r["instance_id"] in ids]
            cell["fresh"] = dict(n=len(sh), resolved=sum(bool(r["resolved"]) for r in sh),
                                 cost=sum(r["cost_usd"] for r in sh), compactions=0, previews=0, sessions=len(sh))
        out[m] = cell
    return out


L = long_pilot()


def long_table():
    if not L:
        return '<p class="note">The long-session pilot has not run yet.</p>'
    body = []
    for m, c in L.items():
        for key, label in (("fresh", "a fresh session per issue"), ("plain", "one session per 12 issues"),
                           ("plugin", "one session per 12 issues + automem")):
            v = c.get(key)
            if not v:
                continue
            body.append(f'<tr><th>{m.capitalize()} · {label}</th><td class="nm">{v["resolved"]}/{v["n"]}</td>'
                        f'<td class="nm">${v["cost"]:.2f}</td><td class="nm">${v["cost"] / max(v["n"], 1):.4f}</td>'
                        f'<td class="nm">{v["compactions"]}</td><td class="nm">{v["previews"]}</td></tr>')
    return ('<div class="tbl-wrap"><table><thead><tr><th>Setting (same 36 issues)</th><th>Resolved</th><th>Cost</th>'
            '<th>$ / issue</th><th>Compactions</th><th>Long outputs previewed</th></tr></thead><tbody>'
            + "".join(body) + "</tbody></table></div>")


def pilot_table():
    if not P:
        return '<p class="note">The pilot is running; its results will appear here when the page is regenerated.</p>'
    body = []
    for m, c in P.items():
        a, b = c["plain"], c["plugin"]
        dc = (b["cost"] / a["cost"] - 1) * 100 if a["cost"] else 0
        for s, v in (("Claude Code", a), ("Claude Code + automem", b)):
            body.append(f'<tr><th>{m.capitalize()} · {s}</th><td class="nm">{v["resolved"]}/{v["n"]}</td>'
                        f'<td class="nm">${v["cost"]:.2f}</td><td class="nm">${v["cost"] / max(v["resolved"], 1):.3f}</td>'
                        f'<td class="nm">{v["peak"] / 1000:.1f}K</td><td class="nm">{v["turns"]:.0f}</td>'
                        f'<td class="nm">{v["previews"] or v["ccsaved"]}</td></tr>')
        body.append(f'<tr class="sub"><td colspan="7">{m.capitalize()}: plugin cost {dc:+.0f}% vs plain; resolved only '
                    f'with the plugin {c["only_plugin"]}, only without it {c["only_plain"]}.</td></tr>')
    done = min(c["plain"]["n"] for c in P.values())
    status = ("complete" if done >= TARGET and len(P) == 2 else f"partial: {done} of {TARGET} issues paired so far")
    reading = ""
    if status == "complete":
        reading = ('<div class="duo"><div class="good"><span class="k">What the pilot shows</span><ul class="plain">'
                   '<li>The plugin is safe to install<span class="ev">same accuracy on both models; no errors; cost within ±10%</span></li>'
                   '<li>Claude Code sessions on single issues are short<span class="ev">median 4–6 turns; prompts of 37–41K tokens, almost all Claude Code\'s own instructions and tools</span></li>'
                   '<li>Long outputs are rare there<span class="ev">3 previews in 20 Haiku sessions, none in 20 Sonnet sessions; Claude Code\'s own output saving never triggered</span></li></ul></div>'
                   '<div class="bad"><span class="k">What it does not show</span><ul class="plain">'
                   '<li>A saving caused by the plugin<span class="ev">Sonnet was 10% cheaper with no preview fired: run-to-run variation, one run per issue</span></li>'
                   '<li>The handoff recap or recall in Claude Code<span class="ev">no session compacted; each issue was a new project</span></li>'
                   '<li>Long sessions<span class="ev">tested next (4.3): still neutral</span></li></ul></div></div>')
    return (f'<p class="note">Pilot status: {status}.</p><div class="tbl-wrap"><table><thead><tr><th>Setting</th>'
            '<th>Resolved</th><th>Cost</th><th>$ / resolved</th><th>Median peak</th><th>Median turns</th>'
            '<th>Long outputs previewed</th></tr></thead><tbody>' + "".join(body) + "</tbody></table></div>" + reading)


# ---- page pieces --------------------------------------------------------------------------------------------
CSS = """
  .layout main section + section { margin-top: 0; }
  table td.nm, table th.nm { font-family: var(--font-mono); font-variant-numeric: tabular-nums; text-align: right; white-space: nowrap; }
  table tr.sub td { font-size: 0.8rem; color: var(--muted); background: transparent !important; padding-top: 0; }
  .chart { border: 1px solid var(--rule); border-radius: 4px; background: var(--paper); padding: 8px; overflow-x: auto; }
  .chart svg { display: block; width: 100%; height: auto; min-width: 640px; }
  .todo { display: grid; gap: 8px; }
  .todo .it { display: grid; grid-template-columns: minmax(0, 1fr) auto; gap: 4px 14px; border: 1px solid var(--rule); border-radius: 4px; padding: 10px 14px; background: var(--paper); }
  .todo .it > * { min-width: 0; }
  .todo .it h4 { margin: 0; font-size: 1rem; }
  .todo .it p { margin: 0; grid-column: 1 / -1; font-size: 0.9rem; color: var(--muted); }
  .todo .it .cost { font-family: var(--font-mono); font-size: 0.8rem; color: var(--muted); white-space: nowrap; }
  .kv { display: grid; grid-template-columns: repeat(auto-fit, minmax(210px, 1fr)); gap: 10px; }
  .kv > div { border: 1px solid var(--rule); border-radius: 4px; padding: 10px 14px; background: var(--paper); min-width: 0; }
  .kv strong { display: block; font-family: var(--font-display); font-size: 1.05rem; margin-bottom: 2px; }
  .kv p { margin: 0; font-size: 0.88rem; color: var(--muted); }
  .toc { grid-template-columns: repeat(auto-fit, minmax(170px, 1fr)); }
  .banner .meta span { overflow-wrap: anywhere; min-width: 0; }
  @media (max-width: 640px) { .todo .it { grid-template-columns: minmax(0, 1fr); } }
  /* bar board */
  .board { display: flex; flex-direction: column; gap: 0; border: 1px solid var(--rule); border-radius: 4px; background: var(--paper); overflow-x: auto; }
  .board-row { display: grid; grid-template-columns: minmax(170px, 230px) minmax(240px, 1fr) minmax(240px, 1fr); align-items: center; gap: 0 14px; padding: 5px 12px; border-bottom: 1px solid var(--rule); min-width: 700px; }
  .board-row:last-child { border-bottom: 0; }
  .board-row.head { background: var(--ink); color: var(--paper); font-family: var(--font-cond); font-weight: 600; font-size: 0.78rem; letter-spacing: 0.06em; text-transform: uppercase; }
  .board-row.grp { background: var(--surface); font-family: var(--font-cond); font-weight: 600; font-size: 0.76rem; letter-spacing: 0.06em; text-transform: uppercase; color: var(--muted); padding: 3px 12px; }
  .bname { font-size: 0.88rem; font-weight: 500; line-height: 1.25; }
  .bname .sub { font-size: 0.74rem; }
  .bcell { display: grid; grid-template-columns: minmax(0, 1fr) 150px; gap: 8px; align-items: center; }
  .btrack { position: relative; height: 14px; background: var(--surface); border-radius: 2px; }
  .bfill { position: absolute; left: 0; top: 0; bottom: 0; border-radius: 2px; background: var(--muted); opacity: 0.55; }
  .bfill.g-ours { background: var(--violet); opacity: 1; }
  .bfill.g-new { background: var(--amber); opacity: 0.9; }
  .bfill.g-pub { background: var(--accent); opacity: 0.85; }
  .bfill.g-anc { background: var(--muted); opacity: 0.45; }
  .bmark { position: absolute; top: -3px; bottom: -3px; width: 2px; background: var(--ink); }
  .bval { font-family: var(--font-mono); font-size: 0.78rem; color: var(--ink); white-space: nowrap; }
  .bval .c { color: var(--muted); }
  .bval .c.cheap { color: var(--check); font-weight: 500; }
  .bval .c.dear { color: var(--warn); }
"""

NAV_ITEMS = [
    ("wd", "01", "Work done", "wrench", [("wd-time", "Timeline"), ("wd-built", "What was built"), ("wd-spend", "Runs and spend")]),
    ("fd", "02", "Findings", "bulb", [("fd-key", "Key findings"), ("fd-works", "What works, what does not")]),
    ("rs", "03", "Results", "gauge", [("rs-synth", "Four long tasks"), ("rs-swe", "SWE-bench Verified"), ("rs-valid", "Validation round"), ("rs-pick", "Which preset")]),
    ("cc", "04", "Claude Code plugin", "layers", [("cc-how", "How it works"), ("cc-pilot", "Pilot in Claude Code"), ("cc-long", "Long sessions"), ("cc-vs", "Versus other memory tools")]),
    ("todo", "05", "To-do", "flag", [("todo-blocked", "Blocked"), ("todo-next", "Next steps"), ("todo-gaps", "Known gaps")]),
]


def nav():
    parts = [f'<li class="sn-part sn-p0" data-name="Overview"><a href="#top">{ic("home", "ic sn-ic")}<span>Overview</span></a></li>']
    for i, (pid, no, name, icon, subs) in enumerate(NAV_ITEMS, 1):
        sub = "".join(f'<li><a href="#{sid}">{ic("file")}<span><i>{i}.{j}</i> {E(t)}</span></a></li>'
                      for j, (sid, t) in enumerate(subs, 1))
        parts.append(f'<li class="sn-part sn-p{min(i, 4)}" data-name="{no} {E(name)}"><a href="#{pid}">{ic(icon, "ic sn-ic")}'
                     f'<span><b>{no}</b> {E(name)}</span></a><ol>{sub}</ol></li>')
    parts.append('<li class="sn-sep" role="presentation"></li>')
    parts.append(f'<li class="sn-part sn-p5" data-name="Links"><a href="#links">{ic("book", "ic sn-ic")}<span>Links</span></a></li>')
    return (f'<nav class="sidenav" id="sidenav" aria-label="Sections"><div class="sn-top">'
            f'<button type="button" class="sn-toggle" aria-expanded="false" aria-controls="sn-list">{ic("list")}Contents</button>'
            '<a class="sn-title" href="#top">Efficient Agent Memory</a>'
            '<div class="sn-now"><span class="sn-now-k">Now reading</span><span class="sn-cur-part"></span>'
            '<span class="sn-current">Overview</span></div><div class="sn-progress" aria-hidden="true"><span></span></div>'
            f'</div><ol class="sn-list" id="sn-list">{"".join(parts)}</ol></nav>')


def toc():
    cols = []
    for i, (pid, no, name, icon, subs) in enumerate(NAV_ITEMS, 1):
        sub = "".join(f'<li><span>{i}.{j}</span><a href="#{sid}">{E(t)}</a></li>' for j, (sid, t) in enumerate(subs, 1))
        cols.append(f'<div><span class="part">{ic(icon)}Part {i}</span><a class="ttl" href="#{pid}">{E(name)}</a><ol>{sub}</ol></div>')
    return f'<nav class="toc" aria-label="Contents">{"".join(cols)}</nav>'


def banner(pid, no, tag, icon, title, meta):
    return (f'<div class="banner" id="{pid}" data-pn="{no}"><span class="tag">{ic(icon)}{E(tag)}</span>'
            f'<h2>{E(title)}</h2><div class="meta">{"".join(f"<span>{E(m)}</span>" for m in meta)}</div></div>')


def section(sid, no, icon, title, body):
    return (f'<section id="{sid}" aria-labelledby="h-{sid}"><h3 id="h-{sid}">{ic(icon, "ic hic")}<span class="no">{no}</span>'
            f'{E(title)}</h3>{body}</section>')


def pilot_headline():
    if not P:
        return "The pilot of the plugin inside Claude Code is running."
    bits = []
    for m, c in P.items():
        a, b = c["plain"], c["plugin"]
        bits.append(f'{m.capitalize()}: {b["resolved"]}/{b["n"]} resolved with the plugin vs {a["resolved"]}/{a["n"]} without, '
                    f'at {(b["cost"] / a["cost"] - 1) * 100:+.0f}% cost' if a["cost"] else m)
    return ("Pilots inside Claude Code: on single issues (" + "; ".join(bits)
            + ") and in 12-issue sessions with compaction (cost −4% Haiku, +1% Sonnet, ±1 issue), the plugin is neutral."
            " Claude Code already caches, compacts and filters long output itself.")


TIMELINE_ROWS = [
    ("22 Oct", "Phase 1: single methods", "ReSum, masking, AgentDiet, Context-Folding, turn control, workspace on two tasks", "No single method solves multi-session work"),
    ("23–26 Oct", "Long tasks, AutoMemory v1", "Four long tasks, model-normalised protocol; MemoryOS, LightMem, Nemori", "Workspace + compaction is model-robust; memory systems 0.2–0.5 lower"),
    ("4 Nov", "Eight new methods; v2 and v3", "Strands, CADOC, ReFold, SJC, AKV, raw RAG, CORAL, SelfCompact; previews, folding", "AutoMemory v2 becomes the default"),
    ("5 Nov", "Sonnet seeds; SWE-bench (40 issues)", "Decision rule fixed in advance; first real-repository workdays", "automem_v2_strong; lean wins on real code"),
    ("6 Nov", "NVIDIA handoff; 100 issues", "EoCC prompts; SWE-bench-faithful grading; 32K and 16K windows; 480 runs", "automem_v2_lean_handoff for accuracy-first coding"),
    ("6–7 Nov", "Front page and housekeeping", "README with charts and flowcharts; CONTRIBUTING, CITATION; papers folder ignored", "PRs #1–#3 merged"),
    ("8 Nov", "Claude Code plugin and pilots", "Hooks: previews from Claude Code's saved output, handoff at compaction, recall, autosave; short and 12-issue sessions", "Neutral inside Claude Code"),
    ("8 Nov", "Brief handoff recap; adaptive workspace", "Two follow-up checks on the 100 Django issues and the synthetic tasks", "Kept as options; their first cost readings did not survive the validation round"),
    ("8–12 Nov", "Validation round", "Every decision cell re-run on one day; two cells repeated; an independent audit of the measurement code; SymPy and related-issue Django workdays; 596 runs", "Headline results hold; four cost and ranking claims withdrawn; a harness artifact found and fixed"),
    ("12–13 Nov", "Follow-up: three runs per cell", "Ceiling, lean and lean + handoff run twice more on the 100 Django issues; EoCC alone next to its ceiling on both models; 280 runs with the 8K cap", "Lean costs 80% of the ceiling on Sonnet; handoff and ReSum level; EoCC alone resolves 5 fewer in 100. PR #8 merged"),
]


def timeline_table():
    rows = "".join(f'<tr><th>{E(d)}</th><td><strong>{E(w)}</strong><br><span class="desc">{E(s)}</span></td><td>{E(r)}</td></tr>'
                   for d, w, s, r in TIMELINE_ROWS)
    return f'<div class="tbl-wrap"><table><thead><tr><th>When</th><th>Work</th><th>Outcome</th></tr></thead><tbody>{rows}</tbody></table></div>'


SPEND = [("Phases 1–3 and the eight new methods", "≈ 1,900", 820), ("AutoMemory v2, v3 ablation, Sonnet seeds", "≈ 250", 102),
         ("SWE-bench, 40 issues", "164", 56), ("Earlier pilots and calibration", "—", 162),
         ("NVIDIA handoff: synthetic tasks", "80", 68.59), ("SWE-bench, 100 issues at 32K and the own window", "260", 98.19),
         ("SWE-bench, 100 issues at 16K", "140", 54.31),
         ("Brief handoff recap and adaptive workspace checks", "—", 57),
         ("Validation round: same-day controls, repeats, related issues, SymPy", "596", 293.28),
         ("Follow-up: three runs per coding cell; EoCC alone next to its ceiling", "280", 81.09)]


def spend_table():
    pil = sum(c[s]["cost"] for c in P.values() for s in ("plain", "plugin")) if P else 0
    lp = sum(c[k]["cost"] for c in L.values() for k in ("plain", "plugin", "fresh") if k in c) if L else 0
    rows = SPEND + ([("Claude Code long sessions and fresh-session control", str(sum(c[k]["n"] for c in L.values() for k in c)), lp)] if L else []) + ([("Claude Code pilot (so far)" if min(c["plain"]["n"] for c in P.values()) < TARGET else "Claude Code pilot",
                      str(sum(c[s]["n"] for c in P.values() for s in ("plain", "plugin"))), pil)] if P else [])
    body = "".join(f'<tr><th>{E(a)}</th><td class="nm">{E(b)}</td><td class="nm">${c:,.0f}</td></tr>' for a, b, c in rows)
    tot = sum(c for _, _, c in rows)
    return (f'<div class="tbl-wrap"><table><thead><tr><th>Run set</th><th class="nm">Runs</th><th class="nm">Cost</th></tr></thead>'
            f'<tbody>{body}<tr><th>Total</th><td class="nm">≈ 3,900</td><td class="nm"><strong>${tot:,.0f}</strong></td></tr></tbody></table></div>'
            '<p class="note">Claude Code CLI route at list prices. The first four rows are rounded from the phase reports.</p>')


def todo(items):
    return '<div class="todo">' + "".join(
        f'<div class="it"><h4>{E(t)}</h4><span>{lvl(s, k)} <span class="cost">{E(c)}</span></span><p>{d}</p></div>'
        for t, s, k, c, d in items) + "</div>"


BLOCKED = [
    ("Bedrock validation", "Blocked: credentials", "high", "—",
     "Every result uses the Claude Code CLI's list prices. Bedrock bills cache writes at 1.25× (not 2×) and uses explicit cache points, which could change the cost ranking. Needs AWS credentials or a Bedrock API key; runbook in scripts/run_bedrock_validation.sh."),
    ("GPT and other non-Claude models", "Blocked: credentials", "high", "—",
     "No non-Claude model has been measured. GPT-5.6 is reachable through Bedrock's OpenAI-compatible endpoints with the same key; prices go in config/models.json."),
]
NEXT = [
    ("Native tool-calling route", "Blocked: credentials", "high", "—",
     "The runaway replies come from emulating tools as text through the Claude Code CLI. A route with native tool calls (Bedrock Converse) removes them at the source and is the same work as the Bedrock validation above."),
    ("Three runs of the SymPy and related-issue sets", "Next", "low", "≈ $45",
     "Lean's cost against the ceiling is established on the 100 Django issues only. On SymPy and the related-issue workdays each cell ran once and the intervals are wide (Sonnet: 70% [54–109] and 95% [66–126])."),
    ("Three runs per cell on Django", "Done: lean is cheaper on Sonnet", "med", "$81 with the next two",
     "Ceiling, lean and lean + handoff, three runs each. Sonnet: lean costs 80% of the ceiling [72–90] (82%, 77%, 81% run by run) and resolves 87 of 100 against 87. Haiku: 96% [83–110], 81 against 78. With the 8K cap, two runs of one cell differ by 1–15% in cost."),
    ("EoCC alone, corrected grading, next to its ceiling", "Done: cheaper, fewer issues", "low", "",
     "Haiku 75 of 100 against 80 for the ceiling at 85% of its cost; Sonnet 85 against 90 at 74%. Pooled over both models it gained 2 issues and lost 12 (p = 0.013). 22 and 19 of 100 sessions filled the 16K window and were stopped; 8 of the 12 lost issues were in those sessions."),
    ("Handoff recap or ReSum summary", "Done: level", "low", "",
     "Over three runs the two resolve the same number of issues (Haiku 80 and 81, Sonnet 88 and 87) at the same cost (handoff at 104% [93–118] and 102% [94–111] of ReSum). The earlier pooled 22 against 11 (p = 0.08) did not repeat: 10 against 12 in the two new runs."),
    ("Decide the plugin's role", "Next", "med", "no API cost",
     "Both pilots (short and long sessions) found the plugin neutral in Claude Code, which already caches, compacts and filters output. Keep it as an optional, harmless add-on; aim further work at agents without these built-ins (custom loops on Bedrock, other CLIs)."),
    ("Brief handoff recap", "Done: no advantage", "low", "$25",
     "Six fields as terse bullets, at most 150 words. Its first reading (79% of the ceiling's cost on Haiku, the cheapest per resolved issue) did not repeat on the same day: 90% and the fewest issues resolved (75). Kept as the option handoff_variant=brief, without a claim."),
    ("Adaptive workspace", "Done: an option, not the default", "low", "$32",
     "A short question to the summariser at each session start chooses notes on or off. On Sonnet it stayed close to the right fixed preset on both kinds of work (1.00 at 61% of the ceiling's cost on the synthetic tasks; 86 of 100 Django issues at 105%). On Haiku it cost more than the right preset on both (155% and 131%). Kept as automem_v2_adaptive."),
    ("Report cost on two price bases", "Next", "low", "no API cost",
     "List prices with caching (Bedrock and the CLI today) and context-length pricing (the NVIDIA paper's model) for self-hosted or long-context-tier users."),
]
GAPS = [
    ("Two repositories, one language", "Gap", "low", "", "The SWE-bench sets are Django and SymPy, both Python. Sonnet's out-of-sample sets are smaller (50 related issues, 40 SymPy issues)."),
    ("One run for most cells", "Gap", "med", "", "Only the ceiling, lean and lean + handoff cells on Django were run three times. For the other cells, intervals are a bootstrap over the workdays of one run and are wide; there is no correction for the number of comparisons."),
    ("Rows before 12 November", "Gap", "low", "", "They ran with a 32K output cap and thinking settings inherited from the launching session, and do not record the CLI version. New rows record all three."),
    ("Emulated windows", "Gap", "low", "", "The synthetic tasks emulate small windows (16K–48K) to create memory pressure."),
    ("Local-only reports", "Gap", "low", "", "Detailed reports in docs/results/ and the rows behind docs/overview.html are git-ignored, so a fresh clone cannot rebuild those pages; the README charts can be rebuilt."),
]


# ---- the validation round (2026-11-08 to 11-12): numbers from scripts/analyze_validation.py ---------------------
SAMEDAY = [  # (issue set, setting, Haiku, Sonnet)
    ("Django, 100 issues, three runs", "Ceiling: full history, own window", "78 · 100%", "87 · 100%"),
    ("", "automem_v2_lean", "81 · 96% [83–110]", "87 · 80% [72–90]"),
    ("", "automem_v2_lean_handoff", "80 · 100% [91–109]", "88 · 81% [74–89]"),
    ("Django, the same issues, one run", "Ceiling", "77 · 100%", "83 · 100%"),
    ("", "… brief recap", "75 · 90% [73–110]", "84 · 86% [72–105]"),
    ("", "automem_v2_adaptive", "78 · 131% [96–174]", "86 · 105% [85–130]"),
    ("Django, the same issues, one run", "Ceiling", "80 · 100%", "90 · 100%"),
    ("", "EoCC alone: handoff recap, no previews", "75 · 85% [70–100]", "85 · 74% [67–82]"),
    ("Django, related issues (80 Haiku, 50 Sonnet)", "Ceiling", "64 · 100%", "44 · 100%"),
    ("", "automem_v2_lean", "70 · 117% [89–152]", "44 · 95% [66–126]"),
    ("", "automem_v2 (with notes)", "64 · 208% [169–247]", "44 · 87% [69–113]"),
    ("", "automem_v2_adaptive", "67 · 106% [83–135]", "45 · 80% [60–104]"),
    ("SymPy (75 Haiku, 40 Sonnet)", "Ceiling", "50 · 100%", "35 · 100%"),
    ("", "automem_v2_lean", "50 · 116% [81–158]", "35 · 70% [54–109]"),
    ("", "automem_v2_lean_handoff", "52 · 92% [71–123]", "34 · 74% [56–108]"),
]


def sameday_table():
    rows = "".join(f'<tr><th>{E(a)}</th><td><code>{E(b)}</code></td><td class="nm">{E(h)}</td><td class="nm">{E(so)}</td></tr>'
                   if b.startswith(("automem", "…")) else
                   f'<tr><th>{E(a)}</th><td>{E(b)}</td><td class="nm">{E(h)}</td><td class="nm">{E(so)}</td></tr>'
                   for a, b, h, so in SAMEDAY)
    return ('<div class="tbl-wrap"><table><thead><tr><th>Issue set</th><th>Setting</th><th class="nm">Haiku</th>'
            f'<th class="nm">Sonnet</th></tr></thead><tbody>{rows}</tbody></table></div>'
            '<p class="note">Issues resolved · cost relative to the ceiling [95% interval over workdays]. 16K window, '
            'one fresh session per issue. Every cell is compared with a ceiling run on the same day. The first three rows are '
            'three runs each: mean issues resolved, costs pooled.</p>')


CHECKS = [
    ("Same-day controls", "Every decision cell re-run on one day",
     "The two headline results hold. Baselines drift between days: the ceiling resolved 82 and 88 Django issues on 6 November and 77 and 83 here."),
    ("Noise", "One cell per workload run twice",
     "Coding: the same setting resolved 80 and 81 (Haiku) and 85 and 87 (Sonnet), 6–7 issues flipped, cost differed by 7% and 38%. Synthetic: Haiku scored 0.75 and 0.86, Sonnet 0.99 and 1.00, cost within 10%."),
    ("Code audit", "An independent review of the measurement, grading and aggregation code",
     "15 findings, 13 fixed. Two changed a published result: sessions that ended early were scored without grading their final state, and a recap larger than the window was not counted as an overflow."),
    ("Out-of-sample tasks", "SymPy; Django workdays that stay in one subsystem",
     "Lean matches the ceiling on a second repository. Notes do not pay on coding issues even when consecutive issues are related."),
]
FOLLOWUP = [  # 2026-11-12 to 11-13: numbers from scripts/analyze_validation.py, followup()
    ("Is lean cheaper than the ceiling?", "On Sonnet yes, on Haiku no",
     "Sonnet: 80% of the ceiling's cost [72–90] over three runs (82%, 77%, 81%). Haiku: 96% [83–110] (92%, 110%, 89%). Issues resolved: 87 against 87, and 81 against 78."),
    ("Does the handoff recap resolve more issues than a ReSum summary?", "Not confirmed",
     "Three runs: 80 and 81 of 100 on Haiku, 88 and 87 on Sonnet; handoff at 104% [93–118] and 102% [94–111] of ReSum's cost."),
    ("Does EoCC alone resolve fewer issues?", "Yes, 5 in 100 on both models",
     "75 against 80 (Haiku) and 85 against 90 (Sonnet) for the ceiling of the same day; pooled 2 gained, 12 lost, p = 0.013. One session in five filled the window and was stopped. Cost: 85% and 74% of the ceiling's."),
    ("Did the 8K cap reduce the cost noise?", "Yes",
     "Two runs of one cell differ by 1–15% in cost, against 7% and 38% with the 32K cap."),
]
VERDICTS = [
    ("ok", "Stands", "AutoMemory v2 reaches the ceiling's accuracy below its cost on multi-session work",
     "Sonnet 0.99 and 1.00 at 56% in two runs; Haiku 0.75 and 0.86 at 87% and 74% (ceiling 0.80)"),
    ("ok", "Stands", "Without notes, multi-session work fails", "0.64 at 249% (Haiku), 0.87 at 152% (Sonnet)"),
    ("ok", "Stands", "Lean resolves as many coding issues as the ceiling, inside a 16K window",
     "Django, related Django and SymPy on both models; no paired difference is significant"),
    ("ok", "Stands", "Lean is cheaper than the ceiling on Sonnet", "Follow-up: 80% [72–90] over three Django runs. One run each: 95% and 70% on the other two sets"),
    ("ok", "Stands", "Notes do not pay on coding issues",
     "Related issues, Haiku: 64 resolved at 208% with notes, 70 at 117% without"),
    ("med", "Changes", "Lean is cheaper than the ceiling on Haiku (83%)", "Not distinguishable. Follow-up: 96% [83–110] over three Django runs; 117% and 116% on the other sets"),
    ("med", "Changes", "Handoff recap resolves more than a ReSum summary", "Not confirmed. In the round: 22 against 11 in the pooled pairs, p = 0.08. Follow-up: 10 against 12 in two new runs; level in accuracy and cost over three"),
    ("med", "Changes", "Adaptive workspace: not adopted", "A usable single setting on Sonnet; costs more than the right preset on Haiku"),
    ("high", "Falls", "Handoff costs 6–16 points more than ReSum", "Same day: 89% vs 92% (Haiku), 85% vs 82% (Sonnet)"),
    ("high", "Falls", "The brief recap is the cheapest per resolved issue on Haiku", "Same day: 90% and the fewest resolved (75)"),
    ("med", "Changes", "EoCC alone resolves the fewest issues", "The first figure was a grading bug (72 of 100 on Haiku, re-graded 77). Follow-up, next to a same-day ceiling: 75 against 80 (Haiku) and 85 against 90 (Sonnet), pooled p = 0.013"),
    ("high", "Falls", "Dollar-per-issue rankings between the lean settings", "Inside the run-to-run spread"),
]


def validation_section():
    checks = "".join(f'<tr><th>{E(a)}</th><td>{E(b)}</td><td>{E(c)}</td></tr>' for a, b, c in CHECKS)
    kind = {"ok": "low", "med": "med", "high": "high"}
    verdicts = "".join(f'<tr><th>{lvl(v, kind[k])}</th><td>{E(c)}</td><td>{E(e)}</td></tr>' for k, v, c, e in VERDICTS)
    return ('<p class="lead-in">After the first results, four checks were run together to find out whether the conclusions came '
            'from the methods or from the experiment design and the infrastructure.</p>'
            '<div class="tbl-wrap"><table><thead><tr><th>Check</th><th>What was done</th><th>What it found</th></tr></thead>'
            f'<tbody>{checks}</tbody></table></div>'
            '<div class="tbl-wrap"><table><thead><tr><th>Verdict</th><th>Earlier conclusion</th><th>Evidence in this round and the follow-up</th></tr></thead>'
            f'<tbody>{verdicts}</tbody></table></div>'
            '<div class="duo"><div class="bad"><span class="k">Harness artifact found</span><ul class="plain">'
            '<li>Runaway replies at the output cap<span class="ev">tools are emulated as text through the Claude Code CLI; in about 1% '
            'of calls the model loops until the 32K cap, and the loop is billed and discarded</span></li>'
            '<li>Share of all measured cost in the round<span class="ev">22% (Sonnet) and 26% (Haiku); most of the cost noise</span></li></ul></div>'
            '<div class="good"><span class="k">Fixed for new runs</span><ul class="plain">'
            '<li>Output cap 8K instead of 32K<span class="ev">a runaway reply costs about a quarter as much; the agent still recovers (measured)</span></li>'
            '<li>Every row counts cap hits<span class="ev">and records the CLI version, the cap and the thinking settings</span></li>'
            '<li>Thinking settings can be pinned<span class="ev">until now they were inherited from the launching session</span></li></ul></div></div>'
            '<h4>Follow-up (12–13 November): three runs per cell</h4>'
            '<p>The ceiling, lean and lean + handoff cells were run twice more on the 100 Django issues, and EoCC alone was run next to '
            'its ceiling on both models: 280 runs, all with the 8K cap.</p>'
            '<div class="tbl-wrap"><table><thead><tr><th>Question</th><th>Answer</th><th>Evidence</th></tr></thead><tbody>'
            + "".join(f'<tr><th>{E(q)}</th><td>{E(a)}</td><td>{E(e)}</td></tr>' for q, a, e in FOLLOWUP) + '</tbody></table></div>')


def build():
    syn = RC.synth_chart(RC.THEMES["light"])
    swe = RC.swe_chart(RC.THEMES["light"])
    page = f"""<title>Efficient Agent Memory Report</title>
<meta name="claude:viewport-fit-sides" content="cover">
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link rel="stylesheet" href="https://fonts.googleapis.com/css2?family=IBM+Plex+Mono:wght@400;500&family=IBM+Plex+Sans+Condensed:wght@500;600&family=IBM+Plex+Sans:ital,wght@0,400;0,500;0,600;1,400&family=Newsreader:ital,opsz,wght@0,6..72,500;0,6..72,600;1,6..72,400;1,6..72,500&display=swap">
<style>{(ASSETS / "ref.css").read_text()}{X.CSS}{CSS}</style>
{(ASSETS / "sprite.svg").read_text()}
<div class="readbar" aria-hidden="true"><span></span></div>
<div class="layout">
{nav()}
<main>
  <header id="top">
    <div class="hero">
      <p class="eyebrow">Work report · 12 November 2026</p>
      <h1>Efficient Agent Memory</h1>
      <p class="dek">What was built, what the measurements show after a validation round, how the memory layer ships as a Claude Code plugin, and what is left to do.</p>
      <p class="hero-meta"><span>≈ 3,900 benchmark runs</span><span>27 methods and variants</span><span>Claude Haiku and Sonnet</span><span>SWE-bench Verified: Django and SymPy</span><span>PRs #1–#8 merged</span></p>
    </div>
    <div class="brief">
      <span class="k">{ic("brief")}Key points</span>
      <ul class="plain">
        <li><strong>Fewer tokens is not fewer dollars.</strong> Re-sent history is cheap while it stays in the prompt cache; methods that rewrite it every step cost more than they save (AKV: 93% of the ceiling's cost dropping every turn, 22% in blocks of 8).</li>
        <li><strong>Let the harness remember.</strong> Previews at ingestion, automatic recall and compaction at a fixed trigger worked on Haiku and Sonnet; methods that need the model to manage its memory failed on Haiku.</li>
        <li><strong>AutoMemory v2</strong> matches the unoptimised ceiling on four long multi-session tasks at 85% (Haiku) and 58% (Sonnet) of its cost; a same-day re-run and a repeat gave 74–87% and 56%. No newer published method beats it across the board.</li>
        <li><strong>On real coding issues</strong> (Django and SymPy, SWE-bench Verified), <code>automem_v2_lean</code> inside a 16K window resolves as many issues as the unoptimised agent with its full window. On Sonnet it costs 80% of that agent over three runs (95% interval 72–90%); on Haiku its cost cannot be told apart from the ceiling's.</li>
        <li><strong>A validation round</strong> (same-day controls, repeats, a code audit, a second repository) confirmed both results and withdrew four smaller claims, among them "handoff costs more than ReSum". About a quarter of all measured cost was a harness artifact, now capped and counted.</li>
        <li><strong>A follow-up with three runs per cell</strong> settled three open questions: lean is cheaper than the ceiling on Sonnet and not on Haiku; the handoff recap and a ReSum summary are level; EoCC alone, without previews, resolves 5 fewer issues in 100.</li>
        <li><strong>{E(pilot_headline())}</strong></li>
      </ul>
      <p class="rec"><strong>Recommendation:</strong> use the plugin's harness steps (previews, handoff at compaction, recall) rather than instructions in CLAUDE.md; pick <code>automem_v2</code> for multi-session work and <code>automem_v2_lean</code> for coding issues. Expect the saving on the dearer model: with Sonnet, 44% on multi-session work and about 20% on coding issues (5–30% across the three issue sets).</p>
    </div>
    {toc()}
  </header>

  {banner("wd", "01", "Part 1 · What", "wrench", "Work done", ["github.com/GaryTang32/Efficient-Agent-Memory", "main @ PR #8, follow-up runs on the working branch"])}
  {section("wd-time", "1.1", "trend", "Timeline", timeline_table())}
  {section("wd-built", "1.2", "box", "What was built", '''
    <div class="kv">
      <div><strong>Benchmark harness</strong><p>ReAct loop with technique hooks, emulated windows, a cache-aware cost meter; Claude Code CLI, Bedrock, LiteLLM and mock backends.</p></div>
      <div><strong>27 methods and variants</strong><p>Faithful ports of published methods, each with its source and deviations documented, from ReSum to NVIDIA's EoCC.</p></div>
      <div><strong>Tasks</strong><p>Four long synthetic tasks and SWE-bench Verified workdays on Django (100 issues, plus workdays of related issues) and SymPy (75), graded as SWE-bench grades them.</p></div>
      <div><strong>AutoMemory</strong><p>The combined memory layer as a bench technique, a Python library and an MCP server, with six presets.</p></div>
      <div><strong>Claude Code plugin</strong><p><code>plugins/automem</code>: four hooks, a skill and a handoff command; standard library only.</p></div>
      <div><strong>Docs</strong><p>README with charts and flowcharts, the interactive overview, paper notes, methodology, CONTRIBUTING and CITATION.</p></div>
    </div>''')}
  {section("wd-spend", "1.3", "chart", "Runs and spend", spend_table())}

  {banner("fd", "02", "Part 2 · Why it matters", "bulb", "Findings", ["Evidence from the result reports", "Claude Code CLI route, list prices"])}
  {section("fd-key", "2.1", "bulb", "Key findings", '''
    <div class="tbl-wrap"><table><thead><tr><th>Finding</th><th>Evidence</th></tr></thead><tbody>
      <tr><th>Fewer tokens is not fewer dollars</th><td>Rewritten history is billed as cache writes (2× on the CLI, 1.25× on Bedrock). Masking cost up to 608% and AgentDiet 410% of full context on Haiku.</td></tr>
      <tr><th>Automatic beats model-managed</th><td>CORAL's memory tools were barely used (Haiku 7 of 56 sessions); ReFold's Haiku recovery was 0.25. Harness-applied previews, recall and compaction held on both models.</td></tr>
      <tr><th>Plain notes beat memory systems</th><td>MemoryOS, LightMem and Nemori scored 0.2–0.5 lower than a note workspace with the same compaction.</td></tr>
      <tr><th>Match the layer to the work</th><td>Notes are essential for multi-session tasks (without them 0.64 and 0.87 in score at 1.5–2.5 times the ceiling's cost) and overhead on coding issues, even related ones (Haiku: twice the ceiling's cost, fewer issues resolved).</td></tr>
      <tr><th>Real coding sessions fit in short contexts</th><td>Inside a 16K window with compaction, the agent resolves as many issues as with its full window, on Django and on SymPy. Sessions peak at 16–21K tokens without a limit.</td></tr>
      <tr><th>The kind of summary matters little on coding work</th><td>Over three runs on Django, NVIDIA's handoff recap and a ReSum summary resolved the same number of issues (80 and 81 of 100 on Haiku, 88 and 87 on Sonnet) at the same cost. Trimming at ingestion matters more: the recap alone, without previews, lost 5 issues in 100.</td></tr>
      <tr><th>Measure the noise before ranking</th><td>The same setting run twice differed by up to 38% in cost; about a quarter of all measured cost was runaway replies at the output cap. Four early rankings did not survive a same-day re-run; three runs per cell were needed to establish the lean saving on Sonnet.</td></tr>
      <tr><th>Grading must follow SWE-bench exactly</th><td>The first 40-issue run checked 63% of the official tests (docstring-named tests were dropped); fixed and superseded.</td></tr>
    </tbody></table></div>''')}
  {section("fd-works", "2.2", "check", "What works, what does not", '''
    <div class="duo">
      <div class="good"><span class="k">Works on both models</span><ul class="plain">
        <li>Shrinking outputs when they arrive, with retrieval<span class="ev">Haiku 11/16 runs solved vs 7/16</span></li>
        <li>Automatic recall and autosave of notes<span class="ev">beats engineered memory systems by 0.2–0.5</span></li>
        <li>Compaction at a fixed trigger, keeping recent steps<span class="ev">without it: 0.04–0.62</span></li>
        <li>A cheaper model writing summaries<span class="ev">Sonnet: same accuracy, 20–40% cheaper</span></li></ul></div>
      <div class="bad"><span class="k">Fails or depends on the model</span><ul class="plain">
        <li>Editing history every step<span class="ev">masking 608%, AgentDiet 410%</span></li>
        <li>Asking the model to manage its memory<span class="ev">CORAL tools barely used</span></li>
        <li>A compaction method alone, without a guard<span class="ev">EoCC alone: one session in five ran out of the 16K window; 5 fewer issues resolved than its same-day ceiling on both models (2 gained, 12 lost, p = 0.013)</span></li>
        <li>Notes on coding issues<span class="ev">Haiku: 208% of the ceiling's cost on related issues, 6 fewer resolved</span></li>
        <li>Ranking settings from one run<span class="ev">cost differed by 7–38% between two runs of the same setting (1–15% since the 8K cap)</span></li></ul></div>
    </div>''')}

  {banner("rs", "03", "Part 3 · How much", "gauge", "Results", ["Floor and ceiling on the same instances", "Cost relative to the ceiling"])}
  {section("rs-synth", "3.1", "chart", "Four long synthetic tasks", f'<p class="lead-in">Mean score against cost relative to the unoptimised ceiling. Top left is best.</p><div class="chart">{syn}</div>')}
  {section("rs-swe", "3.2", "cpu", "SWE-bench Verified: Django and SymPy", f'''<p class="lead-in">One fresh session per issue, graded with the official FAIL_TO_PASS and PASS_TO_PASS tests. The memory settings work inside a 16K window; the ceiling keeps the full history in the model's own window.</p>
    <div class="chart">{swe}</div>{sameday_table()}
    <h4>Earlier grid (6 November): 32K and 16K windows, one run per cell</h4>
    <p class="note">Read with the validation round in mind: sessions that ended early were scored unresolved without grading (this lowered the EoCC rows most), cells ran on different days, and cost differences under about 25 points are inside the run-to-run spread.</p>
    {X.swe_board(SWE)}''')}
  {section("rs-valid", "3.3", "check", "Validation round", validation_section())}
  {section("rs-pick", "3.4", "route", "Which preset", '''
    <div class="tbl-wrap"><table><thead><tr><th>Work</th><th>Preset</th><th>Why</th></tr></thead><tbody>
      <tr><th>Multi-session work that builds on earlier results</th><td><code>automem_v2</code></td><td>Ceiling accuracy at 74–87% (Haiku) and 56–58% (Sonnet) of its cost, in three runs</td></tr>
      <tr><th>Same, strong agent model</th><td><code>automem_v2_strong</code></td><td>Sonnet solved 16/16 runs at 61%</td></tr>
      <tr><th>Coding issues and tickets, one per session</th><td><code>automem_v2_lean</code></td><td>The ceiling's accuracy inside a 16K window on Django and SymPy; 80% of its cost on Sonnet over three runs</td></tr>
      <tr><th>Same, with NVIDIA's recap at resets</th><td><code>automem_v2_lean_handoff</code></td><td>The same accuracy and cost as lean over three runs; the recap lists applied changes, dead ends and the next command</td></tr>
      <tr><th>Unknown workload on a strong model</th><td><code>automem_v2_adaptive</code></td><td>Sonnet: 1.00 at 61% on multi-session tasks, 86/100 Django issues at 105%</td></tr>
      <tr><th>Short sessions on a large window</th><td>cached full history</td><td>Haiku 77/100 at 62% at 32K (one run, 6 November)</td></tr>
    </tbody></table></div>''')}

  {banner("cc", "04", "Part 4 · For everyday users", "layers", "Claude Code plugin", ["plugins/automem", "claude --plugin-dir plugins/automem"])}
  {section("cc-how", "4.1", "steps", "How it works", '''
    <p>The plugin runs the measured harness steps as Claude Code hooks: no extra model calls, nothing rewritten in the cached history. Claude Code already caches prompts and cuts long Bash output to a 2 KB head-only preview with the full text saved to a file; the plugin builds on that.</p>
    <div class="tbl-wrap"><table><thead><tr><th>Hook</th><th>What it does</th><th>Measured rule behind it</th></tr></thead><tbody>
      <tr><th>PostToolUse (Bash)</th><td>Long output reaches the model as head + tail (1,500 characters each). For output Claude Code truncated, the tail is read from Claude Code's own saved copy, so test summaries and failures at the end stay visible.</td><td>Previews at ingestion (Haiku 11/16 vs 7/16)</td></tr>
      <tr><th>PreCompact</th><td>Compaction keeps NVIDIA's six-field handoff recap.</td><td>Level with a ReSum summary in accuracy and cost over three runs</td></tr>
      <tr><th>SessionStart</th><td>Recalls this project's notes at startup, resume, clear and after compaction.</td><td>Recall: Haiku 0.34 without, 0.99 with notes on Sonnet</td></tr>
      <tr><th>Stop</th><td>Saves each turn's final message as a project note.</td><td>Autosave</td></tr>
    </tbody></table></div>
    <p class="note">Checked live: with a 108 KB output, plain Claude Code showed the model lines 1–234; with the plugin the model saw the head and the real last line, and found a middle line in the saved file without re-running the command.</p>''')}
  {section("cc-pilot", "4.2", "gauge", "Pilot inside Claude Code: single issues", f'''<p class="lead-in">Headless Claude Code with its own tools and agent loop, one fresh session per SWE-bench Verified issue, the same prompt and the same spending cap, with and without the plugin.</p>{pilot_table()}''')}
  {section("cc-long", "4.3", "trend", "Long sessions", f'''<p class="lead-in">One Claude Code session works through 12 issues, one turn per issue, with compaction at 100K tokens; three such sessions per model and setting. A fresh session per issue on the same 36 issues is the control.</p>{long_table()}
    <div class="duo"><div class="good"><span class="k">What it shows</span><ul class="plain">
      <li>The plugin acted<span class="ev">compaction fired 4–11 times per model with the handoff recap; 8 long outputs previewed</span></li>
      <li>It still made no difference<span class="ev">cost −4% (Haiku) and +1% (Sonnet), within one issue</span></li>
      <li>A fresh session per issue is a little cheaper<span class="ev">7% (Sonnet) and 27% (Haiku) less per issue than one long session, at similar accuracy</span></li></ul></div>
    <div class="bad"><span class="k">Measurement note</span><ul class="plain">
      <li>With <code>--resume</code>, Claude Code reports the session's running cost<span class="ev">a first summary added the running totals and overstated long sessions about 6×; corrected here</span></li></ul></div></div>''')}
  {section("cc-vs", "4.4", "grid", "Versus other memory tools", '''
    <div class="tbl-wrap"><table><thead><tr><th></th><th>Claude Code's own memory</th><th>Memory services (fact extraction + retrieval)</th><th>Model-managed memory (memory tools)</th><th>This plugin</th></tr></thead><tbody>
      <tr><th>Who acts</th><td>Harness: CLAUDE.md and auto memory loaded each session; compaction near the context limit</td><td>An extra LLM extracts facts; embeddings retrieve them</td><td>The agent decides when to read and write memory</td><td>Harness hooks, no extra LLM calls</td></tr>
      <tr><th>Targets</th><td>Persistent instructions and facts</td><td>Long-term recall across chats</td><td>Long-term recall</td><td>Context size and cost per task, plus recall</td></tr>
      <tr><th>Cost side effects</th><td>None added</td><td>Extraction calls per turn; retrieved text changes the prompt</td><td>Tool calls the model may skip</td><td>None added; edits only at ingestion and compaction</td></tr>
      <tr><th>Measured here</th><td>Prompt caching and output persistence observed</td><td>MemoryOS, LightMem, Nemori: 0.2–0.5 lower than plain notes</td><td>CORAL: tools barely used on Haiku</td><td>Bench evidence above; Claude Code pilot in 4.2</td></tr>
    </tbody></table></div>
    <p class="note">Other memory services (for example mem0, Zep or Letta) have not been measured in this repository.</p>''')}

  {banner("todo", "05", "Part 5 · Next", "flag", "To-do", ["Status as of 12 November 2026"])}
  {section("todo-blocked", "5.1", "alert", "Blocked", todo(BLOCKED))}
  {section("todo-next", "5.2", "route", "Next steps", todo(NEXT))}
  {section("todo-gaps", "5.3", "info", "Known gaps", todo(GAPS))}

  <section class="endnote" id="links" aria-labelledby="h-links">
    <h2 id="h-links">{ic("book", "ic hic")}Links</h2>
    <div class="refs-group"><ol class="refs">
      <li><a href="https://github.com/GaryTang32/Efficient-Agent-Memory">Repository</a> <span class="desc">README with charts, flowcharts and quick start</span></li>
      <li><a href="https://github.com/GaryTang32/Efficient-Agent-Memory/pull/1">PR #1</a>, <a href="https://github.com/GaryTang32/Efficient-Agent-Memory/pull/2">PR #2</a>, <a href="https://github.com/GaryTang32/Efficient-Agent-Memory/pull/3">PR #3</a>, <a href="https://github.com/GaryTang32/Efficient-Agent-Memory/pull/4">PR #4</a>, <a href="https://github.com/GaryTang32/Efficient-Agent-Memory/pull/5">PR #5</a>, <a href="https://github.com/GaryTang32/Efficient-Agent-Memory/pull/6">PR #6</a>, <a href="https://github.com/GaryTang32/Efficient-Agent-Memory/pull/7">PR #7</a> <span class="desc">merged</span></li>
      <li><a href="https://claude.ai/artifact/JVkigqm5XYpmwbN2F11xdF">Interactive overview</a> <span class="desc">every method's mechanism, diagrams and charts</span></li>
      <li><a href="https://arxiv.org/abs/2611.05306">You don't need long context</a> <span class="src">NVIDIA, arXiv 2611.05306</span></li>
      <li><a href="https://www.swebench.com/">SWE-bench Verified</a> <span class="src">Jimenez et al., ICLR 2024; OpenAI</span></li>
    </ol></div>
  </section>
</main>
</div>
<script>{(ASSETS / "script_tabs_nav.js").read_text()}</script>
<script>{(ASSETS / "script0.js").read_text()}</script>
<script>{X.TOOLTIP_JS}</script>
"""
    OUT.write_text(page)
    print(OUT, len(page), "pilot:", {m: {s: (c[s]["resolved"], c[s]["n"]) for s in ("plain", "plugin")} for m, c in P.items()})


if __name__ == "__main__":
    build()
