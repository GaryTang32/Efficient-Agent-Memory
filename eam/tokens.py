"""Cheap token estimation used for triggers and by the offline mock backend.

Real runs on Bedrock use the exact counts Bedrock returns in ``usage``; this
estimate is only for decisions made *before* a call (e.g. "is this tool output
big enough to offload?") and for the mock.
"""

from __future__ import annotations

import json
import math
from typing import Any

CHARS_PER_TOKEN = 4.0


def estimate_tokens(text: str) -> int:
    if not text:
        return 0
    return math.ceil(len(text) / CHARS_PER_TOKEN)


def estimate_block_tokens(block: Any) -> int:
    if isinstance(block, str):
        return estimate_tokens(block)
    return estimate_tokens(json.dumps(block, sort_keys=True, ensure_ascii=False))


def truncate_to_tokens(text: str, max_tokens: int) -> str:
    max_chars = int(max_tokens * CHARS_PER_TOKEN)
    return text if len(text) <= max_chars else text[:max_chars]
