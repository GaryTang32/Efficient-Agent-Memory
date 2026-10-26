# AutoMemory v1 against the published methods and the official memory systems: four long tasks, Haiku and Sonnet

**Runs:** 2026-10-24 to 2026-10-26.

**Route:** Claude Code CLI, on the corrected harness (see *Harness corrections*).

**Raw rows** (git-ignored, under `results/`):
- `real_v4-{research_corpus,ops_stream,ledger_audit,repo_debug}-{haiku,sonnet}.jsonl`
- `extmem-{memoryos,lightmem,nemori}-haiku.jsonl`
- Sonnet cells for the earlier methods are reused from `real_v3-*-sonnet.jsonl` and `real_v2-cli-sonnet.jsonl`. Sonnet is unaffected by the corrected bugs: its replies are a few hundred tokens.

**Regenerate:**

```bash
F="results/real_v4-research_corpus-haiku.jsonl results/real_v4-research_corpus-sonnet.jsonl results/real_v3-research-sonnet.jsonl
   results/real_v4-ops_stream-haiku.jsonl results/real_v4-ops_stream-sonnet.jsonl results/real_v3-ops-sonnet.jsonl
   results/real_v4-ledger_audit-haiku.jsonl results/real_v4-ledger_audit-sonnet.jsonl results/real_v2-cli-sonnet.jsonl
   results/real_v4-repo_debug-haiku.jsonl results/real_v4-repo_debug-sonnet.jsonl
   results/extmem-memoryos-haiku.jsonl results/extmem-lightmem-haiku.jsonl results/extmem-nemori-haiku.jsonl"
python -m eam.bench.analyze --summary $F; python -m eam.bench.analyze --robust $F; python -m eam.bench.analyze --metrics $F
python scripts/fill_report.py docs/results/2026-10-24-automem-evaluation.md $F   # refreshes the tables below
```

## What was compared

**Tasks** (`docs/methodology.md` §2):

| Task | Shape |
|---|---|
| `research_corpus` | one long research session (BrowseComp-Plus style), 40K window |
| `ops_stream` | 10 sessions of stock-keeping with corrections to earlier days, 32K window |
| `ledger_audit` | 3 dependent sessions over data larger than the 48K window |
| `repo_debug` | 2 sessions fixing 4 bugs each in a real, generated Python library with real `pytest` runs, 16K window. Bugs are only reachable through end-to-end scenarios. |

**Methods:**
- **Anchors:**
  - `naive`: floor; no memory, no caching, no offload.
  - `naive@native` / `full@native`: ceiling; nothing lost, the model's own window. `naive@native` is also the cost reference.
  - `full`: full history with caching.
