"""Charts for the README front page: static SVGs in a light and a dark variant (GitHub swaps them with <picture>).

    python scripts/docs_gen/readme_charts.py          # writes docs/assets/*.svg

The numbers are the published results (README tables; reports in docs/results/, kept local), copied here so the
charts can be rebuilt from a fresh clone. Colours: two validated categorical slots (this project's methods, published
methods) and a neutral grey for the reference points; marker shape repeats the grouping, so it never relies on colour.
"""

from __future__ import annotations

from pathlib import Path
from xml.sax.saxutils import escape as E

OUT = Path(__file__).resolve().parents[2] / "docs" / "assets"

THEMES = {
    "light": dict(ink="#0b0b0b", ink2="#52514e", muted="#6f6d68", grid="#e1e0d9", axis="#c3c2b7",
                  ours="#2a78d6", pub="#eb6834", ref="#898781", ring="#ffffff"),
    "dark": dict(ink="#f0efec", ink2="#c3c2b7", muted="#9b9990", grid="#2c2c2a", axis="#4a4a46",
                 ours="#3987e5", pub="#d95926", ref="#898781", ring="#0d1117"),
}
FONT = 'font-family="system-ui,-apple-system,Segoe UI,Helvetica,Arial,sans-serif"'

# ---- data -------------------------------------------------------------------------------------------------------
# Four long synthetic tasks: (label, group, Haiku (cost %, score), Sonnet (cost %, score), label placement per panel)
SYNTH = [
    ("No memory (floor)", "ref", (27, 0.21), (38, 0.17)),
    ("Ceiling", "ref", (100, 0.88), (100, 0.95)),
    ("Workspace + ReSum", "pub", (126, 0.89), (75, 0.94)),
    ("Strands", "pub", (125, 0.59), (160, 0.88)),
    ("CADOC", "pub", (107, 0.43), (86, 0.86)),
    ("ReFold", "pub", (56, 0.43), (108, 0.97)),
    ("SJC on ReSum", "pub", (136, 0.80), (81, 0.94)),
    ("OpenClaw + SJC", "pub", (90, 0.88), (69, 0.87)),
    ("AKV rolling drop", "pub", (81, 0.45), (69, 0.60)),
    ("Raw-history RAG", "pub", (105, 0.52), (213, 0.99)),
    ("CORAL", "pub", (66, 0.15), (46, 0.38)),
    ("SelfCompact", "pub", (179, 0.75), (134, 0.93)),
    ("EoCC (NVIDIA)", "pub", (89, 0.73), (126, 0.91)),
    ("AutoMemory v1", "ours", (86, 0.83), (68, 0.98)),
    ("AutoMemory v2", "ours", (85, 0.88), (58, 0.99)),
    ("v2 strong", "ours", (114, 0.81), (61, 1.00)),
    ("v2 slim", "ours", (90, 0.87), (80, 1.00)),
]
# labels drawn on the chart (the rest are in the README table), with (dx, dy, anchor)
SYNTH_LABELS = {
    "haiku": {"No memory (floor)": (8, 4, "start"), "Ceiling": (0, -11, "middle"),
              "AutoMemory v2": (-9, -8, "end"), "CORAL": (8, 4, "start"), "SelfCompact": (-8, 16, "end"),
              "Workspace + ReSum": (8, 4, "start"), "ReFold": (-9, 4, "end")},
    "sonnet": {"No memory (floor)": (8, 4, "start"), "Ceiling": (0, 18, "middle"),
               "AutoMemory v2": (-9, -8, "end"), "CORAL": (8, 4, "start"), "AKV rolling drop": (8, 4, "start"),
               "Raw-history RAG": (-8, 16, "end"), "Strands": (8, 4, "start")},
}

