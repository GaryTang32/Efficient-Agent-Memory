"""The AutoMemory MCP server against the official MCP Python client (stdio), offline: handshake, tool listing with
annotations, the note round trip across two connections, previews of offloaded text, and redaction."""

from __future__ import annotations

import asyncio
import os
import sys

import pytest

mcp = pytest.importorskip("mcp")
from mcp import ClientSession, StdioServerParameters  # noqa: E402
from mcp.client.stdio import stdio_client  # noqa: E402

SECRET = "AKIAIOSFODNN7EXAMPLE"


def _text(result) -> str:
    return "\n".join(c.text for c in result.content if getattr(c, "type", "") == "text")


async def _session(root, body):
    env = {**os.environ, "EAM_MEMORY_DIR": str(root), "EAM_MEMORY_WINDOW": "40000"}
    params = StdioServerParameters(command=sys.executable, args=["-m", "eam.mcp_server"], env=env)
    async with stdio_client(params) as (read, write):
        async with ClientSession(read, write) as session:
            init = await session.initialize()
            return init, await body(session)


def test_official_client_round_trip(tmp_path):
    async def first(s):
        tools = (await s.list_tools()).tools
        await s.call_tool("write_note", {"name": "widget stock", "content": f"42 widgets; key {SECRET}",
                                         "type": "fact"})
        await s.call_tool("save_session", {"answer": "Day 1 done: 42 widgets."})
        offloaded = _text(await s.call_tool("offload", {"text": "x" * 50_000, "label": "big"}))
        return tools, offloaded

    async def second(s):
        return _text(await s.call_tool("recall", {})), _text(await s.call_tool("read_notes", {"name": "nope"}))

    init, (tools, offloaded) = asyncio.run(_session(tmp_path, first))
    assert init.protocol_version in ("2025-11-25", "2025-06-18", "2025-03-26", "2024-11-05")
    assert "recall" in (init.instructions or "")
    by = {t.name: t for t in tools}
    assert {"write_note", "read_notes", "read_artifact", "recall", "save_session"} <= set(by)
    assert by["read_notes"].annotations.read_only_hint is True
    assert by["write_note"].annotations.read_only_hint is False
    assert offloaded.startswith("artifact://")

    _, (recall, missing) = asyncio.run(_session(tmp_path, second))
    assert "42 widgets" in recall and "<memory" in recall and "Day 1 done" in recall
    assert SECRET not in recall, "the secret was stored unredacted"
    assert "Error" in missing or "no note" in missing
