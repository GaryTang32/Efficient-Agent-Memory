"""Text tool-calling protocol for backends without native tool calls.

Used by the Claude Code CLI backend (its own tools are switched off) and by the
OpenAI-compatible gateway when it fronts such a backend. The model is told to
emit ``<tool_call>{"name": ..., "arguments": {...}}</tool_call>`` blocks; the
same convention is used by several Chinese-lab agent repos (e.g. Tongyi
DeepResearch, FoldAgent) for text-only tool calling.
"""

from __future__ import annotations

import itertools
import json
import re
from typing import Any

from eam.llm.types import Message, ToolSpec

_ids = itertools.count(1)
TOOL_CALL_RE = re.compile(r"<tool_call>\s*(.*?)\s*</tool_call>", re.S)
# Formats models fall back to when tools are described in text:
INVOKE_RE = re.compile(r'<invoke name="([^"]+)">(.*?)</invoke>', re.S)            # Anthropic-style XML
INVOKE_PARAM_RE = re.compile(r'<parameter name="([^"]+)">(.*?)</parameter>', re.S)
FUNCTION_RE = re.compile(r"<function=([\w.-]+)>(.*?)</function>", re.S)          # FoldAgent / Qwen-coder style
FUNCTION_PARAM_RE = re.compile(r"<parameter=([\w.-]+)>\s*(.*?)\s*</parameter>", re.S)
# Degenerate XML with the tool name missing: <invoke:parameter name="query">…</parameter></invoke>
NAMELESS_PARAM_RE = re.compile(r'<(?:invoke:)?parameter name="([^"]+)">(.*?)</parameter>', re.S)
STRAY_TAGS_RE = re.compile(r"</?(function_calls|reasoning_effort)[^>]*>.*?(?=\n|$)", re.S)


def _param_value(raw: str):
    raw = raw.strip()
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        return raw


def tool_instructions(tools: list[ToolSpec]) -> str:
    specs = "\n".join(
        json.dumps({"name": t.name, "description": t.description, "parameters": t.input_schema}, sort_keys=True)
        for t in tools
    )
    return (
        "# Tools\n"
        "You can call the tools below. To call one, output a block exactly like\n"
        '<tool_call>{"name": "<tool name>", "arguments": {<arguments as JSON>}}</tool_call>\n'
        "You may output several <tool_call> blocks in one reply. After your tool calls, stop and wait: the results "
        "arrive in the next turn inside <tool_result> blocks. Never write a <tool_result> yourself. "
        "When you need no more tools, reply with your final answer and no <tool_call> block.\n\n"
        f"Available tools (JSON schemas):\n{specs}"
    )


def transcript_preamble() -> str:
    return (
        "The conversation so far is given below as a transcript of <user>, <assistant> and <tool_result> blocks. "
        "Write only the next <assistant> turn's content (without the <assistant> tag)."
    )


def render_message_blocks(messages: list[Message]) -> list[str]:
    """One text block per content block, so prompt caches can hit at block boundaries."""
    blocks: list[str] = []
    for msg in messages:
        role = msg["role"]
        for b in msg["content"]:
            if "text" in b:
                blocks.append(f"<{role}>\n{b['text']}\n</{role}>")
            elif "toolUse" in b:
                tu = b["toolUse"]
                call = json.dumps({"name": tu["name"], "arguments": tu.get("input") or {}}, sort_keys=True)
                blocks.append(f"<assistant>\n<tool_call>{call}</tool_call>\n</assistant>")
            elif "toolResult" in b:
                tr = b["toolResult"]
                text = "\n".join(c.get("text", "") for c in tr.get("content", []))
                blocks.append(f'<tool_result id="{tr["toolUseId"]}">\n{text}\n</tool_result>')
            # reasoningContent and cachePoint blocks are not rendered
    return blocks


def _infer_tool(params: dict[str, Any], tools) -> str | None:
    """The one tool whose schema accepts exactly these parameters (all required present, none unknown)."""
    fits = []
    for t in tools or []:
        props = set((t.input_schema or {}).get("properties", {}))
        required = set((t.input_schema or {}).get("required", []))
        if params and required <= set(params) <= props:
            fits.append(t.name)
    return fits[0] if len(fits) == 1 else None


def parse_tool_calls(text: str, tools=None) -> tuple[str, list[dict[str, Any]]]:
    """Split model output into (visible text, Converse toolUse blocks). With `tools` (ToolSpecs), a call whose
    tool name is missing is recovered when its parameters fit exactly one tool."""
    uses = []
    for m in TOOL_CALL_RE.finditer(text):
        raw = m.group(1)
        try:
            obj = json.loads(raw)
        except json.JSONDecodeError:
            # tolerate a trailing comment or code fence around the JSON
            inner = raw[raw.find("{"): raw.rfind("}") + 1]
            try:
                obj = json.loads(inner)
            except json.JSONDecodeError:
                continue
        name = obj.get("name")
        if not name:
            continue
        args = obj.get("arguments", obj.get("input", {}))
        if isinstance(args, str):
            try:
                args = json.loads(args)
            except json.JSONDecodeError:
                args = {"input": args}
        uses.append({"toolUse": {"toolUseId": f"tc_{next(_ids):06d}", "name": name, "input": args or {}}})
    if not uses:
        for name, body in INVOKE_RE.findall(text):
            args = {k: _param_value(v) for k, v in INVOKE_PARAM_RE.findall(body)}
            uses.append({"toolUse": {"toolUseId": f"tc_{next(_ids):06d}", "name": name, "input": args}})
        for name, body in FUNCTION_RE.findall(text):
            args = {k: _param_value(v) for k, v in FUNCTION_PARAM_RE.findall(body)}
            uses.append({"toolUse": {"toolUseId": f"tc_{next(_ids):06d}", "name": name, "input": args}})
    if not uses and tools:
        for chunk in text.split("</invoke>"):
            args = {k: _param_value(v) for k, v in NAMELESS_PARAM_RE.findall(chunk)}
            name = _infer_tool(args, tools)
            if name:
                uses.append({"toolUse": {"toolUseId": f"tc_{next(_ids):06d}", "name": name, "input": args}})
        if uses:
            text = NAMELESS_PARAM_RE.sub("", text).replace("</invoke>", "")
    visible = FUNCTION_RE.sub("", INVOKE_RE.sub("", TOOL_CALL_RE.sub("", text)))
    visible = STRAY_TAGS_RE.sub("", visible)
    # models sometimes keep writing a fake result after the call: drop anything from a <tool_result> on
    visible = visible.split("<tool_result", 1)[0].strip()
    return visible, uses