# SWE-bench Verified, 100 Django issues, 16K window, every cell run on the same day (validation round, 2026-11):
# (label, Haiku, Sonnet), each (cost % of the ceiling, interval low, interval high, issues resolved)
# (label, runs, haiku, sonnet); each model: cost % of the ceiling, interval low, high, resolved, the ceiling's resolved
SWE16 = [
    ("Lean (ReSum summary)", 3, (96, 83, 110, 81, 78), (80, 72, 90, 87, 87)),
    ("Lean + handoff recap", 3, (100, 91, 109, 80, 78), (81, 74, 89, 88, 87)),
    ("Lean + brief recap", 1, (90, 73, 110, 75, 77), (86, 72, 105, 84, 83)),
    ("Adaptive workspace", 1, (131, 96, 174, 78, 77), (105, 85, 130, 86, 83)),
    ("EoCC alone (no previews)", 1, (85, 70, 100, 75, 80), (74, 67, 82, 85, 90)),
]


# ---- drawing ----------------------------------------------------------------------------------------------------
def marker(kind, x, y, t, title):
    tip = f"<title>{E(title)}</title>"
    if kind == "ours":
        return f'<circle cx="{x:.1f}" cy="{y:.1f}" r="5.5" fill="{t["ours"]}" stroke="{t["ring"]}" stroke-width="2">{tip}</circle>'
    if kind == "pub":
        return (f'<rect x="{x - 5:.1f}" y="{y - 5:.1f}" width="10" height="10" rx="1.5" fill="{t["pub"]}" '
                f'stroke="{t["ring"]}" stroke-width="2">{tip}</rect>')
    return (f'<path d="M{x:.1f} {y - 6.5:.1f} L{x + 6.5:.1f} {y:.1f} L{x:.1f} {y + 6.5:.1f} L{x - 6.5:.1f} {y:.1f} Z" '
            f'fill="{t["ref"]}" stroke="{t["ring"]}" stroke-width="2">{tip}</path>')


def legend(x, y, t, items):
    out, cx = [], x
    for kind, text in items:
        out.append(marker(kind, cx + 6, y - 4, t, text))
        out.append(f'<text x="{cx + 18}" y="{y}" fill="{t["ink2"]}" font-size="12.5">{E(text)}</text>')
        cx += 30 + 7.1 * len(text)
    return "".join(out)


def scatter_panel(ox, oy, w, h, t, title, pts, labels, xdom, ydom, xticks, yticks, xfmt, yfmt, xlabel, ylabel):
    (x0, x1), (y0, y1) = xdom, ydom
    sx = lambda v: ox + (v - x0) / (x1 - x0) * w
    sy = lambda v: oy + h - (v - y0) / (y1 - y0) * h
    out = [f'<text x="{ox}" y="{oy - 14}" fill="{t["ink"]}" font-size="14" font-weight="600">{E(title)}</text>']
    for v in yticks:
        out.append(f'<line x1="{ox}" x2="{ox + w}" y1="{sy(v):.1f}" y2="{sy(v):.1f}" stroke="{t["grid"]}" stroke-width="1"/>')
        out.append(f'<text x="{ox - 8}" y="{sy(v) + 4:.1f}" fill="{t["muted"]}" font-size="11.5" text-anchor="end">{yfmt(v)}</text>')
    for v in xticks:
        out.append(f'<text x="{sx(v):.1f}" y="{oy + h + 18}" fill="{t["muted"]}" font-size="11.5" text-anchor="middle">{xfmt(v)}</text>')
    out.append(f'<line x1="{ox}" x2="{ox + w}" y1="{oy + h}" y2="{oy + h}" stroke="{t["axis"]}" stroke-width="1"/>')
    # the ceiling's cost: a dashed reference line
    out.append(f'<line x1="{sx(100):.1f}" x2="{sx(100):.1f}" y1="{oy}" y2="{oy + h}" stroke="{t["axis"]}" '
               f'stroke-width="1" stroke-dasharray="3 4"/>')
    out.append(f'<text x="{ox + w / 2}" y="{oy + h + 38}" fill="{t["ink2"]}" font-size="12" text-anchor="middle">{E(xlabel)}</text>')
    out.append(f'<text transform="translate({ox - 44} {oy + h / 2}) rotate(-90)" fill="{t["ink2"]}" font-size="12" '
               f'text-anchor="middle">{E(ylabel)}</text>')
    for name, kind, (xv, yv) in pts:
        out.append(marker(kind, sx(xv), sy(yv), t, f"{name}: {yfmt(yv)} at {xfmt(xv)} of the ceiling's cost"))
        if name in labels:
            dx, dy, anc = labels[name]
            weight = ' font-weight="600"' if kind == "ours" else ""
            out.append(f'<text x="{sx(xv) + dx:.1f}" y="{sy(yv) + dy:.1f}" fill="{t["ink"]}" font-size="12"{weight} '
                       f'text-anchor="{anc}">{E(name)}</text>')
    return "".join(out)


