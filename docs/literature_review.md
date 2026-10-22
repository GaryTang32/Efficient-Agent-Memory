# Literature review: agent memory and context cost, from Chinese labs (tier-1 venues)

Status as of 2026-10-22. This file is the source of truth for **which techniques this repo implements and where each one comes from**.
Deep-reading notes for individual papers live in [`docs/papers/`](papers/).

## Scope and rules
- **Topic.** Memory effectiveness and token/cost optimisation for LLM agents calling models through an API (Amazon Bedrock). We do not train or host LLMs. A small CPU model, such as an LLMLingua-2 or MiniLM encoder, is acceptable.
- **Tier-1** means CCF-A (AAAI, IJCAI, NeurIPS, ICML, ACL, KDD, WWW, SIGIR, ICSE, FSE, ASE, ISSTA, …) plus ICLR, EMNLP main and NAACL main.
  - Findings, workshops, short papers and companion papers are *not* tier-1.
  - Papers that are not tier-1 appear here only as clearly labelled baselines.
- **Chinese-led** means the first or corresponding author is at a mainland China, Hong Kong or Macau institution. Mixed or Microsoft Research Asia cases are flagged †.
- **How venues were confirmed**, strongest first:
  - OpenReview API `venue` field (ICLR, ICML, NeurIPS).
  - ACL Anthology volume (`*-long` = main, `findings-*` = Findings).
  - AAAI OJS page or DOI.
  - ACM DOI / Crossref (SE, WWW, KDD, SIGIR).
  - An arXiv comment or README alone counts as "claimed" and is not accepted.
- **Affiliations** were checked on page 1 of the PDF. **Repos** were shallow-cloned to confirm they exist and to read their licence; their code was not run.
- **Process.** Three verification passes were run by research sub-agents. I re-checked a sample myself, and every spot-check matched (✓ in the tables below):
  - AgentFold, Sculptor, MemAgent, PACE, SupervisorAgent, EasyTool, AgentDropout, Nemori, Memp (Findings), MemoryOS, FS-Researcher, SeCom, and ReSum (not accepted).
  - The four user-supplied papers were read in full.

---

## A. In-loop context management (one long task, many tool calls)

