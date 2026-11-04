# The eight methods from the 2026-11 literature scan, measured (2026-11-04)

**Question.** The Sep–Nov 2026 scan ([`../literature/2026-11-scan/README.md`](../literature/2026-11-scan/README.md)) found eight methods for agent memory and token cost that had not been tried here:
- the Strands harness defaults (AWS);
- CADOC (SJTU);
- ReFold (UCSB + Intel);
- SJC with its OpenClaw host compactor (University of Virginia);
- AKV rolling drop (Tsinghua + CUHK);
- raw-history RAG (the "Memory Tax" studies);
- CORAL (CUHK + Tencent + HKUST);
- SelfCompact (Apple + JHU).

Does any of them save tokens and dollars at full accuracy on the four long tasks, on both Haiku and Sonnet? Each one is implemented as faithfully as the API allows; sources and deviations are in [`../new_methods.md`](../new_methods.md).

**Answer.**
- **No new method beats AutoMemory v2 across the board.** v2 is the only setting that recovers at least 0.9 of the gap between floor and ceiling on 3 of 4 tasks on Haiku and 4 of 4 on Sonnet, at below the ceiling's cost on both models (85% and 64%).
- **Every new method is strong somewhere and weak somewhere else.** The scaffold-only ones (OpenClaw / SJC, Strands, SelfCompact) can be model-robust. The ones that need the model to manage its own memory (ReFold, CORAL) are fine on Sonnet at best and fail on Haiku.
- **The one candidate for AutoMemory's next version is OpenClaw's structured compaction, with or without SJC's pruning.**
  - It was model-robust on `ledger_audit` and `ops_stream`.
  - It was the cheapest strong compactor on several cells: Haiku `research_corpus` 28%, Sonnet `ops_stream` 61–69%.
  - It was weak on `repo_debug` (0.50–0.88).

Runs per cell: 4 for Haiku, 2 for Sonnet (3 on two of the Sonnet anchors). A difference under about 0.1 in score, or about 15 points in cost, is within run-to-run noise.

## Setup

- **Tasks and windows:** the four long tasks of the AutoMemory evaluation, run on the Claude Code CLI:
  - `research_corpus`: 1 session, 40K window;
  - `ops_stream`: 10 sessions, 32K window;
  - `ledger_audit`: 3 sessions, 48K window;
  - `repo_debug`: 2 sessions, 16K window, real `pytest`.
- **Anchors and comparators** (`naive`, `naive@native`, `fs_workspace+resum`, `automem`, `automem#aux=cc-haiku`): the v4 runs, unchanged. AutoMemory v2 (`automem:ingest=0.1`) comes from [`2026-11-04-automemory-v2.md`](2026-11-04-automemory-v2.md).
- **Single-session task** (`research_corpus`): each method runs alone.
- **Multi-session tasks:**
  - Each within-session method gets the same note workspace (`fs_workspace+X`), so the only difference from `fs_workspace+resum` is the context method.
  - Raw-history RAG replaces the workspace (`raw_rag+resum`).
  - Strands runs alone, because it brings its own long-term memory.
- **Compaction trigger:** the ReSum-family hosts (`sjc`, `openclaw`) fire at the same trigger as ReSum (K = 33 / 26 / 40 / 13).
- **Completeness:** all 258 runs finished; none errored.

## Scoreboard (means over the four tasks)

Columns:
- **Recovery** = (score − floor) / (ceiling − floor), where floor is `naive` and ceiling is `naive@native` on the same task and model.
- **Cost** and **peak context** are ratios to the ceiling's median on each task.
- **Solved** counts runs in which every session was answered fully.

"AutoMemory v1/v2" on Sonnet means the variant with Haiku as the summariser (`#aux=cc-haiku`).

