# Methodology: how methods are compared

This document defines the tasks, conditions, metrics and procedure behind every result in `docs/results/`.
Code references are given so each number can be traced.

## 1. Unit of comparison

A **run** = one task instance (task family + seed) × one **technique spec** × one model/route.

- **Phase 1** compares each technique **alone** against the full-context baseline (`full`) on identical instances, models and routes.
- **Phase 2** compares **combinations** (specs joined with `+`, or the presets in `eam/presets.py`).

A spec such as `resum:max_context_k=40` sets parameters. Everything else uses the official defaults listed in `docs/literature_review.md` and in each module's docstring.

Every result row records the technique's **provenance label**: `official prompt/algorithm`, `baseline`, `ported from paper`, `engineering rules`, or `provisional`. That label shows how close the implementation is to the authors' own (`eam/techniques/*.py`, `provenance` attribute).

## 2. Tasks (`eam/bench/tasks/`)

| Task | What it stresses | Steps (real model) | Scoring |
|---|---|---|---|
| `chain_hunt` | Long sequential trajectory. 20 long files (~1.5K tokens each) must be read one at a time, since each names the next. One fragment per stage must survive until the end. One correction sends the agent back to an earlier file (focus shift). | ~21 | Exact code. `score` = fraction of the 20 fragments correct, in order. |
| `ledger_audit` | Data larger than the context window, plus multiple rounds. 16 monthly ledgers and 8 refund files (≈81K estimated / ≈113K real tokens) against a 48K-token window. Three dependent rounds, each a **fresh session**: totals → net of refunds → discounted payables. | ~20–60 over 3 rounds | 16 checks: 5 totals; 5 nets + highest vendor; 5 payables + sum. `score` = fraction correct. `success` = all three rounds exact. |
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

## 6. Reproducing

```bash
.venv/bin/python -m eam.bench suite real_v1 --n 5 --workers 4 --backend claude-cli --model cc-haiku --aux-model cc-haiku
.venv/bin/python -m eam.bench suite real_v2 --n 3 --workers 4 --backend claude-cli --model cc-haiku --aux-model cc-haiku
.venv/bin/python -m eam.bench report results/<file>.jsonl
```
