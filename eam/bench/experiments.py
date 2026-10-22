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

SUITES = {"individual": INDIVIDUAL, "combined": COMBINED, "smoke": SMOKE}
