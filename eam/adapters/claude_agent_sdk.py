"""AutoMemory for the Claude Agent SDK (`claude-agent-sdk`): Python hook callbacks and in-process memory tools.

    from claude_agent_sdk import ClaudeAgentOptions, query
    from eam.adapters.claude_agent_sdk import AgentMemory

    mem = AgentMemory("~/.eam-memory/project-x")
    options = mem.apply(ClaudeAgentOptions())   # or ClaudeAgentOptions(**mem.options())
    async for message in query(prompt="Count the widgets for day 2.", options=options):
        mem.observe(message)              # optional: real prompt sizes for the in-step guard

What `apply` / `options` add, all through fields the SDK defines (claude_agent_sdk/types.py):

- system_prompt   the note rules and the <memory>-is-data rule, appended to Claude Code's preset (or your prompt)
- mcp_servers     write_note, read_notes, read_artifact as the in-process SDK MCP server "automem"
                  (Claude sees them as mcp__automem__write_note, ...); allowed_tools lets them run without a prompt
- UserPromptSubmit  recall: the first prompt of each session gets the notes as `additionalContext`. The Python SDK's
                  HookEvent has no SessionStart (and no PostCompact), so recall rides on the first prompt instead
- PreCompact      `systemMessage` = the handoff instructions; Claude Code uses a PreCompact callback's systemMessage
                  as extra compaction instructions, so its own summary keeps a handoff recap. The notes are recalled
                  again (as `additionalContext`) on the next prompt or tool result after the compaction
- PostToolUse     long outputs (MCP tools, plain-text outputs, Bash stdout/stderr) are replaced with a head + tail
                  preview through `updatedToolOutput`; the full, redacted text is an artifact read_artifact pages
- Stop            autosave: `last_assistant_message` is saved as the session's result (it supersedes the last one)

`wrap(tool)` makes one of your own `@tool` functions return the preview itself, for hosts where hooks are off.
Claude Code owns compaction in this host, so MemoryHooks.compact is never called here (the conformance driver sets
`compacts = False`).
"""

from __future__ import annotations

import dataclasses
from pathlib import Path
from typing import Any

from claude_agent_sdk import HookMatcher, SdkMcpTool, create_sdk_mcp_server, tool

from eam.adapters.base import MemoryHooks
from eam.automem.prompts import HANDOFF

PERSISTED_MAX = 20 * 2**20  # Claude Code's saved copy of a long Bash output is read only up to this size


def _text_blocks(blocks: Any) -> str | None:
    """The text of an MCP content list, or None if it holds anything but text blocks."""
    if not isinstance(blocks, list) or not all(isinstance(b, dict) and b.get("type") == "text" for b in blocks):
        return None
    return "\n".join(str(b.get("text", "")) for b in blocks)


