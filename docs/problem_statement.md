# Problem statement: agent memory and token cost for everyday coding agents

**Goal of this project:** the fewest tokens and dollars per solved task, at full task accuracy, with a slim and effective context.

This document explains:
- what "agent memory" and "token optimisation" mean for a coding agent such as Codex or Claude Code;
- which problems their daily users run into;
- how the measurements in this repository address each problem, and what is still open.

Numbers come from `docs/results/` and are current as of 2026-11-04. Results for the newer methods (`real_v5`) and AutoMemory v2 are partial while their runs complete.

## 1. Two problems, one budget

A coding agent has no memory of its own. On every step the harness sends the whole conversation again: system prompt, files read, test output, earlier reasoning. That has three consequences:

- **The context window is the agent's working memory.** Anything that is not in the request does not exist for the model.
- **Cost grows faster than the work.** Step N re-sends steps 1…N−1, so a long session costs much more than the sum of its steps. Prompt caching makes re-sent tokens cheap (0.05–0.1× of the input price on the Claude routes measured here), but only while the earlier part of the prompt stays byte-identical. Any edit to earlier history is re-billed from the edit onward, at cache-write price (2× input on the Claude Code CLI, 1.25× on Bedrock).
- **Memory across sessions is extra machinery** (notes, files, retrieval, summaries) built around the model.

So there are two separate problems:

| Problem | Question | Usual name |
|---|---|---|
| Within-session context | What should this request contain, and how small can it be without losing what matters? | Context engineering, compaction, token optimisation |
| Cross-session memory | What should survive until the next session, and how does it come back? | Agent memory, long-term memory |

The common trap is to treat "fewer tokens" as the goal. The measure used here is **cost per solved task at full accuracy**, priced with real cache rates.

## 2. What daily users run into

These are the problems practitioners report (see [`literature/2026-11-scan/community.md`](literature/2026-11-scan/community.md)). The third column says whether these experiments reproduced each one.

| # | Pain point | Seen in our runs? |
|---|---|---|
| 1 | **Tool output floods the context.** Test logs, grep results and whole-file dumps make up most of the tokens, and agents re-read the same files. | Yes. One `pytest` run in `repo_debug` is 3K+ tokens. On every long task the context-window limit was the main way runs failed. |
| 2 | **Context rot.** Quality drops long before the window is full. Drew Breunig: "around 200,000 tokens is my warning point… delete your context." | Indirectly. A smaller peak context at the same accuracy is cheaper on every later step. |
| 3 | **Compaction amnesia.** After auto-compaction the agent forgets decisions, re-reads files and retries failed fixes. | Yes. Haiku re-opened old files instead of using its notes. Without its last steps kept verbatim after a compaction, its replies degenerated into malformed tool calls. |
| 4 | **Session amnesia.** The next session re-explores the repository from scratch; users maintain `AGENTS.md` / `CLAUDE.md` by hand. | Yes. The multi-session tasks fail without a memory carried across sessions. |
| 5 | **Usage caps and surprise bills.** Long sessions hit limits such as "You've hit your session limit · resets …". | Yes. These experiments hit the limit themselves; the harness now waits for the reset. |
| 6 | **"Token savers" that do not save money.** RTK claims 60–90% fewer tokens, but an independent benchmark measured about +1% cost: cache reads were 94–98% of the input tokens but only 26–30% of the bill. | Yes; see AKV in §3. |
| 7 | **Opacity.** Users cannot see what was dropped, or why the agent suddenly forgot something. | Addressed by design: everything removed stays retrievable, and every technique logs what it did. |

## 3. How this research addresses each pain point

### The measurement framework (pain 6)

**Method**
- Every method runs on the same tasks, seeds and windows as two reference points:
  - **floor:** `naive`, no memory and no caching;
  - **ceiling:** `naive@native`, nothing lost and the model's own context window.
- **Recovery** = (score − floor) / (ceiling − floor).
- **Cost** is a ratio to the ceiling's cost, with each route's real cache pricing.
- A method is *model-robust* only if it recovers on both models tested (Haiku and Sonnet).

**Why it matters**
- It separates "fewer tokens" from "fewer dollars".
- **Example: AKV rolling drop**, Sonnet on `research_corpus`, one run each:
  - Dropping old tool results on every turn cost **89%** of the ceiling, with 14% cache hits.
  - Dropping the same results in blocks of 8 cost **21%**, with 82% cache hits, at the same score of 1.00.
- AKV's own paper measured its text-level variant at 1.85× the cost of full context.

### Tool-output flood (pain 1): handle it at ingestion

An output that is shrunk *before* it enters the history never breaks the cache. Three mechanisms do this:
- AutoMemory's in-step guard offloads an output that would push the prompt past 90% of the window.
- Strands-style head/tail previews keep the full text retrievable by reference (`retrieve_context`, with grep or a line range).
- ReFold replaces repeated reads, searches and identical outputs with stubs that point to the earlier copy.

