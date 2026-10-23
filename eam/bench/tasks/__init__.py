from eam.bench.tasks import (chain_hunt, inventory_ops, ledger_audit, long_document_qa, multi_session_profile,
                             needle_research, ops_stream, research_corpus)

FAMILIES = {
    "chain_hunt": chain_hunt.generate,
    "ledger_audit": ledger_audit.generate,
    "research_corpus": research_corpus.generate,
    "ops_stream": ops_stream.generate,
    "needle_research": needle_research.generate,
    "inventory_ops": inventory_ops.generate,
    "long_document_qa": long_document_qa.generate,
    "multi_session_profile": multi_session_profile.generate,
}
