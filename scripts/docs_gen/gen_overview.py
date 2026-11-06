"""Generator for docs/overview.html.

    python scripts/docs_gen/build_overview_data.py scripts/docs_gen/overview_data.json   # from results/*.jsonl
    python scripts/docs_gen/gen_overview.py

The page style (assets/ref.css, sprite.svg, the navigation and motion scripts) follows the reference brief the user
supplied; overview_extras.py holds the interactive pieces."""
"""Generate docs/overview.html (Efficient Agent Memory research brief) in the reference brief's style."""
import json
import html
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import overview_extras as X  # noqa: E402

HERE = Path(__file__).resolve().parent
ASSETS = HERE / "assets"
REF_CSS = (ASSETS / "ref.css").read_text()
SPRITE = (ASSETS / "sprite.svg").read_text()
D = json.loads((HERE / "overview_data.json").read_text())
SWE = D.pop("__swe__", {})
OUT = HERE.parent.parent / "docs" / "overview.html"
FAMS = ["research_corpus", "ops_stream", "ledger_audit", "repo_debug"]
FAM_SHORT = {"research_corpus": "Research", "ops_stream": "Ops stream", "ledger_audit": "Ledger audit",
             "repo_debug": "Repo debug"}
E = html.escape

EXTRA_CSS = """
  /* ---------- Additions for this brief ---------- */
  .tabs-v { display: grid; grid-template-columns: minmax(0, 250px) minmax(0, 1fr); gap: 14px; align-items: start; }
  .tabs-v > * { min-width: 0; }
  .tabs-v .tablist { flex-direction: column; flex-wrap: nowrap; border-bottom: 0; border-right: 1px solid var(--rule); gap: 1px; padding-right: 8px; }
  .tabs-v .tablist .grp { font-family: var(--font-cond); font-weight: 600; font-size: 0.72rem; letter-spacing: 0.08em; text-transform: uppercase; color: var(--muted); padding: 10px 10px 2px; }
  .tabs-v .tablist button { justify-content: flex-start; text-align: left; border-bottom: 0; border-left: 3px solid transparent; padding: 5px 10px; min-height: 32px; font-size: 0.9rem; }
  .tabs-v .tablist button[aria-selected="true"] { border-left-color: var(--part); background: var(--part-tint); color: var(--ink); }
  .tabs-v .tablist button span { min-width: 2.2em; color: var(--part); }
  .tabpanel h4.mh { margin-top: 2px; }
  .mname { font-family: var(--font-display); font-weight: 600; font-size: 1.32rem; line-height: 1.2; }
  .mmeta { font-family: var(--font-mono); font-size: 0.76rem; color: var(--muted); display: flex; flex-wrap: wrap; gap: 2px 14px; }
  .chipset { display: flex; flex-wrap: wrap; gap: 6px; }
  .chip { font-family: var(--font-mono); font-size: 0.72rem; padding: 2px 8px; border-radius: 999px; white-space: nowrap; background: var(--surface); color: var(--muted); border: 1px solid var(--rule); }
  .chip.h { background: var(--check-tint); color: var(--check); border-color: transparent; }
  .chip.m { background: var(--amber-tint); color: var(--amber); border-color: transparent; }
  .chip.a { background: var(--accent-tint); color: var(--accent); border-color: transparent; }
  .chip.v { background: var(--violet-tint); color: var(--violet); border-color: transparent; }
  .resgrid { display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); gap: 10px; }
  .resgrid .rg { border: 1px solid var(--rule); border-radius: 4px; padding: 8px 12px; display: flex; flex-direction: column; gap: 4px; min-width: 0; background: var(--paper); overflow-x: auto; }
  .rg .k { font-family: var(--font-cond); font-weight: 600; font-size: 0.78rem; letter-spacing: 0.06em; text-transform: uppercase; color: var(--muted); }
  .rg table { min-width: 0; font-size: 0.82rem; }
  .rg th, .rg td { padding: 3px 6px; }
  .rg thead th { background: var(--surface); color: var(--muted); }
  .rg tbody tr:nth-child(even) > * { background: transparent; }

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
  .legend { display: flex; flex-wrap: wrap; gap: 6px 16px; font-size: 0.8rem; color: var(--muted); align-items: center; }
  .legend i { display: inline-block; width: 14px; height: 10px; border-radius: 2px; margin-right: 6px; vertical-align: -1px; }

  /* heatmap */
  table.heat { min-width: 980px; font-size: 0.8rem; }
  table.heat td.hc { text-align: center; font-family: var(--font-mono); font-size: 0.76rem; white-space: nowrap; padding: 4px 4px; }
  table.heat td.hc b { display: block; font-weight: 600; font-size: 0.8rem; }
  table.heat td.na { color: var(--soft); text-align: center; }
  table.heat thead th.mg { text-align: center; border-left: 2px solid var(--paper); }
  table.heat tbody th { font-size: 0.82rem; white-space: nowrap; }
  table.heat td.sep { border-left: 2px solid var(--rule-strong); }
  .hl-0 { background: #FBE9E6 !important; } .hl-1 { background: #FCF1DC !important; } .hl-2 { background: #F4F4E4 !important; }
  .hl-3 { background: #E3F2EC !important; } .hl-4 { background: #C9E8DE !important; }

  .flow-note { font-family: var(--font-mono); font-size: 0.74rem; color: var(--muted); }
  .verdict-line { font-size: 0.94rem; background: var(--part-tint); border-radius: 2px; padding: 8px 12px; }
  .verdict-line strong { color: var(--part); font-family: var(--font-cond); font-size: 0.84rem; letter-spacing: 0.06em; text-transform: uppercase; margin-right: 6px; }
  code { font-family: var(--font-mono); font-size: 0.86em; background: var(--surface); padding: 0 4px; border-radius: 2px; }
  @media (max-width: 1100px) { .tabs-v { grid-template-columns: minmax(0, 1fr); } .tabs-v .tablist { border-right: 0; border-bottom: 1px solid var(--rule); flex-direction: row; flex-wrap: wrap; padding: 0 0 6px; } .tabs-v .tablist .grp { width: 100%; padding: 6px 0 0; } }
  @media (max-width: 900px) { .resgrid { grid-template-columns: 1fr; } }
  [id^="obj"] { --part: var(--accent); --part-tint: var(--accent-tint); }
  [id^="hx"] { --part: var(--check); --part-tint: var(--check-tint); }
  [id^="mt"] { --part: var(--amber); --part-tint: var(--amber-tint); }
  [id^="ef"] { --part: var(--violet); --part-tint: var(--violet-tint); }
"""

# ------------------------------------------------------------------ data helpers
def cell(spec_by_fam, model):
    out = {}
    for f in FAMS:
        s = spec_by_fam(f) if callable(spec_by_fam) else spec_by_fam
        if s is None:
            continue
        v = D.get(s, {}).get(model, {}).get(f)
        if v:
            out[f] = v
    return out


def within(name):
    return lambda f: name if f == "research_corpus" else f"fs_workspace+{name}"


ROWS = [  # (group, label, sub, haiku spec, sonnet spec)
    ("anc", "No memory (floor)", "naive: full history, no caching, task window", "naive", "naive"),
    ("anc", "Full context, cached", "full: provider caching, task window", "full", "full"),
    ("anc", "Unoptimised ceiling", "naive@native: the model's own window", "naive@native", "naive@native"),
    ("pub", "ReSum alone", "Alibaba Tongyi Lab", "resum", "resum"),
    ("pub", "Observation masking", "Lindenbauer et al. 2025", "obs_mask", "obs_mask"),
    ("pub", "Context-Folding", "ByteDance Seed", None, "folding"),
    ("pub", "Note workspace alone", "FS-Researcher / Manus", "fs_workspace", "fs_workspace"),
    ("pub", "Workspace + ReSum", "best single combination of phase 1", "fs_workspace+resum", "fs_workspace+resum"),
    ("pub", "MemoryOS + ReSum", "BUPT + Tencent (official package)", "ext:memoryos+resum", None),
    ("pub", "LightMem + ReSum", "Zhejiang University (official package)", "ext:lightmem+resum", None),
    ("pub", "Nemori + ReSum", "Fudan + Shanda (official package)", "ext:nemori+resum", None),
    ("new", "Strands harness defaults", "AWS", "strands", "strands"),
    ("new", "CADOC", "SJTU", within("cadoc"), within("cadoc")),
    ("new", "ReFold", "UCSB + Intel", within("refold"), within("refold")),
    ("new", "SJC on ReSum", "University of Virginia", within("sjc"), within("sjc")),
    ("new", "OpenClaw (SJC's host)", "University of Virginia", within("openclaw"), within("openclaw")),
    ("new", "OpenClaw + SJC", "University of Virginia", within("openclaw,sjc=true"), within("openclaw,sjc=true")),
    ("new", "AKV drop, every turn", "Tsinghua + CUHK", within("akv_drop"), within("akv_drop")),
    ("new", "AKV drop, blocks of 8", "Tsinghua + CUHK; our cache-aware variant", within("akv_drop:keep=8,block=8"),
     within("akv_drop:keep=8,block=8")),
    ("new", "Raw-history RAG + ReSum", "Memory Tax / Naive RAG studies", "raw_rag+resum", "raw_rag+resum"),
    ("new", "CORAL (prompting)", "CUHK + Tencent + HKUST", within("coral"), within("coral")),
    ("new", "SelfCompact", "Apple + JHU", within("selfcompact"), within("selfcompact")),
    ("ours", "AutoMemory v1", "Sonnet: Haiku summariser", "automem", "automem#aux=cc-haiku"),
    ("ours", "AutoMemory v2 (default)", "v1 + previews at ingestion", "automem:ingest=0.1", "automem:ingest=0.1#aux=cc-haiku"),
    ("ours", "AutoMemory v2 slim", "v2 + ReFold folding", "automem:fold=true,ingest=0.1",
     "automem:fold=true,ingest=0.1#aux=cc-haiku"),
    ("ours", "AutoMemory v2 strong", "v2 + SJC pruning; for strong agent models", "automem:ingest=0.1,compact=sjc",
     "automem:ingest=0.1,compact=sjc#aux=cc-haiku"),
    ("ours", "v2 + OpenClaw (v3 candidate)", "structured summaries", "automem:ingest=0.1,compact=openclaw",
     "automem:ingest=0.1,compact=openclaw#aux=cc-haiku"),
]
GROUP_NAME = {"anc": "Reference points", "pub": "Published methods (phase 1)",
              "new": "Methods from the Sep–Nov 2026 scan", "ours": "This project: AutoMemory"}


def agg(c):
    if not c:
        return None
    sc = [v["score"] for v in c.values()]
    rec = [v["rec"] for v in c.values() if v["rec"] is not None]
    return dict(n=len(c), score=sum(sc) / len(sc), rec=sum(rec) / len(rec) if rec else None,
                cost=sum(v["cost"] for v in c.values()) / len(c), peak=sum(v["peak"] for v in c.values()) / len(c),
                solved=sum(v["solved"] for v in c.values()), runs=sum(v["n"] for v in c.values()),
                minscore=min(sc))


# ------------------------------------------------------------------ SVG helpers
def flow_svg(fid, title, desc, nodes, notes=None, width=820):
    """Horizontal flow: nodes = [(name, sub, kind)], kind in nb | nb-focal | nb-check | nb-dash."""
    n = len(nodes)
    gap = 34
    w = (width - 64 - gap * (n - 1)) / n
    h = 78
    y = 34
    parts = [f'<svg class="dg" viewBox="0 0 {width} 150" style="min-width:720px;max-width:100%" role="img" '
             f'aria-labelledby="{fid}-t {fid}-d"><title id="{fid}-t">{E(title)}</title><desc id="{fid}-d">{E(desc)}</desc>',
             f'<defs><marker id="{fid}-a" markerWidth="8" markerHeight="6" refX="7" refY="3" orient="auto">'
             f'<polygon points="0 0, 8 3, 0 6" class="hd"/></marker></defs>',
             f'<rect width="{width}" height="150" class="bgp"/>']
    for i, (name, sub, kind) in enumerate(nodes):
        x = 32 + i * (w + gap)
        parts.append(f'<rect x="{x:.0f}" y="{y}" width="{w:.0f}" height="{h}" rx="6" class="mk"/>'
                     f'<rect x="{x:.0f}" y="{y}" width="{w:.0f}" height="{h}" rx="6" class="{kind}"/>')
        parts.append(f'<circle cx="{x + 14:.0f}" cy="{y + 14}" r="9" class="stepno"/>'
                     f'<text x="{x + 14:.0f}" y="{y + 18}" text-anchor="middle" class="stepno-t">{i + 1}</text>')
        lines = _wrap(name, int(w / 7.6))
        for j, ln in enumerate(lines[:2]):
            parts.append(f'<text x="{x + w / 2:.0f}" y="{y + 34 + j * 16}" text-anchor="middle" class="n-name">{E(ln)}</text>')
        sl = _wrap(sub, int(w / 6.3))
        for j, ln in enumerate(sl[:2]):
            parts.append(f'<text x="{x + w / 2:.0f}" y="{y + 34 + len(lines[:2]) * 16 + 2 + j * 13}" text-anchor="middle" '
                         f'class="n-sub">{E(ln)}</text>')
        if i < n - 1:
            x2 = x + w
            parts.append(f'<path d="M{x2 + 2:.0f} {y + h / 2:.0f} H{x2 + gap - 4:.0f}" class="ar" marker-end="url(#{fid}-a)"/>')
    if notes:
        parts.append(f'<text x="32" y="138" class="lane-s">{E(notes)}</text>')
    parts.append("</svg>")
    return "".join(parts)


def _wrap(text, n):
    words, lines, cur = text.split(), [], ""
    for wd in words:
        if len(cur) + len(wd) + 1 > n and cur:
            lines.append(cur)
            cur = wd
        else:
            cur = f"{cur} {wd}".strip()
    if cur:
        lines.append(cur)
    return lines


