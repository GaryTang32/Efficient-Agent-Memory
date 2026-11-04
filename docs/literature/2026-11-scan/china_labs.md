# Chinese labs, companies and universities: agent memory and context/token efficiency, 2026-09-04 to 2026-11-04

> **Provenance.** These are raw research notes compiled on 2026-11-04 by a research agent.
>
> **Sources used:**
> - arXiv (31 queries). Affiliations were matched on the arXiv HTML author block only, which avoids false positives from papers that merely use Qwen or DeepSeek models.
> - Hugging Face model cards.
> - GitHub READMEs, read through raw.githubusercontent.com because the GitHub API was blocked.
> - 量子位 (qbitai) for community coverage. 机器之心, Zhihu and WeChat were not reachable.
>
> **Checked again by hand on 2026-11-04** (titles and dates on arXiv): Hy-Memory-30B-A3B (2610.22196), CORAL (2610.40350), Cache Engineering for Agents (2610.28577), TraceLite (2610.28612), Compact-Bench (2610.31710), DeepSeek-V4.1-Flash (2609.19969).
>
> Numbers are the authors' claims.
>
> **"Bedrock?"** says whether a team calling models only through Bedrock APIs (no self-hosting or training) can use the item:
> - **Yes:** can be implemented in the harness.
> - **Partial:** the idea transfers, but the best results need a trained or self-hosted part.
> - **No:** needs control of model serving or training.
>
> **[AUG]** marks an August item included because it matters.

## Companies

### DeepSeek

