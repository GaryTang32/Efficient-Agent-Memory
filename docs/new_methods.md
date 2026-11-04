# Methods from the Sep–Nov 2026 literature scan

These are the eight methods that [the scan](literature/2026-11-scan/README.md) found but that had not been tried yet. Each one is implemented as a technique in this harness and follows its own source as closely as the API allows. Every module's docstring states its source and lists its deviations. Results are in `docs/results/2026-11-04-new-methods.md`.

## The methods at a glance

| Spec | Method | Developer | Source used | Faithful to the source | Deviations (API-only, structured tools) |
|---|---|---|---|---|---|
| `strands` | Strands harness defaults | AWS | `strands-harness` 0.3.3 and `strands-agents` 1.63.0, ported from the package source (Apache-2.0) | Ingestion truncation (>1,500 tokens → 750-token head/tail preview plus a stash reference). `retrieve_context` with grep or line range. Summarisation by the main model at 85% of the window, keeping the task and the last 4 messages. Emergency drop of 20%. A single rolling cache point. Long-term memory: facts extracted by the small model, keyword top-5 injected ephemerally on user turns, plus a `search_memory` tool. All prompts verbatim. | Strands retries a request that overflowed; this loop stops instead, so the emergency drop runs before the call. Memory is extracted at the end of every session (Strands does this every 5 invocations and at shutdown). |
| `cadoc` | CADOC, Cache-Aware Dynamic Object Context | SJTU | arXiv 2609.37012 (no public code) | Deterministic `<OBJECT_CARD>`s with no LLM synopsis. Immutable versioned objects and byte-exact `retrieve_object`. Raw hot tail of h=4 steps / 12,800 tokens. The waiting-ledger commit rule W + w_r·G ≥ Q with batch commits. Forced commits at 2h steps or 25,600 pending tokens. | Objects are whole tool results. The Card's `contains` fields and the receipt text are ours. `mode=route` prices a rewrite as a cache *write* (2× on the Claude Code CLI), where the paper prices a miss at 1×. |
| `refold` | ReFold, reversible inter-turn folding | UCSB + Intel | Official engine vendored (github.com/YupengSu/ReFold @017328f, Apache-2.0) | The PROGRESS/STALE protocol, chunked boundary k=3, folding, line-level deduplication of reads, search and output deduplication, pytest filtering, `restore`, reminders. All prompts and notes verbatim. | One step per structured tool call. Reads, searches and tests are classified by tool name. `restore` is a tool, not a bash command, and the prompt wording says so. A partly folded multi-call reply keeps its call, with a one-line pointer in place of the result. |
| `sjc`, `openclaw[:sjc=true]` | SJC, Source-Judged Compaction, with its host compressor (OpenClaw safeguard) | University of Virginia | arXiv 2610.20927. The official repo has no licence, so this is a re-implementation; prompts are quoted from the paper. | The CONTEXT and QUESTION texts verbatim. Entries are split by the official rule. BM25 evidence selection within the 30K-token budget. τ = 0.5. Fail-open. The pruned summary is also the next "previous checkpoint". | The judge is Claude Haiku returning p_yes in JSON, in place of the Jev classifier. `sjc` = SJC adapted to ReSum, whose summary has no fixed sections. The OpenClaw host is simplified: no chunked summarisation and no retention plan. |
| `akv_drop` | AKV tool-response rolling drop, "Cache Engineering for Agents" | Tsinghua + CUHK | arXiv 2610.28577 and github.com/thu-nics/AKV (Apache-2.0) | The selection policy: on every turn, drop every tool result older than the latest 12 tool turns. Calls and the agent's text are never dropped. | AKV drops KV entries inside the serving engine, at no re-prefill cost. Over an API the text has to be removed, and a short placeholder is left. The paper measured this text-level variant at 1.85× the cost of full context. `block=8` (our variant) drops in batches. |
| `raw_rag` | Raw-history retrieval as memory | UIUC et al. (Memory Tax), SJTU (MemoryTax), and the "Naive RAG" authors | arXiv 2610.34073, 2610.30755 and 2610.29823 (no RAG code released) | Memory Tax "RAG (1rd)" settings: turn-based chunks of ~1,024 characters with last-turn overlap, 8,192-character windows, BM25 top-10 ∪ dense top-10, reranked to the top 10. The query is the raw task text. Nothing is extracted or summarised. | all-MiniLM-L6-v2 and the ms-marco-MiniLM cross-encoder replace Qwen3-Embedding and Qwen3-Reranker. Recall is capped at 15% of the window. |
| `coral` | CORAL, agent-managed working memory with context resets | CUHK + Tencent + HKUST | arXiv 2610.40350, prompting-only variant (the code link returns 404) | System prompt, `memory-management-tool` and `context-optimization-tool` descriptions and the reset template are all verbatim. The agent alone decides when to reset. | The prompt is appended to the benchmark's own system prompt. Unit ids, memory rendering and tool return texts are ours. |
| `selfcompact` | SelfCompact, self-compacting agents | Apple + JHU | arXiv 2606.23525 and github.com/tianjianl/selfcompact (MIT) | Gates: round ≥ 3, period 2, cap 1000. The C1/C2/C3/N1 rubric and the summary are both written by the agent's own model. The prompts and the reset message are verbatim. | The 40K gate is scaled to 0.31 × window. A backstop at 0.8 × window forces a compaction (the code has none; the paper mentions one at 0.30). The probe is appended to the last user message and the tools are kept. |

## Shared harness change

Some techniques send a rendered copy of the history instead of editing it: ReFold, CADOC, and Strands' memory injection. For these, the loop now adds the context gauge to the request that is actually sent, and counts history rewrites on that request rather than on the stored history. Techniques that do not render a copy behave exactly as before.

## How they are compared

The suite is `real_v5` in `eam/bench/experiments.py`, and it reuses the v4 anchors and comparators.

**Task setup**
- **research_corpus** (one session): each method on its own.
- **Multi-session tasks:** each within-session method is paired with the same note workspace as the comparator (`fs_workspace+X` against `fs_workspace+resum`), so the context method is the only difference.
- **`raw_rag`** replaces the workspace (`raw_rag+resum` against `fs_workspace+resum`).
- **`strands`** runs on its own, because it brings its own long-term memory.

**Scoring and cost**
- Same seeds, windows, tasks and Claude Code CLI route as v4.
- Floor: `naive`. Ceiling: `naive@native`.
- The cost ratio is taken against `naive@native`.