def figure(svg, caption):
    return f'<figure><div class="diagram">{svg}</div><figcaption>{caption}</figcaption></figure>'


def ic(name, cls="ic"):
    return f'<svg class="{cls}" aria-hidden="true"><use href="#i-{name}"/></svg>'


# ------------------------------------------------------------------ methods catalogue
M = []  # dicts


def method(**kw):
    M.append(kw)


method(id="resum", grp="Published methods", tag="P1", name="ReSum", dev="Alibaba Tongyi Lab",
       src="arXiv 2509.13313 · official WebResummer code (MIT)", acts="Compaction", driver="Harness",
       what="Periodic summarisation that replaces the whole history with one reset message.",
       how=["The harness watches the context size. When it reaches 0.9 × (K·1024 − 1000) tokens, it calls a summariser model.",
            "The summariser sees the question, the previous summary and every message since the last reset, and writes a "
            "<code>&lt;summary&gt;</code> of the essential facts. Its prompt forbids guessing or inferring.",
            "The history is replaced by one user message: the question plus the summary. The agent continues from there."],
       impl="Official prompts and trigger (third_party/resum.py). K is set per task so the trigger sits just under the window. "
            "Inside AutoMemory the summariser can be a cheaper model.",
       flow=[("History grows", "every step adds calls and results", "nb"), ("Trigger", "0.9 × (K·1024 − 1000) tokens", "nb-focal"),
             ("Summariser call", "question + last summary + history", "nb"), ("Reset", "question + <summary> only", "nb-check")],
       ev="strong", evtext="Measured on all four long tasks and both models; core of AutoMemory.",
       verdict="Necessary but not sufficient alone: it loses cross-session state, so it is combined with a note workspace.",
       rows=("resum", "resum"))
method(id="obsmask", grp="Published methods", tag="P2", name="Observation masking", dev="Lindenbauer et al. (NeurIPS'25 DL4Code)",
       src="settings from AgentDiet / AttnCompress artifacts", acts="History edit", driver="Harness",
       what="Old tool outputs are replaced by a placeholder; the agent keeps its own reasoning and calls.",
       how=["After each step, every observation older than the last 2 steps is checked.",
            "If it has at least 300 tokens it becomes \"Environment Observation Ommited\" (sic).",
            "Nothing is summarised; the text is simply gone. Every masking edit changes earlier history, which breaks the prompt cache from that point on."],
       impl="Window 2, minimum 300 tokens, the artifact's placeholder string. Publishes a stable boundary so a Bedrock cache point can sit before the edits.",
       flow=[("Step completes", "assistant call + tool result", "nb"), ("Age check", "older than last 2 steps, ≥300 tokens", "nb-focal"),
             ("Placeholder", "observation text removed", "nb-dash"), ("Cache breaks", "re-billed from the edit on", "nb")],
       ev="strong", evtext="chain_hunt: Haiku 1/5 solved at 608% of full-context cost; Sonnet 3/3 at 187% with a 9K peak.",
       verdict="Slim context but cache-hostile; only works when the model can redo lost reads. Model-dependent.",
       rows=("obs_mask", "obs_mask"))
method(id="agentdiet", grp="Published methods", tag="P3", name="AgentDiet", dev="PKU + ByteDance (FSE'26)",
       src="official artifact, CC BY 4.0 · prompt + Algorithm 1", acts="History edit", driver="Side model",
       what="A cheap reflection model rewrites an earlier step to remove useless, redundant or expired content.",
       how=["Two steps after a step completes (a = 2), a reflection model reads it with one step of context either side (b = 1).",
            "If the step is longer than θ = 500 tokens, the model returns a trimmed version that drops what is no longer needed.",
            "The trimmed text replaces the original in the history."],
       impl="Official prompt and parameters verbatim; the reflector is the run's auxiliary model.",
       flow=[("Step k done", "full observation in history", "nb"), ("Reflect at k+2", "cheap model reads k−1…k+1", "nb-focal"),
             ("Trim", "drop useless / redundant / expired", "nb"), ("Replace", "history edited in place", "nb-dash")],
       ev="outcome", evtext="chain_hunt: Haiku 5/5 solved, but 410% of full-context cost with 7% cache hits. Sonnet's API safeguards refused the reflection calls on ledger_audit.",
       verdict="Saves tokens, costs dollars on a cached route: every trim rewrites history. Not used further.",
       rows=None)
method(id="folding", grp="Published methods", tag="P4", name="Context-Folding (FoldAgent)", dev="ByteDance Seed + CMU, Stanford (ICML'26)",
       src="sunnweiwei/FoldAgent · Apache-2.0", acts="Sub-context", driver="Model",
       what="The agent branches a subtask into a separate context and folds back only its summary.",
       how=["The agent calls a <code>branch</code> tool with a subtask description.",
            "A sub-agent works in a fresh context that inherits the main history, and finishes with <code>return</code> and a summary.",
            "Only the summary enters the main context; the branch's tool outputs never do."],
       impl="Official protocol and prompts, at most 5 branches per run.",
       flow=[("Main agent", "decides a subtask", "nb"), ("branch()", "sub-context, own tools", "nb-focal"),
             ("return()", "summary of the subtask", "nb"), ("Fold", "only the summary stays", "nb-check")],
       ev="outcome", evtext="Sonnet research_corpus 3/3 at 20% of the ceiling's cost; ops_stream 0.20 at 308%; ledger_audit 0.11. Haiku never branched on chain_hunt.",
       verdict="Excellent when the model decides to branch on a task that splits cleanly; otherwise expensive or unused.",
       rows=(None, "folding"))
method(id="turn", grp="Published methods", tag="P5", name="Turn control", dev="ByteDance (ICSE'26)",
       src="paper reminder strings · calibration helper", acts="Prompt", driver="Harness",
       what="A turn budget with reminders, calibrated to the 75th percentile of the model's own turn counts.",
       how=["Run the baseline, take the 75th percentile of its turn counts as the limit.",
            "Inject the paper's reminder strings as the agent approaches the limit.",
            "End the run at the limit."],
       impl="Exact reminder strings from the paper; limit from <code>eam-bench calibrate</code>.",
       flow=[("Calibrate", "p75 of baseline turns", "nb"), ("Run", "count turns", "nb"), ("Remind", "paper's strings near the limit", "nb-focal"),
             ("Stop", "at the limit", "nb-dash")],
       ev="outcome", evtext="chain_hunt: 101% (Haiku) and 97% (Sonnet) of full-context cost, same success. No effect.",
       verdict="A no-op on these tasks: the agents finish well inside the calibrated budget.", rows=None)
method(id="workspace", grp="Published methods", tag="P6", name="Note workspace", dev="FS-Researcher (ACL'26, USTC) · Manus",
       src="our minimal port (the repo has no licence)", acts="Cross-session", driver="Model + harness",
       what="Persistent named notes the agent writes and reads, surviving the context window and the session.",
       how=["Two tools: <code>write_note(name, content)</code> and <code>read_notes()</code>.",
            "The system prompt asks the agent to save intermediate results and to read its notes at the start of a session.",
            "Notes live outside the conversation, so compaction and session ends do not erase them."],
       impl="Three-line tool layer; notes persist for the life of the technique object, i.e. across the sessions of a task.",
       flow=[("Agent works", "finds intermediate results", "nb"), ("write_note()", "saved outside the context", "nb-check"),
             ("Session ends", "conversation discarded", "nb-dash"), ("read_notes()", "next session resumes", "nb-focal")],
       ev="strong", evtext="Alone it overflows on the long tasks; with ReSum it is model-robust on all four tasks (phase-1 best).",
       verdict="The cross-session half of the answer. AutoMemory makes recall and saving automatic.",
       rows=("fs_workspace", "fs_workspace"))
method(id="extmem", grp="Published methods", tag="P7", name="Official memory systems", dev="MemoryOS (BUPT + Tencent) · LightMem (ZJU) · Nemori (Fudan + Shanda)",
       src="official packages through a sidecar process", acts="Cross-session", driver="Side model",
       what="Dedicated long-term memory systems: tiers and heat-based promotion (MemoryOS), pre-compressed topic segments (LightMem), predictive episodes (Nemori).",
       how=["Each session's messages are added to the memory system, which extracts and stores memories with its own LLM calls.",
            "At the start of the next session the task is the query; retrieved memories go into the first message.",
            "Within a session, ReSum compaction is the same as in the comparator, so the memory system is the only difference."],
       impl="Separate virtualenv and sidecar (scripts/memory_sidecar.py); their LLM calls go through a private gateway and are billed as side calls. Runtime fixes are documented in docs/official_memory_repos.md.",
       flow=[("Session transcript", "messages added", "nb"), ("Memory system", "extract, tier, embed", "nb-focal"),
             ("Next session", "task as the query", "nb"), ("Recall", "memories in the first message", "nb-check")],
       ev="strong", evtext="Haiku, 3 multi-session tasks: 0.2–0.5 lower than a plain note workspace with the same compaction.",
       verdict="Engineered memory loses to plain notes on agent tasks, matching the independent 'Memory Tax' studies.",
       rows=None)
method(id="strands", grp="Sep–Nov 2026 scan", tag="N1", name="Strands harness defaults", dev="AWS",
       src="strands-harness 0.3.3 · strands-agents 1.63.0 · Apache-2.0", acts="Ingestion + compaction + memory", driver="Harness",
       what="AWS's agent harness: truncate big tool outputs to a preview, summarise at 85% of the window, extract facts as long-term memory.",
       how=["A successful tool result over 1,500 tokens becomes a 750-token head/tail preview with a <code>[Stashed] [ref]</code> key; <code>retrieve_context</code> greps or pages the original.",
            "At 85% projected window use, every message except the task and the last 4 is summarised by the main model.",
            "At session end a small model extracts facts into one-line memory files; the top-5 keyword matches are injected ephemerally on the next user turn."],
       impl="Ported from the package source with prompts verbatim. Overflow retry replaced by a pre-call emergency drop; memory extracted every session.",
       flow=[("Tool result", ">1,500 tokens?", "nb"), ("Preview + stash", "750 tokens, retrievable", "nb-focal"),
             ("Summarise at 85%", "keep task + last 4 messages", "nb"), ("Facts to memory", "keyword recall next session", "nb-check")],
       ev="outcome", evtext="ledger_audit: Sonnet 1.00 at 34% cost, Haiku 0.86 at 56%. research_corpus: 0.11 (Haiku) / 0.72 (Sonnet). Sonnet ops_stream 513% cost.",
       verdict="Its ingestion previews are the idea v2 adopted, with a window-relative threshold; the fixed 1,500-token threshold hides document facts.",
       rows=("strands", "strands"))
method(id="cadoc", grp="Sep–Nov 2026 scan", tag="N2", name="CADOC", dev="SJTU",
       src="arXiv 2609.37012 · no public code: re-implemented from the paper", acts="Render (cards)", driver="Harness",
       what="Large tool results become deterministic object cards, replaced in batches only when the cache economics say so.",
       how=["Each large tool result is registered as an immutable, versioned object; its bytes go to a store.",
            "Outside a hot tail (4 steps, 12,800 tokens) objects wait as pending. A ledger W accumulates the cost of carrying them raw.",
            "All pending objects are replaced by <code>&lt;OBJECT_CARD&gt;</code>s at once when W + w_r·G ≥ Q (Q = the cached tokens a rewrite would re-bill). <code>retrieve_object</code> returns exact bytes."],
       impl="Commit rule and defaults as published; rewrite priced as a cache write on this route (w_m = 2, w_r = 0.1 / 0.05).",
       flow=[("Tool result", "registered as an object", "nb"), ("Hot tail", "kept raw", "nb"), ("Pending + ledger W", "wait while W + w_r·G < Q", "nb-focal"),
             ("Batch commit", "cards replace raw text", "nb-check")],
       ev="outcome", evtext="Haiku committed 1,376 cards in 180 batches. Sonnet recovery 0.86; Haiku 0.03–0.23 on two multi-session tasks.",
       verdict="The batching logic works; only the stronger model copes with cards.", rows=(within("cadoc"), within("cadoc")))
method(id="refold", grp="Sep–Nov 2026 scan", tag="N3", name="ReFold", dev="UCSB + Intel",
       src="arXiv 2610.07863 · official engine vendored (Apache-2.0)", acts="Render (dedup + fold)", driver="Model + harness",
       what="The agent marks finished steps STALE; the harness folds them into one-line notes and stubs repeated reads, without editing history.",
       how=["Every reply starts with <code>PROGRESS:</code> and <code>STALE:</code> lines; only the last 3 steps can be named.",
            "Behind a boundary that advances 3 steps at a time, STALE runs fold into one note with their PROGRESS lines and file signatures.",
            "Repeated reads, searches and outputs become stubs pointing at the earlier copy; <code>restore</code> shows any original again."],
       impl="Official engine vendored; adapter for structured tools (restore is a tool). The loop now adds the context gauge to rendered copies.",
       flow=[("Reply", "PROGRESS + STALE lines", "nb"), ("Boundary b_t", "advances every 3 steps", "nb"), ("Fold + dedup", "notes and stubs at render", "nb-focal"),
             ("restore()", "originals on demand", "nb-check")],
       ev="outcome", evtext="Protocol followed in 100% of 927 replies. Sonnet recovery 1.01 (cost 111%); Haiku 0.25 (folded figures it needed).",
       verdict="Slimmest context on Sonnet; relies on the model's STALE judgement, which Haiku gets wrong.", rows=(within("refold"), within("refold")))
