"""Interactive and animated pieces of docs/overview.html: the AutoMemory stepper, the cache simulator, the method map,
the score-vs-cost chart, the token-mix chart, the experiment timeline and the setting chooser."""
import html
import json

E = html.escape

CSS = """
  /* ---------- Interactive additions ---------- */
  .sim2 { background: var(--paper); border: 1px solid var(--rule); border-radius: 4px; padding: 12px 14px; display: flex; flex-direction: column; gap: 10px; }
  .sim2-top { display: flex; flex-wrap: wrap; gap: 10px 18px; align-items: center; }
  .sim2-k { font-family: var(--font-cond); font-weight: 600; font-size: 0.78rem; letter-spacing: 0.06em; text-transform: uppercase; color: var(--muted); }
  .sim2 .seg button { font-size: 0.82rem; }
  .sim2-out { display: grid; grid-template-columns: repeat(4, minmax(0, 1fr)); gap: 10px; }
  .sim2-out div { border-left: 3px solid var(--part); background: var(--part-tint); padding: 6px 10px; border-radius: 2px; display: flex; flex-direction: column; min-width: 0; }
  .sim2-out b { font-family: var(--font-display); font-size: 1.35rem; font-weight: 600; color: var(--part); font-variant-numeric: tabular-nums; }
  .sim2-out span { font-size: 0.78rem; color: var(--muted); }
  .sim2-ctl { display: flex; flex-wrap: wrap; gap: 8px; align-items: center; }
  .sim2-ctl input[type=range] { flex: 1 1 200px; accent-color: var(--part); }
  .sim2-why { font-size: 0.88rem; background: var(--surface); border-radius: 2px; padding: 8px 12px; min-height: 2.6em; }
  .bar-read { fill: var(--check); fill-opacity: 0.75; } .bar-write { fill: var(--warn); fill-opacity: 0.8; } .bar-unc { fill: var(--amber); fill-opacity: 0.85; }
  .bar-sum { fill: var(--violet); fill-opacity: 0.9; }
  .win-l { stroke: var(--warn); stroke-width: 1.4; stroke-dasharray: 5 4; }
  .sel-l { stroke: var(--ink); stroke-width: 1.2; }
  .sw { display: inline-block; width: 12px; height: 10px; border-radius: 2px; margin-right: 5px; vertical-align: -1px; }

  .scatter .pt { cursor: default; }
  .scatter .pt circle { stroke: var(--paper); stroke-width: 1.5; }
  .scatter .pt:hover circle, .scatter .pt:focus circle { stroke: var(--ink); stroke-width: 2; }
  .pt-anc circle { fill: var(--muted); } .pt-pub circle { fill: var(--accent); } .pt-new circle { fill: var(--amber); } .pt-ours circle { fill: var(--violet); }
  .pt-lab { fill: var(--ink); font-family: var(--font-body); font-size: 10.5px; }
  .zone { fill: var(--check-tint); }
  .zone-t { fill: var(--check); font-family: var(--font-mono); font-size: 10px; letter-spacing: 0.06em; }
  .scatter-wrap[data-model="haiku"] .m-sonnet, .scatter-wrap[data-model="sonnet"] .m-haiku { display: none; }

  .map-chip { cursor: pointer; }
  .map-chip rect { stroke-width: 1; }
  .map-chip.ok rect { fill: var(--check-tint); stroke: var(--check); }
  .map-chip.mid rect { fill: var(--amber-tint); stroke: var(--amber); }
  .map-chip.bad rect { fill: var(--warn-tint); stroke: var(--warn); }
  .map-chip.us rect { fill: var(--violet-tint); stroke: var(--violet); stroke-width: 1.6; }
  .map-chip text { fill: var(--ink); font-family: var(--font-body); font-size: 11.5px; font-weight: 500; }
  .map-chip:hover rect, .map-chip:focus rect { stroke-width: 2.4; }
  .map-col { fill: var(--surface); }

  .chooser { display: grid; grid-template-columns: minmax(0, 320px) minmax(0, 1fr); gap: 14px; align-items: start; }
  .q { display: flex; flex-direction: column; gap: 4px; padding: 8px 0; border-bottom: 1px solid var(--rule); }
  .q:last-of-type { border-bottom: 0; }
  .q p { font-weight: 600; font-size: 0.92rem; }
  .q .seg button { min-height: 32px; font-size: 0.82rem; }
  .q.off { opacity: 0.4; pointer-events: none; }
  .fc .fn rect { fill: var(--paper); stroke: var(--rule-strong); stroke-width: 1; transition: fill var(--motion-fast), stroke var(--motion-fast); }
  .fc .fn.on rect { fill: var(--violet-tint); stroke: var(--violet); stroke-width: 2; }
  .fc .fn.res rect { stroke-dasharray: 4 3; }
  .fc .fn.res.on rect { fill: var(--check-tint); stroke: var(--check); stroke-dasharray: none; stroke-width: 2.2; }
  .fc .fe { stroke: var(--rule-strong); stroke-width: 1.4; fill: none; transition: stroke var(--motion-fast); }
  .fc .fe.on { stroke: var(--violet); stroke-width: 2.4; }
  .fc .fl { fill: var(--soft); font-family: var(--font-mono); font-size: 9.5px; letter-spacing: 0.06em; }
  .fc .fl.on { fill: var(--violet); }
  .pick { border: 1px solid var(--rule); border-left: 3px solid var(--check); border-radius: 2px; padding: 10px 14px; background: #F2FAF7; display: flex; flex-direction: column; gap: 4px; }
  .pick code { font-size: 0.95rem; }
  .tl-dot { fill: var(--part); }
  @media (max-width: 900px) { .chooser { grid-template-columns: 1fr; } .sim2-out { grid-template-columns: repeat(2, minmax(0, 1fr)); } }
"""


