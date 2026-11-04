# AutoMemory v3 ablation: OpenClaw and SJC as the compaction step (2026-11-04)

**Question.** In [`2026-11-04-new-methods.md`](2026-11-04-new-methods.md), two methods were the cheapest strong compactors on several tasks:
- **OpenClaw's structured summary**, the host compactor of the SJC paper (five fixed sections);
- **SJC's source-judged pruning**, which deletes summary entries that did not come from what the tools returned.

Does either one improve AutoMemory v2 when it replaces ReSum as v2's compaction step?

**Answer: not as a default.**
- **Haiku:** every variant is worse than v2, on accuracy or cost or both.
  - Mean score 0.77–0.81, against 0.88 for v2.
  - Mean cost 114–124% of the ceiling, against 85%.
- **Sonnet:** all variants tie v2 within noise.
  - **SJC on ReSum** solved 8 of 8 runs (v2: 6 of 8) at 66% of the ceiling's cost (v2: 64%). It fixed v2's one weak cell (`ops_stream`: 0.93 → 1.00).
  - With 2 runs per cell, that is a hint, not a result.

**Decision.**
- **v2 stays the default** (`automem_v2`).
- **`compact=sjc` is an option for strong agent models.** It is not adopted as a default, because it lowered Haiku's `research_corpus` and `ledger_audit` scores.
- **OpenClaw adds nothing over ReSum inside AutoMemory.**

## Variants

All are AutoMemory v2:
- workspace notes, recall and autosave;
- the in-step guard;
- head/tail previews of tool outputs above 10% of the window;
- compaction at 0.75 × window, keeping the last 2 steps.

Only the compaction step differs.

