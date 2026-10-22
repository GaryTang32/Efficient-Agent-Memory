"""Conversion between this repo's Converse-shaped Request/Response and the
OpenAI Chat Completions wire format (both directions).

Used by ``OpenAICompatClient`` (Request -> OpenAI -> Response) and by the
local gateway (OpenAI -> Request -> backend -> OpenAI).
"""

from __future__ import annotations

import json
import time
import uuid
from typing import Any

from eam.llm.types import Message, Request, Response, ToolSpec, Usage

EPHEMERAL = {"type": "ephemeral"}


def _text_part(text: str, cache: bool) -> dict[str, Any]:
    part: dict[str, Any] = {"type": "text", "text": text}
    if cache:
        part["cache_control"] = dict(EPHEMERAL)
    return part


def to_openai_payload(req: Request, model_id: str, *, cache_control: bool = False,
                      max_tokens_field: str = "max_tokens") -> dict[str, Any]:
    """Render a Request as a /chat/completions body.

    ``cache_control=True`` adds Anthropic-style ``cache_control`` markers where the
    CachePlan puts Converse cachePoints; LiteLLM translates them to Bedrock cache
    points for models that support caching. Plain OpenAI-compatible servers ignore them.
    """
    msgs: list[dict[str, Any]] = []
    system_text = "\n\n".join(b["text"] for b in req.system if "text" in b)
    if system_text:
        if cache_control and req.cache.system:
            msgs.append({"role": "system", "content": [_text_part(system_text, True)]})
        else:
            msgs.append({"role": "system", "content": system_text})

    cache_idx = set(req.cache.message_indices) if cache_control else set()
    for i, m in enumerate(req.messages):
        mark = i in cache_idx
        texts = [b["text"] for b in m["content"] if "text" in b]
        if m["role"] == "assistant":
            calls = [{
                "id": b["toolUse"]["toolUseId"],
                "type": "function",
                "function": {"name": b["toolUse"]["name"],
                             "arguments": json.dumps(b["toolUse"].get("input") or {}, sort_keys=True)},
            } for b in m["content"] if "toolUse" in b]
            out: dict[str, Any] = {"role": "assistant", "content": "\n".join(texts) or None}
            if calls:
                out["tool_calls"] = calls
            msgs.append(out)
            continue
        results = [b["toolResult"] for b in m["content"] if "toolResult" in b]
        for j, tr in enumerate(results):
            text = "\n".join(c.get("text", "") for c in tr.get("content", []))
            last = mark and j == len(results) - 1 and not texts
            msgs.append({"role": "tool", "tool_call_id": tr["toolUseId"],
                         "content": [_text_part(text, True)] if last else text})
        if texts:
            text = "\n".join(texts)
            msgs.append({"role": "user", "content": [_text_part(text, True)] if mark else text})

    body: dict[str, Any] = {"model": model_id, "messages": msgs, max_tokens_field: req.max_tokens}
    if req.temperature is not None:
        body["temperature"] = req.temperature
    if req.tools:
        body["tools"] = [{"type": "function", "function": {
            "name": t.name, "description": t.description, "parameters": t.input_schema}} for t in req.tools]
    return body


def parse_openai_usage(u: dict[str, Any] | None) -> Usage:
    """Normalise usage from OpenAI, LiteLLM (Anthropic/Bedrock passthrough) or Mantle responses."""
    u = u or {}
    prompt = int(u.get("prompt_tokens") or 0)
    details = u.get("prompt_tokens_details") or {}
    read = int(u.get("cache_read_input_tokens") or details.get("cached_tokens") or 0)
    write = int(u.get("cache_creation_input_tokens") or details.get("cache_creation_tokens") or 0)
    # OpenAI semantics: prompt_tokens includes cached tokens.
    return Usage(max(0, prompt - read - write), int(u.get("completion_tokens") or 0), read, write)