# ------------------------------------------------------------------ 1. AutoMemory stepper
def automem_stepper():
    steps = [
        ("Recall", "Notes come back by themselves",
         "At session start, every note saved in earlier sessions is placed in the first message. The model does not have to remember to read its notes.",
         [("Hook", "on_session_start"), ("Cache", "first message only; stable afterwards"),
          ("Evidence", "Without recall and autosave: Haiku 0.50–0.89 and more cost")]),
        ("Request", "Every step re-sends a cached prefix",
         "System prompt, tools and the history so far are sent again. Unchanged, they are read from the prompt cache at 0.05–0.1× the input price; only the newest message is new.",
         [("Hook", "render (unchanged)"), ("Cache", "prefix read at 0.05–0.1×"),
          ("Evidence", "AutoMemory runs: 77–82% of prompt tokens are cache reads")]),
        ("Preview", "Large outputs are shrunk at the door",
         "A tool result above 10% of the window enters the history as a 750-token head/tail preview with a reference key; retrieve_context greps it or reads a line range. The full text never enters the context.",
         [("Hook", "on_tool_result"), ("Cache", "safe: applied before the history"),
          ("Evidence", "v2: Haiku 7 → 11 of 16 runs solved, same cost")]),
        ("Guard", "Nothing pushes the next request over the window",
         "Within one step, a result that would push the next prompt past 90% of the window is offloaded to the artifact store at once; a pointer stays.",
         [("Hook", "on_tool_result"), ("Cache", "safe"), ("Evidence", "Without it, repo_debug overflows (Haiku 0.47)")]),
        ("Compact", "One reset at 75%, keeping the tail",
         "When the context reaches 75% of the window, a cheaper model writes a ReSum summary (for strong agents, SJC then prunes unsourced entries). The history becomes the summary, the notes and the last 2 steps.",
         [("Hook", "before_call"), ("Cache", "one rewrite per reset"),
          ("Evidence", "Without compaction: 0.04–0.62. SJC for Sonnet: 16/16 solved")]),
        ("Autosave", "The answer becomes a note",
         "When the session ends, its final answer is saved as a note automatically, so the next session starts from the result rather than from the raw files.",
         [("Hook", "on_session_end"), ("Cache", "no effect"), ("Evidence", "What later sessions most often need is an earlier result")]),
    ]
    n = len(steps)
    # SVG nodes: a loop of six boxes
    pos = [(32, 70), (232, 70), (432, 70), (632, 70), (632, 230), (232, 230)]
    kinds = ["nb-check", "nb", "nb-focal", "nb", "nb-focal", "nb-check"]
    subs = ["notes → first message", "cached prefix + new message", "> 10% of window → preview", "> 90% next prompt → offload",
            "75% → summary + tail + notes", "final answer → note"]
    g = []
    for i, ((x, y), k, (name, _, _, _), sub) in enumerate(zip(pos, kinds, steps, subs)):
        g.append(f'<g data-motion-item data-step="{i + 1}" aria-label="Step {i + 1}: {E(name)}">'
                 f'<rect x="{x}" y="{y}" width="176" height="78" rx="6" class="mk"/><rect x="{x}" y="{y}" width="176" height="78" rx="6" class="{k}"/>'
                 f'<circle cx="{x + 16}" cy="{y + 16}" r="10" class="stepno"/><text x="{x + 16}" y="{y + 20}" text-anchor="middle" class="stepno-t">{i + 1}</text>'
                 f'<text x="{x + 88}" y="{y + 40}" text-anchor="middle" class="n-name">{E(name)}</text>'
                 f'<text x="{x + 88}" y="{y + 58}" text-anchor="middle" class="n-sub">{E(sub)}</text></g>')
    arrows = [
        '<path d="M208 109 H228" class="ar" marker-end="url(#am-a)"/>',
        '<path d="M408 109 H428" class="ar" marker-end="url(#am-a)"/>',
        '<path d="M608 109 H628" class="ar" marker-end="url(#am-a)"/>',
        '<path d="M720 150 V226" class="ar" marker-end="url(#am-a)"/><rect x="726" y="180" width="86" height="12" rx="2" class="mk"/><text x="769" y="189" text-anchor="middle" class="a-lab">CONTEXT GROWS</text>',
        '<path d="M628 269 H412" class="ar" marker-end="url(#am-a)"/><rect x="470" y="252" width="100" height="12" rx="2" class="mk"/><text x="520" y="261" text-anchor="middle" class="a-lab">LOOP UNTIL DONE</text>',
        '<path d="M232 269 H120 V152" class="ar-acc" marker-end="url(#am-b)"/><rect x="128" y="200" width="96" height="12" rx="2" class="mk"/><text x="176" y="209" text-anchor="middle" class="a-lab-acc">NEXT SESSION</text>',
    ]
    svg = (f'<svg class="dg" viewBox="0 0 860 340" style="min-width:800px;max-width:1000px" role="img" aria-labelledby="am-t am-d">'
           f'<title id="am-t">AutoMemory v2, one session</title><desc id="am-d">Recall, request, preview, guard, compaction and autosave, '
           f'in the order they act during a session; the saved answer is recalled in the next session.</desc>'
           f'<defs><marker id="am-a" markerWidth="8" markerHeight="6" refX="7" refY="3" orient="auto"><polygon points="0 0, 8 3, 0 6" class="hd"/></marker>'
           f'<marker id="am-b" markerWidth="8" markerHeight="6" refX="7" refY="3" orient="auto"><polygon points="0 0, 8 3, 0 6" class="hd-acc"/></marker></defs>'
           f'<rect width="860" height="340" class="bgp"/><text x="32" y="40" class="lane-t">ONE SESSION · EVERY STEP IS AUTOMATIC</text>'
           + "".join(arrows) + "".join(g) +
           '<line x1="32" y1="318" x2="828" y2="318" class="rule-line"/>'
           '<rect x="32" y="326" width="14" height="10" rx="2" class="nb-check"/><text x="52" y="335" class="n-sub">memory across sessions</text>'
           '<rect x="250" y="326" width="14" height="10" rx="2" class="nb-focal"/><text x="270" y="335" class="n-sub">shrinks the context</text>'
           '<rect x="440" y="326" width="14" height="10" rx="2" class="nb"/><text x="460" y="335" class="n-sub">keeps the cache valid</text>'
           '</svg>')
    chips = "".join(f'<button type="button" data-goto="{i}">{lab}</button>' for i, lab in
                    enumerate(["Overview"] + [f"{i + 1} {s[0]}" for i, s in enumerate(steps)]))
    arts = ['<article data-n="0"><div class="sd-main"><p class="sd-k">Overview</p><h4 class="sd-h">Six automatic steps, one loop</h4>'
            '<p>Nothing here depends on the model choosing to manage its memory. Each step runs at a fixed point of the loop, and only the compaction reset rewrites cached history.</p></div>'
            '<ol class="sd-list">' + "".join(f"<li><strong>{E(s[0])}</strong>: {E(s[1].lower())}.</li>" for s in steps) + "</ol></article>"]
    for i, (name, head, body, facts) in enumerate(steps):
        dl = "".join(f"<dt>{E(a)}</dt><dd>{E(b)}</dd>" for a, b in facts)
        arts.append(f'<article data-n="{i + 1}"><div class="sd-main"><p class="sd-k">Step {i + 1} of {n} · {E(name)}</p>'
                    f'<h4 class="sd-h">{E(head)}</h4><p>{E(body)}</p></div><dl class="sd-facts">{dl}</dl></article>')
    return (f'<div class="stepper" data-motion-root data-motion-mode="step" data-step-count="{n}" data-step-current="{n}" data-frame="static" '
            f'style="--motion-hold:1400ms"><div class="diagram">{svg}</div>'
            '<div data-motion-controls role="group" aria-label="AutoMemory playback controls">'
            '<button type="button" data-motion-action="prev">Previous</button><button type="button" data-motion-action="play" aria-pressed="false">Play</button>'
            '<button type="button" data-motion-action="pause" aria-pressed="true">Pause</button><button type="button" data-motion-action="next">Next</button>'
            '<button type="button" data-motion-action="replay">Replay</button><span class="keyboard-help">←/→ step · Space play/pause · R replay</span>'
            f'<span data-motion-status-visible aria-hidden="true">Step <span data-motion-step-label>{n}</span> of {n}</span></div>'
            '<p class="sr-only" data-motion-status role="status" aria-live="polite" aria-atomic="true"></p>'
            f'<div class="chips" role="group" aria-label="Jump to a step">{chips}</div>'
            f'<div class="stepdetail">{"".join(arts)}</div></div>')


