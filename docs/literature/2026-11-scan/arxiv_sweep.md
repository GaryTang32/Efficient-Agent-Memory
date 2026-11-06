# arXiv sweep: agent memory and context / token efficiency, 2026-09-01 to 2026-11-04

Generated 2026-11-04 by the scripts next to this file:
- `sweep.py` queries the arXiv API.
- `html_affil.py` reads affiliations from the arXiv HTML author block.
- `classify.py` tags organisations by regex.

**Counts**
- Papers matched by the keyword queries: 1,515.
- Focused on memory, context or token efficiency for agents: 799.
- Selected as highly relevant (title/abstract score ≥ 4): 369.
- Among the selected: **148 (40%) have a Chinese lab, company or university author**, and **34 (9%) a big US lab or company author**.

**Caveats.** Affiliations come from regex matching on the arXiv HTML author block; 19 papers had no HTML author block, and some tags may be wrong. Paper claims below are the authors' own (abstracts), not reproduced.

## Organisations among the selected papers

| organisation | papers |
|---|---|
| Tsinghua | 24 |
| SJTU | 21 |
| HKUST | 18 |
| Alibaba/Qwen/Tongyi | 17 |
| Fudan | 16 |
| Peking U | 14 |
| CUHK | 12 |
| USTC | 10 |
| CAS | 10 |
| Microsoft | 9 |
| Renmin U | 9 |
| Huawei | 9 |
| HKU | 9 |
| Zhejiang U | 9 |
| Nanjing U | 8 |
| Amazon/AWS | 8 |
| Shanghai AI Lab | 8 |
| HIT | 7 |
| Beihang | 6 |
| Meituan | 5 |
| Tencent | 5 |
| Meta | 5 |
| IBM | 4 |
| NVIDIA | 4 |
| SYSU | 3 |
| JD | 3 |
| Southern U S&T | 3 |
| BUPT | 3 |
| Wuhan U | 3 |
| Xiamen U | 3 |

## Themes among the selected papers (a paper can have several)

| theme | papers |
|---|---|
| memory benchmark / evaluation | 268 |
| token / cost efficiency, caching | 244 |
| context compaction / folding / summarisation | 151 |
| experience / skill / procedural memory, self-evolving | 111 |
| memory architecture / memory OS / graph memory | 82 |
| memory security / privacy / poisoning | 49 |
| RL-trained memory management | 48 |
| multi-agent shared memory | 45 |

## Most relevant papers (score ≥ 6)

