# Agent memory and token saving: what changed from September to early November 2026

**Scan date:** 2026-11-04.

**Window:** 2026-09-01 to 2026-11-04. A few August items are included where they matter.

**Files in this directory:**

| File | What it holds |
|---|---|
| [`arxiv_sweep.md`](arxiv_sweep.md) | Generated paper tables (scripts `sweep.py`, `html_affil.py`, `classify.py`) |
| [`china_labs.md`](china_labs.md) | Chinese labs, companies and universities |
| [`us_labs.md`](us_labs.md) | US labs and platforms, including what is and isn't available on Bedrock |
| [`community.md`](community.md) | Repos, benchmarks, practitioners |

## How this was searched

- **arXiv.**
  - Every paper submitted from 2026-09-01 to 2026-11-04 that matched agent-memory, context-management or token-efficiency keywords was pulled through the arXiv API: **1,515 papers**.
  - Of these, 799 are focused on memory, context or tokens for agents. 369 were scored highly relevant.
  - Affiliations were read from each paper's arXiv HTML author block.
- **Labs, community and repos.** Three research passes covered:
  - US labs and platforms, from official docs, changelogs, blogs and AWS What's New;
  - Chinese labs, from arXiv author blocks, Hugging Face model cards, GitHub READMEs and 量子位;
  - repos, benchmarks and practitioners, from GitHub, PyPI, author blogs and Hacker News.
- **Verification.** Key claims were re-checked by hand: arXiv titles and dates, the Bedrock feature page, the AWS cost playbook, the Apple page and the Strands blog.
- **Not reachable:** openai.com articles (403), the GitHub REST API for some passes, Reddit (403), 机器之心, Zhihu, WeChat.
- **All numbers are the sources' own claims.**

## The picture in one paragraph

Research volume is large, and **China leads it**. Of the 369 most relevant papers, **40% (148) have a Chinese university or company author**, against **9% (34) for the big US labs and companies**. Tsinghua, SJTU, HKUST, Alibaba, Fudan, PKU and CUHK top the list (`arxiv_sweep.md`).

The US labs' output in the window is mostly **products and pricing**: cheaper cache reads, server-side compaction, message threads, harnesses, memory services. China's is mostly **papers and open weights**: KV-efficient models, compaction methods, memory-writer models.

The community has converged on a **standard toolbox**:
- offload large tool results;
- compact near the window;
- progressive disclosure through skills and tool search;
- subagents;
- keep the prompt cache intact.

It has also **turned sceptical of elaborate memory systems**. Four independent October papers find plain retrieval over raw history matches or beats them.

## Seven themes, with the strongest evidence

### 1. Compaction is lossy and unsafe; measure and constrain it

