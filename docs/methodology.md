# Methodology: how methods are compared

This document defines the tasks, conditions, metrics and procedure behind every result in `docs/results/`.
Code references are given so each number can be traced.

## 1. Unit of comparison

A **run** = one task instance (task family + seed) × one **technique spec** × one model/route.

- **Phase 1** compares each technique **alone** against the full-context baseline (`full`) on identical instances, models and routes.
- **Phase 2** compares **combinations** (specs joined with `+`, or the presets in `eam/presets.py`).

A spec such as `resum:max_context_k=40` sets parameters. Everything else uses the official defaults listed in `docs/literature_review.md` and in each module's docstring.

### Baselines

| Spec | What it is | Prompt caching | Harness offload | Window |
|---|---|---|---|---|
| `naive` (**B0**, the floor) | No memory management and no cost optimisation: full history, raw tool output | off (`DISABLE_PROMPT_CACHING=1` on the CLI) | off | the task's window |
| `full` (**B1**) | Full history | provider default (Claude Code: on) | on | the task's window |
| `naive@native` / `full@native` (the ceiling) | As above, but no emulated window: the model's own (1M tokens on the CLI route) | off / on | off / on | native |

`<spec>@native` and `<spec>@64k` change only the window (`eam/bench/runner.py: split_window`). Caching does not change what the model outputs, so the cost of `naive@native` can also be computed exactly from a `full@native` run's token counts (`eam/bench/analyze.py: uncached_cost`, rates in §4).

Every result row records the technique's **provenance label**: `official prompt/algorithm`, `baseline`, `ported from paper`, `engineering rules`, or `provisional`. That label shows how close the implementation is to the authors' own (`eam/techniques/*.py`, `provenance` attribute).

## 2. Tasks (`eam/bench/tasks/`)

| Task | What it stresses | Steps (real model) | Scoring |
|---|---|---|---|
| `chain_hunt` | Long sequential trajectory. 20 long files (~1.5K tokens each) must be read one at a time, since each names the next. One fragment per stage must survive until the end. One correction sends the agent back to an earlier file (focus shift). | ~21 | Exact code. `score` = fraction of the 20 fragments correct, in order. |
| `ledger_audit` | Data larger than the context window, plus multiple rounds. 16 monthly ledgers and 8 refund files (≈81K estimated / ≈113K real tokens) against a 48K-token window. Three dependent rounds, each a **fresh session**: totals → net of refunds → discounted payables. | ~20–60 over 3 rounds | 16 checks: 5 totals; 5 nets + highest vendor; 5 payables + sum. `score` = fraction correct. `success` = all three rounds exact. |
| `research_corpus` | Long single-session deep research (BrowseComp-Plus style, the benchmark of ReSum / Context-Folding / IterResearch). There are 130 documents of ~2K tokens (≈260K) about invented entities with confusable namesakes, and the facts are buried mid-document. 8 multi-hop questions (3–4 hops each) are revealed one at a time through `submit_answer`, so they cannot be researched in parallel. Q9 = the sum of the year answers. The final answer must list all 9 answers. 40K-token window. | ≥ ~65 sequential | `score` = fraction of the 9 answers right; `success` = all 9 |
| `ops_stream` | Many sessions plus **knowledge updates**. A warehouse runs for 10 days; each day is a fresh session with 3 new event files (~3K tokens each). `AMEND`/`VOID` lines correct earlier events (mostly from earlier days) by id only. Correct stock needs carried state *and* memory of which earlier event belongs to which SKU. ≈80K estimated tokens of data against a 32K window. | ~60–190 over 10 sessions | per day: 6 stock levels + the lowest-stock SKU; `score` = mean over days; `success` = every day exact |
| `needle_research`, `inventory_ops`, `long_document_qa`, `multi_session_profile` | Earlier, easier tasks (used offline). A real model solves the first one in ~3 parallel steps. | — | Exact answer |

All tasks are synthetic and seeded (`generate(seed)`), so instances are reproducible and answers are scored automatically. The filler text contains no digits and no facts. Relevant facts are placed at random positions inside long outputs.

### Environment rules for `ledger_audit` (identical for every technique)