def svg(w, h, body, title, desc):
    return (f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {w} {h}" width="{w}" height="{h}" {FONT} '
            f'role="img" aria-labelledby="t d"><title id="t">{E(title)}</title><desc id="d">{E(desc)}</desc>{body}</svg>\n')


def synth_chart(t):
    pw, ph, top = 380, 300, 78
    body = [legend(70, 26, t, [("ours", "This project (AutoMemory)"), ("pub", "Published methods"),
                               ("ref", "Floor and ceiling")])]
    for i, (m, key) in enumerate((("Claude Haiku", "haiku"), ("Claude Sonnet", "sonnet"))):
        pts = [(n, k, (hv if key == "haiku" else sv)) for n, k, hv, sv in SYNTH]
        body.append(scatter_panel(78 + i * 470, top, pw, ph, t, m, pts, SYNTH_LABELS[key], (0, 220), (0, 1.05),
                                  [0, 50, 100, 150, 200], [0, 0.25, 0.5, 0.75, 1.0], lambda v: f"{v:.0f}%",
                                  lambda v: f"{v:.2f}", "Cost vs the unoptimised ceiling (lower is cheaper)",
                                  "Mean score over 4 tasks"))
    return svg(960, 440, "".join(body), "Accuracy against cost on four long agent tasks",
               "Scatter plots for Claude Haiku and Claude Sonnet: each method's mean score against its cost relative "
               "to the unoptimised ceiling. AutoMemory v2 sits at the top left: the ceiling's accuracy at 85% "
               "(Haiku) and 58% (Sonnet) of its cost.")


