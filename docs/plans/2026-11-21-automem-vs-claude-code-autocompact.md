# Test plan: does AutoMemory v2 work inside Claude Code, and does it beat Claude Code on its own?

**Status:** agreed in four review rounds (2026-11-21); not yet run. This document is frozen once the pilot has
passed and before the main runs start (section 13).

**Model:** Claude Sonnet only. **Cost:** about $113 for the required tiers, plus about $32 for an optional tier
decided after the pilot.

## 1. The question

Three claims are tested separately:

1. **Workable:** AutoMemory v2 runs inside Claude Code without errors or slowdown, and without lowering results.
2. **Beats Claude Code:** on work that needs memory, Claude Code with AutoMemory v2 is at least as accurate as Claude
   Code as shipped (autocompaction, microcompact and its own auto memory), at a lower cost per correct answer.
3. **Beats a prompt:** it also does better than the cheapest alternative a user has, telling Claude Code to keep its
   own notes file.

**Accuracy comes first, then efficiency.** The judging order is:
1. accuracy must not fall;
2. then cost per correct answer, at real prices with caching;
3. tokens per correct answer and the largest prompt are reported, but are not used for the verdict.

## 2. What the earlier checks missed, and the facts this plan rests on

The earlier Claude Code checks could not show a difference:
- sessions were short, and no session needed an earlier one;
- outputs were small;
- the plugin tested was only part of AutoMemory v2: it has no note tools and no rule to save findings.

**Facts checked for this plan** (Claude Code 2.1.329):

| Fact | Consequence |
|---|---|
| Claude Code has its own **auto memory**, on by default, saving notes to `~/.claude/projects/<folder>/memory/`. This cloud environment turns it off (`CLAUDE_CODE_REMOTE`). `CLAUDE_CODE_DISABLE_AUTO_MEMORY=0` forces it on: a probe wrote `MEMORY.md` | The baseline must have it on, as company laptops do. Earlier pilots ran without it |
| **Microcompact** clears old tool results and saves them to files. Anthropic triggers it from their side, and one form depends on time | It overlaps with previews. It stays at its default and is logged in every run |
| Claude Code shows up to **30,000 characters** of Bash output in full (`bashOutputMaxChars`), cuts the rest to the head, and saves the whole output to a file. The plugin previews anything above 6,000 characters | The plugin changes only outputs between 6K and 30K characters (it previews them), and outputs above 30K (it adds the tail) |
| In 50 earlier Claude Code coding sessions (1,584 tool outputs): 80% were under 2K characters, 18% were 2–6K, 1.6% were 6–30K, and none were above 30K | On natural coding, previews can hardly matter. Any gain there must come from notes or the recap |
| On this account, `sonnet` runs Claude Sonnet 5.5 with a **1M** window | The company setting (a 1M model compacting at 500K) is reproducible |
| The prompt cache lasts **5 minutes** by default | Days run back to back would keep the cache warm; real days start cold |
| Claude Code's own prompt is about 10–12K tokens; a cold start costs about $0.03 on Sonnet | Feeds the cost estimates |
| Two identical Sonnet sessions on the same 5 issues differed in cost by a spread of 0.02–0.17 in log ratio (median about 0.07); issues fixed by 0–1 of 5 | Sets the sample sizes (section 8) |
| *(Found in step 0.)* The earlier pilots passed this machine's whole environment to Claude Code: effort `xhigh`, a 32K thinking budget, `CLAUDE_AUTOCOMPACT_PCT_OVERRIDE=92` and debug mode, none of them Claude Code's defaults | The runner passes only the path, home, proxy and certificate variables, plus each arm's own switches. Everything else is Claude Code's default |

## 3. Hypotheses: one per mechanism, each with a place where it can act

| # | Mechanism | Hypothesis | Where Claude Code alone is weak | Where the test exercises it |
|---|---|---|---|---|
| H1 | Notes across sessions | Later sessions answer correctly without re-reading earlier material | A new session starts from zero, unless auto memory kept the facts | Multi-day task (F1), a new session each day (cell N) |
| H2 | Previews | Less is read for the same answers, without losing accuracy | Outputs of 6–30K characters arrive in full; above 30K, only the head arrives | F1's daily outputs (section 6) |
| H3 | Handoff recap at compaction | State and exact figures survive compaction | The general summary may drop figures | F1 in one resumed session, compacting at 100K (cell R100) |
| H4 | No harm | Same results and cost on ordinary work | — | Real coding issues (F2) |