# ------------------------------------------------------------------ 2. cache simulator
def simulator():
    return """
<div class="sim2" id="sim2">
  <div class="sim2-top">
    <span class="sim2-k">Strategy</span>
    <div class="seg" role="group" aria-label="Context strategy">
      <button type="button" data-strat="full" aria-pressed="true">Keep everything</button>
      <button type="button" data-strat="edit" aria-pressed="false">Edit history every step</button>
      <button type="button" data-strat="batch" aria-pressed="false">Edit in batches of 8</button>
      <button type="button" data-strat="v2" aria-pressed="false">AutoMemory v2</button>
    </div>
    <span class="sim2-k">Prices</span>
    <div class="seg" role="group" aria-label="Price route">
      <button type="button" data-route="cli" aria-pressed="true">Claude Code CLI</button>
      <button type="button" data-route="bedrock" aria-pressed="false">Bedrock</button>
    </div>
  </div>
  <figure class="chart"><div class="diagram"><svg class="dg" id="sim2-svg" viewBox="0 0 900 250" style="min-width:720px;max-width:100%" role="img" aria-labelledby="s2-t s2-d">
    <title id="s2-t">Prompt per step, split by how it is billed</title>
    <desc id="s2-d">Bars show each step's prompt: green is read from cache, red is written to cache, amber is uncached. The dashed line is a 32K window.</desc>
  </svg></div><div class="tip" hidden></div>
  <figcaption><span class="sw" style="background:var(--check)"></span>cache read (0.1×) <span class="sw" style="background:var(--warn)"></span>cache write (2× CLI, 1.25× Bedrock) <span class="sw" style="background:var(--amber)"></span>uncached (1×) · dashed line: a 32K window. Illustrative model, not measured: 40 steps, 1.2K-token results, a 6K-token result every 5th step.</figcaption></figure>
  <div class="sim2-ctl">
    <button type="button" class="btn btn-primary" id="sim2-play">Play</button>
    <input type="range" id="sim2-step" min="1" max="40" value="40" aria-label="Step">
    <span class="counter" id="sim2-at">step 40 / 40</span>
  </div>
  <div class="sim2-out">
    <div><b id="o-tok">—</b><span>prompt tokens so far</span></div>
    <div><b id="o-cost">—</b><span>cost in input-token units</span></div>
    <div><b id="o-rel">—</b><span>cost vs keeping everything</span></div>
    <div><b id="o-peak">—</b><span>peak prompt (window 32K)</span></div>
  </div>
  <p class="sim2-why" id="sim2-why" aria-live="polite"></p>
</div>"""