def from_openai_response(data: dict[str, Any], model_key: str, latency_ms: float) -> Response:
    choice = (data.get("choices") or [{}])[0]
    msg = choice.get("message") or {}
    content: list[dict[str, Any]] = []
    text = msg.get("content")
    if isinstance(text, list):
        text = "".join(p.get("text", "") for p in text if isinstance(p, dict))
    if text:
        content.append({"text": text})
    for call in msg.get("tool_calls") or []:
        fn = call.get("function") or {}
        try:
            args = json.loads(fn.get("arguments") or "{}")
        except json.JSONDecodeError:
            args = {"input": fn.get("arguments")}
        content.append({"toolUse": {"toolUseId": call.get("id") or f"call_{uuid.uuid4().hex[:8]}",
                                    "name": fn.get("name", ""), "input": args}})
    if not content:
        content.append({"text": ""})
    finish = choice.get("finish_reason") or "stop"
    stop = {"tool_calls": "tool_use", "stop": "end_turn", "length": "max_tokens"}.get(finish, finish)
    if any("toolUse" in b for b in content):
        stop = "tool_use"
    return Response({"role": "assistant", "content": content}, stop, parse_openai_usage(data.get("usage")),
                     latency_ms, model_key)


# ---- the other direction (gateway) -------------------------------------------------


def _content_text(content: Any) -> str:
    if content is None:
        return ""
    if isinstance(content, str):
        return content
    return "".join(p.get("text", "") for p in content if isinstance(p, dict) and p.get("type") in (None, "text"))


def request_from_openai(body: dict[str, Any], model) -> Request:
    """Build a Request from a /chat/completions body (system, user, assistant tool_calls, tool results)."""
    system: list[dict[str, Any]] = []
    messages: list[Message] = []

    def push(role: str, blocks: list[dict[str, Any]]) -> None:
        if messages and messages[-1]["role"] == role:
            messages[-1]["content"].extend(blocks)
        else:
            messages.append({"role": role, "content": blocks})

    for m in body.get("messages", []):
        role = m.get("role")
        if role in ("system", "developer"):
            system.append({"text": _content_text(m.get("content"))})
        elif role == "user":
            push("user", [{"text": _content_text(m.get("content")) or " "}])
        elif role == "assistant":
            blocks: list[dict[str, Any]] = []
            text = _content_text(m.get("content"))
            if text:
                blocks.append({"text": text})
            for call in m.get("tool_calls") or []:
                fn = call.get("function") or {}
                try:
                    args = json.loads(fn.get("arguments") or "{}")
                except json.JSONDecodeError:
                    args = {"input": fn.get("arguments")}
                blocks.append({"toolUse": {"toolUseId": call.get("id"), "name": fn.get("name"), "input": args}})
            push("assistant", blocks or [{"text": " "}])
        elif role == "tool":
            push("user", [{"toolResult": {"toolUseId": m.get("tool_call_id"),
                                          "content": [{"text": _content_text(m.get("content"))}]}}])
    tools = [ToolSpec(t["function"]["name"], t["function"].get("description", ""),
                      t["function"].get("parameters") or {"type": "object", "properties": {}})
             for t in body.get("tools") or [] if t.get("type", "function") == "function"]
    max_tokens = body.get("max_completion_tokens") or body.get("max_tokens") or 2048
    return Request(model=model, system=system, messages=messages, tools=tools, max_tokens=int(max_tokens),
                   temperature=body.get("temperature"), tag="gateway")


def openai_response_from(resp: Response, model_name: str) -> dict[str, Any]:
    text = "".join(b["text"] for b in resp.message["content"] if "text" in b)
    calls = [{"id": b["toolUse"]["toolUseId"], "type": "function",
              "function": {"name": b["toolUse"]["name"], "arguments": json.dumps(b["toolUse"]["input"])}}
             for b in resp.message["content"] if "toolUse" in b]
    message: dict[str, Any] = {"role": "assistant", "content": text or (None if calls else "")}
    if calls:
        message["tool_calls"] = calls
    u = resp.usage
    return {
        "id": f"chatcmpl-{uuid.uuid4().hex[:24]}",
        "object": "chat.completion",
        "created": int(time.time()),
        "model": model_name,
        "choices": [{"index": 0, "message": message,
                     "finish_reason": "tool_calls" if calls else ("length" if resp.stop_reason == "max_tokens" else "stop")}],
        "usage": {
            "prompt_tokens": u.prompt_tokens,
            "completion_tokens": u.output_tokens,
            "total_tokens": u.prompt_tokens + u.output_tokens,
            "prompt_tokens_details": {"cached_tokens": u.cache_read_tokens},
            "cache_read_input_tokens": u.cache_read_tokens,
            "cache_creation_input_tokens": u.cache_write_tokens,
        },
    }
