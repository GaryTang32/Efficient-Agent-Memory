"""Sidecar for the official memory systems (run with .venv-memory/bin/python; see docs/official_memory_repos.md).

Protocol: one JSON object per line on stdin, one reply per line on stdout (the libraries' own printing goes to
stderr). Ops:
    {"op": "init", "backend": "memoryos|lightmem|nemori", "base_url": ".../v1", "model": "cc-haiku", "dir": "..."}
    {"op": "add", "task": "...", "answer": "...", "session": 1}
    {"op": "retrieve", "query": "...", "limit": 10}       -> {"text": "...memories formatted for the prompt..."}
    {"op": "close"}

Each backend is used through its own public API with default settings, plus the minimal runtime fixes needed to
run it here (no edits to the installed packages):
* MemoryOS (BAI-LAB, EMNLP'25, Apache-2.0): its keyword extraction ignores the configured model and asks for
  gpt-4o-mini; the configured model is passed in. Context = what Memoryos.get_response puts into its prompt:
  short-term history, retrieved mid-term pages, user profile and knowledge, assistant knowledge.
* LightMem (ZJU, ICLR'26, MIT): LLMLingua-2 pre-compression + topic segmentation, embedded Qdrant; with
  transformers ≥ 5 the segmenter's BERT must use eager attention (SDPA returns no attentions).
  messages_use="hybrid" so that the agent's answers are memorised, not only the user turns.
* Nemori (Fudan + Shanda, ACL'26, MIT): needs Postgres (a local cluster) and Qdrant; Qdrant is used embedded and
  embeddings are local (all-MiniLM-L6-v2) instead of OpenAI's text-embedding-3-small.
"""

from __future__ import annotations

import asyncio
import datetime as dt
import json
import os
import sys

_OUT = os.fdopen(os.dup(1), "w", buffering=1)
sys.stdout = sys.stderr  # library prints must not corrupt the protocol
EMBED_MODEL = "sentence-transformers/all-MiniLM-L6-v2"


def _clean(obj):
    if isinstance(obj, dict):
        return {k: _clean(v) for k, v in obj.items() if "embedding" not in k}
    if isinstance(obj, list):
        return [_clean(v) for v in obj]
    return obj


class MemoryOSBackend:
    def __init__(self, base_url, model, path):
        import functools

        import memoryos.mid_term
        import memoryos.updater
        import memoryos.utils

        kw = functools.partial(memoryos.utils.llm_extract_keywords, model=model)
        memoryos.mid_term.llm_extract_keywords = kw
        memoryos.updater.llm_extract_keywords = kw
        from memoryos.memoryos import Memoryos

        self.m = Memoryos(user_id="agent", openai_api_key="unused", data_storage_path=path,
                          openai_base_url=base_url, llm_model=model)

    def add(self, task, answer, session):
        self.m.add_memory(user_input=task, agent_response=answer,
                          timestamp=(dt.datetime(2025, 1, 1) + dt.timedelta(days=session)).isoformat())

    def retrieve(self, query, limit):
        r = self.m.retriever.retrieve_context(user_query=query, user_id="agent")
        hist = "\n".join(f"User: {qa.get('user_input', '')}\nAssistant: {qa.get('agent_response', '')}"
                         for qa in self.m.short_term_memory.get_all())
        pages = "\n".join(f"[Historical memory] User: {p.get('user_input', '')}\nAssistant: {p.get('agent_response', '')}"
                          f"\nOverview: {p.get('meta_info', '')}" for p in r["retrieved_pages"][:limit])
        profile = self.m.user_long_term_memory.get_raw_user_profile("agent") or ""
        know = "\n".join(f"- {k['knowledge']}" for k in r["retrieved_user_knowledge"] + r["retrieved_assistant_knowledge"])
        parts = [("Recent sessions", hist), ("Retrieved earlier sessions", pages),
                 ("Profile", "" if profile.lower() == "none" else profile), ("Knowledge", know)]
        return "\n\n".join(f"## {t}\n{b}" for t, b in parts if b.strip())