| Spec | Compaction step |
|---|---|
| `automem:ingest=0.1` (v2) | ReSum's summary (official prompts) |
| `automem:ingest=0.1,compact=sjc` | ReSum's summary, pruned by SJC. A Haiku judge reads the compacted span and drops entries not sourced from a tool output or the previous summary (τ = 0.5). |
| `automem:ingest=0.1,compact=openclaw` | OpenClaw safeguard summary: Decisions, Open TODOs, Constraints/Rules, Pending user asks, Exact identifiers, with one corrective retry |
| `automem:ingest=0.1,compact=openclaw+sjc` | OpenClaw summary, pruned by SJC (the SJC paper's "Prompting + SJC") |

**How the hosts are adapted inside AutoMemory:** OpenClaw restarts from the task statement, and AutoMemory re-adds the notes and the recent steps as it does for ReSum (`keep_last=False, first="task"` in `eam/techniques/sjc.py`).

**Setup:**
- The four long tasks, with the same seeds, windows and trigger as v2.
- Haiku: 4 seeds. Sonnet: 2 seeds, with Haiku as the summariser and the SJC judge.
- 72 new runs, none errored.
- Anchors and v1/v2 rows are reused unchanged.

## Results

Each cell: mean score · median cost vs `naive@native` · median peak context vs the ceiling's peak · runs solved. The last column is the mean over the four tasks: score (lowest task), recovery, cost, peak, solved, total spend.

**Haiku (4 seeds):**

| Variant | research_corpus | ops_stream | ledger_audit | repo_debug | Mean |
|---|---|---|---|---|---|
| v1 (`automem`) | 0.75 · 50% · 35% · 3/4 | 0.84 · 66% · 20% · 0/4 | 0.85 · 131% · 29% · 1/4 | 0.88 · 96% · 54% · 3/4 | 0.83 (0.75) · rec 0.89 · 86% · 35% · 7/16 · $2.90 |
| **v2** (ReSum) | 0.75 · 50% · 34% · 3/4 | 0.87 · 76% · 20% · 1/4 | 0.89 · 87% · 30% · 3/4 | 1.00 · 126% · 56% · 4/4 | **0.88 (0.75) · rec 0.99 · 85%** · 35% · **11/16 · $2.45** |
| v2 + SJC on ReSum | 0.64 · 45% · 35% · 1/4 | 0.93 · 139% · 20% · 1/4 | 0.68 · 136% · 29% · 1/4 | 1.00 · 138% · 55% · 4/4 | 0.81 (0.64) · rec 0.91 · 114% · 35% · 7/16 · $3.87 |
| v2 + OpenClaw | 0.75 · 48% · 34% · 3/4 | 0.82 · 95% · 20% · 2/4 | 0.86 · 95% · 29% · 2/4 | 0.75 · 225% · 56% · 2/4 | 0.79 (0.75) · rec 0.80 · 116% · 35% · 9/16 · $2.84 |
| v2 + OpenClaw + SJC | 0.47 · 46% · 34% · 1/4 | 0.93 · 90% · 20% · 0/4 | 0.68 · 136% · 27% · 0/4 | 1.00 · 225% · 57% · 4/4 | 0.77 (0.47) · rec 0.85 · 124% · 34% · 5/16 · $3.16 |

**Sonnet (2 seeds, Haiku summariser):**

| Variant | research_corpus | ops_stream | ledger_audit | repo_debug | Mean |
|---|---|---|---|---|---|
| v1 (`automem#aux=cc-haiku`, 3 / 2 / 3 / 2 runs) | 1.00 · 19% · — · 3/3 | 1.00 · 122% · — · 2/2 | 1.00 · 88% · — · 3/3 | 1.00 · 61% · — · 2/2 | 1.00 (1.00) · rec 1.04 · 72% · 35% · 10/10 · $10.32 |
| **v2** (ReSum) | 1.00 · 20% · 40% · 2/2 | 0.93 · 79% · 20% · 0/2 | 1.00 · 104% · 30% · 2/2 | 1.00 · 52% · 59% · 2/2 | 0.98 (0.93) · rec 1.02 · **64%** · 37% · 6/8 · $7.09 |
| v2 + SJC on ReSum | 1.00 · 20% · 41% · 2/2 | 1.00 · 79% · 20% · 2/2 | 1.00 · 100% · 29% · 2/2 | 1.00 · 64% · 58% · 2/2 | **1.00 (1.00)** · rec 1.04 · 66% · 37% · **8/8** · $7.14 |
| v2 + OpenClaw | 1.00 · 19% · 40% · 2/2 | 0.99 · 99% · 19% · 1/2 | 1.00 · 94% · 30% · 2/2 | 1.00 · 61% · 61% · 2/2 | 1.00 (0.99) · rec 1.04 · 68% · 37% · 7/8 · $7.56 |
| v2 + OpenClaw + SJC | 1.00 · 20% · 40% · 2/2 | 0.94 · 110% · 19% · 1/2 | 1.00 · 80% · 29% · 2/2 | 1.00 · 53% · 64% · 2/2 | 0.98 (0.94) · rec 1.02 · 66% · 38% · 7/8 · $7.68 |

### What the judge did

The counts come from the runs' `records` field.

| Variant | Model | Compactions judged | Entries | Dropped | Fail-open |
|---|---|---|---|---|---|
| SJC on ReSum | Haiku | 170 | 3,655 | 457 (13%) | 0 |
| SJC on ReSum | Sonnet | 28 | 410 | 52 (13%) | 0 |
| OpenClaw + SJC | Haiku | 16 | 371 | 115 (31%) | 0 |
| OpenClaw + SJC | Sonnet | 4 | 70 | 24 (34%) | 0 |

No OpenClaw compaction was cancelled.

### Per task, all rows

Generated by `python -m eam.bench.analyze --summary results/v3_report_rows.jsonl`.

<!-- HEADLINE -->
**ledger_audit** — success · accuracy · recovery · cost vs `naive@native` · rounds · minutes (medians; recovery defined only for methods)

| method | cc-haiku | cc-sonnet |
|---|---|---|
| `naive` | 0/4 · 0.00 · — · 4% · 11 · 1.1 | 0/3 · 0.00 · — · 24% · 13 · 1.1 |
| `naive@native` | 2/4 · 0.82 · — · 100% · 11 · 3.0 | 1/3 · 0.85 · — · 100% · 15 · 2.2 |
| `automem` | 1/4 · 0.85 · 1.13 · 118% · 66 · 16.0 | 3/3 · 1.00 · 1.19 · 111% · 34 · 5.6 |
| `automem#aux=cc-haiku` | — | 3/3 · 1.00 · 1.19 · 90% · 36 · 6.7 |
| `automem:ingest=0.1` | 3/4 · 0.89 · 1.11 · 86% · 58 · 14.5 | — |
| `automem:ingest=0.1#aux=cc-haiku` | — | 2/2 · 1.00 · 1.14 · 99% · 42 · 8.8 |
| `automem:ingest=0.1,compact=openclaw` | 2/4 · 0.86 · 1.15 · 97% · 59 · 11.9 | — |
| `automem:ingest=0.1,compact=openclaw#aux=cc-haiku` | — | 2/2 · 1.00 · 1.14 · 89% · 42 · 6.6 |
| `automem:ingest=0.1,compact=openclaw+sjc` | 0/4 · 0.68 · 0.86 · 138% · 77 · 16.2 | — |
| `automem:ingest=0.1,compact=openclaw+sjc#aux=cc-haiku` | — | 2/2 · 1.00 · 1.14 · 76% · 35 · 6.1 |
| `automem:ingest=0.1,compact=sjc` | 1/4 · 0.68 · 0.86 · 133% · 54 · 14.3 | — |
| `automem:ingest=0.1,compact=sjc#aux=cc-haiku` | — | 2/2 · 1.00 · 1.14 · 95% · 41 · 7.9 |

**ops_stream** — success · accuracy · recovery · cost vs `naive@native` · rounds · minutes (medians; recovery defined only for methods)

| method | cc-haiku | cc-sonnet |
|---|---|---|
| `naive` | 0/4 · 0.20 · — · 14% · 30 · 5.6 | 0/2 · 0.19 · — · 28% · 29 · 2.4 |
| `naive@native` | 0/4 · 0.96 · — · 100% · 30 · 13.3 | 2/2 · 1.00 · — · 100% · 30 · 4.3 |
| `automem` | 0/4 · 0.84 · 0.84 · 69% · 82 · 22.1 | 1/2 · 0.99 · 0.99 · 212% · 74 · 14.4 |
| `automem#aux=cc-haiku` | — | 2/2 · 1.00 · 1.00 · 122% · 66 · 14.8 |
| `automem:ingest=0.1` | 1/4 · 0.87 · 0.88 · 76% · 88 · 24.3 | — |
| `automem:ingest=0.1#aux=cc-haiku` | — | 0/2 · 0.93 · 0.91 · 79% · 48 · 9.7 |
| `automem:ingest=0.1,compact=openclaw` | 2/4 · 0.82 · 0.81 · 91% · 96 · 22.2 | — |
| `automem:ingest=0.1,compact=openclaw#aux=cc-haiku` | — | 1/2 · 0.99 · 0.98 · 99% · 52 · 9.8 |
| `automem:ingest=0.1,compact=openclaw+sjc` | 0/4 · 0.93 · 0.96 · 90% · 87 · 23.9 | — |
| `automem:ingest=0.1,compact=openclaw+sjc#aux=cc-haiku` | — | 1/2 · 0.94 · 0.92 · 110% · 61 · 11.1 |
| `automem:ingest=0.1,compact=sjc` | 1/4 · 0.93 · 0.95 · 151% · 100 · 35.9 | — |
| `automem:ingest=0.1,compact=sjc#aux=cc-haiku` | — | 2/2 · 1.00 · 1.00 · 79% · 48 · 8.9 |

**repo_debug** — success · accuracy · recovery · cost vs `naive@native` · rounds · minutes (medians; recovery defined only for methods)

| method | cc-haiku | cc-sonnet |
|---|---|---|
| `naive` | 1/4 · 0.62 · — · 68% · 14 · 1.7 | 0/2 · 0.25 · — · 58% · 13 · 1.5 |
| `naive@native` | 4/4 · 1.00 · — · 100% · 18 · 2.2 | 2/2 · 1.00 · — · 100% · 16 · 2.2 |
| `automem` | 3/4 · 0.88 · 0.67 · 92% · 22 · 3.0 | 2/2 · 1.00 · 1.00 · 83% · 14 · 2.0 |
| `automem#aux=cc-haiku` | — | 2/2 · 1.00 · 1.00 · 61% · 15 · 2.3 |
| `automem:ingest=0.1` | 4/4 · 1.00 · 1.00 · 123% · 20 · 4.7 | — |
| `automem:ingest=0.1#aux=cc-haiku` | — | 2/2 · 1.00 · 1.00 · 52% · 13 · 2.3 |
| `automem:ingest=0.1,compact=openclaw` | 2/4 · 0.75 · 0.67 · 225% · 36 · 5.5 | — |
| `automem:ingest=0.1,compact=openclaw#aux=cc-haiku` | — | 2/2 · 1.00 · 1.00 · 61% · 14 · 2.2 |
| `automem:ingest=0.1,compact=openclaw+sjc` | 4/4 · 1.00 · 1.00 · 214% · 23 · 5.0 | — |
| `automem:ingest=0.1,compact=openclaw+sjc#aux=cc-haiku` | — | 2/2 · 1.00 · 1.00 · 53% · 14 · 1.9 |
| `automem:ingest=0.1,compact=sjc` | 4/4 · 1.00 · 1.00 · 126% · 22 · 3.7 | — |
| `automem:ingest=0.1,compact=sjc#aux=cc-haiku` | — | 2/2 · 1.00 · 1.00 · 64% · 16 · 2.5 |

**research_corpus** — success · accuracy · recovery · cost vs `naive@native` · rounds · minutes (medians; recovery defined only for methods)

| method | cc-haiku | cc-sonnet |
|---|---|---|
| `naive` | 0/4 · 0.00 · — · 26% · 28 · 9.4 | 0/3 · 0.00 · — · 27% · 27 · 2.0 |
| `naive@native` | 3/4 · 0.75 · — · 100% · 60 · 12.4 | 3/3 · 1.00 · — · 100% · 52 · 4.7 |
| `automem` | 3/4 · 0.75 · 1.00 · 52% · 62 · 20.9 | 3/3 · 1.00 · 1.00 · 29% · 57 · 6.9 |
| `automem#aux=cc-haiku` | — | 3/3 · 1.00 · 1.00 · 19% · 58 · 6.1 |
| `automem:ingest=0.1` | 3/4 · 0.75 · 1.00 · 50% · 55 · 16.9 | — |
| `automem:ingest=0.1#aux=cc-haiku` | — | 2/2 · 1.00 · 1.00 · 18% · 59 · 8.1 |
| `automem:ingest=0.1,compact=openclaw` | 3/4 · 0.75 · 0.67 · 46% · 65 · 17.4 | — |
| `automem:ingest=0.1,compact=openclaw#aux=cc-haiku` | — | 2/2 · 1.00 · 1.00 · 17% · 59 · 6.5 |
| `automem:ingest=0.1,compact=openclaw+sjc` | 1/4 · 0.47 · 0.30 · 44% · 56 · 15.8 | — |
| `automem:ingest=0.1,compact=openclaw+sjc#aux=cc-haiku` | — | 2/2 · 1.00 · 1.00 · 19% · 60 · 7.2 |
| `automem:ingest=0.1,compact=sjc` | 1/4 · 0.64 · 0.52 · 45% · 56 · 11.6 | — |
| `automem:ingest=0.1,compact=sjc#aux=cc-haiku` | — | 2/2 · 1.00 · 1.00 · 19% · 58 · 7.5 |
<!-- /HEADLINE -->

## Findings

1. **On Haiku, pruning summaries costs accuracy where every figure matters.**
   - SJC deleted 13% of ReSum's entries and 31% of OpenClaw's.
   - On `research_corpus` (multi-hop answers) and `ledger_audit` (totals over many ledgers), the score fell:
     - SJC on ReSum: 0.75 → 0.64 and 0.89 → 0.68;
     - OpenClaw + SJC: 0.75 → 0.47 and 0.89 → 0.68.
   - The likely cause is that facts the judge marked as not sourced, such as intermediate totals the agent had computed itself, were still needed.
   - Cost also rose, because lost facts mean more steps: from 85% of the ceiling to 114–124%.
2. **On Sonnet, the summary step barely matters.** All four variants are within 0.02 in score and 4 points in cost. SJC on ReSum is the only one that solved every run (8/8), and the only one at 1.00 on `ops_stream`, where v2 had its weak cell. With 2 runs per cell, that cannot be told apart from noise.
3. **OpenClaw's structured sections bring no gain inside AutoMemory.** On their own (the new-methods report), OpenClaw summaries were strong because they were the only memory the agent had. Inside AutoMemory the workspace notes already carry the identifiers and decisions that OpenClaw's sections are designed to preserve, so the extra summary structure adds tokens without adding facts. Haiku `repo_debug` dropped to 0.75 at 225% cost.
4. **The standalone results did not carry over.** Alone on Haiku `research_corpus`, SJC scored 0.94 and OpenClaw + SJC 1.00. Inside AutoMemory they scored 0.64 and 0.47. A component that is strong alone is not necessarily strong in combination, which is why every candidate is ablated inside the full skill before it is adopted.

## Recommendation

| Use | Setting |
|---|---|
| Default | `automem_v2` (ReSum compaction, previews at ingestion) |
| Strong agent model (Sonnet-class) | `automem_v2` with `compact=sjc` is an option (8/8 solved, 66% cost). It needs more seeds before it becomes a recommendation. |
| Not recommended | `compact=openclaw` or `openclaw+sjc` inside AutoMemory; SJC with a weaker agent model |

## Spend

The 72 new runs cost $32.26 (Haiku $9.88, Sonnet $22.38).

## Reproduce

```bash
X="automem:ingest=0.1,compact=openclaw automem:ingest=0.1,compact=openclaw+sjc automem:ingest=0.1,compact=sjc"
scripts/run_automem_v2.sh cc-haiku 4 3 "" $X
scripts/run_automem_v2.sh cc-sonnet 2 2 "#aux=cc-haiku" $X
python scripts/fill_report.py docs/results/2026-11-04-automemory-v3-ablation.md results/v3_report_rows.jsonl
```

`results/v3_report_rows.jsonl` holds:
- the v4 `naive`, `naive@native`, `automem` and `automem#aux=cc-haiku` rows;
- the `automem:ingest=0.1*` rows (without `fold`) of `results/automem_v2-*.jsonl`.
