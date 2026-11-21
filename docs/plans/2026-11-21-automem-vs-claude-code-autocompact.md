# Test plan: does AutoMemory v2 work inside Claude Code, and does it beat Claude Code's own autocompaction?

Status: **proposed, not run.** Estimated cost: about $30–55, with a $3 pilot first, which decides whether the rest
is worth running.

## 1. The question

Two claims are under test, and each needs its own evidence:

1. **Workable:** AutoMemory v2 runs inside Claude Code on real work without errors, without slowing sessions down,
   and without lowering task results.
2. **Beats autocompaction:** on work that needs memory, Claude Code with AutoMemory v2 reaches the same or better
   results than Claude Code with its own autocompaction alone, at a lower cost per correct result. It must also do
   better than the cheapest alternative a user has: telling Claude Code to keep its own notes file.

## 2. Why the earlier checks could not answer it

| Earlier check | Why it could not show a difference |
|---|---|
| 20 single issues, plain against plugin | Sessions were short (4–6 turns); nothing to compact, no large outputs, nothing carried over |
| Long sessions of 12 issues, compaction at 100K | Compaction fired, but the issues were unrelated: no session needed anything from an earlier one |
| Compaction at 100K and 500K, 36 sessions (2026-11-20) | Prompts peaked at 58–80K and tool outputs stayed under about 2,000 characters, so no mechanism had anything to act on |

There was a second gap: **the plugin is only part of AutoMemory v2.** It previews long Bash output, adds the handoff
recap to compaction, and saves each turn's final message. It has no note tools and no instruction to save
intermediate findings. On the benchmark, that note workspace was the largest gain on multi-session work. Without it,
scores were about 0.1 lower at 1.5–2.5 times the cost. So far, the full v2 has not been tested inside Claude Code.

## 3. What is tested: four mechanisms, each with a place where it should matter

| # | Mechanism | Hypothesis | Where Claude Code alone is weak | Where the test exercises it |
|---|---|---|---|---|
| H1 | Notes across sessions (recall, autosave, note tools) | Later sessions answer correctly without re-reading earlier material | A new session starts from zero | Multi-day task, a new session each day; day *k* needs facts from days 1…*k*−1 |
| H2 | Previews at ingestion (head + tail, full text saved) | The decisive part of a long output is seen at once, in fewer turns | Bash output is cut at about 30,000 characters and only the head is shown | Daily reports of 80–120K characters, with the corrections at the end |
| H3 | Structured handoff recap at compaction | After compaction the agent keeps the running state and does not redo work | Claude Code's general summary may drop exact figures | The multi-day task in one resumed session, with compaction at 100K, so it fires several times |
| H4 | No harm | Same results and cost on ordinary work | — | Real coding issues (SWE-bench), where the benchmark found notes to be overhead |

The design follows from two points:
- **Only tasks where a mechanism can act are informative.** That is what went wrong last time. Each cell therefore
  records whether its mechanism actually fired (section 7). A cell where it did not fire counts as "not exercised",
  not as evidence that the mechanism fails.
- **The predictions are written down before the runs, including the unfavourable ones.** On coding, the benchmark
  found that notes do not pay. If that repeats, it is reported, not hidden.

## 4. Arms: what is compared

| Arm | What it is | Why it is here |
|---|---|---|
| **A: Claude Code** | Plain Claude Code with its own autocompaction | The baseline to beat |
| **A+: Claude Code + a notes prompt** | A, plus one line in the prompt: keep a `NOTES.md` with what later days need, and read it first each day | The cheapest thing a user can do without a plugin. To show it adds value, AutoMemory must beat this too |
| **L: AutoMemory lean** | The plugin with notes off: previews and the handoff recap only (`automem_v2_lean`) | Separates H2 + H3 from H1 |
| **V2: AutoMemory v2** | The plugin in full mode (built in step 0): previews, the handoff recap, notes recalled automatically at every session start, autosave, note tools (`write_note`, `read_notes`), and the rule to save intermediate findings | The proposal under test |

Comparing V2 with L shows what the notes add. Comparing L with A shows what previews and the recap add. Comparing V2
with A+ shows whether the package beats a plain prompt.