- **DeepSeek-V4.1-Flash: Pushing the Limits of KV Cache Compression.**
  - **Links:** [arXiv 2609.19969](https://arxiv.org/abs/2609.19969) (2026-09-17); open weights on Hugging Face (MIT).
  - **What it is:** a multimodal MoE built for input-heavy agent workloads.
  - **Claims:**
    - 552B backbone, 1M context.
    - 16B active parameters in decode, 8B in prefill.
    - Global KV cache 890 bytes/token, about 1/4 of V4-Flash, using cross-layer KV reuse (CSA2) and an FP4 KV cache.
  - **Bedrock?** Partial: the savings belong to whoever serves the model.
- **DSec elastic sandbox compute for agentic RL.** [arXiv 2609.22978](https://arxiv.org/abs/2609.22978). Bedrock? No.
- **[AUG] DeepSeek Harness.** A plugin-based agent harness (MIT). MemOS added memory plugins on 2026-08-17.

### Alibaba (Tongyi, Qwen, Alibaba Cloud, Taobao) and Ant Group

- **REMORY.** [arXiv 2610.11287](https://arxiv.org/abs/2610.11287). Alibaba with SJTU, Fudan and CUHK.
  - **What it is:** soft "residual memory" tokens appended after a compaction summary.
  - **Claim:** near full-context score on SummHay using 5.2% of input positions.
  - **Bedrock?** No, but it shows a summary alone loses state needed later.
- **MemForest.** [arXiv 2609.08273](https://arxiv.org/abs/2609.08273).
  - **Claims:** under Mem0, 97.1% of performance kept with 50% of memory compressed, and 1.89× faster retrieval.
  - **Code:** released.
  - **Bedrock?** Yes.
- **EGMemory** (evidence-grounded, training-free). [arXiv 2609.23465](https://arxiv.org/abs/2609.23465).
  - **Claims:** GroupMemBench 68.2% (+22.7 pp), LoCoMo 73.6%.
  - **Bedrock?** Yes.
- **FlowState** (Ant Group): execution state as memory. [arXiv 2609.34565](https://arxiv.org/abs/2609.34565).
  - **Claims:** with DeepSeek-V4-Flash, +13.95 pp on τ³-Bench with 40–43% fewer tokens.
  - **Bedrock?** Yes.
- **Other Alibaba papers:**
  - [RPMem](https://arxiv.org/abs/2609.23466): parametric memory. Bedrock? No.
  - [MemCalib](https://arxiv.org/abs/2609.24259).
  - [T²Mem](https://arxiv.org/abs/2610.13348): code under OpenBMB/T2Mem, MIT.
  - [Socratic Skill Learning](https://arxiv.org/abs/2610.17860).
  - Belief states, [2610.01415](https://arxiv.org/abs/2610.01415).
  - [MemHarmBench](https://arxiv.org/abs/2611.01700) (with Fudan): cross-session prompt injection that persists in memory.
- **Repos with nothing in the window:** Tongyi DeepResearch / WebAgent (last README news 2025-09-20).

### Tencent (Hunyuan, Youtu, Yuanbao)

- **Hy-Memory-30B-A3B.** [arXiv 2610.22196](https://arxiv.org/abs/2610.22196) (2026-10-15); Apache-2.0 on Hugging Face.
  - **What it is:** an open memory-*writer* model for Mem0, MemOS and Hy-Memory.
  - **Claim:** macro average 55.49% vs Claude Opus 5 at 54.62%, including on a held-out harness.
  - **Bedrock?** Partial: it must be self-hosted, but it shows the choice of writer model matters.
- **CORAL: checkpoint-and-reset working-memory tools.** [arXiv 2610.40350](https://arxiv.org/abs/2610.40350) (2026-10-29).
  - **Claim:** 6–7× fewer input tokens than ReAct.
  - **Bedrock?** Yes for the tools; No for the RL training.
- **[AUG] ContextPilot.** [arXiv 2608.28476](https://arxiv.org/abs/2608.28476). Context-edit tools trained with RL. EMNLP 2026, per its README.
- **Other Tencent papers:**
  - [MemAgent](https://arxiv.org/abs/2609.32521) (with Tsinghua): routes among 13 memory methods.
  - [GroupAssistBench](https://arxiv.org/abs/2611.04867): the best memory system rivals full context on recall but falls far behind on use.
  - [Tool Graph Memory study](https://arxiv.org/abs/2610.21571): its gains cost more than twice the LLM calls.

### Meituan (LongCat)

- **NCE: context editing as special tokens.** [arXiv 2610.25550](https://arxiv.org/abs/2610.25550).
  - **Claims:** −36% tokens and +5.6 pp. Bedrock? No.
- **LongCat-DeepResearch** (sub-agents in separate contexts). [arXiv 2609.36071](https://arxiv.org/abs/2609.36071). Bedrock? Yes.
- **[MemScope](https://arxiv.org/abs/2610.21170)** and **[EvoGroup](https://arxiv.org/abs/2611.03868)** (EverMemBench 71.07% → 89.58%). Bedrock? Yes.

### ByteDance

- **Traverse** (BandAI with PKU). [arXiv 2609.37082](https://arxiv.org/abs/2609.37082).
  - **What it is:** a "Seal Memory" tool for active context management, trained with RL.
  - **Claims:** BrowseComp 72.83 with a 35B model. "Autonomous compression outperforms automatic compaction."
  - **Code:** Apache-2.0.
- **ByteDance Seed:** nothing in the window.

### Huawei, Xiaohongshu, Kuaishou, Baidu, StepFun, MiniMax, MemTensor

- **Huawei:**
  - [RefCon](https://arxiv.org/abs/2609.39143), [TallyMem](https://arxiv.org/abs/2610.19474): Bedrock? Yes.
  - [EfficientAgent](https://arxiv.org/abs/2609.33762) KV reuse: 93% fewer recomputed tokens. Bedrock? No.
  - openJiuwen agent-memory and X-Router: secondary sources only.
- **Xiaohongshu:** KV-reuse serving papers (RedKnot-MLA, CacheWeave). Bedrock? No.
- **Kuaishou:** [MM-ContextFold](https://arxiv.org/abs/2609.23121), training-free: +6.3 pp vs ReAct with 27.5% shorter context. Bedrock? Yes.
- **Baidu:** [RoLaQ](https://arxiv.org/abs/2610.20686), 2-bit MLA KV. Bedrock? No. ERNIE: nothing in the window.
- **StepFun:** [ECHOES](https://arxiv.org/abs/2610.22408) (with Tsinghua): recursive history compression for GUI agents.
- **MiniMax:** MiniMax-M3.1-Flash (Hugging Face, 2026-10-17): sparse attention, 1M context. No paper.
- **MemTensor:**
  - **MemT-1.0** (Apache-2.0): memory-native model; claims 66× less persistent storage than a full KV cache at 128K.
  - **[MemTrace](https://arxiv.org/abs/2610.04838)** (with SJTU): provenance-aware memory for coding agents. Bedrock? Yes.
- **Moonshot, Zhipu:** no paper in the window.

## Universities

### USTC

- **Compact-Bench.** [arXiv 2610.31710](https://arxiv.org/abs/2610.31710).
  - **Scope:** 35 SWE-bench repairs and 14 summarisers.
  - **Claims:**
    - Compaction damages 5–64% of tasks that full history solves.
    - LLM summaries keep at most **16.0%** of recurring details, against **79.1%** for mechanical extraction.
  - **Code and data:** released.
  - **Bedrock?** Yes.
- **[ActKV](https://arxiv.org/abs/2609.31395):** action-guided KV management. Bedrock? No.

### Tsinghua (often with Renmin University)

- **WorkBuddyBench compression series:**
  - [StateComp](https://arxiv.org/abs/2609.27298): −52.27% tokens.
  - [DRSR](https://arxiv.org/abs/2609.27276): −20.8% tokens.
  - GEM: −21.4%, training-free.
  - ICLR (a method name, not the venue): −25.5% input tokens, training-free.
- **[Cache Engineering for Agents (AKV)](https://arxiv.org/abs/2610.28577)** (with CUHK).
  - **Claim:** modifying the prefix invalidates the cached states after it; a rolling drop of old tool outputs gives +1.7 points at −27.7% cost.
- **[ContextPipe](https://arxiv.org/abs/2609.00749):** database-style context assembly.
  - **Claims:** −31% tokens and −23% LLM calls on a SWE-bench Pro subset.
- **[Memory Tax](https://arxiv.org/abs/2610.34073)** (with RUC): many memory systems underperform naive RAG.

### Peking University

- **[AttnCompress](https://arxiv.org/abs/2609.08318):** one of this project's four original papers. Claims −21.6% tokens and −33.6% cost.
- **[KVMem](https://arxiv.org/abs/2609.04852):** a 1M-token workspace on a 24 GB GPU.
- **[In-model soft-token compression](https://arxiv.org/abs/2610.41291)** (with SJTU).

### SJTU

- **[MemoryTax: The Bitter Lesson of Agent Memory](https://arxiv.org/abs/2610.29823):** a coding agent searching raw history reaches 99% at under half the full-context cost.
- **[CADOC](https://arxiv.org/abs/2609.37012).**
  - **What it is:** cache-aware batch replacement of large objects with retrievable "Cards".
  - **Claim:** about 40% lower input cost.
  - **Bedrock?** Yes.

### CUHK

- **[TraceLite](https://arxiv.org/abs/2610.28612).**
  - **What it is:** training-free trace reduction for SWE agents.
  - **Claims:** −33% tokens and −21% cost on SWE-bench Verified (78.25%).
  - **Bedrock?** Yes.
- **MemUse:** memory systems within 0.4 pp of no memory on 8,000 SWE-bench episodes.

### HKUST

- **[MemPrice](https://arxiv.org/abs/2610.24955):** memory allocation through adaptive pricing.
- **Chain on Demand:** LoCoMo 82.2%.
- **[LatentRemedy](https://arxiv.org/abs/2610.18014)** (with Microsoft): non-prefix KV reuse.

### Fudan

- **[ContextEvo](https://arxiv.org/abs/2609.34649):** self-evolving context-management policies. Starts from the Pi-agent harness; claims to match Codex, OpenCode and OpenClaw.
- **Memory-attack papers:** [2609.34132](https://arxiv.org/abs/2609.34132), and MemHarmBench with Alibaba.

### Shanghai AI Lab, BUPT and Zhejiang University

- **Shanghai AI Lab:** [RSI-Router](https://arxiv.org/abs/2609.34712): −74.7–82.2% cost on ALFWorld, ScienceWorld and WebShop. Bedrock? Yes.
- **BUPT:** MemoryOS repo has nothing new in the window. [SEPM](https://arxiv.org/abs/2610.14515): procedural memory.
- **Zhejiang University:** LightMem has nothing new in the window. EM²Mem (EMNLP 2026, per its README): −63.66% tokens.

## What the Chinese community is discussing (量子位)

1. Harnesses with plugins: DeepSeek Harness, Kimi recording Skills from browsing.
2. "White-box" memory with offline "dreaming" consolidation: PilotDeck 2.0 (OpenBMB), Huawei MindMemOS.
3. Model routing to save tokens ("token factory" framing).
4. KV cache as the cost centre of agent serving: DeepSeek's 890 B/token.
5. Memory-native models: MemT-1.0.
6. Growing scepticism that elaborate memory beats raw history plus search: Memory Tax, MemoryTax, MemUse.

## Top 5

1. **DeepSeek-V4.1-Flash:** architecture for input-heavy agents, with open weights.
2. **Tencent Hy-Memory-30B-A3B:** the first open specialised memory-writer model.
3. **USTC Compact-Bench:** measures what compaction destroys, and is directly actionable.
4. **Tsinghua/CUHK AKV with the Tsinghua/RUC compression series:** cache-preserving drops beat summarisation, and training-free variants exist.
5. **Tencent CORAL and Ant FlowState:** checkpoint and reset, and pointers to raw observations, both working with API models.
