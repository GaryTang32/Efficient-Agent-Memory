"""AutoMemory for the OpenAI Agents SDK (``pip install openai-agents``).

One object gives the agent its memory tools, wraps your tools so long outputs reach the model as a preview, and
supplies the run hooks and the run config that recall notes, record the prompt size, compact and autosave:

    from agents import Agent, Runner
    from eam.adapters.openai_agents import OpenAIAgentsMemory

    mem = OpenAIAgentsMemory("~/.eam-memory/project-x", window=200_000, summarize=cheap_llm)
    agent = Agent(name="assistant", instructions="You count widgets.", tools=mem.tools(fetch_report, lookup))
    result = await Runner.run(agent, "Count the widgets.", hooks=mem.run_hooks(), run_config=mem.run_config())

What each piece does:

* ``run_config()`` sets ``RunConfig.call_model_input_filter``. Before every model call it adds the note rules to
  the instructions, puts the recalled notes in front of the task message, and, once the prompt reached 75% of the
  window, replaces the history with AutoMemory's reset (task + summary + notes). The SDK does not keep filter edits,
  so the reset is re-applied to every later call of the run.
* ``run_hooks()`` starts a session when a run starts, passes each response's ``usage.input_tokens`` (which already
  counts cached tokens) to ``after_call``, and autosaves the final output.
* ``tools(*user_tools)`` returns your function tools wrapped (string outputs go through ``on_tool_result``) plus
  ``write_note``, ``read_notes`` and ``read_artifact``.

Limits: one run at a time per object; history must be sent by the client (not ``previous_response_id`` or
``conversation_id``) for compaction to apply; only string outputs of function tools are previewed.
"""

from __future__ import annotations

import dataclasses
import inspect
import json
from copy import copy
from functools import update_wrapper
from pathlib import Path
from typing import Any

from agents import FunctionTool, RunConfig, RunHooks
from agents.run_config import CallModelData, ModelInputData

from eam.adapters.base import MemoryHooks

__all__ = ["OpenAIAgentsMemory"]


def _as_dict(item: Any) -> dict[str, Any]:
    if isinstance(item, dict):
        return item
    dump = getattr(item, "model_dump", None)
    return dump(exclude_unset=True) if callable(dump) else {}


def _parts_text(content: Any) -> str:
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        return "\n".join(str(p.get("text") or p.get("refusal") or "") for p in map(_as_dict, content))
    return "" if content is None else str(content)


def item_text(item: Any) -> str:
    """The text of one Responses-API input item (message, function call or function call output)."""
    d = _as_dict(item)
    kind = d.get("type")
    if kind == "function_call":
        return f"[tool call {d.get('name')} {d.get('arguments', '')}]"
    if kind == "function_call_output":
        return _parts_text(d.get("output"))
    return _parts_text(d.get("content"))


def to_messages(items: list[Any]) -> list[dict[str, Any]]:
    """SDK input items as the OpenAI-style dicts MemoryHooks.compact reads."""
    out = []
    for item in items:
        d = _as_dict(item)
        kind = d.get("type")
        role = "assistant" if kind == "function_call" else "tool" if kind == "function_call_output" else d.get("role")
        if role:
            out.append({"role": role, "content": item_text(d)})
    return out