- **Context window** (`context_limit`, 48K tokens). Before each call, the request size is estimated from characters. The estimate is then scaled by the ratio of real to estimated tokens observed on the previous call, because dense numeric text is undercounted by about 1.4×. A request whose estimated or actual size exceeds the window ends the run with `context_overflow`, as a real API would (`eam/agent/loop.py`).
- **Disclosure condition** (`disclose_limit`):
  - **unaware** (default, the papers' setting): the window is enforced silently.
  - **aware**: the system prompt states the limit and each step ends with `[Context used: about X of N tokens]`.
- **Per-step observation budget** (`step_observation_budget`, 6K estimated tokens), a harness-level recoverable offload. Within one step, tool output beyond the budget is stored outside the context. A preview plus an `artifact://` pointer is left in its place, and the agent can page it back with `read_artifact`. This mirrors production harnesses such as Trae Agent, which truncates tool output at 16 KB, and the Manus "file system as context" rule. Without it, unaware agents read every file in one parallel step and overflowed before any technique could act (pilot of 2026-10-22).
- **`calc` tool**, so arithmetic slips are not mistaken for memory loss.

### Harness rules for every task

- **Malformed reply**: no tool call and no `FINAL ANSWER:`. The loop re-prompts at most twice (`nudges`), identically for all techniques.
- **Step limit** per task (`max_steps`). Hitting it counts as not finished.

## 3. Metrics (one row per run, `eam/bench/runner.py`)

| Metric | Definition |
|---|---|
| `success` | All checks correct (single task: exact answer; multi-round: every round exact). |
| `score` | Partial credit in [0, 1]: the fraction of required items correct, averaged over rounds. |
| `round_scores`, `round_answers` | Per-round score and the first 1,500 characters of each round's answer. |
| `cost_usd` | Total dollars for the run: agent calls + auxiliary calls (AgentDiet reflector, ReSum summariser, MemAgent reader, memory extraction) + sub-agent calls (folding branches). On the `claude-cli` route this is Claude Code's reported `total_cost_usd` (list price). On Bedrock routes it is usage × the prices in `config/models.json`. |
| `by_tag` | Cost and tokens split into `main` (agent), `aux` (technique side calls) and `subagent`. |
| `prompt_tokens` | Sum over all calls of uncached + cache-read + cache-write input tokens. |
| `usage` | Split of prompt tokens into input (uncached), cache read, cache write, plus output tokens. |
| `cache_hit_rate` | cache-read tokens ÷ prompt tokens, over all calls. |
| `peak_prompt_tokens` | Largest single prompt in the run: the context-size high-water mark. |
| `history_rewrites` | Number of calls where earlier messages differed from what was previously sent. Each one is a prompt-cache break after the changed point. |
| `steps` | LLM calls of the agent (summed over rounds). |
| `nudges` | Re-prompts after malformed replies (§2). |
| `overflow` | True if any round ended with `context_overflow`. |
| `llm_latency_ms`, `wall_s` | Summed model latency, and wall-clock time of the run. |
| `events` | Counts of technique events (e.g. `agentdiet_reduced`, `obs_masked`, `resum_rebuild`, `folded`, `step_budget_offload`). |

The report (`python -m eam.bench report <rows>`) aggregates per (task, model, spec):
- success rate, mean score, mean cost and cost relative to `full`;
- **$/success** (total cost ÷ successes);
- mean prompt tokens, peak context, cache hit rate, rewrites, steps and LLM seconds.

`python -m eam.bench.analyze` adds:
- per-round scores;
- overflow counts;
- the median split of cost into agent calls and technique side calls;
- the list of runs that errored. These are reported, never dropped silently. A run that errored for an infrastructure reason, such as a CLI timeout, is rerun and the rerun counted.

Results documents report **medians** next to success counts. LLM runs have heavy-tailed costs: single runs occasionally balloon about 7× through model variance.

## 4. Models and routes

See `docs/backends.md`. Results so far use the Claude Code CLI route with the `haiku`, `sonnet` and `opus` aliases (`config/models.example.json`: `cc-haiku`, `cc-sonnet`, `cc-opus`). The same model serves as the agent and the auxiliary model. `scripts/run_model_comparison.sh` runs one suite on one model, and `python -m eam.bench.analyze <rows>...` produces the cross-model tables.

CLI list rates per 1M tokens: uncached input / cache read / cache write. These were fitted exactly to every recorded `total_cost_usd` and checked with single calls under `DISABLE_PROMPT_CACHING=1`:

| Model | Uncached input | Cache read | Cache write |
|---|---|---|---|
| Haiku | $0.10 | $0.01 | $0.20 |
| Sonnet | $2.00 | $0.10 | $4.00 |
| Opus | $4.00 | $0.20 | $8.00 |

Output costs 5× input. Claude Code writes the cache with the 1-hour TTL, so a write costs 2× input. Each history rewrite therefore costs more on this route than at the 5-minute rate of 1.25×.

Route-specific facts that affect interpretation:
- **Caching:** Claude Code places one cache breakpoint at the end of the conversation (our `cachePoint`s are not applied), and adds ~1.3K tokens of fixed overhead per call.
- **Sampling:** temperature cannot be set.
- **Tool calls** use the text protocol in `eam/llm/text_tools.py`.

Bedrock Converse runs will use explicit cache points, which is where cache-layout combinations can be tested.

## 5. Procedure and statistics

1. **Pilot** with one seed to check the task is solvable and the harness behaves.
2. **Full batch:**
   - 3–5 seeds × every spec, run concurrently (`--workers`); every run is independent.
   - For turn control, limits come from `python -m eam.bench calibrate` on the baseline rows: the 75th percentile, following the ICSE'26 paper.
3. **Report:**
   - per-method success counts, medians and the cost split;
   - failure modes read from `round_answers`/`answer` and `events`.

With 3–5 seeds per cell, a difference of one success is within noise. Claims in the results documents are limited to effects that are consistent across seeds or large (e.g. 0/5 vs 5/5, or 4× cost).

## 6. Measuring a method independently of model strength

Comparing raw scores across models mixes two effects: a stronger model scores higher with *any* method. To say whether a memory or cost method works *regardless of the model*, each method is measured against **that model's own** anchors, on the same instance (paired by seed):

- **Floor F:** score of `naive` on the task's window. This is what the model achieves with no memory management.
- **Ceiling C:** score of `full@native` (or `naive@native`). This is what the same model achieves when nothing is ever lost: the model's capability on the task.
- **Recovery** = (S − F) / (C − F). This is the share of the window-induced loss that the method wins back. 0 = no better than doing nothing; 1 = as good as unlimited context; it can exceed 1 when the method also helps reasoning. It is defined only when the model has headroom (C − F ≥ 0.15). A task too hard even with unlimited context, or one the floor already solves, says nothing about a memory method on that model.
- **Cost ratio** = method $ ÷ $ of `naive@native`. This is what an unoptimised long-context agent (no caching, no offload, no memory) actually pays for the same model and instance. It also normalises away the ~40× price difference between Haiku and Opus. Where `naive@native` was not run, the `full@native` run's cost is recomputed without caching. That is a weaker reference, because harness offload changes how many steps an agent takes: on the Haiku pilot of `ops_stream`, `naive@native` took 29 steps and `full@native` 108.

**Verdicts** (`python -m eam.bench.analyze --robust <rows>`):

| Verdict | Condition |
|---|---|
| Model-robust | Mean recovery ≥ 0.5 on every model where it is defined, with at least two such models |
| Model-dependent | ≥ 0.5 on some models only |
| Not effective | < 0.5 on every model where it is defined |

The table also reports, per model:
- the range of recovery over instances;
- Δscore versus the floor;
- the number of successes;
- the median cost ratio.

**Interpreting the cost side.** A method is cost-effective for a model if its cost ratio is below 100% at non-inferior recovery. Comparing against the *cached* ceiling cost (also reported) shows whether the method beats simply using the long window with caching on.

## 7. Reproducing

```bash
.venv/bin/python -m eam.bench suite real_v1 --n 5 --workers 4 --backend claude-cli --model cc-haiku --aux-model cc-haiku
.venv/bin/python -m eam.bench suite real_v2 --n 3 --workers 4 --backend claude-cli --model cc-haiku --aux-model cc-haiku
.venv/bin/python -m eam.bench report results/<file>.jsonl
.venv/bin/python -m eam.bench suite real_v3 --n 3 --workers 6 --backend claude-cli --model cc-sonnet --aux-model cc-sonnet
.venv/bin/python -m eam.bench.analyze --robust results/real_v3-*.jsonl
```