**A cell gives a verdict on a hypothesis only if that mechanism actually fired there** (section 7). Otherwise the
hypothesis is "not exercised" in that cell.

## 4. Arms

| Arm | What it is | Settings that differ |
|---|---|---|
| **A** | Claude Code as shipped: autocompaction, microcompact at its default, auto memory on | `CLAUDE_CODE_DISABLE_AUTO_MEMORY=0` |
| **A′** | An identical copy of A | The same as A |
| **A0** | Autocompaction only | `CLAUDE_CODE_DISABLE_AUTO_MEMORY=1` |
| **A+** | A, plus one prompt line: keep a `NOTES.md` with what later days need, and read it first each day | The prompt line |
| **L** | A, plus the plugin in lean mode: previews and the handoff recap only | `--plugin-dir`, `AUTOMEM_NOTES=off` |
| **V2** | A, plus the plugin in full mode: previews, the recap, notes recalled at every session start, autosave, the note tools and the note rule | `--plugin-dir`, `AUTOMEM_WORKSPACE=on`, the `automem-mcp` MCP server |

**What each comparison shows:**

| Comparison | Shows |
|---|---|
| V2 against A | The verdict |
| V2 against A+ | Whether the plugin beats a plain prompt |
| V2 against L | What the notes add |
| L against A | What previews and the recap add |
| A against A0 | What Claude Code's auto memory adds |
| A′ against A | The noise |

