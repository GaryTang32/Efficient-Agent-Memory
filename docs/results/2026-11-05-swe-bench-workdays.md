# Real repositories: SWE-bench Verified workdays on Django (2026-11-05)

**Question.** Do the memory settings that worked on the synthetic long tasks also save tokens and dollars at full accuracy on real coding work?

**Setup in brief:**
- Real GitHub issues from SWE-bench Verified.
- Grouped into workdays of consecutive sessions in one repository.
- Graded the way SWE-bench grades them.

**Answer: yes, but only without the note workspace.**

**AutoMemory v2 without the workspace** (`automem_v2_lean`: previews at ingestion, in-step guard, compaction) was the best setting on both models:

| Model | Window | Resolved | Cost vs ceiling | Peak context |
|---|---|---|---|---|
| Sonnet | 16K | 36/40 | **60%** | 10.5K |
| Sonnet | own | 36/40 | 76% | 15.7K |
| Haiku | 16K | 35/40 (= ceiling) | 94% | 10.7K |
| Haiku | own | 35/40 (= ceiling) | 95% | 16.2K |

- Sonnet's ceiling resolved 37/40. Lean's $0.077 per resolved issue on Sonnet is the lowest of all eleven settings.

**AutoMemory v2 with the workspace** costs more:
- At the model's own window it is 58% (Haiku) and 18% (Sonnet) more expensive than the ceiling.
- The extra tool calls go to writing and reading notes. Issues in a workday are unrelated, so the notes carry nothing the next session needs.

## Task

`swe_workday` (`eam/bench/tasks/swe_workday.py`):

**Issues.**
- 40 SWE-bench Verified issues on Django 4.2 and 5.0, ordered by creation date.
- Grouped into 8 workdays of 5 issues.

**Sessions.**
- One session per issue, starting from a fresh git worktree at the issue's base commit.
- The conversation of earlier sessions is gone. Only the memory method's own store carries over.