method(id="sjc", grp="Sep–Nov 2026 scan", tag="N4", name="SJC + OpenClaw", dev="University of Virginia",
       src="arXiv 2610.20927 · repo has no licence: re-implemented; prompts quoted", acts="Compaction", driver="Harness + judge",
       what="After each compaction, a judge deletes summary entries that did not come from what the tools returned.",
       how=["The host (OpenClaw) writes a five-section summary: Decisions, Open TODOs, Constraints/Rules, Pending user asks, Exact identifiers.",
            "The summary is split into entries. A judge reads the compacted span with BM25-selected evidence (30K budget) and asks of each entry whether it came from an environment output.",
            "Entries scored below 0.5 are deleted; headings stay; any failure commits the raw summary."],
       impl="Judge = Claude Haiku returning p_yes per entry (the paper's Jev classifier is not available). Also adapted to ReSum's free-form summaries.",
       flow=[("Compaction", "OpenClaw five-section summary", "nb"), ("Split entries", "bullets per section", "nb"), ("Source judge", "BM25 evidence, p(yes) per entry", "nb-focal"),
             ("Prune < 0.5", "commit pruned summary", "nb-check")],
       ev="outcome", evtext="Pruned ~37% of OpenClaw entries, 13–16% of ReSum's. Alone: Haiku research 0.75 → 1.00. Inside AutoMemory: Haiku research 0.64, ledger 0.68.",
       verdict="Helps standalone; inside AutoMemory it drops facts Haiku needed. Sonnet-only option (v3 ablation).",
       rows=(within("openclaw,sjc=true"), within("openclaw,sjc=true")))
method(id="akv", grp="Sep–Nov 2026 scan", tag="N5", name="AKV rolling drop", dev="Tsinghua + CUHK",
       src="arXiv 2610.28577 · github.com/thu-nics/AKV (Apache-2.0)", acts="History edit", driver="Harness",
       what="Keep only the latest 12 tool-response turns; drop older ones.",
       how=["Inside a serving engine, AKV drops the KV cache entries of old tool results with no re-prefill.",
            "Over an API the text itself must be removed: every tool result older than the latest 12 tool turns becomes a short placeholder.",
            "Our cache-aware variant waits until 8 turns are past the window and drops them together."],
       impl="Official selection policy (TurnTrigger + TurnSelection(12, tool)); prompt-level drop. block=8 is ours.",
       flow=[("Tool turns", "counted per assistant call", "nb"), ("Window", "latest 12 kept", "nb"), ("Drop", "older results → placeholder", "nb-dash"),
             ("Cache", "re-billed from the drop on", "nb-focal")],
       ev="outcome", evtext="Sonnet research: 93% cost every turn vs 22% in blocks of 8 (same score). ledger_audit 0.00–0.17 on both models.",
       verdict="A serving-engine method; over an API it deletes data the task needs. Batching the edits is the lesson.",
       rows=(within("akv_drop"), within("akv_drop")))
method(id="rawrag", grp="Sep–Nov 2026 scan", tag="N6", name="Raw-history RAG", dev="UIUC et al. (Memory Tax) · Naive RAG · SJTU (MemoryTax)",
       src="arXiv 2610.34073, 2610.30755, 2610.29823 · no RAG code released", acts="Cross-session", driver="Harness",
       what="Index every session's raw turns and retrieve the most relevant chunks for the next session; no extraction, no summaries.",
       how=["At session end, raw turns (task, agent text, calls, full tool results) are chunked into ~1,024-character units with a session header.",
            "At the next session the task text is the query: BM25 top-10 ∪ dense top-10, reranked by a cross-encoder, top 10 kept.",
            "Retrieved chunks go into the first message, capped at 15% of the window."],
       impl="MiniLM embeddings and an ms-marco cross-encoder in a sidecar (scripts/retrieval_sidecar.py).",
       flow=[("Session ends", "raw turns chunked", "nb"), ("Index", "BM25 + dense", "nb"), ("Next task", "query = task text", "nb-focal"),
             ("Recall", "top-10 reranked chunks", "nb-check")],
       ev="outcome", evtext="Sonnet ledger/repo 1.00 at ~90% cost; ops_stream 463% cost. Haiku 0.38–0.62.",
       verdict="Works on Sonnet but notes with automatic recall are cheaper and more accurate here.",
       rows=("raw_rag+resum", "raw_rag+resum"))
method(id="coral", grp="Sep–Nov 2026 scan", tag="N7", name="CORAL (prompting-only)", dev="CUHK + Tencent + HKUST (COLM'26)",
       src="arXiv 2610.40350 · prompts verbatim; code link returns 404", acts="Memory + reset", driver="Model",
       what="The agent manages a structured working memory and decides when to clear its own context.",
       how=["A <code>memory-management-tool</code> adds, updates and deletes units: a YAML task plan and verified facts.",
            "A <code>context-optimization-tool</code> clears the conversation; the next episode starts from the task, the memory and a checkpoint.",
            "The prompt asks for an optimisation after every 3–5 tool calls or a milestone; the model decides."],
       impl="System prompt, tool descriptions and reset template verbatim; unit ids and memory rendering are ours.",
       flow=[("Work", "tool calls", "nb"), ("Memory tool", "plan + verified facts", "nb"), ("Optimise tool", "model decides to reset", "nb-focal"),
             ("New episode", "task + memory + checkpoint", "nb-check")],
       ev="none", evtext="Models barely used the tools: Haiku 7 of 56 sessions, Sonnet 1 of 32. Without resets the context overflows.",
       verdict="Prompting alone does not get the model to manage its memory on these tasks.", rows=(within("coral"), within("coral")))
method(id="selfc", grp="Sep–Nov 2026 scan", tag="N8", name="SelfCompact", dev="Apple + JHU (NeurIPS'26)",
       src="arXiv 2606.23525 · tianjianl/selfcompact (MIT)", acts="Compaction", driver="Model",
       what="The agent judges its own trajectory with a four-question rubric and compacts itself when the answers say it is safe.",
       how=["After a tool round (round ≥ 3, every 2 rounds, past a size gate), the agent's own model answers C1 closed unit, C2 summarisable, C3 progress, N1 stuck.",
            "It compacts iff C1 = C2 = C3 = yes and N1 = no: the same model writes the summary.",
            "The history becomes the task, \"Here is my research so far: …\" and \"Continue your research\"."],
       impl="Official prompts and gates; size gate 0.31 × window; backstop at 0.8 × window (ours).",
       flow=[("Tool round", "gates: round, period, size", "nb"), ("Rubric probe", "C1 C2 C3 N1 on own model", "nb-focal"),
             ("Summary", "same model writes it", "nb"), ("Reset", "task + summary + continue", "nb-check")],
       ev="outcome", evtext="Rubric passed 53% (Haiku) / 67% (Sonnet). Sonnet's smallest mean peak (30%) but 138–179% mean cost.",
       verdict="Slim context, expensive: every probe and summary is a full-prompt call on the agent model.",
       rows=(within("selfcompact"), within("selfcompact")))
method(id="eocc", grp="Sep–Nov 2026 scan", tag="N9", name="EoCC handoff compaction", dev="NVIDIA (\"You don't need long context\")",
       src="arXiv 2611.05306 · compaction prompts from App. G (no code released)", acts="Compaction", driver="Model writes, harness triggers",
       what="At 75% of the window the agent writes a structured handoff recap; the conversation restarts from the task and the recap.",
       how=["The harness sends the paper's compaction prompt as the agent's next user message; the agent answers with no tool calls, so the whole history is read from the prompt cache.",
            "The recap has six fields: objective, established facts, applied changes (verified or not), checks run, dead ends, and the remaining plan with the immediate next command.",
            "The conversation resets to the system prompt, the task and the recap. Inside AutoMemory (compact=handoff) the notes and the last two steps come back too."],
       impl="Prompts quoted verbatim; the texts for its placeholders are ours. writer=aux lets the summariser write the recap. Preset automem_v2_lean_handoff for coding work.",
       flow=[("History grows", "trigger at 0.75 × window", "nb"), ("Handoff prompt", "agent's own next turn", "nb-focal"),
             ("Recap", "facts, changes, dead ends, next command", "nb"), ("Reset", "task + recap (+ notes, last steps)", "nb-check")],
       ev="outcome", evtext="SWE-bench at 16K (100 issues): lean + handoff 81 / 88 resolved vs 76 / 86 with ReSum, at 6–16 points more cost. Alone it overflowed (15 Haiku sessions). Synthetic tasks: ties ReSum on Sonnet, lower on Haiku.",
       verdict="The better recap for coding sessions under a tight window, inside AutoMemory; not a full memory layer on its own.",
       rows=("eocc", "eocc"))
method(id="am1", grp="This project", tag="A1", name="AutoMemory v1", dev="this project",
       src="eam/techniques/auto_memory.py · library eam/memory_skill.py · MCP server eam/mcp_server.py", acts="All four", driver="Harness",
       what="The combination that measured best in phase 1, with every step automatic and every component a switch.",
       how=["Recall: the notes go into the first message of every session and after every compaction. Autosave: each session's answer becomes a note.",
            "Guard: a tool result that would push the next prompt past 90% of the window is offloaded at once, with a pointer.",
            "Compaction: ReSum at 75% of the window (a cheaper summariser is fine), keeping the last 2 steps verbatim."],
       impl="Ablations switch off one component at a time: guard, recall/autosave, keep_recent, compaction (mask / none).",
       flow=[("Session start", "notes recalled", "nb-check"), ("Ingestion guard", "offload what would overflow", "nb"),
             ("Compaction", "ReSum at 0.75 × window", "nb-focal"), ("Session end", "answer autosaved", "nb-check")],
       ev="strong", evtext="Model-robust on all four tasks; Sonnet with a Haiku summariser solved 10/10 at 72% mean cost. Compaction essential (score 0.04–0.62 without).",
       verdict="The base of every later version.", rows=("automem", "automem#aux=cc-haiku"))
method(id="am2", grp="This project", tag="A2", name="AutoMemory v2 (default)", dev="this project",
       src="preset automem_v2 = automem:ingest=0.1", acts="All four", driver="Harness",
       what="v1 plus head/tail previews of tool outputs larger than 10% of the window, retrievable by reference.",
       how=["Everything v1 does.",
            "At ingestion, an output above 10% of the window becomes a 750-token head/tail preview with a stash key; <code>retrieve_context</code> greps it or reads a line range.",
            "Because previews happen before the output enters the history, they never break the prompt cache."],
       impl="Also the default in the library and the MCP server (preview = 0.1). Slim mode adds ReFold folding (automem_v2_slim).",
       flow=[("Tool result", "> 10% of window?", "nb"), ("Preview + stash", "head/tail, retrievable", "nb-focal"),
             ("v1 pipeline", "guard, compaction, recall", "nb"), ("Same accuracy", "fewer tokens per solve", "nb-check")],
       ev="strong", evtext="Haiku 0.88 mean, 11/16 solved (v1 7/16) at 85% cost. Sonnet 0.98 at 64% (v1 72%).",
       verdict="The current default: the only setting at the ceiling's accuracy below its cost on both models.",
       rows=("automem:ingest=0.1", "automem:ingest=0.1#aux=cc-haiku"))
method(id="am3", grp="This project", tag="A3", name="v2 strong + v3 ablation", dev="this project",
       src="automem:ingest=0.1,compact=sjc | openclaw | openclaw+sjc", acts="Compaction", driver="Harness + judge",
       what="v2 with ReSum's summary replaced by OpenClaw's structured summary, SJC pruning, or both.",
       how=["Same as v2 except the compaction step.", "OpenClaw restarts from the task statement; AutoMemory re-adds notes and recent steps.",
            "SJC's Haiku judge prunes entries not sourced from tool outputs."],
       impl="72 runs at the same seeds and windows as v2, then 34 more Sonnet runs (instances 2–3) under a decision rule fixed in advance. v2 + SJC is the preset automem_v2_strong.",
       flow=[("v2", "unchanged", "nb"), ("Compaction swap", "OpenClaw / SJC", "nb-focal"), ("Judge", "prune unsourced entries", "nb"),
             ("Compare", "same seeds as v2", "nb-check")],
       ev="outcome", evtext="Haiku: 0.77–0.81 mean (v2 0.88) at 114–124% cost. Sonnet at 4 seeds: v2 + SJC solved 16/16 (v2 13/16), never below v2 on any task, mean cost +3 to +5 points.",
       verdict="OpenClaw not adopted. SJC on ReSum is the strong-model preset automem_v2_strong; v2 stays the default for weaker models.",
       rows=("automem:ingest=0.1,compact=sjc", "automem:ingest=0.1,compact=sjc#aux=cc-haiku"))

STR = {"strong": ("str-strong", "Measured · both models"), "outcome": ("str-outcome", "Measured · mixed"),
       "qual": ("str-qual", "Partial"), "none": ("str-none", "Did not engage")}


def method_results(m):
    if not m.get("rows"):
        return '<p class="note">Measured on the earlier phase-1 tasks (chain_hunt, ledger_audit); see the evidence line.</p>'
    hs, ss = m["rows"]
    parts = []
    for model, spec, label in (("cc-haiku", hs, "Haiku"), ("cc-sonnet", ss, "Sonnet")):
        c = cell(spec, model) if spec else {}
        if not c:
            parts.append(f'<div class="rg"><span class="k">{label}</span><p class="note">Not run on this model.</p></div>')
            continue
        rows = "".join(
            f'<tr><th>{FAM_SHORT[f]}</th><td>{v["score"]:.2f}</td><td>{"—" if v["rec"] is None else f"{v["rec"]:.2f}"}</td>'
            f'<td>{v["cost"]}%</td><td>{v["peak"]}%</td><td>{v["solved"]}/{v["n"]}</td></tr>' for f, v in c.items())
        parts.append(f'<div class="rg"><span class="k">{label}</span><table><thead><tr><th>Task</th><th>Score</th><th>Recovery</th>'
                     f'<th>Cost</th><th>Peak</th><th>Solved</th></tr></thead><tbody>{rows}</tbody></table></div>')
    return '<div class="resgrid">' + "".join(parts) + "</div>"


