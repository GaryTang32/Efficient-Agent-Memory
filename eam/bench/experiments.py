"""Named experiment suites: which technique specs to run on which task."""

INDIVIDUAL = {
    "needle_research": ["full", "cache_layout", "offload", "compression", "keep_last_n", "resum",
                        "iter_research", "folding", "todo", "router"],
    "inventory_ops": ["full", "cache_layout", "keep_last_n", "resum:trigger_tokens=5000", "iter_research", "todo", "router"],
    "long_document_qa": ["full", "cache_layout", "offload", "compression", "memagent", "resum"],
    "multi_session_profile": ["full", "carryover", "tiered_memory", "tiered_memory:retrieval=on_demand"],
}

COMBINED = {
    "needle_research": ["full", "cache_layout+offload", "cache_layout+offload+folding", "cache_first", "lean", "auto"],
    "inventory_ops": ["full", "cache_layout+keep_last_n", "cache_layout+todo", "cache_first", "lean", "auto"],
    "long_document_qa": ["full", "cache_layout+memagent", "cache_layout+offload", "cache_first", "lean", "auto"],
    "multi_session_profile": ["full", "cache_layout+tiered_memory", "carryover"],
}

SMOKE = {family: specs[:3] for family, specs in INDIVIDUAL.items()}

SUITES = {"individual": INDIVIDUAL, "combined": COMBINED, "smoke": SMOKE}