SIM_JS = r"""
(() => {
  const root = document.getElementById('sim2'); if (!root) return;
  const svg = document.getElementById('sim2-svg'); const tip = root.querySelector('.tip');
  const N = 40, W = 32000, SYS = 3000;
  const obs = Array.from({ length: N }, (_, i) => ((i + 1) % 5 === 0 ? 6000 : 1200));
  const WHY = {
    full: 'Each step re-sends the whole history. Almost all of it is a cache read, so tokens grow fast but cost grows slowly — until the window overflows.',
    edit: 'Every step edits an observation three steps back, so everything after the edit must be re-written to the cache at 2× the input price. Fewer tokens, more dollars.',
    batch: 'The same edit, applied to eight steps at once: the cache breaks once every eight steps instead of every step. This is why CADOC and AKV in blocks are cheaper.',
    v2: 'Large outputs enter as previews, so the context grows slower; one compaction at 75% of the window rewrites the cache once. Fewer tokens and fewer dollars.'
  };
  const PRICES = { cli: { read: 0.1, write: 2 }, bedrock: { read: 0.1, write: 1.25 } };
  let strat = 'full', route = 'cli', upto = N, timer = 0;
  const model = (s) => {
    // history = list of segment sizes; prefix cached up to `cachedLen` tokens of the previous request
    const rows = []; let hist = [], prevReq = 0, stable = 0;
    for (let t = 0; t < N; t++) {
      let o = obs[t];
      if (s === 'v2' && o > 0.1 * W) o = 750 + 150;
      hist.push({ size: o + 300 });
      let editAt = null;
      if (s === 'edit' && t >= 3) { const k = t - 3; if (hist[k].size > 600) { hist[k].size = 80; editAt = k; } }
      if (s === 'batch' && t >= 3 && (t + 1) % 8 === 0) {
        for (let k = 0; k < t - 2; k++) if (hist[k].size > 600) { hist[k].size = 80; editAt = editAt === null ? k : Math.min(editAt, k); }
      }
      let total = SYS + hist.reduce((a, h) => a + h.size, 0);
      if (s === 'v2' && total > 0.75 * W) { hist = [{ size: 1800 }, ...hist.slice(-2)]; editAt = 0; total = SYS + hist.reduce((a, h) => a + h.size, 0); }
      // cached part = the previous request's prefix that is unchanged
      let unchanged = prevReq;
      if (editAt !== null) unchanged = SYS + hist.slice(0, editAt).reduce((a, h) => a + h.size, 0);
      unchanged = Math.min(unchanged, total);
      const read = t === 0 ? 0 : unchanged; const write = total - read; const unc = 0;
      rows.push({ total, read, write, unc }); prevReq = total;
    }
    return rows;
  };
  const NS = 'http://www.w3.org/2000/svg';
  const el = (tag, attrs) => { const e = document.createElementNS(NS, tag); for (const k in attrs) e.setAttribute(k, attrs[k]); return e; };
  const fmt = (x) => x >= 1e6 ? (x / 1e6).toFixed(2) + 'M' : x >= 1e3 ? (x / 1e3).toFixed(0) + 'K' : String(Math.round(x));
  const cost = (rows, p) => rows.reduce((a, r) => a + r.read * p.read + r.write * p.write + r.unc, 0);
  const draw = () => {
    const rows = model(strat); const p = PRICES[route];
    const base = model('full');
    while (svg.lastChild && svg.lastChild.nodeName !== 'desc') svg.removeChild(svg.lastChild);
    svg.appendChild(el('rect', { width: 900, height: 250, class: 'bgp' }));
    const X0 = 56, X1 = 884, Y0 = 220, Y1 = 16; const peakAll = Math.max(...rows.map((r) => r.total)); const max = Math.max(60000, Math.ceil(peakAll / 30000) * 30000);
    const y = (v) => Y0 - (v / max) * (Y0 - Y1);
    Array.from({ length: max / 30000 + 1 }, (_, k) => k * 30000).forEach((v) => {
      svg.appendChild(el('line', { x1: X0, x2: X1, y1: y(v), y2: y(v), class: 'grid-l' }));
      const t = el('text', { x: X0 - 6, y: y(v) + 4, 'text-anchor': 'end', class: 'tick' }); t.textContent = fmt(v); svg.appendChild(t);
    });
    svg.appendChild(el('line', { x1: X0, x2: X1, y1: y(W), y2: y(W), class: 'win-l' }));
    const wl = el('text', { x: X1, y: y(W) - 5, 'text-anchor': 'end', class: 'a-lab-warn' }); wl.textContent = 'WINDOW 32K'; svg.appendChild(wl);
    const bw = (X1 - X0) / N;
    rows.forEach((r, i) => {
      if (i >= upto) return;
      const x = X0 + i * bw + 2, w = bw - 4;
      const g = el('g', { class: 'row', tabindex: '0', 'data-tip': `Step ${i + 1}: prompt ${fmt(r.total)} · cache read ${fmt(r.read)} · written ${fmt(r.write)}` });
      g.appendChild(el('rect', { x: x - 2, y: Y1, width: bw, height: Y0 - Y1, class: 'hit' }));
      g.appendChild(el('rect', { x, y: y(r.read), width: w, height: Y0 - y(r.read), class: 'bar-read' }));
      g.appendChild(el('rect', { x, y: y(r.read + r.write), width: w, height: y(r.read) - y(r.read + r.write), class: 'bar-write' }));
      svg.appendChild(g);
    });
    [1, 10, 20, 30, 40].forEach((s) => { const t = el('text', { x: X0 + (s - 0.5) * bw, y: 238, 'text-anchor': 'middle', class: 'tick' }); t.textContent = s; svg.appendChild(t); });
    const sub = rows.slice(0, upto), bsub = base.slice(0, upto);
    const tok = sub.reduce((a, r) => a + r.total, 0);
    const c = cost(sub, p), cb = cost(bsub, p);
    document.getElementById('o-tok').textContent = fmt(tok);
    document.getElementById('o-cost').textContent = fmt(c);
    document.getElementById('o-rel').textContent = Math.round((c / cb) * 100) + '%';
    const peak = Math.max(...sub.map((r) => r.total));
    document.getElementById('o-peak').textContent = fmt(peak) + (peak > W ? ' · overflow' : '');
    document.getElementById('sim2-at').textContent = `step ${upto} / ${N}`;
    document.getElementById('sim2-step').value = upto;
    document.getElementById('sim2-why').textContent = WHY[strat];
  };
  root.querySelectorAll('[data-strat]').forEach((b) => b.addEventListener('click', () => {
    strat = b.dataset.strat; root.querySelectorAll('[data-strat]').forEach((x) => x.setAttribute('aria-pressed', String(x === b))); draw();
  }));
  root.querySelectorAll('[data-route]').forEach((b) => b.addEventListener('click', () => {
    route = b.dataset.route; root.querySelectorAll('[data-route]').forEach((x) => x.setAttribute('aria-pressed', String(x === b))); draw();
  }));
  document.getElementById('sim2-step').addEventListener('input', (e) => { upto = Number(e.target.value); clearInterval(timer); timer = 0; document.getElementById('sim2-play').textContent = 'Play'; draw(); });
  const playBtn = document.getElementById('sim2-play');
  playBtn.addEventListener('click', () => {
    if (timer) { clearInterval(timer); timer = 0; playBtn.textContent = 'Play'; return; }
    if (matchMedia('(prefers-reduced-motion: reduce)').matches) { upto = N; draw(); return; }
    upto = 1; draw(); playBtn.textContent = 'Pause';
    timer = setInterval(() => { upto += 1; draw(); if (upto >= N) { clearInterval(timer); timer = 0; playBtn.textContent = 'Play'; } }, 120);
  });
  svg.addEventListener('pointermove', (ev) => {
    const row = ev.target.closest('[data-tip]'); if (!row) { tip.hidden = true; return; }
    const c = root.querySelector('.chart').getBoundingClientRect(); tip.textContent = row.dataset.tip; tip.hidden = false;
    tip.style.left = Math.max(80, Math.min(c.width - 80, ev.clientX - c.left)) + 'px'; tip.style.top = (ev.clientY - c.top - 14) + 'px';
  });
  svg.addEventListener('pointerleave', () => { tip.hidden = true; });
  draw();
})();
"""