def method_tabs():
    lst, panels, grp = [], [], None
    for i, m in enumerate(M):
        if m["grp"] != grp:
            grp = m["grp"]
            lst.append(f'<div class="grp" role="presentation">{E(grp)}</div>')
        lst.append(f'<button type="button" role="tab" id="tab-{m["id"]}" aria-controls="panel-{m["id"]}" '
                   f'aria-selected="{"true" if i == 0 else "false"}"><span>{m["tag"]}</span>{E(m["name"])}</button>')
        cls, lab = STR[m["ev"]]
        how = "".join(f"<li>{h}</li>" for h in m["how"])
        chips = (f'<span class="chip a">acts at: {E(m["acts"])}</span><span class="chip {"h" if m["driver"] == "Harness" else "m"}">'
                 f'driven by: {E(m["driver"])}</span>')
        panels.append(f'''
      <div class="tabpanel" role="tabpanel" id="panel-{m["id"]}" aria-labelledby="tab-{m["id"]}" tabindex="0"{"" if i == 0 else " hidden"}>
        <span class="mname">{E(m["name"])}</span>
        <div class="mmeta"><span>{E(m["dev"])}</span><span>{m["src"]}</span></div>
        <div class="chipset">{chips}</div>
        <dl class="spec">
          <dt>Idea</dt><dd>{m["what"]}</dd>
          <dt>Mechanism</dt><dd><ol class="sd-list">{how}</ol></dd>
          <dt>In this repo</dt><dd>{m["impl"]}</dd>
          <dt>Evidence</dt><dd><span class="str {cls}">{lab}</span>{m["evtext"]}</dd>
        </dl>
        {figure(flow_svg("f-" + m["id"], m["name"] + " mechanism", m["what"], m["flow"]), "Mechanism, step by step.")}
        <h4 class="mh">Measured on the four long tasks</h4>
        {method_results(m)}
        <p class="verdict-line"><strong>Verdict</strong>{m["verdict"]}</p>
      </div>''')
    return ('<div class="tabs tabs-v" data-tabs><div class="tablist" role="tablist" aria-orientation="vertical" '
            'aria-label="Methods">' + "".join(lst) + "</div><div>" + "".join(panels) + "</div></div>")


# ------------------------------------------------------------------ scoreboard (CSS bars)
def scoreboard():
    out = ['<div class="board" role="table" aria-label="Mean score and cost per method and model">',
           '<div class="board-row head" role="row"><span role="columnheader">Method</span>'
           '<span role="columnheader">Haiku · mean score (cost vs ceiling)</span>'
           '<span role="columnheader">Sonnet · mean score (cost vs ceiling)</span></div>']
    grp = None
    for g, label, sub, hs, ss in ROWS:
        if g != grp:
            grp = g
            out.append(f'<div class="board-row grp" role="row"><span role="cell">{GROUP_NAME[g]}</span><span></span><span></span></div>')
        cells = []
        for model, spec in (("cc-haiku", hs), ("cc-sonnet", ss)):
            a = agg(cell(spec, model)) if spec else None
            if not a:
                cells.append('<span class="bcell" role="cell"><span class="btrack"></span><span class="bval"><span class="c">not run</span></span></span>')
                continue
            ceil = agg(cell("naive@native", model))["score"]
            cc = "cheap" if a["cost"] < 90 else "dear" if a["cost"] > 110 else ""
            cov = "" if a["n"] == 4 else f" · {a['n']}/4"
            tip = (f"{label} · {model[3:]}: mean score {a['score']:.2f} (lowest task {a['minscore']:.2f}), "
                   f"recovery {a['rec']:.2f}, cost {a['cost']:.0f}%, peak {a['peak']:.0f}%, solved {a['solved']}/{a['runs']}{cov}"
                   if a["rec"] is not None else f"{label}: score {a['score']:.2f}, cost {a['cost']:.0f}%")
            cells.append(f'<span class="bcell" role="cell" title="{E(tip)}"><span class="btrack"><span class="bfill g-{g}" '
                         f'style="width:{a["score"] * 100:.0f}%"></span><span class="bmark" style="left:{ceil * 100:.0f}%" '
                         f'title="ceiling"></span></span><span class="bval">{a["score"]:.2f} <span class="c {cc}">'
                         f'({a["cost"]:.0f}%{cov})</span></span></span>')
        out.append(f'<div class="board-row" role="row"><span class="bname" role="rowheader">{E(label)}<span class="sub">{E(sub)}</span></span>'
                   + "".join(cells) + "</div>")
    out.append("</div>")
    return "".join(out)


def heatmap():
    head = ('<tr><th rowspan="2">Method</th>' + "".join(f'<th colspan="4" class="mg">{m}</th>' for m in ("Haiku", "Sonnet"))
            + "</tr><tr>" + "".join(f"<th>{FAM_SHORT[f]}</th>" for _ in range(2) for f in FAMS) + "</tr>")
    body, grp = [], None
    for g, label, sub, hs, ss in ROWS:
        if g == "anc" and label != "No memory (floor)" and label != "Unoptimised ceiling":
            continue
        if g != grp:
            grp = g
            body.append(f'<tr><th colspan="9" style="background:var(--surface);font-family:var(--font-cond);'
                        f'text-transform:uppercase;letter-spacing:.06em;font-size:.74rem;color:var(--muted)">{GROUP_NAME[g]}</th></tr>')
        tds = []
        for mi, (model, spec) in enumerate((("cc-haiku", hs), ("cc-sonnet", ss))):
            c = cell(spec, model) if spec else {}
            for fi, f in enumerate(FAMS):
                sep = " sep" if fi == 0 and mi == 1 else ""
                v = c.get(f)
                if not v:
                    tds.append(f'<td class="na{sep}">—</td>')
                    continue
                s = v["score"]
                lvl = 0 if s < 0.4 else 1 if s < 0.7 else 2 if s < 0.85 else 3 if s < 0.97 else 4
                tds.append(f'<td class="hc hl-{lvl}{sep}" title="{E(label)} · {model[3:]} · {f}: score {s:.2f}, cost {v["cost"]}%, '
                           f'peak {v["peak"]}%, solved {v["solved"]}/{v["n"]}"><b>{s:.2f}</b>{v["cost"]}%</td>')
        body.append(f'<tr><th>{E(label)}</th>{"".join(tds)}</tr>')
    return f'<div class="tbl-wrap"><table class="heat"><thead>{head}</thead><tbody>{"".join(body)}</tbody></table></div>'


# ------------------------------------------------------------------ static diagrams
OVERVIEW_SVG = """<svg class="dg" viewBox="0 0 960 300" style="min-width:960px;max-width:1100px" role="img" aria-labelledby="ov-t ov-d">
<title id="ov-t">Where memory and token methods act in an agent loop</title>
<desc id="ov-d">Every step the harness sends the whole history to the model. Methods act at four points: when a tool result is ingested, when the request is rendered, when the history is compacted, and between sessions.</desc>
<defs><marker id="ov-a" markerWidth="8" markerHeight="6" refX="7" refY="3" orient="auto"><polygon points="0 0, 8 3, 0 6" class="hd"/></marker>
<marker id="ov-b" markerWidth="8" markerHeight="6" refX="7" refY="3" orient="auto"><polygon points="0 0, 8 3, 0 6" class="hd-acc"/></marker></defs>
<rect width="960" height="300" class="bgp"/>
<text x="32" y="28" class="lane-t">ONE SESSION · EVERY STEP RE-SENDS THE HISTORY</text>
<rect x="32" y="46" width="170" height="70" rx="6" class="mk"/><rect x="32" y="46" width="170" height="70" rx="6" class="nb"/>
<text x="117" y="76" text-anchor="middle" class="n-name">Task + recalled notes</text><text x="117" y="94" text-anchor="middle" class="n-sub">first message</text>
<rect x="262" y="46" width="200" height="70" rx="6" class="mk"/><rect x="262" y="46" width="200" height="70" rx="6" class="nb-focal"/>
<text x="362" y="76" text-anchor="middle" class="n-name">Request to the model</text><text x="362" y="94" text-anchor="middle" class="n-sub">system + full history</text>
<rect x="522" y="46" width="170" height="70" rx="6" class="mk"/><rect x="522" y="46" width="170" height="70" rx="6" class="nb"/>
<text x="607" y="76" text-anchor="middle" class="n-name">Reply + tool calls</text><text x="607" y="94" text-anchor="middle" class="n-sub">output at 5× input price</text>
<rect x="752" y="46" width="176" height="70" rx="6" class="mk"/><rect x="752" y="46" width="176" height="70" rx="6" class="nb"/>
<text x="840" y="76" text-anchor="middle" class="n-name">Tool results</text><text x="840" y="94" text-anchor="middle" class="n-sub">files, logs, tests</text>
<path d="M204 81 H258" class="ar" marker-end="url(#ov-a)"/><path d="M464 81 H518" class="ar" marker-end="url(#ov-a)"/><path d="M694 81 H748" class="ar" marker-end="url(#ov-a)"/>
<path d="M840 118 V150 H362 V120" class="ar-dash" marker-end="url(#ov-a)"/>
<rect x="545" y="143" width="120" height="13" rx="2" class="mk"/><text x="605" y="153" text-anchor="middle" class="a-lab">APPENDED TO HISTORY</text>
<line x1="32" y1="176" x2="928" y2="176" class="rule-line"/>
<text x="32" y="198" class="lane-t">WHERE THE METHODS ACT</text>
<rect x="32" y="210" width="210" height="70" rx="6" class="nb-check"/>
<text x="137" y="232" text-anchor="middle" class="t-check">1 · Ingestion</text><text x="137" y="250" text-anchor="middle" class="n-sub">previews, guard, offload</text><text x="137" y="266" text-anchor="middle" class="n-sub">cache-safe</text>
<rect x="262" y="210" width="210" height="70" rx="6" class="nb-focal"/>
<text x="367" y="232" text-anchor="middle" class="n-name">2 · Render</text><text x="367" y="250" text-anchor="middle" class="n-sub">dedup, folding, object cards</text><text x="367" y="266" text-anchor="middle" class="n-sub">rewrites prefix in batches</text>
<rect x="492" y="210" width="210" height="70" rx="6" class="nb"/>
<text x="597" y="232" text-anchor="middle" class="n-name">3 · Compaction</text><text x="597" y="250" text-anchor="middle" class="n-sub">summaries, masking, drops</text><text x="597" y="266" text-anchor="middle" class="n-sub">rare resets keep the cache</text>
<rect x="722" y="210" width="206" height="70" rx="6" class="nb-dash"/>
<text x="825" y="232" text-anchor="middle" class="n-name">4 · Across sessions</text><text x="825" y="250" text-anchor="middle" class="n-sub">notes, recall, memory systems</text><text x="825" y="266" text-anchor="middle" class="n-sub">survives the session end</text>
<path d="M137 208 V196 H840 V120" class="ar-dash" style="opacity:.35"/>
</svg>"""

LOOP_SVG = """<svg class="dg" viewBox="0 0 960 230" style="min-width:960px;max-width:1100px" role="img" aria-labelledby="lp-t lp-d">
<title id="lp-t">The benchmark's agent loop and technique hooks</title>
<desc id="lp-d">Per step: before_call, render, the model call, after_call, the tool runs, on_tool_result. Session-level hooks are on_session_start and on_session_end.</desc>
<defs><marker id="lp-a" markerWidth="8" markerHeight="6" refX="7" refY="3" orient="auto"><polygon points="0 0, 8 3, 0 6" class="hd"/></marker></defs>
<rect width="960" height="230" class="bgp"/>
<text x="32" y="26" class="lane-t">PER STEP</text>
""" + "".join(
    f'<rect x="{32 + i * 152}" y="40" width="136" height="72" rx="6" class="mk"/><rect x="{32 + i * 152}" y="40" width="136" height="72" rx="6" class="{k}"/>'
    f'<circle cx="{46 + i * 152}" cy="54" r="9" class="stepno"/><text x="{46 + i * 152}" y="58" text-anchor="middle" class="stepno-t">{i + 1}</text>'
    f'<text x="{100 + i * 152}" y="78" text-anchor="middle" class="n-name">{a}</text><text x="{100 + i * 152}" y="96" text-anchor="middle" class="n-sub">{b}</text>'
    + (f'<path d="M{170 + i * 152} 76 H{182 + i * 152}" class="ar" marker-end="url(#lp-a)"/>' if i < 5 else "")
    for i, (a, b, k) in enumerate([("before_call", "compaction, drops", "nb"), ("render", "folding, cards", "nb-focal"),
                                   ("model call", "metered, cached", "nb"), ("after_call", "logs, strip", "nb"),
                                   ("tools run", "real side effects", "nb"), ("on_tool_result", "previews, guard", "nb-check")])) + """
<path d="M852 114 V140 H100 V116" class="ar-dash" marker-end="url(#lp-a)"/>
<text x="476" y="134" text-anchor="middle" class="a-lab">NEXT STEP</text>
<text x="32" y="172" class="lane-t">PER SESSION</text>
<rect x="32" y="182" width="288" height="36" rx="6" class="nb-check"/><text x="176" y="205" text-anchor="middle" class="n-name">on_session_start · recall, preamble</text>
<rect x="336" y="182" width="288" height="36" rx="6" class="nb"/><text x="480" y="205" text-anchor="middle" class="n-name">system_addendum · tools · static</text>
<rect x="640" y="182" width="288" height="36" rx="6" class="nb-check"/><text x="784" y="205" text-anchor="middle" class="n-name">on_session_end · autosave, index</text>
</svg>"""