| arXiv | date | title | organisations |
|---|---|---|---|
| [2610.07863v1](https://arxiv.org/abs/2610.07863v1) | 2026-10-06 | ReFold: Training-Free Reversible Inter-Turn Context Folding for Long-Horizon Agents | Intel |
| [2609.40118v1](https://arxiv.org/abs/2609.40118v1) | 2026-09-30 | Persistent Context Graphs for Efficient Memory Compaction in LLM Agents | Microsoft |
| [2610.41291v1](https://arxiv.org/abs/2610.41291v1) | 2026-10-30 | In-Model Context Compression with Agentic Soft Tokens for Long-Horizon LLM Agents | Peking U, SJTU |
| [2609.07471v1](https://arxiv.org/abs/2609.07471v1) | 2026-09-07 | MEMO: Multimodal Evidence Memory Organization for Long-Horizon LLM Agents | — |
| [2609.25537v1](https://arxiv.org/abs/2609.25537v1) | 2026-09-22 | Compressing Long Context into Answer-Aligned Memory Embeddings for LLM Inference | — |
| [2609.27286v1](https://arxiv.org/abs/2609.27286v1) | 2026-09-23 | Memory Control Signals Emerge Before Action in Long Horizon Agents | Tsinghua, Renmin U |
| [2609.27298v1](https://arxiv.org/abs/2609.27298v1) | 2026-09-23 | StateComp: Learning When to Compress History in Long Horizon Agents | Tsinghua, Renmin U |
| [2609.27332v1](https://arxiv.org/abs/2609.27332v1) | 2026-09-23 | Stable Geometry with Divergent Task Evidence for Efficient Long-Horizon Agent Compression | Tsinghua, Renmin U |
| [2609.34565v2](https://arxiv.org/abs/2609.34565v2) | 2026-09-28 | FlowState: Execution State as Memory for Long-Horizon LLM Agents | Alibaba/Qwen/Tongyi |
| [2609.36526v1](https://arxiv.org/abs/2609.36526v1) | 2026-09-29 | Adapting Context Compression for Long-Horizon Agents with Counterfactual Continuations | — |
| [2610.01415v1](https://arxiv.org/abs/2610.01415v1) | 2026-10-01 | Beyond Memory: Harnessing Long-Horizon Agents with Explicit Belief States | Alibaba/Qwen/Tongyi, Tsinghua |
| [2610.04838v3](https://arxiv.org/abs/2610.04838v3) | 2026-10-04 | MemTrace: State-Consistent Memory for Long-Horizon Coding Agents | MemTensor, SJTU |
| [2610.07118v1](https://arxiv.org/abs/2610.07118v1) | 2026-10-05 | AMBER: Training Long-Horizon Web Agents through Append-Only Memory | — |
| [2610.20927v1](https://arxiv.org/abs/2610.20927v1) | 2026-10-14 | Prune the Summary, Not the History: Source-Judged Compaction for Long-Horizon Agents | — |
| [2610.21165v1](https://arxiv.org/abs/2610.21165v1) | 2026-10-15 | From Long Context to Selective Memory:A Survey of Memory-Centric Compression for Large Language Models | — |
| [2610.24955v1](https://arxiv.org/abs/2610.24955v1) | 2026-10-18 | MemPrice: Online Memory Allocation via Adaptive Pricing for Long-Horizon Agents | HKUST |
| [2610.31710v2](https://arxiv.org/abs/2610.31710v2) | 2026-10-22 | Compact-Bench: Measuring What Context Compaction Costs Long-Horizon Coding Agents | USTC |
| [2611.01858v1](https://arxiv.org/abs/2611.01858v1) | 2026-11-01 | Learning-to-Memorize: Dynamic Context Management for Long-Horizon Autoregressive Video Generation | ByteDance, Tsinghua |
| [2609.04802v3](https://arxiv.org/abs/2609.04802v3) | 2026-09-04 | Linguistic Trajectory Encoding for Efficient Long-Horizon Spatial Memory in Embodied Agents | Huawei, Nanjing U, Tianjin U |
| [2609.19969v1](https://arxiv.org/abs/2609.19969v1) | 2026-09-17 | DeepSeek-V4.1-Flash: Pushing the Limits of KV Cache Compression | DeepSeek |
| [2609.23465v2](https://arxiv.org/abs/2609.23465v2) | 2026-09-20 | Propose, Verify, Commit: Evidence-Grounded Memory for Long-Horizon Multi-Actor Conversations | Alibaba/Qwen/Tongyi |
| [2609.26779v1](https://arxiv.org/abs/2609.26779v1) | 2026-09-22 | CliffCompaction: Cost-Efficient Compaction for Long-Horizon Coding Agents | — |
| [2609.32256v1](https://arxiv.org/abs/2609.32256v1) | 2026-09-26 | LAM: Efficient Lossy Agent Memory Framework With A Retrieval-Score Error Bound | IBM |
| [2609.32852v1](https://arxiv.org/abs/2609.32852v1) | 2026-09-26 | ARSM: Auto-Regressive State Machine for Agentic Reasoning Compression | Fudan |
| [2609.33717v1](https://arxiv.org/abs/2609.33717v1) | 2026-09-27 | Self-Designed Evaluators and Warm Memory for Long-Horizon Agents | — |
| [2609.37082v2](https://arxiv.org/abs/2609.37082v2) | 2026-09-29 | Traverse: Learning When to Remember, Reset, and Redirect for Long-Horizon Web Search | ByteDance, Peking U |
| [2610.00042v1](https://arxiv.org/abs/2610.00042v1) | 2026-09-03 | Zengram-Lite: An In-Browser Agentic-Memory Framework - Semantic Knowledge, Session Tracking, and Token-Budgeted Context | — |
| [2610.02815v1](https://arxiv.org/abs/2610.02815v1) | 2026-10-02 | iS-KV: Online Low-Rank KV Cache Compression via Block-Incremental SVD | CAS, HKUST |
| [2610.11287v3](https://arxiv.org/abs/2610.11287v3) | 2026-10-08 | REMORY: Learning Residual Memory for Context Compaction | Alibaba/Qwen/Tongyi, SJTU, Fudan, Nanjing U |
| [2610.12874v1](https://arxiv.org/abs/2610.12874v1) | 2026-10-09 | Temporal Evidence Forests for Long-Horizon Multi-Party Conversational Memory | Alibaba/Qwen/Tongyi, Beihang |
| [2610.20959v2](https://arxiv.org/abs/2610.20959v2) | 2026-10-14 | Same Context, Different Agents: A Behavioral Study of Semantic Layers, Multi-Agent Orchestration and Memory Compaction in Data Agents | — |
| [2610.22686v2](https://arxiv.org/abs/2610.22686v2) | 2026-10-15 | Multimodal Filesystem Memory For Long-Horizon Embodied Agents | — |
| [2610.29869v1](https://arxiv.org/abs/2610.29869v1) | 2026-10-21 | Compaction Laundering: Provenance Destruction in Context-Compacting Coding Agents | — |
| [2610.34251v1](https://arxiv.org/abs/2610.34251v1) | 2026-10-25 | Variational Cognitive Memory Abstraction for Long-Horizon Vision-Language-Action Models | — |
| [2610.34335v1](https://arxiv.org/abs/2610.34335v1) | 2026-10-25 | CoLink: Global Compression and Knowledge Linking for Multi-Turn Dialogue Modeling | HIT |
| [2610.36153v1](https://arxiv.org/abs/2610.36153v1) | 2026-10-26 | Stratum: Repository Memory for Coding Agents Beyond the Context Window | — |
| [2609.00749v1](https://arxiv.org/abs/2609.00749v1) | 2026-09-01 | ContextPipe: Database-Inspired Context Assembly for Long-Horizon Agents | Tsinghua |
| [2609.02074v1](https://arxiv.org/abs/2609.02074v1) | 2026-09-02 | CHIME: Credit-Aware Hierarchical Memory Evolution for Long-Horizon Agentic Planning | — |
| [2609.04915v1](https://arxiv.org/abs/2609.04915v1) | 2026-09-04 | Compact-Memory LLM Agents via Online Max-Member Clustering and Atom-Aware Packing | — |
| [2609.08318v1](https://arxiv.org/abs/2609.08318v1) | 2026-09-08 | AttnCompress: Dynamic Attention-Guided Trajectory Compression for Software Engineering Agents | Peking U |
| [2609.08566v1](https://arxiv.org/abs/2609.08566v1) | 2026-09-08 | BIO-MEMART: Biometric-Aware KV Cache Memory for Multi-User LLM Agents | — |
| [2609.11192v1](https://arxiv.org/abs/2609.11192v1) | 2026-09-10 | FlexComp: One Model for Every Ratio in Context Compression | — |
| [2609.17969v1](https://arxiv.org/abs/2609.17969v1) | 2026-09-16 | Memory Has Geometry: Non-Uniform Geometric Memory for Long-Horizon Personalized AI | HKUST, CUHK |
| [2609.19519v1](https://arxiv.org/abs/2609.19519v1) | 2026-09-17 | An Architecture for Long-Horizon Agents: Levels, Ticks and Cascaded Intelligence | Salesforce |
| [2609.23790v1](https://arxiv.org/abs/2609.23790v1) | 2026-09-20 | Total Cost of Agency: Exact Attribution of Memory Injection Cost in Multi-Agent LLM Workflows | — |
| [2609.25913v3](https://arxiv.org/abs/2609.25913v3) | 2026-09-22 | When Does Execution Provenance Help Agent Memory Retrieval? | Nanjing U, Southern U S&T |
| [2609.30797v1](https://arxiv.org/abs/2609.30797v1) | 2026-09-25 | HasMem: Hard-Origin Adaptively Softened Memory for Long-Term LLM Agents | — |
| [2609.31395v1](https://arxiv.org/abs/2609.31395v1) | 2026-09-25 | ActKV: Efficient LLM Agents through Action-Guided KV Cache Management | USTC |
| [2609.32297v1](https://arxiv.org/abs/2609.32297v1) | 2026-09-26 | Agentsensus: Consensus-Compressed Shared Memory for Multi-Agent Story Worlds | — |
| [2609.34054v2](https://arxiv.org/abs/2609.34054v2) | 2026-09-28 | PReCache: Efficient KV Cache Sharing for Multi-LoRA Agents via Low-Rank Precomputation and Neutral Reconstruction | — |
| [2609.34422v2](https://arxiv.org/abs/2609.34422v2) | 2026-09-28 | Coding Agent Memory Post-training: Unlocking the Memory Potential of Pre-trained File Operations for Long-Horizon Tasks via Reinforcement Learning | JD |
| [2609.34649v1](https://arxiv.org/abs/2609.34649v1) | 2026-09-28 | Beyond Skill Evolution: Self-Evolving Context Management Policies for Long-Horizon Agent Harnesses | Fudan |
| [2609.35540v1](https://arxiv.org/abs/2609.35540v1) | 2026-09-28 | Continuous Context Management | — |
| [2609.35750v3](https://arxiv.org/abs/2609.35750v3) | 2026-09-28 | KV-streams for Efficient Compaction in Agentic Reinforcement Learning | Microsoft |
| [2609.37012v1](https://arxiv.org/abs/2609.37012v1) | 2026-09-29 | CADOC: Cache-Aware Dynamic Object Context for Long-Horizon Agents | SJTU |
| [2609.37017v1](https://arxiv.org/abs/2609.37017v1) | 2026-09-29 | LatCom: Cross-Agent Latent Compression for Efficient Multi-Agent Collaboration | USTC |
| [2609.37590v1](https://arxiv.org/abs/2609.37590v1) | 2026-09-29 | FOCUS: Training-Free Decision-Preserving Context Compression for LLM Agents | Microsoft |
| [2609.38641v1](https://arxiv.org/abs/2609.38641v1) | 2026-09-29 | Vision-Language-Action Autonomous Driving Agent with Language-based Memory | NVIDIA |
| [2609.39915v1](https://arxiv.org/abs/2609.39915v1) | 2026-09-30 | NavHarness: Adaptive Goals for Agentic Vision-Language Navigation | HIT |
| [2610.02163v1](https://arxiv.org/abs/2610.02163v1) | 2026-10-01 | AutoCompact: Learning When to Compact Context in Long-Horizon Coding Agents | — |
| [2610.02687v2](https://arxiv.org/abs/2610.02687v2) | 2026-10-02 | Decoupling Memory from Context: Structured Memory for Token-Efficient Test-Time Continual Learning | IBM |
| [2610.06927v1](https://arxiv.org/abs/2610.06927v1) | 2026-10-03 | AttSVD:Prompt-Adaptive Low-Rank KV Cache Compression via Attention-Guided SVD | Microsoft |
| [2610.07625v1](https://arxiv.org/abs/2610.07625v1) | 2026-10-06 | Stateless Language Agents: Scaling Long-Horizon Automated Research | — |
| [2610.18784v2](https://arxiv.org/abs/2610.18784v2) | 2026-10-13 | Pack Light, CarryOn: Building Object-Oriented Context for Long-Horizon Agents | — |
| [2610.19376v1](https://arxiv.org/abs/2610.19376v1) | 2026-10-14 | DeLoop: Repeated Actions as Self-Supervision for Long-Horizon Agents | — |
| [2610.21073v1](https://arxiv.org/abs/2610.21073v1) | 2026-10-15 | Skip the Compressor: Coding Agents Fix More Issues When They Pick Whole Files | — |
| [2610.21126v1](https://arxiv.org/abs/2610.21126v1) | 2026-10-15 | Compression Does Not End at Selection: Post-Selection Positional Geometry for Sparse KV Caches | — |
| [2610.21170v1](https://arxiv.org/abs/2610.21170v1) | 2026-10-15 | MemScope: Evolving Agent Memory Architectures through Localized Code Repair | Meituan, CAS |
| [2610.22408v1](https://arxiv.org/abs/2610.22408v1) | 2026-10-14 | ECHOES: Seeing Beyond the Current Image via Recursive History Compression and Privileged On-Policy Distillation | StepFun, Tsinghua |
| [2610.23598v1](https://arxiv.org/abs/2610.23598v1) | 2026-10-16 | RL-Guided Temporal Localization for Dual-Channel Retrieval in Long-Horizon Agent Memory | Tsinghua |
| [2610.23892v1](https://arxiv.org/abs/2610.23892v1) | 2026-09-28 | EMMA: Event-Driven Multimodal Memory System with Multi-Agent Retrieval | Huawei, BUPT |
| [2610.25516v1](https://arxiv.org/abs/2610.25516v1) | 2026-10-18 | Bud ContextCompact 2.0: Context Compaction for Agent Success and Accuracy with Small Language Models and Constrained Context Windows | — |
| [2610.25561v1](https://arxiv.org/abs/2610.25561v1) | 2026-10-18 | Let Them Sleep: Recursive Self-Pruning Memory for Long-Horizon LLM Agents | — |
| [2610.27032v1](https://arxiv.org/abs/2610.27032v1) | 2026-10-19 | M-Plan: Comprehensive Planning For LLM Agents with Memory Arrangement | Fudan |
| [2610.29671v1](https://arxiv.org/abs/2610.29671v1) | 2026-10-21 | Uni-Mem: Learning a Long-Horizon Agentic Memory Manager with Unified Online Policy Optimization | Huawei, SYSU |
| [2610.31778v1](https://arxiv.org/abs/2610.31778v1) | 2026-10-22 | Benchmarks Are Surprisingly Compaction-Friendly | — |
| [2610.35066v2](https://arxiv.org/abs/2610.35066v2) | 2026-10-26 | MemVLN: Streaming Episodic Memory for Vision-Language Navigation | Peking U |
| [2610.35349v1](https://arxiv.org/abs/2610.35349v1) | 2026-10-26 | MarkovSim: an LLM Agent Harness with Bounded Context for Long-Horizon Computational Simulation | — |
| [2610.35801v1](https://arxiv.org/abs/2610.35801v1) | 2026-10-26 | FOCUS: Active Critic Learning for Long-Horizon Language Model Agents | — |
| [2610.38980v1](https://arxiv.org/abs/2610.38980v1) | 2026-10-28 | Context Compaction for World Models | — |
| [2611.03005v1](https://arxiv.org/abs/2611.03005v1) | 2026-11-02 | BLPO: Beyond-Local Policy Optimization for Long-Horizon LLM Agents | Alibaba/Qwen/Tongyi, Beihang |

## Chinese-affiliated papers (all selected)

| arXiv | date | title | organisations |
|---|---|---|---|
| [2610.41291v1](https://arxiv.org/abs/2610.41291v1) | 2026-10-30 | In-Model Context Compression with Agentic Soft Tokens for Long-Horizon LLM Agents | Peking U, SJTU |
| [2609.27286v1](https://arxiv.org/abs/2609.27286v1) | 2026-09-23 | Memory Control Signals Emerge Before Action in Long Horizon Agents | Tsinghua, Renmin U |
| [2609.27298v1](https://arxiv.org/abs/2609.27298v1) | 2026-09-23 | StateComp: Learning When to Compress History in Long Horizon Agents | Tsinghua, Renmin U |
| [2609.27332v1](https://arxiv.org/abs/2609.27332v1) | 2026-09-23 | Stable Geometry with Divergent Task Evidence for Efficient Long-Horizon Agent Compression | Tsinghua, Renmin U |
| [2609.34565v2](https://arxiv.org/abs/2609.34565v2) | 2026-09-28 | FlowState: Execution State as Memory for Long-Horizon LLM Agents | Alibaba/Qwen/Tongyi |
| [2610.01415v1](https://arxiv.org/abs/2610.01415v1) | 2026-10-01 | Beyond Memory: Harnessing Long-Horizon Agents with Explicit Belief States | Alibaba/Qwen/Tongyi, Tsinghua |
| [2610.04838v3](https://arxiv.org/abs/2610.04838v3) | 2026-10-04 | MemTrace: State-Consistent Memory for Long-Horizon Coding Agents | MemTensor, SJTU |
| [2610.24955v1](https://arxiv.org/abs/2610.24955v1) | 2026-10-18 | MemPrice: Online Memory Allocation via Adaptive Pricing for Long-Horizon Agents | HKUST |
| [2610.31710v2](https://arxiv.org/abs/2610.31710v2) | 2026-10-22 | Compact-Bench: Measuring What Context Compaction Costs Long-Horizon Coding Agents | USTC |
| [2611.01858v1](https://arxiv.org/abs/2611.01858v1) | 2026-11-01 | Learning-to-Memorize: Dynamic Context Management for Long-Horizon Autoregressive Video Generation | ByteDance, Tsinghua |
| [2609.04802v3](https://arxiv.org/abs/2609.04802v3) | 2026-09-04 | Linguistic Trajectory Encoding for Efficient Long-Horizon Spatial Memory in Embodied Agents | Huawei, Nanjing U, Tianjin U |
| [2609.19969v1](https://arxiv.org/abs/2609.19969v1) | 2026-09-17 | DeepSeek-V4.1-Flash: Pushing the Limits of KV Cache Compression | DeepSeek |
| [2609.23465v2](https://arxiv.org/abs/2609.23465v2) | 2026-09-20 | Propose, Verify, Commit: Evidence-Grounded Memory for Long-Horizon Multi-Actor Conversations | Alibaba/Qwen/Tongyi |
| [2609.32852v1](https://arxiv.org/abs/2609.32852v1) | 2026-09-26 | ARSM: Auto-Regressive State Machine for Agentic Reasoning Compression | Fudan |
| [2609.37082v2](https://arxiv.org/abs/2609.37082v2) | 2026-09-29 | Traverse: Learning When to Remember, Reset, and Redirect for Long-Horizon Web Search | ByteDance, Peking U |
| [2610.02815v1](https://arxiv.org/abs/2610.02815v1) | 2026-10-02 | iS-KV: Online Low-Rank KV Cache Compression via Block-Incremental SVD | CAS, HKUST |
| [2610.11287v3](https://arxiv.org/abs/2610.11287v3) | 2026-10-08 | REMORY: Learning Residual Memory for Context Compaction | Alibaba/Qwen/Tongyi, SJTU, Fudan, Nanjing U |
| [2610.12874v1](https://arxiv.org/abs/2610.12874v1) | 2026-10-09 | Temporal Evidence Forests for Long-Horizon Multi-Party Conversational Memory | Alibaba/Qwen/Tongyi, Beihang |
| [2610.34335v1](https://arxiv.org/abs/2610.34335v1) | 2026-10-25 | CoLink: Global Compression and Knowledge Linking for Multi-Turn Dialogue Modeling | HIT |
| [2609.00749v1](https://arxiv.org/abs/2609.00749v1) | 2026-09-01 | ContextPipe: Database-Inspired Context Assembly for Long-Horizon Agents | Tsinghua |
| [2609.08318v1](https://arxiv.org/abs/2609.08318v1) | 2026-09-08 | AttnCompress: Dynamic Attention-Guided Trajectory Compression for Software Engineering Agents | Peking U |
| [2609.17969v1](https://arxiv.org/abs/2609.17969v1) | 2026-09-16 | Memory Has Geometry: Non-Uniform Geometric Memory for Long-Horizon Personalized AI | HKUST, CUHK |
| [2609.25913v3](https://arxiv.org/abs/2609.25913v3) | 2026-09-22 | When Does Execution Provenance Help Agent Memory Retrieval? | Nanjing U, Southern U S&T |
| [2609.31395v1](https://arxiv.org/abs/2609.31395v1) | 2026-09-25 | ActKV: Efficient LLM Agents through Action-Guided KV Cache Management | USTC |
| [2609.34422v2](https://arxiv.org/abs/2609.34422v2) | 2026-09-28 | Coding Agent Memory Post-training: Unlocking the Memory Potential of Pre-trained File Operations for Long-Horizon Tasks via Reinforcement Learning | JD |
| [2609.34649v1](https://arxiv.org/abs/2609.34649v1) | 2026-09-28 | Beyond Skill Evolution: Self-Evolving Context Management Policies for Long-Horizon Agent Harnesses | Fudan |
| [2609.37012v1](https://arxiv.org/abs/2609.37012v1) | 2026-09-29 | CADOC: Cache-Aware Dynamic Object Context for Long-Horizon Agents | SJTU |
| [2609.37017v1](https://arxiv.org/abs/2609.37017v1) | 2026-09-29 | LatCom: Cross-Agent Latent Compression for Efficient Multi-Agent Collaboration | USTC |
| [2609.39915v1](https://arxiv.org/abs/2609.39915v1) | 2026-09-30 | NavHarness: Adaptive Goals for Agentic Vision-Language Navigation | HIT |
| [2610.21170v1](https://arxiv.org/abs/2610.21170v1) | 2026-10-15 | MemScope: Evolving Agent Memory Architectures through Localized Code Repair | Meituan, CAS |
| [2610.22408v1](https://arxiv.org/abs/2610.22408v1) | 2026-10-14 | ECHOES: Seeing Beyond the Current Image via Recursive History Compression and Privileged On-Policy Distillation | StepFun, Tsinghua |
| [2610.23598v1](https://arxiv.org/abs/2610.23598v1) | 2026-10-16 | RL-Guided Temporal Localization for Dual-Channel Retrieval in Long-Horizon Agent Memory | Tsinghua |
| [2610.23892v1](https://arxiv.org/abs/2610.23892v1) | 2026-09-28 | EMMA: Event-Driven Multimodal Memory System with Multi-Agent Retrieval | Huawei, BUPT |
| [2610.27032v1](https://arxiv.org/abs/2610.27032v1) | 2026-10-19 | M-Plan: Comprehensive Planning For LLM Agents with Memory Arrangement | Fudan |
| [2610.29671v1](https://arxiv.org/abs/2610.29671v1) | 2026-10-21 | Uni-Mem: Learning a Long-Horizon Agentic Memory Manager with Unified Online Policy Optimization | Huawei, SYSU |
| [2610.35066v2](https://arxiv.org/abs/2610.35066v2) | 2026-10-26 | MemVLN: Streaming Episodic Memory for Vision-Language Navigation | Peking U |
| [2611.03005v1](https://arxiv.org/abs/2611.03005v1) | 2026-11-02 | BLPO: Beyond-Local Policy Optimization for Long-Horizon LLM Agents | Alibaba/Qwen/Tongyi, Beihang |
| [2609.04438v3](https://arxiv.org/abs/2609.04438v3) | 2026-09-03 | ICM-Bench: Person-Level Identity Reasoning in Multimodal Agents with Long-Term Memory | Tsinghua |
| [2609.04852v1](https://arxiv.org/abs/2609.04852v1) | 2026-09-04 | KVMem: Virtualizing Million-Token Agent Workspaces on a Consumer GPU | Peking U |
| [2609.06504v1](https://arxiv.org/abs/2609.06504v1) | 2026-09-06 | CAM: Question Answering on Entity-Centric Videos with Continuous Extraction and Adaptive Querying | Wuhan U, CUHK |
| [2609.07344v2](https://arxiv.org/abs/2609.07344v2) | 2026-09-07 | Staying on the Attack Path: Structured State for Long-Horizon Automated Penetration Testing | Tianjin U |
| [2609.08273v2](https://arxiv.org/abs/2609.08273v2) | 2026-09-08 | MemForest: Efficient Agent Memory Management via EventTree Partitioning and Progressive Merging | Alibaba/Qwen/Tongyi, Tsinghua, SJTU, Fudan |
| [2609.20301v1](https://arxiv.org/abs/2609.20301v1) | 2026-09-14 | AgentPProf: Semantic Profiler for Long Horizon AI Agents | Alibaba/Qwen/Tongyi, HKUST |
| [2609.23466v2](https://arxiv.org/abs/2609.23466v2) | 2026-09-20 | RPMem: Learning Long-Term Recurrent Parametric Memory Across Sessions for LLM Agents | Alibaba/Qwen/Tongyi, Fudan |
| [2609.25611v1](https://arxiv.org/abs/2609.25611v1) | 2026-09-22 | Qwen3.8-Omni: Towards Native Omni-Modal Agents | Alibaba/Qwen/Tongyi |
| [2609.27276v1](https://arxiv.org/abs/2609.27276v1) | 2026-09-23 | DRSR: Learning Set-Level Deletion Risk for Efficient Long-Horizon Agents | Tsinghua, Renmin U |
| [2609.28466v1](https://arxiv.org/abs/2609.28466v1) | 2026-09-23 | The Past Frames the Future: Memory for Autoregressive Video Generation | NVIDIA, Peking U, HKUST |
| [2609.31430v1](https://arxiv.org/abs/2609.31430v1) | 2026-09-25 | Compress What You See, Not What You Say: Anchored Context Distillation for Latent-Observation Software Engineering Agents | Peking U |
| [2609.31507v1](https://arxiv.org/abs/2609.31507v1) | 2026-09-25 | SatNav: A Scalable Benchmark for Long-Horizon UAV Vision-Language Navigation from Satellite Imagery | HKUST |
| [2609.31995v1](https://arxiv.org/abs/2609.31995v1) | 2026-09-25 | Before the Rollout Ends: Early Terminal Reward Prediction for Long-horizon Coding Agents | HKUST |
| [2609.32511v1](https://arxiv.org/abs/2609.32511v1) | 2026-09-26 | Learning from Others, Acting for You: Cross-User Memory Sharing for LLM Agents | SJTU, Shanghai AI Lab |
| [2609.32521v1](https://arxiv.org/abs/2609.32521v1) | 2026-09-26 | MemAgent: Learning to Manage Heterogeneous Memory Providers for LLM Agents | Tencent, Tsinghua |
| [2609.32689v1](https://arxiv.org/abs/2609.32689v1) | 2026-09-26 | Self-Evolving Time-Series Forecasting Agents with Episodic Memory and Online Policy Learning | Tsinghua, SJTU, Shanghai AI Lab |
| [2609.34132v1](https://arxiv.org/abs/2609.34132v1) | 2026-09-28 | From Attack Success to Attack Severity: Counterfactual Memory Attacks on LLM Agents | Fudan |
| [2609.35333v1](https://arxiv.org/abs/2609.35333v1) | 2026-09-28 | Scalable In-Context Reinforcement Learning with Recurrent Algorithm Distillation | CUHK |
| [2609.39384v1](https://arxiv.org/abs/2609.39384v1) | 2026-09-30 | RoboAssist: Interactive Human-Humanoid Planning for Long-Horizon Surgical Assistance | Zhejiang U |
| [2610.03020v1](https://arxiv.org/abs/2610.03020v1) | 2026-10-02 | DyadMem: A Long-Term Memory Benchmark of How Agents Work with Users | HKU |
| [2610.13494v1](https://arxiv.org/abs/2610.13494v1) | 2026-10-09 | Humanize MLE Agents: Multi-Agent Session Alternation Beyond Single-Agent Limits | NVIDIA, Tsinghua, Zhejiang U |
| [2610.14515v1](https://arxiv.org/abs/2610.14515v1) | 2026-10-10 | SEPM: Self-Evolving Procedural Memory Grounded in Task Graphs for Multi-Agent Collaboration | BUPT |
| [2610.16118v1](https://arxiv.org/abs/2610.16118v1) | 2026-10-12 | Elephant in the Fridge: Constant-Memory Frame Packing for Long Video Understanding | Renmin U |
| [2610.16998v1](https://arxiv.org/abs/2610.16998v1) | 2026-10-12 | Glasseek: A Transparent Recipe for Training and Trustworthy Evaluation of DeepSearch Agents | SenseTime, Peking U, CAS, HKUST |
| [2610.17970v1](https://arxiv.org/abs/2610.17970v1) | 2026-10-13 | AlignPred: Error-Controlled KV Cache Compression via Alignment and Predictive Coding | Tencent |
| [2610.20786v1](https://arxiv.org/abs/2610.20786v1) | 2026-10-14 | EvolvingBrain: An Adaptive Skill System for Multi-modal Agents Self-Evolution in Open Worlds | Meituan, HIT |
| [2610.21405v1](https://arxiv.org/abs/2610.21405v1) | 2026-10-15 | MemCut: Every Secret Leaves a Trail in the Long-Term Memory of LLM Agents | USTC, HKUST |
| [2610.21893v1](https://arxiv.org/abs/2610.21893v1) | 2026-10-15 | GACC-Bench: Benchmarking Goal-Adaptive Context Compression Ability across Large Language Models | JD, Fudan, HIT, CAS |
| [2610.23104v1](https://arxiv.org/abs/2610.23104v1) | 2026-10-16 | WebCoder: Scaling General Frontend Development with Artifact-Grounded Agentic Reinforcement Learning | Zhipu/Z.ai, Tsinghua, Beihang |
| [2610.23950v1](https://arxiv.org/abs/2610.23950v1) | 2026-10-09 | Compaction-Aware Reinforcement Learning For Ascend Triton Kernel Generation | Huawei |
| [2610.27435v1](https://arxiv.org/abs/2610.27435v1) | 2026-10-20 | Harness Self-Evolution for Long-Horizon Terminal Agents | Tencent |
| [2610.27861v1](https://arxiv.org/abs/2610.27861v1) | 2026-10-20 | RoboCasa-Shift: Stage-Aware Robustness Evaluation of Vision-Language-Action Policies in Long-Horizon Household Manipulation | SJTU, Fudan, CAS, CUHK |
| [2610.28577v1](https://arxiv.org/abs/2610.28577v1) | 2026-10-20 | Cache Engineering for Agents | Tsinghua, CUHK |
| [2610.28612v1](https://arxiv.org/abs/2610.28612v1) | 2026-10-20 | TraceLite: Efficient Trace Reduction for SWE Agents via Optical Compression and Redundancy Removal | HIT, CUHK |
| [2610.29995v1](https://arxiv.org/abs/2610.29995v1) | 2026-10-21 | Remembering Through Change: Provenance-Preserving Hypergraph Memory for Multimodal Agents | Huawei, SYSU |
| [2610.32373v1](https://arxiv.org/abs/2610.32373v1) | 2026-10-23 | Past as State, Present as Attention: Persistent-State Blockwise Flow Matching for Long-Horizon Co-Speech Motion Generation | Alibaba/Qwen/Tongyi |
| [2610.33015v1](https://arxiv.org/abs/2610.33015v1) | 2026-10-08 | SLICE-Mem: Salience-Gated Lightweight Information Curation for Efficient LLM Agent Memory | Xiaomi |
| [2610.34673v1](https://arxiv.org/abs/2610.34673v1) | 2026-10-26 | Agent Memory as Recommendation: Recommender-System Design for Long-Term Memory of LLM Agents | Fudan |
| [2610.34977v1](https://arxiv.org/abs/2610.34977v1) | 2026-10-26 | Adaptive Memory Index Evolution for Agents | Meituan |
| [2610.37224v1](https://arxiv.org/abs/2610.37224v1) | 2026-10-27 | Spine: Compiling Subtask Trees into Structured Context for Long-Horizon Coding Agents | Southern U S&T |
| [2610.38902v1](https://arxiv.org/abs/2610.38902v1) | 2026-10-28 | HEDGE: Gated Hypergraph Memory for Scalable Multi-Agent Debate | Huawei |
| [2610.39812v2](https://arxiv.org/abs/2610.39812v2) | 2026-10-29 | GROME: GROunding Factorized MEmory into Video World Models | Fudan, Shanghai AI Lab, Beihang, CUHK |
| [2611.00988v1](https://arxiv.org/abs/2611.00988v1) | 2026-10-31 | Pulse: Long-Horizon Tasks Need Streaming Personalization | Nanjing U |
| [2611.04894v1](https://arxiv.org/abs/2611.04894v1) | 2026-11-03 | VisSearch-Bench: Evaluating Long Horizon Visual Search in Multimodal Agents | Alibaba/Qwen/Tongyi, Tsinghua, Renmin U |
| [2609.08550v1](https://arxiv.org/abs/2609.08550v1) | 2026-09-08 | CreaMem: A Scene-Aware Memory Architecture for Personalized Agents | HKU |
| [2609.11024v2](https://arxiv.org/abs/2609.11024v2) | 2026-09-10 | The Missing Boundary: How Autonomous Agents Lose Control | Tencent |
| [2609.12354v1](https://arxiv.org/abs/2609.12354v1) | 2026-09-11 | CueMem: Cue-Guided Context Reconstruction for Long-Term Conversational Memory | HIT |
| [2609.16053v1](https://arxiv.org/abs/2609.16053v1) | 2026-09-13 | Retrieval-Driven Memory Reconsolidation for Long-Term LLM Agents | SJTU |
| [2609.17193v1](https://arxiv.org/abs/2609.17193v1) | 2026-09-15 | End-to-End Latency-Minimizing and Load-Balanced Request Scheduling for Edge LLM Inference in Agentic AI Services | HKU |
| [2609.17983v1](https://arxiv.org/abs/2609.17983v1) | 2026-09-16 | Contiguity, Not Importance: Budgeted Repair of Stale KV Caches After Document Edits | Xiaomi |
| [2609.18849v1](https://arxiv.org/abs/2609.18849v1) | 2026-09-16 | Ask the Tool, Don't Guess: Agent Tool Calls Hold Their Progress, and the Serving System Should Read It | Alibaba/Qwen/Tongyi, Tsinghua, Zhejiang U |
| [2609.22641v1](https://arxiv.org/abs/2609.22641v1) | 2026-09-18 | ConsistWorld: Evidence Routing for Consistent Multi-Agent World Models | StepFun, Westlake |
| [2609.24259v3](https://arxiv.org/abs/2609.24259v3) | 2026-09-21 | MemCalib: Benchmarking and Optimizing Memory Use in LLM Agents | Alibaba/Qwen/Tongyi, Fudan, USTC |
| [2609.26763v1](https://arxiv.org/abs/2609.26763v1) | 2026-09-22 | SARA: SLO-Aware Resource Allocation for Disaggregated Agentic LLM Services | HKUST, HKU |
| [2609.30734v1](https://arxiv.org/abs/2609.30734v1) | 2026-09-25 | Learning What to Skip: Counterfactual Credit Assignment for Efficient Multi-Agent LLM Workflows | HKUST, HKU |
| [2609.30813v1](https://arxiv.org/abs/2609.30813v1) | 2026-09-25 | A Benchmark and Diagnostic Study of Epistemic Admission in Shared Agent Memory | Nanjing U |
| [2609.32401v1](https://arxiv.org/abs/2609.32401v1) | 2026-09-26 | Shared Worlds, Private Minds: Structured Memory for Long-Form Writing as World Creation | Renmin U |
| [2609.32459v1](https://arxiv.org/abs/2609.32459v1) | 2026-09-26 | Beyond the Model: Demystifying Harness Effects in Software Engineering Agents | Nanjing U |
| [2609.32522v1](https://arxiv.org/abs/2609.32522v1) | 2026-09-26 | Beyond Dyadic Memory: Interaction-Aware Multimodal Memory with Adaptive Agentic Retrieval for Multi-Party Spoken Conversations | Meituan, Zhejiang U |
| [2609.32862v1](https://arxiv.org/abs/2609.32862v1) | 2026-09-26 | RoboFoundry: System-as-Policy Evolution for Self-Learning Embodied Agents | SJTU, Beihang |
| [2609.33412v1](https://arxiv.org/abs/2609.33412v1) | 2026-09-27 | Resolving State-Representation Mismatch: State-Space Visual Reasoning for Open-Loop VLA Planning | Kuaishou |
| [2609.34372v1](https://arxiv.org/abs/2609.34372v1) | 2026-09-28 | PersMem: Internalizing Personality into Dual-Pathway Memory for LLM Agents | Nanjing U |
| [2609.34385v1](https://arxiv.org/abs/2609.34385v1) | 2026-09-28 | Just-In-Time Agent Memory with Runtime Agentic Research | Peking U, BAAI |
| [2609.34633v1](https://arxiv.org/abs/2609.34633v1) | 2026-09-28 | GenMem: Generative Symbolic Memory for Self-Evolving Harness | Peking U |
| [2610.02932v1](https://arxiv.org/abs/2610.02932v1) | 2026-10-02 | When to Compile a Computer-Use Agent? Measuring Payback and Making Compilation Decisions for Token Efficiency | HKU |
| [2610.03286v1](https://arxiv.org/abs/2610.03286v1) | 2026-10-02 | VenusRL: A Fully Disaggregated Agentic RL System with Priority Scheduling and Scalable Interaction | CAS, Beihang |
| [2610.05162v1](https://arxiv.org/abs/2610.05162v1) | 2026-10-04 | Memadapter: Counterfactual Adaptation Against Memory-induced Sycophancy | Xiamen U |
| [2610.06597v1](https://arxiv.org/abs/2610.06597v1) | 2026-10-05 | Can Agent Harnesses and Inference Engines Hear Each Other? The HEAR Protocol for Agentic LLM Serving | HIT |
| [2610.06830v1](https://arxiv.org/abs/2610.06830v1) | 2026-10-05 | MemPilot: Orchestrating On-Demand Multimodal Memory Curation for LLM Agents | Tsinghua |
| [2610.08101v1](https://arxiv.org/abs/2610.08101v1) | 2026-10-06 | Beyond Corrected Memory: Execution Consistency in Multi-Agent Systems | HKUST |
| [2610.09348v1](https://arxiv.org/abs/2610.09348v1) | 2026-10-07 | Relevance Is Not Sufficiency: What Actually Closes the Evidence Gap in Long-Term Memory QA | Zhejiang U, SJTU |
| [2610.10778v1](https://arxiv.org/abs/2610.10778v1) | 2026-10-07 | MemoWM: How World Models Change What Agents Need to Remember | Tsinghua, Peking U, SJTU, Fudan |
| [2610.11784v1](https://arxiv.org/abs/2610.11784v1) | 2026-10-08 | Compile the Table: Query-Calibrated Operator Compression for Tabular In-Context Learning | JD |
| [2610.11920v1](https://arxiv.org/abs/2610.11920v1) | 2026-10-08 | Event-Centric Memory with Query-Aware Graph Augmentation for Long-Term Conversational Agents | Alibaba/Qwen/Tongyi, Renmin U, CAS |
| [2610.12124v1](https://arxiv.org/abs/2610.12124v1) | 2026-10-08 | Use and Disuse: Intent-Structured Experience Consolidation for Memory and Learning in LLM Agents | CAS |
| [2610.14431v1](https://arxiv.org/abs/2610.14431v1) | 2026-10-10 | MemForm: Benchmarking Memory Formation Poisoning in LLM Agents | USTC |
| [2610.14731v1](https://arxiv.org/abs/2610.14731v1) | 2026-10-10 | VitaBench: Memory Lifecycles Beyond Retrieval | CUHK, HKU |
| [2610.15642v1](https://arxiv.org/abs/2610.15642v1) | 2026-10-11 | Recall What Is Missing: Composing Evidence from Long-Term Agent Memory | CUHK |
| [2610.17763v1](https://arxiv.org/abs/2610.17763v1) | 2026-10-13 | Memory Echo in Single-Agent Long-Term Memory: Lifecycle Evaluation and Provenance-Guided Mitigation | Zhejiang U |
| [2610.17953v1](https://arxiv.org/abs/2610.17953v1) | 2026-10-13 | Agent-Reflex: Teaching Language Agents to Act Reflectively | Renmin U |
| [2610.18014v1](https://arxiv.org/abs/2610.18014v1) | 2026-10-13 | LatentRemedy: Efficient Remedy For Non-Prefix KV Cache Reuse in Multi-Agent Systems | Microsoft, HKUST, HKU |
| [2610.18052v1](https://arxiv.org/abs/2610.18052v1) | 2026-10-13 | Can Agents Forget When Asked? A Benchmark for Memory Unlearning in LLM Agents | Tsinghua |
| [2610.20137v1](https://arxiv.org/abs/2610.20137v1) | 2026-10-14 | StreamErase: Towards Ultra-Fast Streaming Video Erasing | Alibaba/Qwen/Tongyi, SJTU, Wuhan U, HKUST |
| [2610.20392v1](https://arxiv.org/abs/2610.20392v1) | 2026-10-14 | FOLD: Position-Free Far Memory with Local Order for Long-Context Speculative Decoding | Peking U, SYSU |
| [2610.22196v1](https://arxiv.org/abs/2610.22196v1) | 2026-10-15 | Hy-Memory-30B-A3B: Attributed Reinforcement Learning for Long-Term Memory Writing | Tencent |
| [2610.23313v1](https://arxiv.org/abs/2610.23313v1) | 2026-10-16 | From Memory Hits to Answerable Evidence: Query-Conditioned Memory Compilation for Long-Term Agent Memory | USTC |
| [2610.24520v2](https://arxiv.org/abs/2610.24520v2) | 2026-10-17 | HABIT-Bench: Evaluating Habit Induction from Longitudinal Weak Evidence in Agent Memory | SJTU, Fudan, Shanghai AI Lab |
| [2610.25127v1](https://arxiv.org/abs/2610.25127v1) | 2026-10-18 | MemBubble: Benchmarking How Agent Memory Shapes LLM Response Diversity | Baidu, Huawei, CAS |
| [2610.25373v1](https://arxiv.org/abs/2610.25373v1) | 2026-10-18 | MemDerive: A Diagnostic Benchmark for Agent Memory over Evolving Data | SJTU |
| [2610.25550v1](https://arxiv.org/abs/2610.25550v1) | 2026-10-18 | Editing as Language: Teaching LLM Agents a Grammar for Native Context Editing | Meituan, CUHK |
| [2610.26825v2](https://arxiv.org/abs/2610.26825v2) | 2026-10-19 | MemT-1.0: Towards Memory-Native Evolution | MemTensor |
| [2610.29249v1](https://arxiv.org/abs/2610.29249v1) | 2026-10-21 | MOSAIC: An Omni-Modal Benchmark for Long-Term Memory and Cross-Modal Reasoning in Conversational Agents | HKUST |
| [2610.29560v1](https://arxiv.org/abs/2610.29560v1) | 2026-10-21 | From VLM Planners to Robotic Agents: Self-Evolving Harnesses for History-Dependent Manipulation | Zhejiang U, SJTU, USTC, Shanghai AI Lab |
| [2610.29823v1](https://arxiv.org/abs/2610.29823v1) | 2026-10-21 | MemoryTax: The Bitter Lesson of Agent Memory | SJTU |
| [2610.31169v1](https://arxiv.org/abs/2610.31169v1) | 2026-10-22 | SARIA: Persistence-Aware KV Caching with Coordinated DRAM--SSD Reload for LLM Agents | Huawei, Wuhan U, CUHK, Xiamen U |
| [2610.32464v1](https://arxiv.org/abs/2610.32464v1) | 2026-10-23 | Agentic Memory Management Is the Next Frontier of Information Retrieval | Tsinghua |
| [2610.33019v1](https://arxiv.org/abs/2610.33019v1) | 2026-10-08 | Intuition with Evidence: Adaptive Dual Memory for Multimodal Agents | Peking U |
| [2610.33432v1](https://arxiv.org/abs/2610.33432v1) | 2026-10-24 | ConMem: Counterfactual Multi-Scenario Probing for Resolving LLM Memory Misalignment | Tsinghua |
| [2610.34767v1](https://arxiv.org/abs/2610.34767v1) | 2026-10-26 | The Right Fact, the Wrong Decision: SciValidityBench for Scientific Agent Memory | Tsinghua, USTC |
| [2610.35089v1](https://arxiv.org/abs/2610.35089v1) | 2026-10-26 | Learning to Remember: Advances in Memory Mechanisms for Large Language Models | SJTU |
| [2610.35832v1](https://arxiv.org/abs/2610.35832v1) | 2026-10-26 | Profiling a Frontier Agent with EBench: From Direct Control to Harness with Policy | Zhejiang U, SJTU, Fudan, Shanghai AI Lab |
| [2610.39276v1](https://arxiv.org/abs/2610.39276v1) | 2026-10-29 | MemSteer: Turning User Histories into Supervision for Agent Memory Optimization | Microsoft, Peking U |
| [2611.00060v1](https://arxiv.org/abs/2611.00060v1) | 2026-10-13 | Memorix: Managing Memory Selections for AI Agents | SJTU |
| [2611.01404v1](https://arxiv.org/abs/2611.01404v1) | 2026-11-01 | Serving Agentic Robot Fleets: Workload Characterization, KV-Cache Thrashing, and Admission Control | Huawei |
| [2611.01700v1](https://arxiv.org/abs/2611.01700v1) | 2026-11-01 | MemHarmBench: Evaluating Cross-Session Prompt Injection in Memory-Persistent AI Agents | Alibaba/Qwen/Tongyi, Fudan |
| [2611.01747v1](https://arxiv.org/abs/2611.01747v1) | 2026-11-01 | Evolving Memory, Learning to Meta-Control: Test-Time Adaptation for Experience-augmented LLM Agents | Meta, SJTU, Shanghai AI Lab |
| [2611.02912v1](https://arxiv.org/abs/2611.02912v1) | 2026-11-02 | A State Change Is Local, Its Consequences Are Not: Dependency-Aware State Revision for Long-Term Agent Memory | Southern U S&T |
| [2611.03157v1](https://arxiv.org/abs/2611.03157v1) | 2026-11-02 | Toward Knowledge-Centric AI: Discovering, Internalizing, and Using Explicit Knowledge Across Agents and Generations | HKUST |
| [2611.03743v1](https://arxiv.org/abs/2611.03743v1) | 2026-11-02 | EvoMemState: Evolving Memory State for Personal Agents | Xiamen U |
| [2611.04807v1](https://arxiv.org/abs/2611.04807v1) | 2026-11-03 | Asymptotic Optimality of $cμ$-Rule for LLM Inference Scheduling under Memory Constraint | HKUST |
| [2611.05313v1](https://arxiv.org/abs/2611.05313v1) | 2026-11-03 | MDSKILL: Learning to Internalize Skill Memory through Multi-View Distillation for Efficient Dynamic Agent Self-Evolution | Kuaishou, Zhejiang U |

## Big-US-lab-affiliated papers (all selected)

| arXiv | date | title | organisations |
|---|---|---|---|
| [2610.07863v1](https://arxiv.org/abs/2610.07863v1) | 2026-10-06 | ReFold: Training-Free Reversible Inter-Turn Context Folding for Long-Horizon Agents | Intel |
| [2609.40118v1](https://arxiv.org/abs/2609.40118v1) | 2026-09-30 | Persistent Context Graphs for Efficient Memory Compaction in LLM Agents | Microsoft |
| [2609.32256v1](https://arxiv.org/abs/2609.32256v1) | 2026-09-26 | LAM: Efficient Lossy Agent Memory Framework With A Retrieval-Score Error Bound | IBM |
| [2609.19519v1](https://arxiv.org/abs/2609.19519v1) | 2026-09-17 | An Architecture for Long-Horizon Agents: Levels, Ticks and Cascaded Intelligence | Salesforce |
| [2609.35750v3](https://arxiv.org/abs/2609.35750v3) | 2026-09-28 | KV-streams for Efficient Compaction in Agentic Reinforcement Learning | Microsoft |
| [2609.37590v1](https://arxiv.org/abs/2609.37590v1) | 2026-09-29 | FOCUS: Training-Free Decision-Preserving Context Compression for LLM Agents | Microsoft |
| [2609.38641v1](https://arxiv.org/abs/2609.38641v1) | 2026-09-29 | Vision-Language-Action Autonomous Driving Agent with Language-based Memory | NVIDIA |
| [2610.02687v2](https://arxiv.org/abs/2610.02687v2) | 2026-10-02 | Decoupling Memory from Context: Structured Memory for Token-Efficient Test-Time Continual Learning | IBM |
| [2610.06927v1](https://arxiv.org/abs/2610.06927v1) | 2026-10-03 | AttSVD:Prompt-Adaptive Low-Rank KV Cache Compression via Attention-Guided SVD | Microsoft |
| [2609.09233v1](https://arxiv.org/abs/2609.09233v1) | 2026-09-07 | Subagents vs Agent Skills: Executing Reusable Knowledge for Long-Horizon Agentic Tasks | Microsoft |
| [2609.16635v1](https://arxiv.org/abs/2609.16635v1) | 2026-09-15 | EchoPath: Execution-Level Replayable Memory for GUI Agents | Amazon/AWS |
| [2609.27279v2](https://arxiv.org/abs/2609.27279v2) | 2026-09-23 | EnSIMem: Entity-Structured Indexing for Long-Term Agent Memory | Amazon/AWS |
| [2609.28466v1](https://arxiv.org/abs/2609.28466v1) | 2026-09-23 | The Past Frames the Future: Memory for Autoregressive Video Generation | NVIDIA, Peking U, HKUST |
| [2609.32046v1](https://arxiv.org/abs/2609.32046v1) | 2026-09-25 | Receiver-Conditioned Latent Communication gives 94% CacheBack | Amazon/AWS |
| [2610.13494v1](https://arxiv.org/abs/2610.13494v1) | 2026-10-09 | Humanize MLE Agents: Multi-Agent Session Alternation Beyond Single-Agent Limits | NVIDIA, Tsinghua, Zhejiang U |
| [2610.15095v1](https://arxiv.org/abs/2610.15095v1) | 2026-10-10 | Swarm Telepathy: Prefill-Free KV-Cache Transfer Across Families | IBM |
| [2610.22671v2](https://arxiv.org/abs/2610.22671v2) | 2026-10-15 | MemoProAgent: Toward Memory-Driven Proactive Assistance | Meta |
| [2610.27307v2](https://arxiv.org/abs/2610.27307v2) | 2026-10-19 | Evolving Self-tuning Benchmarks for Long-Horizon Tool Use | Google/DeepMind |
| [2610.27377v1](https://arxiv.org/abs/2610.27377v1) | 2026-10-19 | REM: What to Store, When to Recall, What to Forget in Experience Memory for Coding Agents | Amazon/AWS |
| [2609.05707v1](https://arxiv.org/abs/2609.05707v1) | 2026-09-04 | Intra-Prompt Parallel Decoding for Common-Context Question Answering | Amazon/AWS, Apple |
| [2609.10922v1](https://arxiv.org/abs/2609.10922v1) | 2026-09-10 | Auto-RecSys: Harnessing Autonomous Research Agents for Industry-Scale Recommender System | Meta |
| [2609.12320v1](https://arxiv.org/abs/2609.12320v1) | 2026-09-11 | AIM: A Privacy-Aware Interoperable Memory Framework for Multi-Agent Multi-User LLM Systems | Microsoft |
| [2609.16074v1](https://arxiv.org/abs/2609.16074v1) | 2026-09-13 | World-Action Models for Robot Learning and Control: A Survey | Amazon/AWS |
| [2609.17346v1](https://arxiv.org/abs/2609.17346v1) | 2026-09-15 | Where Should a Document Live: Context, Representations, or Parameters? | Amazon/AWS |
| [2609.20519v1](https://arxiv.org/abs/2609.20519v1) | 2026-09-17 | SoL-Pi: Recursively Scaling Auto-Research Loops for Efficient Agent Harness | NVIDIA |
| [2609.24972v3](https://arxiv.org/abs/2609.24972v3) | 2026-09-21 | RRSI: Regularized Recursive Self-Improvement of Agent Harnesses | Google/DeepMind |
| [2609.32091v1](https://arxiv.org/abs/2609.32091v1) | 2026-09-25 | Memory as Middleware for Self-Improving AI Agents | IBM |
| [2609.34242v2](https://arxiv.org/abs/2609.34242v2) | 2026-09-28 | Stashbird: Episode-Grounded Lifecycle Reconciliation for Conversational Agent Memory | Microsoft |
| [2610.07100v1](https://arxiv.org/abs/2610.07100v1) | 2026-10-05 | When to Remember, When to Abstain: Category-Conditioned Retention for Reliable Agent Memory | Meta |
| [2610.18014v1](https://arxiv.org/abs/2610.18014v1) | 2026-10-13 | LatentRemedy: Efficient Remedy For Non-Prefix KV Cache Reuse in Multi-Agent Systems | Microsoft, HKUST, HKU |
| [2610.21091v2](https://arxiv.org/abs/2610.21091v2) | 2026-10-15 | MemComposer: Learning to Assemble Memories for LLM Agents via Reinforcement Learning | Amazon/AWS |
| [2610.23904v1](https://arxiv.org/abs/2610.23904v1) | 2026-09-29 | LVMH: A Meta-Optimization Harness for Long-Video Agent Memory | Meta |
| [2610.39276v1](https://arxiv.org/abs/2610.39276v1) | 2026-10-29 | MemSteer: Turning User Histories into Supervision for Agent Memory Optimization | Microsoft, Peking U |
| [2611.01747v1](https://arxiv.org/abs/2611.01747v1) | 2026-11-01 | Evolving Memory, Learning to Meta-Control: Test-Time Adaptation for Experience-augmented LLM Agents | Meta, SJTU, Shanghai AI Lab |