def from_messages(messages: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """MemoryHooks' reset (user/assistant text messages) back as SDK input items; system messages are dropped
    because the SDK sends the instructions separately."""
    return [{"role": m["role"], "content": str(m.get("content", ""))} for m in messages
            if m.get("role") in ("user", "assistant")]


def _forward(name: str):
    async def method(self: _RunHooks, *args: Any) -> None:
        if self.base is not None:
            await getattr(self.base, name)(*args)
    return method


class _RunHooks(RunHooks):
    """Session start, usage and autosave; every event is also forwarded to the user's own hooks."""

    def __init__(self, mem: OpenAIAgentsMemory, base: RunHooks | None):
        self.mem, self.base = mem, base

    async def on_agent_start(self, context: Any, agent: Any) -> None:
        self.mem._on_run_start(context)
        await _forward("on_agent_start")(self, context, agent)

    async def on_llm_end(self, context: Any, agent: Any, response: Any) -> None:
        self.mem._on_response(response)
        await _forward("on_llm_end")(self, context, agent, response)

    async def on_agent_end(self, context: Any, agent: Any, output: Any) -> None:
        self.mem._on_final(output)
        await _forward("on_agent_end")(self, context, agent, output)

    on_llm_start = _forward("on_llm_start")
    on_tool_start = _forward("on_tool_start")
    on_tool_end = _forward("on_tool_end")
    on_handoff = _forward("on_handoff")


class OpenAIAgentsMemory:
    """AutoMemory for one OpenAI Agents SDK agent. Pass a memory directory and MemoryHooks options (window,
    summarize, ...) or ready-made ``hooks``."""

    def __init__(self, root: str | Path | None = None, *, hooks: MemoryHooks | None = None, **kwargs: Any):
        self.hooks = hooks if hooks is not None else MemoryHooks(root, **kwargs)
        self._addendum = self.hooks.system_text("")
        self._run: Any = None          # the Usage object of the current run: identifies the run
        self._recall = ""
        self._task_index: int | None = None
        self._reset: list[dict[str, Any]] | None = None
        self._cut = 0                  # number of raw input items the reset replaces

    # ---- tools ---------------------------------------------------------------------------------------------
    def memory_tools(self) -> list[FunctionTool]:
        """write_note, read_notes and read_artifact as SDK function tools."""
        def make(spec: dict[str, Any]) -> FunctionTool:
            name = spec["name"]

            async def invoke(ctx: Any, args: str) -> str:
                try:
                    parsed = json.loads(args or "{}")
                except json.JSONDecodeError as exc:
                    return f"Error: invalid JSON arguments ({exc})"
                return self.hooks.call_tool(name, parsed if isinstance(parsed, dict) else {})
            return FunctionTool(name=name, description=spec["description"], params_json_schema=spec["input_schema"],
                                on_invoke_tool=invoke, strict_json_schema=False)
        return [make(spec) for spec in self.hooks.tool_specs()]

    def wrap(self, tool: Any) -> Any:
        """A copy of a function tool whose string outputs go through ``on_tool_result`` (preview, redaction,
        guard). Other tools are returned unchanged."""
        if not isinstance(tool, FunctionTool) or self.hooks.is_memory_tool(tool.name):
            return tool
        wrapped, name = copy(tool), tool.name
        inner = wrapped.on_invoke_tool

        async def invoke(ctx: Any, args: str) -> Any:
            out = await inner(ctx, args)
            return self.hooks.on_tool_result(name, out) if isinstance(out, str) else out
        update_wrapper(invoke, inner, updated=())   # keeps the context type the SDK reads from the signature
        wrapped.on_invoke_tool = invoke
        return wrapped

    def tools(self, *user_tools: Any) -> list[Any]:
        """Your tools, wrapped, followed by the memory tools."""
        return [self.wrap(t) for t in user_tools] + self.memory_tools()

    # ---- run wiring ----------------------------------------------------------------------------------------
    def run_hooks(self, base: RunHooks | None = None) -> RunHooks:
        """RunHooks for ``Runner.run(hooks=...)``; ``base`` (your own hooks) still receives every event."""
        return _RunHooks(self, base)

    def run_config(self, base: RunConfig | None = None, **overrides: Any) -> RunConfig:
        """A copy of ``base`` (or a new RunConfig) with the memory input filter, run after any filter it has."""
        base = base or RunConfig()
        user_filter = base.call_model_input_filter
        flt = self.input_filter
        if user_filter is not None:
            async def flt(data: CallModelData[Any]) -> ModelInputData:
                out = user_filter(data)
                data.model_data = await out if inspect.isawaitable(out) else out
                return self.input_filter(data)
        return dataclasses.replace(base, call_model_input_filter=flt, **overrides)

    def input_filter(self, data: CallModelData[Any]) -> ModelInputData:
        """The ``call_model_input_filter``: rules in the instructions, recall before the task, compaction."""
        raw = list(data.model_data.input)
        instructions = data.model_data.instructions or ""
        if self._addendum not in instructions:
            instructions = self.hooks.system_text(instructions)
        if self._reset is not None:
            items = self._reset + raw[self._cut:]
        else:
            items = self._with_recall(raw)
        if self.hooks.should_compact():
            messages = to_messages(items)
            out = self.hooks.compact(messages)
            if out is not messages:
                self._reset, self._cut = from_messages(out), len(raw)
                items = list(self._reset)
        return ModelInputData(input=items, instructions=instructions)

    # ---- internals -----------------------------------------------------------------------------------------
    def _with_recall(self, items: list[Any]) -> list[Any]:
        if not self._recall:
            return items
        i = self._task_index
        if i is None or i >= len(items) or not self._is_task(items[i]):
            i = next((j for j in range(len(items) - 1, -1, -1) if self._is_task(items[j])), None)
            self._task_index = i
        if i is None:
            return items
        d = _as_dict(items[i])
        content = d.get("content")
        if isinstance(content, list):
            content = [{"type": "input_text", "text": self._recall}, *content]
        else:
            content = self._recall + str(content or "")
        return [*items[:i], {**d, "content": content}, *items[i + 1:]]

    def _is_task(self, item: Any) -> bool:
        d = _as_dict(item)
        return d.get("role") == "user" and d.get("type", "message") == "message" and \
            _parts_text(d.get("content")) == self.hooks.task

    def _on_run_start(self, context: Any) -> None:
        usage = getattr(context, "usage", None)
        if usage is not None and usage is self._run:
            return                     # a handoff inside the same run
        self._run, self._reset, self._cut, self._task_index = usage, None, 0, None
        turn = list(getattr(context, "turn_input", None) or [])
        task = next((_parts_text(d.get("content")) for d in map(_as_dict, reversed(turn))
                     if d.get("role") == "user"), "")
        self.hooks.start_session(task)
        self._recall = self.hooks.recalled

    def _on_response(self, response: Any) -> None:
        usage = getattr(response, "usage", None)
        reply = "\n".join(item_text(o) for o in getattr(response, "output", None) or [])
        self.hooks.after_call(getattr(usage, "input_tokens", 0) or 0, reply)

    def _on_final(self, output: Any) -> None:
        self.hooks.end_session(output if isinstance(output, str) else json.dumps(output, default=str))