SCALE_SVG = """<svg class="dg" viewBox="0 0 960 150" style="min-width:960px;max-width:1100px" role="img" aria-labelledby="sc-t sc-d">
<title id="sc-t">Model-normalised scale</title>
<desc id="sc-d">Each method is placed between the same model's floor (no memory, task window) and ceiling (no memory pressure, the model's own window). Recovery is the share of that gap the method closes; cost is a ratio to the ceiling's cost.</desc>
<defs><marker id="sc-a" markerWidth="8" markerHeight="6" refX="7" refY="3" orient="auto"><polygon points="0 0, 8 3, 0 6" class="hd-acc"/></marker></defs>
<rect width="960" height="150" class="bgp"/>
<line x1="120" y1="70" x2="840" y2="70" class="base-l"/>
<rect x="60" y="48" width="120" height="44" rx="6" class="chip-no"/><text x="120" y="68" text-anchor="middle" class="chip-no-t">Floor</text><text x="120" y="84" text-anchor="middle" class="n-sub">naive</text>
<rect x="780" y="48" width="120" height="44" rx="6" class="chip-ok"/><text x="840" y="68" text-anchor="middle" class="chip-ok-t">Ceiling</text><text x="840" y="84" text-anchor="middle" class="n-sub">naive@native</text>
<circle cx="610" cy="70" r="9" class="stepno"/><text x="610" y="40" text-anchor="middle" class="t-acc">method score</text>
<path d="M182 112 H606" class="ar-acc" marker-end="url(#sc-a)"/><text x="394" y="130" text-anchor="middle" class="a-lab-acc">RECOVERY = (SCORE − FLOOR) ÷ (CEILING − FLOOR)</text>
<text x="480" y="22" text-anchor="middle" class="lane-s">defined only when the ceiling beats the floor by ≥ 0.15 · ≥ 0.5 on both models = model-robust</text>
</svg>"""

PIPE_SVG = flow_svg("pipe", "Logging and analysis pipeline",
                    "Each run writes one JSON row with usage, cost, events and per-method records; analyze turns rows into tables; fill_report writes them into the result documents.",
                    [("Run", "claude -p per call, metered", "nb"), ("Row (JSONL)", "score, tokens, cache, cost, events, records", "nb-focal"),
                     ("analyze", "--summary --robust --metrics --reprice", "nb"), ("fill_report", "tables written into docs", "nb-check")])


# ------------------------------------------------------------------ page
def a(fam):
    return agg(cell(fam[0], "cc-haiku")), agg(cell(fam[1], "cc-sonnet"))


v2h, v2s = a(("automem:ingest=0.1", "automem:ingest=0.1#aux=cc-haiku"))
v1h, v1s = a(("automem", "automem#aux=cc-haiku"))
v2x = agg(cell("automem:ingest=0.1,compact=sjc#aux=cc-haiku", "cc-sonnet"))
POINTS = []
for g_, label_, sub_, hs_, ss_ in ROWS:
    for model_, spec_ in (("haiku", hs_), ("sonnet", ss_)):
        if not spec_:
            continue
        a_ = agg(cell(spec_, "cc-" + model_))
        if a_:
            POINTS.append(dict(model=model_, group=g_, label=label_, cost=a_["cost"], score=a_["score"], n=a_["n"],
                               ceiling=agg(cell("naive@native", "cc-" + model_))["score"]))
MIX = []
for label_, spec_ in (("Unoptimised ceiling (no cache)", "naive@native"), ("Full context, cached (overflows)", "full"),
                      ("AutoMemory v2", "automem:ingest=0.1#aux=cc-haiku"), ("AutoMemory v2 strong", "automem:ingest=0.1,compact=sjc#aux=cc-haiku"),
                      ("ReFold", "refold"), ("CADOC", "cadoc"), ("SelfCompact", "selfcompact"), ("Strands defaults", "strands"),
                      ("AKV drop, blocks of 8", "akv_drop:keep=8,block=8"), ("Observation masking", "obs_mask"), ("AKV drop, every turn", "akv_drop")):
    v_ = D.get(spec_, {}).get("cc-sonnet", {}).get("research_corpus")
    if v_:
        MIX.append((label_, v_["read"], v_["write"], v_["unc"], v_["cost"]))

NAV = """
<nav class="sidenav" id="sidenav" aria-label="Sections">
  <div class="sn-top">
    <button type="button" class="sn-toggle" aria-expanded="false" aria-controls="sn-list">%(list)sContents</button>
    <a class="sn-title" href="#top">Efficient Agent Memory</a>
    <div class="sn-now"><span class="sn-now-k">Now reading</span><span class="sn-cur-part"></span><span class="sn-current">Overview</span></div>
    <div class="sn-progress" aria-hidden="true"><span></span></div>
  </div>
  <ol class="sn-list" id="sn-list">
    <li class="sn-part sn-p0" data-name="Overview"><a href="#top">%(home)s<span>Overview</span></a></li>
    <li class="sn-part sn-p1" data-name="01 Objective and scope"><a href="#obj">%(target)s<span><b>01</b> Objective and scope</span></a>
      <ol>
        <li><a href="#obj-summary">%(file)s<span><i>1.1</i> Executive summary</span></a></li>
        <li><a href="#obj-problem">%(info)s<span><i>1.2</i> The problem</span></a></li>
        <li><a href="#obj-pain">%(alert)s<span><i>1.3</i> Pain points</span></a></li>
        <li><a href="#obj-scope">%(box)s<span><i>1.4</i> Scope</span></a></li>
        <li><a href="#obj-measure">%(scale)s<span><i>1.5</i> How it is measured</span></a></li>
      </ol></li>
    <li class="sn-part sn-p2" data-name="02 Harness and experiments"><a href="#hx">%(wrench)s<span><b>02</b> Harness and experiments</span></a>
      <ol>
        <li><a href="#hx-loop">%(steps)s<span><i>2.1</i> The agent loop</span></a></li>
        <li><a href="#hx-tasks">%(list)s<span><i>2.2</i> The four long tasks</span></a></li>
        <li><a href="#hx-runs">%(route)s<span><i>2.3</i> Experiments run</span></a></li>
        <li><a href="#hx-log">%(audit)s<span><i>2.4</i> Logging and analysis</span></a></li>
        <li><a href="#hx-fix">%(shield)s<span><i>2.5</i> Harness corrections</span></a></li>
      </ol></li>
    <li class="sn-part sn-p3" data-name="03 Methods"><a href="#mt">%(layers)s<span><b>03</b> Methods</span></a>
      <ol>
        <li><a href="#mt-map">%(grid)s<span><i>3.1</i> Where each method acts</span></a></li>
        <li><a href="#mt-auto">%(steps)s<span><i>3.2</i> AutoMemory step by step</span></a></li>
        <li><a href="#mt-cards">%(sliders)s<span><i>3.3</i> Method by method</span></a></li>
      </ol></li>
    <li class="sn-part sn-p4" data-name="04 Effectiveness now"><a href="#ef">%(gauge)s<span><b>04</b> Effectiveness now</span></a>
      <ol>
        <li><a href="#ef-board">%(chart)s<span><i>4.1</i> Scoreboard</span></a></li>
        <li><a href="#ef-heat">%(grid)s<span><i>4.2</i> Per task</span></a></li>
        <li><a href="#ef-v2">%(trend)s<span><i>4.3</i> AutoMemory v1 → v3</span></a></li>
        <li><a href="#ef-swe">%(cpu)s<span><i>4.4</i> Real repositories</span></a></li>
        <li><a href="#ef-lessons">%(bulb)s<span><i>4.5</i> What works</span></a></li>
        <li><a href="#ef-pick">%(route)s<span><i>4.6</i> Which setting?</span></a></li>
        <li><a href="#ef-next">%(flag)s<span><i>4.7</i> Open questions</span></a></li>
      </ol></li>
    <li class="sn-sep" role="presentation"></li>
    <li class="sn-part sn-p5" data-name="Conclusion"><a href="#conclusion">%(check)s<span>Conclusion</span></a></li>
    <li class="sn-part sn-p5" data-name="References"><a href="#references">%(book)s<span>References</span></a></li>
  </ol>
</nav>"""
ICONS = {k: ic(v, "ic sn-ic") if k in ("home", "target", "wrench", "layers", "gauge", "check", "book") else ic(v)
         for k, v in dict(list="list", home="home", target="target", file="file", info="info", alert="alert", box="box",
                          scale="scale", wrench="wrench", steps="steps", route="route", audit="audit", shield="shield",
                          layers="layers", grid="grid", sliders="sliders", gauge="gauge", chart="chart", trend="trend",
                          bulb="bulb", flag="flag", check="check", book="book", cpu="cpu").items()}
ICONS["list"] = ic("list")

