# Open-source and practitioner community: agent memory and context engineering, 2026-09-04 to 2026-11-04

> **Provenance.** These are raw research notes compiled on 2026-11-04 by a research agent.
>
> **Sources used:**
> - Star counts are GitHub search API snapshots from 2026-11-04.
> - Releases come from GitHub release lists (through a mirror of the GitHub API) and from PyPI.
> - Blogs were read on the authors' own sites, Hacker News through the HN Algolia API, and papers through the arXiv API.
>
> **Limits:** Reddit returned 403, so Reddit items are secondary. Star *growth* within the window could not be measured.
>
> **Checked again by hand on 2026-11-04** (titles and dates on arXiv): the four "raw retrieval vs memory systems" papers and DolphinBench. Two other items were confirmed through independent coverage: the Strands harness launch and OpenAI's compaction-injection report.

## 1. Repositories

### 1a. Memory layers and frameworks

| Repo | Stars | Latest release (date) | What changed in the window | Licence |
|---|---:|---|---|---|
| thedotmack/claude-mem | 112,181 | v15.9.0 (11-02) | v15.0.0 (10-20): progressive "smart search" by default (compact index → context → selected details). v15.0.2: observer calls no longer spend reasoning tokens. | Apache-2.0 |
| mem0ai/mem0 | 68,363 | v2.2.1 (09-25) | "User Profiles" (an always-current JSON summary of one user); harness plugins | Apache-2.0 |
| volcengine/OpenViking | 41,478 | v0.5.3 (11-02) | v0.5.0 (10-09): base-URL memory gateway. Injected content is replayed byte-for-byte, so the prompt cache stays valid; bounded summary at 90% of the window. | AGPL-3.0 |
| topoteretes/cognee | 33,042 | v1.6.6 (10-29) | Keyless workflows; durable fact-conflict resolution | Apache-2.0 |
| getzep/graphiti | 32,501 | v0.31.2 (10-20) | MCP SDK 2.x; LLM runtime routing | Apache-2.0 |
| getzep/zep | 4,989 | v4 "Context API" (10-14) | Hyperedges; bi-temporal facts | Apache-2.0 |
| supermemoryai/supermemory | 31,522 | server-v0.0.9 (10-12) | Local server; company brain and Nova discontinued 09-09 | MIT |
| langchain-ai/deepagents | 30,972 | 0.7.32 (10-23) | Async subagents (10-29) | MIT |
| langchain-ai/openwiki | 17,718 | v0.7.2 (10-09) | Agent-maintained documentation wiki | MIT |
| letta-ai/letta-code | 3,777 | v0.34.38 (11-02) | Subagent orchestration. The Letta server has had no release since 0.16.8 (May). | Apache-2.0 |
| MemTensor/MemOS | 12,246 | v2.0.34 (09-23) | Maintenance; new MemT-1.0 model repo (10-19) | Apache-2.0 |
| EverMind-AI/EverOS | 13,800 | v1.5.1 (10-22) | Async ingestion queue | Apache-2.0 |
| basicmachines-co/basic-memory | 4,468 | v1.0.0 (10-29) | 1.0 release | AGPL-3.0 |
| plastic-labs/honcho | 7,932 | v3.5.0 (10-30) | ChromaDB backend | AGPL-3.0 |
| MemMachine/MemMachine | 3,085 | v0.4.0 (10-08) | BEAM benchmark support | Apache-2.0 |

No release in the window: memU, MIRIX, Memobase, Memori, memvid, LangMem, Microsoft Kernel Memory, OpenMemory.

### 1b. Token-saving tools

| Repo | Stars | Latest release | Notes |
|---|---:|---|---|
| rtk-ai/rtk | 85,502 | v1.1.0 (10-25) | Compresses shell output; claims "60-90%" fewer tokens. An independent benchmark (§2) disputes the cost benefit. |
| headroomlabs-ai/headroom | 78,780 | v0.42.0 (10-26) | Claims "21–57% fewer input tokens"; per-request counterfactual savings records |
| strands-agents/sdk-python (Strands harness) | 9,034 | harness v0.3.2 (10-22) | Strands harness launched 09-21 |

### 1c. New repos gaining traction in the window

- **tigerless-labs/agent-memory** (4,303 stars, created 09-01). Markdown is the source of truth; retrieval is local and ranked; a "sleep-time" layer consolidates and forgets.
- **okf-memory/okf-agent-memory** (852 stars).
- **Graphicle-AI/graphicle** (501 stars).
- **aerovato/operator-memory** (495 stars).

## 2. Benchmarks and evaluations

### New benchmarks

