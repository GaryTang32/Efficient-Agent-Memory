# `ledger_audit` across models: data larger than the window, three rounds (Claude Code CLI)

> **Note (2026-10-24):** the Haiku rows here were recorded before a harness bug was fixed: a retried empty reply had its prompt tokens summed into the context size, which can cause false overflows. The output-cap continuation bug did not exist yet. Haiku `ledger_audit` was rerun on the corrected harness; see `docs/results/2026-10-24-automem-evaluation.md`. Sonnet and Opus rows are unaffected (short replies, no empty-reply retries observed).


**Phase 1 (each method alone) plus the first phase-2 combinations, on Haiku, Sonnet and Opus.** Date 2026-10-22.

Raw rows (git-ignored, under `results/`): `real_v2-cli-haiku.jsonl`, `real_v2-cli-sonnet.jsonl`, `real_v2-cli-opus.jsonl`.
Regenerate the table with `python -m eam.bench.analyze <those files>`. Metric definitions are in `docs/methodology.md` §3.

## Setup

- **Task** (`eam/bench/tasks/ledger_audit.py`), seeds 0–2. Each round is a *fresh session*: nothing from earlier rounds is in the conversation.
  - **Round 1:** total the payments to 5 vendors across 16 monthly ledgers.
  - **Round 2:** use the round-1 totals and 8 refund files to give net spend and the top vendor.
  - **Round 3:** apply the `DISCOUNTS` file to give payables and their sum.
  - **Size:** the data is ≈113K real tokens, against an enforced **48K-token window**.
  - **Scoring:** 16 exact checks. `success` means all three rounds are exact.
- **Environment rules** (identical for every method; `docs/methodology.md` §2):
  - The window is enforced silently (*unaware* condition): a request over 48K ends that round as `context_overflow`.
  - Per-step observation budget of 6K, with recoverable offload (`read_artifact`).
  - A `calc` tool.
  - At most 2 nudges after a malformed reply.
