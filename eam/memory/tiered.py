"""Persistent tiered memory store (MemoryOS-style mid/long tiers with heat)."""

from __future__ import annotations

import json
import math
from dataclasses import asdict, dataclass, field
from pathlib import Path

from eam.memory.embed import Embedder, HashingEmbedder, cosine


@dataclass
class MemoryRecord:
    id: str
    text: str
    tier: str = "mid"  # "mid" (retrieved by relevance) | "long" (always loaded, e.g. user profile)
    hits: int = 0
    created_session: int = 0
    last_session: int = 0
    vector: list[float] = field(default_factory=list)

    def heat(self, session: int, tau: float = 3.0) -> float:
        return self.hits + math.exp(-(session - self.last_session) / tau)


class TieredMemoryStore:
    def __init__(self, path: str | Path | None = None, embedder: Embedder | None = None,
                 mid_capacity: int = 200, promote_hits: int = 2, dedupe_threshold: float = 0.92):
        self.path = Path(path) if path else None
        self.embedder = embedder or HashingEmbedder()
        self.mid_capacity = mid_capacity
        self.promote_hits = promote_hits
        self.dedupe_threshold = dedupe_threshold
        self.session = 0
        self.records: list[MemoryRecord] = []
        if self.path and self.path.exists():
            data = json.loads(self.path.read_text())
            self.session = data["session"]
            self.records = [MemoryRecord(**r) for r in data["records"]]

    def save(self) -> None:
        if self.path:
            self.path.parent.mkdir(parents=True, exist_ok=True)
            self.path.write_text(json.dumps({"session": self.session, "records": [asdict(r) for r in self.records]}))

    def add(self, text: str) -> MemoryRecord:
        vec = self.embedder.embed([text])[0]
        for r in self.records:
            if r.vector and cosine(r.vector, vec) >= self.dedupe_threshold:
                r.hits += 1
                r.last_session = self.session
                return r
        rec = MemoryRecord(f"m{len(self.records) + 1:04d}", text, created_session=self.session,
                           last_session=self.session, vector=vec)
        self.records.append(rec)
        return rec

    def search(self, query: str, k: int = 5, exclude: set[str] | None = None, min_score: float = 0.05) -> list[MemoryRecord]:
        qv = self.embedder.embed([query])[0]
        scored = [(cosine(qv, r.vector), r) for r in self.records
                  if r.tier == "mid" and r.vector and not (exclude and r.id in exclude)]
        scored.sort(key=lambda x: -x[0])
        hits = [r for s, r in scored[:k] if s >= min_score]
        for r in hits:
            r.hits += 1
            r.last_session = self.session
        return hits

    def long_term(self) -> list[MemoryRecord]:
        return [r for r in self.records if r.tier == "long"]

    def maintain(self) -> None:
        """Promote frequently used memories to the long tier; evict cold mid-tier ones."""
        for r in self.records:
            if r.tier == "mid" and r.hits >= self.promote_hits:
                r.tier = "long"
        mid = [r for r in self.records if r.tier == "mid"]
        if len(mid) > self.mid_capacity:
            mid.sort(key=lambda r: r.heat(self.session))
            evict = {r.id for r in mid[: len(mid) - self.mid_capacity]}
            self.records = [r for r in self.records if r.id not in evict]
