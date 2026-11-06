# Efficient-Agent-Memory

A test bench for agent memory and context-window techniques — taken from tier-1 papers by Chinese AI labs — for
agents that call LLMs through **Amazon Bedrock** (no self-hosted models). Goal: measure each technique on its own
(accuracy, tokens, $ with prompt caching on, latency), then combine the best into a reusable memory skill.

- `docs/overview.html` — **the HTML overview**: objective, scope, each method's mechanism, diagrams and interactive charts of the results.
- `docs/problem_statement.md` — **why this matters**: what agent memory and token optimisation mean for everyday coding agents (Codex, Claude Code), their users' pain points, and how each is addressed here.
- `docs/plans/2026-11-05-next-steps.md` — **plan and proposal**: more Sonnet seeds for `compact=sjc` (running), and a realistic coding benchmark on SWE-bench Verified (Django) workdays, with cost estimates (≈ $95–215 together).
- `docs/new_methods.md` — the eight methods from the 2026-11 scan (Strands, CADOC, ReFold, SJC, AKV, raw-history RAG, CORAL, SelfCompact), plus NVIDIA's end-of-conversation handoff compaction (EoCC, `eocc`, AutoMemory `compact=handoff`): sources and deviations.
- `docs/literature/2026-11-scan/` — **literature scan, Sep–Nov 2026**: a sweep of 1,515 arXiv papers (40% of the most relevant have Chinese authors, 9% big US labs), plus the US labs, Chinese labs, repos and practitioners, and what it means for AutoMemory v2 and Bedrock.
- `docs/literature_review.md` — verified list of papers (venue, lab, repo, licence, Bedrock fit) and the implementation shortlist.
- `docs/papers/` — deep-reading notes for individual papers.
- `docs/methodology.md` — tasks, environment rules, metric definitions, procedure.
- `docs/automem.md` — **AutoMemory v1**, the combined memory skill: bench technique, framework-agnostic library (`eam/memory_skill.py`), MCP server (`python -m eam.mcp_server`).
- **Presets** (`eam/presets.py`): `automem_v2` (default; multi-session work that builds on earlier results), `automem_v2_strong` (strong agent models), `automem_v2_slim` (smallest working context), `automem_v2_lean` (independent tasks such as coding issues: no note workspace), `automem_v2_lean_handoff` (the same with NVIDIA's handoff recap: accuracy first under a tight window).
- `docs/backends.md` — how to run: Claude Code CLI (no Bedrock), Bedrock Converse, LiteLLM, Bedrock OpenAI-compatible endpoints, and a local gateway for third-party repos.
- `eam/` — harness: Bedrock Converse client, offline mock backend with a prompt-cache simulator, cost meter, agent loop with technique hooks, scored sample tasks.
- `papers/` — local PDF copies (git-ignored).

Status:
- Phase 1 (each method alone) has been measured on the Claude Code CLI route.
- Phase 2 (combinations, AutoMemory v1/v2, the 2026-11 methods, NVIDIA's handoff compaction, SWE-bench Verified workdays on 100 Django issues) has been measured too. Result reports, raw rows and logs are kept locally and are not part of the repository (`docs/results/`, `results/` are git-ignored).
- Each technique carries a provenance label: official prompt/algorithm, ported, baseline, or provisional (`eam/techniques/__init__.py`).

## Results

**Coverage:** about 2,800 benchmark runs on the Claude Code CLI route (Claude Haiku and Sonnet), measured up to 2026-11-06.

**The question:** which method gives the fewest tokens and dollars per solved task at full accuracy?

**Measurement** (details in `docs/methodology.md`):
- Each method is placed between the same model's **floor** and **ceiling** on the same task instances:
  - floor (`naive`): no memory, no caching, the task's window;
  - ceiling (`naive@native`): nothing removed, the model's own window, caching off.
- **Cost** is relative to the ceiling's cost, so 60% means 40% cheaper.
- **Peak** is the largest prompt sent, as a share of the ceiling's.
- Runs per cell: Haiku 4, Sonnet 2–4. Differences under about 0.1 in score or 15 points in cost are within run-to-run noise.

### 1. Four long synthetic tasks

The tasks (`docs/methodology.md` §2):

| Task | Sessions | Window | Work |
|---|---|---|---|
| `research_corpus` | 1 | 40K | multi-hop research |
| `ops_stream` | 10 | 32K | stock keeping with corrections |
| `ledger_audit` | 3 | 48K | data larger than the window |
| `repo_debug` | 2 | 16K | real `pytest` |

Each cell is the mean over the four tasks: **score · cost vs ceiling · runs fully solved · peak context vs ceiling**.

| Method | Developer | Haiku | Sonnet |
|---|---|---|---|
| No memory (floor) | — | 0.21 · 27% · 1/16 · 34% | 0.17 · 38% · 1/16 · 48% |
| Unoptimised ceiling | — | 0.88 · 100% · 9/16 · 100% | 0.95 · 100% · 12/16 · 100% |
| Workspace + ReSum (best phase-1 combination) | USTC / Alibaba Tongyi | 0.89 · 126% · 11/16 · 40% | 0.94 · 71% · 8/10 · 42% |
| MemoryOS / LightMem / Nemori + ReSum (3 tasks) | BUPT+Tencent / ZJU / Fudan+Shanda | 0.54–0.61 · 116–184% | — |
| Strands harness defaults | AWS | 0.59 · 125% · 7/16 · 35% | 0.88 · 148% · 4/8 · 43% |
| CADOC | SJTU | 0.43 · 107% · 5/16 · 44% | 0.86 · 83% · 4/8 · 40% |
| ReFold | UCSB + Intel | 0.43 · 56% · 3/16 · 41% | 0.97 · 106% · 7/8 · 38% |
| SJC on ReSum | University of Virginia | 0.80 · 136% · 7/16 · 42% | 0.94 · 80% · 7/8 · 40% |
| OpenClaw + SJC | University of Virginia | 0.88 · 90% · 10/16 · 39% | 0.87 · 68% · 5/8 · 39% |
| AKV rolling drop | Tsinghua + CUHK | 0.45 · 81% · 4/16 · 39% | 0.60 · 68% · 3/8 · 43% |
| Raw-history RAG (3 tasks) | Memory Tax studies | 0.52 · 105% · 1/12 · 41% | 0.99 · 199% · 4/6 · 48% |
| CORAL (prompting-only) | CUHK + Tencent + HKUST | 0.15 · 66% · 0/16 · 46% | 0.38 · 45% · 1/8 · 48% |
| SelfCompact | Apple + JHU | 0.75 · 179% · 6/16 · 38% | 0.93 · 130% · 6/8 · 30% |
| AutoMemory v1 | this repo | 0.83 · 86% · 7/16 · 34% | 0.98 · 68% · 14/16 · 36% |
| **AutoMemory v2** (`automem_v2`) | this repo | **0.88 · 85% · 11/16** · 35% | 0.99 · **58%** · 13/16 · 37% |
| **AutoMemory v2 strong** (`automem_v2_strong`) | this repo | 0.81 · 114% · 7/16 · 35% | **1.00 · 61% · 16/16** · 37% |
| AutoMemory v2 slim (`automem_v2_slim`) | this repo | 0.87 · 90% · 6/16 · **30%** | 1.00 · 78% · 7/8 · **30%** |
| EoCC handoff compaction alone (`eocc`) | NVIDIA | 0.73 · 89% · 6/16 · 42% | 0.91 · 126% · 9/16 · 46% |
| AutoMemory v2 with the handoff recap (`compact=handoff`) | this repo + NVIDIA | 0.83 · 79% · 8/16 · 35% | 1.00 · 66% · 13/16 · 37% |
| … recap written by the Haiku summariser (`compact=handoff_aux`) | this repo + NVIDIA | — | 0.99 · 58% · 12/16 · 38% |

Notes on the table:
- On Sonnet, AutoMemory uses Haiku as its summariser.
- The phase-1 methods tested on earlier tasks are left out above. On those tasks: observation masking cost up to 608%, AgentDiet 410%, and turn control had no effect. Context-Folding solved Sonnet `research_corpus` at 20% but failed `ops_stream` and `ledger_audit`.

### 2. Real repositories: SWE-bench Verified workdays

**Setup:**
- 100 real Django issues (SWE-bench Verified, Django 4.0–5.0, all difficulties), grouped into 20 workdays of 5 consecutive sessions.
- Each session starts from a fresh checkout at its issue's commit.
- Grading follows SWE-bench: the test modules touched by the issue's test patch are run, the log is parsed with SWE-bench's Django parser, and the issue is resolved iff every FAIL_TO_PASS and PASS_TO_PASS test passes.
- Two emulated windows from the NVIDIA paper (16K with compaction at 12K; 32K with compaction at 24K), plus the model's own window. 400 runs.

Each cell: **issues resolved of 100 · cost vs ceiling · $ per resolved issue**.

| Setting | Window | Haiku | Sonnet |
|---|---|---|---|
| Ceiling: full history, no cache | own | 82 · 100% · $0.015 | 88 · 100% · $0.165 |
| Full history, cached (no memory layer) | own | 79 · 86% · $0.013 | 86 · 84% · $0.142 |
| Full history, cached | 32K | 77 · **62%** · **$0.010** | 87 · 100% · $0.168 |
| AutoMemory v2 lean (`automem_v2_lean`) | 32K | 78 · 98% · $0.015 | 87 · 92% · $0.154 |
| AutoMemory v2 lean + handoff (`automem_v2_lean_handoff`) | 32K | 77 · 87% · $0.014 | **89 · 79% · $0.130** |
| EoCC alone (`eocc`) | 32K | 82 · 88% · $0.013 | 84 · 87% · $0.151 |
| AutoMemory v2 lean | 16K | 76 · 83% · $0.013 | 86 · **73% · $0.123** |
| **AutoMemory v2 lean + handoff** | 16K | **81** · 89% · $0.013 | **88** · 89% · $0.147 |
| … recap written by the Haiku summariser | 16K | — | 86 · 90% · $0.152 |
| EoCC alone | 16K | 72 · 93% · $0.016 (15 overflows) | 83 · 100% · $0.175 (7 overflows) |

Notes:
- At 32K the window rarely binds (sessions peak at 16–21K; 3–9 compactions in 100 issues), so the settings there are within noise of each other.
- At 16K, paired by issue, handoff resolves 7 issues ReSum misses and misses 2 it resolves (Haiku); 3 and 1 (Sonnet). The direction is consistent but not yet certain.
- An earlier 40-issue run (Django 4.2/5.0) graded only the tests whose ids name a test method, 63% of the official tests; every setting was graded the same way, so its comparisons hold, and it is superseded by this table.

### What the results show

1. **Fewer tokens is not fewer dollars.**
   - Re-sent history costs 0.05–0.1× the input price while it stays in the prompt cache. Rewriting earlier history is billed as cache writes, at 2× on the CLI and 1.25× on Bedrock.
   - Methods that edit history every step therefore cost more than they save. AKV rolling drop on Sonnet `research_corpus` costs 93% when it drops every turn and 22% when it drops in blocks of 8, at the same score.
2. **Steps the harness applies by itself work on both models.** Previews of large outputs at ingestion, automatic recall of notes, and compaction at a fixed trigger all held up on Haiku and Sonnet. Methods that need the model to manage its own memory fail on the weaker model:
   - CORAL's tools were barely used.
   - ReFold's Haiku recovery was 0.25.
3. **Plain notes beat engineered memory systems.** MemoryOS, LightMem and Nemori scored 0.2–0.5 lower than a note workspace with the same compaction.
4. **On coding work under a tight window, NVIDIA's handoff recap beats ReSum's summary.** Its fields (applied changes and whether verified, dead ends, the next command) are what a coding session needs after a reset: at 16K it brings both models to the ceiling's accuracy or within one issue of it (81/100 against 82; 88/100 against 88) for 6–16 points more cost, because the agent writes about 45% more after a reset. On the synthetic multi-session tasks it only ties ReSum. The paper's method on its own, without AutoMemory's guard, previews and notes, overflowed the window and resolved the fewest issues.
5. **Match the memory layer to the work.**
   - **Sessions that build on earlier results** (synthetic multi-session tasks): the note workspace is essential, and `automem_v2` / `automem_v2_strong` are best.
   - **Independent tasks** (one coding issue per session): the workspace's note-taking is overhead, about 50% more tool calls. `automem_v2_lean` (previews, guard and compaction only) is the cheapest memory layer (73% of the ceiling's cost on Sonnet at 16K); `automem_v2_lean_handoff` is the accuracy-first choice.

| Work | Preset |
|---|---|
| Multi-session work that builds on earlier results | `automem_v2`; `automem_v2_strong` for strong agent models, with a cheaper summariser (`#aux=`) |
| Independent tasks (coding issues, tickets), cost first | `automem_v2_lean` |
| Independent tasks, accuracy first, tight window or long sessions | `automem_v2_lean_handoff` |
| Smallest working context first | `automem_v2_slim` |
| Short sessions on a large window | full history with provider caching may be enough |

**Limitations:**
- All runs use the Claude Code CLI route at list prices. Bedrock validation is blocked on credentials, and Codex/OpenAI pricing has not been re-priced.
- The synthetic tasks emulate small windows to create memory pressure.
- The SWE-bench set is 100 issues from one repository (Django).

Quick start with your Claude Code CLI (no Bedrock needed):

```bash
python -m venv .venv && .venv/bin/pip install pytest
.venv/bin/python -m eam.smoke --route claude-cli --model cc-haiku
.venv/bin/python -m eam.bench run --task needle_research -t full -t offload --backend claude-cli --model cc-haiku --aux-model cc-haiku --n 1
```

Quick start (offline):

```bash
python -m venv .venv && .venv/bin/pip install pytest boto3
.venv/bin/python -m pytest -q
.venv/bin/python -m eam.bench run --task needle_research -t full -t cache_layout --n 2
```

On Bedrock: copy `config/models.example.json` to `config/models.json`, fill in model ids and prices, then
`python -m eam.bench suite individual --backend converse --model sonnet --aux-model haiku`
(or `--backend litellm` / `mantle` / `bedrock-openai`; see `docs/backends.md`).