Evidence: the Strands harness defaults solved `ledger_audit` at about 36% of the ceiling's cost on both Haiku and Sonnet (2 of 2 runs each, partial).

### Slim context (pain 2): keep the peak small without losing accuracy

On Sonnet `research_corpus`, ReFold and SelfCompact peaked at 15–18K tokens, against about 30K for AutoMemory v1 and 72K for the ceiling, at full accuracy (one run each so far).

Both depend on the model following a protocol: ReFold needs it to mark finished steps as STALE, and SelfCompact needs it to answer its own rubric honestly. Both were less reliable on Haiku.

### Compaction amnesia (pain 3): compaction done right

From the AutoMemory v1 ablations (`docs/results/2026-10-24-automem-evaluation.md`):
- **Compaction is necessary.** With compaction switched off, the long tasks fail.
- **ReSum summaries beat observation masking.**
- **Keep the last 2 steps verbatim** after a compaction.
- **Re-inject the notes** after a compaction.
- **A cheaper model can write the summaries.** Sonnet with a Haiku summariser solved all of its runs at 19–61% of the ceiling's cost, depending on the task.

### Session amnesia (pain 4): simple, automatic memory

- **Automatic carry-over wins.** A note workspace that is recalled automatically at session start, with each session's answer saved automatically, beat the official long-term memory systems (MemoryOS, LightMem, Nemori), which scored 0.2–0.5 lower on the same tasks.
- **This matches the "Memory Tax" papers.** Several independent studies (arXiv 2610.34073, 2610.30755, 2610.29823) found that plain retrieval over raw history often beats dedicated memory systems for strong models.
- **Raw-history retrieval also holds up here.** It solved `repo_debug` and `ledger_audit` on Sonnet at 90–91% of the ceiling's cost (partial).

### Usage caps and cost (pain 5)

The best combinations so far reach about 20–60% of the ceiling's cost at full accuracy, depending on the task. The final numbers come from the v5 and AutoMemory v2 runs.

### Opacity (pain 7)

- Every offload, preview, fold and compaction is logged.
- The original content stays retrievable through `read_artifact`, `retrieve_context` or `restore`, so nothing is lost silently.

## 4. The design lesson: automate memory in the harness

Across both models, the methods split into two groups.

**Fragile: methods that rely on the model choosing to manage its own memory.**
- **CORAL:** the prompting-only variant's memory and reset tools were never called on these tasks.
- **ReFold:** the model has to mark finished steps STALE.
- **SelfCompact:** the model has to answer a rubric on whether to compact.

**Robust: steps the harness performs automatically.**
- Ingestion guard and previews.
- Recall at session start and autosave of results.
- Compaction at a fixed threshold, keeping recent steps.
- Batched history edits.

For a Codex or Claude Code user, this means the fix belongs in the tool, not in the user's prompts.

There is also a packaging consequence. AutoMemory already ships as an MCP server (`eam/mcp_server.py`, documented in `docs/automem.md`): notes, recall, offload, compaction and context-budget tools. It was verified across two Claude Code sessions. But ingestion previews, render-time deduplication and compaction timing need hooks inside the agent loop, which an MCP server cannot provide. Those parts belong in the harness itself, which is where production harnesses (Strands, Claude Code, Codex) are absorbing them.

## 5. What is still open

1. **Realistic coding workloads.** Apart from `repo_debug` (real pytest runs on a generated library), the tasks are synthetic. A benchmark on real repositories and multi-day sessions (SWE-bench style) is the missing evidence.
2. **Codex and OpenAI pricing.** Everything was measured on the Claude Code CLI route. OpenAI's prompt caching is automatic and priced differently, so whether a method pays off has to be re-checked there. The framework takes prices as parameters, so this is a re-pricing exercise plus a validation run. This has not been done.
3. **Bedrock validation** is blocked on AWS credentials; the runbook is `docs/results/2026-10-24-bedrock-validation-plan.md`.
4. **Sample sizes** are 1–4 runs per cell, and single runs on these tasks vary by up to 0.5 in score. The pending runs bring the new methods to 4 seeds on Haiku and 2 on Sonnet.

## 6. Where this is heading: AutoMemory v2

AutoMemory v2 is a cache-aware harness layer built from the components that measured best:
- handle large outputs at ingestion, with retrieval by reference;
- deduplicate and fold finished steps at render time, in batches;
- compact rarely, with a cheap summariser, keeping the recent steps verbatim;
- carry notes across sessions automatically.

Every component is a switch so it can be ablated. It is judged on dollars and tokens per solved task at full accuracy, on both models. Results ([`results/2026-11-04-automemory-v2.md`](results/2026-11-04-automemory-v2.md)): previews at ingestion (`automem_v2`) solved 11/16 Haiku runs (v1: 7/16) at the same cost, and cut Sonnet to 64% of the unoptimised cost (v1: 72%). Folding (`automem_v2_slim`) gives the smallest peak context, at a higher cost.
