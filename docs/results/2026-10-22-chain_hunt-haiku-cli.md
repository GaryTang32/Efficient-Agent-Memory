# First real comparison — `chain_hunt`, Claude Haiku via Claude Code CLI

**Phase 1: each method alone, against the full-context baseline.** Date 2026-10-22.
Raw rows: `results/real_v1-cli-haiku.jsonl` (batch A) and `results/real_v1b-cli-haiku.jsonl` (batch B); `results/` is git-ignored.

## Setup
- **Task:** `chain_hunt`, seeds 0–4. Follow 20 long files (≈1.5K tokens each) one at a time, keep one fragment per stage, and apply one correction that points back to an earlier file. Exact answer required. The partial score is the fraction of fragments right.
- **Model:** the `haiku` alias of Claude Code, as both agent and auxiliary model (AgentDiet reflector, ReSum summariser). Route: `claude-cli`.
- **Caching:** automatic, handled by Claude Code. Its one breakpoint sits at the end of the conversation, and our cache points are not used on this route.
- **Cost:** Claude Code's reported `total_cost_usd`, at list price.
- **Method settings** are the official defaults:
  - AgentDiet: a=2, b=1, θ=500.
  - Observation masking: window 2, at least 300 tokens.
  - ReSum: official prompts; trigger = 0.9 × (16K − 1K) tokens, scaled down from 32K because this task peaks at ~40K.
  - Folding: the FoldAgent protocol, at most 5 branches.
  - Turn control: limit 21, the 75th percentile of the baseline's turn counts (`eam.bench calibrate`).
- **Batch B vs batch A:** B adds a harness rule that re-prompts at most twice when a reply has neither a tool call nor `FINAL ANSWER`. Batch A had three step-1 degenerate outputs (from the text tool protocol) that ended runs before any technique acted. B is the headline batch; A agrees with it.

## Results (medians over 5 runs; success over 5)

| Method (provenance) | Success B (A) | Median $/run | Agent prompt tokens | Peak context | Cache hit | Median LLM time |
|---|---|---|---|---|---|---|
| Full context (baseline) | 4/5 (5/5) | **$0.0192** | 445K | 40.5K | 88% | 57 s |
| Turn control, limit 21 (official strings) | **5/5** | $0.0195 | 451K | 41.1K | 87% | 62 s |
| Context-Folding (FoldAgent protocol) | 4/5 (4/5) | $0.0192 | 449K | 40.7K | 88% | 63 s |
| ReSum (official prompts) | **5/5** (4/5) | $0.0237 | 177K (+35K summariser) | **15.3K** | 57% | 60 s |
| AgentDiet (official prompt + Alg. 1) | **5/5** (4/5) | $0.0786 | **198K** (+171K reflector) | **14.3K** | 7% | 130 s |
| Observation masking (published settings) | 1/5 (0/5) | $0.117 | 474K | 39.8K | 2% | 214 s |

Means are distorted by outliers. One baseline run and one folding run each grew to ~110K peak context and cost ~$0.14–0.15, which is model variance, not a method effect. Use the medians.

## What this shows
1. **On a heavily cached route, cutting tokens is not cutting cost.**
   - AgentDiet removed 56% of the agent's prompt tokens, in line with the paper's −40% to −60%, and kept accuracy at 100%. Yet each run cost ~4× the baseline.
     - About half of that is the reflector's own calls.
     - The other half is the agent's cache collapsing from 88% to 7% hits. AgentDiet edits a *different* older step every turn, and with a single end-of-conversation cache breakpoint every edit invalidates every previously written cache entry.
   - The paper's cost accounting includes cached prices, but its harness (Trae Agent) also puts its breakpoint at the end. Whether real savings survive therefore depends on where cache breakpoints sit relative to the edited window. **Bedrock Converse lets us test exactly that**, with a second `cachePoint` placed just before step s−a (planned as a phase-2 combination, `cache_layout`+`agentdiet`).
2. **ReSum bounded the context (15K vs 40K peak) and kept accuracy** at a small cost premium (+23%). Each reset is a cache miss, but resets are rare (≈2 per run).
3. **Observation masking fails this task.** Haiku did not copy fragments into its own messages before their file contents were masked, and re-opened files are masked again two steps later. It usually refused to guess rather than inventing an answer; one run did fabricate a code. Masking also rewrites history every step: 2% cache hits, 6× cost.
4. **Turn control at the natural length costs nothing and helped slightly** (5/5). The task has a fixed minimum path (21 turns), so this measures only the overhead of the reminders. A real test needs a task whose length varies across runs.
5. **Folding was a no-op: Haiku never called `branch`.** The FoldAgent paper trains the folding behaviour (FoldGRPO). Prompt-only, a small model does not adopt it here. Worth repeating with a stronger model.

## Caveats
- One model (Haiku), one task, 5 seeds per method. Differences of one success are within noise.
- **CLI route:**
  - No temperature control.
  - Claude Code adds ~1.3K tokens of fixed overhead per call.
  - Our cache points are not applied, so cache-layout effects can only be measured on Bedrock.
- Costs are Claude Code's list-price figures for the `haiku` alias. Bedrock prices and models differ.