| Technique | Venue (confirmed) | Lab | Code / licence | Training-free + API? | Priority | Plan |
|---|---|---|---|---|---|---|
| **AgentDiet** — a cheap LLM rewrites step s−a to remove useless, redundant or expired content | FSE'26 ✓ (DOI 10.1145/3797084) | PKU + ByteDance | Figshare 30073654, **CC BY 4.0**; prompt `traj_analyzer.py` `SYS_PROMPT` | Yes | **High** | Port the official prompt and Alg. 1 verbatim ([notes](papers/2509.23586-agentdiet.md)) |
| **PACE** — every step kept at 4 detail levels; embedding relevance plus "pressure" pick a level per step; a `glimpse` tool restores a step | ACL'26 main ✓ (2026.acl-long.1252) | Alibaba + PKU | **no repo** | Yes | **High** | Re-implement from the paper (Titan embeddings, Haiku/Nova summariser) |
| **Sculptor** — the model gets tools to fragment, summarise, hide, restore and search its own context | ICLR'26 ✓ | Tsinghua | **no repo**; schemas in App. F, prompts in App. C.1 | Yes (zero-shot gains with Claude-4-Sonnet and GPT-4.1) | **High** | Re-implement from the appendix |
| **HiAgent** — subgoal-based working memory; completed subgoals' steps are replaced by summaries | ACL'25 main | HKU + HIT + Shanghai AI Lab | HiAgent2024/HiAgent (no licence) | Yes | **High** | Port the prompts and schedule |
| **AOrchestra** — orchestrator gives each sub-agent only a curated slice of the context | ICML'26 | HKUST-GZ + DeepWisdom | FoundationAgents/AOrchestra, **Apache-2.0**, `base_url` config | Yes (Claude-4.5-Haiku: GAIA 60.6 vs 47.9) | **High** | Use the repo's prompts; compare with our `folding` |
| **NestBrowse** — a nested loop reads long pages and returns only what the goal needs | ACL'26 main | Tongyi Lab | DeepResearch `WebAgent/NestBrowse`, **Apache-2.0** | Yes (untrained GPT-OSS-120B ablation) | High | Port as an observation-condensation tool |
| **FS-Researcher** — file-system workspace that outlives the context | ACL'26 main ✓ | USTC + Metastone | Ignoramus0817/FS-Researcher (no licence) | Yes | High | Port; generalises our `offload` |
| **IterResearch** — rebuild workspace each round as question + evolving report + last observation | ICLR'26 | Tongyi + Renmin | no code in repo | Prompt-only claimed (+19.2 pp) | Med | Keep our port, citing the paper |
| **AgentFold** — learned multi-scale folding | ICLR'26 ✓ | Tongyi | `WebAgent/AgentFold` (trained format) | No (SFT-trained) | Low | Background only |
| **Context-Folding / FoldGRPO** — branch/return sub-trajectories | ICML'26 | ByteDance Seed (+CMU, Stanford) | sunnweiwei/FoldAgent, **Apache-2.0**, `OPENAI_BASE_URL` | Yes for evaluation (README: gpt-5-nano) | **High** | Use the repo's prompts and fold workflow directly |
| **MemAgent** — overwrite a fixed-size memory while reading chunks | ICLR'26 **Oral** ✓ | ByteDance Seed + Tsinghua | BytedTsinghua-SIA/MemAgent, **Apache-2.0**, `URL`/`API_KEY` | Workflow yes; the RL weights need a GPU | Med | Use the `quickstart.py` templates |
| **RE-TRAC** — structured state written after each attempt; restart from it | ICML'26 | SEU + MSRA † | microsoft/InfoAgent, MIT | Yes | Med | Optional |
| **DeepAgent**, **HiRA**, **Search-o1**, **WebThinker**, **MindSearch** — condensation through sub-agents or document digestion | WWW'26 / SIGIR'26 / EMNLP'25 / NeurIPS'25 / ICLR'25 | RUC, USTC, Shanghai AI Lab | MIT / Apache | Yes, but completion-style loops need adapting | Med–Low | Later |
| **AttnCompress** — PPL-spike blocks + proxy-attention relevance + three-tier rolling window | ISSTA'26 ✓ | PKU | ZZR0/AttnCompress (**no licence**) | **No**: needs a local Qwen3-4B with attention outputs | Low | "AttnCompress-lite" adaptation, labelled as ours ([notes](papers/2609.08318-attncompress.md)) |

## B. Token / cost efficiency of the agent loop

