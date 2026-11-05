# Plan and proposal: next steps after AutoMemory v2 (2026-11-05)

**Context.**
- **AutoMemory v2 is the default** (`automem_v2`): v1 plus head/tail previews of large tool outputs at ingestion. It is the only setting that matches the unoptimised ceiling's accuracy on both Haiku and Sonnet below the ceiling's cost.
  - Haiku: 0.88 mean score, 11/16 runs solved, 85% of the ceiling's cost.
  - Sonnet: 0.98, 64%.
- **Two questions remain open:**
  - **A.** Is `compact=sjc` (ReSum summaries pruned by SJC's source judge) better than v2 for strong agent models?
  - **B.** Do the results hold on real coding work, not just the synthetic long tasks?

Background:
- [`../problem_statement.md`](../problem_statement.md)
- [`../results/2026-11-04-automemory-v2.md`](../results/2026-11-04-automemory-v2.md)
- [`../results/2026-11-04-new-methods.md`](../results/2026-11-04-new-methods.md)
- [`../results/2026-11-04-automemory-v3-ablation.md`](../results/2026-11-04-automemory-v3-ablation.md)

## A. More Sonnet seeds for `compact=sjc` (done 2026-11-05)

**Outcome.**
- **Rule met:** SJC on ReSum solved 16/16 Sonnet runs (v2: 13/16), with a score at least as high as v2 on every task, at a mean cost 3–5 points higher.
- **New preset:** `automem_v2_strong`, the recommended setting for strong agent models.
- **Details:** [`../results/2026-11-04-automemory-v3-ablation.md`](../results/2026-11-04-automemory-v3-ablation.md), section *Sonnet at 4 seeds*.
- **Cost:** 34 runs, $36.11.

**Why.**
- In the v3 ablation, on Sonnet (2 seeds), `compact=sjc` solved 8/8 runs at 66% of the ceiling's cost.
- v2 solved 6/8 at 64%, and SJC fixed v2's only weak cell (`ops_stream` 0.93 → 1.00).
- With 2 seeds per cell that is within run-to-run noise.

**What.**
- **Seeds:** add instances 2–3 for v2 and v2 + SJC on all four long tasks, so every Sonnet cell has 4 seeds.
- **Same instances for the references:** run the floor (`naive`), the ceiling (`naive@native`) and v1 (`automem#aux=cc-haiku`) on the new instances too, so every comparison is on the same instances.
- **Unchanged settings:** Haiku is the summariser and SJC judge, as before.
- **Script:** `scripts/run_sonnet_seeds.sh`. Output: `results/seeds_sonnet-<task>.jsonl`.

**Cost and time.** 36 Sonnet runs, about **$33**, about 2 hours:

| Runs | Cost |
|---|---|
| v2 and v2 + SJC | ≈ $14 |
| Floor and ceiling | ≈ $12 |
| v1 | ≈ $7 |

**Decision rule.**
- **Adopt** `compact=sjc` as the recommended setting for strong agent models only if, at 4 seeds, it does both of the following:
  - matches or beats v2's mean score on every task;
  - stays within 10 points of v2's cost.
- **Otherwise** it stays an option.
- **Haiku is excluded either way:** SJC already lowered Haiku's scores on `research_corpus` and `ledger_audit`.

**Deliverable.** An update to `docs/results/2026-11-04-automemory-v3-ablation.md` with the 4-seed Sonnet numbers.

## B. A realistic coding benchmark (proposed; blocked on a permission)

**Why.** Apart from `repo_debug` (real `pytest` on a generated library), the benchmark tasks are synthetic. The open gap in [`../problem_statement.md`](../problem_statement.md) §5 is evidence on real repositories and multi-session work, which is the setting of a daily Codex or Claude Code user:
- repeated exploration of a large codebase;
- floods of test logs;
- forgetting between sessions.

### Design

1. **Issues.** Use real issues from **SWE-bench Verified** (500 issues, human-validated) on **Django 4.2 and 5.0**.
   - Django is pure Python and tests with its own runner, so no Docker is needed.
   - There are 85 candidates of difficulty "< 15 min" or "15 min – 1 hour".
   - A validation pass keeps only the issues whose FAIL_TO_PASS tests fail on the unfixed code and whose full test set passes with the official fix in this container.
   - Pick about 20 of them.
2. **Workdays.** Group the issues into about 4 "workdays" of 5 issues each, in the same repository, run as consecutive sessions.
   - Each session starts from a fresh working copy at its issue's base commit.
   - The conversation of earlier sessions is gone; only the memory method's own store survives (notes, retrieved history).
   - This measures what memory buys a coding agent across a day: less re-exploration, faster orientation.
3. **Tools.** The same structured tools as `repo_debug`: `list_files`, `read_file`, `grep`, `replace_in_file`, and `run_tests` (Django's `tests/runtests.py` with a label).
4. **Grading.** As SWE-bench does: apply the issue's test patch to the agent's working copy, then run FAIL_TO_PASS + PASS_TO_PASS. The issue is resolved iff all of them pass. The workday score is the fraction of its issues resolved.
5. **Window.**
   - **Pilot:** first measure real context sizes on the model's own window.
   - **Main runs:** use an emulated window chosen from the pilot (expected 64K), so that compaction and previews are exercised as they are in a long daily session.
   - **Native-window ceiling:** run as well, so results are model-normalised as in `docs/methodology.md` §6.
6. **Methods.**

   | Spec | Role |
   |---|---|
   | `naive` | Floor |
   | `naive@native` | Ceiling |
   | `automem` | v1 |
   | `automem_v2` | v2 |
   | `automem:ingest=0.1,compact=sjc` | v2 + SJC (Sonnet only, if A supports it) |

   Sonnet uses Haiku as the summariser (`#aux=cc-haiku`).
7. **Metrics** (the project's objective: tokens and dollars per solved task at full accuracy):
   - issues resolved, recovery between floor and ceiling;
   - cost and prompt tokens per resolved issue, peak context;
   - wall time, agent rounds;
   - tool calls spent re-exploring files already seen in an earlier session.
8. **Order of work.**
   1. Validate the instances (no API spend).
   2. Pilot: 3 issues × ceiling × Haiku and Sonnet, about $5, to tighten the estimate.
   3. Full grid.

### Cost estimate

| Item | Estimate |
|---|---|
| Engineering (task module, workday grouping, grading, tests) | Half a day to a day; no API spend |
| Haiku: 20 issues × 5 methods × 2 seeds = 200 runs, about $0.05–0.15 each | $10–30 |
| Sonnet: 20 issues × 5 methods × 1 seed = 100 runs, about $0.5–1.5 each | $50–150 |
| **Total B** | **about $60–180**, most likely about $100 |
| **A + B** | **about $95–215**, most likely about $130 |

The per-run costs are extrapolated from `repo_debug` (Sonnet $0.2–0.6 per 2-session run at a 16K window) and from the ReFold and AKV papers (about $0.38 per SWE-bench task for Opus 4.8 on Bedrock). The pilot replaces them with measured numbers before the full grid.

### Status and the permission it needs

**Done** (no API spend):
- SWE-bench Verified downloaded from the Hugging Face datasets server.
- Django cloned (blobless, 70 MB) into `~/.cache/eam/swe/`.
- A Python 3.11 virtualenv with Django's two runtime dependencies (asgiref, sqlparse).
- Helpers in `eam/bench/tasks/swe_env.py`: per-issue worktrees, Django's test runner, SWE-bench grading.

**Blocked.** The validation step was refused by the session's auto-mode permission check, which classifies it as running code from an external source. The step runs Django's test suite and applies the SWE-bench patches, and every benchmark run would do the same.

**What the step runs:**
- the code of Django's official repository at each issue's commit;
- the patches published by SWE-bench.

It runs inside this session's isolated cloud container.

**To unblock**, the user either:
- approves running Django's test suite and SWE-bench patches in this container; or
- adds a Bash permission rule for the benchmark's commands.

### Fallback if third-party code should not run

Extend the synthetic `repo_debug` task instead:
- more sessions (a 5-session "workday");
- a larger generated codebase (about 150K tokens);
- issues that touch the same modules across sessions.

It needs no new permission and costs about $30–60 for the same method grid. It is less realistic: the code is generated and the bugs are planted.

## Order and decisions

1. A runs now. When it finishes, update the v3 ablation report and apply the decision rule above.
2. B starts once the permission is granted: validation, then the pilot (about $5), then a cost check before the full grid.
3. If the permission is not granted, run the fallback instead and say so in the report.
