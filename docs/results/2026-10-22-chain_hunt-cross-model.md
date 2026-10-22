# `chain_hunt` across models: Haiku vs Sonnet vs Opus (Claude Code CLI)

**Phase 1: each method alone against the full-context baseline, repeated on three model sizes.** Date 2026-10-22.

Raw rows (git-ignored, under `results/`):
- `real_v1b-cli-haiku.jsonl`: Haiku, 5 seeds. This is batch B of `2026-10-22-chain_hunt-haiku-cli.md`.
- `real_v1-cli-sonnet.jsonl`: Sonnet, 3 seeds.
- `real_v1-cli-opus.jsonl`: Opus, 2 seeds.

To regenerate the table: `python -m eam.bench.analyze <those files>`. Metric definitions are in `docs/methodology.md` §3.

## Setup

The setup is the same as the Haiku report. Only the model changes, and the same model also serves as the auxiliary model (ReSum summariser).
- **Task:** `chain_hunt`, seeds 0…n−1. There are 20 long files, read one at a time, plus one correction; the answer must be an exact code.
- **Method settings:**
  - ReSum: `max_context_k=16`.
  - Turn control: limit 21.
  - Masking: window 2, ≥300 tokens.
  - Folding: FoldAgent protocol, ≤5 branches.
- **Route:** `claude-cli` with the aliases `haiku`, `sonnet` and `opus`. Cost is Claude Code's reported list price.
- **Not run on Sonnet or Opus:**
  - AgentDiet. Its reflection calls were rejected by Sonnet's API safeguards on `ledger_audit` (see the ledger report). We did not try to work around that.
  - Turn control on Opus. It was a no-op on the other two models, so it was skipped to save cost.

## Results (medians; success over runs)

| Model | Method | Success | Median $/run (vs full) | Agent prompt tok | Peak context | Cache hit | Side-call $ |
|---|---|---|---|---|---|---|---|
| Haiku | full | 4/5 | $0.019 (100%) | 445K | 40.5K | 88% | — |
| Haiku | turn_control | 5/5 | $0.019 (101%) | 451K | 41.1K | 87% | — |
| Haiku | folding | 4/5 | $0.019 (100%) | 449K | 40.7K | 88% | never branched |
| Haiku | ReSum | 5/5 | $0.024 (123%) | 211K | 15.3K | 57% | $0.008 |
| Haiku | AgentDiet | 5/5 | $0.079 (410%) | 364K | 14.3K | 7% | $0.039 |
| Haiku | obs_mask | **1/5** | $0.117 (608%) | 474K | 39.8K | 2% | — |
| Sonnet | full | 3/3 | $0.283 (100%) | 437K | 39.7K | 87% | — |
| Sonnet | turn_control | 3/3 | $0.276 (97%) | 438K | 39.9K | 87% | — |
| Sonnet | ReSum | 3/3 | $0.401 (142%) | 210K | 15.6K | 57% | $0.160 |
| Sonnet | obs_mask | **3/3** | $0.529 (187%) | 137K | **9.0K** | 8% | — |
| Sonnet | folding | 3/3 | $0.824 (291%) | 1,262K | 41.1K | 87% | $0.519 (branches) |
| Opus | full | 2/2 | $0.554 (100%) | 436K | 39.7K | 87% | — |
| Opus | folding | 2/2 | $0.560 (101%) | 446K | 40.3K | 87% | never branched |
| Opus | ReSum | 2/2 | $0.796 (144%) | 205K | 15.0K | 56% | $0.303 |
| Opus | obs_mask | 2/2 | $1.018 (184%) | 133K | **8.4K** | 8% | — |

Spend for this comparison, at list price: Haiku $1.50, Sonnet $6.55, Opus $5.85.

## Findings

1. **The task is too easy for Sonnet and Opus.** Every method solved every run, so on this task the methods differ only in cost and context size. `ledger_audit` is the discriminating task.
2. **The relative cost ranking holds across all three models.** Full context and turn control are cheapest (~100%), ReSum next (~123–144%), then observation masking (~184–608%). On a cached route the order is set by cache behaviour, not by token count:
   - ReSum resets the context about twice per run, so the cache survives in between: 57% hits.
   - Masking rewrites a step every turn: 2–8% hits.
3. **Observation masking depends on the model.**
   - Haiku solved only 1/5. It did not copy fragments into its own messages before the file text was masked.
   - Sonnet and Opus solved every run, holding a *4.5× smaller* peak context (8–9K vs 40K).
   - Masking is the most effective context *bound*, but only for models that take notes in their own turns. It still costs ~1.85× on a cached route.
4. **Folding without training is unpredictable.**
   - Haiku and Opus never called `branch`.
   - Sonnet branched in every run (2–4 times). Branches inherit MAIN's full history and re-read it, as the FoldAgent protocol prescribes, and branch calls cost $0.52 of the $0.82 median run.
   - In one Sonnet run (seed 2) MAIN delegated almost all of the work to branches. That run finished in 5 MAIN steps for $0.35, *cheaper* than full context. So the protocol can save money when the model uses it decisively.
5. **ReSum's premium is the summariser.**
   - On Haiku the summariser uses the same cheap model, so the premium stays small (+23%).
   - On Sonnet and Opus, summarising with the same large model costs +42–44%.
   - The paper's setting allows a separate summary model (ReSumTool-30B). Using a cheaper summariser, e.g. Haiku for a Sonnet agent, is a phase-2 test.
6. **Model price dominates method choice.** Opus ≈ 2× Sonnet ≈ 15× Haiku per run with the same method. On tasks Haiku can solve, Haiku with full context is the cheapest correct option by an order of magnitude.

## Caveats

- **Seeds:** 2 (Opus) and 3 (Sonnet). Every cell where all runs succeeded is consistent, but small n.
- **Route:** CLI only.
  - One end-of-conversation cache breakpoint.
  - ~1.3K tokens of fixed overhead per call.
  - No temperature control.
- **Prices:** list prices for the Claude Code aliases. Bedrock prices and cache behaviour with explicit `cachePoint`s may differ (see `docs/backends.md`).