def swe_chart(t):
    """Cost against the ceiling with its 95% interval (dot and whisker), and the issues resolved, per setting."""
    left, pw, top, rowh = 172, 250, 92, 38
    x0, x1 = 50, 180
    body = [f'<text x="20" y="26" fill="{t["ink"]}" font-size="14" font-weight="600">SWE-bench Verified, 100 Django '
            f'issues at a 16K window: cost against the ceiling of the same run</text>',
            f'<text x="20" y="46" fill="{t["ink2"]}" font-size="12.5">Dot: cost as a share of the ceiling\'s. Line: 95% '
            f'interval over workdays. Right: issues resolved of 100 by the setting · by its ceiling (means over the runs).</text>']
    for i, (m, key) in enumerate((("Claude Haiku", "haiku"), ("Claude Sonnet", "sonnet"))):
        ox = left + i * 470
        sx = lambda v, ox=ox: ox + (min(max(v, x0), x1) - x0) / (x1 - x0) * pw
        bottom = top + rowh * len(SWE16)
        body.append(f'<text x="{ox}" y="{top - 14}" fill="{t["ink"]}" font-size="13.5" font-weight="600">{m}</text>')
        for v in (50, 75, 100, 125, 150, 175):
            body.append(f'<line x1="{sx(v):.1f}" x2="{sx(v):.1f}" y1="{top}" y2="{bottom}" stroke="{t["grid"]}" stroke-width="1"/>')
            body.append(f'<text x="{sx(v):.1f}" y="{bottom + 17}" fill="{t["muted"]}" font-size="11.5" '
                        f'text-anchor="middle">{v}%</text>')
        body.append(f'<line x1="{sx(100):.1f}" x2="{sx(100):.1f}" y1="{top - 4}" y2="{bottom}" stroke="{t["ref"]}" '
                    f'stroke-width="1.5" stroke-dasharray="4 4"/>')
        for r, (name, runs, hv, sv) in enumerate(SWE16):
            cost, lo, hi, res, ceil = hv if key == "haiku" else sv
            y = top + r * rowh + rowh / 2
            if i == 0:
                body.append(f'<text x="{ox - 12}" y="{y + 1:.1f}" fill="{t["ink"]}" font-size="12.5" text-anchor="end">{E(name)}</text>')
                body.append(f'<text x="{ox - 12}" y="{y + 15:.1f}" fill="{t["muted"]}" font-size="11" text-anchor="end">'
                            f'{"3 runs" if runs == 3 else "1 run"}</text>')
            tip = (f"{name}, {m}, {runs} run{'s' if runs > 1 else ''}: {cost}% of the ceiling's cost (95% interval {lo}–{hi}%), "
                   f"{res} of 100 resolved against {ceil} for the ceiling")
            body.append(f'<line x1="{sx(lo):.1f}" x2="{sx(hi):.1f}" y1="{y:.1f}" y2="{y:.1f}" stroke="{t["ours"]}" '
                        f'stroke-width="2.5" stroke-linecap="round" opacity="0.55"><title>{E(tip)}</title></line>')
            body.append(f'<circle cx="{sx(cost):.1f}" cy="{y:.1f}" r="5.5" fill="{t["ours"]}" stroke="{t["ring"]}" '
                        f'stroke-width="2"><title>{E(tip)}</title></circle>')
            body.append(f'<text x="{sx(cost):.1f}" y="{y - 10:.1f}" fill="{t["ink2"]}" font-size="11.5" text-anchor="middle">{cost}%</text>')
            body.append(f'<text x="{ox + pw + 12}" y="{y + 4:.1f}" fill="{t["ink"]}" font-size="12.5">{res}'
                        f'<tspan fill="{t["muted"]}"> · {ceil}</tspan></text>')
        body.append(f'<text x="{ox + pw + 12}" y="{top - 14}" fill="{t["muted"]}" font-size="11.5">resolved</text>')
        body.append(f'<text x="{ox + pw / 2}" y="{bottom + 36}" fill="{t["ink2"]}" font-size="12" text-anchor="middle">'
                    f'Cost vs the ceiling (left of the dashed line is cheaper)</text>')
    return svg(960, top + rowh * len(SWE16) + 50, "".join(body),
               "SWE-bench Verified: 100 Django issues at a 16K window, each setting against the ceiling of its run",
               "Cost relative to the ceiling with 95% intervals and issues resolved, for Haiku and Sonnet. Over three "
               "runs the lean settings cost 80 to 81% of the ceiling on Sonnet and 96 to 100% on Haiku, and resolve as "
               "many issues. The adaptive workspace costs more. EoCC alone costs 74 to 85% but resolves 5 fewer issues "
               "than its ceiling on both models.")


