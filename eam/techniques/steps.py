"""Step view of a Converse conversation, shared by trajectory-reduction techniques.

A *step* is one assistant message plus the user message that carries its tool
results: messages[1 + 2k] and messages[2 + 2k] (messages[0] is the task).
`serialize_step` reproduces the AgentDiet artifact's format (expert.py,
extract_step_into_traj): <step id="k"><think>…</think><call tool="…">…</call><result>…</result></step>.
"""

from __future__ import annotations

import json
from functools import lru_cache

from eam.llm.types import Message
from eam.tokens import estimate_tokens


@lru_cache(maxsize=1)
def _encoder():
    try:
        import tiktoken

        return tiktoken.encoding_for_model("gpt-4o")  # the AgentDiet artifact counts with this encoding
    except Exception:
        return None


def count_tokens(text: str) -> int:
    enc = _encoder()
    return len(enc.encode(text)) if enc else estimate_tokens(text)


def step_indices(messages: list[Message]) -> list[tuple[int, int | None]]:
    """(assistant index, tool-result user index or None) for every step after the task message."""
    out = []
    i = 1
    while i < len(messages):
        if messages[i]["role"] != "assistant":
            i += 1
            continue
        nxt = i + 1 if i + 1 < len(messages) and messages[i + 1]["role"] == "user" else None
        out.append((i, nxt))
        i += 2
    return out


def completed_steps(messages: list[Message]) -> int:
    """Number of steps whose tool results are already in the history."""
    return sum(1 for _, u in step_indices(messages) if u is not None)


def serialize_step(messages: list[Message], k: int, originals: dict[int, str] | None = None) -> str:
    if k == -1:
        return "\n".join(b.get("text", "") for b in messages[0]["content"])
    if originals and k in originals:  # the artifact shows the original text of already-compressed steps
        return originals[k]
    a, u = step_indices(messages)[k]
    out = [f'<step id="{k}">']
    for b in messages[a]["content"]:
        if b.get("text", "").strip():
            out.append(f"<think>{b['text']}</think>")
        elif "toolUse" in b:
            tu = b["toolUse"]
            out.append(f'<call tool="{tu["name"]}">{json.dumps(tu.get("input") or {})}</call>')
    if u is not None:
        for b in messages[u]["content"]:
            if "toolResult" in b:
                text = "\n".join(c.get("text", "") for c in b["toolResult"]["content"])
                out.append(f"<result>{text}</result>")
            elif b.get("text", "").strip():
                out.append(f"<user>{b['text']}</user>")
    out.append("</step>")
    return "\n".join(out)