class LightMemBackend:
    def __init__(self, base_url, model, path):
        from lightmem.memory.lightmem import LightMemory

        cfg = {
            "pre_compress": True,
            "pre_compressor": {"model_name": "llmlingua-2", "configs": {"llmlingua_config": {
                "model_name": "microsoft/llmlingua-2-bert-base-multilingual-cased-meetingbank",
                "device_map": "cpu", "use_llmlingua2": True}}},
            "topic_segment": True, "precomp_topic_shared": True, "topic_segmenter": {"model_name": "llmlingua-2"},
            "messages_use": "hybrid", "metadata_generate": True, "text_summary": True,
            "memory_manager": {"model_name": "openai", "configs": {"model": model, "api_key": "unused",
                                                                   "max_tokens": 4000, "openai_base_url": base_url}},
            "extract_threshold": 0.1, "index_strategy": "embedding",
            "text_embedder": {"model_name": "huggingface", "configs": {"model": EMBED_MODEL, "embedding_dims": 384,
                                                                       "model_kwargs": {"device": "cpu"}}},
            "retrieve_strategy": "embedding",
            "embedding_retriever": {"model_name": "qdrant", "configs": {
                "collection_name": "lt", "embedding_model_dims": 384, "path": os.path.join(path, "qdrant")}},
            "update": "offline",
            "logging": {"level": "WARNING", "file_enabled": False, "log_dir": os.path.join(path, "logs")},
        }
        self.lm = LightMemory.from_config(cfg)
        self.lm.segmenter.model.set_attn_implementation("eager")

    def add(self, task, answer, session):
        stamp = (dt.date(2025, 1, 1) + dt.timedelta(days=session)).isoformat()
        msgs = [{"role": "user", "content": task, "time_stamp": stamp},
                {"role": "assistant", "content": answer, "time_stamp": stamp}]
        self.lm.add_memory(messages=msgs, force_segment=True, force_extract=True)

    def retrieve(self, query, limit):
        res = self.lm.retrieve(query, limit=limit)
        return "\n".join(f"- {x}" for x in res) if isinstance(res, list) else str(res)


class NemoriBackend:
    def __init__(self, base_url, model, path):
        from qdrant_client import QdrantClient
        from sentence_transformers import SentenceTransformer

        import nemori.api.facade
        import nemori.db.qdrant_store
        import nemori.factory
        from nemori import MemoryConfig, NemoriMemory

        qpath = os.path.join(path, "qdrant")
        nemori.db.qdrant_store.QdrantClient = lambda *a, **k: QdrantClient(path=qpath)
        st = SentenceTransformer(EMBED_MODEL, device="cpu")

        class LocalEmbedding:
            def __init__(self, *a, **k):
                pass

            async def embed(self, t):
                return st.encode(t, normalize_embeddings=True).tolist()

            async def embed_batch(self, ts):
                return st.encode(list(ts), normalize_embeddings=True).tolist()

            async def probe_dimension(self):
                return 384

        nemori.api.facade.AsyncEmbeddingClient = nemori.factory.AsyncEmbeddingClient = LocalEmbedding
        dsn = os.environ.get("EAM_NEMORI_DSN", "postgresql://nemori:nemori@127.0.0.1:55432/nemori")
        self.user = "agent-" + os.path.basename(path.rstrip("/"))  # one Nemori user per run
        self.cfg = MemoryConfig(dsn=dsn, db_pool_min=1, db_pool_max=4, llm_model=model, llm_api_key="unused",
                                llm_base_url=base_url, embedding_dimension=384)
        self.loop = asyncio.new_event_loop()
        self.mem = NemoriMemory(config=self.cfg)
        self.loop.run_until_complete(self.mem.__aenter__())

    def add(self, task, answer, session):
        stamp = (dt.datetime(2025, 1, 1, 9) + dt.timedelta(days=session)).isoformat()
        msgs = [{"role": "user", "content": task, "timestamp": stamp},
                {"role": "assistant", "content": answer, "timestamp": stamp}]
        self.loop.run_until_complete(self.mem.add_messages(self.user, msgs))
        self.loop.run_until_complete(self.mem.flush(self.user))

    def retrieve(self, query, limit):
        res = _clean(self.loop.run_until_complete(self.mem.search(self.user, query)))
        eps = res.get("episodes", [])[:limit]
        sem = res.get("semantic_memories", [])[:limit]

        def text(x):
            return x.get("content") or x.get("text") or x.get("title") or json.dumps(x, default=str)[:500]

        return ("## Episodes\n" + "\n".join(f"- {(e.get('title') or '')}: {text(e)}" for e in eps)
                + "\n\n## Facts\n" + "\n".join(f"- {text(s)}" for s in sem))

    def close(self):
        self.loop.run_until_complete(self.mem.__aexit__(None, None, None))


BACKENDS = {"memoryos": MemoryOSBackend, "lightmem": LightMemBackend, "nemori": NemoriBackend}


def main():
    backend = None
    for line in sys.stdin:
        if not line.strip():
            continue
        msg = json.loads(line)
        try:
            op = msg["op"]
            if op == "init":
                backend = BACKENDS[msg["backend"]](msg["base_url"], msg.get("model", "cc-haiku"), msg["dir"])
                out = {"ok": True}
            elif op == "add":
                backend.add(msg["task"], msg["answer"], int(msg.get("session", 1)))
                out = {"ok": True}
            elif op == "retrieve":
                out = {"ok": True, "text": backend.retrieve(msg["query"], int(msg.get("limit", 10)))}
            elif op == "close":
                if hasattr(backend, "close"):
                    backend.close()
                _OUT.write(json.dumps({"ok": True}) + "\n")
                break
            else:
                out = {"ok": False, "error": f"unknown op {op}"}
        except Exception as exc:  # report, keep serving
            out = {"ok": False, "error": f"{type(exc).__name__}: {exc}"[:2000]}
        _OUT.write(json.dumps(out) + "\n")


if __name__ == "__main__":
    main()