# ------------------------------------------------------------------ 3. method map
MAP_ITEMS = [  # (label, column 0..3, driver row 0 harness / 1 side model / 2 model, verdict, tab id)
    ("Previews (v2)", 0, 0, "us", "am2"), ("Guard (v1)", 0, 0, "us", "am1"), ("Strands truncate", 0, 0, "mid", "strands"),
    ("ReFold folding", 1, 2, "mid", "refold"), ("CADOC cards", 1, 0, "mid", "cadoc"),
    ("ReSum", 2, 0, "ok", "resum"), ("SJC pruning", 2, 1, "mid", "sjc"), ("Obs. masking", 2, 0, "bad", "obsmask"),
    ("AKV drop", 2, 0, "bad", "akv"), ("AgentDiet", 2, 1, "bad", "agentdiet"), ("SelfCompact", 2, 2, "mid", "selfc"),
    ("Context-Folding", 2, 2, "mid", "folding"), ("CORAL resets", 2, 2, "bad", "coral"),
    ("Notes + recall", 3, 0, "us", "am1"), ("Note workspace", 3, 2, "ok", "workspace"), ("Raw-history RAG", 3, 0, "mid", "rawrag"),
    ("Memory systems", 3, 1, "bad", "extmem"), ("Turn control", 2, 0, "mid", "turn"),
]