**Held the same in every arm:**
- the model (`sonnet`), Claude Code 2.1.329 with auto-updates off, and the task prompt (except A+'s line);
- the allowed tools (`Bash Read Edit Write Grep Glob`, plus the note tools in V2), the per-day spending cap and the
  timeouts;
- user and project settings off (`--setting-sources ""`), and `--strict-mcp-config` everywhere.

## 5. Cells

| Cell | Task · sessions · compaction window | Arms × instances | Role |
|---|---|---|---|
| **N** (headline) | F1 · a new session per day · **500K** (the company setting) | A, A′, A+, V2 × **6**; A0, L × **4** | The verdict, a prompt as alternative, attribution |
| **F2** | Coding · a new session per issue · **500K** | A, L, V2 × **8 workdays** (40 issues) | No harm (equivalence); notes on related tickets |
| **R100** | F1 with the daily inbox (section 16) · one resumed session over 10 days · **100K** (Claude Code's minimum) | A, V2, A+ × **4** (amended: L dropped, A+ added) | The recap at compaction (2–3 compactions per run) |
| ~~R500~~ | Dropped at the checkpoint (section 16) | — | — |

The compaction window is set with `CLAUDE_CODE_AUTO_COMPACT_WINDOW`. In N, F2 and R500, sessions peak far below
both 400K and 500K. So either value behaves the same in this test, and 500K is kept because it is the company's
setting.

## 6. Tasks

### F1: a 10-day stock ledger

F1 is built from the benchmark's `ops_stream` generator, which predates the plugin.
- **Setup:** 10 days and 6 tracked products. Each day's reports are served by `tools/report.py` on that day only,
  and the previous day's are removed. Otherwise the file system would stand in for memory: an agent could re-read
  every earlier day each morning, and notes would be irrelevant. (Found in step 0.) The prompt says the reports
  are replaced overnight. Saving them is allowed in every arm, as a real agent might, and is logged.
- **The answer key** is held by the runner and written to disk only after the run.
- **Three outputs a day,** sized so that each case of section 2 happens:

  | Output | Size | Claude Code alone | With the plugin |
  |---|---|---|---|
  | Receipts report | ~15K characters | Shown in full | Previewed; the agent searches the saved file for what it needs |
  | Shipments report | ~15K characters | Shown in full | Previewed |
  | Audit log, with corrections to earlier events at the end, by event id only | ~60K characters | Head only, unless the agent opens the saved file | Head and tail |

- **What each day asks:** the closing stock of the 6 products, and which one is lowest. That is 7 checks per day and
  70 per run, graded exactly. Later days need the running stock, and the product and quantity behind every earlier
  event a correction can name.
- **The prompt,** the same for every arm, says the job spans 10 days and that later days build on earlier ones, as a
  real user would. The answer comes as a fixed JSON block.
- **Previews cut both ways here.** On the 15K reports, the plugin hides content the agent needs. If that costs turns
  or accuracy, the test shows it.

### F2: coding on one codebase

- **The issues:** SWE-bench Verified Django issues, in workdays of 5 related issues from one subsystem
  (`scripts/swe_related.py`). 8 workdays, 40 issues.
- **How they run:** a new Claude Code session per issue. Graded the way SWE-bench grades. Nothing is changed to
  force large outputs.
- **Stated in advance:** previews are expected to do almost nothing here.

## 7. Logging and measurements

**Kept for every run** (git-ignored, under `results/`):
- the run's configuration: arm, cell, model, instance seed, Claude Code version, plugin commit, and the environment
  with secrets removed;
- Claude Code's full event stream (`stream-json`), and its own session transcript, which includes the compaction
  summaries;
- a per-call table: prompt size, cache reads, cache writes, uncached and output tokens, cost;
- every tool call: name, output size, whether Claude Code cut it, whether AutoMemory previewed it;
- compaction and microcompact events, with the prompt size before and after;
- a hook log: event, time taken in ms, what it did;
- snapshots of each memory store after every day: AutoMemory's notes, Claude Code's auto memory, `NOTES.md`;
- the grader's result per check, day and run.

**Results (primary):**
- F1: checks correct, out of 70 per run.
- F2: issues resolved.
- Cost per run (Claude Code's `total_cost_usd`; for resumed sessions, the increase per turn), and cost per correct
  check or per resolved issue.

**Explanations (secondary):**
- tokens by kind, tokens per correct answer, the largest and the average prompt, turns, wall time;
- re-exploration: earlier days' outputs read again (F1); files read again (F2).

**Mechanism checks per cell:**

| Mechanism | Counted as |
|---|---|
| H1 | Auto memory written and loaded (A, A+, L, V2); `write_note` calls and recall on day ≥ 2 (V2); `NOTES.md` written (A+) |
| H2 | Outputs Claude Code cut, and previews fired |
| H3 | Compactions per run |
| Workable | Hook errors, hook time, unfinished sessions, cap hits |

## 8. Quantifying the difference: statistics and decision rules

- **Unit:** one instance, meaning a 10-day run (F1) or a 5-issue workday (F2).
- **Pairing:** each arm is compared with A on the same instances.
- **Uncertainty:** 95% bootstrap intervals over instances, with 10,000 resamples.

| Claim | AutoMemory passes if |
|---|---|
| **Workable** | ≥ 95% of sessions finish; no hook crashes; median hook time under 100 ms; accuracy within the margin below |
| **Accuracy (F1)** | The lower bound of the paired accuracy difference (V2 − A) is above **−5 points**. The −3-point target is reported as a point estimate |
| **Efficiency** | Cost per correct answer is at most **0.90** of A's, and the interval's upper bound is below **1.00** |
| **Beats a prompt** | The same two rules, with A+ in place of A |
| **No harm (F2)** | An equivalence test (TOST): issues resolved within **±10 points**, and cost ratio between **0.85 and 1.15** |
| **Validity** | If A′ and A differ by more than ±10% in cost in a cell, that cell is "too noisy" and gives no verdict |

- **Headline:** V2 against A in cell N, on F1. The no-harm headline is F2.
- **Everything else** is secondary, Holm-adjusted and reported in full.
- **Small effects:** a difference smaller than the cell can detect is "not detected", not "no effect".

**What each cell can detect.** This assumes a spread of about 0.10 in log cost between replicates (measured on Sonnet
at 0.02–0.17) and about 5 points in accuracy (the pilot measures this):

| Cell · arms | Instances | 95% interval, cost | Smallest saving it can show |
|---|---|---|---|
| N · A, A′, A+, V2 | 6 | about ±11% | about 15–20% |
| N · A0, L | 4 | about ±16% | about 25% |
| F2 | 8 workdays | about ±6% cost, ±8–10 points in issues | equivalence, if the true difference is near zero |
| R100 | 4 | about ±16% | about 25% |
| R500 (optional) | 3 | about ±25% | about 30% |

## 9. Sources of bias, and how each is handled

| Bias | Handling |
|---|---|
| A handicapped baseline | Claude Code's auto memory is forced on in A (it is off in this environment). Microcompact stays at its default |
| A task built to favour the plugin | F1 comes from a generator older than the plugin. The 15K reports make previews a trade-off. F2 is unmodified real work, and its prediction (no gain) is reported either way. A+ gives Claude Code a fair memory alternative |
| Warm-cache optimism | At least 6 minutes between days, so each day starts with a cold cache. The pilot checks whether microcompact behaves differently after 61 minutes; if so, the resumed cells use 61-minute gaps |
| Noise read as an effect | The A/A arm, paired tests, and fixed rules |
| Drift during the runs | All arms of an instance start together. The Claude Code version is pinned. Anthropic's own feature switches are the same for concurrent runs and are recorded through their events |
| Re-running bad results | Re-runs only for infrastructure failures defined in advance, and then for every arm of that instance |
| Choosing the analysis after the data | Plan, script and rules are frozen after the pilot. Every result is reported, and failures count as failures |
| Grader errors | The answer key must score 70/70 and stale answers must fail, before any spending |
| The agent reading answers or future data | The key is outside the folder, and each day's data is released only on that day |

## 10. Isolation and control

Every run gets:
- a fresh, unique working folder, so it also gets its own Claude Code project and auto-memory folder;
- its own AutoMemory data folder and MCP store;
- an explicit, minimal environment, not inherited from this machine;
- Claude Code pinned, with auto-updates off.

*(Found at the first pilot launch.)* Agents save the day's reports in `/tmp`, which concurrent sessions share, so
the arms would overwrite each other's files. Every session therefore runs in its own mount namespace:
- a private `/tmp`, holding its working folder;
- a private `/var/tmp`;
- a private `~/.claude/projects`, holding its transcripts and auto memory;
- the results and the other runs' areas hidden.

A real check confirmed that a session sees only its own run.

Day *k*'s files are copied in at the start of day *k*. In cell N, the folder stays the same across a run's days, so
auto memory and notes can carry over, as in real use. Nothing is shared between runs. After each run, its folders
are archived into the logs and deleted.

## 11. Limits, failures and re-runs

- **Per day:** a $2 spending cap and a 30-minute timeout, the same for every arm.
- **Hitting a cap** counts that day's answers as wrong.
- **Re-runs** only for an API outage, or an error before the model is called, and then for every arm of the instance.

## 12. Steps, gates and budget

| Step | What | Cost |
|---|---|---|
| **0. Build** (done 2026-11-21) | The plugin's full mode (`AUTOMEM_WORKSPACE=on`, the `automem-mcp` note tools, the hooks reading and writing the same note store); the F1 generator, daily release and grader; the runner (arms, cells, environment, gaps, logging, snapshots); the analysis script; an offline rehearsal with a stand-in `claude` program that makes no model calls | $0 |
| **1. Pilot** | Cell N at half length (5 days): A and A′ × 2 instances; A0, A+, L and V2 × 1. Cell R100 at full length: A and V2 × 1, with one 61-minute gap between days 5 and 6 | ≈ $11 |
| **Checkpoint** | A report to you: gate results, measured cost per run, noise, instance counts, the re-estimated budget, and whether to run R500. Main runs start only after you approve | $0 |
| **2. Main runs** | The matrix of section 5 | tiers below |
| **3. Report** | Results in `docs/results.md`, each hypothesis marked passed, failed, not detected or not exercised; a one-line verdict in the README | $0 |

**Pilot gates. Every one must pass before any main run:**

| Gate | Passes if |
|---|---|
| **G1 Logging** | Every session finishes with every log present |
| **G2 Isolation** | Separate project and memory folders per run; the key is never opened; day *k* sees only day *k*'s data |
| **G3 Realistic baseline** | A writes Claude Code's auto memory and loads it on day ≥ 2; A0 writes none; microcompact events are logged |
| **G4 Cold days** | Each day's first call writes at least Claude Code's prompt (about 10K tokens) to the cache |
| **G5 Mechanisms fire** | In A, the audit log is cut and the 15K reports arrive in full. In L and V2, each of the three reports is previewed at least once per run (an agent may filter later reports itself). R100 compacts at least twice. V2 writes notes and recalls them on day ≥ 2. A+ writes `NOTES.md` |
| **G6 Grader** | The key scores 70/70; stale answers fail; 100% of answers parse |
| **G7 Noise** | A against A′: spread of the log cost ratio ≤ 0.35; accuracy within 10 points |
| **G8 Cost** | Within ±50% of the estimates |
| **G9 Hooks** | No crashes; median hook time under 100 ms |

If a gate fails, that part is fixed and re-piloted (at most $3), and no main runs start until everything passes.

**Budget.** These estimates come from measured costs: a cold start costs about $0.03, and a Sonnet issue in Claude
Code about $0.044. The estimates per run are about $1.50 for N, $2.40 for R100, $4.60 for R500, and $0.40 for an
F2 workday. The pilot replaces them with measurements.

| Tier | Contents | Cost | With 15% contingency |
|---|---|---|---|
| **1. Required** | Pilot ($11) + N ($48) + F2 ($10) | $69 | **≈ $79** |
| **2** | R100 | $29 | **≈ $33** |
| **3. Optional** | R500 (decided at the checkpoint) | $28 | ≈ $32 |

Tiers 1 and 2 come to about $113. About $54 of the original $150 is left, so the total rises to about $209. Each
tier has a hard cap, and runs stop when it is reached.

## 13. Freezing

After the pilot passes, and before any main run, this plan and the analysis script are committed and frozen. From
then on, only the instance counts may change, and only as set at the checkpoint.

## 14. Limits of the result

- **Sonnet only.** Weaker models are untested. On the benchmark, memory mattered most for the weaker model.
- **F1 is a synthetic data task,** realistic but constructed. F2 is one repository (Django).
- **Claude Code changes often.** Results hold for 2.1.329, with Anthropic's feature switches as they were during the
  runs.

## 15. What each outcome would mean

- **V2 beats A and A+ on F1, and is equivalent on F2.** Recommend AutoMemory for multi-day work, and lean mode for
  independent tickets.
- **V2 beats A, but not A+.** A notes prompt gets most of the gain. The plugin's value is convenience; say so.
- **L beats A, but V2 does not beat L.** Previews and the recap carry the gain. Make lean the default in Claude Code.
- **A beats A0, and nothing beats A.** Claude Code's own auto memory and compaction are enough. Position AutoMemory
  for agents without them (the adapters), and say so plainly.

## 16. Post-pilot amendments (2026-11-21, approved before any main run)

**What the pilot found** ($4.66; cell N at 5 days with all six arms, cell R100 with A and V2):
- **No session got long.** The largest prompt in any session was 24K to 46K tokens; nothing compacted. Sonnet saves
  big outputs to files and searches them, and Claude Code cuts command output above 30,000 characters, so the
  reports never fill the context. A resumed session grew by about 2.5K tokens a day.
- **Claude Code caches for an hour here,** not five minutes. After a 6-minute gap, a resumed day read the whole of
  yesterday from the cache; only the day after the 61-minute gap started cold.
- **Claude Code's auto memory was on** (its instructions add 685 tokens to A's prompt) **but wrote nothing** in 25
  sessions. Without memory, A's agents refused to answer on 7 of 20 later days, or dug through Claude Code's saved
  logs of their own earlier sessions. A+, L and V2 got every check right.
- **No session saw another run's files.** Three sessions searched the whole disk; the test's own code and plan were
  visible to such a search, though nobody opened them.

**Changes:**

| Change | Why |
|---|---|
| R cells get a **daily inbox**: 10–14 messages, about 100,000 characters (25K tokens) a day. Messages name products by description. Some change stock in plain words (write-offs, stock found, short shipments and deliveries by order or PO number, often from earlier days); others only mention products. The prompt lists the tracked products' names and says to read every message | The resumed session fills up through reading, as real sessions do, so it compacts. Without it H3 cannot be tested. Cell N keeps the piloted task, byte for byte |
| **A new line in the system prompt each day** (`Today is workday N of this job.`), the same in every arm | Yesterday's conversation is not read back from the cache, as on a real next morning. Claude Code's own shared prompt stays cached, as in any company. Gaps between days drop to 1 minute, since time no longer decides the cache |
| The repository's `scripts/`, `docs/`, `tests/` and `.git`, and Claude Code's per-session folders in `~/.claude` (`tasks`, `sessions`, `session-env`, `backups`, `uploads`, `shell-snapshots`, `file-history`, `todos`, `plans`, `debug` and others), are each covered by a private empty folder of the run's own | A whole-disk search cannot reach the generator, the plan, or other sessions' files. What a session writes there is archived with its run |
| Agents' reads of their **own** earlier session logs stay allowed, and are counted | That is Claude Code as shipped |
| A hard spending cap in the runner (`--cap-usd`); an instance stopped by it is left out of the analysis | The budget is enforced by the runner, not by watching |
| R100: **A+ added, L dropped**. R500 dropped | A+ tests "beats a notes prompt" in a long session. At 25K tokens a day, a 500K session would need 20 days to compact once |

**Gates, as amended** (G1 and G9 unchanged):

| Gate | Passes if |
|---|---|
| **G2 Isolation** | No session sees another run's files (names of other runs in tool results). Attempts at hidden folders, whole-disk searches and reads of the run's own logs are recorded |
| **G3 Realistic baseline** | A has Claude Code's auto memory on (folder present; with A0 alongside, A's prompt is at least 300 tokens longer), and A0 writes none. Whether A writes to it is a result, recorded |
| **G4 Cold days** | No later day's first call reads more than 20K tokens from the cache (Claude Code's shared prompt only) |
| **G5 Mechanisms fire** | Every R run compacts at least twice; the inbox is read on at least 90% of R days; V2 writes notes and recalls them; A+ writes `NOTES.md` (when present); F2 sessions finish |
| **G6 Grader** | The key follows from what the agent sees (reports, inbox, product names); no malformed answers. Refusals are wrong answers, and fair |
| **G7 Noise** | As before, where A and A′ both run; otherwise not applicable |
| **G8 Cost** | Within ±50% of: N $0.97 per run (measured), R100 $6.00 per run (re-estimated), F2 $0.40 per workday |

