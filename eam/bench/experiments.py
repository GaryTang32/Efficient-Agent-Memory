"""Named experiment suites: which technique specs to run on which task.

Phase 1 ("individual") runs every method on its own against the full-context baseline. Methods are chosen from
docs/literature_review.md; provisional (non-paper) methods are not in the suites. `turn_control` limits should come
from `python -m eam.bench calibrate <baseline results>` (75th percentile of the model's own turn counts); the values
here are placeholders for the offline mock.
"""

PAPER_FAITHFUL = ["agentdiet", "turn_control", "folding", "memagent", "resum"]

INDIVIDUAL = {
    "needle_research": ["full", "cache_layout", "obs_mask", "agentdiet", "folding", "turn_control:limit=10",
                        "resum:max_context_k=8", "offload"],
    "inventory_ops": ["full", "cache_layout", "obs_mask", "agentdiet", "folding", "turn_control:limit=16",
                      "resum:max_context_k=4", "iter_research"],
    "long_document_qa": ["full", "cache_layout", "obs_mask", "agentdiet", "memagent", "resum:max_context_k=8"],
    "multi_session_profile": ["full", "carryover", "tiered_memory"],
}

COMBINED = {
    "needle_research": ["full", "cache_layout+agentdiet", "cache_layout+folding", "cache_first", "lean", "auto"],
    "inventory_ops": ["full", "cache_layout+obs_mask", "cache_layout+turn_control:limit=16", "cache_first", "lean",
                      "auto"],
    "long_document_qa": ["full", "cache_layout+memagent", "cache_layout+agentdiet", "cache_first", "lean", "auto"],
    "multi_session_profile": ["full", "cache_layout+tiered_memory", "carryover"],
}

SMOKE = {family: specs[:3] for family, specs in INDIVIDUAL.items()}

# First real comparison (phase 1, each method alone) on the deep sequential task. `cache_layout` is omitted
# because the Claude Code CLI route places cache breakpoints itself (it equals `full` there); add it on Bedrock.
# turn_control limits come from `calibrate` on this suite's `full` rows.
REAL_V1 = {
    # turn_control limit = 75th percentile of the cc-haiku `full` turn counts (calibrate: p25=p50=p75=21)
    "chain_hunt": ["full", "obs_mask", "agentdiet", "folding", "resum:max_context_k=16", "turn_control:limit=21"],
}

# Overflow + multiple rounds: 24 ledgers (~100K tokens) and 10 refund files under a 48K-token window, three
# sessions that depend on each other. Each method alone, plus one combination (workspace for cross-round memory +
# masking for the window) because no single method addresses both requirements.
REAL_V2 = {
    "ledger_audit": ["full", "obs_mask", "agentdiet", "resum:max_context_k=40", "folding", "fs_workspace",
                     "fs_workspace+obs_mask", "fs_workspace+resum:max_context_k=40"],
}

# Long-horizon tasks, every model, model-normalised (docs/methodology.md §6). Anchors: `naive` (floor: no memory,
# no caching, no offload), `full` (B1), `full@native` (ceiling: nothing lost, model's own window; its uncached
# cost is computed from its tokens). ReSum's trigger sits just below each task's window
# (0.9 × (K·1024 − 1000) ≈ 0.8 × window). AgentDiet is run where the provider accepts its reflection calls.
REAL_V3 = {
    "research_corpus": ["naive", "full", "full@native", "obs_mask", "resum:max_context_k=33", "fs_workspace",
                        "fs_workspace+resum:max_context_k=33", "folding"],
    "ops_stream": ["naive", "full", "full@native", "obs_mask", "resum:max_context_k=26", "fs_workspace",
                   "fs_workspace+resum:max_context_k=26", "folding"],
}

# Phase 2: AutoMemory v1 against the anchors and the best single method per task, plus ablations (one switch off
# at a time). Corrected harness (2026-10-24: retried and continued CLI calls are no longer read as oversized
# prompts), so every Haiku cell of the long tasks is rerun.
AUTOMEM_ABLATIONS = ["automem", "automem:guard=0", "automem:recall=false,autosave=false", "automem:keep_recent=0",
                     "automem:compact=mask", "automem:compact=none"]
REAL_V4_HAIKU = {
    "research_corpus": ["naive", "naive@native", "full", "obs_mask", "resum:max_context_k=33",
                        "fs_workspace+resum:max_context_k=33", *AUTOMEM_ABLATIONS],
    "ops_stream": ["naive", "naive@native", "full", "resum:max_context_k=26", "fs_workspace",
                   "fs_workspace+resum:max_context_k=26", *AUTOMEM_ABLATIONS],
    "ledger_audit": ["naive", "naive@native", "full", "resum:max_context_k=40", "fs_workspace",
                     "fs_workspace+resum:max_context_k=40", *AUTOMEM_ABLATIONS],
    "repo_debug": ["naive", "naive@native", "full", "obs_mask", "resum:max_context_k=13",
                   "fs_workspace+resum:max_context_k=13", *AUTOMEM_ABLATIONS],
}
# Sonnet: its earlier rows are unaffected by the corrected bugs (its replies are a few hundred tokens), so only the
# new cells: AutoMemory on every task (also with Haiku as the summariser: `#aux=cc-haiku`), and the new repo_debug
# task.
REAL_V4_SONNET = {
    "research_corpus": ["automem", "automem#aux=cc-haiku"],
    "ops_stream": ["automem", "automem#aux=cc-haiku"],
    "ledger_audit": ["automem", "automem#aux=cc-haiku", "naive", "naive@native"],
    "repo_debug": ["naive", "naive@native", "full", "obs_mask", "resum:max_context_k=13",
                   "fs_workspace+resum:max_context_k=13", "automem", "automem#aux=cc-haiku"],
}

# Official long-term memory systems (item 4b) on the multi-session tasks, each with the same ReSum compaction as
# `fs_workspace+resum`, so the memory system is the only difference. One suite per backend.
def _ext(backend: str) -> dict[str, list[str]]:
    k = {"ops_stream": 26, "ledger_audit": 40, "repo_debug": 13}
    return {task: [f"ext_memory:backend={backend}+resum:max_context_k={kk}"] for task, kk in k.items()}


SUITES = {"individual": INDIVIDUAL, "combined": COMBINED, "smoke": SMOKE, "real_v1": REAL_V1, "real_v2": REAL_V2,
          "real_v2_aware": REAL_V2,
          "real_v3": REAL_V3, "real_v4_haiku": REAL_V4_HAIKU, "real_v4_sonnet": REAL_V4_SONNET,
          "extmem_memoryos": _ext("memoryos"), "extmem_lightmem": _ext("lightmem"), "extmem_nemori": _ext("nemori")}

# Task settings per suite. real_v2 = "unaware" (the papers' setting: the harness silently enforces the window);
# real_v2_aware = the agent is told the limit and sees a context gauge each step.
SUITE_TASK_KWARGS = {"real_v2_aware": {"ledger_audit": {"disclose_limit": True}}}
