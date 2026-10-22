from eam.bench.tasks import inventory_ops, long_document_qa, multi_session_profile, needle_research

FAMILIES = {
    "needle_research": needle_research.generate,
    "inventory_ops": inventory_ops.generate,
    "long_document_qa": long_document_qa.generate,
    "multi_session_profile": multi_session_profile.generate,
}
