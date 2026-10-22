from eam.bench.tasks import chain_hunt, inventory_ops, long_document_qa, multi_session_profile, needle_research

FAMILIES = {
    "chain_hunt": chain_hunt.generate,
    "needle_research": needle_research.generate,
    "inventory_ops": inventory_ops.generate,
    "long_document_qa": long_document_qa.generate,
    "multi_session_profile": multi_session_profile.generate,
}
