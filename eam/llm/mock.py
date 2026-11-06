"""Offline backend: deterministic scripted policies + simulated prefix caching.

The mock does NOT measure how well a real model copes with a technique. It
exists to (1) validate that every technique produces conversations Bedrock
would accept, (2) compare token/cost/cache behaviour offline, and (3) give a
rough *information-retention* signal: task oracles answer only from facts that
are still visible in the context they receive.
"""

from __future__ import annotations

import itertools
import re
from typing import Any, Callable, Iterator

from eam.llm.cache_sim import PrefixCacheSimulator
from eam.llm.render import render_converse, validate_messages
from eam.llm.types import Message, Request, Response, Usage
from eam.tokens import estimate_block_tokens, estimate_tokens

Policy = Callable[[Request], Message]

_ids = itertools.count(1)


def tool_use(name: str, input: dict[str, Any]) -> dict[str, Any]:
    return {"toolUse": {"toolUseId": f"tu_{next(_ids):06d}", "name": name, "input": input}}


def assistant(*blocks: dict[str, Any]) -> Message:
    return {"role": "assistant", "content": list(blocks)}


def final(text: str) -> Message:
    return assistant({"text": text})


def block_text(block: dict[str, Any]) -> str:
    if "text" in block:
        return block["text"]
    if "toolResult" in block:
        return "\n".join(c.get("text", "") for c in block["toolResult"]["content"])
    if "toolUse" in block:
        return f"{block['toolUse']['name']}({block['toolUse']['input']})"
    return ""


def context_text(req: Request) -> str:
    parts = [b.get("text", "") for b in req.system]
    for msg in req.messages:
        parts.extend(block_text(b) for b in msg["content"])
    return "\n".join(parts)


def last_user_text(req: Request) -> str:
    for msg in reversed(req.messages):
        if msg["role"] == "user":
            return "\n".join(block_text(b) for b in msg["content"])
    return ""


def tool_exchanges(messages: list[Message]) -> Iterator[tuple[str, dict[str, Any], str]]:
    """Yield (tool name, input, result text) for every visible tool call."""
    uses: dict[str, dict[str, Any]] = {}
    for msg in messages:
        for b in msg["content"]:
            if "toolUse" in b:
                uses[b["toolUse"]["toolUseId"]] = b["toolUse"]
            elif "toolResult" in b:
                tu = uses.get(b["toolResult"]["toolUseId"])
                if tu:
                    yield tu["name"], tu["input"], block_text(b)


_FIRST_PERSON = re.compile(r"\b(i|i'm|my|me|prefer|always|allergic)\b", re.I)
_PROPER_PAIR = re.compile(r"\b[A-Z][a-z]+ [A-Z][a-z]+\b")


def extractive_aux(req: Request) -> Message:
    """Stand-in for summarise / extract / memory-update calls: keep the most
    fact-like sentences (numbers, first-person statements, proper nouns)."""
    text = last_user_text(req)
    sentences = [s.strip() for s in re.split(r"(?<=[.!?])\s+|\n+", text) if s.strip()]
    def score(s: str) -> float:
        return (2.0 if re.search(r"\d", s) else 0.0) + (2.0 if _FIRST_PERSON.search(s) else 0.0) \
            + (2.0 if _PROPER_PAIR.search(s) else 0.0) + 0.1 * len(re.findall(r"\b[A-Z][a-z]+", s))
    ranked = sorted(range(len(sentences)), key=lambda i: -score(sentences[i]))
    budget = req.max_tokens
    keep: set[int] = set()
    for i in ranked:
        if score(sentences[i]) < 2.0:
            break
        cost = estimate_tokens(sentences[i])
        if cost > budget:
            continue
        keep.add(i)
        budget -= cost
    return final("\n".join(sentences[i] for i in sorted(keep)) or "(nothing relevant)")


class MockLLM:
    def __init__(self, policy: Policy, aux_policy: Policy = extractive_aux, ttl_s: float = 300.0,
                 validate: bool = True, prompt_cache: bool = True):
        self.policy = policy
        self.prompt_cache = prompt_cache
        self.aux_policy = aux_policy
        self.ttl_s = ttl_s
        self.validate = validate
        self._caches: dict[str, PrefixCacheSimulator] = {}

    def converse(self, req: Request) -> Response:
        kwargs = render_converse(req)
        if self.validate:
            validate_messages(req.messages, bool(req.tools))
        policy = self.policy if req.tag in ("main", "subagent") else self.aux_policy
        msg = policy(req)
        if req.model.supports_cache and self.prompt_cache:
            sim = self._caches.setdefault(req.model.key, PrefixCacheSimulator(req.model.min_cache_tokens, self.ttl_s))
            uncached, read, write = sim.account(kwargs)
        else:
            uncached, read, write = _total_tokens(kwargs), 0, 0
        out_tokens = estimate_block_tokens(msg["content"])
        usage = Usage(uncached, out_tokens, read, write)
        # Indicative latency only: prefill cost per uncached token, cheaper for cached, plus decode.
        latency = 150 + 0.03 * (uncached + write) + 0.003 * read + 8 * out_tokens
        stop = "tool_use" if any("toolUse" in b for b in msg["content"]) else "end_turn"
        return Response(msg, stop, usage, latency, req.model.key)


def _total_tokens(kwargs: dict[str, Any]) -> int:
    total = 0
    for tool in kwargs.get("toolConfig", {}).get("tools", []):
        if "cachePoint" not in tool:
            total += estimate_block_tokens(tool)
    for block in kwargs.get("system", []):
        if "cachePoint" not in block:
            total += estimate_block_tokens(block)
    for msg in kwargs.get("messages", []):
        for block in msg["content"]:
            if "cachePoint" not in block:
                total += estimate_block_tokens({"role": msg["role"], **block})
    return total
