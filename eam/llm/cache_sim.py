"""Prefix-cache simulator mimicking Bedrock/Anthropic prompt-caching semantics.

Order of the cached prefix is tools -> system -> messages. A ``cachePoint``
writes the prefix up to that point (if it is at least ``min_tokens`` long);
a later request reads the longest previously written prefix found within
``lookback`` blocks before one of its own cache points.

Used by the mock backend so cache-related techniques can be compared offline,
and handy for predicting cache behaviour of a request layout before paying for it.
"""

from __future__ import annotations

import hashlib
import json
import time
from typing import Any, Callable

from eam.tokens import estimate_block_tokens


class PrefixCacheSimulator:
    def __init__(self, min_tokens: int = 1024, ttl_s: float = 300.0, lookback: int = 20,
                 clock: Callable[[], float] = time.monotonic):
        self.min_tokens = min_tokens
        self.ttl_s = ttl_s
        self.lookback = lookback
        self.clock = clock
        self._entries: dict[str, float] = {}  # prefix hash -> expiry time

    def account(self, kwargs: dict[str, Any]) -> tuple[int, int, int]:
        """Return (uncached_input, cache_read, cache_write) token counts for a rendered request."""
        hasher = hashlib.sha256()
        positions: list[tuple[str, int]] = []  # (prefix hash, prefix tokens) after each block
        cps: list[int] = []
        tokens = 0

        def add(block: Any) -> None:
            nonlocal tokens
            hasher.update(json.dumps(block, sort_keys=True, ensure_ascii=False).encode())
            tokens += estimate_block_tokens(block)
            positions.append((hasher.hexdigest(), tokens))

        def mark() -> None:
            if positions:
                cps.append(len(positions) - 1)

        for tool in kwargs.get("toolConfig", {}).get("tools", []):
            mark() if "cachePoint" in tool else add(tool)
        for block in kwargs.get("system", []):
            mark() if "cachePoint" in block else add(block)
        for msg in kwargs.get("messages", []):
            for block in msg["content"]:
                mark() if "cachePoint" in block else add({"role": msg["role"], **block})

        now = self.clock()
        self._entries = {h: exp for h, exp in self._entries.items() if exp > now}

        read = 0
        for cp in cps:
            for j in range(cp, max(-1, cp - self.lookback - 1), -1):
                h, t = positions[j]
                if h in self._entries:
                    if t > read:
                        read = t
                    self._entries[h] = now + self.ttl_s
                    break

        write = 0
        valid = [cp for cp in cps if positions[cp][1] >= self.min_tokens]
        if valid:
            write = max(0, positions[valid[-1]][1] - read)
            for cp in valid:
                self._entries[positions[cp][0]] = now + self.ttl_s

        return tokens - read - write, read, write
