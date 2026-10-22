"""Cache-first layout — Manus, "Context Engineering for AI Agents" (Yichao Ji).

* stable prefix: tools + system never change between calls (enforced by the
  loop; this technique warns if it is violated);
* append-only history (any rewrite is counted by the loop as a cache break);
* cachePoints on tools, system, and a rolling one on the newest message so
  each call reads the whole previous conversation from cache.
"""

from __future__ import annotations

import hashlib
import json

from eam.llm.types import CachePlan
from eam.techniques.base import Technique


class CacheLayout(Technique):
    name = "cache_layout"
    source = "Manus context engineering (KV-cache hit rate first)"
    provenance = "engineering rules from the Manus blog (no paper)"

    def __init__(self, rolling: bool = True, cache_tools: bool = True, cache_system: bool = True):
        self.rolling = rolling
        self.cache_tools = cache_tools
        self.cache_system = cache_system
        self._prefix_hash: str | None = None

    def render(self, ctx, req):
        if not req.model.supports_cache:
            return req
        prefix = hashlib.sha1(json.dumps([req.system, [t.to_converse() for t in req.tools]], sort_keys=True).encode()).hexdigest()
        if self._prefix_hash and prefix != self._prefix_hash:
            ctx.log("prefix_changed")  # e.g. a timestamp or reordered tools in the system prompt
        self._prefix_hash = prefix

        plan = CachePlan(tools=self.cache_tools and bool(req.tools), system=self.cache_system)
        if self.rolling and req.messages:
            # Keep the previous rolling point too, so a hit survives one extra appended turn.
            idx = [len(req.messages) - 1]
            if len(req.messages) >= 3:
                idx.insert(0, len(req.messages) - 3)
            plan.message_indices = idx[: 4 - plan.count()]
        req.cache = plan
        return req