class AgentMemory:
    """MemoryHooks wired into ClaudeAgentOptions. One object per agent; sessions are told apart by session_id."""

    def __init__(self, root: str | Path | None = None, *, hooks: MemoryHooks | None = None,
                 server_name: str = "automem", **hook_kwargs: Any):
        self.hooks = hooks if hooks is not None else MemoryHooks(root, **hook_kwargs)
        self.server_name = server_name
        self.prompt_tokens = 0                    # last real prompt size seen by observe()
        self._sessions: set[str] = set()          # sessions whose first prompt got the recall
        self._recall_due: set[str] = set()        # sessions compacted since their last recall
        self._wrapped: set[str] = set()           # outputs wrap() already previewed (the hook leaves them alone)

    # ---- options -------------------------------------------------------------------------------------------
    def tool_names(self) -> list[str]:
        """The memory tools as Claude Code names them: mcp__<server>__<tool>."""
        return [f"mcp__{self.server_name}__{t['name']}" for t in self.hooks.tool_specs()]

    def server(self) -> Any:
        """write_note, read_notes and read_artifact as an in-process SDK MCP server (McpSdkServerConfig)."""
        def make(spec: dict[str, Any]) -> SdkMcpTool[Any]:
            async def handler(args: dict[str, Any]) -> dict[str, Any]:
                out = self.hooks.call_tool(spec["name"], args)
                return {"content": [{"type": "text", "text": out}], "is_error": out.startswith("Error:")}
            return tool(spec["name"], spec["description"], spec["input_schema"])(handler)
        return create_sdk_mcp_server(self.server_name, tools=[make(s) for s in self.hooks.tool_specs()])

    def system_prompt(self, base: Any = None) -> Any:
        """`base` (a ClaudeAgentOptions.system_prompt value) with AutoMemory's rules appended."""
        rules = self.hooks.system_text()
        if base is None:
            return {"type": "preset", "preset": "claude_code", "append": rules}
        if isinstance(base, str):
            return self.hooks.system_text(base)
        if isinstance(base, dict) and base.get("type") == "preset":
            return {**base, "append": f"{base['append']}\n\n{rules}" if base.get("append") else rules}
        if isinstance(base, dict) and base.get("type") == "custom":
            return {**base, "prompt": self.hooks.system_text(base.get("prompt", ""))}
        raise TypeError(f"cannot append AutoMemory's rules to system_prompt {base!r}; append system_text() yourself")

    def hook_matchers(self) -> dict[str, list[HookMatcher]]:
        return {"UserPromptSubmit": [HookMatcher(hooks=[self.on_user_prompt])],
                "PostToolUse": [HookMatcher(hooks=[self.on_post_tool_use])],
                "PreCompact": [HookMatcher(hooks=[self.on_pre_compact])],
                "Stop": [HookMatcher(hooks=[self.on_stop])]}

    def options(self, system_prompt: Any = None) -> dict[str, Any]:
        """Keyword arguments for ClaudeAgentOptions (use `apply` to merge into options that have their own)."""
        return {"system_prompt": self.system_prompt(system_prompt), "mcp_servers": {self.server_name: self.server()},
                "allowed_tools": self.tool_names(), "hooks": self.hook_matchers()}

    def apply(self, options: Any) -> Any:
        """A copy of `options` (ClaudeAgentOptions) with the memory tools, hooks and rules merged in."""
        if not isinstance(options.mcp_servers, dict):
            raise TypeError("mcp_servers is a path or JSON string; merge options() into it yourself")
        hooks = {k: list(v) for k, v in (options.hooks or {}).items()}
        for event, matchers in self.hook_matchers().items():
            hooks.setdefault(event, []).extend(matchers)
        return dataclasses.replace(options, system_prompt=self.system_prompt(options.system_prompt),
                                   mcp_servers={**options.mcp_servers, self.server_name: self.server()},
                                   allowed_tools=[*options.allowed_tools, *self.tool_names()], hooks=hooks)

    # ---- your own tools ------------------------------------------------------------------------------------
    def wrap(self, sdk_tool: SdkMcpTool[Any]) -> SdkMcpTool[Any]:
        """Your `@tool` function, returning AutoMemory's preview of its text output instead of the full text."""
        inner = sdk_tool.handler

        async def handler(args: Any) -> dict[str, Any]:
            result = await inner(args)
            text = _text_blocks(result.get("content"))
            if text is None or result.get("is_error"):
                return result
            out = self._ingest(sdk_tool.name, text)
            if out != text:
                if len(self._wrapped) > 64:   # hooks are off: nothing will consume these
                    self._wrapped.clear()
                self._wrapped.add(out)
            return {**result, "content": [{"type": "text", "text": out}]}
        return dataclasses.replace(sdk_tool, handler=handler)

    def observe(self, message: Any) -> None:
        """Feed each streamed message: an AssistantMessage's usage is the real prompt size for the in-step guard."""
        usage = getattr(message, "usage", None)
        if type(message).__name__ == "AssistantMessage" and isinstance(usage, dict):
            self.prompt_tokens = sum(int(usage.get(k) or 0) for k in
                                     ("input_tokens", "cache_read_input_tokens", "cache_creation_input_tokens"))

    # ---- hook callbacks (HookCallback: input, tool_use_id, context -> HookJSONOutput) ------------------------
    async def on_user_prompt(self, data: Any, tool_use_id: str | None, context: Any) -> dict[str, Any]:
        sid, prompt = str(data.get("session_id", "")), str(data.get("prompt", ""))
        if sid not in self._sessions:
            self._sessions.add(sid)
            self.hooks.start_session(prompt)
            recall = self.hooks.recalled.strip()
        else:
            recall = self._due(sid)
        return self._context("UserPromptSubmit", recall)

    async def on_post_tool_use(self, data: Any, tool_use_id: str | None, context: Any) -> dict[str, Any]:
        name = str(data.get("tool_name", ""))
        out = self._context("PostToolUse", self._due(str(data.get("session_id", ""))))
        if not self.hooks.is_memory_tool(name.rsplit("__", 1)[-1]):
            updated = self._preview(name, data.get("tool_response"))
            if updated is not None:
                out.setdefault("hookSpecificOutput", {"hookEventName": "PostToolUse"})["updatedToolOutput"] = updated
        return out

    async def on_pre_compact(self, data: Any, tool_use_id: str | None, context: Any) -> dict[str, Any]:
        self._recall_due.add(str(data.get("session_id", "")))
        return {"systemMessage": HANDOFF}

    async def on_stop(self, data: Any, tool_use_id: str | None, context: Any) -> dict[str, Any]:
        if not data.get("stop_hook_active"):
            self.hooks.end_session(str(data.get("last_assistant_message") or ""))
        return {}

    # ---- helpers -------------------------------------------------------------------------------------------
    @staticmethod
    def _context(event: str, text: str) -> dict[str, Any]:
        return {"hookSpecificOutput": {"hookEventName": event, "additionalContext": text}} if text else {}

    def _due(self, sid: str) -> str:
        if sid not in self._recall_due:
            return ""
        self._recall_due.discard(sid)
        return self.hooks.recall().strip()

    def _ingest(self, name: str, text: str) -> str:
        self.hooks.after_call(self.prompt_tokens)   # each output is checked against the last known prompt size
        return self.hooks.on_tool_result(name, text)

    def _preview(self, name: str, resp: Any) -> Any:
        """The replacement output in the tool's own shape, or None to keep the original."""
        def short(text: str) -> str | None:
            if text in self._wrapped:
                self._wrapped.discard(text)
                return None
            out = self._ingest(name, text)
            return out if out != text else None

        if isinstance(resp, str):
            return short(resp)
        if isinstance(resp, list) and (text := _text_blocks(resp)) is not None:
            out = short(text)
            return None if out is None else [{"type": "text", "text": out}]
        if not isinstance(resp, dict):
            return None
        if isinstance(resp.get("content"), list) and (text := _text_blocks(resp["content"])) is not None:
            out = short(text)
            return None if out is None else {**resp, "content": [{"type": "text", "text": out}]}
        if name != "Bash":
            return None
        streams = {k: resp.get(k) for k in ("stdout", "stderr") if isinstance(resp.get(k), str)}
        saved = resp.get("persistedOutputPath")
        if isinstance(saved, str) and Path(saved).is_file() and Path(saved).stat().st_size <= PERSISTED_MAX:
            streams = {"stdout": Path(saved).read_text(errors="replace"), "stderr": ""}  # the untruncated output
        changed = {k: v for k, v in ((k, short(t)) for k, t in streams.items()) if v is not None}
        if not changed:
            return None
        merged = {**resp, **streams, **changed}
        return {k: merged[k] for k in ("stdout", "stderr", "interrupted", "isImage") if k in merged}


__all__ = ["AgentMemory", "HANDOFF"]