# Roadmap: (stage, dates, status, what was done, what it showed). Status: done | next | blocked.
ROADMAP = [
    ("Measure published methods", "22–26 Oct", "done",
     "ReSum, AgentDiet, Context-Folding, MemoryOS, LightMem, Nemori and others on four long multi-session tasks",
     "No single method is enough; plain notes beat engineered memory systems"),
    ("Build AutoMemory", "23 Oct – 5 Nov", "done",
     "v1, then v2 after eight more methods from the 2026 literature; a Python library and an MCP server",
     "v2 reaches the ceiling's accuracy at 85% (Haiku) and 58% (Sonnet) of its cost"),
    ("Real repositories", "5–6 Nov", "done",
     "SWE-bench Verified workdays on Django, graded with the official tests; NVIDIA's handoff recap",
     "A 16K window with compaction resolves as many issues as the model's full window"),
    ("Ship to users", "8 Nov", "done",
     "Claude Code plugin (previews, handoff at compaction, recall, autosave) and two pilots",
     "Neutral inside Claude Code, which already caches and compacts"),
    ("Validate", "8–13 Nov", "done",
     "Same-day controls, repeats, a code audit, SymPy and related issues, three runs per cell",
     "Headline results hold; lean costs 80% of the ceiling on Sonnet; four claims withdrawn"),
    ("Broaden", "next", "next",
     "Native tool calls on Bedrock, GPT models, a second language, three runs on SymPy",
     "Bedrock and GPT wait on credentials; the rest needs no new access"),
]
ROADMAP_NEXT = [
    ("next", "Next", [("Three runs of SymPy and related issues", "≈ $45"),
                      ("Cost on two price bases", "no API cost"),
                      ("Plugin for agents without built-in caching", "no API cost")]),
    ("blocked", "Blocked on credentials", [("Bedrock validation, native tool calls", "AWS key"),
                                           ("GPT and other non-Claude models", "API key")]),
    ("todo", "Not started", [("Codex / OpenAI re-pricing", "no API cost"),
                             ("A repository outside Python", "needs its own test setup")]),
]


def status_mark(kind, x, y, t, r=7.5):
    if kind == "done":
        return (f'<circle cx="{x}" cy="{y}" r="{r}" fill="{t["ours"]}" stroke="{t["ring"]}" stroke-width="2"/>'
                f'<path d="M{x - 3.6} {y + 0.2} l2.5 2.6 l4.8 -5.2" fill="none" stroke="{t["ring"]}" stroke-width="2" '
                f'stroke-linecap="round" stroke-linejoin="round"/>')
    if kind == "next":
        return (f'<circle cx="{x}" cy="{y}" r="{r}" fill="{t["ring"]}" stroke="{t["pub"]}" stroke-width="2.5"/>'
                f'<circle cx="{x}" cy="{y}" r="{r - 4.5}" fill="{t["pub"]}"/>')
    if kind == "blocked":
        return (f'<circle cx="{x}" cy="{y}" r="{r}" fill="{t["ring"]}" stroke="{t["ref"]}" stroke-width="2"/>'
                f'<line x1="{x - 4}" y1="{y + 4}" x2="{x + 4}" y2="{y - 4}" stroke="{t["ref"]}" stroke-width="2" stroke-linecap="round"/>')
    return f'<circle cx="{x}" cy="{y}" r="{r}" fill="{t["ring"]}" stroke="{t["ref"]}" stroke-width="2" stroke-dasharray="3 2.5"/>'