- **Models:** Claude Code aliases `haiku`, `sonnet` and `opus`. The same model serves as the agent, the ReSum summariser and the folding branches.
- **Cost:** Claude Code's reported list price.
- **Methods:**

  | Spec | Paper / repo | Provenance |
  |---|---|---|
  | `full` | baseline | — |
  | `obs_mask` | observation masking: window 2, ≥300 tokens, using AttnCompress's artifact settings; the baseline in AgentDiet and AttnCompress | baseline |
  | `agentdiet` | AgentDiet (FSE'26; PKU + ByteDance) | official prompt + Algorithm 1 |
  | `resum:max_context_k=40` | ReSum (Tongyi Lab, Alibaba; not accepted at ICLR'26, so used as a baseline) | official prompts. Trigger = 0.9 × (40K − 1K) tokens, just under the window. |
  | `folding` | Context-Folding / FoldAgent (ICML'26; ByteDance Seed + CMU, Stanford) | official protocol and prompts, ≤5 branches |
  | `fs_workspace` | FS-Researcher (ACL'26, USTC) file-system workspace; Manus "file system as context" | our minimal port: `write_note` / `read_notes`, persistent across sessions |
  | `fs_workspace+obs_mask`, `fs_workspace+resum:…` | phase-2 combinations | — |

- **Coverage:**
  - Haiku and Sonnet: 3 seeds × every spec.
  - Opus, to bound cost (see Spend): 3 seeds of `resum` and `fs_workspace+resum`; seed 0 of `full`, `fs_workspace` and `fs_workspace+obs_mask`.
  - AgentDiet was run on Haiku only. On Sonnet, all three runs ended at the first reflection call when Sonnet's API safeguards rejected it. We report those as errored and did not try to work around the safeguard. AgentDiet was not run on Opus.

## Results (medians; success = all 3 rounds exact)

| Model | Method | Success | Mean score | Round 1 / 2 / 3 score | Overflow | Median $/run (vs full) | $/success | Peak ctx | Cache hit | Steps | Agent $ / side-call $ |
|---|---|---|---|---|---|---|---|---|---|---|---|
| Haiku | `fs_workspace+resum` | 0/3 | **0.41** | 0.67 / 0.22 / 0.33 | 0/3 | $0.142 (222%) | ∞ | 43.6K | 54% | 60 | 0.109 / 0.033 |
| Haiku | `resum` | 0/3 | **0.41** | 1.00 / 0.22 / 0.00 | 0/3 | $0.305 (478%) | ∞ | 45.2K | 43% | 76 | 0.204 / 0.101 |
| Haiku | `obs_mask` | 0/3 | 0.06 | 0.00 / 0.17 / 0.00 | 0/3 | $0.208 (325%) | ∞ | 41.3K | 7% | 54 | 0.208 / 0 |
| Haiku | `agentdiet` | 0/3 | 0.04 | 0.00 / 0.11 / 0.00 | 1/3 | $0.394 (618%) | ∞ | 41.7K | 7% | 47 | 0.198 / 0.196 |
| Haiku | `fs_workspace+obs_mask` | 0/3 | 0.02 | 0.00 / 0.06 / 0.00 | 3/3 | $0.388 (608%) | ∞ | 43.4K | 8% | 74 | 0.388 / 0 |
| Haiku | `fs_workspace` | 0/3 | 0.00 | 0 / 0 / 0 | 3/3 | $0.061 (95%) | ∞ | 46.5K | 67% | 26 | 0.061 / 0 |
| Haiku | `full` | 0/3 | 0.00 | 0 / 0 / 0 | 3/3 | $0.064 (100%) | ∞ | 42.7K | 51% | 29 | 0.064 / 0 |
| Haiku | `folding` | 0/3 | 0.00 | 0 / 0 / 0 | 3/3 | $0.084 (132%) | ∞ | 47.9K | 65% | 29 | 0.061 / 0.021 |
| Sonnet | **`fs_workspace+resum`** | **3/3** | 1.00 | 1 / 1 / 1 | 0/3 | **$1.356 (165%)** | **$1.32** | 41.3K | 58% | 37 | 0.824 / 0.548 |
| Sonnet | `fs_workspace+obs_mask` | **3/3** | 1.00 | 1 / 1 / 1 | 0/3 | $2.041 (248%) | $2.38 | **24.3K** | 15% | 43 | 2.041 / 0 |
| Sonnet | `resum` | 1/3 | 0.80 | 1.00 / 0.56 / 0.83 | 0/3 | $3.091 (375%) | $9.03 | 40.4K | 58% | 67 | 1.689 / 1.395 |
| Sonnet | `obs_mask` | 0/3 | 0.65 | 1.00 / 0.28 / 0.67 | 0/3 | $6.654 (807%) | ∞ | 26.7K | 12% | 106 | 6.654 / 0 |
| Sonnet | `fs_workspace` | 0/3 | 0.33 | 0 / 0 / 1.00 | 3/3 | $0.823 (100%) | ∞ | 47.3K | 79% | 37 | 0.823 / 0 |
| Sonnet | `folding` | 0/3 | 0.11 | 0.33 / 0 / 0 | 3/3 | $2.258 (274%) | ∞ | 46.1K | 75% | 40 | 0.855 / 1.403 |
| Sonnet | `full` | 0/3 | 0.00 | 0 / 0 / 0 | 3/3 | $0.824 (100%) | ∞ | 44.8K | 76% | 33 | 0.824 / 0 |
| Sonnet | `agentdiet` | — (3 errored: safeguards) | | | | | | | | | |
| Opus | **`fs_workspace+resum`** | **3/3** | 1.00 | 1 / 1 / 1 | 0/3 | **$2.701 (184%)** | **$2.58** | 38.6K | 60% | 37 | 1.613 / 1.040 |
| Opus | `fs_workspace+obs_mask` | 1/1 | 1.00 | 1 / 1 / 1 | 0/1 | $3.507 (239%) | $3.51 | 24.9K | 15% | 38 | 3.507 / 0 |
| Opus | `resum` | 2/3 | 0.89 | 1.00 / 1.00 / 0.67 | 0/3 | $4.929 (336%) | $6.98 | 40.7K | 60% | 67 | 2.958 / 1.972 |
| Opus | `fs_workspace` | 0/1 | 0.00 | 0 / 0 / 0 | 1/1 | $1.582 (108%) | ∞ | 44.3K | 75% | 32 | 1.582 / 0 |
| Opus | `full` | 0/1 | 0.00 | 0 / 0 / 0 | 1/1 | $1.469 (100%) | ∞ | 44.9K | 78% | 38 | 1.469 / 0 |

Errored runs, recorded and excluded from the medians:
- Sonnet `agentdiet`, seeds 0–2: safeguard rejection, as above.
- Haiku `resum`, seed 2: one CLI call timed out after 240 s. The run was repeated and the repeat is the row counted above (score 0.44).

## Findings

1. **No single published method solves the task on any model. One combination does, on every model strong enough to use it.**
   - `fs_workspace+resum` went 3/3 on Sonnet and 3/3 on Opus.
   - It is also the cheapest per success: $1.32 on Sonnet, versus $2.38 for `fs_workspace+obs_mask` and $9.03 for ReSum alone.
2. **The two halves cover different failures, and the round scores show which.**
   - **Overflow inside a session.** The data does not fit in 48K tokens.
     - `full`, `fs_workspace` and `folding` overflowed in essentially every run on every model, so they scored round 1 = 0.
     - Compaction methods (`resum`, `obs_mask`) never overflowed and got round 1 right on Sonnet and Opus.
   - **Loss across sessions.** Each round starts empty.
     - With compaction alone, the agent must re-derive rounds 1–2 from raw files in every round. That shows up as about 2× steps (67 vs 37) and about 2× cost.
     - It also causes errors. Sonnet `resum` drifted in round 2 in two of three runs: it redefined "total paid" as discounted. Opus `resum` refused round 3 once because "the round-2 net spends aren't available".
     - The workspace removes this: rounds 2–3 begin with `read_notes`.
   - **Workspace alone helps only partly.** Sonnet `fs_workspace` overflowed in rounds 1–2, yet still got round 3 exact in 3/3. The notes saved before each overflow carried enough partial results across sessions for round 3 to finish.
3. **Model capability gates every method here.**
   - Haiku scored at most 0.41 under any method. Its typical failure was not hallucination but **refusal**: it reported "I can't give reliable totals" when offloaded or masked outputs needed paging back.
   - With masking, Haiku read the placeholder "Environment Observation Ommited" as missing data (score 0.06). Sonnet and Opus scored 0.65+ with the same mechanism.
   - Prompt-only methods inherit the model's diligence. A cheaper model does not become viable on this task through memory management alone.
4. **Cost on a cached route follows cache behaviour, not token count.**
   - `fs_workspace+obs_mask` holds the smallest context (24K peak vs 41K). But masking rewrites history every step (15% cache hits), so it costs about 1.5× `fs_workspace+resum`, which resets only ~3 times per run (58–60% hits).
   - `obs_mask` alone is the worst case: 106 steps at 12% hits, 8× the baseline cost.
5. **Folding is not a fix for this kind of overflow without training.**
   - Sonnet branched 8–9 times per run and still overflowed in nearly every round.
   - Under the FoldAgent protocol a branch inherits MAIN's full history, so branches start near the limit, and branch calls cost more than MAIN ($1.40 vs $0.86 median).
   - Haiku branched 1–3 times per run, to no effect.
6. **AgentDiet** ran only on Haiku: 0.04 score at 6× cost.
   - Its reflection removes the very numbers this task needs later. It also breaks the cache every step (7% hits).
   - On `chain_hunt` it did keep accuracy (5/5), so its aggressiveness suits trajectories whose old steps are truly obsolete, not ones that accumulate facts.

## What this means for phase 2

- **Default recipe for long, multi-session agent work:** a persistent external workspace plus a rare, threshold-triggered summarising reset (ReSum), set just below the window. Rare resets keep the prompt cache alive; per-step masking or reflection does not.
- **Open questions for the next experiments:**
  1. A cheaper summariser, e.g. Haiku summarising for a Sonnet agent: side calls are 40% of the combination's cost.
  2. On Bedrock Converse, a second explicit `cachePoint` placed before the edited region, to test whether masking or AgentDiet can keep their token savings without the cache collapse seen on the CLI route.
  3. Whether the workspace instructions can be made strong enough for Haiku-class models, e.g. by forcing `read_notes` at session start, as Manus's "todo recitation" does.

## Spend (list price, ledger_audit only)

| Model | Spend |
|---|---|
| Haiku | $5.00 |
| Sonnet | $51.56 |
| Opus | $28.25 |

- A first Opus batch covering all 7 specs × 3 seeds was stopped before any run completed, because its projected cost was $100–250. Its partial spend is not in the rows.
- Including the `chain_hunt` cross-model rows, today's measured total is ≈$99 at list price. That excludes pilots and Haiku `chain_hunt` batch A.

## Caveats

- **Sample size:** 3 seeds per cell (1 for several Opus cells). Only effects that are consistent across seeds are claimed: 3/3 vs 0/3, and 2× cost.
- **Route:** CLI only. One end-of-conversation cache breakpoint, ~1.3K tokens of fixed overhead per call, no temperature control.
- **Bedrock:** cache layout effects can only be measured there.
- **`fs_workspace` is our own minimal port of the FS-Researcher idea.** That repo has no licence, so we did not copy its code.
- **The window is an emulated 48K limit**, not a model's native limit. Overflow detection uses calibrated token estimates plus the real prompt size reported after each call (`eam/agent/loop.py`).
