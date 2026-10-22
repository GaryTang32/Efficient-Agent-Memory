"""Render a ``Request`` into Bedrock Converse keyword arguments, and validate it."""

from __future__ import annotations

import copy
from typing import Any

from eam.llm.types import Message, Request

CACHE_POINT = {"cachePoint": {"type": "default"}}
MAX_CACHE_POINTS = 4


def render_converse(req: Request) -> dict[str, Any]:
    if req.cache.count() > MAX_CACHE_POINTS:
        raise ValueError(f"Bedrock allows at most {MAX_CACHE_POINTS} cache points, got {req.cache.count()}")

    messages = copy.deepcopy(req.messages)
    for idx in req.cache.message_indices:
        messages[idx]["content"].append(dict(CACHE_POINT))

    kwargs: dict[str, Any] = {"modelId": req.model.model_id, "messages": messages}

    inference: dict[str, Any] = {"maxTokens": req.max_tokens}
    if req.temperature is not None:
        inference["temperature"] = req.temperature
    kwargs["inferenceConfig"] = inference

    if req.system:
        system = list(req.system)
        if req.cache.system:
            system.append(dict(CACHE_POINT))
        kwargs["system"] = system

    if req.tools:
        tools: list[dict[str, Any]] = [t.to_converse() for t in req.tools]
        if req.cache.tools:
            tools.append(dict(CACHE_POINT))
        kwargs["toolConfig"] = {"tools": tools}

    if req.extra:
        kwargs["additionalModelRequestFields"] = req.extra
    return kwargs


def validate_messages(messages: list[Message], has_tools: bool) -> None:
    """Raise if Bedrock would reject the conversation shape.

    Catches the bugs history-rewriting techniques tend to introduce: broken
    role alternation and orphaned toolResult blocks.
    """
    if not messages:
        raise ValueError("conversation is empty")
    if messages[0]["role"] != "user":
        raise ValueError("conversation must start with a user message")
    pending: set[str] = set()
    for i, msg in enumerate(messages):
        if i and msg["role"] == messages[i - 1]["role"]:
            raise ValueError(f"message {i}: roles must alternate")
        if not msg.get("content"):
            raise ValueError(f"message {i}: empty content")
        uses = {b["toolUse"]["toolUseId"] for b in msg["content"] if "toolUse" in b}
        results = {b["toolResult"]["toolUseId"] for b in msg["content"] if "toolResult" in b}
        if (uses or results) and not has_tools:
            raise ValueError(f"message {i}: tool blocks present but no toolConfig")
        if msg["role"] == "user":
            if results != pending and (results or pending):
                raise ValueError(f"message {i}: toolResults {sorted(results)} do not match toolUses {sorted(pending)}")
            pending = set()
        else:
            if results:
                raise ValueError(f"message {i}: assistant message cannot carry toolResult")
            pending = uses
    if messages[-1]["role"] != "user":
        raise ValueError("conversation must end with a user message")