PAGE = f"""<title>Efficient Agent Memory</title>
<meta name="claude:viewport-fit-sides" content="cover">
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link rel="stylesheet" href="https://fonts.googleapis.com/css2?family=IBM+Plex+Mono:wght@400;500&family=IBM+Plex+Sans+Condensed:wght@500;600&family=IBM+Plex+Sans:ital,wght@0,400;0,500;0,600;1,400&family=Newsreader:ital,opsz,wght@0,6..72,500;0,6..72,600;1,6..72,400;1,6..72,500&display=swap">
<style>{REF_CSS}{EXTRA_CSS}{X.CSS}</style>
{SPRITE}
<div class="readbar" aria-hidden="true"><span></span></div>
<div class="layout">
{NAV % ICONS}
<main>
  <header id="top">
    <div class="hero">
      <p class="eyebrow">Research brief · November 2026</p>
      <h1>Efficient Agent Memory</h1>
      <p class="dek">What this repository studies, how each memory and token-saving method works, and how well each one works today on four long agent tasks, measured on Claude Haiku and Sonnet.</p>
      <p class="hero-meta"><span>≈ 2,790 benchmark runs</span><span>27 methods and variants</span><span>Claude Code CLI route</span><span>SWE-bench Verified: 100 Django issues</span><span>Evidence to 6 Nov 2026</span></p>
    </div>
    <div class="brief">
      <span class="k">{ic("brief")}Key points</span>
      <ul class="plain">
        <li><strong>The objective</strong> is the fewest tokens and dollars per solved task, at full accuracy, with a slim working context, for long-running agents such as coding agents.</li>
        <li><strong>Fewer tokens is not fewer dollars.</strong> Re-sent history is cheap only while it stays byte-identical in the prompt cache; methods that edit history every step often cost more than they save.</li>
        <li><strong>Automatic beats model-managed.</strong> Steps the harness applies by itself (previews at ingestion, recall, compaction at a fixed trigger) work on both models; methods that need the model to manage its own memory fail on the weaker one.</li>
        <li><strong>AutoMemory v2 is the current best:</strong> Haiku {v2h["score"]:.2f} mean score at {v2h["cost"]:.0f}% of the unoptimised cost; Sonnet {v2s["score"]:.2f} at {v2s["cost"]:.0f}%. For strong models, v2 + SJC pruning solved {v2x["solved"]}/{v2x["runs"]} Sonnet runs at {v2x["cost"]:.0f}%. No newer method beats it across the board.</li>
        <li><strong>On real repositories</strong> (100 SWE-bench Verified Django issues), AutoMemory without the note workspace is the cheapest memory layer under a tight window (Sonnet: 86/100 at 73% of the ceiling's cost at 16K); with NVIDIA's handoff recap it reaches the ceiling's accuracy (81 and 88 of 100 against 82 and 88) for 6–16 points more cost. With the workspace, independent issues cost more than they save.</li>
      </ul>
      <p class="rec"><strong>Recommendation:</strong> use <code>automem_v2</code> as the default memory layer; for a strong agent use <code>automem_v2_strong</code> with a cheaper model writing summaries and judging them. For independent tasks such as coding issues, drop the workspace: <code>automem_v2_lean</code>, or <code>automem_v2_lean_handoff</code> when accuracy comes first. See the chooser (<a href="#ef-pick">4.6</a>).</p>
    </div>
    {figure(OVERVIEW_SVG, "Every step re-sends the conversation. The four places a method can act decide whether it keeps the prompt cache.")}
    <details class="glossary">
      <summary>{ic("info")}Glossary</summary>
      <dl>
        <dt>Context window</dt><dd>The most tokens one request may hold. The tasks emulate a small window (16K–48K) to create memory pressure.</dd>
        <dt>Prompt cache</dt><dd>Re-sent prefix tokens billed at 0.05–0.1× the input price, while the prefix is unchanged. Changing earlier history re-bills from that point as cache writes (2× on the Claude Code CLI, 1.25× on Bedrock).</dd>
        <dt>Compaction</dt><dd>Replacing part of the history with a summary when the context grows too large.</dd>
        <dt>Ingestion</dt><dd>The moment a tool result enters the history. Shrinking it here never invalidates the cache.</dd>
        <dt>Session</dt><dd>One conversation. Multi-session tasks start each session fresh; only the memory method's own store carries over.</dd>
        <dt>Floor / ceiling</dt><dd>The same model with no memory method in the task's window, and with its own large window. Every result is placed between them.</dd>
        <dt>Recovery</dt><dd>The share of the floor-to-ceiling gap a method closes. 1.0 = as good as the ceiling.</dd>
        <dt>Solved</dt><dd>A run in which every session's answer was fully correct.</dd>
      </dl>
    </details>
    <nav class="toc" aria-label="Contents">
      <div><span class="part">{ic("target")}Part 1</span><a class="ttl" href="#obj">Objective and scope</a><span class="gist">The problem, the pain points, what is in and out</span>
        <ol><li><span>1.1</span><a href="#obj-summary">Executive summary</a></li><li><span>1.2</span><a href="#obj-problem">The problem</a></li><li><span>1.3</span><a href="#obj-pain">Pain points</a></li><li><span>1.4</span><a href="#obj-scope">Scope</a></li><li><span>1.5</span><a href="#obj-measure">How it is measured</a></li></ol></div>
      <div><span class="part">{ic("wrench")}Part 2</span><a class="ttl" href="#hx">Harness and experiments</a><span class="gist">The loop, the tasks, the runs and the logs</span>
        <ol><li><span>2.1</span><a href="#hx-loop">The agent loop</a></li><li><span>2.2</span><a href="#hx-tasks">The four long tasks</a></li><li><span>2.3</span><a href="#hx-runs">Experiments run</a></li><li><span>2.4</span><a href="#hx-log">Logging and analysis</a></li><li><span>2.5</span><a href="#hx-fix">Harness corrections</a></li></ol></div>
      <div><span class="part">{ic("layers")}Part 3</span><a class="ttl" href="#mt">Methods</a><span class="gist">{len(M)} methods: mechanism, evidence, verdict</span>
        <ol><li><span>3.1</span><a href="#mt-map">Where each method acts</a></li><li><span>3.2</span><a href="#mt-auto">AutoMemory step by step</a></li><li><span>3.3</span><a href="#mt-cards">Method by method</a></li></ol></div>
      <div><span class="part">{ic("gauge")}Part 4</span><a class="ttl" href="#ef">Effectiveness now</a><span class="gist">Scores, costs and what they mean</span>
        <ol><li><span>4.1</span><a href="#ef-board">Scoreboard</a></li><li><span>4.2</span><a href="#ef-heat">Per task</a></li><li><span>4.3</span><a href="#ef-v2">AutoMemory v1 → v3</a></li><li><span>4.4</span><a href="#ef-swe">Real repositories</a></li><li><span>4.5</span><a href="#ef-lessons">What works</a></li><li><span>4.6</span><a href="#ef-pick">Which setting?</a></li><li><span>4.7</span><a href="#ef-next">Open questions</a></li></ol></div>
    </nav>
  </header>

  <!-- =================== PART 1 =================== -->
  <div class="banner" id="obj" data-pn="01">
    <span class="tag">{ic("target")}Part 1 · Why</span>
    <h2>Objective and scope</h2>
    <div class="meta"><span>Repository: Efficient-Agent-Memory</span><span>docs/problem_statement.md</span></div>
  </div>

  <section id="obj-summary" aria-labelledby="h-obj-sum">
    <h3 id="h-obj-sum">{ic("file", "ic hic")}<span class="no">1.1</span>Executive summary</h3>
    <dl class="summary">
      <dt>Objective</dt><dd>Save tokens and cost with a slim, effective context, without losing task accuracy, for long-running LLM agents.</dd>
      <dt>Approach</dt><dd>Implement published memory and context methods faithfully (official code or prompts where they exist), measure each on the same long tasks and models, then combine the winners into one memory layer (AutoMemory).</dd>
      <dt>Route</dt><dd>Claude Code CLI (Haiku, Sonnet; Opus in phase 1), with Bedrock-ready code paths. Bedrock validation is blocked on credentials.</dd>
      <dt>Deliverables</dt><dd>A benchmark harness, {len(M)} method implementations, AutoMemory v1/v2 as a bench technique, a Python library and an MCP server, and result reports for every phase.</dd>
      <dt>Bottom line</dt><dd class="bottom">AutoMemory v2 matches the unoptimised ceiling's accuracy on both models at {min(v2h["cost"], v2s["cost"]):.0f}–{max(v2h["cost"], v2s["cost"]):.0f}% of its cost.</dd>
    </dl>
  </section>

  <section id="obj-problem" aria-labelledby="h-obj-prob">
    <h3 id="h-obj-prob">{ic("info", "ic hic")}<span class="no">1.2</span>The problem: two problems, one budget</h3>
    <p>A coding agent has no memory of its own. On every step the harness sends the whole conversation again. That makes the context window the agent's working memory, and makes cost grow faster than the work.</p>
    <div class="stats">
      <div class="stat"><span class="num">N − 1</span><span class="lbl">earlier steps re-sent on step N</span></div>
      <div class="stat"><span class="num">0.05–0.1×</span><span class="lbl">price of a cached re-sent token</span></div>
      <div class="stat"><span class="num">2×</span><span class="lbl">price of re-writing history on the CLI (1.25× on Bedrock)</span></div>
      <div class="stat"><span class="num">+1%</span><span class="lbl">cost change of a "60–90% fewer tokens" shell tool in an independent test</span></div>
    </div>
    <div class="duo">
      <div class="good"><span class="k">Within a session: context</span><ul class="plain">
        <li>What should this request contain?</li><li>How small can it be without losing what matters?</li><li>Called context engineering, compaction, token optimisation.</li></ul></div>
      <div class="good"><span class="k">Across sessions: memory</span><ul class="plain">
        <li>What should survive until the next session?</li><li>How does it come back at the right moment?</li><li>Called agent memory, long-term memory.</li></ul></div>
    </div>
    <p class="implication">{ic("bulb")}<strong>Measure</strong>cost per solved task at full accuracy, with real cache prices. Tokens removed is the wrong target.</p>
    <h4>Try it: why fewer tokens can cost more</h4>
    <p class="lead-in">Pick a strategy and press Play. Each bar is one step's prompt: green is read from the cache, red is re-written to it. Switch the price route to see how Bedrock's cheaper cache writes change the picture.</p>
    {X.simulator()}
  </section>

  <section id="obj-pain" aria-labelledby="h-obj-pain">
    <h3 id="h-obj-pain">{ic("alert", "ic hic")}<span class="no">1.3</span>The pain points of everyday coding-agent users</h3>
    <div class="tbl-wrap"><table>
      <thead><tr><th>Pain point</th><th>Seen in these runs</th><th>Addressed by</th></tr></thead>
      <tbody>
        <tr><th>Tool output floods the context<span class="sub">test logs, grep results, file dumps</span></th><td>Overflow was the main failure on every long task; one pytest run is 3K+ tokens.</td><td>Previews and guard at ingestion (AutoMemory v2, Strands); ReFold deduplication.</td></tr>
        <tr><th>Context rot<span class="sub">quality drops before the window is full</span></th><td>Indirectly: a smaller peak at equal accuracy is cheaper on every later step.</td><td>Folding and self-compaction keep Sonnet's peak at 15–18K vs 72K.</td></tr>
        <tr><th>Compaction amnesia<span class="sub">the agent forgets decisions after auto-compact</span></th><td>Haiku re-opened old files instead of its notes; replies degenerated without recent steps.</td><td>Keep the last 2 steps, re-inject notes, cheap summariser (AutoMemory).</td></tr>
        <tr><th>Session amnesia<span class="sub">tomorrow's session re-explores from scratch</span></th><td>Multi-session tasks fail without carried memory.</td><td>Notes with automatic recall and autosave; compared with official memory systems and raw-history RAG.</td></tr>
        <tr><th>Usage caps and surprise bills</th><td>These experiments hit the CLI's session limit.</td><td>Cost per solved task as the headline metric; harness waits for the reset.</td></tr>
        <tr><th>Token savers that save no money</th><td>AKV drop: 93% vs 22% of the ceiling's cost for the same idea, per-turn vs batched.</td><td>Cache-aware pricing in every comparison; batched edits.</td></tr>
        <tr><th>Opacity<span class="sub">what was dropped, and why</span></th><td>—</td><td>Every offload, fold and compaction is logged; originals stay retrievable.</td></tr>
      </tbody></table></div>
  </section>

  <section id="obj-scope" aria-labelledby="h-obj-scope">
    <h3 id="h-obj-scope">{ic("box", "ic hic")}<span class="no">1.4</span>Scope</h3>
    <div class="duo">
      <div class="good"><span class="k">In scope</span><ul class="plain">
        <li>Within-session context methods: compaction, masking, folding, offload, deduplication, cache-aware batching.</li>
        <li>Cross-session memory: note workspaces, official memory systems (MemoryOS, LightMem, Nemori), raw-history retrieval.</li>
        <li>Faithful ports: official code, prompts and defaults; every deviation documented in its module.</li>
        <li>Model-normalised evaluation on Haiku and Sonnet; cost with real cache prices.</li>
        <li>Shipping the result: bench technique, library, MCP server.</li></ul></div>
      <div class="bad"><span class="k">Out of scope or not yet done</span><ul class="plain">
        <li>Self-hosted models and KV-cache editing (the user runs on hosted APIs).</li>
        <li>Training-based methods (CORAL's RL variant, MemAgent's RL weights).</li>
        <li>Bedrock validation: code ready, blocked on credentials.</li>
        <li>Larger real-repository runs: 40 Django issues so far, one model route.</li>
        <li>Codex / OpenAI pricing: not yet re-priced.</li></ul></div>
    </div>
  </section>

  <section id="obj-measure" aria-labelledby="h-obj-meas">
    <h3 id="h-obj-meas">{ic("scale", "ic hic")}<span class="no">1.5</span>How effectiveness is measured</h3>
    <p>A stronger model scores higher with any method, so each method is measured against the same model's two anchors on the same task instances.</p>
    {figure(SCALE_SVG, "The same scale is used for every method, task and model (docs/methodology.md §6).")}
    <dl class="spec">
      <dt>Score</dt><dd>Task accuracy in [0, 1], exact-match checks per session; a regression halves the repo_debug score.</dd>
      <dt>Recovery</dt><dd>(score − floor) ÷ (ceiling − floor); defined when the ceiling beats the floor by at least 0.15.</dd>
      <dt>Cost</dt><dd>Median USD per run as reported by the route, as a percentage of the ceiling's median cost.</dd>
      <dt>Tokens</dt><dd>Prompt tokens (cached + uncached + written) and peak context per run.</dd>
      <dt>Effort</dt><dd>Agent rounds, tool calls, wall-clock minutes, side-call cost (summaries, judges, memory systems).</dd>
      <dt>Verdict</dt><dd>Model-robust = recovery ≥ 0.5 on both models; model-dependent = one model only; not effective = neither.</dd>
    </dl>
  </section>

  <!-- =================== PART 2 =================== -->
  <div class="banner" id="hx" data-pn="02">
    <span class="tag">{ic("wrench")}Part 2 · How it was tested</span>
    <h2>Harness and experiments</h2>
    <div class="meta"><span>eam/agent/loop.py</span><span>eam/bench/</span><span>docs/methodology.md</span></div>
  </div>

  <section id="hx-loop" aria-labelledby="h-hx-loop">
    <h3 id="h-hx-loop">{ic("steps", "ic hic")}<span class="no">2.1</span>The agent loop and its hooks</h3>
    <p>One minimal ReAct loop runs every method. A technique is a set of optional hooks, so the only difference between two runs is the technique under test. Combinations are pipelines of techniques.</p>
    {figure(LOOP_SVG, "Hook order per step. Editing at on_tool_result is cache-safe; editing earlier messages at before_call or render rewrites the cached prefix.")}
    <ul class="plain">
      <li><strong>Same rules for every method:</strong> an emulated context window (a request over it ends the session as an overflow), a context gauge in the newest message, at most 2 nudges after a malformed reply, a per-step output budget with recoverable offload.</li>
      <li><strong>Routes:</strong> Claude Code CLI (<code>claude -p</code>, stream-json, text tool protocol), Bedrock Converse, LiteLLM, Bedrock OpenAI-compatible endpoints, and a mock backend for offline tests.</li>
      <li><strong>Tests:</strong> 209 offline tests, including a mock run of every method on every long task.</li>
    </ul>
  </section>

  <section id="hx-tasks" aria-labelledby="h-hx-tasks">
    <h3 id="h-hx-tasks">{ic("list", "ic hic")}<span class="no">2.2</span>The four long tasks</h3>
    <div class="tbl-wrap"><table>
      <thead><tr><th>Task</th><th>Sessions</th><th>Window</th><th>What makes it hard</th><th>Scoring</th></tr></thead>
      <tbody>
        <tr><th>research_corpus<span class="sub">BrowseComp-Plus style</span></th><td>1</td><td>40K</td><td>130 documents (BM25 search), 8 multi-hop questions revealed one by one, the last a sum of earlier answers.</td><td>Exact answers per question</td></tr>
        <tr><th>ops_stream<span class="sub">stock keeping</span></th><td>10</td><td>32K</td><td>10 days × 3 event files; later days amend or void earlier events.</td><td>Exact state per day</td></tr>
        <tr><th>ledger_audit<span class="sub">data larger than the window</span></th><td>3</td><td>48K</td><td>16 ledgers + 8 refund files (≈ 113K tokens); each round builds on the last.</td><td>16 exact checks</td></tr>
        <tr><th>repo_debug<span class="sub">real pytest</span></th><td>2</td><td>16K</td><td>A generated 50K-token Python library with 8 bugs reachable only through end-to-end scenarios.</td><td>Tests fixed, halved on regression</td></tr>
      </tbody></table></div>
    <p class="note">Earlier phase-1 tasks (chain_hunt, the first ledger_audit) are reported in docs/results/2026-10-22-*.md.</p>
  </section>

  <section id="hx-runs" aria-labelledby="h-hx-runs">
    <h3 id="h-hx-runs">{ic("route", "ic hic")}<span class="no">2.3</span>Experiments run</h3>
    <div class="tbl-wrap"><table>
      <thead><tr><th>Phase</th><th>Question</th><th>Models · seeds</th><th>Result</th><th>Report</th></tr></thead>
      <tbody>
        <tr><th>1 · Single methods</th><td>Does each published method work alone?</td><td>Haiku, Sonnet, Opus · 2–5</td><td>No single method solves the multi-session tasks; workspace + ReSum does.</td><td>2026-10-22-*.md</td></tr>
        <tr><th>2 · Long horizon</th><td>Is the effect model-independent?</td><td>Haiku, Sonnet · 2–4</td><td>Model-normalised protocol; erratum after two harness bugs.</td><td>2026-10-23-long-horizon</td></tr>
        <tr><th>3 · AutoMemory v1</th><td>Does the combination beat its parts? Official memory systems?</td><td>Haiku 4 · Sonnet 2–3</td><td>Model-robust on all four tasks; memory systems 0.2–0.5 lower.</td><td>2026-10-24-automem-evaluation</td></tr>
        <tr><th>4 · Eight new methods</th><td>Do the Sep–Nov 2026 methods help?</td><td>Haiku 4 · Sonnet 2 · 258 runs</td><td>None beats AutoMemory across the board.</td><td>2026-11-04-new-methods</td></tr>
        <tr><th>5 · AutoMemory v2</th><td>Previews and folding as switches?</td><td>Haiku 4 · Sonnet 2 · 72 runs</td><td>Previews become the default.</td><td>2026-11-04-automemory-v2</td></tr>
        <tr><th>6 · v3 ablation</th><td>OpenClaw / SJC as the compaction step?</td><td>Haiku 4 · Sonnet 2 · 72 runs</td><td>Not adopted; SJC an option for strong models.</td><td>2026-11-04-automemory-v3-ablation</td></tr>
        <tr><th>7 · More Sonnet seeds</th><td>Confirm or rule out compact=sjc</td><td>Sonnet 4 · 34 runs</td><td>SJC 16/16 solved; adopted for strong models.</td><td>2026-11-04-automemory-v3-ablation</td></tr>
        <tr><th>8 · SWE-bench Verified</th><td>Does it hold on real repositories?</td><td>Haiku, Sonnet · 40 issues · 160 runs</td><td>Lean (no workspace) best; workspace is overhead on independent issues. Superseded by 9 (grading covered 63% of the tests).</td><td>2026-11-05-swe-bench-workdays</td></tr>
        <tr><th>9 · NVIDIA handoff, 100 issues</th><td>Does EoCC's recap beat ReSum? Do the SWE results hold on 100 issues with faithful grading?</td><td>Haiku, Sonnet · 100 issues · 400 SWE + 80 synthetic runs</td><td>Handoff reaches the ceiling at 16K for more cost; lean (ReSum) cheapest; EoCC alone overflows.</td><td>2026-11-06-handoff-and-swe-100</td></tr>
      </tbody></table></div>
    <h4>Timeline</h4>
    {X.timeline()}
    <div class="stats">
      <div class="stat"><span class="num">≈ 2,790</span><span class="lbl">CLI benchmark runs recorded, pilots included</span></div>
      <div class="stat"><span class="num">≈ $1,140</span><span class="lbl">total list-price spend (Sonnet ≈ $870, Haiku ≈ $235, Opus ≈ $34)</span></div>
      <div class="stat"><span class="num">1,515</span><span class="lbl">arXiv papers screened in the Sep–Nov 2026 scan</span></div>
      <div class="stat"><span class="num">{len(M)}</span><span class="lbl">methods implemented and documented here</span></div>
    </div>
  </section>

  <section id="hx-log" aria-labelledby="h-hx-log">
    <h3 id="h-hx-log">{ic("audit", "ic hic")}<span class="no">2.4</span>Logging and analysis</h3>
    {figure(PIPE_SVG, "Every number in the result documents is generated from the row files by the same analysis code.")}
    <div class="cards">
      <div><strong>Per call</strong><p>Tag (main, aux:summary, judge, probe), uncached / cache-read / cache-write / output tokens, latency, reported cost.</p></div>
      <div><strong>Per run</strong><p>Score per session, success, steps, tool calls, peak context, cache-hit rate, cost by tag, wall time, overflow, history rewrites.</p></div>
      <div><strong>Per method</strong><p>Records: ReFold labels and folds, SJC verdicts per entry, SelfCompact probe answers, CADOC commits, CORAL tool use.</p></div>
      <div><strong>Events</strong><p>Compactions, offloads, previews, drops, nudges, retries, overflows, with the step they happened at.</p></div>
      <div><strong>Transcripts</strong><p>Opt-in (EAM_TRANSCRIPTS): every message and call of every session, for failure analysis.</p></div>
      <div><strong>Analysis</strong><p><code>analyze --summary --robust --metrics --reprice</code>; medians (costs are heavy-tailed); superseded errors dropped; Bedrock re-pricing.</p></div>
    </div>
  </section>

  <section id="hx-fix" aria-labelledby="h-hx-fix">
    <h3 id="h-hx-fix">{ic("shield", "ic hic")}<span class="no">2.5</span>Harness corrections that changed conclusions</h3>
    <p>Measurement bugs were found by checking surprising results against the raw usage. Affected rows were moved aside and rerun; the reports carry errata.</p>
    <div class="tbl-wrap"><table>
      <thead><tr><th>Bug</th><th>Effect</th><th>Fix</th></tr></thead>
      <tbody>
        <tr><th>Retried CLI calls</th><td>A retry summed both attempts' prompt tokens into the context size: false overflows.</td><td>Billing keeps the sum; size checks use the final attempt.</td></tr>
        <tr><th>Internal continuation turns</th><td>Replies over the output cap were continued internally; a 2.6K request read as 12.9K.</td><td>32K cap; size = (prompt − output) ÷ turns. Every Haiku cell rerun.</td></tr>
        <tr><th>Prompt-size predictor</th><td>A ratio fit inflated by fixed overhead rejected valid requests.</td><td>Affine fit (overhead + slope).</td></tr>
        <tr><th>Empty answers accepted</th><td>Sonnet could skip questions in research_corpus.</td><td>submit_answer rejects empty answers; rows rerun.</td></tr>
        <tr><th>Stale bytecode</th><td>Same-size edits within a second were shadowed by cached .pyc in repo_debug.</td><td>pytest -B, caches cleared.</td></tr>
        <tr><th>Rendered copies</th><td>Methods that render a copy of the history missed the context gauge.</td><td>The loop adds the gauge to the request sent; rewrites counted on it.</td></tr>
      </tbody></table></div>
  </section>

  <!-- =================== PART 3 =================== -->
  <div class="banner" id="mt" data-pn="03">
    <span class="tag">{ic("layers")}Part 3 · What was tried</span>
    <h2>Methods</h2>
    <div class="meta"><span>eam/techniques/</span><span>docs/new_methods.md</span><span>third_party/NOTICE.md</span></div>
  </div>

  <section id="mt-map" aria-labelledby="h-mt-map">
    <h3 id="h-mt-map">{ic("grid", "ic hic")}<span class="no">3.1</span>Where each method acts</h3>
    <p>The hook a method uses predicts its cost behaviour; who drives it (the harness or the model) predicts whether it works on a weaker model.</p>
    {figure(X.method_map(), "Colour: violet = AutoMemory component, green = works on both models, amber = mixed or model-dependent, red = fails on these tasks. Select a chip to open its method card. The harness-driven, cache-safe methods (top row, left) are the ones that held up on both models.")}
    <div class="tbl-wrap"><table>
      <thead><tr><th>Method</th><th>Developer</th><th>Acts at</th><th>Driven by</th><th>Status</th></tr></thead>
      <tbody>{"".join(f'<tr><th>{E(m["name"])}</th><td>{E(m["dev"])}</td><td>{E(m["acts"])}</td><td>{E(m["driver"])}</td><td><span class="str {STR[m["ev"]][0]}">{STR[m["ev"]][1]}</span></td></tr>' for m in M)}</tbody>
    </table></div>
  </section>

  <section id="mt-auto" aria-labelledby="h-mt-auto">
    <h3 id="h-mt-auto">{ic("steps", "ic hic")}<span class="no">3.2</span>AutoMemory v2, step by step</h3>
    <p class="lead-in">Press Play, use the arrow keys, or pick a step. Each step names its hook, its effect on the prompt cache, and the measurement behind it.</p>
    {X.automem_stepper()}
  </section>

  <section id="mt-cards" aria-labelledby="h-mt-cards">
    <h3 id="h-mt-cards">{ic("sliders", "ic hic")}<span class="no">3.3</span>Method by method</h3>
    <p class="lead-in">Select a method for its mechanism, how it is implemented here, the evidence, and its measured results on the four long tasks.</p>
    {method_tabs()}
    <p class="note">Score = mean task accuracy; recovery = share of the floor-to-ceiling gap closed; cost and peak = median as a percentage of the unoptimised ceiling on the same task. Within-session methods run with the same note workspace on multi-session tasks.</p>
  </section>

  <!-- =================== PART 4 =================== -->
  <div class="banner" id="ef" data-pn="04">
    <span class="tag">{ic("gauge")}Part 4 · Where things stand</span>
    <h2>Effectiveness now</h2>
    <div class="meta"><span>docs/results/</span><span>Haiku 4 seeds · Sonnet 2–4 seeds</span><span>Differences under ~0.1 score or ~15 points cost are within noise</span></div>
  </div>

  <section id="ef-board" aria-labelledby="h-ef-board">
    <h3 id="h-ef-board">{ic("chart", "ic hic")}<span class="no">4.1</span>Scoreboard</h3>
    <h4>Accuracy against cost</h4>
    <p class="lead-in">Up is more accurate, left is cheaper. The green zone is the goal: the ceiling's accuracy at below its cost. Switch models to compare.</p>
    {X.scatter(POINTS)}
    <h4>All methods, both models</h4>
    <p class="lead-in">Mean score over the four long tasks; the black tick is the ceiling's score. In brackets, mean cost as a percentage of the ceiling (green below 90%, red above 110%) and, where a method ran on fewer tasks, how many of the four. Hover a bar for recovery, peak and solved runs.</p>
    <div class="legend"><span><i style="background:var(--muted);opacity:.45"></i>Reference</span><span><i style="background:var(--accent)"></i>Published (phase 1)</span><span><i style="background:var(--amber)"></i>Sep–Nov 2026 scan</span><span><i style="background:var(--violet)"></i>AutoMemory</span></div>
    {scoreboard()}
  </section>

  <section id="ef-heat" aria-labelledby="h-ef-heat">
    <h3 id="h-ef-heat">{ic("grid", "ic hic")}<span class="no">4.2</span>Per task and model</h3>
    <p class="lead-in">Each cell: mean score (bold) and median cost as a percentage of the ceiling. Colour follows the score.</p>
    <div class="legend"><span><i class="hl-0"></i>&lt; 0.40</span><span><i class="hl-1"></i>0.40–0.69</span><span><i class="hl-2"></i>0.70–0.84</span><span><i class="hl-3"></i>0.85–0.96</span><span><i class="hl-4"></i>≥ 0.97</span></div>
    {heatmap()}
  </section>

  <section id="ef-v2" aria-labelledby="h-ef-v2">
    <h3 id="h-ef-v2">{ic("trend", "ic hic")}<span class="no">4.3</span>AutoMemory v1 → v2 → v3</h3>
    <div class="stats">
      <div class="stat"><span class="num">{v2h["score"]:.2f}</span><span class="lbl">Haiku v2 mean score (v1 {v1h["score"]:.2f}); {v2h["solved"]}/{v2h["runs"]} runs solved (v1 {v1h["solved"]}/{v1h["runs"]})</span></div>
      <div class="stat"><span class="num">{v2h["cost"]:.0f}%</span><span class="lbl">Haiku v2 mean cost vs the ceiling (v1 {v1h["cost"]:.0f}%)</span></div>
      <div class="stat"><span class="num">{v2s["score"]:.2f}</span><span class="lbl">Sonnet v2 mean score (v1 {v1s["score"]:.2f})</span></div>
      <div class="stat"><span class="num">{v2s["cost"]:.0f}%</span><span class="lbl">Sonnet v2 mean cost vs the ceiling (v1 {v1s["cost"]:.0f}%)</span></div>
    </div>
    <div class="tbl-wrap"><table>
      <thead><tr><th>Change</th><th>Haiku</th><th>Sonnet</th><th>Decision</th></tr></thead>
      <tbody>
        <tr><th>Compaction off (v1 ablation)</th><td>Score 0.04–0.62 on the multi-session tasks</td><td>—</td><td>Compaction is essential</td></tr>
        <tr><th>Recall + autosave off (v1 ablation)</th><td>0.50–0.89, more cost on repo_debug</td><td>—</td><td>Keep</td></tr>
        <tr><th>Cheaper summariser (v1)</th><td>—</td><td>Same accuracy, 20–40% cheaper</td><td>Default for strong models</td></tr>
        <tr><th>Previews at 10% of window (v2)</th><td>0.83 → 0.88; 7 → 11 of 16 solved</td><td>72% → 64% cost</td><td><strong>Adopted (automem_v2)</strong></td></tr>
        <tr><th>ReFold folding (v2 slim)</th><td>Smallest peak; ledger_audit worse</td><td>Peak 16K vs 29K; +10–16 points cost</td><td>Optional slim mode</td></tr>
        <tr><th>SJC / OpenClaw compaction (v3)</th><td>0.77–0.81, 114–124% cost</td><td>4 seeds: SJC 16/16 solved (v2 13/16), +3 to +5 points cost</td><td><strong>SJC adopted for strong models (automem_v2_strong)</strong>; OpenClaw not adopted</td></tr>
      </tbody></table></div>
  </section>

  <section id="ef-swe" aria-labelledby="h-ef-swe">
    <h3 id="h-ef-swe">{ic("cpu", "ic hic")}<span class="no">4.4</span>Real repositories: SWE-bench Verified workdays</h3>
    <p class="lead-in">100 real Django issues (4.0–5.0) in 20 workdays of 5 consecutive sessions, graded as SWE-bench grades them; 400 runs at the NVIDIA paper's 32K and 16K settings and the model's own window. The bar is the share of issues resolved; the black tick is the ceiling's. Cost is the total over the same workdays as a percentage of the ceiling's.</p>
    {X.swe_board(SWE)}
    <div class="duo">
      <div class="good"><span class="k">What held up on real code</span><ul class="plain">
        <li>Previews, guard and ReSum without the workspace (<code>automem_v2_lean</code>)<span class="ev">cheapest under a tight window: Sonnet 86/100 at 73% of the ceiling's cost (16K)</span></li>
        <li>NVIDIA's handoff recap in place of ReSum (<code>automem_v2_lean_handoff</code>)<span class="ev">16K: 81 / 88 resolved vs 76 / 86 with ReSum; ceiling 82 / 88; 6–16 points more cost</span></li>
        <li>Plain caching when the window does not bind<span class="ev">sessions peak at 16–21K; Haiku cached history at 32K: 77/100 at 62%</span></li></ul></div>
      <div class="bad"><span class="k">What did not</span><ul class="plain">
        <li>The paper's method alone (<code>eocc</code>)<span class="ev">no guard or previews: 15 Haiku sessions overflowed at 16K; 72 / 83 resolved</span></li>
        <li>Handoff recaps written by the cheaper model<span class="ev">Sonnet 86/100 at 90%: the extra cost is the agent's own replies (+45% output), not the recap</span></li>
        <li>The note workspace on independent issues (earlier run)<span class="ev">+50% tool calls; 118–158% of the ceiling's cost</span></li></ul></div>
    </div>
    <p class="note">The earlier 40-issue run graded only the tests whose ids name a test method (63% of the official tests); this board replaces it.</p>
    <p class="implication">{ic("bulb")}<strong>Rule</strong>keep the within-session half of AutoMemory always on; use the handoff recap when accuracy comes first under a tight window; switch the note workspace on only when later sessions build on earlier results.</p>
  </section>

  <section id="ef-lessons" aria-labelledby="h-ef-lessons">
    <h3 id="h-ef-lessons">{ic("bulb", "ic hic")}<span class="no">4.5</span>What works and what does not</h3>
    <div class="duo">
      <div class="good"><span class="k">Works on both models</span><ul class="plain">
        <li>Shrinking outputs at ingestion, with retrieval<span class="ev">v2: Haiku 11/16 solved vs 7/16 at the same cost</span></li>
        <li>Automatic recall and autosave of notes<span class="ev">beats MemoryOS, LightMem, Nemori by 0.2–0.5</span></li>
        <li>Compaction at a fixed trigger, keeping recent steps<span class="ev">without it: 0.04–0.62</span></li>
        <li>A cheaper model writing the summaries<span class="ev">Sonnet: same accuracy, 20–40% cheaper</span></li>
        <li>Batching any history edit<span class="ev">AKV: 93% → 22% cost at the same score</span></li></ul></div>
      <div class="bad"><span class="k">Fails or depends on the model</span><ul class="plain">
        <li>Editing history every step<span class="ev">masking 608%, AgentDiet 410% of full-context cost on Haiku</span></li>
        <li>Asking the model to manage its own memory<span class="ev">CORAL tools barely used; ReFold Haiku recovery 0.25</span></li>
        <li>Fixed small preview thresholds<span class="ev">Strands research_corpus 0.11 / 0.72</span></li>
        <li>Deleting old tool results over an API<span class="ev">AKV ledger_audit 0.00–0.17</span></li>
        <li>Self-probing on the agent model<span class="ev">SelfCompact 138–179% mean cost</span></li></ul></div>
    </div>
    <h4>Measured: where the prompt tokens go</h4>
    <p class="lead-in">The cache explains the cost column. Methods that edit history often turn cache reads (cheap) into cache writes (2× the input price).</p>
    {X.token_mix(MIX)}
    <div class="message">
      <p class="lead">Let the harness do the remembering, and keep the cached prefix stable.</p>
      <div class="tiles">
        <div><strong>Shrink at the door</strong><p>Decide what enters the history when it arrives; never rewrite it every step.</p></div>
        <div><strong>Reset rarely, keep the tail</strong><p>One summary at 75% of the window, plus the last two steps and the notes.</p></div>
        <div><strong>Remember outside the context</strong><p>Notes that come back by themselves beat engineered memory systems on agent work.</p></div>
      </div>
    </div>
  </section>

  <section id="ef-pick" aria-labelledby="h-ef-pick">
    <h3 id="h-ef-pick">{ic("route", "ic hic")}<span class="no">4.6</span>Which setting should I use?</h3>
    <p class="lead-in">Answer up to four questions; the flowchart follows your answers.</p>
    {X.chooser()}
  </section>

  <section id="ef-next" aria-labelledby="h-ef-next">
    <h3 id="h-ef-next">{ic("flag", "ic hic")}<span class="no">4.7</span>Open questions and next steps</h3>
    <div class="tbl-wrap"><table>
      <thead><tr><th>Item</th><th>Status</th><th>Cost</th><th>Why it matters</th></tr></thead>
      <tbody>
        <tr><th>A · Sonnet seeds for compact=sjc</th><td><span class="lvl lvl-low">Done: rule met</span></td><td>$36</td><td>SJC pruning is now the strong-model preset (automem_v2_strong).</td></tr>
        <tr><th>B · SWE-bench Verified workdays (Django)</th><td><span class="lvl lvl-low">Done</span></td><td>$56</td><td>automem_v2_lean is the setting for independent coding tasks.</td></tr>
        <tr><th>C · NVIDIA handoff and 100 SWE issues</th><td><span class="lvl lvl-low">Done</span></td><td>$221</td><td>automem_v2_lean_handoff for accuracy-first coding work under a tight window.</td></tr>
        <tr><th>Handoff with fewer agent tokens after a reset</th><td><span class="lvl lvl-med">Next</span></td><td>small</td><td>The recap helps; the agent's longer replies after it are the cost to cut.</td></tr>
        <tr><th>Adaptive workspace</th><td><span class="lvl lvl-med">Next</span></td><td>small</td><td>Turn the note workspace on only when a task refers to earlier results.</td></tr>
        <tr><th>Bedrock validation</th><td><span class="lvl lvl-high">Blocked: credentials</span></td><td>—</td><td>Explicit cache points and Bedrock prices (writes 1.25×).</td></tr>
        <tr><th>Codex / OpenAI pricing</th><td><span class="lvl lvl-low">Not started</span></td><td>re-pricing only</td><td>Automatic caching at different prices may change which methods pay off.</td></tr>
      </tbody></table></div>
  </section>

  <section class="endnote" id="conclusion" aria-labelledby="h-concl">
    <h2 id="h-concl">{ic("check", "ic hic")}Conclusion</h2>
    <p>The repository set out to cut tokens and cost for long-running agents without losing accuracy. After faithful ports of {len(M)} published and new methods and about 2,790 benchmark runs, the answer is a small set of automatic, cache-aware rules rather than any single clever technique: shrink outputs when they arrive, compact rarely and keep the recent steps, and keep notes outside the context that come back by themselves.</p>
    <p>AutoMemory v2 packages those rules. It matches the unoptimised ceiling's accuracy on Haiku and Sonnet at {min(v2h["cost"], v2s["cost"]):.0f}–{max(v2h["cost"], v2s["cost"]):.0f}% of its cost, and no method from the latest literature beats it across the board. For strong agent models, adding SJC's source-judged pruning made it solve every Sonnet run. On 100 real Django issues the within-session half alone (automem_v2_lean) is the cheapest layer under a tight window, and with NVIDIA's handoff recap it reaches the ceiling's accuracy for 6–16 points more cost: the note workspace belongs only where sessions build on each other. The next proof point is Bedrock prices.</p>
    <p class="note">Results are from the Claude Code CLI route at list prices, on four long benchmark tasks with emulated windows; 2–4 runs per cell. See each report in docs/results/ for exact tables and regeneration commands.</p>
  </section>

  <section class="endnote" id="references" aria-labelledby="h-refs">
    <h2 id="h-refs">{ic("book", "ic hic")}References</h2>
    <div class="refs-group"><h4>Published methods</h4><ol class="refs">
      <li><a href="https://arxiv.org/abs/2509.13313">ReSum</a> <span class="src">arXiv 2509.13313 · Alibaba Tongyi Lab</span></li>
      <li><a href="https://doi.org/10.6084/m9.figshare.30073654">AgentDiet artifact</a> <span class="src">FSE'26 · PKU + ByteDance</span></li>
      <li><a href="https://github.com/sunnweiwei/FoldAgent">Context-Folding / FoldAgent</a> <span class="src">ICML'26 · ByteDance Seed</span></li>
      <li><a href="https://github.com/BAI-LAB/MemoryOS">MemoryOS</a> <span class="src">EMNLP'25 · BUPT + Tencent</span></li>
      <li><a href="https://github.com/zjunlp/LightMem">LightMem</a> <span class="src">ICLR'26 · Zhejiang University</span></li>
      <li><a href="https://github.com/nemori-ai/nemori">Nemori</a> <span class="src">ACL'26 · Fudan + Shanda</span></li>
    </ol></div>
    <div class="refs-group"><h4>Methods from the Sep–Nov 2026 scan</h4><ol class="refs">
      <li><a href="https://pypi.org/project/strands-harness/">Strands harness</a> <span class="src">AWS · Apache-2.0</span></li>
      <li><a href="https://arxiv.org/abs/2609.37012">CADOC: Cache-Aware Dynamic Object Context</a> <span class="src">arXiv 2609.37012 · SJTU</span></li>
      <li><a href="https://github.com/YupengSu/ReFold">ReFold</a> <span class="src">arXiv 2610.07863 · UCSB + Intel</span></li>
      <li><a href="https://arxiv.org/abs/2610.20927">Source-Judged Compaction (SJC)</a> <span class="src">arXiv 2610.20927 · University of Virginia</span></li>
      <li><a href="https://github.com/thu-nics/AKV">AKV: Cache Engineering for Agents</a> <span class="src">arXiv 2610.28577 · Tsinghua + CUHK</span></li>
      <li><a href="https://arxiv.org/abs/2610.34073">Memory Tax</a>, <a href="https://arxiv.org/abs/2610.30755">Naive RAG Is Stronger Than We Thought</a>, <a href="https://arxiv.org/abs/2610.29823">MemoryTax: The Bitter Lesson of Agent Memory</a></li>
      <li><a href="https://arxiv.org/abs/2610.40350">CORAL</a> <span class="src">arXiv 2610.40350 · CUHK + Tencent + HKUST</span></li>
      <li><a href="https://github.com/tianjianl/selfcompact">SelfCompact</a> <span class="src">arXiv 2606.23525 · Apple + JHU</span></li>
    </ol></div>
    <div class="refs-group"><h4>This repository</h4><ol class="refs">
      <li>docs/problem_statement.md <span class="desc">Pain points of everyday coding-agent users and how each is addressed.</span></li>
      <li>docs/methodology.md <span class="desc">Tasks, environment rules, metric definitions, model-normalised protocol.</span></li>
      <li>docs/new_methods.md <span class="desc">Sources and deviations of the eight new methods.</span></li>
      <li>docs/results/2026-10-24-automem-evaluation.md, 2026-11-04-new-methods.md, 2026-11-04-automemory-v2.md, 2026-11-04-automemory-v3-ablation.md</li>
      <li>docs/literature/2026-11-scan/ <span class="desc">1,515-paper arXiv sweep, labs, repositories and practitioners.</span></li>
      <li>docs/plans/2026-11-05-next-steps.md <span class="desc">Plan and cost estimate for the next experiments.</span></li>
    </ol></div>
  </section>
</main>
</div>
<script>{(ASSETS / "script_tabs_nav.js").read_text()}</script>
<script>{(ASSETS / "script0.js").read_text()}</script>
<script>
(() => {{
  document.querySelectorAll('[data-motion-root]').forEach((root) => {{
    root.querySelectorAll('[data-goto]').forEach((chip) => chip.addEventListener('click', () => {{
      const target = Number(chip.dataset.goto); let cur = Number(root.dataset.stepCurrent); let guard = 12;
      while (cur !== target && guard-- > 0) {{
        const btn = root.querySelector(`[data-motion-action="${{target > cur ? 'next' : 'prev'}}"]`);
        if (!btn || btn.disabled) break; btn.click(); cur = Number(root.dataset.stepCurrent);
      }}
    }}));
  }});
}})();
</script>
<script>{X.SIM_JS}{X.MAP_JS}{X.SCATTER_JS}{X.CHOOSER_JS}{X.TOOLTIP_JS}</script>
<script>
(() => {{
  document.querySelectorAll('[data-tabs]').forEach((root) => {{
    const tabs = [...root.querySelectorAll('[role="tab"]')];
    const panels = tabs.map((t) => document.getElementById(t.getAttribute('aria-controls')));
    const list = root.querySelector('[role="tablist"]');
    const vertical = list && list.getAttribute('aria-orientation') === 'vertical';
    const select = (i, focus) => {{
      tabs.forEach((t, j) => {{ const on = i === j; t.setAttribute('aria-selected', String(on)); t.tabIndex = on ? 0 : -1; if (panels[j]) panels[j].hidden = !on; }});
      if (focus) tabs[i].focus();
    }};
    tabs.forEach((t, i) => {{
      t.addEventListener('click', () => select(i, false));
      t.addEventListener('keydown', (e) => {{
        const fwd = e.key === 'ArrowRight' || (vertical && e.key === 'ArrowDown');
        const back = e.key === 'ArrowLeft' || (vertical && e.key === 'ArrowUp');
        let n = null;
        if (fwd) n = (i + 1) % tabs.length; if (back) n = (i - 1 + tabs.length) % tabs.length;
        if (e.key === 'Home') n = 0; if (e.key === 'End') n = tabs.length - 1;
        if (n !== null) {{ e.preventDefault(); select(n, true); }}
      }});
    }});
    select(0, false);
  }});
}})();
</script>
"""
OUT.write_text(PAGE)
print(OUT, len(PAGE))