**Tools.**
- `list_files` (one directory)
- `read_file` (200 lines per call)
- `grep` (Python files, at most 150 hits)
- `replace_in_file`
- `run_tests` (Django's `tests/runtests.py` on labels)

**Grading** (SWE-bench's own):
- The issue's test patch is applied to the agent's working copy.
- The issue is resolved iff every FAIL_TO_PASS and PASS_TO_PASS test passes.
- Tests run under Python 3.11 with Django's runtime dependencies; no Docker.

**Validation.**
- Run with `scripts/swe_validate.py` on 44 candidate issues of difficulty below "1–4 hours".
- 42 qualified: FAIL_TO_PASS fails without the official fix, and every test passes with it.
- Excluded: `django__django-16801`, whose test already passes before the fix, and `django__django-16950`, whose test run exceeds 10 minutes.
- The first 40 qualifying issues are used.

**Runs.**
- One run per (workday, setting): 8 runs × 5 issues = 40 issues per cell.
- 160 runs in total, none errored.
- Claude Code CLI route. Sonnet's summaries and judging are done by Haiku.

**Two windows.**
- The model's own window (`@native`), as in everyday Claude Code or Codex use.
- An emulated 16K window, standing in for long, crowded sessions: a request above it ends the session.

**Reference points.**
- **Ceiling:** `naive@native`, full history with no caching on the model's own window. All costs are relative to it, summed over the same 8 workdays.
- **Everyday default:** `full@native`, full history with provider caching, i.e. what an agent does without any memory layer.

## Results

Each cell gives:
- issues resolved;
- total cost as a percentage of the ceiling's;
- dollars per resolved issue;
- median peak prompt per session;
- median steps per workday.

**Sonnet** (40 issues per cell):

| Setting | Window | Resolved | Cost vs ceiling | $ / resolved | Peak | Steps |
|---|---|---|---|---|---|---|
| Ceiling (`naive@native`) | own | **37 (92%)** | 100% | 0.125 | 14.2K | 32 |
| Full history, cached (`full@native`) | own | **37 (92%)** | 106% | 0.133 | 13.7K | 32 |
| AutoMemory v2 | own | 35 (88%) | 118% | 0.156 | 19.1K | 33 |
| AutoMemory v2 strong | own | 36 (90%) | 120% | 0.154 | 18.3K | 37 |
| **AutoMemory v2 lean** (no workspace) | own | 36 (90%) | **76%** | **0.098** | 15.7K | 33 |
| No memory (`naive`) | 16K | 32 (80%) | 113% | 0.163 | 12.8K | 32 |
| Full history, cached (`full`) | 16K | 33 (82%) | 85% | 0.119 | 12.3K | 32 |
| AutoMemory v1 | 16K | 36 (90%) | 116% | 0.150 | 11.8K | 40 |
| AutoMemory v2 | 16K | **37 (92%)** | 90% | 0.113 | 11.7K | 37 |
| AutoMemory v2 strong | 16K | 35 (88%) | 123% | 0.163 | 11.9K | 38 |
| **AutoMemory v2 lean** (no workspace) | 16K | 36 (90%) | **60%** | **0.077** | **10.5K** | 34 |

**Haiku** (40 issues per cell):

| Setting | Window | Resolved | Cost vs ceiling | $ / resolved | Peak | Steps |
|---|---|---|---|---|---|---|
| Ceiling (`naive@native`) | own | **35 (88%)** | 100% | 0.011 | 15.1K | 30 |
| Full history, cached (`full@native`) | own | **35 (88%)** | **76%** | **0.008** | 14.9K | 30 |
| AutoMemory v2 | own | **35 (88%)** | 158% | 0.017 | 23.7K | 38 |
| **AutoMemory v2 lean** (no workspace) | own | **35 (88%)** | 95% | 0.010 | 16.2K | 32 |
| No memory (`naive`) | 16K | 31 (78%) | 87% | 0.011 | 14.6K | 33 |
| Full history, cached (`full`) | 16K | 31 (78%) | 95% | 0.012 | 14.5K | 34 |
| AutoMemory v1 | 16K | 34 (85%) | 228% | 0.026 | 12.0K | 41 |
| AutoMemory v2 | 16K | 33 (82%) | 240% | 0.028 | 11.9K | 41 |
| **AutoMemory v2 lean** (no workspace) | 16K | **35 (88%)** | 94% | 0.010 | **10.7K** | 34 |

**Paired by issue** (which issues each setting resolves):
- **Ceiling:** Sonnet's ceiling and lean differ on one issue. Haiku's differ on one issue in each direction.
- **16K window:**
  - On Haiku, lean resolves 4 issues that cached full history does not, and misses none that it resolves.
  - On Sonnet, lean resolves 4 more and misses 1.
- **Unsolved:** 2 issues (Sonnet) and 4 (Haiku) were resolved by no setting.

Differences of one or two issues are within run-to-run noise. The cost differences are larger and consistent across workdays.

### Where AutoMemory v2's extra cost comes from

Measured over the 8 workdays, at the model's own window:

| | Tool calls | Steps | Malformed replies (nudges) | Compactions |
|---|---|---|---|---|
| Haiku, cached full history | 242 | 246 | 5 | 0 |
| Haiku, AutoMemory v2 | 375 | 322 | 21 | 0 |
| Sonnet, cached full history | 306 | 264 | 0 | 0 |
| Sonnet, AutoMemory v2 | 428 | 268 | 0 | 0 |

- **No compaction fires** at the model's own window: real issue sessions peak at 12–26K tokens.
- **The extra 50% of tool calls** are the workspace's `write_note` / `read_notes`. The system prompt asks the agent to save intermediate results, and each session's first message recalls every earlier session's notes.
- **Removing the workspace removes the overhead.** Lean's tool calls, steps and cost fall back to the cached baseline's level or below. Lean then keeps the previews: Django's test output is up to 12K characters per run, and the previews shrink it, along with the guard and compaction.

## Findings

1. **On real coding issues, the note workspace costs more than it returns.**
   - The issues in a workday touch unrelated parts of Django, so earlier notes do not help the next session.
   - Writing and reading them adds steps. On Haiku it also adds malformed replies.
   - This is the opposite of the synthetic multi-session tasks (`ops_stream`, `ledger_audit`), where later sessions depend on earlier results. There the workspace was essential.
2. **The within-session half of AutoMemory works on real code.**
   - Previews of large outputs, the guard and compaction at 75% of the window cut Sonnet's cost to 60–76% of the ceiling, at 36/40 resolved (ceiling: 37/40).
   - The same components bring Haiku under a 16K window to the ceiling's accuracy (35/40, against 31/40 without them) at 94% of its cost, with the smallest peak of any setting.
3. **Without a memory layer, a tight window costs accuracy.** At 16K, no memory and cached full history both lose 4–5 issues on each model, through overflows and lost context.
4. **SJC pruning (v2 strong) does not help on short sessions.** It costs 2–5 points more than v2 and resolved 1–2 fewer issues. Its benefit was measured on long synthetic sessions, where compaction fires often.
5. **For Haiku at its own window, plain caching is the cheapest.** Cached full history resolves 35/40 at 76% of the ceiling's cost, slightly cheaper than lean's 95%. Haiku's sessions are short enough that nothing needs managing.

## Recommendation

**Default by kind of work.** These settings correspond to the decision flowchart on the overview page:

| Work | Setting |
|---|---|
| Independent tasks, one per session (coding issues, tickets) | **`automem_v2_lean`**: previews, guard, compaction; no workspace |
| Multi-session work that builds on earlier results (audits, running state, research over several days) | `automem_v2` (`automem_v2_strong` for strong models) |
| Short sessions on a large window, weaker model | Cached full history may be enough; `automem_v2_lean` costs about the same and protects against long sessions |

**Next step for AutoMemory:** make the workspace adaptive, so it is on only when a session's task refers to earlier results. Instead of a fixed choice, the cheapest signal is whether the task text mentions earlier sessions or saved results.

## Spend

| Run set | Haiku | Sonnet | Total |
|---|---|---|---|
| Grid, ablation and pilot (164 runs) | $4.59 | $51.77 | **$56.36** |

## Reproduce

```bash
python scripts/swe_validate.py results/swe_validation.jsonl 4    # which issues qualify in this environment
scripts/run_swe_grid.sh                                          # 8 workdays x 5 issues, both models, both windows
L="automem:workspace=false,ingest=0.1"
python scripts/run_swe.py --model cc-haiku --specs "$L" "$L@native" --workdays 8 --issues 5 --window 16000 --out results/swe-haiku.jsonl
python scripts/run_swe.py --model cc-sonnet --aux-model cc-haiku --specs "$L" "$L@native" --workdays 8 --issues 5 --window 16000 --out results/swe-sonnet.jsonl
```

Rows: `results/swe-haiku.jsonl`, `results/swe-sonnet.jsonl`. The SWE-bench data, the Django clone and the test virtualenv are created in `~/.cache/eam/swe` by `eam/bench/tasks/swe_env.py`.
