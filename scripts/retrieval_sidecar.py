"""Embedding + reranking sidecar for the raw_rag technique, run under .venv-memory (sentence-transformers).

JSON lines on stdin/stdout:
  {"op": "embed", "texts": [...]}                 -> {"vectors": [[...], ...]}   (L2-normalised)
  {"op": "rerank", "query": "...", "docs": [...]} -> {"scores": [...]}
Models: sentence-transformers/all-MiniLM-L6-v2 (dense) and cross-encoder/ms-marco-MiniLM-L-6-v2 (reranker), CPU.
"""
import json
import os
import sys

out = sys.stdout
sys.stdout = sys.stderr  # library chatter must not corrupt the protocol
from sentence_transformers import CrossEncoder, SentenceTransformer  # noqa: E402

EMB = os.environ.get("EAM_RAG_EMBED", "sentence-transformers/all-MiniLM-L6-v2")
RER = os.environ.get("EAM_RAG_RERANK", "cross-encoder/ms-marco-MiniLM-L-6-v2")
emb = SentenceTransformer(EMB, device="cpu")
rer = CrossEncoder(RER, device="cpu") if RER else None
out.write(json.dumps({"ready": True, "embed": EMB, "rerank": RER}) + "\n")
out.flush()
for line in sys.stdin:
    req = json.loads(line)
    try:
        if req["op"] == "embed":
            v = emb.encode(req["texts"], normalize_embeddings=True, batch_size=32).tolist()
            res = {"vectors": v}
        elif req["op"] == "rerank":
            s = rer.predict([(req["query"], d) for d in req["docs"]]).tolist() if rer else [0.0] * len(req["docs"])
            res = {"scores": s}
        else:
            res = {"error": f"unknown op {req['op']}"}
    except Exception as exc:  # noqa: BLE001
        res = {"error": str(exc)}
    out.write(json.dumps(res) + "\n")
    out.flush()