**Second pilot:** R100 with A and V2 × 1, and an F2 check (one workday, A and V2). About $15.

**The go-ahead rule (approved):** if every gate passes and an R100 run costs at most $7, the main runs start
without another checkpoint, under a hard cap of $138 from this point (the second pilot included):

| Cell | Arms × instances | Estimate |
|---|---|---|
| N | A, A′, A+, V2 × 6; A0, L × 4 | ~$31 |
| R100 | A, V2, A+ × 4 | ~$50–85 |
| F2 | A, L, V2 × 8 workdays | ~$10 |

If R100 runs cost more than $6, R100 drops to 3 instances to stay inside the cap.

## Decision log

| Round | Decisions |
|---|---|
| 1 | Accuracy first, then cost per correct answer. Baseline: Claude Code as shipped, plus an autocompaction-only arm. Full v2 mode, on top of the defaults. Compaction tested where it fires affordably. An A/A arm and an equivalence test. Log everything raw. Isolation as in section 10. Freeze before the main runs |
| 2 | The six arms. F1 redesigned (10 days, daily release, three outputs of different sizes, the dependency stated in the prompt). F2 kept natural. The compaction cell at 100K. The headline is Sonnet V2 against A in cell N. Paired bootstrap, the noise check, an equivalence test, Holm. Identical caps; re-runs only for infrastructure failures, for every arm |
| 3 | Margins the data can meet (−5 points; F2 ±10 points with 8 workdays). The matrix, the tiered budget, the pilot gates, the full mode on the package's MCP server, the offline rehearsal, a check with a 61-minute gap, a checkpoint after the pilot, the deliverables |
| 4 | Sonnet only (attribution arms kept on Sonnet). R500 optional, decided at the checkpoint. A leaner Sonnet pilot. Budget: tiers 1 and 2 (≈ $113; total about $209). Sonnet-only limits stated. Compaction window kept at 500K (400K would behave the same in this test) |
| 5 | After the pilot (section 16): the daily inbox in R cells, a new system line each day, the test's code and Claude Code's per-session folders hidden, gates G2–G8 amended, A+ added to R100, L dropped from R100, R500 dropped, a runner spending cap, the second pilot, and the go-ahead rule with a $138 cap |
