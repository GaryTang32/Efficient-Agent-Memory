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
    return (f'<p class="note">Pilot status: {status}.</p><div class="tbl-wrap"><table><thead><tr><th>Setting</th>'
            '<th>Resolved</th><th>Cost</th><th>$ / resolved</th><th>Median peak</th><th>Median turns</th>'
            '<th>Long outputs previewed</th></tr></thead><tbody>' + "".join(body) + "</tbody></table></div>")


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
"""

NAV_ITEMS = [
    ("wd", "01", "Work done", "wrench", [("wd-time", "Timeline"), ("wd-built", "What was built"), ("wd-spend", "Runs and spend")]),
    ("fd", "02", "Findings", "bulb", [("fd-key", "Key findings"), ("fd-works", "What works, what does not")]),
    ("rs", "03", "Results", "gauge", [("rs-synth", "Four long tasks"), ("rs-swe", "SWE-bench Verified"), ("rs-pick", "Which preset")]),
    ("cc", "04", "Claude Code plugin", "layers", [("cc-how", "How it works"), ("cc-pilot", "Pilot in Claude Code"), ("cc-vs", "Versus other memory tools")]),
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
    return "Pilot inside Claude Code (same issues, same prompt): " + "; ".join(bits) + "."


TIMELINE_ROWS = [
    ("22 Oct", "Phase 1: single methods", "ReSum, masking, AgentDiet, Context-Folding, turn control, workspace on two tasks", "No single method solves multi-session work"),
    ("23–26 Oct", "Long tasks, AutoMemory v1", "Four long tasks, model-normalised protocol; MemoryOS, LightMem, Nemori", "Workspace + compaction is model-robust; memory systems 0.2–0.5 lower"),
    ("4 Nov", "Eight new methods; v2 and v3", "Strands, CADOC, ReFold, SJC, AKV, raw RAG, CORAL, SelfCompact; previews, folding", "AutoMemory v2 becomes the default"),
    ("5 Nov", "Sonnet seeds; SWE-bench (40 issues)", "Decision rule fixed in advance; first real-repository workdays", "automem_v2_strong; lean wins on real code"),
    ("6 Nov", "NVIDIA handoff; 100 issues", "EoCC prompts; SWE-bench-faithful grading; 32K and 16K windows; 480 runs", "automem_v2_lean_handoff for accuracy-first coding"),
    ("6–7 Nov", "Front page and housekeeping", "README with charts and flowcharts; CONTRIBUTING, CITATION; papers folder ignored", "PRs #1–#3 merged"),
    ("8 Nov", "Claude Code plugin and pilot", "Hooks: previews from Claude Code's saved output, handoff at compaction, recall, autosave", "Measured inside Claude Code (pilot)"),
]


def timeline_table():
    rows = "".join(f'<tr><th>{E(d)}</th><td><strong>{E(w)}</strong><br><span class="desc">{E(s)}</span></td><td>{E(r)}</td></tr>'
                   for d, w, s, r in TIMELINE_ROWS)
    return f'<div class="tbl-wrap"><table><thead><tr><th>When</th><th>Work</th><th>Outcome</th></tr></thead><tbody>{rows}</tbody></table></div>'


SPEND = [("Phases 1–3 and the eight new methods", "≈ 1,900", 820), ("AutoMemory v2, v3 ablation, Sonnet seeds", "≈ 250", 102),
         ("SWE-bench, 40 issues", "164", 56), ("Earlier pilots and calibration", "—", 162),
         ("NVIDIA handoff: synthetic tasks", "80", 68.59), ("SWE-bench, 100 issues at 32K and the own window", "260", 98.19),
         ("SWE-bench, 100 issues at 16K", "140", 54.31)]


def spend_table():
    pil = sum(c[s]["cost"] for c in P.values() for s in ("plain", "plugin")) if P else 0
    rows = SPEND + ([("Claude Code pilot (so far)" if min(c["plain"]["n"] for c in P.values()) < TARGET else "Claude Code pilot",
                      str(sum(c[s]["n"] for c in P.values() for s in ("plain", "plugin"))), pil)] if P else [])
    body = "".join(f'<tr><th>{E(a)}</th><td class="nm">{E(b)}</td><td class="nm">${c:,.0f}</td></tr>' for a, b, c in rows)
    tot = sum(c for _, _, c in rows)
    return (f'<div class="tbl-wrap"><table><thead><tr><th>Run set</th><th class="nm">Runs</th><th class="nm">Cost</th></tr></thead>'
            f'<tbody>{body}<tr><th>Total</th><td class="nm">≈ 3,000</td><td class="nm"><strong>${tot:,.0f}</strong></td></tr></tbody></table></div>'
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
    ("Finish and extend the Claude Code pilot", "Running" if P and min(c["plain"]["n"] for c in P.values()) < TARGET else "Next", "med", "$60–100 for 100 issues",
     "20 issues per model first; if the plugin holds accuracy at lower cost, run all 100 issues on both models to make the result firm."),
    ("Fewer agent tokens after a handoff reset", "Next", "med", "≈ $20–30",
     "After a handoff reset the agent writes about 45% more output, which is the 6–16 points the recap costs. Cutting that would make the accurate preset cheap as well."),
    ("Adaptive workspace", "Next", "med", "small",
     "Turn the note workspace on only when the task refers to earlier sessions, so one preset fits both multi-session and independent work."),
    ("More SWE-bench evidence for handoff", "Next", "low", "≈ $50–60",
     "At 16K, handoff resolved 7 issues ReSum missed and missed 2 (Haiku; sign test p ≈ 0.18). More seeds or a second repository would settle it."),
    ("Report cost on two price bases", "Next", "low", "no API cost",
     "List prices with caching (Bedrock and the CLI today) and context-length pricing (the NVIDIA paper's model) for self-hosted or long-context-tier users."),
]
GAPS = [
    ("One repository", "Gap", "low", "", "The SWE-bench set is 100 issues from Django; another repository would test generality."),
    ("Emulated windows", "Gap", "low", "", "The synthetic tasks emulate small windows (16K–48K) to create memory pressure."),
    ("Local-only reports", "Gap", "low", "", "Detailed reports in docs/results/ and the rows behind docs/overview.html are git-ignored, so a fresh clone cannot rebuild those pages; the README charts can be rebuilt."),
]


def build():
    syn = RC.synth_chart(RC.THEMES["light"])
    swe = RC.swe_chart(RC.THEMES["light"])
    dol = RC.dollars_chart(RC.THEMES["light"])
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
      <p class="eyebrow">Work report · 8 November 2026</p>
      <h1>Efficient Agent Memory</h1>
      <p class="dek">What was built, what the measurements show, how the memory layer now ships as a Claude Code plugin, and what is left to do.</p>
      <p class="hero-meta"><span>≈ 3,000 benchmark runs</span><span>27 methods and variants</span><span>Claude Haiku and Sonnet</span><span>SWE-bench Verified: 100 Django issues</span><span>PRs #1–#3 merged</span></p>
    </div>
    <div class="brief">
      <span class="k">{ic("brief")}Key points</span>
      <ul class="plain">
        <li><strong>Fewer tokens is not fewer dollars.</strong> Re-sent history is cheap while it stays in the prompt cache; methods that rewrite it every step cost more than they save (AKV: 93% of the ceiling's cost dropping every turn, 22% in blocks of 8).</li>
        <li><strong>Let the harness remember.</strong> Previews at ingestion, automatic recall and compaction at a fixed trigger worked on Haiku and Sonnet; methods that need the model to manage its memory failed on Haiku.</li>
        <li><strong>AutoMemory v2</strong> matches the unoptimised ceiling on four long tasks at 85% (Haiku) and 58% (Sonnet) of its cost; no newer published method beats it across the board.</li>
        <li><strong>On 100 real Django issues</strong> at a 16K window, <code>automem_v2_lean</code> is the cheapest ($0.123 per resolved issue on Sonnet), and NVIDIA's handoff recap brings both models to the ceiling's accuracy for 6–16 points more cost.</li>
        <li><strong>{E(pilot_headline())}</strong></li>
      </ul>
      <p class="rec"><strong>Recommendation:</strong> use the plugin's harness steps (previews, handoff at compaction, recall) rather than instructions in CLAUDE.md; pick <code>automem_v2</code> for multi-session work and <code>automem_v2_lean</code> for independent coding issues.</p>
    </div>
    {toc()}
  </header>

  {banner("wd", "01", "Part 1 · What", "wrench", "Work done", ["github.com/GaryTang32/Efficient-Agent-Memory", "main @ PR #3"])}
  {section("wd-time", "1.1", "trend", "Timeline", timeline_table())}
  {section("wd-built", "1.2", "box", "What was built", '''
    <div class="kv">
      <div><strong>Benchmark harness</strong><p>ReAct loop with technique hooks, emulated windows, a cache-aware cost meter; Claude Code CLI, Bedrock, LiteLLM and mock backends.</p></div>
      <div><strong>27 methods and variants</strong><p>Faithful ports of published methods, each with its source and deviations documented, from ReSum to NVIDIA's EoCC.</p></div>
      <div><strong>Tasks</strong><p>Four long synthetic tasks and SWE-bench Verified workdays on 100 Django issues, graded as SWE-bench grades them.</p></div>
      <div><strong>AutoMemory</strong><p>The combined memory layer as a bench technique, a Python library and an MCP server, with five presets.</p></div>
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
      <tr><th>Match the layer to the work</th><td>Notes were essential for multi-session tasks and pure overhead (about 50% more tool calls) on independent coding issues.</td></tr>
      <tr><th>A structured recap helps coding sessions</th><td>NVIDIA's handoff fields (applied changes, dead ends, next command): 81 vs 76 (Haiku) and 88 vs 86 (Sonnet) resolved at 16K; ties ReSum on synthetic tasks.</td></tr>
      <tr><th>Real coding sessions fit in short contexts</th><td>Django issue sessions peaked at 16–21K tokens; at 32K compaction fired 3–9 times in 100 issues.</td></tr>
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
        <li>A compaction method alone, without guard or notes<span class="ev">EoCC alone: 15 Haiku sessions overflowed at 16K</span></li>
        <li>Notes on independent tasks<span class="ev">+50% tool calls</span></li></ul></div>
    </div>''')}

  {banner("rs", "03", "Part 3 · How much", "gauge", "Results", ["Floor and ceiling on the same instances", "Cost relative to the ceiling"])}
  {section("rs-synth", "3.1", "chart", "Four long synthetic tasks", f'<p class="lead-in">Mean score against cost relative to the unoptimised ceiling. Top left is best.</p><div class="chart">{syn}</div>')}
  {section("rs-swe", "3.2", "cpu", "SWE-bench Verified: 100 Django issues", f'''<p class="lead-in">One fresh session per issue, graded with the official FAIL_TO_PASS and PASS_TO_PASS tests. The board shows every setting; the charts show the 16K window and Sonnet's dollars per resolved issue.</p>
    {X.swe_board(SWE)}<div class="chart">{swe}</div><div class="chart">{dol}</div>''')}
  {section("rs-pick", "3.3", "route", "Which preset", '''
    <div class="tbl-wrap"><table><thead><tr><th>Work</th><th>Preset</th><th>Why</th></tr></thead><tbody>
      <tr><th>Multi-session work that builds on earlier results</th><td><code>automem_v2</code></td><td>Ceiling accuracy at 85% / 58% of its cost</td></tr>
      <tr><th>Same, strong agent model</th><td><code>automem_v2_strong</code></td><td>Sonnet solved 16/16 runs at 61%</td></tr>
      <tr><th>Independent coding issues, cost first</th><td><code>automem_v2_lean</code></td><td>Sonnet $0.123 per resolved issue at 16K</td></tr>
      <tr><th>Independent coding issues, accuracy first</th><td><code>automem_v2_lean_handoff</code></td><td>81 / 88 of 100 resolved at 16K</td></tr>
      <tr><th>Short sessions on a large window</th><td>cached full history</td><td>Haiku 77/100 at 62% at 32K</td></tr>
    </tbody></table></div>''')}

  {banner("cc", "04", "Part 4 · For everyday users", "layers", "Claude Code plugin", ["plugins/automem", "claude --plugin-dir plugins/automem"])}
  {section("cc-how", "4.1", "steps", "How it works", '''
    <p>The plugin runs the measured harness steps as Claude Code hooks: no extra model calls, nothing rewritten in the cached history. Claude Code already caches prompts and cuts long Bash output to a 2 KB head-only preview with the full text saved to a file; the plugin builds on that.</p>
    <div class="tbl-wrap"><table><thead><tr><th>Hook</th><th>What it does</th><th>Measured rule behind it</th></tr></thead><tbody>
      <tr><th>PostToolUse (Bash)</th><td>Long output reaches the model as head + tail (1,500 characters each). For output Claude Code truncated, the tail is read from Claude Code's own saved copy, so test summaries and failures at the end stay visible.</td><td>Previews at ingestion (Haiku 11/16 vs 7/16)</td></tr>
      <tr><th>PreCompact</th><td>Compaction keeps NVIDIA's six-field handoff recap.</td><td>81 vs 76 / 88 vs 86 at 16K</td></tr>
      <tr><th>SessionStart</th><td>Recalls this project's notes at startup, resume, clear and after compaction.</td><td>Recall: Haiku 0.34 without, 0.99 with notes on Sonnet</td></tr>
      <tr><th>Stop</th><td>Saves each turn's final message as a project note.</td><td>Autosave</td></tr>
    </tbody></table></div>
    <p class="note">Checked live: with a 108 KB output, plain Claude Code showed the model lines 1–234; with the plugin the model saw the head and the real last line, and found a middle line in the saved file without re-running the command.</p>''')}
  {section("cc-pilot", "4.2", "gauge", "Pilot inside Claude Code", f'''<p class="lead-in">Headless Claude Code with its own tools and agent loop, one fresh session per SWE-bench Verified issue, the same prompt and the same spending cap, with and without the plugin.</p>{pilot_table()}''')}
  {section("cc-vs", "4.3", "grid", "Versus other memory tools", '''
    <div class="tbl-wrap"><table><thead><tr><th></th><th>Claude Code's own memory</th><th>Memory services (fact extraction + retrieval)</th><th>Model-managed memory (memory tools)</th><th>This plugin</th></tr></thead><tbody>
      <tr><th>Who acts</th><td>Harness: CLAUDE.md and auto memory loaded each session; compaction near the context limit</td><td>An extra LLM extracts facts; embeddings retrieve them</td><td>The agent decides when to read and write memory</td><td>Harness hooks, no extra LLM calls</td></tr>
      <tr><th>Targets</th><td>Persistent instructions and facts</td><td>Long-term recall across chats</td><td>Long-term recall</td><td>Context size and cost per task, plus recall</td></tr>
      <tr><th>Cost side effects</th><td>None added</td><td>Extraction calls per turn; retrieved text changes the prompt</td><td>Tool calls the model may skip</td><td>None added; edits only at ingestion and compaction</td></tr>
      <tr><th>Measured here</th><td>Prompt caching and output persistence observed</td><td>MemoryOS, LightMem, Nemori: 0.2–0.5 lower than plain notes</td><td>CORAL: tools barely used on Haiku</td><td>Bench evidence above; Claude Code pilot in 4.2</td></tr>
    </tbody></table></div>
    <p class="note">Other memory services (for example mem0, Zep or Letta) have not been measured in this repository.</p>''')}

  {banner("todo", "05", "Part 5 · Next", "flag", "To-do", ["Status as of 8 November 2026"])}
  {section("todo-blocked", "5.1", "alert", "Blocked", todo(BLOCKED))}
  {section("todo-next", "5.2", "route", "Next steps", todo(NEXT))}
  {section("todo-gaps", "5.3", "info", "Known gaps", todo(GAPS))}

  <section class="endnote" id="links" aria-labelledby="h-links">
    <h2 id="h-links">{ic("book", "ic hic")}Links</h2>
    <div class="refs-group"><ol class="refs">
      <li><a href="https://github.com/GaryTang32/Efficient-Agent-Memory">Repository</a> <span class="desc">README with charts, flowcharts and quick start</span></li>
      <li><a href="https://github.com/GaryTang32/Efficient-Agent-Memory/pull/1">PR #1</a>, <a href="https://github.com/GaryTang32/Efficient-Agent-Memory/pull/2">PR #2</a>, <a href="https://github.com/GaryTang32/Efficient-Agent-Memory/pull/3">PR #3</a> <span class="desc">merged</span></li>
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
