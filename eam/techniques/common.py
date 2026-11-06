"""Helpers shared by several techniques."""

from __future__ import annotations

from eam.agent.context import AgentContext, Tool
from eam.llm.types import ToolSpec


def read_artifact_tool() -> Tool:
    """Lets the agent recover content that was offloaded, cleared or compressed."""

    def handler(args: dict, ctx: AgentContext) -> str:
        aid = str(args.get("artifact_id", "")).removeprefix("artifact://")
        text = ctx.store.get(aid)
        if text is None:
            raise ValueError(f"no artifact '{aid}'")
        offset = int(args.get("offset", 0))
        length = int(args.get("length", 12000))
        chunk = text[offset : offset + length]
        rest = len(text) - offset - len(chunk)
        return chunk + (f"\n…[{rest} more chars; call read_artifact with offset={offset + len(chunk)}]" if rest > 0 else "")

    return Tool(
        ToolSpec(
            "read_artifact",
            "Read the full content behind an artifact://ID pointer (content that was moved out of the "
            "context to save space). Use offset/length (characters) to page through long artifacts.",
            {
                "type": "object",
                "properties": {
                    "artifact_id": {"type": "string", "description": "e.g. artifact://a0003"},
                    "offset": {"type": "integer", "default": 0},
                    "length": {"type": "integer", "default": 12000},
                },
                "required": ["artifact_id"],
            },
        ),
        handler,
    )


def last_results_text(ctx: AgentContext, max_chars: int = 3000) -> str:
    """Text of the most recent tool results (the latest observation)."""
    for msg in reversed(ctx.messages):
        if msg["role"] == "user" and any("toolResult" in b for b in msg["content"]):
            return ctx.transcript([msg], max_result_chars=max_chars)
    return ""
