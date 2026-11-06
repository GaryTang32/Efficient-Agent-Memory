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
    ("Workspace + ReSum", "pub", (126, 0.89), (71, 0.94)),
    ("Strands", "pub", (125, 0.59), (148, 0.88)),
    ("CADOC", "pub", (107, 0.43), (83, 0.86)),
    ("ReFold", "pub", (56, 0.43), (106, 0.97)),
    ("SJC on ReSum", "pub", (136, 0.80), (80, 0.94)),
    ("OpenClaw + SJC", "pub", (90, 0.88), (68, 0.87)),
    ("AKV rolling drop", "pub", (81, 0.45), (68, 0.60)),
    ("Raw-history RAG", "pub", (105, 0.52), (199, 0.99)),
    ("CORAL", "pub", (66, 0.15), (45, 0.38)),
    ("SelfCompact", "pub", (179, 0.75), (130, 0.93)),
    ("EoCC (NVIDIA)", "pub", (89, 0.73), (126, 0.91)),
    ("AutoMemory v1", "ours", (86, 0.83), (68, 0.98)),
    ("AutoMemory v2", "ours", (85, 0.88), (58, 0.99)),
    ("v2 strong", "ours", (114, 0.81), (61, 1.00)),
    ("v2 slim", "ours", (90, 0.87), (78, 1.00)),
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

# SWE-bench Verified, 100 Django issues, 16K window (+ the ceiling at the own window): (cost %, resolved)
SWE16 = [
    ("Ceiling (own window)", "ref", (100, 82), (100, 88)),
    ("AutoMemory lean (ReSum)", "ours", (83, 76), (73, 86)),
    ("AutoMemory lean + handoff", "ours", (89, 81), (89, 88)),
    ("EoCC alone (NVIDIA)", "pub", (93, 72), (100, 83)),
]
SWE_LABELS = {
    "haiku": {"Ceiling (own window)": (-9, -10, "end"), "AutoMemory lean (ReSum)": (-9, 4, "end"),
              "AutoMemory lean + handoff": (-9, 4, "end"), "EoCC alone (NVIDIA)": (-9, 4, "end")},
    "sonnet": {"Ceiling (own window)": (-9, 20, "end"), "AutoMemory lean (ReSum)": (9, 18, "start"),
               "AutoMemory lean + handoff": (-9, 4, "end"), "EoCC alone (NVIDIA)": (-9, 4, "end")},
}

# Sonnet, dollars per resolved issue on the 100 issues
DOLLARS = [
    ("AutoMemory lean, 16K", "ours", 0.123),
    ("AutoMemory lean + handoff, 32K", "ours", 0.130),
    ("Cached full history, own window", "ref", 0.142),
    ("AutoMemory lean + handoff, 16K", "ours", 0.147),
    ("Ceiling: full history, no cache", "ref", 0.165),
    ("EoCC alone, 16K", "pub", 0.175),
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
        body.append(scatter_panel(78 + i * 470, top, pw, ph, t, m, pts, SYNTH_LABELS[key], (0, 210), (0, 1.05),
                                  [0, 50, 100, 150, 200], [0, 0.25, 0.5, 0.75, 1.0], lambda v: f"{v:.0f}%",
                                  lambda v: f"{v:.2f}", "Cost vs the unoptimised ceiling (lower is cheaper)",
                                  "Mean score over 4 tasks"))
    return svg(960, 440, "".join(body), "Accuracy against cost on four long agent tasks",
               "Scatter plots for Claude Haiku and Claude Sonnet: each method's mean score against its cost relative "
               "to the unoptimised ceiling. AutoMemory v2 sits at the top left: the ceiling's accuracy at 85% "
               "(Haiku) and 58% (Sonnet) of its cost.")


def swe_chart(t):
    pw, ph, top = 380, 250, 78
    body = [legend(70, 26, t, [("ours", "AutoMemory"), ("pub", "NVIDIA EoCC alone"), ("ref", "Ceiling")])]
    for i, (m, key) in enumerate((("Claude Haiku", "haiku"), ("Claude Sonnet", "sonnet"))):
        pts = [(n, k, (hv if key == "haiku" else sv)) for n, k, hv, sv in SWE16]
        body.append(scatter_panel(78 + i * 470, top, pw, ph, t, m, pts, SWE_LABELS[key], (60, 105), (70, 92),
                                  [60, 70, 80, 90, 100], [70, 75, 80, 85, 90], lambda v: f"{v:.0f}%",
                                  lambda v: f"{v:.0f}", "Cost vs the ceiling (lower is cheaper)",
                                  "Issues resolved of 100"))
    return svg(960, 390, "".join(body), "SWE-bench Verified: 100 Django issues at a 16K window",
               "Issues resolved against cost relative to the ceiling, for Haiku and Sonnet. AutoMemory lean with ReSum "
               "is the cheapest; with NVIDIA's handoff recap it reaches the ceiling's accuracy for more cost; EoCC "
               "alone resolves the fewest.")


def dollars_chart(t):
    left, top, w, rowh = 250, 48, 560, 34
    vmax = 0.20
    sx = lambda v: left + v / vmax * w
    body = [f'<text x="20" y="24" fill="{t["ink"]}" font-size="14" font-weight="600">Claude Sonnet: dollars per resolved '
            f'issue, 100 SWE-bench Verified issues (lower is better)</text>']
    for v in (0, 0.05, 0.10, 0.15, 0.20):
        body.append(f'<line x1="{sx(v):.1f}" x2="{sx(v):.1f}" y1="{top - 6}" y2="{top + rowh * len(DOLLARS)}" '
                    f'stroke="{t["grid"]}" stroke-width="1"/>')
        body.append(f'<text x="{sx(v):.1f}" y="{top + rowh * len(DOLLARS) + 18}" fill="{t["muted"]}" font-size="11.5" '
                    f'text-anchor="middle">${v:.2f}</text>')
    for i, (name, kind, v) in enumerate(DOLLARS):
        y = top + i * rowh
        col = t["ours"] if kind == "ours" else t["pub"] if kind == "pub" else t["ref"]
        bw = sx(v) - left
        body.append(f'<text x="{left - 12}" y="{y + 19}" fill="{t["ink"]}" font-size="12.5" text-anchor="end">{E(name)}</text>')
        body.append(f'<path d="M{left} {y + 6} h{bw - 4:.1f} a4 4 0 0 1 4 4 v12 a4 4 0 0 1 -4 4 h{-(bw - 4):.1f} Z" '
                    f'fill="{col}"><title>{E(name)}: ${v:.3f} per resolved issue</title></path>')
        body.append(f'<text x="{sx(v) + 8:.1f}" y="{y + 19}" fill="{t["ink2"]}" font-size="12.5">${v:.3f}</text>')
    body.append(f'<line x1="{left}" x2="{left}" y1="{top - 6}" y2="{top + rowh * len(DOLLARS)}" stroke="{t["axis"]}" stroke-width="1"/>')
    return svg(900, top + rowh * len(DOLLARS) + 34, "".join(body), "Dollars per resolved issue (Sonnet)",
               "Horizontal bars: AutoMemory lean at a 16K window is the cheapest per resolved issue ($0.123); the "
               "unoptimised ceiling costs $0.165 and EoCC alone $0.175.")


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    for name, fn in (("synthetic-frontier", synth_chart), ("swe-16k", swe_chart), ("swe-dollars", dollars_chart)):
        for mode, t in THEMES.items():
            (OUT / f"{name}-{mode}.svg").write_text(fn(t))
    print("wrote", sorted(p.name for p in OUT.glob("*.svg")))


if __name__ == "__main__":
    main()