- **DolphinBench** (Mem0). [arXiv 2609.24971](https://arxiv.org/abs/2609.24971), 2026-09-21.
  - **Design:** memory graded by *actions*, not QA, with cost and latency reported alongside accuracy.
  - **Results** (Hermes with GPT-5.6-Luna):

    | Memory | Score | Cost |
    |---|---|---|
    | Built-in | 65.67% | $61.48 |
    | Mem0 | 70.67% | $96.21 |
    | Supermemory | 59.17% | $345.64 |

  - **Caveat:** vendor-authored.
- **Mem0's LoCoMo sweep over extraction models (10-20):** "the most expensive costs 233 times as much as the cheapest". Nova Micro scored 88.0% at $0.86 per 1,000 adds.

### Independent evaluations: plain retrieval over raw history is a strong baseline

- **[2610.30755](https://arxiv.org/abs/2610.30755) "Naive RAG Is Stronger Than We Thought":** Raw-RAG ranks first in six of seven benchmark × model settings.
- **[2610.34073](https://arxiv.org/abs/2610.34073) "Memory Tax":** many dedicated memory systems have negative net value against naive RAG.
- **[2610.29823](https://arxiv.org/abs/2610.29823) "MemoryTax: The Bitter Lesson of Agent Memory":** coding agents searching raw history beat Mem0 and Zep once the model is strong. Small study: one conversation.
- **[2610.24671](https://arxiv.org/abs/2610.24671):** six explicit memory systems show no consistent advantage over raw-history RAG.
- **[2610.36308](https://arxiv.org/abs/2610.36308):** obsolete facts hurt as the evidence budget grows (BM25 45% → 32%).

### Disputes and audits

- **MemStrata [2610.05343](https://arxiv.org/abs/2610.05343):** grading the same answers two ways gives 90.91% vs 78.25% on LoCoMo.
- **Quesma on RTK (09-11, HN 170 points):**
  - 1,740 attempts; Fable "1% more expensive" and DeepSeek "+17%".
  - Cache reads were 94–98% of input tokens but 26–30% of the bill.
  - "rtk gain is useless as a cost metric."

## 3. Practitioners and KOLs

### Recurring threads

- **Drew Breunig.**
  - "The State of Context Engineering" (10-24, HN 274 points): six fixes (augmentation, loadout, quarantine, pruning, offloading, summarisation). "Around 200,000 tokens is my warning point… Delete your context." "Mind your prompt caching."
  - "Context Inertia" (10-14): "throw the context away and keep the work".
- **Harrison Chase, "New context engineering challenges in late 2026" (11-02).**
  - The standard toolbox: summarisation, offloading tool results, skills (progressive disclosure), tool search, subagents, bash.
  - Open problems: what memory should keep, async subagents, goal tracking.
- **Philipp Schmid, "Why Agents Are Soon Only Going to Have 1 Tool" (11-01).** One `exec(code)` tool; results are filtered in the sandbox before they enter the context.
- **Simon Willison.**
  - Wants default hard budget caps (10-03, HN 652 points).
  - Covered OpenAI's compaction-summary injections ([09-17](https://simonwillison.net/2026/Sep/17/compaction-summaries/)).
- **Dex Horthy, SlopCodeBench (10-15).** "XHigh costs 2.11-4.22x as much as Medium" without better results.
- **Kevin Liao, "Agents Don't Need Memory. They Need Documentation." (10-03, HN 392 points).**
- **Spotify Engineering (09-03).**
  - Large reads routed to a cheaper model: "Mean bulk-read savings were around a whopping 90%."
  - But "You can't delegate editing… reasoning."
- **arXiv [2609.20804](https://arxiv.org/abs/2609.20804), harness study (HN 225 points).**
  - "Rule-based elision before LLM-based summarization provides the strongest overall efficiency."
  - Making the elided content recoverable gave "no accuracy gain".
- **Nothing in the window:** Lance Martin, Chroma, Jason Liu, Eugene Yan, Yichao Ji (Manus).

### Themes

1. The toolbox is settled and has moved into the harness.
2. Memory as Markdown or file indexes, loaded on demand.
3. Deliberate forgetting and context resets.
4. Measure cost per solved task, not tokens removed.
5. Prompt caching is the main cost lever.
6. Cheap models or sub-agents as context routers.
7. Compaction summaries and memory as injection surfaces.

### Disagreements

- **Engineered memory vs docs or raw history.**
  - Papers and Liao find negative net value for strong models.
  - Vendors answer with DolphinBench, OpenWiki and Zep.
- **Single loop vs isolated subagents.** Anthropic (10-22) advises one loop; Meta (10-19) isolates subagents.
- **When to reset.**
- **Pruning mid-history vs keeping the cache.**
