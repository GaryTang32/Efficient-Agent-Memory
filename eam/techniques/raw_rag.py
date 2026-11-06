"""Raw-history retrieval as cross-session memory — the "plain retrieval over raw history" baseline of three recent
independent evaluations: "Memory Tax" (arXiv 2610.34073, UIUC et al.; RAG (1rd)), "Naive RAG Is Stronger Than We
Thought" (arXiv 2610.30755, Raw-RAG) and "MemoryTax: The Bitter Lesson of Agent Memory" (arXiv 2610.29823, SJTU).
None of them released its RAG code (the Memory Tax repo's naive-RAG README is a TODO), so this is our
implementation of the published settings.

Nothing is extracted or summarised: every session's raw turns (task, the agent's text, tool calls, full tool
results) are chunked and indexed when the session ends; at the start of the next session the task text is the
query, and the retrieved chunks go into the first message.

``mode=memtax`` (default, Memory Tax RAG 1rd, App. A.2/B.1): turns are greedily merged into ~1,024-character chunks
(the last turn carried over as overlap), longer turns stay separate, turns over 8,192 characters are split into
8,192-character windows with 1,024 overlap; each chunk has a session header. BM25 top-10 ∪ dense top-10, reranked by
a cross-encoder, top-10 in relevance order. ``mode=bm25turns`` (Bitter Lesson baseline): BM25 top-8 turns, each with
±2 neighbouring turns of the same session, in first-seen order.

Deviations: the dense model is all-MiniLM-L6-v2 and the reranker cross-encoder/ms-marco-MiniLM-L-6-v2 (the papers
use Qwen3-Embedding-0.6B and Qwen3-Reranker-0.6B; the Memory Tax ablation puts MiniLM 2–3 points lower), run in the
``.venv-memory`` sidecar (scripts/retrieval_sidecar.py); without it, BM25 only (logged). Agent transcripts carry long
tool results, so the recalled text is capped at ``budget`` × window tokens (Raw-RAG reports no loss under a 5K cap).
"""

from __future__ import annotations

import atexit
import json
import math
import os
import re
import subprocess
from pathlib import Path

from eam.techniques.base import Technique
from eam.tokens import estimate_tokens

RECALL = "Memories from earlier sessions (retrieved by raw_rag):\n\n{text}\n\nUse them where they help."
_ROOT = Path(__file__).resolve().parents[2]


def _tok(text: str) -> list[str]:
    """Bitter Lesson BM25 tokenizer: lowercase, punctuation → space, whitespace split (digits kept)."""
    return re.sub(r"[^\w\s]", " ", text.lower()).split()


class _BM25:
    def __init__(self, docs: list[str], k1: float = 1.2, b: float = 0.75):
        self.docs = [_tok(d) for d in docs]
        self.k1, self.b = k1, b
        n = len(self.docs) or 1
        self.avg = sum(map(len, self.docs)) / n or 1
        df: dict[str, int] = {}
        for d in self.docs:
            for t in set(d):
                df[t] = df.get(t, 0) + 1
        self.idf = {t: math.log(1 + (n - c + 0.5) / (c + 0.5)) for t, c in df.items()}
        self.tf = [{t: d.count(t) for t in set(d)} for d in self.docs]

    def top(self, query: str, k: int) -> list[int]:
        q = set(_tok(query))
        scored = []
        for i, (d, tf) in enumerate(zip(self.docs, self.tf)):
            s = sum(self.idf[t] * tf[t] * (self.k1 + 1) / (tf[t] + self.k1 * (1 - self.b + self.b * len(d) / self.avg))
                    for t in q if t in tf)
            if s > 0:
                scored.append((-s, i))
        return [i for _, i in sorted(scored)[:k]]


class _Sidecar:
    """Persistent embedding/reranking subprocess under .venv-memory (shared by all raw_rag instances)."""

    _proc = None
    _failed = False

    @classmethod
    def call(cls, payload: dict) -> dict | None:
        if cls._failed:
            return None
        if cls._proc is None:
            py = Path(os.environ.get("EAM_MEMORY_PYTHON", _ROOT / ".venv-memory" / "bin" / "python"))
            if not py.exists():
                cls._failed = True
                return None
            cls._proc = subprocess.Popen([str(py), str(_ROOT / "scripts" / "retrieval_sidecar.py")],
                                         stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL,
                                         text=True, env={**os.environ, "HF_HUB_OFFLINE": "1",
                                                         "TOKENIZERS_PARALLELISM": "false"})
            atexit.register(cls._proc.kill)
            ready = cls._proc.stdout.readline()
            if not ready.strip():
                cls._failed = True
                return None
        try:
            cls._proc.stdin.write(json.dumps(payload) + "\n")
            cls._proc.stdin.flush()
            res = json.loads(cls._proc.stdout.readline())
        except (OSError, json.JSONDecodeError, ValueError):
            cls._failed = True
            return None
        return None if "error" in res else res