- **USTC [Compact-Bench](https://arxiv.org/abs/2610.31710):**
  - LLM summaries keep at most **16.0%** of recurring details, against **79.1%** for mechanical extraction.
  - Compaction damages **5–64%** of the tasks that full history solves, across 14 summarisers.
- **[Source-Judged Compaction](https://arxiv.org/abs/2610.20927):**
  - **83%** of failed runs trace to a summary entry that no environment output supports.
  - The proposed fix strips unsupported entries with one cheap judge call.
- **Salesforce ([2610.08722](https://arxiv.org/abs/2610.08722)):** predicting harmful compactions avoids 21% of them while keeping 84% of the opportunities.
- **Safety:**
  - OpenAI found jailbreak-like instructions that models wrote into their own compaction summaries ([Willison, 2026-09-17](https://simonwillison.net/2026/Sep/17/compaction-summaries/)).
  - Anthropic shows misalignment propagating through memory ([2610.04083](https://arxiv.org/abs/2610.04083)).
  - [MemHarmBench](https://arxiv.org/abs/2611.01700) (Alibaba/Fudan) shows injected instructions persisting across sessions.

### 2. The prompt cache is the main cost lever, so editing must be cache-aware

- **Bedrock cache reads for Claude Sonnet 5.5 and Opus 5.5 now cost 0.05× input** ([AWS cost playbook, 2026-10-30](https://aws.amazon.com/blogs/machine-learning/managing-amazon-bedrock-costs-end-to-end-a-playbook-for-finops-and-platform-teams/)).
- **Quesma:** cache reads were 94–98% of input tokens but only 26–30% of the bill. A popular token-compression tool raised real cost.
- **Cache-aware context methods:**

  | Method | Lab | Idea | Claim |
  |---|---|---|---|
  | [Cache Engineering / AKV](https://arxiv.org/abs/2610.28577) | Tsinghua/CUHK | Rolling drop of old tool outputs | −27.7% cost vs summarisation |
  | [CADOC](https://arxiv.org/abs/2609.37012) | SJTU | Batched, cache-aware replacement with retrievable "Cards" | ≈−40% input cost |
  | [ReFold](https://arxiv.org/abs/2610.07863) | UCSB/Intel | Reversible folding that rewrites the cached prefix only every few steps | — |
  | OpenViking v0.5 gateway | ByteDance Volcengine | Replays injected memory byte-for-byte so the cache stays valid | — |

### 3. Raw history plus search is a hard baseline for memory systems

- **Four October papers.**
  - [2610.30755](https://arxiv.org/abs/2610.30755): Raw-RAG first in 6 of 7 settings.
  - [2610.34073 "Memory Tax"](https://arxiv.org/abs/2610.34073): negative net value for many dedicated memory systems.
  - [2610.29823 "MemoryTax"](https://arxiv.org/abs/2610.29823): a coding agent searching raw history reaches 99% at under half the full-context cost.
  - [2610.24671](https://arxiv.org/abs/2610.24671): no consistent advantage for explicit memory.
- **Further support:**
  - CUHK MemUse: memory systems within 0.4 pp of no memory on SWE-bench.
  - ["What is this memory useful for?"](https://arxiv.org/abs/2611.03930): raw memories beat task-blind summaries.
- **Vendors' counter-evidence** grades memory by *actions*: Mem0's DolphinBench ([2609.24971](https://arxiv.org/abs/2609.24971)) and LangChain OpenWiki.
- **[Explicit state outlasts long context](https://arxiv.org/abs/2611.02361):** past a horizon that depends on the model reading it, a compact explicit state beats re-reading the whole history.

### 4. Memory as files or indexes, loaded on demand, with consolidation ("dreaming")

- Claude Code's MEMORY.md index.
- claude-mem v15's progressive search (112K stars).
- NVIDIA NemoClaw: a Markdown self-model plus a SQLite ledger; changed-fact tracking 60% → 100%.
- Anthropic Managed Agents "Dreams", consolidating a memory store from past transcripts.
- Huawei MindMemOS and OpenBMB PilotDeck "dream mode".
- Liao's "Agents need documentation, not memory" (HN 392 points).

### 5. Harnesses now carry the savings

- **[Strands harness](https://strandsagents.com/blog/introducing-strands-harness/)** (AWS, 2026-09-21).
  - Truncates tool results over about 1,500 tokens and compacts above 85% of the window.
  - Claims 28% lower token cost; vendor-run.
- **Anthropic's cost playbook:** 24–73% cost cuts on four benchmarks from caching, effort and trimming.
- **[ContextPipe](https://arxiv.org/abs/2609.00749)** (Tsinghua): −31% tokens, −23% calls.
- **[TraceLite](https://arxiv.org/abs/2610.28612)** (CUHK): −33% tokens on SWE-bench Verified.
- **NVIDIA [SoL-Pi](https://arxiv.org/abs/2609.20519):** −45–49% token traffic.
- **[Harness study](https://arxiv.org/abs/2609.20804):** "rule-based elision before LLM-based summarization" is the most efficient combination.

### 6. Let the model decide when to compact or reset

- **Apple [Self-Compacting Agents](https://machinelearning.apple.com/research/self-compacting-language-agents)** (NeurIPS): a compaction *tool* plus a rubric gives "30–70% lower per-question cost".
- **Tencent [CORAL](https://arxiv.org/abs/2610.40350):** checkpoint-and-reset tools use 6–7× fewer input tokens than ReAct.
- **ByteDance [Traverse](https://arxiv.org/abs/2609.37082):** "autonomous compression outperforms automatic compaction".
- **Breunig:** "throw the context away and keep the work".

### 7. Subagents, skills, effort and routing

- **Subagents vs one loop: the labs disagree.**
  - Anthropic (2026-10-22) recommends a single loop with progressive skills and tool search.
  - Meta's "Thin Orchestrator" (2026-10-19) isolates 14 subagents.
  - Microsoft finds subagents beat in-context skills when the skills have clear input-output contracts ([2609.09233](https://arxiv.org/abs/2609.09233)).
- **Effort:** extra-high effort costs 2–4× with no gain (SlopCodeBench).
- **Routing:** cheap routers need held-out validation (Google, 2026-11-03). Switching to a cheaper model mid-session costs cache reuse ([2610.19292](https://arxiv.org/abs/2610.19292)).

## Chinese labs: highlights

Full detail in [`china_labs.md`](china_labs.md).

| Organisation | Item | Why it matters | Usable through Bedrock? |
|---|---|---|---|
| DeepSeek | [V4.1-Flash](https://arxiv.org/abs/2609.19969) | Architecture for input-heavy agents: 890 bytes/token KV, 8B active in prefill, MIT weights | Only through price and latency |
| Tencent | [Hy-Memory-30B-A3B](https://arxiv.org/abs/2610.22196) | First open, specialised memory-*writer* model for Mem0/MemOS. Claims 55.49 vs 54.62 for Claude Opus 5 | Self-host only; shows the writer model matters |
| Tencent | [CORAL](https://arxiv.org/abs/2610.40350) | Checkpoint-and-reset working-memory tools, 6–7× fewer input tokens | The tools, yes |
| USTC | [Compact-Bench](https://arxiv.org/abs/2610.31710) | Quantifies what compaction loses | Yes |
| Tsinghua/CUHK, Tsinghua/RUC | [AKV](https://arxiv.org/abs/2610.28577), StateComp/DRSR/GEM series | Cache-preserving drops; −20.8% to −52.3% tokens (two variants are training-free) | Training-free ones, yes |
| Ant Group | [FlowState](https://arxiv.org/abs/2609.34565) | Execution state as memory: −40–43% tokens | Yes |
| Alibaba | [REMORY](https://arxiv.org/abs/2610.11287), [MemForest](https://arxiv.org/abs/2609.08273), [EGMemory](https://arxiv.org/abs/2609.23465) | Residual memory; memory compression; evidence-grounded memory | MemForest and EGMemory, yes |
| SJTU | [CADOC](https://arxiv.org/abs/2609.37012), [MemoryTax](https://arxiv.org/abs/2610.29823) | Cache-aware replacement; the case for raw history | Yes |
| MemTensor | MemT-1.0, [MemTrace](https://arxiv.org/abs/2610.04838) | Memory-native model; provenance-aware coding memory | MemTrace, yes |

**Checked, nothing in the window:** ByteDance Seed, Moonshot (papers), Zhipu (papers), MiniMax (papers), Baidu ERNIE, Tongyi DeepResearch, MemoryOS, LightMem.

## US labs: highlights, and what is on Bedrock

Full detail in [`us_labs.md`](us_labs.md).

| Organisation | Item (date) | Claim | On Bedrock? |
|---|---|---|---|
| Anthropic | Claude 5.5 cache-read price (09-22 / 10-07) | Reads at 0.05× input | **Yes** (AWS confirms) |
| Anthropic | Cost playbook + `/claude-api cost-optimize` (09-08) | −24% to −73% cost at ≈ equal accuracy | Yes; client-side practices |
| Anthropic | On-demand compaction (09-14), message threads (11-02, −35% TTFT at 500K–1M) | Server-side context management | **Not listed** for Bedrock. Threshold compaction and context editing are beta there |
| Anthropic | Programmatic tool calling, Skills, MCP connector, Managed Agents (memory, Dreams) | — | **Not supported** (Bedrock feature page) |
| Anthropic | Memory tool; tool search | — | Memory tool supported; tool search per the docs |
| AWS | Strands harness (09-21) | 28% lower token cost, vendor-run | Yes, Bedrock-native |
| AWS | AgentCore Memory: consumption pricing, long-term TTL, IngestData (Sep–Oct) | $1/GB ingestion, $0.20/GB retrieval | Yes |
| AWS | REM, EchoPath, EnSIMem papers | REM: 27.6% vs 24.9% resolution at −17% cost | Ideas, yes |
| OpenAI | 12-hour prompt caching; Agents API with managed compaction | — | No (OpenAI platform) |
| Google | Gemini 4 Argon implicit caching (95% discount); route by cost per task | — | No |
| Microsoft | [FOCUS](https://arxiv.org/abs/2609.37590), environment-probing memory curation, model-switch cache cost | FOCUS −48% peak context. Curation: $3.38 → $1.68 per task, tested on Claude | Ideas, yes |
| Meta | Thin Orchestrator; [GitSwarm](https://arxiv.org/abs/2610.04862); [retention](https://arxiv.org/abs/2610.07100) | — | Ideas, yes |
| Apple | [Self-Compacting Agents](https://machinelearning.apple.com/research/self-compacting-language-agents) | 30–70% lower cost per question | Yes; a tool plus a rubric |

## What this means for this project

### Where the field confirms this project's measurements

1. **Summaries lose exact state; explicit notes keep it.**
   - Compact-Bench's 16% vs 79% matches what we saw:
     - ReSum on Sonnet redefined a quantity mid-task.
     - LightMem's extraction dropped the numbers.
     - The note workspace was the only model-robust method across sessions.
   - SJC's "83% of failures trace to unsupported summary entries" is the same failure mode.
2. **The cache decides cost, and history rewrites can make caching cost more than it saves.**
   - Here, masking and AgentDiet were cheaper with caching off.
   - Quesma, AKV and CADOC find the same; the community calls it "prompt caching is the main cost lever".
3. **Official memory systems underperform simple storage.**
   - Here, MemoryOS, LightMem and Nemori scored 0.2–0.5 below a plain workspace.
   - That agrees with the four "Memory Tax" papers.
4. **Harness defaults matter more than any single method.** AutoMemory's combination (offload, compact near the window, workspace) is the shape Strands, Anthropic and Chase all describe.

### What to change or test next (AutoMemory v2)

| Change | Source | Fits our data |
|---|---|---|
| Make history edits cache-aware: batch them, or drop old tool outputs on a rolling basis instead of summarising the prefix | AKV, CADOC, ReFold | Masking/AgentDiet cache collapse; the guard's cost on `ledger_audit` |
| Check every summary entry against its sources before keeping it (SJC) and **keep mechanical facts alongside the summary** (Compact-Bench) | SJC, Compact-Bench | ReSum's definition drift |
| Offer the model a **compaction or reset tool with a rubric** in addition to the threshold trigger | Apple SELFCOMPACT, CORAL, Traverse | The guard is task-dependent; a model-chosen trigger may fix `ledger_audit` |
| Add **raw-history retrieval** (BM25 or dense search over the stored transcript) as a baseline and as a memory backend | Memory Tax papers | Not yet tested here |
| Treat recalled memories and summaries as **untrusted**: provenance tags, no instructions in memory | OpenAI, Anthropic, MemHarmBench | AutoMemory's autosave and recall have no injection guard yet |
| Adopt Strands-style defaults as a baseline harness on Bedrock: truncate tool results over ≈1,500 tokens, compact at 85% | Strands | Directly comparable to our `full` + guard |

### Bedrock-specific notes

- **Move to Claude Sonnet 5.5 or Opus 5.5 on Bedrock.** Cache reads at 0.05× make cache hygiene worth even more. AWS publishes CloudWatch queries for finding caching candidates.
- **Know the gaps.** On-demand compaction, message threads, programmatic tool calling, Skills and Managed Agents memory are not available on Bedrock. Claude Platform on AWS has most of them. AutoMemory and Strands implement the equivalent client-side.

## Caveats

- **Two months of mostly unreviewed preprints.** Venue is given only where a paper states it. Most numbers are authors' or vendors' own claims.
- **Affiliation tagging is regex-based** on arXiv author blocks: 19 of the 369 papers had none, and some tags may be wrong.
- **Some sources were unreachable:** openai.com (403), Reddit (403), 机器之心, Zhihu and WeChat. OpenAI and Chinese-community coverage is thinner as a result.