**Held the same in every arm:**
- the model, the Claude Code version, the prompts (except A+'s one line), the tools allowed, the per-turn spending
  cap and the timeouts;
- user and project settings switched off (`--setting-sources ""`), so no `CLAUDE.md` differs between arms;
- a fresh working copy and memory directory per run;
- the same task instances, interleaved on the same day.

## 5. Settings: what is varied

| Dimension | Values | Why |
|---|---|---|
| Model | Sonnet (the company's model), Haiku (weaker; where the benchmark found memory helps most) | Results so far differ by model |
| Claude Code compaction window (`CLAUDE_CODE_AUTO_COMPACT_WINDOW`) | **500K** (the company setting: a 1M model compacting at 500K) and **100K** (Claude Code's minimum) | 500K is the real configuration. 100K makes compaction fire within budget, so H3 can be observed |
| Session continuity | **A new session per day**, or **one resumed session** across all days | Developers do both. A new session tests H1; a resumed session tests H3 and the cost of carrying long history |

The model's 1M window is used as is. The pilot confirms the model id and the window Claude Code reports.

## 6. Tasks

### F1: multi-day stock ledger (memory needed; tests H1, H2 and H3)

This is built from the benchmark's `ops_stream` generator, which predates the plugin, so it was not designed around
it.
- **Setup:** a warehouse over 6 days, with 6 tracked products. Each day, `python tools/report.py --day k` prints that
  day's event log, 80–120K characters with filler lines.
- **Corrections:** the end of each log holds AMEND and VOID lines that correct earlier events, often from earlier
  days, by event id only, without naming the product.
- **The question each day:** the closing stock of the 6 products, and which one is lowest. That is 7 checks per day,
  graded exactly from the generator's ground truth.
- **What memory has to carry:** day *k*'s answer needs the running stock, and the product and quantity of every
  earlier event a correction might name. An agent that has forgotten them must re-read every earlier day, or answer
  wrong.
- **Why the logs are long:** they exceed Claude Code's 30,000-character cut, so plain Claude Code sees only the head
  unless it opens the saved file. This is an intended stress for H2, and it is realistic: test runners and CI print
  their summary and errors at the end. It is disclosed as a constructed advantage, and F2 measures how often large
  outputs occur naturally.
- **Answer format:** a fixed JSON block in the final message.
- **Grader check:** before any run, the grader is checked on the generator's own answers (all 7 checks pass) and on
  empty or stale answers (they fail).

### F2: coding on one codebase over several sessions (generality; tests H4, and H1 in coding)

- **The issues:** SWE-bench Verified Django issues, in workdays of 5 related issues from one subsystem
  (`scripts/swe_related.py`).
- **How they run:** a new Claude Code session per issue, as a developer starting a ticket. Graded the way SWE-bench
  grades.
- **Prediction, from the benchmark:** L is level with A, and V2 is level or slightly more expensive, because notes
  were overhead on coding.
- **What else it measures:** how often outputs larger than 30,000 characters occur on natural coding work, and so how
  often H2 can matter in practice.

## 7. Measurements

**Results (primary):**
- F1: checks correct per day (7 per day), and the share of days fully correct.
- F2: issues resolved.
- Cost per run, from Claude Code's own `total_cost_usd`, and cost per correct check or per resolved issue.

**Explanations (secondary):**
- tokens by kind (uncached, cache read, cache write, output), turns, wall time;
- re-exploration: earlier days' reports re-run or re-read (F1); files read again (F2).

**Mechanism checks** (whether each hypothesis was exercised in a cell):

| Mechanism | Counted as |
|---|---|
| H1 | Recall injected at the start of day ≥ 2 (size); `write_note` calls; `NOTES.md` written (A+) |
| H2 | Outputs Claude Code cut (`persistedOutputPath`), and AutoMemory previews fired |
| H3 | Compactions per run, and whether the recap instructions were applied |
| H4 / workable | Hook errors, hook time per call (from a timing log), sessions that did not finish |

## 8. Decision rules (set before the runs)

Each family is judged per model and per cell. The headline is the company cell: Sonnet, compaction at 500K.

| Claim | AutoMemory passes if |
|---|---|
| **Workable** | ≥ 95% of sessions finish; no hook crashes; median hook time under 100 ms; F1 checks or F2 issues at most 3 points below A |
| **Beats autocompaction** (V2 against A, or L against A for coding) | Results not lower (difference ≥ −3 points) **and** cost per correct result at most 90% of A's, with the 95% paired-bootstrap interval's upper bound below 100%. **Or** results at least 10 points higher (sign test p < 0.1) at no more than 110% of A's cost |
| **Adds value beyond a prompt** | The same test against A+ |
| **Attribution** | V2 against L (notes); L against A (previews and recap) |

- **Pairing:** the same instance and day in each arm. The bootstrap resamples instances.
- **No mechanism, no verdict:** where a mechanism did not fire, its hypothesis is "not exercised" in that cell.
- **Effect size:** a difference smaller than the rules above is "not detected", not "no effect".

**Power.** In F1, n = 5 instances × 6 days × 7 checks gives 210 checks per arm and cell. That detects differences
of roughly 10–15 points in accuracy and about 15–20% in cost. The benchmark's effects on this kind of task were
larger: 0.64 against 0.88 in score without notes, at 152–249% of the cost. Smaller effects will not be detected, and
will be reported that way. The pilot measures the run-to-run spread, and n is adjusted before step 2.

## 9. Steps, gates and cost

| Step | What | Cost | Gate before the next step |
|---|---|---|---|
| **0. Build** (no API cost) | The F1 harness (files, `report.py`, prompts, grader); the plugin's full v2 mode (below); a timing log for hooks; the report script (paired bootstrap, sign test, mechanism counts) | $0 | Offline tests pass; the grader scores the generator's answers 7/7 and stale answers below 7/7; full mode passes the plugin tests |
| **1. Pilot** | F1, 1 instance, Haiku, all 4 arms, "new session" at 500K and "resumed" at 100K | ≈ $3 | (a) Claude Code cuts the reports in A; (b) previews fire in L and V2; (c) at least one compaction per resumed run at 100K; (d) V2 writes notes and recall reaches day 2; (e) cost per run within ±50% of the estimate. If any of these fails, redesign first |
| **2. Main runs** | The matrix below | ≈ $25–50 | — |
| **3. Report** | Tables per family, model and cell; each hypothesis marked passed, failed, not detected or not exercised | $0 | — |

**The plugin's full v2 mode (built in step 0).** Switched on with `AUTOMEM_WORKSPACE=on`:
- the session-start hook adds AutoMemory's note rule, and recalls notes from the same store the MCP server uses;
- the plugin registers the AutoMemory MCP server (`automem-mcp`, from the package), which provides `write_note`,
  `read_notes` and `read_artifact`;
- the stop hook autosaves into that store, so each autosaved answer replaces the previous one in recall.

The plugin stays standard-library-only; the note tools need the package installed.

**Main matrix (step 2):**

| Family | Model | Arms | Cells | Runs | Estimated cost |
|---|---|---|---|---|---|
| F1 | Haiku | A, A+, L, V2 | new@500K, resumed@100K, resumed@500K | 4 × 3 × n=5 = 60 | ≈ $15 |
| F1 | Sonnet | A, A+, V2 | new@500K, resumed@100K | 3 × 2 × n=3 = 18 | ≈ $18 |
| F2 | Haiku, Sonnet | A, L, V2 | new session per issue @500K | 3 arms × 20 issues per model | ≈ $3 |

These estimates come from measured costs. A Sonnet Django issue in Claude Code cost about $0.044, and a Haiku one
about $0.005. The long daily reports are estimated at $0.10–0.25 per Sonnet day. The pilot replaces these estimates
with measured ones.

**A smaller version** (≈ $20–25):
- F1 on Haiku as above, with n = 4;
- F1 on Sonnet with A and V2 only, new@500K, n = 3;
- F2 on Sonnet only.

## 10. Threats to validity, and how each is handled

| Threat | Handling |
|---|---|
| The task favours AutoMemory by construction | F1 comes from a generator older than the plugin. The long logs are disclosed as an intended stress. F2 is real, unmodified work, and its prediction (no gain) is reported whichever way it goes. A+ gives Claude Code a fair memory alternative |
| Run-to-run noise and day-to-day drift | Arms run interleaved, on the same instances, on the same day. The pilot measures the spread. Paired tests are used |
| Claude Code changes during the runs | Its version is recorded per run and must be the same across arms |
| Leakage between runs | A fresh working copy, memory directory and plugin data directory per run |
| Grader errors | Checked against the generator's answers and against stale answers before any spending |
| Cost measured wrongly | Claude Code's own `total_cost_usd`. For resumed sessions, the per-turn increase, as in `run_cc_long.py` |
| The 500K cell never compacts | Expected for six days of reports. That cell measures the cost of carrying long cached history, where previews are AutoMemory's only lever. The 100K cell covers compaction |
| Small samples | Rules are fixed in advance; "not detected" is kept apart from "no effect"; n is adjusted after the pilot |

## 11. What each outcome would mean

- **V2 beats A and A+ on F1, and is level on F2.** AutoMemory is worth installing for multi-day work. Advise turning
  notes off for independent tickets (lean mode).
- **V2 beats A, but not A+.** The gain is real, but a notes prompt gets most of it. The plugin's value is
  convenience, not a new capability, and the README should say so.
- **L beats A, but V2 does not beat L.** Previews and the recap carry the gain. Make lean the default in Claude Code.
- **Nothing beats A.** Inside Claude Code, its built-ins are enough. Position AutoMemory for agents without them (the
  adapters), and say so plainly.