def roadmap_chart(t):
    done = sum(s == "done" for _, _, s, _, _ in ROADMAP)
    W, lx, tx, rowh, top = 960, 136, 162, 64, 112
    body = [f'<text x="20" y="28" fill="{t["ink"]}" font-size="15" font-weight="600">Roadmap and progress</text>',
            f'<text x="20" y="49" fill="{t["ink2"]}" font-size="12.5">{done} of {len(ROADMAP)} stages done · '
            f'22 Oct – 13 Nov 2026 · about 3,700 benchmark runs on Claude Haiku and Sonnet</text>']
    seg, gap, bx = 128, 6, 20
    for i, (_, _, s, _, _) in enumerate(ROADMAP):
        x = bx + i * (seg + gap)
        fill = t["ours"] if s == "done" else t["pub"] if s == "next" else t["grid"]
        body.append(f'<rect x="{x}" y="64" width="{seg}" height="8" rx="4" fill="{fill}" opacity="{1 if s == "done" else 0.85}"/>')
    lx2 = bx + len(ROADMAP) * (seg + gap) + 10
    body.append(status_mark("done", lx2 + 8, 68, t, 6) +
                f'<text x="{lx2 + 20}" y="72" fill="{t["ink2"]}" font-size="12">done</text>' +
                status_mark("next", lx2 + 68, 68, t, 6) +
                f'<text x="{lx2 + 80}" y="72" fill="{t["ink2"]}" font-size="12">next</text>')
    y0, y1 = top - 8, top + rowh * (len(ROADMAP) - 1) + 8
    last_done = top + rowh * (done - 1)
    body.append(f'<line x1="{lx}" x2="{lx}" y1="{y0}" y2="{last_done}" stroke="{t["ours"]}" stroke-width="3" stroke-linecap="round"/>')
    body.append(f'<line x1="{lx}" x2="{lx}" y1="{last_done}" y2="{y1}" stroke="{t["axis"]}" stroke-width="2" stroke-dasharray="4 4"/>')
    for i, (name, dates, s, what, result) in enumerate(ROADMAP):
        y = top + i * rowh
        body.append(f'<text x="{lx - 18}" y="{y + 4}" fill="{t["muted"] if s != "done" else t["ink2"]}" font-size="12" '
                    f'text-anchor="end">{E(dates)}</text>')
        body.append(status_mark(s, lx, y, t))
        body.append(f'<text x="{tx}" y="{y + 5}" fill="{t["ink"]}" font-size="14" font-weight="600">'
                    f'<tspan fill="{t["muted"]}" font-weight="400">{i + 1}  </tspan>{E(name)}</text>')
        body.append(f'<text x="{tx}" y="{y + 24}" fill="{t["ink2"]}" font-size="12.5">{E(what)}</text>')
        col = t["ours"] if s == "done" else t["pub"]
        body.append(f'<text x="{tx}" y="{y + 42}" fill="{t["ink"]}" font-size="12.5">'
                    f'<tspan fill="{col}" font-weight="600">→ </tspan>{E(result)}</text>')
    ny = top + rowh * len(ROADMAP) + 10
    body.append(f'<line x1="20" x2="{W - 20}" y1="{ny}" y2="{ny}" stroke="{t["grid"]}" stroke-width="1"/>')
    body.append(f'<text x="20" y="{ny + 30}" fill="{t["ink"]}" font-size="14" font-weight="600">What is left</text>')
    cw = (W - 40) / len(ROADMAP_NEXT)
    for c, (kind, head, items) in enumerate(ROADMAP_NEXT):
        cx = 20 + c * cw
        body.append(status_mark(kind, cx + 8, ny + 56, t, 6.5) +
                    f'<text x="{cx + 22}" y="{ny + 60.5}" fill="{t["ink"]}" font-size="13" font-weight="600">{E(head)}</text>')
        for k, (item, cost) in enumerate(items):
            iy = ny + 86 + k * 38
            body.append(f'<text x="{cx + 22}" y="{iy}" fill="{t["ink"]}" font-size="12.5">{E(item)}</text>'
                        f'<text x="{cx + 22}" y="{iy + 16}" fill="{t["muted"]}" font-size="11.5">{E(cost)}</text>')
    h = ny + 86 + 3 * 38 - 8
    return svg(W, h, "".join(body), "Roadmap and progress of Efficient Agent Memory",
               f"{done} of {len(ROADMAP)} stages are done: measuring published methods, building AutoMemory, real "
               "repositories, shipping a Claude Code plugin, and a validation round. Next: broaden to native tool calls "
               "on Bedrock and GPT models (blocked on credentials), three runs on SymPy, cost on two price bases, and a "
               "repository outside Python.")


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    for name, fn in (("synthetic-frontier", synth_chart), ("swe-16k", swe_chart), ("roadmap", roadmap_chart)):
        for mode, t in THEMES.items():
            (OUT / f"{name}-{mode}.svg").write_text(fn(t))
    print("wrote", sorted(p.name for p in OUT.glob("*.svg")))


if __name__ == "__main__":
    main()