class RawHistoryRAG(Technique):
    name = "raw_rag"
    source = "Raw-history RAG: Memory Tax (2610.34073), Naive RAG Is Stronger (2610.30755), MemoryTax (2610.29823)"
    provenance = "our implementation of the published settings (no RAG code released)"
    cache_safe = True  # recall goes into the first message only

    def __init__(self, mode: str = "memtax", k: int = 10, n_bm25: int = 10, n_dense: int = 10,
                 chunk_chars: int = 1024, max_turn_chars: int = 8192, overlap_chars: int = 1024,
                 budget: float = 0.15, rerank: bool = True, default_window: int = 200_000):
        self.mode = str(mode)
        self.k = int(k)
        self.n_bm25, self.n_dense = int(n_bm25), int(n_dense)
        self.chunk_chars, self.max_turn_chars, self.overlap_chars = int(chunk_chars), int(max_turn_chars), \
            int(overlap_chars)
        self.budget = float(budget)
        self.rerank = bool(rerank)
        self.default_window = int(default_window)
        self._session = 0
        self._log: list[str] = []
        self._chunks: list[dict] = []  # {"session", "text", "turns": [turn ids]}
        self._turns: list[dict] = []  # {"session", "i", "text"} (bm25turns mode)
        self._vectors: list[list[float]] = []

    def describe(self):
        return f"raw_rag(mode={self.mode}, k={self.k}, budget={self.budget}, rerank={self.rerank})"

    # ---- logging the raw session --------------------------------------------------------------------------
    def on_session_start(self, ctx):
        self._session += 1
        self._log = [f"[task] {ctx.task}"]
        if self._session > 1 and (self._chunks or self._turns):
            window = ctx.context_limit or getattr(ctx.model, "context_window", None) or self.default_window
            text, n, backend = self._retrieve(ctx.task, int(self.budget * window))
            if text:
                ctx.preamble.append(RECALL.format(text=text))
            ctx.log("raw_rag_recall", chunks=n, tokens=estimate_tokens(text), backend=backend)

    def after_call(self, ctx, resp):
        for b in resp.message["content"]:
            if b.get("text", "").strip():
                self._log.append(f"[assistant] {b['text'].strip()}")
            elif "toolUse" in b:
                tu = b["toolUse"]
                self._log.append(f"[call] {tu['name']}({json.dumps(tu.get('input') or {}, sort_keys=True)})")

    def on_tool_result(self, ctx, outcome):
        self._log.append(f"[result] {outcome.text}")
        return outcome

    # ---- indexing ------------------------------------------------------------------------------------------
    def _session_chunks(self) -> list[str]:
        header = f"[Session {self._session}]"
        units: list[str] = []
        for t in self._log:
            if len(t) > self.max_turn_chars:
                step = self.max_turn_chars - self.overlap_chars
                units.extend(t[s: s + self.max_turn_chars] for s in range(0, len(t), step))
            else:
                units.append(t)
        chunks, buf = [], []
        for u in units:
            if len(u) >= self.chunk_chars:  # long turns stay separate
                if buf:
                    chunks.append("\n".join(buf))
                    buf = []
                chunks.append(u)
                continue
            if buf and sum(map(len, buf)) + len(u) > self.chunk_chars:
                chunks.append("\n".join(buf))
                buf = [buf[-1]]  # the last turn carries over as overlap
            buf.append(u)
        if buf:
            chunks.append("\n".join(buf))
        return [f"{header}\n{c}" for c in chunks]

    def on_session_end(self, ctx, answer):
        if answer and not any(answer.strip()[:200] in t for t in self._log[-3:]):
            self._log.append(f"[assistant] {answer.strip()}")
        for i, t in enumerate(self._log):
            self._turns.append({"session": self._session, "i": i, "text": f"[Session {self._session}] {t}"})
        new = self._session_chunks()
        self._chunks.extend({"session": self._session, "text": c} for c in new)
        if self.mode == "memtax":
            res = _Sidecar.call({"op": "embed", "texts": [c[:2000] for c in new]})
            if res is not None:
                self._vectors.extend(res["vectors"])
        ctx.log("raw_rag_index", chunks=len(new), total=len(self._chunks))

    # ---- retrieval -----------------------------------------------------------------------------------------
    def _retrieve(self, query: str, budget_tokens: int) -> tuple[str, int, str]:
        if self.mode == "bm25turns":
            texts = [t["text"] for t in self._turns]
            hits = _BM25(texts).top(query, 8)
            picked: list[int] = []
            for h in hits:
                s = self._turns[h]["session"]
                for j in range(h - 2, h + 3):
                    if 0 <= j < len(self._turns) and self._turns[j]["session"] == s and j not in picked:
                        picked.append(j)
            return self._pack([texts[j] for j in picked], budget_tokens), len(picked), "bm25"
        texts = [c["text"] for c in self._chunks]
        cand = _BM25(texts).top(query, self.n_bm25)
        backend = "bm25"
        if len(self._vectors) == len(texts):
            q = _Sidecar.call({"op": "embed", "texts": [query[:2000]]})
            if q is not None:
                qv = q["vectors"][0]
                sims = sorted(((-sum(a * b for a, b in zip(qv, v)), i) for i, v in enumerate(self._vectors)))
                cand = list(dict.fromkeys(cand + [i for _, i in sims[: self.n_dense]]))
                backend = "bm25+dense"
        order = cand
        if self.rerank and backend != "bm25" and cand:
            r = _Sidecar.call({"op": "rerank", "query": query[:2000], "docs": [texts[i][:2000] for i in cand]})
            if r is not None:
                order = [i for _, i in sorted(zip((-s for s in r["scores"]), cand))]
                backend += "+rerank"
        order = order[: self.k]
        return self._pack([texts[i] for i in order], budget_tokens), len(order), backend

    @staticmethod
    def _pack(texts: list[str], budget_tokens: int) -> str:
        out, used = [], 0
        for t in texts:
            n = estimate_tokens(t)
            if used + n > budget_tokens:
                continue
            out.append(t)
            used += n
        return "\n\n---\n\n".join(out)