| Technique | Venue (confirmed) | Lab | Code / licence | Training-free + API? | Priority | Plan |
|---|---|---|---|---|---|---|
| **Turn control** — fixed or dynamic turn budget with reminders | ICSE'26 ✓ (DOI 10.1145/3744916.3773250) | ByteDance | Figshare 30705524, CC BY 4.0 (logs only); prompts in the paper | Yes | **High** | Port the exact reminder strings ([notes](papers/2510.16786-turn-control.md)) |
| **To Run or Not to Run** — restrict or forbid code execution | ISSTA'26 (DOI 10.1145/3832113) | Beihang | mathieu0905/To_Run_Or_Not_To_Run (no licence), `prompt_builder.py` | Yes | Med (coding agents only) | Port the policy prompts if we add a coding task |
| **SupervisorAgent** — rule filter plus a supervisor LLM that corrects, guides or cleans observations | ICLR'26 ✓ | ZJU + Westlake | LINs-lab/SupervisorAgent, **Apache-2.0**, ships `AmazonBedrockServerModel` | Yes (GAIA −29.7% tokens, same pass@1) | **High** | Use the repo's logic |
| **EasyTool** — rewrite tool docs into concise instructions offline (a smaller cached prefix) | NAACL'25 main ✓ | Fudan + MSRA † | microsoft/JARVIS `easytool/`, MIT | Yes | **High** | Apply the paper's Table 2 prompt to our tool specs |
| **AutoTool** — tool-transition graph skips predictable LLM calls | AAAI'26 | HUST | jiajingyyyyyy/AutoTool (no licence) | Yes (SimCSE on CPU) | Med | Later |
| **BAMAS / MasRouter / MaAS** — budget-aware model selection or routing | AAAI'26 / ACL'25 / ICML'25 | PKU / Tongji / NUS+Tongji+SH AI Lab | Apache / Apache / MIT (MaAS has a Bedrock provider) | A small controller is trained from API runs | Med | Phase 2 (pairs with our `router`) |
| **AgentPrune, AgentDropout, G-Designer, S²-MAD** — prune multi-agent communication | ICLR'25 / ACL'25 ✓ / ICML'25 / NAACL'25 | Tongji, HIT-SZ, CUHK, USTC+JD | mostly unlicensed | Small masks trained / training-free (S²-MAD) | Low (multi-agent only) | Out of scope for now |

## C. Cross-session (long-term) memory