- **The best published methods per task:** ReSum, observation masking, Context-Folding, FS-Researcher's workspace.
- **This project's recipe:** `fs_workspace+resum`.
- **AutoMemory v1** (`docs/automem.md`), with Sonnet or Haiku as the summariser (`#aux=cc-haiku`).
- **Five ablations of AutoMemory:** one switch off at a time.
- **Three official long-term memory systems** through their own packages: MemoryOS (EMNLP'25), LightMem (ICLR'26) and Nemori (ACL'26). Each has the same ReSum compaction, so the memory system is the only difference.

**Runs per cell:**
- Haiku: 4 instances.
- Sonnet: 2–3.
- Official memory systems: 3 (Haiku).

**Recovery** = (score − floor) ÷ (ceiling − floor) on the same model and instance (§6 of the methodology). It can exceed 1 where the method beats the unlimited-context run.

## Headline: across all four tasks

Computed from the rows: per-task means, then the mean over tasks. Cost is the median ratio to `naive@native` per task.

| Method | Haiku: solved | Haiku: mean recovery (lowest task) | Haiku: cost per task | Sonnet: solved | Sonnet: mean recovery (lowest task) | Sonnet: cost per task |
|---|---|---|---|---|---|---|
| **AutoMemory, Haiku summariser** | — | — | — | **10/10** | **1.05 (1.00)** | 19% · 122% · 90% · 61% |
| AutoMemory | 7/16 | **0.91 (0.67)** | 52% · 69% · 118% · 92% | 9/10 | 1.05 (0.99) | 29% · 212% · 111% · 83% |
| Workspace + ReSum | **11/16** | 0.89 (0.67) | 39% · 100% · 102% · 282% | 8/10 | 0.98 (0.75) | 29% · 81% · 119% · 70% |
| ReSum | 4/16 | 0.57 (0.00) | 40% · 184% · 204% · 108% | 8/10 | 0.98 (0.93) | 22% · 384% · 248% · 124% |
| Observation masking | — | — | — | 3/10 | 0.56 (0.23) | 37% · 1616% · 526% · 340% |
| `full` (history + caching) | 1/16 | 0.08 | 7% · 27% · 36% · 54% | 0/10 | 0.06 | 7% · 80% · 71% · 93% |
| `naive` (floor) | 1/16 | 0.00 | — | 0/10 | 0.00 | — |
| `naive@native` (ceiling) | 9/16 | 1.00 | 100% | 8/10 | 1.00 | 100% |

Task order in the cost columns: `research_corpus` · `ops_stream` · `ledger_audit` · `repo_debug`.

**Verdicts** (`--robust`; recovery ≥ 0.5 on both models):
- **AutoMemory and workspace + ReSum are the only methods that are model-robust on all four tasks.**
- ReSum is model-robust on three tasks (model-dependent on `repo_debug`: Haiku 0.00, Sonnet 1.00).
- Masking is robust on one.

Per task, with every metric: tables below.

<!-- HEADLINE -->
**ledger_audit** — success · accuracy · recovery · cost vs `naive@native` · rounds · minutes (medians; recovery defined only for methods)

| method | cc-haiku | cc-sonnet |
|---|---|---|
| `naive` | 0/4 · 0.00 · — · 4% · 11 · 1.1 | 0/3 · 0.00 · — · 24% · 13 · 1.1 |
| `full` | 0/4 · 0.00 · 0.00 · 36% · 28 · 4.4 | 0/3 · 0.00 · 0.00 · 71% · 33 · 3.2 |
| `naive@native` | 2/4 · 0.82 · — · 100% · 11 · 3.0 | 1/3 · 0.85 · — · 100% · 15 · 2.2 |
| `automem` | 1/4 · 0.85 · 1.13 · 118% · 66 · 16.0 | 3/3 · 1.00 · 1.19 · 111% · 34 · 5.6 |
| `automem#aux=cc-haiku` | — | 3/3 · 1.00 · 1.19 · 90% · 36 · 6.7 |
| `automem:compact=mask` | 0/4 · 0.22 · 0.32 · 207% · 75 · 14.9 | — |
| `automem:compact=none` | 0/4 · 0.04 · 0.06 · 62% · 64 · 11.3 | — |
| `automem:guard=0` | 3/4 · 0.97 · 1.26 · 93% · 52 · 11.5 | — |
| `automem:keep_recent=0` | 1/4 · 0.60 · 0.83 · 91% · 62 · 14.6 | — |
| `automem:recall=false,autosave=false` | 0/4 · 0.64 · 0.75 · 127% · 66 · 19.1 | — |
| `ext_memory:backend=lightmem+resum:max_context_k=40` | 0/3 · 0.48 · 0.56 · 159% · 78 · 27.5 | — |
| `ext_memory:backend=memoryos+resum:max_context_k=40` | 1/3 · 0.59 · 0.80 · 100% · 41 · 13.2 | — |
| `ext_memory:backend=nemori+resum:max_context_k=40` | 0/3 · 0.54 · 0.61 · 152% · 80 · 22.8 | — |
| `folding` | — | 0/3 · 0.11 · 0.11 · 188% · 40 · 8.5 |
| `fs_workspace` | 0/4 · 0.00 · 0.00 · 46% · 30 · 5.8 | 0/3 · 0.33 · 0.40 · 72% · 37 · 3.6 |
| `fs_workspace+obs_mask` | — | 3/3 · 1.00 · 1.19 · 179% · 43 · 4.4 |
| `fs_workspace+resum:max_context_k=40` | 3/4 · 0.97 · 1.24 · 102% · 58 · 13.4 | 3/3 · 1.00 · 1.19 · 119% · 37 · 3.9 |
| `obs_mask` | — | 0/3 · 0.65 · 0.78 · 526% · 106 · 11.2 |
| `resum:max_context_k=40` | 0/4 · 0.51 · 0.62 · 204% · 92 · 18.3 | 1/3 · 0.80 · 0.93 · 248% · 67 · 7.5 |

**ops_stream** — success · accuracy · recovery · cost vs `naive@native` · rounds · minutes (medians; recovery defined only for methods)

| method | cc-haiku | cc-sonnet |
|---|---|---|
| `naive` | 0/4 · 0.20 · — · 14% · 30 · 5.6 | 0/2 · 0.19 · — · 28% · 29 · 2.4 |
| `full` | 0/4 · 0.20 · 0.00 · 27% · 56 · 7.4 | 0/2 · 0.17 · -0.03 · 80% · 54 · 4.4 |
| `naive@native` | 0/4 · 0.96 · — · 100% · 30 · 13.3 | 2/2 · 1.00 · — · 100% · 30 · 4.3 |
| `automem` | 0/4 · 0.84 · 0.84 · 69% · 82 · 22.1 | 1/2 · 0.99 · 0.99 · 212% · 74 · 14.4 |
| `automem#aux=cc-haiku` | — | 2/2 · 1.00 · 1.00 · 122% · 66 · 14.8 |
| `automem:compact=mask` | 0/4 · 0.09 · -0.14 · 175% · 152 · 34.7 | — |
| `automem:compact=none` | 0/4 · 0.42 · 0.28 · 55% · 104 · 24.9 | — |
| `automem:guard=0` | 1/4 · 0.70 · 0.64 · 74% · 78 · 19.1 | — |
| `automem:keep_recent=0` | 1/4 · 0.91 · 0.93 · 91% · 94 · 29.7 | — |
| `automem:recall=false,autosave=false` | 1/4 · 0.89 · 0.91 · 75% · 94 · 24.1 | — |
| `ext_memory:backend=lightmem+resum:max_context_k=26` | 0/3 · 0.69 · 0.64 · 157% · 144 · 36.5 | — |
| `ext_memory:backend=memoryos+resum:max_context_k=26` | 0/3 · 0.69 · 0.64 · 129% · 137 · 36.1 | — |
| `ext_memory:backend=nemori+resum:max_context_k=26` | 0/3 · 0.61 · 0.55 · 129% · 109 · 37.9 | — |
| `folding` | — | 0/2 · 0.20 · 0.01 · 308% · 90 · 24.4 |
| `fs_workspace` | 0/4 · 0.37 · 0.22 · 38% · 62 · 13.7 | 1/2 · 0.99 · 0.99 · 72% · 52 · 6.3 |
| `fs_workspace+resum:max_context_k=26` | 2/4 · 0.95 · 0.99 · 100% · 111 · 37.1 | 1/2 · 0.99 · 0.98 · 81% · 55 · 6.5 |
| `obs_mask` | — | 0/2 · 0.38 · 0.23 · 1616% · 322 · 40.3 |
| `resum:max_context_k=26` | 0/4 · 0.71 · 0.67 · 184% · 159 · 44.7 | 2/2 · 1.00 · 1.00 · 384% · 121 · 17.5 |

**repo_debug** — success · accuracy · recovery · cost vs `naive@native` · rounds · minutes (medians; recovery defined only for methods)

| method | cc-haiku | cc-sonnet |
|---|---|---|
| `naive` | 1/4 · 0.62 · — · 68% · 14 · 1.7 | 0/2 · 0.25 · — · 58% · 13 · 1.5 |
| `full` | 1/4 · 0.62 · 0.33 · 54% · 14 · 1.6 | 0/2 · 0.50 · 0.25 · 93% · 10 · 2.2 |
| `naive@native` | 4/4 · 1.00 · — · 100% · 18 · 2.2 | 2/2 · 1.00 · — · 100% · 16 · 2.2 |
| `automem` | 3/4 · 0.88 · 0.67 · 92% · 22 · 3.0 | 2/2 · 1.00 · 1.00 · 83% · 14 · 2.0 |
| `automem#aux=cc-haiku` | — | 2/2 · 1.00 · 1.00 · 61% · 15 · 2.3 |
| `automem:compact=mask` | 2/4 · 0.75 · 0.33 · 261% · 40 · 6.2 | — |
| `automem:compact=none` | 1/4 · 0.62 · 0.33 · 125% · 24 · 4.1 | — |
| `automem:guard=0` | 0/4 · 0.47 · -0.08 · 86% · 14 · 2.3 | — |
| `automem:keep_recent=0` | 3/4 · 0.88 · 0.67 · 253% · 28 · 9.1 | — |
| `automem:recall=false,autosave=false` | 3/4 · 0.88 · 0.67 · 203% · 31 · 5.1 | — |
| `ext_memory:backend=lightmem+resum:max_context_k=13` | 1/3 · 0.67 · 0.50 · 190% · 28 · 6.0 | — |
| `ext_memory:backend=memoryos+resum:max_context_k=13` | 0/3 · 0.33 · 0.00 · 113% · 18 · 3.6 | — |
| `ext_memory:backend=nemori+resum:max_context_k=13` | 0/3 · 0.50 · 0.00 · 87% · 16 · 3.7 | — |
| `fs_workspace+resum:max_context_k=13` | 3/4 · 0.88 · 0.67 · 282% · 34 · 6.0 | 1/2 · 0.75 · 0.75 · 70% · 12 · 1.7 |
| `obs_mask` | 1/4 · 0.62 · 0.33 · 155% · 28 · 3.0 | 0/2 · 0.50 · 0.25 · 340% · 32 · 5.4 |
| `resum:max_context_k=13` | 0/4 · 0.50 · 0.00 · 108% · 20 · 2.7 | 2/2 · 1.00 · 1.00 · 124% · 18 · 2.8 |

**research_corpus** — success · accuracy · recovery · cost vs `naive@native` · rounds · minutes (medians; recovery defined only for methods)

| method | cc-haiku | cc-sonnet |
|---|---|---|
| `naive` | 0/4 · 0.00 · — · 26% · 28 · 9.4 | 0/3 · 0.00 · — · 27% · 27 · 2.0 |
| `full` | 0/4 · 0.00 · 0.00 · 7% · 28 · 4.4 | 0/3 · 0.00 · 0.00 · 7% · 27 · 1.7 |
| `naive@native` | 3/4 · 0.75 · — · 100% · 60 · 12.4 | 3/3 · 1.00 · — · 100% · 52 · 4.7 |
| `full@native` | — | 3/3 · 1.00 · — · 17% · 52 · 4.0 |
| `automem` | 3/4 · 0.75 · 1.00 · 52% · 62 · 20.9 | 3/3 · 1.00 · 1.00 · 29% · 57 · 6.9 |
| `automem#aux=cc-haiku` | — | 3/3 · 1.00 · 1.00 · 19% · 58 · 6.1 |
| `automem:compact=mask` | 0/4 · 0.75 · 0.74 · 66% · 68 · 11.5 | — |
| `automem:compact=none` | 0/4 · 0.00 · 0.00 · 15% · 40 · 7.4 | — |
| `automem:guard=0` | 3/4 · 0.75 · 0.67 · 47% · 58 · 15.6 | — |
| `automem:keep_recent=0` | 2/4 · 0.72 · 0.63 · 31% · 60 · 13.1 | — |
| `automem:recall=false,autosave=false` | 2/4 · 0.50 · 0.67 · 42% · 54 · 12.3 | — |
| `folding` | — | 3/3 · 1.00 · 1.00 · 20% · 34 · 4.9 |
| `fs_workspace` | — | 0/3 · 0.00 · 0.00 · 7% · 25 · 1.9 |
| `fs_workspace+resum:max_context_k=33` | 3/4 · 0.75 · 0.67 · 39% · 60 · 16.0 | 3/3 · 1.00 · 1.00 · 29% · 60 · 5.8 |
| `obs_mask` | 3/4 · 0.86 · 0.81 · 77% · 82 · 13.2 | 3/3 · 1.00 · 1.00 · 37% · 59 · 4.4 |
| `resum:max_context_k=33` | 4/4 · 1.00 · 1.00 · 40% · 60 · 16.7 | 3/3 · 1.00 · 1.00 · 22% · 57 · 4.4 |
<!-- /HEADLINE -->

## Findings

1. **AutoMemory v1 works regardless of the model's strength, and on Sonnet it is the best method tested.**
   - It recovered at least two thirds of the window-induced loss on every task and both models.
   - **On Sonnet with a Haiku summariser it solved 10/10 runs, more than unlimited context itself (8/10).** It was the cheapest correct method on three of the four tasks: 19%, 90% and 61% of the unoptimised cost.
   - Sonnet `ops_stream` is the exception: the workspace alone is cheaper there (72%, 1/2 solved; AutoMemory 122%, 2/2).

2. **On Haiku it matches the recipe it builds on in recovery, not in full solves.**
   - Mean recovery is 0.91 vs 0.89 for workspace + ReSum, but it fully solved 7/16 runs vs 11/16.
   - It is clearly better on `repo_debug`: the same accuracy (0.88) at a third of the cost (92% vs 282%).
   - It is clearly better on `research_corpus`: recovery 1.00 vs 0.67.
   - It is worse on `ledger_audit` (0.85 vs 0.97), and slightly worse on `ops_stream` (0.84 vs 0.95) at lower cost (69% vs 100%).

3. **The ablations explain the Haiku gap, and what to change in v2.**
   - **Compaction is essential.** Without it, AutoMemory scored 0.00 / 0.42 / 0.04 / 0.62.
   - **ReSum beats masking as the compactor** (mean recovery 0.91 vs 0.31). On `ops_stream`, masking scored 0.09.
   - **The step guard is decisive on `repo_debug`**, where tool output is large relative to the 16K window: 0.88 with it, 0.47 without.
   - **The guard hurts on `ledger_audit`** (0.85 with it, 0.97 without). There it offloads ledger files that the agent then does not fully page back. v2 should offload only what would actually overflow the window (`guard` closer to 1.0), or compact first and offload only if compaction is not enough.
   - **Recall + autosave and keeping recent steps** did not change Haiku's accuracy beyond the noise of 4 seeds. On `repo_debug` they halve the cost (keep_recent off: 253%; recall off: 203%; on: 92%).

4. **A cheaper summariser is free accuracy-wise and saves 20–40%.** With Haiku summarising for Sonnet, accuracy was the same on every task, and cost fell:

   | Task | Sonnet summariser | Haiku summariser |
   |---|---|---|
   | `research_corpus` | 29% | 19% |
   | `ops_stream` | 212% | 122% |
   | `ledger_audit` | 111% | 90% |
   | `repo_debug` | 83% | 61% |

5. **The official long-term memory systems are weaker than a plain note workspace on agent tasks.** All have the same ReSum compaction; Haiku, 3 instances each:

   | Memory | `ops_stream` | `ledger_audit` | `repo_debug` |
   |---|---|---|---|
   | Workspace + ReSum | 0.95 · 100% | 0.97 · 102% | 0.88 · 282% |
   | AutoMemory | 0.84 · 69% | 0.85 · 118% | 0.88 · 92% |
   | MemoryOS | 0.69 · 129% | 0.59 · 100% | 0.33 · 113% |
   | LightMem | 0.69 · 157% | 0.48 · 159% | 0.67 · 190% |
   | Nemori | 0.61 · 129% | 0.54 · 152% | 0.50 · 87% |

   - They are conversational memories: user profiles, episodes, facts. They compress away the exact numbers and identifiers that agent tasks depend on. In the smoke test, LightMem's extraction kept "User reported the stock of SKUs…" without the figures.
   - Their own LLM calls add cost.
   - On `repo_debug` they also give no protection inside a session: their second sessions overflowed the 16K window, as plain ReSum does on Haiku.

6. **The corrected harness overturned the earlier Haiku conclusions.**
   - Plain ReSum on Haiku `research_corpus` is 4/4 (1.00) here, against 0.20 in the 2026-10-23 report.
   - Masking is no longer the only Haiku method that works there: ReSum, AutoMemory and workspace + ReSum recover 0.67–1.00.
   - The 2026-10-23 conclusions for Sonnet stand.

7. **Cost, time and turns.**
   - Solving a long task within a bounded window costs roughly what unlimited context costs uncached (60–120%), and 3–7× what it costs *cached* when the window is not binding (`full@native`: 17% on Sonnet `research_corpus`).
   - Memory methods pay off where the window really binds, or where work spans sessions.
   - AutoMemory took 14–82 agent rounds per run. Wall-clock time:
     - Haiku: 3–22 minutes.
     - Sonnet: 2–15 minutes.
   - Every cell's tokens (uncached / cache read / cache write / output), peak context, cache hit rate, tool calls, LLM calls, wall-clock and model time: `--metrics` tables below.

## AutoMemory v2: changes the data support

| Change | Evidence |
|---|---|
| Use a cheaper summariser by default | finding 4 |
| Guard only what would overflow (`guard≈1.0`), or compact before offloading | finding 3: `ledger_audit` 0.85 → 0.97 with the guard off; `repo_debug` needs a guard |
| Keep ReSum as the compactor; drop the masking option for multi-session work | finding 3 |
| Keep recall, autosave and keep_recent for their cost effect on code tasks; re-test their accuracy effect with more seeds | finding 3 |

## Harness corrections in this round

All Haiku cells were rerun after these fixes; rows recorded before them are not used.

1. **Retried CLI calls.** A retry after an empty reply summed both attempts' prompt tokens into the context size, causing false overflows. Fixed: billing keeps the sum, while size checks use the final attempt.
2. **Internal continuation turns.** When a reply hit the 8K output cap, Claude Code continued in internal turns and reported the summed usage (a 2.6K-token request was reported as 12.9K). Fixed: the cap is now 32K, and the context size is (prompt − output) ÷ turns.
3. **Usage limits.** The CLI's usage limit used to turn queued runs into errors. The client now waits for the stated reset and retries. Errored rows are rerun, and `analyze` drops an error once its run has succeeded.
4. **`repo_debug` redesign** after pilots: the first version, with bugs named by unit tests, was solved by every method in ≤ 18 steps.
5. **Prompt-size predictor.** It is now an affine fit (fixed overhead + slope), and every retry or continuation is logged (`llm_retry`).

## Caveats

- **Few runs:** 2–4 per cell (3 for the official memory systems). Only large, consistent differences are claimed.
- **One route.** The Claude Code CLI writes the cache at 2× input, reads Sonnet's cache at 0.05×, and bills Haiku requests above 100K tokens at 5×. Bedrock prices differ (`2026-10-24-bedrock-validation-plan.md`): there the ranking is unchanged and history-editing methods get about a third cheaper. Bedrock itself could not be run (no valid credentials).
- **Synthetic tasks, plus one task on real code.** `repo_debug` is real code and real tests, but generated, with planted bugs.
- **The official memory systems ran with their default settings and the minimal runtime fixes listed in `scripts/memory_sidecar.py`.** Their LLM is Haiku. Better-tuned settings might narrow the gap.

## Spend (list price; rows in this report, including the reused Sonnet rows)

<!-- SPEND -->
cc-haiku: $40.13 · cc-sonnet: $214.68 · total $254.81
<!-- /SPEND -->

## Full tables

### Model-normalised comparison (`--robust`)

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
| `automem:compact=mask` | 0.32 [0.06…1.08] (+0.22) · 0/4 · 207% | — | does not recover (one model only) |
| `automem:compact=none` | 0.06 [0.00…0.17] (+0.04) · 0/4 · 62% | — | does not recover (one model only) |
| `automem:guard=0` | 1.26 [0.89…1.64] (+0.97) · 3/4 · 93% | — | recovers (one model only) |
| `automem:keep_recent=0` | 0.83 [0.00…1.50] (+0.60) · 1/4 · 91% | — | recovers (one model only) |
| `automem:recall=false,autosave=false` | 0.75 [0.09…1.25] (+0.64) · 0/4 · 127% | — | recovers (one model only) |
| `ext_memory:backend=lightmem+resum:max_context_k=40` | 0.56 [0.39…0.67] (+0.48) · 0/3 · 159% | — | recovers (one model only) |
| `ext_memory:backend=memoryos+resum:max_context_k=40` | 0.80 [0.39…1.64] (+0.59) · 1/3 · 100% | — | recovers (one model only) |
| `ext_memory:backend=nemori+resum:max_context_k=40` | 0.61 [0.55…0.68] (+0.54) · 0/3 · 152% | — | recovers (one model only) |
| `folding` | — | 0.11 [0.00…0.33] (+0.11) · 0/3 · 188% | does not recover (one model only) |
| `fs_workspace` | 0.00 [0.00…0.00] (+0.00) · 0/4 · 46% | 0.40 [0.33…0.43] (+0.33) · 0/3 · 72% | not effective |
| `fs_workspace+obs_mask` | — | 1.19 [1.00…1.29] (+1.00) · 3/3 · 179% | recovers (one model only) |
| `fs_workspace+resum:max_context_k=40` | 1.24 [1.00…1.64] (+0.97) · 3/4 · 102% | 1.19 [1.00…1.29] (+1.00) · 3/3 · 119% | model-robust |
| `full` | 0.00 [0.00…0.00] (+0.00) · 0/4 · 36% | 0.00 [0.00…0.00] (+0.00) · 0/3 · 71% | not effective |
| `obs_mask` | — | 0.78 [0.61…0.86] (+0.65) · 0/3 · 526% | recovers (one model only) |
| `resum:max_context_k=40` | 0.62 [0.50…0.67] (+0.51) · 0/4 · 204% | 0.93 [0.79…1.00] (+0.80) · 1/3 · 248% | model-robust |

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
| `automem:compact=mask` | -0.14 [-0.22…-0.05] (-0.11) · 0/4 · 175% | — | does not recover (one model only) |
| `automem:compact=none` | 0.28 [0.10…0.57] (+0.22) · 0/4 · 55% | — | does not recover (one model only) |
| `automem:guard=0` | 0.64 [-0.24…1.02] (+0.50) · 1/4 · 74% | — | recovers (one model only) |
| `automem:keep_recent=0` | 0.93 [0.83…1.02] (+0.71) · 1/4 · 91% | — | recovers (one model only) |
| `automem:recall=false,autosave=false` | 0.91 [0.74…1.12] (+0.69) · 1/4 · 75% | — | recovers (one model only) |
| `ext_memory:backend=lightmem+resum:max_context_k=26` | 0.64 [0.49…0.78] (+0.49) · 0/3 · 157% | — | recovers (one model only) |
| `ext_memory:backend=memoryos+resum:max_context_k=26` | 0.64 [0.58…0.67] (+0.49) · 0/3 · 129% | — | recovers (one model only) |
| `ext_memory:backend=nemori+resum:max_context_k=26` | 0.55 [0.45…0.62] (+0.41) · 0/3 · 129% | — | recovers (one model only) |
| `folding` | — | 0.01 [-0.11…0.12] (+0.01) · 0/2 · 308% | does not recover (one model only) |
| `fs_workspace` | 0.22 [0.00…0.49] (+0.17) · 0/4 · 38% | 0.99 [0.98…1.00] (+0.80) · 1/2 · 72% | model-dependent |
| `fs_workspace+resum:max_context_k=26` | 0.99 [0.81…1.12] (+0.75) · 2/4 · 100% | 0.98 [0.96…1.00] (+0.79) · 1/2 · 81% | model-robust |
| `full` | 0.00 [0.00…0.00] (+0.00) · 0/4 · 27% | -0.03 [-0.07…0.02] (-0.02) · 0/2 · 80% | not effective |
| `obs_mask` | — | 0.23 [0.18…0.29] (+0.19) · 0/2 · 1616% | does not recover (one model only) |
| `resum:max_context_k=26` | 0.67 [0.62…0.70] (+0.51) · 0/4 · 184% | 1.00 [1.00…1.00] (+0.81) · 2/2 · 384% | model-robust |

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
| `automem:compact=mask` | 0.33 [0.00…1.00] (+0.12) · 2/4 · 261% | — | does not recover (one model only) |
| `automem:compact=none` | 0.33 [0.00…1.00] (+0.00) · 1/4 · 125% | — | does not recover (one model only) |
| `automem:guard=0` | -0.08 [-1.00…0.75] (-0.16) · 0/4 · 86% | — | does not recover (one model only) |
| `automem:keep_recent=0` | 0.67 [0.00…1.00] (+0.25) · 3/4 · 253% | — | recovers (one model only) |
| `automem:recall=false,autosave=false` | 0.67 [0.00…1.00] (+0.25) · 3/4 · 203% | — | recovers (one model only) |
| `ext_memory:backend=lightmem+resum:max_context_k=13` | 0.50 [0.00…1.00] (+0.00) · 1/3 · 190% | — | recovers (one model only) |
| `ext_memory:backend=memoryos+resum:max_context_k=13` | 0.00 [0.00…0.00] (-0.33) · 0/3 · 113% | — | does not recover (one model only) |
| `ext_memory:backend=nemori+resum:max_context_k=13` | 0.00 [0.00…0.00] (-0.17) · 0/3 · 87% | — | does not recover (one model only) |
| `fs_workspace+resum:max_context_k=13` | 0.67 [0.00…1.00] (+0.25) · 3/4 · 282% | 0.75 [0.50…1.00] (+0.50) · 1/2 · 70% | model-robust |
| `full` | 0.33 [0.00…1.00] (+0.00) · 1/4 · 54% | 0.25 [0.00…0.50] (+0.25) · 0/2 · 93% | not effective |
| `obs_mask` | 0.33 [0.00…1.00] (+0.00) · 1/4 · 155% | 0.25 [0.00…0.50] (+0.25) · 0/2 · 340% | not effective |
| `resum:max_context_k=13` | 0.00 [0.00…0.00] (-0.12) · 0/4 · 108% | 1.00 [1.00…1.00] (+0.75) · 2/2 · 124% | model-dependent |

### research_corpus: anchors per model (means over instances)

| model | instances | floor score (`naive`) | ceiling score (unlimited context) | headroom | floor $ | `full@native` $ | `naive@native` $ (cost reference) |
|---|---|---|---|---|---|---|---|
| cc-haiku | 4 | 0.00 | 0.75 | 0.75 | 0.090 | nan | 0.299 |
| cc-sonnet | 3 | 0.00 | 1.00 | 1.00 | 1.097 | 0.706 | 4.349 |

### research_corpus: method effect relative to each model's own floor and ceiling

| method | cc-haiku: recovery (Δscore) · success · $ vs `naive@native` | cc-sonnet: recovery (Δscore) · success · $ vs `naive@native` | verdict |
|---|---|---|---|
| `automem` | 1.00 [1.00…1.00] (+0.75) · 3/4 · 52% | 1.00 [1.00…1.00] (+1.00) · 3/3 · 29% | model-robust |
| `automem#aux=cc-haiku` | — | 1.00 [1.00…1.00] (+1.00) · 3/3 · 19% | recovers (one model only) |
| `automem:compact=mask` | 0.74 [0.56…0.89] (+0.75) · 0/4 · 66% | — | recovers (one model only) |
| `automem:compact=none` | 0.00 [0.00…0.00] (+0.00) · 0/4 · 15% | — | does not recover (one model only) |
| `automem:guard=0` | 0.67 [0.00…1.00] (+0.75) · 3/4 · 47% | — | recovers (one model only) |
| `automem:keep_recent=0` | 0.63 [0.00…1.00] (+0.72) · 2/4 · 31% | — | recovers (one model only) |
| `automem:recall=false,autosave=false` | 0.67 [0.00…1.00] (+0.50) · 2/4 · 42% | — | recovers (one model only) |
| `folding` | — | 1.00 [1.00…1.00] (+1.00) · 3/3 · 20% | recovers (one model only) |
| `fs_workspace` | — | 0.00 [0.00…0.00] (+0.00) · 0/3 · 7% | does not recover (one model only) |
| `fs_workspace+resum:max_context_k=33` | 0.67 [0.00…1.00] (+0.75) · 3/4 · 39% | 1.00 [1.00…1.00] (+1.00) · 3/3 · 29% | model-robust |
| `full` | 0.00 [0.00…0.00] (+0.00) · 0/4 · 7% | 0.00 [0.00…0.00] (+0.00) · 0/3 · 7% | not effective |
| `obs_mask` | 0.81 [0.44…1.00] (+0.86) · 3/4 · 77% | 1.00 [1.00…1.00] (+1.00) · 3/3 · 37% | model-robust |
| `resum:max_context_k=33` | 1.00 [1.00…1.00] (+1.00) · 4/4 · 40% | 1.00 [1.00…1.00] (+1.00) · 3/3 · 22% | model-robust |
<!-- /ROBUST -->

### Every measured quantity (`--metrics`)

<!-- METRICS -->
### ledger_audit — accuracy and effort

| model | method | runs | success | accuracy (mean score) | agentic rounds | tool calls | sessions | LLM calls incl. side calls | overflowed runs | wall-clock (min) | model time (min) |
|---|---|---|---|---|---|---|---|---|---|---|---|
| cc-haiku | `automem:guard=0` | 4 | 3/4 | 0.97 | 52 | 168 | 3 | 56 | 0/4 | 11.5 | 8.8 |
| cc-haiku | `fs_workspace+resum:max_context_k=40` | 4 | 3/4 | 0.97 | 58 | 208 | 3 | 62 | 0/4 | 13.4 | 10.8 |
| cc-haiku | `automem` | 4 | 1/4 | 0.85 | 66 | 234 | 3 | 78 | 0/4 | 16.0 | 12.0 |
| cc-haiku | `naive@native` | 4 | 2/4 | 0.82 | 11 | 68 | 3 | 11 | 0/4 | 3.0 | 2.5 |
| cc-haiku | `automem:recall=false,autosave=false` | 4 | 0/4 | 0.64 | 66 | 223 | 3 | 74 | 0/4 | 19.1 | 12.1 |
| cc-haiku | `automem:keep_recent=0` | 4 | 1/4 | 0.60 | 62 | 215 | 3 | 75 | 0/4 | 14.6 | 9.5 |
| cc-haiku | `ext_memory:backend=memoryos+resum:max_context_k=40` | 3 | 1/3 | 0.59 | 41 | 292 | 3 | 44 | 0/3 | 13.2 | 6.9 |
| cc-haiku | `ext_memory:backend=nemori+resum:max_context_k=40` | 3 | 0/3 | 0.54 | 80 | 505 | 3 | 99 | 0/3 | 22.8 | 12.6 |
| cc-haiku | `resum:max_context_k=40` | 4 | 0/4 | 0.51 | 92 | 578 | 3 | 102 | 0/4 | 18.3 | 13.4 |
| cc-haiku | `ext_memory:backend=lightmem+resum:max_context_k=40` | 3 | 0/3 | 0.48 | 78 | 623 | 3 | 90 | 0/3 | 27.5 | 17.9 |
| cc-haiku | `automem:compact=mask` | 4 | 0/4 | 0.22 | 75 | 321 | 3 | 74 | 1/4 | 14.9 | 11.2 |
| cc-haiku | `automem:compact=none` | 4 | 0/4 | 0.04 | 64 | 186 | 3 | 63 | 4/4 | 11.3 | 7.3 |
| cc-haiku | `naive` | 4 | 0/4 | 0.00 | 11 | 68 | 3 | 8 | 4/4 | 1.1 | 0.4 |
| cc-haiku | `full` | 4 | 0/4 | 0.00 | 28 | 140 | 3 | 25 | 4/4 | 4.4 | 2.5 |
| cc-haiku | `fs_workspace` | 4 | 0/4 | 0.00 | 30 | 154 | 3 | 27 | 4/4 | 5.8 | 4.5 |
| cc-sonnet | `automem#aux=cc-haiku` | 3 | 3/3 | 1.00 | 36 | 69 | 3 | 40 | 0/3 | 6.7 | 5.0 |
| cc-sonnet | `automem` | 3 | 3/3 | 1.00 | 34 | 65 | 3 | 38 | 0/3 | 5.6 | 4.1 |
| cc-sonnet | `fs_workspace+resum:max_context_k=40` | 3 | 3/3 | 1.00 | 37 | — | 3 | 39 | 0/3 | 3.9 | 2.3 |
| cc-sonnet | `fs_workspace+obs_mask` | 3 | 3/3 | 1.00 | 43 | — | 3 | 43 | 0/3 | 4.4 | 2.7 |
| cc-sonnet | `naive@native` | 3 | 1/3 | 0.85 | 15 | 69 | 3 | 15 | 0/3 | 2.2 | 1.5 |
| cc-sonnet | `resum:max_context_k=40` | 3 | 1/3 | 0.80 | 67 | — | 3 | 74 | 0/3 | 7.5 | 4.4 |
| cc-sonnet | `obs_mask` | 3 | 0/3 | 0.65 | 106 | — | 3 | 106 | 0/3 | 11.2 | 7.2 |
| cc-sonnet | `fs_workspace` | 3 | 0/3 | 0.33 | 37 | — | 3 | 35 | 3/3 | 3.6 | 2.2 |
| cc-sonnet | `folding` | 3 | 0/3 | 0.11 | 40 | — | 3 | 82 | 3/3 | 8.5 | 5.3 |
| cc-sonnet | `naive` | 3 | 0/3 | 0.00 | 13 | 65 | 3 | 10 | 3/3 | 1.1 | 0.7 |
| cc-sonnet | `full` | 3 | 0/3 | 0.00 | 33 | — | 3 | 30 | 3/3 | 3.2 | 2.0 |

### ledger_audit — tokens and cost

| model | method | prompt tokens | uncached input | cache read | cache write | output | peak context | cache hit | $ per run | $ per run if uncached | $ per success |
|---|---|---|---|---|---|---|---|---|---|---|---|
| cc-haiku | `automem:guard=0` | 1.24M | 0K | 743K | 474K | 124K | 41K | 64% | 0.170 | 0.191 | 0.224 |
| cc-haiku | `fs_workspace+resum:max_context_k=40` | 1.18M | 0K | 645K | 500K | 148K | 41K | 60% | 0.175 | 0.193 | 0.231 |
| cc-haiku | `automem` | 1.34M | 0K | 712K | 623K | 163K | 34K | 53% | 0.220 | 0.222 | 0.820 |
| cc-haiku | `naive@native` | 391K | 391K | 0K | 0K | 20K | 118K | 0% | 0.169 | 0.169 | 0.353 |
| cc-haiku | `automem:recall=false,autosave=false` | 1.18M | 0K | 580K | 552K | 171K | 34K | 56% | 0.203 | 0.214 | ∞ |
| cc-haiku | `automem:keep_recent=0` | 1.00M | 0K | 468K | 540K | 120K | 34K | 47% | 0.172 | 0.161 | 0.690 |
| cc-haiku | `ext_memory:backend=memoryos+resum:max_context_k=40` | 918K | 0K | 335K | 593K | 94K | 45K | 38% | 0.161 | 0.136 | 0.512 |
| cc-haiku | `ext_memory:backend=nemori+resum:max_context_k=40` | 1.91M | 0K | 803K | 1.19M | 154K | 43K | 46% | 0.327 | 0.283 | ∞ |
| cc-haiku | `resum:max_context_k=40` | 2.25M | 0K | 944K | 1.26M | 174K | 45K | 43% | 0.349 | 0.312 | ∞ |
| cc-haiku | `ext_memory:backend=lightmem+resum:max_context_k=40` | 1.97M | 0K | 736K | 1.23M | 176K | 45K | 39% | 0.342 | 0.285 | ∞ |
| cc-haiku | `automem:compact=mask` | 1.80M | 0K | 144K | 1.66M | 150K | 43K | 10% | 0.407 | 0.255 | ∞ |
| cc-haiku | `automem:compact=none` | 2.07M | 0K | 1.88M | 191K | 85K | 48K | 91% | 0.101 | 0.254 | ∞ |
| cc-haiku | `naive` | 40K | 40K | 0K | 0K | 4K | 12K | 0% | 0.006 | 0.006 | ∞ |
| cc-haiku | `full` | 453K | 0K | 251K | 199K | 30K | 44K | 56% | 0.065 | 0.063 | ∞ |
| cc-haiku | `fs_workspace` | 568K | 0K | 347K | 221K | 67K | 46K | 61% | 0.087 | 0.093 | ∞ |
| cc-sonnet | `automem#aux=cc-haiku` | 700K | 0K | 352K | 335K | 38K | 35K | 52% | 1.000 | 0.959 | 0.990 |
| cc-sonnet | `automem` | 678K | 0K | 389K | 247K | 24K | 36K | 61% | 1.268 | 1.590 | 1.388 |
| cc-sonnet | `fs_workspace+resum:max_context_k=40` | 679K | 0K | 400K | 284K | 19K | 41K | 58% | 1.356 | 1.537 | 1.320 |
| cc-sonnet | `fs_workspace+obs_mask` | 547K | 0K | 76K | 447K | 24K | 24K | 15% | 2.041 | 1.337 | 2.379 |
| cc-sonnet | `naive@native` | 534K | 534K | 0K | 0K | 7K | 118K | 0% | 1.139 | 1.139 | 3.515 |
| cc-sonnet | `resum:max_context_k=40` | 1.55M | 0K | 895K | 656K | 35K | 40K | 58% | 3.091 | 3.506 | 9.035 |
| cc-sonnet | `obs_mask` | 1.67M | 0K | 182K | 1.54M | 48K | 27K | 12% | 6.654 | 3.829 | ∞ |
| cc-sonnet | `fs_workspace` | 723K | 0K | 573K | 147K | 19K | 47K | 79% | 0.823 | 1.634 | ∞ |
| cc-sonnet | `folding` | 1.74M | 0K | 1.31M | 427K | 35K | 46K | 75% | 2.258 | 3.921 | ∞ |
| cc-sonnet | `naive` | 117K | 117K | 0K | 0K | 4K | 44K | 0% | 0.270 | 0.270 | ∞ |
| cc-sonnet | `full` | 654K | 0K | 496K | 158K | 14K | 45K | 76% | 0.824 | 1.451 | ∞ |

### ops_stream — accuracy and effort

| model | method | runs | success | accuracy (mean score) | agentic rounds | tool calls | sessions | LLM calls incl. side calls | overflowed runs | wall-clock (min) | model time (min) |
|---|---|---|---|---|---|---|---|---|---|---|---|
| cc-haiku | `naive@native` | 4 | 0/4 | 0.96 | 30 | 188 | 10 | 30 | 0/4 | 13.3 | 11.8 |
| cc-haiku | `fs_workspace+resum:max_context_k=26` | 4 | 2/4 | 0.95 | 111 | 226 | 10 | 124 | 1/4 | 37.1 | 22.2 |
| cc-haiku | `automem:keep_recent=0` | 4 | 1/4 | 0.91 | 94 | 200 | 10 | 116 | 0/4 | 29.7 | 21.3 |
| cc-haiku | `automem:recall=false,autosave=false` | 4 | 1/4 | 0.89 | 94 | 208 | 10 | 110 | 0/4 | 24.1 | 17.4 |
| cc-haiku | `automem` | 4 | 0/4 | 0.84 | 82 | 172 | 10 | 98 | 0/4 | 22.1 | 14.5 |
| cc-haiku | `resum:max_context_k=26` | 4 | 0/4 | 0.71 | 159 | 782 | 10 | 190 | 2/4 | 44.7 | 36.1 |
| cc-haiku | `automem:guard=0` | 4 | 1/4 | 0.70 | 78 | 156 | 10 | 90 | 3/4 | 19.1 | 12.5 |
| cc-haiku | `ext_memory:backend=lightmem+resum:max_context_k=26` | 3 | 0/3 | 0.69 | 144 | 677 | 10 | 177 | 2/3 | 36.5 | 25.8 |
| cc-haiku | `ext_memory:backend=memoryos+resum:max_context_k=26` | 3 | 0/3 | 0.69 | 137 | 503 | 10 | 159 | 3/3 | 36.1 | 25.4 |
| cc-haiku | `ext_memory:backend=nemori+resum:max_context_k=26` | 3 | 0/3 | 0.61 | 109 | 570 | 10 | 148 | 3/3 | 37.9 | 25.2 |
| cc-haiku | `automem:compact=none` | 4 | 0/4 | 0.42 | 104 | 195 | 10 | 102 | 3/4 | 24.9 | 18.0 |
| cc-haiku | `fs_workspace` | 4 | 0/4 | 0.37 | 62 | 140 | 10 | 56 | 4/4 | 13.7 | 10.5 |
| cc-haiku | `naive` | 4 | 0/4 | 0.20 | 30 | 184 | 10 | 22 | 4/4 | 5.6 | 4.0 |
| cc-haiku | `full` | 4 | 0/4 | 0.20 | 56 | 266 | 10 | 48 | 4/4 | 7.4 | 4.0 |
| cc-haiku | `automem:compact=mask` | 4 | 0/4 | 0.09 | 152 | 516 | 10 | 152 | 0/4 | 34.7 | 23.8 |
| cc-sonnet | `naive@native` | 2 | 2/2 | 1.00 | 30 | 184 | 10 | 30 | 0/2 | 4.3 | 2.9 |
| cc-sonnet | `automem#aux=cc-haiku` | 2 | 2/2 | 1.00 | 66 | 141 | 10 | 80 | 0/2 | 14.8 | 11.0 |
| cc-sonnet | `resum:max_context_k=26` | 2 | 2/2 | 1.00 | 121 | 362 | 10 | 140 | 0/2 | 17.5 | 11.2 |
| cc-sonnet | `fs_workspace` | 2 | 1/2 | 0.99 | 52 | 85 | 10 | 52 | 0/2 | 6.3 | 3.7 |
| cc-sonnet | `automem` | 2 | 1/2 | 0.99 | 74 | 161 | 10 | 90 | 0/2 | 14.4 | 10.2 |
| cc-sonnet | `fs_workspace+resum:max_context_k=26` | 2 | 1/2 | 0.99 | 55 | 83 | 10 | 56 | 0/2 | 6.5 | 4.0 |
| cc-sonnet | `obs_mask` | 2 | 0/2 | 0.38 | 322 | 946 | 10 | 321 | 2/2 | 40.3 | 26.8 |
| cc-sonnet | `folding` | 2 | 0/2 | 0.20 | 90 | 150 | 10 | 172 | 2/2 | 24.4 | 16.4 |
| cc-sonnet | `naive` | 2 | 0/2 | 0.19 | 29 | 146 | 10 | 24 | 2/2 | 2.4 | 1.3 |
| cc-sonnet | `full` | 2 | 0/2 | 0.17 | 54 | 236 | 10 | 46 | 2/2 | 4.4 | 2.4 |

### ops_stream — tokens and cost

| model | method | prompt tokens | uncached input | cache read | cache write | output | peak context | cache hit | $ per run | $ per run if uncached | $ per success |
|---|---|---|---|---|---|---|---|---|---|---|---|
| cc-haiku | `naive@native` | 829K | 829K | 0K | 0K | 206K | 119K | 0% | 0.386 | 0.386 | ∞ |
| cc-haiku | `fs_workspace+resum:max_context_k=26` | 1.94M | 0K | 902K | 1.04M | 300K | 30K | 47% | 0.366 | 0.344 | 0.659 |
| cc-haiku | `automem:keep_recent=0` | 1.70M | 0K | 672K | 1.02M | 286K | 26K | 40% | 0.353 | 0.315 | 1.395 |
| cc-haiku | `automem:recall=false,autosave=false` | 1.48M | 0K | 630K | 853K | 221K | 23K | 45% | 0.287 | 0.259 | 1.009 |
| cc-haiku | `automem` | 1.40M | 0K | 589K | 809K | 175K | 24K | 43% | 0.255 | 0.227 | ∞ |
| cc-haiku | `resum:max_context_k=26` | 3.38M | 0K | 1.07M | 2.31M | 536K | 31K | 32% | 0.742 | 0.607 | ∞ |
| cc-haiku | `automem:guard=0` | 1.64M | 0K | 721K | 918K | 183K | 30K | 46% | 0.284 | 0.264 | 1.098 |
| cc-haiku | `ext_memory:backend=lightmem+resum:max_context_k=26` | 2.83M | 0K | 945K | 1.89M | 389K | 30K | 33% | 0.582 | 0.478 | ∞ |
| cc-haiku | `ext_memory:backend=memoryos+resum:max_context_k=26` | 2.66M | 0K | 926K | 1.73M | 336K | 31K | 35% | 0.524 | 0.434 | ∞ |
| cc-haiku | `ext_memory:backend=nemori+resum:max_context_k=26` | 2.24M | 0K | 810K | 1.43M | 357K | 31K | 32% | 0.472 | 0.402 | ∞ |
| cc-haiku | `automem:compact=none` | 2.31M | 0K | 1.95M | 359K | 228K | 32K | 84% | 0.205 | 0.345 | ∞ |
| cc-haiku | `fs_workspace` | 792K | 0K | 467K | 336K | 165K | 31K | 59% | 0.154 | 0.162 | ∞ |
| cc-haiku | `naive` | 194K | 194K | 0K | 0K | 66K | 26K | 0% | 0.052 | 0.052 | ∞ |
| cc-haiku | `full` | 672K | 0K | 338K | 325K | 53K | 31K | 52% | 0.095 | 0.094 | ∞ |
| cc-haiku | `automem:compact=mask` | 3.08M | 0K | 521K | 2.52M | 331K | 30K | 17% | 0.676 | 0.473 | ∞ |
| cc-sonnet | `naive@native` | 749K | 749K | 0K | 0K | 25K | 119K | 0% | 1.747 | 1.747 | 1.747 |
| cc-sonnet | `automem#aux=cc-haiku` | 1.13M | 0K | 459K | 671K | 85K | 23K | 42% | 2.127 | 1.656 | 2.127 |
| cc-sonnet | `resum:max_context_k=26` | 2.32M | 0K | 889K | 1.43M | 90K | 31K | 38% | 6.715 | 5.539 | 6.715 |
| cc-sonnet | `fs_workspace` | 649K | 0K | 412K | 237K | 27K | 28K | 63% | 1.256 | 1.565 | 2.511 |
| cc-sonnet | `automem` | 1.23M | 0K | 470K | 765K | 60K | 24K | 38% | 3.707 | 3.071 | 7.415 |
| cc-sonnet | `fs_workspace+resum:max_context_k=26` | 665K | 0K | 390K | 275K | 27K | 25K | 59% | 1.411 | 1.603 | 2.822 |
| cc-sonnet | `obs_mask` | 7.00M | 1K | 380K | 6.62M | 173K | 31K | 5% | 28.234 | 15.722 | ∞ |
| cc-sonnet | `folding` | 2.48M | 0K | 1.44M | 1.04M | 109K | 31K | 58% | 5.390 | 6.041 | ∞ |
| cc-sonnet | `naive` | 198K | 198K | 0K | 0K | 10K | 26K | 0% | 0.495 | 0.495 | ∞ |
| cc-sonnet | `full` | 605K | 0K | 303K | 302K | 16K | 32K | 50% | 1.393 | 1.366 | ∞ |

### repo_debug — accuracy and effort

| model | method | runs | success | accuracy (mean score) | agentic rounds | tool calls | sessions | LLM calls incl. side calls | overflowed runs | wall-clock (min) | model time (min) |
|---|---|---|---|---|---|---|---|---|---|---|---|
| cc-haiku | `naive@native` | 4 | 4/4 | 1.00 | 18 | 40 | 2 | 18 | 0/4 | 2.2 | 1.4 |
| cc-haiku | `automem` | 4 | 3/4 | 0.88 | 22 | 40 | 2 | 23 | 0/4 | 3.0 | 1.9 |
| cc-haiku | `automem:recall=false,autosave=false` | 4 | 3/4 | 0.88 | 31 | 74 | 2 | 36 | 0/4 | 5.1 | 3.4 |
| cc-haiku | `automem:keep_recent=0` | 4 | 3/4 | 0.88 | 28 | 56 | 2 | 32 | 0/4 | 9.1 | 6.5 |
| cc-haiku | `fs_workspace+resum:max_context_k=13` | 4 | 3/4 | 0.88 | 34 | 74 | 2 | 38 | 1/4 | 6.0 | 4.2 |
| cc-haiku | `automem:compact=mask` | 4 | 2/4 | 0.75 | 40 | 95 | 2 | 40 | 2/4 | 6.2 | 3.9 |
| cc-haiku | `ext_memory:backend=lightmem+resum:max_context_k=13` | 3 | 1/3 | 0.67 | 28 | 78 | 2 | 33 | 2/3 | 6.0 | 2.9 |
| cc-haiku | `full` | 4 | 1/4 | 0.62 | 14 | 32 | 2 | 13 | 3/4 | 1.6 | 1.0 |
| cc-haiku | `naive` | 4 | 1/4 | 0.62 | 14 | 32 | 2 | 12 | 3/4 | 1.7 | 1.1 |
| cc-haiku | `automem:compact=none` | 4 | 1/4 | 0.62 | 24 | 44 | 2 | 24 | 3/4 | 4.1 | 3.0 |
| cc-haiku | `obs_mask` | 4 | 1/4 | 0.62 | 28 | 64 | 2 | 28 | 3/4 | 3.0 | 1.8 |
| cc-haiku | `ext_memory:backend=nemori+resum:max_context_k=13` | 3 | 0/3 | 0.50 | 16 | 41 | 2 | 19 | 3/3 | 3.7 | 1.3 |
| cc-haiku | `resum:max_context_k=13` | 4 | 0/4 | 0.50 | 20 | 45 | 2 | 20 | 4/4 | 2.7 | 1.9 |
| cc-haiku | `automem:guard=0` | 4 | 0/4 | 0.47 | 14 | 32 | 2 | 14 | 2/4 | 2.3 | 1.6 |
| cc-haiku | `ext_memory:backend=memoryos+resum:max_context_k=13` | 3 | 0/3 | 0.33 | 18 | 44 | 2 | 21 | 3/3 | 3.6 | 2.4 |
| cc-sonnet | `automem#aux=cc-haiku` | 2 | 2/2 | 1.00 | 15 | 42 | 2 | 16 | 0/2 | 2.3 | 1.6 |
| cc-sonnet | `automem` | 2 | 2/2 | 1.00 | 14 | 36 | 2 | 15 | 0/2 | 2.0 | 1.3 |
| cc-sonnet | `naive@native` | 2 | 2/2 | 1.00 | 16 | 38 | 2 | 16 | 0/2 | 2.2 | 1.4 |
| cc-sonnet | `resum:max_context_k=13` | 2 | 2/2 | 1.00 | 18 | 46 | 2 | 20 | 0/2 | 2.8 | 1.9 |
| cc-sonnet | `fs_workspace+resum:max_context_k=13` | 2 | 1/2 | 0.75 | 12 | 36 | 2 | 13 | 1/2 | 1.7 | 1.1 |
| cc-sonnet | `full` | 2 | 0/2 | 0.50 | 10 | 30 | 2 | 9 | 2/2 | 2.2 | 1.8 |
| cc-sonnet | `obs_mask` | 2 | 0/2 | 0.50 | 32 | 86 | 2 | 32 | 2/2 | 5.4 | 3.9 |
| cc-sonnet | `naive` | 2 | 0/2 | 0.25 | 13 | 35 | 2 | 12 | 2/2 | 1.5 | 0.9 |

### repo_debug — tokens and cost

| model | method | prompt tokens | uncached input | cache read | cache write | output | peak context | cache hit | $ per run | $ per run if uncached | $ per success |
|---|---|---|---|---|---|---|---|---|---|---|---|
| cc-haiku | `naive@native` | 187K | 187K | 0K | 0K | 17K | 22K | 0% | 0.027 | 0.027 | 0.027 |
| cc-haiku | `automem` | 167K | 0K | 106K | 67K | 23K | 12K | 60% | 0.026 | 0.028 | 0.095 |
| cc-haiku | `automem:recall=false,autosave=false` | 285K | 0K | 141K | 150K | 48K | 12K | 53% | 0.053 | 0.052 | 0.095 |
| cc-haiku | `automem:keep_recent=0` | 294K | 0K | 145K | 149K | 76K | 12K | 50% | 0.069 | 0.067 | 0.125 |
| cc-haiku | `fs_workspace+resum:max_context_k=13` | 334K | 0K | 156K | 178K | 70K | 13K | 43% | 0.071 | 0.067 | 0.102 |
| cc-haiku | `automem:compact=mask` | 421K | 0K | 116K | 237K | 46K | 15K | 27% | 0.074 | 0.068 | 0.142 |
| cc-haiku | `ext_memory:backend=lightmem+resum:max_context_k=13` | 285K | 0K | 112K | 173K | 34K | 15K | 45% | 0.052 | 0.045 | 0.134 |
| cc-haiku | `full` | 93K | 0K | 55K | 30K | 13K | 14K | 65% | 0.013 | 0.016 | 0.067 |
| cc-haiku | `naive` | 98K | 98K | 0K | 0K | 13K | 12K | 0% | 0.017 | 0.017 | 0.072 |
| cc-haiku | `automem:compact=none` | 261K | 0K | 197K | 58K | 38K | 16K | 76% | 0.033 | 0.048 | 0.138 |
| cc-haiku | `obs_mask` | 211K | 0K | 49K | 162K | 23K | 15K | 24% | 0.044 | 0.032 | 0.168 |
| cc-haiku | `ext_memory:backend=nemori+resum:max_context_k=13` | 129K | 0K | 58K | 72K | 15K | 13K | 44% | 0.022 | 0.020 | ∞ |
| cc-haiku | `resum:max_context_k=13` | 150K | 0K | 78K | 72K | 25K | 14K | 50% | 0.028 | 0.027 | ∞ |
| cc-haiku | `automem:guard=0` | 102K | 0K | 55K | 54K | 29K | 12K | 48% | 0.026 | 0.025 | ∞ |
| cc-haiku | `ext_memory:backend=memoryos+resum:max_context_k=13` | 169K | 0K | 69K | 76K | 42K | 12K | 54% | 0.031 | 0.031 | ∞ |
| cc-sonnet | `automem#aux=cc-haiku` | 117K | 0K | 60K | 57K | 9K | 11K | 52% | 0.209 | 0.211 | 0.209 |
| cc-sonnet | `automem` | 101K | 0K | 50K | 50K | 8K | 10K | 50% | 0.282 | 0.277 | 0.282 |
| cc-sonnet | `naive@native` | 138K | 138K | 0K | 0K | 7K | 18K | 0% | 0.343 | 0.343 | 0.343 |
| cc-sonnet | `resum:max_context_k=13` | 148K | 0K | 67K | 81K | 9K | 15K | 45% | 0.425 | 0.390 | 0.425 |
| cc-sonnet | `fs_workspace+resum:max_context_k=13` | 85K | 0K | 41K | 45K | 6K | 13K | 48% | 0.239 | 0.227 | 0.478 |
| cc-sonnet | `full` | 66K | 0K | 33K | 33K | 19K | 12K | 50% | 0.325 | 0.321 | ∞ |
| cc-sonnet | `obs_mask` | 285K | 0K | 66K | 219K | 28K | 14K | 23% | 1.159 | 0.847 | ∞ |
| cc-sonnet | `naive` | 81K | 81K | 0K | 0K | 4K | 15K | 0% | 0.200 | 0.200 | ∞ |

### research_corpus — accuracy and effort

| model | method | runs | success | accuracy (mean score) | agentic rounds | tool calls | sessions | LLM calls incl. side calls | overflowed runs | wall-clock (min) | model time (min) |
|---|---|---|---|---|---|---|---|---|---|---|---|
| cc-haiku | `resum:max_context_k=33` | 4 | 4/4 | 1.00 | 60 | 67 | 1 | 62 | 0/4 | 16.7 | 13.6 |
| cc-haiku | `obs_mask` | 4 | 3/4 | 0.86 | 82 | 96 | 1 | 82 | 0/4 | 13.2 | 8.3 |
| cc-haiku | `fs_workspace+resum:max_context_k=33` | 4 | 3/4 | 0.75 | 60 | 72 | 1 | 62 | 0/4 | 16.0 | 11.7 |
| cc-haiku | `automem:guard=0` | 4 | 3/4 | 0.75 | 58 | 74 | 1 | 60 | 0/4 | 15.6 | 12.1 |
| cc-haiku | `automem` | 4 | 3/4 | 0.75 | 62 | 92 | 1 | 66 | 0/4 | 20.9 | 13.8 |
| cc-haiku | `automem:compact=mask` | 4 | 0/4 | 0.75 | 68 | 110 | 1 | 68 | 0/4 | 11.5 | 5.1 |
| cc-haiku | `naive@native` | 4 | 3/4 | 0.75 | 60 | 66 | 1 | 60 | 0/4 | 12.4 | 6.8 |
| cc-haiku | `automem:keep_recent=0` | 4 | 2/4 | 0.72 | 60 | 81 | 1 | 62 | 0/4 | 13.1 | 6.5 |
| cc-haiku | `automem:recall=false,autosave=false` | 4 | 2/4 | 0.50 | 54 | 71 | 1 | 56 | 0/4 | 12.3 | 9.4 |
| cc-haiku | `full` | 4 | 0/4 | 0.00 | 28 | 28 | 1 | 27 | 4/4 | 4.4 | 2.0 |
| cc-haiku | `automem:compact=none` | 4 | 0/4 | 0.00 | 40 | 50 | 1 | 38 | 4/4 | 7.4 | 3.9 |
| cc-haiku | `naive` | 4 | 0/4 | 0.00 | 28 | 27 | 1 | 27 | 3/4 | 9.4 | 5.9 |
| cc-sonnet | `full@native` | 3 | 3/3 | 1.00 | 52 | 51 | 1 | 52 | 0/3 | 4.0 | 1.7 |
| cc-sonnet | `automem#aux=cc-haiku` | 3 | 3/3 | 1.00 | 58 | 95 | 1 | 61 | 0/3 | 6.1 | 3.6 |
| cc-sonnet | `folding` | 3 | 3/3 | 1.00 | 34 | 33 | 1 | 69 | 0/3 | 4.9 | 2.1 |
| cc-sonnet | `resum:max_context_k=33` | 3 | 3/3 | 1.00 | 57 | 57 | 1 | 59 | 0/3 | 4.4 | 1.8 |
| cc-sonnet | `automem` | 3 | 3/3 | 1.00 | 57 | 94 | 1 | 60 | 0/3 | 6.9 | 4.4 |
| cc-sonnet | `fs_workspace+resum:max_context_k=33` | 3 | 3/3 | 1.00 | 60 | 95 | 1 | 63 | 0/3 | 5.8 | 2.9 |
| cc-sonnet | `obs_mask` | 3 | 3/3 | 1.00 | 59 | 58 | 1 | 59 | 0/3 | 4.4 | 1.7 |
| cc-sonnet | `naive@native` | 3 | 3/3 | 1.00 | 52 | 51 | 1 | 52 | 0/3 | 4.7 | 2.3 |
| cc-sonnet | `full` | 3 | 0/3 | 0.00 | 27 | 26 | 1 | 26 | 3/3 | 1.7 | 0.7 |
| cc-sonnet | `fs_workspace` | 3 | 0/3 | 0.00 | 25 | 39 | 1 | 24 | 3/3 | 1.9 | 0.8 |
| cc-sonnet | `naive` | 3 | 0/3 | 0.00 | 27 | 26 | 1 | 26 | 3/3 | 2.0 | 1.0 |

### research_corpus — tokens and cost

| model | method | prompt tokens | uncached input | cache read | cache write | output | peak context | cache hit | $ per run | $ per run if uncached | $ per success |
|---|---|---|---|---|---|---|---|---|---|---|---|
| cc-haiku | `resum:max_context_k=33` | 1.18M | 0K | 894K | 293K | 107K | 32K | 75% | 0.121 | 0.170 | 0.122 |
| cc-haiku | `obs_mask` | 1.13M | 0K | 182K | 945K | 75K | 21K | 14% | 0.231 | 0.152 | 0.326 |
| cc-haiku | `fs_workspace+resum:max_context_k=33` | 1.30M | 0K | 920K | 312K | 92K | 31K | 71% | 0.118 | 0.176 | 0.160 |
| cc-haiku | `automem:guard=0` | 1.25M | 0K | 912K | 337K | 132K | 31K | 73% | 0.143 | 0.191 | 0.211 |
| cc-haiku | `automem` | 1.39M | 0K | 956K | 391K | 139K | 30K | 72% | 0.153 | 0.209 | 0.233 |
| cc-haiku | `automem:compact=mask` | 1.07M | 0K | 177K | 841K | 48K | 26K | 19% | 0.195 | 0.134 | ∞ |
| cc-haiku | `naive@native` | 2.75M | 2.75M | 0K | 0K | 46K | 84K | 0% | 0.305 | 0.305 | 0.399 |
| cc-haiku | `automem:keep_recent=0` | 1.09M | 0K | 812K | 278K | 73K | 29K | 75% | 0.100 | 0.146 | 0.187 |
| cc-haiku | `automem:recall=false,autosave=false` | 1.09M | 0K | 799K | 295K | 122K | 30K | 73% | 0.128 | 0.170 | 0.239 |
| cc-haiku | `full` | 574K | 0K | 514K | 61K | 8K | 39K | 89% | 0.022 | 0.062 | ∞ |
| cc-haiku | `automem:compact=none` | 1.04M | 0K | 952K | 85K | 32K | 38K | 92% | 0.041 | 0.118 | ∞ |
| cc-haiku | `naive` | 622K | 622K | 0K | 0K | 44K | 39K | 0% | 0.084 | 0.084 | ∞ |
| cc-sonnet | `full@native` | 2.02M | 0K | 1.91M | 113K | 3K | 73K | 94% | 0.672 | 4.078 | 0.706 |
| cc-sonnet | `automem#aux=cc-haiku` | 1.03M | 0K | 794K | 231K | 15K | 29K | 77% | 0.752 | 1.799 | 0.892 |
| cc-sonnet | `folding` | 986K | 0K | 819K | 167K | 6K | 33K | 83% | 0.820 | 2.044 | 0.847 |
| cc-sonnet | `resum:max_context_k=33` | 979K | 0K | 788K | 191K | 5K | 32K | 80% | 0.894 | 2.008 | 0.900 |
| cc-sonnet | `automem` | 1.04M | 0K | 788K | 239K | 13K | 29K | 77% | 1.165 | 2.283 | 1.272 |
| cc-sonnet | `fs_workspace+resum:max_context_k=33` | 969K | 0K | 738K | 233K | 20K | 30K | 76% | 1.257 | 2.281 | 1.263 |
| cc-sonnet | `obs_mask` | 464K | 0K | 96K | 362K | 4K | 11K | 21% | 1.499 | 0.967 | 1.513 |
| cc-sonnet | `naive@native` | 2.01M | 2.01M | 0K | 0K | 3K | 72K | 0% | 4.055 | 4.055 | 4.349 |
| cc-sonnet | `full` | 530K | 0K | 472K | 58K | 1K | 38K | 89% | 0.291 | 1.074 | ∞ |
| cc-sonnet | `fs_workspace` | 453K | 0K | 399K | 55K | 4K | 38K | 88% | 0.295 | 0.943 | ∞ |
| cc-sonnet | `naive` | 530K | 530K | 0K | 0K | 2K | 38K | 0% | 1.075 | 1.075 | ∞ |
<!-- /METRICS -->
