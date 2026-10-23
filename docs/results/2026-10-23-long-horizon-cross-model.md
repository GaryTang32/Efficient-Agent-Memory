# Long-horizon tasks: memory and cost methods on Haiku and Sonnet, measured against each model's own floor and ceiling

**Date:** 2026-10-23.

**Route:** Claude Code CLI (`claude-cli`). The same model serves as the agent, the summariser and the sub-agents.

**Raw rows** (git-ignored, under `results/`):
- `real_v3-research-haiku.jsonl`
- `real_v3-research-sonnet.jsonl`
- `real_v3-ops-haiku.jsonl`
- `real_v3-ops-sonnet.jsonl`

**Rows excluded because of a harness bug** (see *Data quality*): `results/excluded/`.

**Regenerate every table below:**

```bash
F="results/real_v3-research-haiku.jsonl results/real_v3-research-sonnet.jsonl results/real_v3-ops-haiku.jsonl results/real_v3-ops-sonnet.jsonl"
python -m eam.bench.analyze --metrics $F   # accuracy, rounds, tool calls, time, tokens, cost
python -m eam.bench.analyze --robust  $F   # recovery against each model's floor/ceiling + verdicts
```

Definitions of every metric: `docs/methodology.md` §3. The model-independence protocol is in §6.

## Question

Does a memory or cost method work **regardless of how capable the model is**? A stronger model scores higher with any method. So each method is measured against *the same model's* two anchors on the same instance:
- **Floor:** `naive`. No memory management and no cost optimisation: full history, raw tool output, prompt caching off, the task's window.
- **Ceiling:** `naive@native` / `full@native`. Nothing is ever lost, and the model's own 1M-token window applies.

**Recovery** = (score − floor) ÷ (ceiling − floor): the share of the loss caused by the window that the method wins back.

**Cost** is reported relative to `naive@native`: what an unoptimised long-context agent actually pays on the same model and instance.

## Tasks

Both tasks are synthetic, seeded and scored automatically (`docs/methodology.md` §2).

| Task | Shape | Data vs window | Length | Scoring |
|---|---|---|---|---|
| `research_corpus` | One long session of deep research (BrowseComp-Plus style). 130 documents about invented entities with confusable namesakes. 8 multi-hop questions are revealed one at a time; Q9 sums the year answers; the final answer restates all 9. | ≈260K-token corpus; 40K window | 50–75 rounds | fraction of the 9 answers right; success = 9/9 |
| `ops_stream` | 10 sessions (days) of warehouse events. `AMEND`/`VOID` lines correct earlier days' events by id only, so knowledge must be updated. | ≈80K-token log; 32K window | 30–320 rounds over 10 sessions | per day: 6 stock levels + the lowest SKU; success = all 10 days exact |

## Methods

Settings are the official defaults unless stated (`docs/literature_review.md`).