| Method | Model | Mean score | Lowest task score | Mean recovery | Tasks recovered ≥ 0.9 | Runs solved | Mean cost | Mean peak |
|---|---|---|---|---|---|---|---|---|
| workspace + ReSum (best single method of v1) | haiku | 0.89 | 0.75 | 0.96 | 3/4 | 11/16 | 126% | 40% |
| workspace + ReSum (best single method of v1) | sonnet | 0.93 | 0.75 | 0.96 | 3/4 | 8/10 | 75% | 42% |
| AutoMemory v1 | haiku | 0.83 | 0.75 | 0.89 | 2/4 | 7/16 | 86% | 35% |
| AutoMemory v1 | sonnet | 1.00 | 1.00 | 1.04 | 4/4 | 10/10 | 72% | 37% |
| **AutoMemory v2** | haiku | 0.88 | 0.75 | 0.99 | 3/4 | 11/16 | 85% | 35% |
| **AutoMemory v2** | sonnet | 0.98 | 0.93 | 1.02 | 4/4 | 6/8 | 64% | 37% |
| OpenClaw + SJC | haiku | 0.88 | 0.75 | 0.91 | 2/4 | 10/16 | 90% | 39% |
| OpenClaw + SJC | sonnet | 0.87 | 0.50 | 0.87 | 3/4 | 5/8 | 71% | 40% |
| OpenClaw (SJC's host) | haiku | 0.79 | 0.62 | 0.75 | 2/4 | 8/16 | 122% | 42% |
| OpenClaw (SJC's host) | sonnet | 0.94 | 0.75 | 0.96 | 3/4 | 7/8 | 75% | 42% |
| SJC on ReSum | haiku | 0.80 | 0.57 | 0.86 | 1/4 | 7/16 | 136% | 42% |
| SJC on ReSum | sonnet | 0.94 | 0.75 | 0.96 | 3/4 | 7/8 | 83% | 40% |
| SelfCompact | haiku | 0.75 | 0.42 | 0.78 | 1/4 | 6/16 | 179% | 37% |
| SelfCompact | sonnet | 0.93 | 0.75 | 0.95 | 3/4 | 6/8 | 138% | **30%** |
| Strands harness | haiku | 0.59 | 0.11 | 0.61 | 2/4 | 7/16 | 125% | 35% |
| Strands harness | sonnet | 0.88 | 0.72 | 0.91 | 2/4 | 4/8 | 161% | 43% |
| ReFold | haiku | 0.43 | 0.25 | 0.25 | 0/4 | 3/16 | 56% | 41% |
| ReFold | sonnet | 0.97 | 0.90 | 1.01 | 3/4 | 7/8 | 111% | 39% |
| CADOC | haiku | 0.42 | 0.03 | 0.37 | 0/4 | 5/16 | 107% | 44% |
| CADOC | sonnet | 0.86 | 0.50 | 0.86 | 3/4 | 4/8 | 87% | 40% |
| AKV drop, every turn | haiku | 0.46 | 0.00 | 0.33 | 1/4 | 4/16 | 81% | 39% |
| AKV drop, every turn | sonnet | 0.60 | 0.17 | 0.54 | 2/4 | 3/8 | 73% | 44% |
| AKV drop, blocks of 8 | haiku | 0.21 | 0.00 | −0.12 | 0/4 | 0/16 | 46% | 42% |
| AKV drop, blocks of 8 | sonnet | 0.62 | 0.00 | 0.58 | 2/4 | 3/8 | 51% | 44% |
| CORAL | haiku | 0.14 | 0.00 | −0.21 | 0/4 | 0/16 | 66% | 46% |
| CORAL | sonnet | 0.38 | 0.00 | 0.34 | 0/4 | 1/8 | 47% | 48% |

Raw-history RAG was run only on the three multi-session tasks (`ops_stream`, `ledger_audit`, `repo_debug`):

| Model | Scores (ops / ledger / repo) | Cost (ops / ledger / repo) |
|---|---|---|
| Haiku | 0.58 / 0.38 / 0.62 | 109% / 117% / 89% |
| Sonnet | 0.97 / 1.00 / 1.00 | 463% / 91% / 90% |

## Per task, model-normalised

Each cell gives: recovery [range over instances] (Δscore over the floor) · runs solved · cost vs `naive@native`.

A verdict of **model-robust** means a recovery of at least 0.5 on every model where recovery is defined. On Sonnet the AutoMemory rows with Haiku as the summariser carry a different spec name, so they appear as their own "one model only" rows.

Generated by `python -m eam.bench.analyze --robust results/v5_report_rows.jsonl`.

<!-- ROBUST -->
### ledger_audit: anchors per model (means over instances)

| model | instances | floor score (`naive`) | ceiling score (unlimited context) | headroom | floor $ | `full@native` $ | `naive@native` $ (cost reference) |
|---|---|---|---|---|---|---|---|
| cc-haiku | 4 | 0.00 | 0.82 | 0.82 | 0.007 | nan | 0.176 |
| cc-sonnet | 3 | 0.00 | 0.85 | 0.85 | 0.292 | nan | 1.172 |

### ledger_audit: method effect relative to each model's own floor and ceiling

| method | cc-haiku: recovery (Δscore) · success · $ vs `naive@native` | cc-sonnet: recovery (Δscore) · success · $ vs `naive@native` | verdict |
|---|---|---|---|
| `automem` | 1.13 [0.72…1.55] (+0.85) · 1/4 · 118% | 1.19 [1.00…1.29] (+1.00) · 3/3 · 111% | model-robust |
| `automem#aux=cc-haiku` | — | 1.19 [1.00…1.29] (+1.00) · 3/3 · 90% | recovers (one model only) |
| `automem:ingest=0.1` | 1.11 [0.93…1.50] (+0.89) · 3/4 · 86% | — | recovers (one model only) |
| `automem:ingest=0.1#aux=cc-haiku` | — | 1.14 [1.00…1.29] (+1.00) · 2/2 · 99% | recovers (one model only) |
| `fs_workspace+akv_drop` | 0.00 [0.00…0.00] (+0.00) · 0/4 · 43% | 0.21 [0.00…0.43] (+0.17) · 0/2 · 90% | not effective |
| `fs_workspace+akv_drop:keep=8,block=8` | 0.00 [0.00…0.00] (+0.00) · 0/4 · 48% | 0.00 [0.00…0.00] (+0.00) · 0/2 · 70% | not effective |
| `fs_workspace+cadoc` | 0.03 [0.00…0.08] (+0.03) · 0/4 · 117% | 1.14 [1.00…1.29] (+1.00) · 2/2 · 103% | model-dependent |
| `fs_workspace+coral` | 0.00 [0.00…0.00] (+0.00) · 0/4 · 33% | 0.38 [0.33…0.43] (+0.33) · 0/2 · 66% | not effective |
| `fs_workspace+openclaw:max_context_k=40` | 1.16 [1.00…1.64] (+0.92) · 3/4 · 85% | 1.14 [1.00…1.29] (+1.00) · 2/2 · 120% | model-robust |
| `fs_workspace+openclaw:max_context_k=40,sjc=true` | 1.14 [0.78…1.50] (+0.89) · 2/4 · 110% | 1.14 [1.00…1.29] (+1.00) · 2/2 · 122% | model-robust |
| `fs_workspace+refold` | 0.25 [0.00…0.67] (+0.25) · 0/4 · 58% | 1.14 [1.00…1.29] (+1.00) · 2/2 · 138% | model-dependent |
| `fs_workspace+resum:max_context_k=40` | 1.24 [1.00…1.64] (+0.97) · 3/4 · 102% | 1.19 [1.00…1.29] (+1.00) · 3/3 · 119% | model-robust |
| `fs_workspace+selfcompact` | 1.15 [0.72…1.64] (+0.86) · 2/4 · 171% | 1.14 [1.00…1.29] (+1.00) · 2/2 · 184% | model-robust |
| `fs_workspace+sjc:max_context_k=40` | 0.77 [0.39…1.27] (+0.57) · 0/4 · 110% | 1.14 [1.00…1.29] (+1.00) · 2/2 · 105% | model-robust |
| `raw_rag+resum:max_context_k=40` | 0.48 [0.39…0.64] (+0.38) · 0/4 · 118% | 1.14 [1.00…1.29] (+1.00) · 2/2 · 87% | model-dependent |
| `strands` | 1.15 [0.44…1.64] (+0.86) · 3/4 · 56% | 1.14 [1.00…1.29] (+1.00) · 2/2 · 34% | model-robust |

### ops_stream: anchors per model (means over instances)

| model | instances | floor score (`naive`) | ceiling score (unlimited context) | headroom | floor $ | `full@native` $ | `naive@native` $ (cost reference) |
|---|---|---|---|---|---|---|---|
| cc-haiku | 4 | 0.20 | 0.96 | 0.76 | 0.049 | nan | 0.378 |
| cc-sonnet | 2 | 0.19 | 1.00 | 0.81 | 0.495 | nan | 1.747 |

### ops_stream: method effect relative to each model's own floor and ceiling

| method | cc-haiku: recovery (Δscore) · success · $ vs `naive@native` | cc-sonnet: recovery (Δscore) · success · $ vs `naive@native` | verdict |
|---|---|---|---|
| `automem` | 0.84 [0.49…1.10] (+0.64) · 0/4 · 69% | 0.99 [0.98…1.00] (+0.80) · 1/2 · 212% | model-robust |
| `automem#aux=cc-haiku` | — | 1.00 [1.00…1.00] (+0.81) · 2/2 · 122% | recovers (one model only) |
| `automem:ingest=0.1` | 0.88 [0.70…1.02] (+0.67) · 1/4 · 76% | — | recovers (one model only) |
| `automem:ingest=0.1#aux=cc-haiku` | — | 0.91 [0.84…0.98] (+0.74) · 0/2 · 79% | recovers (one model only) |
| `fs_workspace+akv_drop` | 0.38 [0.13…1.12] (+0.28) · 1/4 · 41% | 0.98 [0.96…1.00] (+0.79) · 1/2 · 63% | model-dependent |
| `fs_workspace+akv_drop:keep=8,block=8` | 0.25 [0.13…0.38] (+0.19) · 0/4 · 39% | 0.99 [0.98…1.00] (+0.80) · 1/2 · 63% | model-dependent |
| `fs_workspace+cadoc` | 0.13 [0.00…0.39] (+0.10) · 0/4 · 98% | 0.93 [0.88…0.98] (+0.75) · 0/2 · 121% | model-dependent |
| `fs_workspace+coral` | 0.16 [0.00…0.26] (+0.12) · 0/4 · 30% | 0.62 [0.25…1.00] (+0.51) · 1/2 · 69% | model-dependent |
| `fs_workspace+openclaw:max_context_k=26` | 0.90 [0.74…1.08] (+0.68) · 1/4 · 71% | 1.00 [1.00…1.00] (+0.81) · 2/2 · 69% | model-robust |
| `fs_workspace+openclaw:max_context_k=26,sjc=true` | 0.88 [0.64…1.04] (+0.68) · 2/4 · 105% | 0.96 [0.93…1.00] (+0.78) · 1/2 · 61% | model-robust |
| `fs_workspace+refold` | 0.57 [0.00…1.02] (+0.44) · 1/4 · 36% | 0.88 [0.75…1.00] (+0.71) · 1/2 · 129% | model-robust |
| `fs_workspace+resum:max_context_k=26` | 0.99 [0.81…1.12] (+0.75) · 2/4 · 100% | 0.98 [0.96…1.00] (+0.79) · 1/2 · 81% | model-robust |
| `fs_workspace+selfcompact` | 0.86 [0.73…1.12] (+0.65) · 1/4 · 105% | 0.97 [0.95…1.00] (+0.79) · 1/2 · 202% | model-robust |
| `fs_workspace+sjc:max_context_k=26` | 0.82 [0.66…1.02] (+0.63) · 1/4 · 138% | 1.00 [1.00…1.00] (+0.81) · 2/2 · 63% | model-robust |
| `raw_rag+resum:max_context_k=26` | 0.48 [0.45…0.51] (+0.37) · 0/4 · 114% | 0.96 [0.95…0.98] (+0.78) · 0/2 · 463% | model-dependent |
| `strands` | 0.25 [0.13…0.38] (+0.19) · 0/4 · 165% | 0.74 [0.60…0.87] (+0.59) · 0/2 · 513% | model-dependent |

### repo_debug: anchors per model (means over instances)

| model | instances | floor score (`naive`) | ceiling score (unlimited context) | headroom | floor $ | `full@native` $ | `naive@native` $ (cost reference) |
|---|---|---|---|---|---|---|---|
| cc-haiku | 4 | 0.62 | 1.00 | 0.38 | 0.018 | nan | 0.027 |
| cc-sonnet | 2 | 0.25 | 1.00 | 0.75 | 0.200 | nan | 0.343 |

### repo_debug: method effect relative to each model's own floor and ceiling

| method | cc-haiku: recovery (Δscore) · success · $ vs `naive@native` | cc-sonnet: recovery (Δscore) · success · $ vs `naive@native` | verdict |
|---|---|---|---|
| `automem` | 0.67 [0.00…1.00] (+0.25) · 3/4 · 92% | 1.00 [1.00…1.00] (+0.75) · 2/2 · 83% | model-robust |
| `automem#aux=cc-haiku` | — | 1.00 [1.00…1.00] (+0.75) · 2/2 · 61% | recovers (one model only) |
| `automem:ingest=0.1` | 1.00 [1.00…1.00] (+0.38) · 4/4 · 123% | — | recovers (one model only) |
| `automem:ingest=0.1#aux=cc-haiku` | — | 1.00 [1.00…1.00] (+0.75) · 2/2 · 52% | recovers (one model only) |
| `fs_workspace+akv_drop` | 0.33 [0.00…1.00] (+0.00) · 1/4 · 151% | 0.00 [0.00…0.00] (+0.00) · 0/2 · 41% | not effective |
| `fs_workspace+akv_drop:keep=8,block=8` | -0.33 [-1.00…0.00] (-0.38) · 0/4 · 90% | 0.25 [0.00…0.50] (+0.25) · 0/2 · 46% | not effective |
| `fs_workspace+cadoc` | 1.00 [1.00…1.00] (+0.25) · 3/4 · 145% | 0.25 [0.00…0.50] (+0.25) · 0/2 · 98% | model-dependent |
| `fs_workspace+coral` | -0.33 [-1.00…0.00] (-0.38) · 0/4 · 176% | 0.25 [0.00…0.50] (+0.25) · 0/2 · 43% | not effective |
| `fs_workspace+openclaw:max_context_k=13` | 0.33 [0.00…1.00] (+0.00) · 1/4 · 303% | 0.75 [0.50…1.00] (+0.50) · 1/2 · 82% | model-dependent |
| `fs_workspace+openclaw:max_context_k=13,sjc=true` | 0.33 [0.00…1.00] (+0.12) · 2/4 · 106% | 0.25 [0.00…0.50] (+0.25) · 0/2 · 72% | not effective |
| `fs_workspace+refold` | 0.33 [-1.00…1.00] (-0.12) · 2/4 · 79% | 1.00 [1.00…1.00] (+0.75) · 2/2 · 140% | model-dependent |
| `fs_workspace+resum:max_context_k=13` | 0.67 [0.00…1.00] (+0.25) · 3/4 · 282% | 0.75 [0.50…1.00] (+0.50) · 1/2 · 70% | model-robust |
| `fs_workspace+selfcompact` | 1.00 [1.00…1.00] (+0.25) · 3/4 · 343% | 0.75 [0.50…1.00] (+0.50) · 1/2 · 121% | model-robust |
| `fs_workspace+sjc:max_context_k=13` | 0.67 [0.00…1.00] (+0.25) · 3/4 · 248% | 0.75 [0.50…1.00] (+0.50) · 1/2 · 140% | model-robust |
| `raw_rag+resum:max_context_k=13` | 0.33 [0.00…1.00] (+0.00) · 1/4 · 98% | 1.00 [1.00…1.00] (+0.75) · 2/2 · 91% | model-dependent |
| `strands` | 1.00 [1.00…1.00] (+0.38) · 4/4 · 256% | 1.00 [1.00…1.00] (+0.75) · 2/2 · 78% | model-robust |

### research_corpus: anchors per model (means over instances)

| model | instances | floor score (`naive`) | ceiling score (unlimited context) | headroom | floor $ | `full@native` $ | `naive@native` $ (cost reference) |
|---|---|---|---|---|---|---|---|
| cc-haiku | 4 | 0.00 | 0.75 | 0.75 | 0.090 | nan | 0.299 |
| cc-sonnet | 3 | 0.00 | 1.00 | 1.00 | 1.097 | nan | 4.349 |

### research_corpus: method effect relative to each model's own floor and ceiling

| method | cc-haiku: recovery (Δscore) · success · $ vs `naive@native` | cc-sonnet: recovery (Δscore) · success · $ vs `naive@native` | verdict |
|---|---|---|---|
| `akv_drop` | 0.63 [0.44…1.00] (+0.72) · 2/4 · 72% | 1.00 [1.00…1.00] (+1.00) · 2/2 · 85% | model-robust |
| `akv_drop:keep=8,block=8` | 0.15 [0.00…0.33] (+0.19) · 0/4 · 13% | 1.00 [1.00…1.00] (+1.00) · 2/2 · 20% | model-dependent |
| `automem` | 1.00 [1.00…1.00] (+0.75) · 3/4 · 52% | 1.00 [1.00…1.00] (+1.00) · 3/3 · 29% | model-robust |
| `automem#aux=cc-haiku` | — | 1.00 [1.00…1.00] (+1.00) · 3/3 · 19% | recovers (one model only) |
| `automem:ingest=0.1` | 1.00 [1.00…1.00] (+0.75) · 3/4 · 50% | — | recovers (one model only) |
| `automem:ingest=0.1#aux=cc-haiku` | — | 1.00 [1.00…1.00] (+1.00) · 2/2 · 18% | recovers (one model only) |
| `cadoc` | 0.33 [0.00…1.00] (+0.50) · 2/4 · 63% | 1.00 [1.00…1.00] (+1.00) · 2/2 · 19% | model-dependent |
| `coral` | 0.00 [0.00…0.00] (+0.00) · 0/4 · 14% | 0.00 [0.00…0.00] (+0.00) · 0/2 · 6% | not effective |
| `fs_workspace+resum:max_context_k=33` | 0.67 [0.00…1.00] (+0.75) · 3/4 · 39% | 1.00 [1.00…1.00] (+1.00) · 3/3 · 29% | model-robust |
| `openclaw:max_context_k=33` | 0.67 [0.00…1.00] (+0.75) · 3/4 · 31% | 1.00 [1.00…1.00] (+1.00) · 2/2 · 20% | model-robust |
| `openclaw:max_context_k=33,sjc=true` | 1.00 [1.00…1.00] (+1.00) · 4/4 · 57% | 1.00 [1.00…1.00] (+1.00) · 2/2 · 20% | model-robust |
| `refold` | 0.44 [0.33…0.56] (+0.33) · 0/4 · 40% | 1.00 [1.00…1.00] (+1.00) · 2/2 · 27% | model-dependent |
| `selfcompact` | 0.56 [0.11…0.78] (+0.42) · 0/4 · 69% | 1.00 [1.00…1.00] (+1.00) · 2/2 · 32% | model-robust |
| `sjc:max_context_k=33` | 0.93 [0.78…1.00] (+0.94) · 3/4 · 45% | 1.00 [1.00…1.00] (+1.00) · 2/2 · 21% | model-robust |
| `strands` | 0.15 [0.00…0.44] (+0.11) · 0/4 · 31% | 0.72 [0.56…0.89] (+0.72) · 0/2 · 16% | model-dependent |
<!-- /ROBUST -->

## What each method did

The diagnostics come from each run's `records` field: ReFold's labels, SJC's verdicts, SelfCompact's probes, and CORAL and CADOC counts.

**OpenClaw and SJC (University of Virginia).**
- **OpenClaw** writes the summary in five fixed sections (Decisions, Open TODOs, Constraints/Rules, Pending user asks, Exact identifiers). It never failed its own format audit, so no compaction was cancelled.
- **SJC** asked a Haiku judge whether each entry came from what the tools returned. It deleted about 38% of OpenClaw's entries on Haiku and 37% on Sonnet, shrinking those summaries by about a third (Haiku: 158K → 108K estimated tokens over all compactions).
- **On ReSum's free-form summaries** it deleted only 13–16%. No judge call failed.
- **Where it helped:**
  - Haiku `research_corpus`: OpenClaw alone 0.75 → with SJC 1.00. SJC on ReSum: 0.94.
  - Haiku `repo_debug`: 0.62 → 0.75.
- **Where it hurt:** Sonnet `repo_debug` (0.75 → 0.50). On 2 runs, that is not distinguishable from noise.
- **Paper comparison:** the SJC paper reports +2 to +9 points of Pass@3 over OpenClaw. Here the gain is clear only on Haiku `research_corpus`.

**SelfCompact (Apple + JHU).**
- The agent's own model answered the four-question rubric (closed unit, summarisable, progress, not stuck) and compacted when it passed: Haiku passed 53% of 204 probes, Sonnet 67% of 63.
- It gives Sonnet the smallest mean peak of any method (30% of the ceiling's peak).
- But every probe and every summary is a full-prompt call on the agent model, so cost runs to 138–179% of the ceiling on average.
- The backstop at 0.8 × window forced 27 of Haiku's 132 compactions and 3 of Sonnet's 44.

**Strands harness defaults (AWS).**
- **Strong on `ledger_audit`:** Sonnet 1.00 at 34% of the ceiling's cost, Haiku 0.86 at 56%.
- **Fails on `research_corpus`** (Haiku 0.11, Sonnet 0.72). Its fixed 1,500-token threshold turns every ~2K-token document into a preview that hides the facts, and the models rarely went back for the full text.
- **Ran away on Sonnet `ops_stream`:** 513% of the ceiling's cost, the most expensive cell in the study. It truncates the daily files, and the agent then pages them back repeatedly over 10 sessions.
- AutoMemory v2 keeps the preview idea with a window-relative threshold (10%), which avoids both failures.

**ReFold (UCSB + Intel).**
- The protocol was followed perfectly: no reply lacked its PROGRESS/STALE lines (536 Haiku and 391 Sonnet replies).
- The models also named steps as STALE: Haiku folded 74 runs of steps and Sonnet 90.
- **Sonnet:** recovery 1.01, at 111% cost.
- **Haiku:** marked steps STALE whose figures it later needed (recovery 0.25) and called `restore` 31 times.
- **Cost:** every boundary advance rewrites the cached history, which the CLI bills as cache writes. That is how the paper's own Bedrock run saw −24% tokens but only −11% cost.

**CADOC (SJTU).**
- The commit rule batched replacements as designed: Haiku committed 1,376 object cards in 180 commits, about 8 per commit.
- **Sonnet** worked with the cards, retrieving objects when needed (recovery 0.86).
- **Haiku** could not: it overflowed or answered from cards on `ledger_audit` (0.03) and `ops_stream` (0.23).
- **Fit to these tasks:** in the paper, the cost win comes from very long chains with history kept across tasks. Short sessions here rarely commit.

**AKV rolling drop (Tsinghua + CUHK).**
- **Inside a serving engine** AKV drops the KV cache of old tool results at no re-processing cost. Over an API, the text itself has to be removed.
- **Dropping every turn:** the cache breaks on every turn (Sonnet `research_corpus`: 93% of the ceiling's cost, against 22% when dropping in blocks of 8). That confirms the paper's own warning about the text-level variant.
- **Either way, the multi-session tasks fail** (`ledger_audit` 0.00–0.17). The ledgers the agent dropped are the ones it has to add up at the end.

**Raw-history RAG ("Memory Tax", "Naive RAG", "MemoryTax").**
- **Setup:** each session's raw turns (tool results included) are retrieved by BM25 plus dense search with a cross-encoder reranker, and placed in the next session's first message.
- **Sonnet:** fine on `ledger_audit` and `repo_debug` (1.00 at about 90% cost), but very expensive on `ops_stream` (463%): the retrieved raw chunks are large, and they are repeated in every one of 10 sessions.
- **Haiku:** weak (0.38–0.62).
- **Compared with notes:** a note workspace with automatic recall (v1/v2) is both cheaper and more accurate here.

**CORAL (CUHK + Tencent + HKUST), prompting-only variant.**
- The models barely used its tools:
  - Haiku called the memory tool in 7 of 56 sessions and the context-optimisation tool once.
  - Sonnet made one memory call in 32 sessions.
- Without a reset the context simply overflows, so CORAL behaves like the floor. The paper's prompting-only gain (Sonnet 4 on BrowseComp) relied on a research prompt and web tools this benchmark doesn't have; its trained variants are not available.

## What this means for AutoMemory

1. **Keep v2 as the default.** No new method is better on both models across the four tasks.
2. **Candidate v3 component: OpenClaw-style structured summaries in place of ReSum's** (plus SJC pruning as a switch). The ablation ([`2026-11-04-automemory-v3-ablation.md`](2026-11-04-automemory-v3-ablation.md)) did not support it: inside AutoMemory every variant was worse than v2 on Haiku and tied on Sonnet.
3. **Do not add:**
   - per-turn history edits (AKV every turn);
   - methods that rely on the model to manage its own memory (CORAL, ReFold's STALE marking) as defaults;
   - SelfCompact's per-step probes on a model billed per call.

   Each lost accuracy or cost on at least one model.
4. **The general lesson holds.** Steps the harness performs automatically (previews at ingestion, recall, compaction at a fixed trigger) are robust across models. Steps that depend on the model's choices are not. See [`../problem_statement.md`](../problem_statement.md) §4.

## Spend

The new runs cost $149.40 (Haiku $28.95, Sonnet $120.46). The total below also includes the reused v4 anchors and comparators and the v2 rows.

<!-- SPEND -->
cc-haiku: $41.27 · cc-sonnet: $191.18 · total $232.44
<!-- /SPEND -->

## Reproduce

```bash
scripts/run_v5.sh cc-haiku 4 3        # suite real_v5 (eam/bench/experiments.py), one process per task
scripts/run_v5.sh cc-sonnet 2 2
python scripts/fill_report.py docs/results/2026-11-04-new-methods.md results/v5_report_rows.jsonl
```

`results/v5_report_rows.jsonl` contains:
- the v4 rows of `naive`, `naive@native`, `automem`, `automem#aux=cc-haiku` and `fs_workspace+resum:*` (same file list as the v1 report);
- the `automem:ingest=0.1*` rows of `results/automem_v2-*.jsonl`;
- all rows of `results/real_v5-*.jsonl`.