| System | Venue (confirmed) | Lab | Code / licence | API-only? | Priority | Plan |
|---|---|---|---|---|---|---|
| **MemoryOS** — STM/MTM/LPM tiers with heat-based promotion | EMNLP'25 main ✓ | BUPT + Tencent | BAI-LAB/MemoryOS, **Apache-2.0**, `pip install memoryos-pro`, `openai_base_url` | Yes (local MiniLM/BGE embeddings, faiss-cpu) | **High** | Use the repo directly through an adapter |
| **LightMem** — LLMLingua-2 pre-compression, topic segments, offline "sleep-time" update | ICLR'26 | ZJU | zjunlp/LightMem, MIT*, `openai_base_url` | Yes | **High** | Use the repo directly |
| **Nemori / "What Deserves Memory"** — episodes; distil only what memory fails to predict | ACL'26 main ✓ | Fudan + Shanda | nemori-ai/nemori, MIT; Postgres + Qdrant | Yes | **High** | Use the repo directly |
| **EverMemOS** (+ HyperMem) — MemCells → MemScenes plus profile | ACL'26 main | Shanda/EverMind † (+ IIE-CAS) | EverMind-AI/EverOS, Apache-2.0 | Yes (reranker needs an adapter) | Med–High | Use the repo directly |
| **Chain-of-Memory** — light construction plus reasoning-path chaining | ACL'26 main | ICT-CAS | Xiucheng-Xu/CoM (no licence) | Yes | High | Use the repo directly (permission needed for redistribution) |
| **SeCom** — topical segmentation plus LLMLingua-2 denoising | ICLR'25 ✓ | Tsinghua + Microsoft † | microsoft/SeCom, MIT | Yes | Med–High | Use the repo directly |
| **MemGAS** — multi-granularity memory with an entropy router | ICLR'26 | USTC + CityU + Huawei | quqxui/MemGAS (no licence) | Yes | Med | Later |
| **ExpeL**, **AutoManual**, **MemEvolve/EvolveLab** — experience / procedural memory | AAAI'24 / NeurIPS'24 / ICML'26 | Tsinghua / HDU+ZJU / OPPO † | Apache / none / Apache | Yes | Med | Phase 2: experience memory to cut steps |
| MemoryBank (AAAI'24), MemoRAG (WWW'25), M3-Agent (ICLR'26) | ✓ venues | SYSU / PKU+BAAI / ByteDance | — | Legacy code / need a GPU | Low | Background only |

## D. Benchmarks and evaluation frameworks (tier-1, Chinese-led)

| Benchmark | Venue | Lab | Use |
|---|---|---|---|
| **LOCA-bench** | ICML'26 | HKUST | hkust-nlp/LOCA-bench, MIT; Anthropic/OpenAI base URLs. Measures clearing tool results, compaction and memory tools as context grows. **Adopt for track A.** |
| **UnifiedMem** ("Does Memory Need Graphs?") | ACL'26 main | PKU | Stage-wise memory harness with per-stage base URLs. **Adopt for track C.** |
| **AMemGym** | ICLR'26 | HKUST + Meituan | On-policy memory evaluation with simulated users |
| **MemoryBench** | ICML'26 | Tsinghua | Continual learning from feedback; finds that no memory system consistently beats RAG |
| **Locomo-Plus**, **MemSim** | ACL'26 / NeurIPS'25 | XJTU+Tencent / RUC+Huawei | Implicit-memory and personal-assistant QA |

## E. Not tier-1, kept only as labelled baselines or engineering rules
- **ReSum** (Tongyi): *not accepted* at ICLR'26 ✓. A useful summarisation baseline; prompts in `WebAgent/WebResummer/src/prompt.py`.
- **Memp** and **ReMe**: ACL'26 **Findings** ✓.
- **MemOS**: no peer-reviewed venue.
- **MemoryWalker**: preprint, training-only ([notes](papers/2609.00865-memorywalker.md)).
- **SWE-Pruner** and the **OPPO Efficient Agents** study: no venue found.
- **LLMLingua-2**: Findings of ACL'24, Microsoft. It is a building block inside LightMem and SeCom.
- **Manus context-engineering rules**: industry blog, no code. Kept as engineering defaults: stable prefix, append-only context, recoverable offload, todo recitation.
- **Vendor guidance**: MiniMax M2.1 (keep the first and last 5 AI turns past 30% of the context), DeepSeek V3.2 (discard-all / discard-75%), Qwen-Agent truncation. These are cheap baselines from Chinese model vendors; they are documentation, not papers.
- **Observation masking**: the baseline in both AgentDiet and AttnCompress, implemented in AttnCompress's `traj_analyzer.py` (window 2, minimum 300 tokens). It is the cheapest strong baseline.

## F. Implementation shortlist (phase 1: test each technique on its own)

Each entry either uses the official code or prompt verbatim, or is labelled "ported from paper" or "our adaptation".

1. **Baselines:**
   - full context
   - observation masking (AttnCompress artifact settings)
   - LLM summary (AttnCompress artifact prompt)
   - ReSum (official prompt)
   - Manus-rules cache layout
2. **Turn control** (ICSE'26): exact reminder strings; percentile calibration helper.
3. **AgentDiet** (FSE'26): official CC-BY prompt and Alg. 1 (`a=2, b=1, θ=500`), with a Bedrock cheap model as the reflector.
4. **SupervisorAgent** (ICLR'26): official logic, which ships Bedrock support.
5. **HiAgent** (ACL'25) and **Context-Folding** (ICML'26): official prompts.
6. **PACE** (ACL'26) and **Sculptor** (ICLR'26): re-implemented from the papers, since no code is released.
7. **EasyTool** (NAACL'25): one-off tool-doc compression measured against cached-prefix size.
8. **Cross-session:** MemoryOS, LightMem and Nemori through thin adapters over their official packages; LOCA-bench / UnifiedMem for evaluation.

Every technique is measured with Bedrock prompt caching **on**. Most headline numbers in these papers ignore caching; only AgentDiet and AttnCompress count cached prices. Accuracy must be reported alongside cost.

## G. Still unverified / to do
- Whether Bedrock's OpenAI-compatible endpoint serves `/v1/embeddings`, and which models it covers. This decides whether repos needing embeddings can call Bedrock directly or need a LiteLLM gateway.
- Licence permission for repos without a LICENSE file (AttnCompress, HiAgent, CoM, AutoTool, To-Run). We may read and cite them, but not copy their code into this repo.
- EMNLP'26 proceedings are not online yet, so AgentSwing and others remain unverified.