| Spec | Source | Notes |
|---|---|---|
| `naive` | floor | no caching, no offload |
| `full` | B1 | full history, Claude Code's caching, harness offload of tool output above 6K tokens per step |
| `naive@native`, `full@native` | ceiling | as above, without the emulated window |
| `obs_mask` | observation masking: window 2, ≥300 tokens (AttnCompress artefact settings; the baseline in AgentDiet and AttnCompress) | |
| `resum:max_context_k=K` | ReSum (Tongyi Lab), official prompts | Trigger at 0.9·(K·1024 − 1000) tokens. K=33 for the 40K window (29.5K) and K=26 for the 32K window (23.1K). Sensitivity runs: K=28 and K=22. |
| `fs_workspace` | FS-Researcher (ACL'26, USTC) file-system workspace | our minimal port: notes that persist across sessions |
| `fs_workspace+resum` | combination | recipe from `2026-10-22-ledger_audit-cross-model.md` |
| `folding` | Context-Folding / FoldAgent (ICML'26, ByteDance Seed) | official protocol, ≤5 branches |
| `agentdiet` | AgentDiet (FSE'26) | official prompt and Algorithm 1. Haiku only: Sonnet's API safeguards reject its reflection calls (2026-10-22 report). |

**Runs per cell:**

| Task | Haiku | Sonnet |
|---|---|---|
| `research_corpus` | 5 instances | 3 |
| `ops_stream` | 5 | 2 (cost: ≈$47 per Sonnet seed) |

`full@native` was not run on Sonnet `ops_stream`; `naive@native` gives that ceiling.

## Headline results

<!-- HEADLINE -->
**ops_stream** — success · accuracy · recovery · cost vs `naive@native` · rounds · minutes (medians; recovery defined only for methods)

| method | cc-haiku | cc-sonnet |
|---|---|---|
| `naive` | 0/5 · 0.20 · — · 7% · 29 · 3.3 | 0/2 · 0.19 · — · 28% · 29 · 2.4 |
| `full` | 0/5 · 0.20 · 0.00 · 21% · 54 · 9.2 | 0/2 · 0.17 · -0.03 · 80% · 54 · 4.4 |
| `naive@native` | 1/5 · 0.89 · — · 100% · 31 · 22.7 | 2/2 · 1.00 · — · 100% · 30 · 4.3 |
| `full@native` | 0/5 · 0.81 · — · 246% · 115 · 37.8 | — |
| `agentdiet` | 0/5 · 0.29 · 0.15 · 108% · 70 · 20.1 | — |
| `folding` | 0/5 · 0.20 · 0.01 · 21% · 55 · 8.7 | 0/2 · 0.20 · 0.01 · 308% · 90 · 24.4 |
| `fs_workspace` | 0/5 · 0.34 · 0.27 · 28% · 62 · 11.5 | 1/2 · 0.99 · 0.99 · 72% · 52 · 6.3 |
| `fs_workspace+resum:max_context_k=26` | 0/5 · 0.55 · 0.58 · 60% · 79 · 20.9 | 1/2 · 0.99 · 0.98 · 81% · 55 · 6.5 |
| `obs_mask` | 0/5 · 0.12 · -0.12 · 118% · 122 · 16.2 | 0/2 · 0.38 · 0.23 · 1616% · 322 · 40.3 |
| `resum:max_context_k=26` | 0/5 · 0.43 · 0.35 · 144% · 127 · 37.8 | 2/2 · 1.00 · 1.00 · 384% · 121 · 17.5 |

**research_corpus** — success · accuracy · recovery · cost vs `naive@native` · rounds · minutes (medians; recovery defined only for methods)

| method | cc-haiku | cc-sonnet |
|---|---|---|
| `naive` | 0/5 · 0.00 · — · 21% · 25 · 2.4 | 0/3 · 0.00 · — · 27% · 27 · 2.0 |
| `full` | 0/5 · 0.00 · 0.00 · 8% · 16 · 3.5 | 0/3 · 0.00 · 0.00 · 7% · 27 · 1.7 |
| `naive@native` | 4/5 · 0.98 · — · 100% · 61 · 7.6 | 3/3 · 1.00 · — · 100% · 52 · 4.7 |
| `full@native` | 4/5 · 0.96 · — · 27% · 59 · 8.2 | 3/3 · 1.00 · — · 17% · 52 · 4.0 |
| `agentdiet` | 1/5 · 0.20 · 0.20 · 108% · 64 · 15.3 | — |
| `folding` | 0/5 · 0.00 · 0.00 · 9% · 24 · 3.4 | 3/3 · 1.00 · 1.00 · 20% · 34 · 4.9 |
| `fs_workspace` | 0/5 · 0.00 · 0.00 · 9% · 12 · 2.8 | 0/3 · 0.00 · 0.00 · 7% · 25 · 1.9 |
| `fs_workspace+resum:max_context_k=28` | 0/5 · 0.04 · 0.05 · 8% · 18 · 2.3 | — |
| `fs_workspace+resum:max_context_k=33` | 0/5 · 0.00 · 0.00 · 15% · 30 · 4.2 | 3/3 · 1.00 · 1.00 · 29% · 60 · 5.8 |
| `obs_mask` | 2/5 · 0.62 · 0.63 · 55% · 76 · 8.5 | 3/3 · 1.00 · 1.00 · 37% · 59 · 4.4 |
| `resum:max_context_k=28` | 1/5 · 0.20 · 0.20 · 24% · 46 · 5.7 | — |
| `resum:max_context_k=33` | 1/5 · 0.20 · 0.20 · 12% · 24 · 3.2 | 3/3 · 1.00 · 1.00 · 22% · 57 · 4.4 |
<!-- /HEADLINE -->

## Findings

1. **Doing nothing fails.** With no memory management, `naive` and `full` solved 0 of 30 runs on either model. Accuracy was 0.00 on `research_corpus` and ≈0.20 on `ops_stream`, which is roughly day 1 and day 2 correct before the window overflows.

2. **No method was model-robust on both tasks. The right method depends on the task's shape.**
   - **One long session (`research_corpus`):** observation masking was the only method that helped on both models. Recovery was 0.63 on Haiku and 1.00 on Sonnet.
   - **Many sessions with corrections (`ops_stream`):** the persistent workspace plus ReSum was the only model-robust method. Recovery was 0.58 on Haiku and 0.98 on Sonnet.
   - Each method fails on the other task's shape:
     - Masking on `ops_stream`: −0.12 on Haiku, 0.23 on Sonnet, at 16× the cost on Sonnet.
     - A workspace inside a single session holds nothing that is lost: 0.00 on both models.

3. **Model capability gates most methods.** On Sonnet, 4 of the 5 methods recovered ≥ 0.98 on `research_corpus`. The best Haiku result was 0.63. Prompt-only methods depend on the model *using* the mechanism:
   - **Context-Folding:** Haiku called `branch` once in 5 research runs and overflowed. Sonnet branched 5 times per run and solved 3/3.
   - **ReSum on Haiku:** the session overflowed before the summary trigger fired, in 4/5 runs on `research_corpus` and 5/5 on `ops_stream`. Workspace + ReSum overflowed in 4/5 on each task. A single Haiku step can add more than the margin left below the window. Moving the trigger earlier did not help on `research_corpus` (K=28: 0.20). For `ops_stream`, see the sensitivity rows.
   - **Workspace alone on Haiku `ops_stream`:** Haiku re-read old files instead of trusting its notes (0.34), while Sonnet scored 0.99.

4. **Caching is the largest cost lever, and on a cached route long context is hard to beat.**
   - On `research_corpus`, the same unlimited-context run cost 27% (Haiku) and 17% (Sonnet) of its uncached price, at ceiling accuracy.
   - No memory method was cheaper than cached long context at equal accuracy there. The best was Context-Folding at 20% on Sonnet.
   - Memory methods pay off when the window really binds, or across sessions. On Sonnet `ops_stream`, the workspace reached 0.99 at 72% of the unoptimised cost, against 384% for ReSum and 1,616% for masking.

5. **Methods that rewrite history can make caching backfire.** Claude Code writes the cache at 2× the input price (1-hour TTL). Masking, AgentDiet and ReSum resets rewrite the history and pay that write again.
   - On Sonnet `ops_stream`, masking took 322 rounds at 10% cache hits: $28 per run.
   - For masking and AgentDiet, the *uncached* counterfactual is cheaper than the cached cost on both tasks and both models (`--metrics`: "$ per run if uncached"; Sonnet `ops_stream` masking: $28.23 cached vs $15.72 uncached).
   - The cost of compression is set by cache behaviour, not by tokens removed.

6. **Turns and time follow the same pattern as cost.**
   - Successful Sonnet methods on `research_corpus` took 34–60 rounds and 4–6 minutes per run.
   - On `ops_stream`, the workspace took 52–55 rounds (≈6.5 min). ReSum took 121 rounds (17.5 min) because it rebuilds earlier days from the raw files every session. Masking took 322 rounds (40 min).

## Recommendations

| Situation | Use | Evidence |
|---|---|---|
| Single long session, model ≥ Sonnet | Cached long context if the window allows. Otherwise ReSum or Context-Folding (20–22% of the uncached cost, 3/3). | `research_corpus`, Sonnet |
| Single long session, Haiku-class model | Observation masking is the only method that recovered anything (0.63) | `research_corpus`, Haiku |
| Work spread over sessions, with updates | Persistent workspace + ReSum. On Sonnet the workspace alone is enough and cheaper (72%). | `ops_stream`, `ledger_audit` (2026-10-22) |
| Any method that edits history on a route that caches at 2× | Budget for the cache rewrites; prefer rare resets (ReSum) over per-step edits (masking, AgentDiet) | finding 5 |

## Data quality: bugs found and fixed during this round

All bugs below were fixed before the reported rows were recorded. Affected rows were discarded or rerun, not patched.

1. **Overflow check overestimated request size after a tiny first call.**
   - The ratio scaling was inflated by the CLI's fixed ~1.3K-token overhead. It is now an affine fit: overhead + slope × estimate.
   - Pilots were rerun.
   - Earlier `ledger_audit` runs may have ended up to ~5% early. Their conclusions do not change.
2. **`submit_answer` accepted empty answers and advanced the question.** Sonnet issued empty calls in parallel and skipped Q2–Q8.
   - Empty answers are now rejected.
   - All Haiku `research_corpus` rows and Sonnet's `fs_workspace+resum` rows from before the fix were discarded and rerun (`results/excluded/`).
   - Sonnet's other rows were 9/9 correct or ended in a recorded overflow, so the bug could not have changed them.
3. **A tool call with the tool name missing** (`<invoke:parameter name="query">`) was not parsed. It is now recovered from the parameter names when exactly one tool fits.
4. **Runaway replies.** With no output cap, a repeating reply ran until the 240 s timeout. The CLI now gets `CLAUDE_CODE_MAX_OUTPUT_TOKENS` (≥ 8,192), and a reply over the cap becomes an empty, truncated turn rather than a failed run.
5. **Infrastructure errors are rerun, not counted.**
   - A CLI usage-limit window was hit mid-batch (about 70 runs failed), plus a few CLI timeouts.
   - Those runs were rerun with `--resume`.
   - `analyze` drops an error row once the same run has succeeded.

## Caveats

- **Few seeds:** 3 and 2 on Sonnet. Claims are limited to large, consistent effects (0/n vs n/n, recovery ≈ 0 vs ≈ 1, multi-× cost).
- **One route.** The Claude Code CLI places one cache breakpoint at the end, adds ~1.3K tokens of overhead per call, and allows no temperature control. Bedrock, with explicit cache points, may change the cost picture for history-editing methods.
- **Emulated windows.** The 32K and 40K windows are emulated limits that stand in for a native window that real data overflows.
- **Opus not run yet** on these tasks. On `ledger_audit` it behaved like Sonnet.
- **`fs_workspace` is our own minimal port.** FS-Researcher's repo has no licence.

## Spend (list price, this round, reported rows only)

<!-- SPEND -->
cc-haiku: $34.46 · cc-sonnet: $127.07 · total $161.53
<!-- /SPEND -->

## Full tables

### Model-normalised comparison (`--robust`)

<!-- ROBUST -->
### ops_stream: anchors per model (means over instances)

| model | instances | floor score (`naive`) | ceiling score (unlimited context) | headroom | floor $ | `full@native` $ | `naive@native` $ (cost reference) |
|---|---|---|---|---|---|---|---|
| cc-haiku | 5 | 0.20 | 0.85 | 0.66 | 0.032 | 2.087 | 1.315 |
| cc-sonnet | 2 | 0.19 | 1.00 | 0.81 | 0.495 | nan | 1.747 |

### ops_stream: method effect relative to each model's own floor and ceiling

| method | cc-haiku: recovery (Δscore) · success · $ vs `naive@native` | cc-sonnet: recovery (Δscore) · success · $ vs `naive@native` | verdict |
|---|---|---|---|
| `agentdiet` | 0.15 [-0.02…0.28] (+0.09) · 0/5 · 108% | — | does not recover (one model only) |
| `folding` | 0.01 [0.00…0.03] (+0.01) · 0/5 · 21% | 0.01 [-0.11…0.12] (+0.01) · 0/2 · 308% | not effective |
| `fs_workspace` | 0.27 [-0.32…1.27] (+0.14) · 0/5 · 28% | 0.99 [0.98…1.00] (+0.80) · 1/2 · 72% | model-dependent |
| `fs_workspace+resum:max_context_k=26` | 0.58 [0.00…1.06] (+0.35) · 0/5 · 60% | 0.98 [0.96…1.00] (+0.79) · 1/2 · 81% | model-robust |
| `full` | 0.00 [0.00…0.02] (+0.00) · 0/5 · 21% | -0.03 [-0.07…0.02] (-0.02) · 0/2 · 80% | not effective |
| `obs_mask` | -0.12 [-0.18…-0.09] (-0.08) · 0/5 · 118% | 0.23 [0.18…0.29] (+0.19) · 0/2 · 1616% | not effective |
| `resum:max_context_k=26` | 0.35 [0.21…0.58] (+0.24) · 0/5 · 144% | 1.00 [1.00…1.00] (+0.81) · 2/2 · 384% | model-dependent |

### research_corpus: anchors per model (means over instances)

| model | instances | floor score (`naive`) | ceiling score (unlimited context) | headroom | floor $ | `full@native` $ | `naive@native` $ (cost reference) |
|---|---|---|---|---|---|---|---|
| cc-haiku | 5 | 0.00 | 0.97 | 0.97 | 0.053 | 0.084 | 0.313 |
| cc-sonnet | 3 | 0.00 | 1.00 | 1.00 | 1.097 | 0.706 | 4.349 |

### research_corpus: method effect relative to each model's own floor and ceiling

| method | cc-haiku: recovery (Δscore) · success · $ vs `naive@native` | cc-sonnet: recovery (Δscore) · success · $ vs `naive@native` | verdict |
|---|---|---|---|
| `agentdiet` | 0.20 [0.00…1.00] (+0.20) · 1/5 · 108% | — | does not recover (one model only) |
| `folding` | 0.00 [0.00…0.00] (+0.00) · 0/5 · 9% | 1.00 [1.00…1.00] (+1.00) · 3/3 · 20% | model-dependent |
| `fs_workspace` | 0.00 [0.00…0.00] (+0.00) · 0/5 · 9% | 0.00 [0.00…0.00] (+0.00) · 0/3 · 7% | not effective |
| `fs_workspace+resum:max_context_k=28` | 0.05 [0.00…0.24] (+0.04) · 0/5 · 8% | — | does not recover (one model only) |
| `fs_workspace+resum:max_context_k=33` | 0.00 [0.00…0.00] (+0.00) · 0/5 · 15% | 1.00 [1.00…1.00] (+1.00) · 3/3 · 29% | model-dependent |
| `full` | 0.00 [0.00…0.00] (+0.00) · 0/5 · 8% | 0.00 [0.00…0.00] (+0.00) · 0/3 · 7% | not effective |
| `obs_mask` | 0.63 [0.00…1.00] (+0.62) · 2/5 · 55% | 1.00 [1.00…1.00] (+1.00) · 3/3 · 37% | model-robust |
| `resum:max_context_k=28` | 0.20 [0.00…1.00] (+0.20) · 1/5 · 24% | — | does not recover (one model only) |
| `resum:max_context_k=33` | 0.20 [0.00…1.00] (+0.20) · 1/5 · 12% | 1.00 [1.00…1.00] (+1.00) · 3/3 · 22% | model-dependent |
<!-- /ROBUST -->

### Every measured quantity (`--metrics`)

<!-- METRICS -->
### ops_stream — accuracy and effort

| model | method | runs | success | accuracy (mean score) | agentic rounds | tool calls | sessions | LLM calls incl. side calls | overflowed runs | wall-clock (min) | model time (min) |
|---|---|---|---|---|---|---|---|---|---|---|---|
| cc-haiku | `naive@native` | 5 | 1/5 | 0.89 | 31 | 185 | 10 | 31 | 0/5 | 22.7 | 9.4 |
| cc-haiku | `full@native` | 5 | 0/5 | 0.81 | 115 | 568 | 10 | 115 | 0/5 | 37.8 | 23.6 |
| cc-haiku | `fs_workspace+resum:max_context_k=26` | 5 | 0/5 | 0.55 | 79 | 165 | 10 | 86 | 4/5 | 20.9 | 16.2 |
| cc-haiku | `resum:max_context_k=26` | 5 | 0/5 | 0.43 | 127 | 573 | 10 | 147 | 5/5 | 37.8 | 27.2 |
| cc-haiku | `fs_workspace` | 5 | 0/5 | 0.34 | 62 | 146 | 10 | 58 | 5/5 | 11.5 | 8.3 |
| cc-haiku | `agentdiet` | 5 | 0/5 | 0.29 | 70 | 322 | 10 | 102 | 5/5 | 20.1 | 14.5 |
| cc-haiku | `folding` | 5 | 0/5 | 0.20 | 55 | 290 | 10 | 49 | 5/5 | 8.7 | 3.5 |
| cc-haiku | `full` | 5 | 0/5 | 0.20 | 54 | 275 | 10 | 46 | 5/5 | 9.2 | 3.4 |
| cc-haiku | `naive` | 5 | 0/5 | 0.20 | 29 | 184 | 10 | 22 | 5/5 | 3.3 | 1.9 |
| cc-haiku | `obs_mask` | 5 | 0/5 | 0.12 | 122 | 711 | 10 | 116 | 5/5 | 16.2 | 11.5 |
| cc-sonnet | `naive@native` | 2 | 2/2 | 1.00 | 30 | 184 | 10 | 30 | 0/2 | 4.3 | 2.9 |
| cc-sonnet | `resum:max_context_k=26` | 2 | 2/2 | 1.00 | 121 | 362 | 10 | 140 | 0/2 | 17.5 | 11.2 |
| cc-sonnet | `fs_workspace` | 2 | 1/2 | 0.99 | 52 | 85 | 10 | 52 | 0/2 | 6.3 | 3.7 |
| cc-sonnet | `fs_workspace+resum:max_context_k=26` | 2 | 1/2 | 0.99 | 55 | 83 | 10 | 56 | 0/2 | 6.5 | 4.0 |
| cc-sonnet | `obs_mask` | 2 | 0/2 | 0.38 | 322 | 946 | 10 | 321 | 2/2 | 40.3 | 26.8 |
| cc-sonnet | `folding` | 2 | 0/2 | 0.20 | 90 | 150 | 10 | 172 | 2/2 | 24.4 | 16.4 |
| cc-sonnet | `naive` | 2 | 0/2 | 0.19 | 29 | 146 | 10 | 24 | 2/2 | 2.4 | 1.3 |
| cc-sonnet | `full` | 2 | 0/2 | 0.17 | 54 | 236 | 10 | 46 | 2/2 | 4.4 | 2.4 |

### ops_stream — tokens and cost

| model | method | prompt tokens | uncached input | cache read | cache write | output | peak context | cache hit | $ per run | $ per run if uncached | $ per success |
|---|---|---|---|---|---|---|---|---|---|---|---|
| cc-haiku | `naive@native` | 859K | 859K | 0K | 0K | 173K | 119K | 0% | 0.422 | 0.422 | 6.577 |
| cc-haiku | `full@native` | 8.80M | 0K | 6.50M | 2.30M | 516K | 824K | 78% | 1.707 | 2.062 | ∞ |
| cc-haiku | `fs_workspace+resum:max_context_k=26` | 1.44M | 0K | 793K | 650K | 231K | 29K | 51% | 0.253 | 0.260 | ∞ |
| cc-haiku | `resum:max_context_k=26` | 3.02M | 0K | 887K | 2.13M | 403K | 31K | 33% | 0.637 | 0.503 | ∞ |
| cc-haiku | `fs_workspace` | 870K | 0K | 535K | 320K | 116K | 31K | 63% | 0.128 | 0.145 | ∞ |
| cc-haiku | `agentdiet` | 2.15M | 0K | 227K | 1.92M | 216K | 32K | 11% | 0.529 | 0.353 | ∞ |
| cc-haiku | `folding` | 704K | 0K | 398K | 306K | 48K | 31K | 57% | 0.089 | 0.094 | ∞ |
| cc-haiku | `full` | 678K | 0K | 373K | 334K | 46K | 32K | 53% | 0.094 | 0.090 | ∞ |
| cc-haiku | `naive` | 168K | 168K | 0K | 0K | 28K | 26K | 0% | 0.029 | 0.029 | ∞ |
| cc-haiku | `obs_mask` | 2.24M | 0K | 223K | 2.03M | 138K | 32K | 10% | 0.478 | 0.293 | ∞ |
| cc-sonnet | `naive@native` | 749K | 749K | 0K | 0K | 25K | 119K | 0% | 1.747 | 1.747 | 1.747 |
| cc-sonnet | `resum:max_context_k=26` | 2.32M | 0K | 889K | 1.43M | 90K | 31K | 38% | 6.715 | 5.539 | 6.715 |
| cc-sonnet | `fs_workspace` | 649K | 0K | 412K | 237K | 27K | 28K | 63% | 1.256 | 1.565 | 2.511 |
| cc-sonnet | `fs_workspace+resum:max_context_k=26` | 665K | 0K | 390K | 275K | 27K | 25K | 59% | 1.411 | 1.603 | 2.822 |
| cc-sonnet | `obs_mask` | 7.00M | 1K | 380K | 6.62M | 173K | 31K | 5% | 28.234 | 15.722 | ∞ |
| cc-sonnet | `folding` | 2.48M | 0K | 1.44M | 1.04M | 109K | 31K | 58% | 5.390 | 6.041 | ∞ |
| cc-sonnet | `naive` | 198K | 198K | 0K | 0K | 10K | 26K | 0% | 0.495 | 0.495 | ∞ |
| cc-sonnet | `full` | 605K | 0K | 303K | 302K | 16K | 32K | 50% | 1.393 | 1.366 | ∞ |

### research_corpus — accuracy and effort

| model | method | runs | success | accuracy (mean score) | agentic rounds | tool calls | sessions | LLM calls incl. side calls | overflowed runs | wall-clock (min) | model time (min) |
|---|---|---|---|---|---|---|---|---|---|---|---|
| cc-haiku | `naive@native` | 5 | 4/5 | 0.98 | 61 | 65 | 1 | 61 | 0/5 | 7.6 | 5.2 |
| cc-haiku | `full@native` | 5 | 4/5 | 0.96 | 59 | 63 | 1 | 59 | 0/5 | 8.2 | 5.3 |
| cc-haiku | `obs_mask` | 5 | 2/5 | 0.62 | 76 | 88 | 1 | 76 | 1/5 | 8.5 | 5.2 |
| cc-haiku | `resum:max_context_k=33` | 5 | 1/5 | 0.20 | 24 | 27 | 1 | 25 | 4/5 | 3.2 | 2.3 |
| cc-haiku | `resum:max_context_k=28` | 5 | 1/5 | 0.20 | 46 | 47 | 1 | 49 | 4/5 | 5.7 | 3.7 |
| cc-haiku | `agentdiet` | 5 | 1/5 | 0.20 | 64 | 107 | 1 | 107 | 4/5 | 15.3 | 9.1 |
| cc-haiku | `fs_workspace+resum:max_context_k=28` | 5 | 0/5 | 0.04 | 18 | 22 | 1 | 19 | 3/5 | 2.3 | 1.8 |
| cc-haiku | `full` | 5 | 0/5 | 0.00 | 16 | 14 | 1 | 16 | 5/5 | 3.5 | 2.4 |
| cc-haiku | `fs_workspace` | 5 | 0/5 | 0.00 | 12 | 16 | 1 | 12 | 5/5 | 2.8 | 2.3 |
| cc-haiku | `folding` | 5 | 0/5 | 0.00 | 24 | 27 | 1 | 26 | 5/5 | 3.4 | 2.4 |
| cc-haiku | `fs_workspace+resum:max_context_k=33` | 5 | 0/5 | 0.00 | 30 | 33 | 1 | 33 | 4/5 | 4.2 | 2.8 |
| cc-haiku | `naive` | 5 | 0/5 | 0.00 | 25 | 26 | 1 | 25 | 5/5 | 2.4 | 1.5 |
| cc-sonnet | `full@native` | 3 | 3/3 | 1.00 | 52 | 51 | 1 | 52 | 0/3 | 4.0 | 1.7 |
| cc-sonnet | `folding` | 3 | 3/3 | 1.00 | 34 | 33 | 1 | 69 | 0/3 | 4.9 | 2.1 |
| cc-sonnet | `resum:max_context_k=33` | 3 | 3/3 | 1.00 | 57 | 57 | 1 | 59 | 0/3 | 4.4 | 1.8 |
| cc-sonnet | `fs_workspace+resum:max_context_k=33` | 3 | 3/3 | 1.00 | 60 | 95 | 1 | 63 | 0/3 | 5.8 | 2.9 |
| cc-sonnet | `obs_mask` | 3 | 3/3 | 1.00 | 59 | 58 | 1 | 59 | 0/3 | 4.4 | 1.7 |
| cc-sonnet | `naive@native` | 3 | 3/3 | 1.00 | 52 | 51 | 1 | 52 | 0/3 | 4.7 | 2.3 |
| cc-sonnet | `full` | 3 | 0/3 | 0.00 | 27 | 26 | 1 | 26 | 3/3 | 1.7 | 0.7 |
| cc-sonnet | `fs_workspace` | 3 | 0/3 | 0.00 | 25 | 39 | 1 | 24 | 3/3 | 1.9 | 0.8 |
| cc-sonnet | `naive` | 3 | 0/3 | 0.00 | 27 | 26 | 1 | 26 | 3/3 | 2.0 | 1.0 |

### research_corpus — tokens and cost

| model | method | prompt tokens | uncached input | cache read | cache write | output | peak context | cache hit | $ per run | $ per run if uncached | $ per success |
|---|---|---|---|---|---|---|---|---|---|---|---|
| cc-haiku | `naive@native` | 2.84M | 2.84M | 0K | 0K | 51K | 139K | 0% | 0.304 | 0.304 | 0.391 |
| cc-haiku | `full@native` | 3.00M | 0K | 2.85M | 148K | 52K | 143K | 95% | 0.085 | 0.327 | 0.104 |
| cc-haiku | `obs_mask` | 1.02M | 0K | 169K | 852K | 53K | 26K | 13% | 0.198 | 0.128 | 0.532 |
| cc-haiku | `resum:max_context_k=33` | 392K | 0K | 288K | 104K | 24K | 30K | 77% | 0.036 | 0.051 | 0.216 |
| cc-haiku | `resum:max_context_k=28` | 739K | 0K | 531K | 207K | 50K | 33K | 70% | 0.072 | 0.099 | 0.297 |
| cc-haiku | `agentdiet` | 2.14M | 0K | 645K | 1.49M | 104K | 38K | 35% | 0.360 | 0.269 | 1.320 |
| cc-haiku | `fs_workspace+resum:max_context_k=28` | 239K | 0K | 138K | 70K | 24K | 26K | 74% | 0.024 | 0.033 | ∞ |
| cc-haiku | `full` | 269K | 0K | 208K | 61K | 26K | 29K | 78% | 0.025 | 0.045 | ∞ |
| cc-haiku | `fs_workspace` | 201K | 0K | 144K | 57K | 28K | 32K | 72% | 0.029 | 0.036 | ∞ |
| cc-haiku | `folding` | 551K | 0K | 496K | 65K | 21K | 39K | 88% | 0.029 | 0.065 | ∞ |
| cc-haiku | `fs_workspace+resum:max_context_k=33` | 460K | 0K | 256K | 134K | 35K | 30K | 72% | 0.047 | 0.075 | ∞ |
| cc-haiku | `naive` | 545K | 545K | 0K | 0K | 16K | 38K | 0% | 0.063 | 0.063 | ∞ |
| cc-sonnet | `full@native` | 2.02M | 0K | 1.91M | 113K | 3K | 73K | 94% | 0.672 | 4.078 | 0.706 |
| cc-sonnet | `folding` | 986K | 0K | 819K | 167K | 6K | 33K | 83% | 0.820 | 2.044 | 0.847 |
| cc-sonnet | `resum:max_context_k=33` | 979K | 0K | 788K | 191K | 5K | 32K | 80% | 0.894 | 2.008 | 0.900 |
| cc-sonnet | `fs_workspace+resum:max_context_k=33` | 969K | 0K | 738K | 233K | 20K | 30K | 76% | 1.257 | 2.281 | 1.263 |
| cc-sonnet | `obs_mask` | 464K | 0K | 96K | 362K | 4K | 11K | 21% | 1.499 | 0.967 | 1.513 |
| cc-sonnet | `naive@native` | 2.01M | 2.01M | 0K | 0K | 3K | 72K | 0% | 4.055 | 4.055 | 4.349 |
| cc-sonnet | `full` | 530K | 0K | 472K | 58K | 1K | 38K | 89% | 0.291 | 1.074 | ∞ |
| cc-sonnet | `fs_workspace` | 453K | 0K | 399K | 55K | 4K | 38K | 88% | 0.295 | 0.943 | ∞ |
| cc-sonnet | `naive` | 530K | 530K | 0K | 0K | 2K | 38K | 0% | 1.075 | 1.075 | ∞ |
<!-- /METRICS -->