def method_map():
    cols = ["INGESTION", "RENDER", "COMPACTION / EDITS", "ACROSS SESSIONS"]
    rows = ["HARNESS", "SIDE MODEL", "AGENT MODEL"]
    X0, Y0, CW, RH = 110, 46, 238, 96
    out = ['<svg class="dg" viewBox="0 0 1070 344" style="min-width:900px;max-width:1100px" role="img" aria-labelledby="mp-t mp-d">'
           '<title id="mp-t">Method map: where each method acts and who drives it</title>'
           '<desc id="mp-d">Columns are the loop point a method acts at; rows are who decides: the harness, a side model, or the agent model. '
           'Colour is the verdict: violet AutoMemory, green works on both models, amber mixed, red fails.</desc>'
           '<rect width="1070" height="344" class="bgp"/>']
    for i, c in enumerate(cols):
        out.append(f'<rect x="{X0 + i * CW + 4}" y="{Y0}" width="{CW - 8}" height="{RH * 3}" rx="4" class="map-col"/>'
                   f'<text x="{X0 + i * CW + CW / 2}" y="34" text-anchor="middle" class="lane-t">{c}</text>')
    for j, r in enumerate(rows):
        out.append(f'<text x="20" y="{Y0 + j * RH + RH / 2 + 4}" class="lane-t">{r}</text>')
        if j:
            out.append(f'<line x1="{X0}" y1="{Y0 + j * RH}" x2="{X0 + 4 * CW}" y2="{Y0 + j * RH}" class="rule-line"/>')
    slots = {}
    for label, c, r, v, tab in MAP_ITEMS:
        k = slots.get((c, r), 0)
        slots[(c, r)] = k + 1
        x = X0 + c * CW + 12 + (k % 2) * 110
        y = Y0 + r * RH + 12 + (k // 2) * 34
        w = 104
        lab = label
        out.append(f'<g class="map-chip {v}" tabindex="0" role="button" data-tab="{tab}" aria-label="{E(label)}: open its method card">'
                   f'<title>{E(label)}</title><rect x="{x}" y="{y}" width="{w}" height="26" rx="13"/>'
                   f'<text x="{x + w / 2}" y="{y + 17}" text-anchor="middle">{E(lab)}</text></g>')
    out.append("</svg>")
    return "".join(out)


MAP_JS = r"""
(() => {
  document.querySelectorAll('.map-chip').forEach((chip) => {
    const go = () => {
      const tab = document.getElementById('tab-' + chip.dataset.tab); if (!tab) return;
      tab.click(); document.getElementById('mt-cards').scrollIntoView({ behavior: 'smooth', block: 'start' }); tab.focus({ preventScroll: true });
    };
    chip.addEventListener('click', go);
    chip.addEventListener('keydown', (e) => { if (e.key === 'Enter' || e.key === ' ') { e.preventDefault(); go(); } });
  });
})();
"""


# ------------------------------------------------------------------ 4. score vs cost scatter
def scatter(points):
    """points: list of dict(model, group, label, cost, score, ceiling)."""
    X0, X1, Y0, Y1 = 70, 880, 330, 24
    xmax = 200
    x = lambda c: X0 + min(c, xmax) / xmax * (X1 - X0)
    y = lambda s: Y0 - s * (Y0 - Y1)
    out = ['<svg class="dg scatter" viewBox="0 0 900 370" style="min-width:760px;max-width:1100px" role="img" aria-labelledby="sp-t sp-d">'
           '<title id="sp-t">Mean score against mean cost, per method</title>'
           '<desc id="sp-d">Each dot is a method on one model: right is more expensive, up is more accurate. The shaded zone is at least the ceiling\'s accuracy (within 0.03) at below its cost.</desc>'
           '<rect width="900" height="370" class="bgp"/>']
    for m in ("haiku", "sonnet"):
        ceil = next(p["ceiling"] for p in points if p["model"] == m)
        out.append(f'<g class="m-{m}"><rect x="{X0}" y="{Y1}" width="{x(100) - X0}" height="{y(ceil - 0.03) - Y1}" class="zone"/>'
                   f'<text x="{X0 + 8}" y="{Y1 + 14}" class="zone-t">AT CEILING ACCURACY, CHEAPER</text></g>')
    for v in (0, 50, 100, 150, 200):
        out.append(f'<line x1="{x(v)}" y1="{Y1}" x2="{x(v)}" y2="{Y0}" class="grid-l"/><text x="{x(v)}" y="{Y0 + 16}" text-anchor="middle" class="tick">{v}%{"+" if v == 200 else ""}</text>')
    for v in (0, 0.25, 0.5, 0.75, 1.0):
        out.append(f'<line x1="{X0}" y1="{y(v)}" x2="{X1}" y2="{y(v)}" class="grid-l"/><text x="{X0 - 8}" y="{y(v) + 4}" text-anchor="end" class="tick">{v:.2f}</text>')
    out.append(f'<text x="{(X0 + X1) / 2}" y="364" text-anchor="middle" class="lane-s">mean cost vs the unoptimised ceiling →</text>'
               f'<text x="16" y="{(Y0 + Y1) / 2}" transform="rotate(-90 16 {(Y0 + Y1) / 2})" text-anchor="middle" class="lane-s">mean score →</text>')
    label_set = {"Unoptimised ceiling", "No memory (floor)", "Strands harness defaults", "ReFold", "CORAL (prompting)", "SelfCompact",
                 "AKV drop, every turn"}
    for m in ("haiku", "sonnet"):
        ceil = next(p["ceiling"] for p in points if p["model"] == m)
        inzone = [p["label"].replace(" (default)", "") for p in points if p["model"] == m and p["cost"] < 100 and p["score"] >= ceil - 0.03
                  and p["group"] != "anc"]
        out.append(f'<g class="m-{m}"><text x="{X0 + 8}" y="{Y1 + 30}" class="pt-lab">In the zone: {E(", ".join(inzone[:5]))}{" …" if len(inzone) > 5 else ""}</text></g>')
    for p in points:
        cx, cy = x(p["cost"]), y(p["score"])
        tip = f'{p["label"]} · {p["model"]}: score {p["score"]:.2f}, cost {p["cost"]:.0f}% of the ceiling' + (
            f' ({p["n"]}/4 tasks)' if p["n"] < 4 else "")
        lab = ""
        if p["label"] in label_set:
            lab = f'<text x="{cx + 9}" y="{cy + 4}" class="pt-lab">{E(p["label"].replace(" (default)", "").replace(" (prompting)", ""))}</text>'
        out.append(f'<g class="pt pt-{p["group"]} m-{p["model"]} row" tabindex="0" data-tip="{E(tip)}"><circle cx="{cx:.1f}" cy="{cy:.1f}" r="6.5"/>{lab}</g>')
    out.append("</svg>")
    return ('<div class="scatter-wrap" data-model="sonnet"><div class="seg" role="group" aria-label="Model">'
            '<button type="button" data-sm="haiku" aria-pressed="false">Haiku</button><button type="button" data-sm="sonnet" aria-pressed="true">Sonnet</button></div>'
            '<figure class="chart"><div class="diagram">' + "".join(out) + '</div><div class="tip" hidden></div>'
            '<figcaption>Means over the tasks each method ran on. Costs above 200% are drawn at the edge. Hover or focus a dot for its numbers. '
            '<span class="sw" style="background:var(--accent)"></span>published <span class="sw" style="background:var(--amber)"></span>Sep–Nov 2026 scan '
            '<span class="sw" style="background:var(--violet)"></span>AutoMemory <span class="sw" style="background:var(--muted)"></span>reference</figcaption></figure></div>')


SCATTER_JS = r"""
(() => {
  document.querySelectorAll('.scatter-wrap').forEach((w) => {
    w.querySelectorAll('[data-sm]').forEach((b) => b.addEventListener('click', () => {
      w.dataset.model = b.dataset.sm; w.querySelectorAll('[data-sm]').forEach((x) => x.setAttribute('aria-pressed', String(x === b)));
    }));
  });
})();
"""


# ------------------------------------------------------------------ 5. token mix (measured)
def token_mix(rows):
    """rows: list of (label, read, write, unc, cost)."""
    out = ['<svg class="dg" viewBox="0 0 900 %d" style="min-width:760px;max-width:1100px" role="img" aria-labelledby="tm-t tm-d">' % (40 + 34 * len(rows)),
           '<title id="tm-t">Where the prompt tokens go</title><desc id="tm-d">Measured share of prompt tokens read from cache, written to cache, or uncached, per method, Sonnet on research_corpus, with the median cost.</desc>',
           '<rect width="900" height="%d" class="bgp"/>' % (40 + 34 * len(rows))]
    X0, X1 = 250, 760
    for v in (0, 50, 100):
        xx = X0 + v / 100 * (X1 - X0)
        out.append(f'<text x="{xx}" y="16" text-anchor="middle" class="tick">{v}%</text>')
    out.append(f'<text x="{X1 + 70}" y="16" text-anchor="middle" class="tick">cost</text>')
    for i, (lab, r, w, u, c) in enumerate(rows):
        t = r + w + u or 1
        yy = 28 + i * 34
        x = X0
        tip = f"{lab}: {r / t:.0%} cache read, {w / t:.0%} cache write, {u / t:.0%} uncached; cost {c}% of the ceiling"
        segs = ""
        for val, cls in ((r, "bar-read"), (w, "bar-write"), (u, "bar-unc")):
            ww = val / t * (X1 - X0)
            if ww > 0.5:
                segs += f'<rect x="{x:.1f}" y="{yy}" width="{ww:.1f}" height="20" class="{cls}"/>'
            x += ww
        out.append(f'<g class="row" tabindex="0" data-tip="{E(tip)}"><rect x="0" y="{yy - 6}" width="900" height="32" class="hit"/>'
                   f'<text x="{X0 - 10}" y="{yy + 14}" text-anchor="end" class="n-body">{E(lab)}</text>{segs}'
                   f'<text x="{X1 + 70}" y="{yy + 14}" text-anchor="middle" class="val">{c}%</text></g>')
    out.append("</svg>")
    return ('<figure class="chart"><div class="diagram">' + "".join(out) + '</div><div class="tip" hidden></div>'
            '<figcaption><span class="sw" style="background:var(--check)"></span>cache read <span class="sw" style="background:var(--warn)"></span>cache write '
            '<span class="sw" style="background:var(--amber)"></span>uncached (the floor and ceiling run with caching off, by definition). '
            'Measured: Sonnet, research_corpus, all runs of each method. Cost = median per run vs the ceiling.</figcaption></figure>')


# ------------------------------------------------------------------ 6. timeline
def timeline():
    ev = [("22 Oct", "Phase 1", "single methods · chain_hunt, ledger_audit", "Haiku · Sonnet · Opus"),
          ("23 Oct", "Phase 2", "long-horizon tasks, model-normalised protocol", "erratum after two harness bugs"),
          ("24–26 Oct", "AutoMemory v1", "four long tasks + official memory systems", "model-robust on all four"),
          ("4 Nov", "Scan + 8 methods", "1,515 papers; 258 runs", "none beats AutoMemory"),
          ("4 Nov", "v2 + v3 ablation", "previews, folding, OpenClaw, SJC; 144 runs", "previews adopted"),
          ("5 Nov", "Sonnet seeds", "34 runs, decision rule fixed in advance", "automem_v2_strong")]
    n = len(ev)
    X0, X1 = 70, 870
    out = ['<svg class="dg" viewBox="0 0 940 210" style="min-width:860px;max-width:1100px" role="img" aria-labelledby="tl-t tl-d">'
           '<title id="tl-t">Experiment timeline</title><desc id="tl-d">From single methods on 22 October to the strong-model preset on 5 November.</desc>'
           '<rect width="940" height="210" class="bgp"/>'
           f'<line x1="{X0}" y1="70" x2="{X1}" y2="70" class="base-l"/>']
    for i, (d, h, s, r) in enumerate(ev):
        xx = X0 + i * (X1 - X0) / (n - 1)
        anchor = "start" if i == 0 else "end" if i == n - 1 else "middle"
        out.append(f'<g data-motion-item data-step="{i + 1}" aria-label="{E(h)}"><circle cx="{xx}" cy="70" r="8" class="tl-dot"/>'
                   f'<text x="{xx}" y="50" text-anchor="{anchor}" class="t-acc">{E(d)}</text>'
                   f'<text x="{xx}" y="98" text-anchor="{anchor}" class="n-name">{E(h)}</text>'
                   f'<text x="{xx}" y="116" text-anchor="{anchor}" class="n-sub">{E(s[:34])}</text>'
                   f'<text x="{xx}" y="130" text-anchor="{anchor}" class="n-sub">{E(s[34:68])}</text>'
                   f'<text x="{xx}" y="152" text-anchor="{anchor}" class="t-check">{E(r)}</text></g>')
    out.append('<text x="70" y="196" class="lane-s">Blocked: Bedrock validation (credentials) · SWE-bench Verified workdays (permission to run third-party tests)</text></svg>')
    return (f'<div class="stepper" data-motion-root data-motion-mode="reveal" data-step-count="{n}" data-step-current="{n}" data-frame="static" '
            f'style="--motion-hold:700ms"><div class="diagram">' + "".join(out) + '</div>'
            '<div data-motion-controls role="group" aria-label="Timeline playback controls">'
            '<button type="button" data-motion-action="prev">Previous</button><button type="button" data-motion-action="play" aria-pressed="false">Play</button>'
            '<button type="button" data-motion-action="pause" aria-pressed="true">Pause</button><button type="button" data-motion-action="next">Next</button>'
            '<button type="button" data-motion-action="replay">Replay</button>'
            f'<span data-motion-status-visible aria-hidden="true">Step <span data-motion-step-label>{n}</span> of {n}</span></div>'
            '<p class="sr-only" data-motion-status role="status" aria-live="polite" aria-atomic="true"></p></div>')


# ------------------------------------------------------------------ 7. setting chooser
def chooser():
    nodes = {  # id: (x, y, w, label, kind)
        "q1": (200, 16, 340, "Long task, many steps or several sessions?", "q"),
        "r0": (10, 104, 240, "Short task: full context with caching", "res"),
        "q2": (300, 104, 300, "Strong agent model (Sonnet-class)?", "q"),
        "q3": (40, 192, 300, "Smallest working context matters most?", "q"),
        "r3": (410, 192, 320, "automem_v2_strong + cheap summariser", "res"),
        "r1": (10, 280, 200, "automem_v2", "res"),
        "r2": (230, 280, 220, "automem_v2_slim", "res"),
    }
    edges = {  # id: (path, label, lx, ly)
        "e1n": ("M300 60 V80 H130 V102", "NO", 206, 76), "e1y": ("M450 60 V102", "YES", 458, 86),
        "e2n": ("M380 148 V168 H190 V190", "NO", 276, 164), "e2y": ("M540 148 V168 H570 V190", "YES", 578, 182),
        "e3n": ("M110 236 V278", "NO", 118, 262), "e3y": ("M280 236 V256 H340 V278", "YES", 348, 270),
    }
    out = ['<svg class="dg fc" viewBox="0 0 740 330" style="min-width:680px;max-width:900px" role="img" aria-labelledby="fc-t fc-d">'
           '<title id="fc-t">Which memory setting to use</title><desc id="fc-d">Short tasks need no memory layer; strong models use automem_v2_strong; otherwise automem_v2, or automem_v2_slim when the smallest context matters most.</desc>'
           '<rect width="740" height="330" class="bgp"/>'
           '<defs><marker id="fc-a" markerWidth="8" markerHeight="6" refX="7" refY="3" orient="auto"><polygon points="0 0, 8 3, 0 6" class="hd"/></marker></defs>']
    for eid, (d, lab, lx, ly) in edges.items():
        out.append(f'<path id="fc-{eid}" d="{d}" class="fe" marker-end="url(#fc-a)"/><text id="fcl-{eid}" x="{lx}" y="{ly}" class="fl">{lab}</text>')
    for nid, (x, y, w, lab, kind) in nodes.items():
        out.append(f'<g id="fc-{nid}" class="fn{" res" if kind == "res" else ""}"><rect x="{x}" y="{y}" width="{w}" height="44" rx="6"/>'
                   f'<text x="{x + w / 2}" y="{y + 27}" text-anchor="middle" class="{"n-name" if kind == "q" else "t-check"}">{E(lab)}</text></g>')
    out.append("</svg>")
    qs = [("q1", "Is it a long task: many steps, large tool outputs, or several sessions?"),
          ("q2", "Is the agent a strong model (Sonnet-class or above)?"),
          ("q3", "Does the smallest working context matter more than the last 10–15% of cost?")]
    qhtml = "".join(f'<div class="q" data-q="{qid}"><p>{E(t)}</p><div class="seg" role="group" aria-label="{E(t)}">'
                    f'<button type="button" data-a="y" aria-pressed="false">Yes</button><button type="button" data-a="n" aria-pressed="false">No</button></div></div>'
                    for qid, t in qs)
    return (f'<div class="chooser" id="chooser"><div>{qhtml}<div class="pick" id="pick" aria-live="polite"><span class="sim2-k">Recommended setting</span>'
            f'<span id="pick-name"><code>automem_v2</code></span><span class="note" id="pick-why">Answer the questions to follow the flowchart.</span></div></div>'
            f'<figure><div class="diagram">{"".join(out)}</div><figcaption>The path for your answers is highlighted.</figcaption></figure></div>')


CHOOSER_JS = r"""
(() => {
  const root = document.getElementById('chooser'); if (!root) return;
  const ans = { q1: 'y', q2: 'n', q3: 'n' };
  const PICK = {
    r0: ['full (provider caching), no memory layer', 'Short tasks fit the window; caching alone keeps re-sent history cheap.'],
    r1: ['automem_v2', 'The default: previews at ingestion, guard, ReSum at 75% with the last 2 steps, notes with recall and autosave. Haiku 0.88 at 85% of the unoptimised cost.'],
    r2: ['automem_v2_slim', 'v2 plus ReFold folding: the smallest peak context, at 10–16 points more cost and lower ledger_audit accuracy.'],
    r3: ['automem_v2_strong', 'v2 with SJC pruning of the summaries, judged by a cheaper model. Sonnet: 16/16 runs solved at 61% of the unoptimised cost.']
  };
  const render = () => {
    const on = new Set(); let res;
    on.add('q1');
    if (ans.q1 === 'n') { on.add('e1n'); res = 'r0'; }
    else { on.add('e1y'); on.add('q2');
      if (ans.q2 === 'y') { on.add('e2y'); res = 'r3'; }
      else { on.add('e2n'); on.add('q3'); if (ans.q3 === 'y') { on.add('e3y'); res = 'r2'; } else { on.add('e3n'); res = 'r1'; } } }
    on.add(res);
    root.querySelectorAll('.fn, .fe').forEach((n) => n.classList.toggle('on', on.has(n.id.replace('fc-', ''))));
    root.querySelectorAll('.fl').forEach((n) => n.classList.toggle('on', on.has(n.id.replace('fcl-', ''))));
    root.querySelector('[data-q="q2"]').classList.toggle('off', ans.q1 === 'n');
    root.querySelector('[data-q="q3"]').classList.toggle('off', ans.q1 === 'n' || ans.q2 === 'y');
    root.querySelectorAll('.q').forEach((q) => q.querySelectorAll('[data-a]').forEach((b) => b.setAttribute('aria-pressed', String(ans[q.dataset.q] === b.dataset.a))));
    document.getElementById('pick-name').innerHTML = '<code>' + PICK[res][0] + '</code>';
    document.getElementById('pick-why').textContent = PICK[res][1];
  };
  root.querySelectorAll('.q').forEach((q) => q.querySelectorAll('[data-a]').forEach((b) => b.addEventListener('click', () => { ans[q.dataset.q] = b.dataset.a; render(); })));
  render();
})();
"""

TOOLTIP_JS = r"""
(() => {
  document.querySelectorAll('.chart').forEach((chart) => {
    if (chart.closest('#sim2')) return;
    const tip = chart.querySelector('.tip'); if (!tip) return;
    chart.addEventListener('pointermove', (ev) => {
      const row = ev.target.closest('[data-tip]'); if (!row || !chart.contains(row)) { tip.hidden = true; return; }
      const c = chart.getBoundingClientRect(); tip.textContent = row.dataset.tip; tip.hidden = false;
      tip.style.left = Math.max(80, Math.min(c.width - 80, ev.clientX - c.left)) + 'px'; tip.style.top = Math.max(28, ev.clientY - c.top - 14) + 'px';
    });
    chart.addEventListener('pointerleave', () => { tip.hidden = true; });
    chart.addEventListener('focusin', (ev) => {
      const row = ev.target.closest('[data-tip]'); if (!row) return;
      const c = chart.getBoundingClientRect(), r = row.getBoundingClientRect(); tip.textContent = row.dataset.tip; tip.hidden = false;
      tip.style.left = (r.left - c.left + r.width / 2) + 'px'; tip.style.top = Math.max(28, r.top - c.top - 6) + 'px';
    });
    chart.addEventListener('focusout', () => { tip.hidden = true; });
  });
})();
"""
