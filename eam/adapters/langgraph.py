"""AutoMemory for LangChain v1 agents (built on LangGraph) and hand-built LangGraph graphs.

    from langchain.agents import create_agent
    from eam.adapters.langgraph import AutoMemoryMiddleware

    memory = AutoMemoryMiddleware("~/.eam-memory/project-x", window=200_000, summarize=cheap_llm)
    agent = create_agent(model, tools=[search, run_tests], system_prompt="You fix bugs.", middleware=[memory])
    agent.invoke({"messages": [{"role": "user", "content": "Fix the failing test."}]})

One invocation is one session. The middleware adds the note rules to the system prompt, the recalled notes to the
thread's first user message, the memory tools (write_note, read_notes, read_artifact), a preview or pointer for long
tool outputs, the real prompt size from `AIMessage.usage_metadata`, the rare compaction of the message state, and the
autosave of the final answer.

A hand-built LangGraph graph can use the same pieces with a MemoryHooks of its own: `memory_tools(hooks)` for the
tool node, `hooks.after_call(prompt_tokens(ai_message), ai_message.text)` after the model node,
`hooks.on_tool_result` on tool outputs, and `compact_update(hooks, state["messages"])` as the state update of a node
placed before the model node (it returns None when there is nothing to do).

LangChain is imported by this module only; `import eam.adapters` stays free of it.
"""

from __future__ import annotations

from typing import Any, Callable

from langchain.agents.middleware import AgentMiddleware
from langchain_core.messages import (AIMessage, AnyMessage, BaseMessage, HumanMessage, RemoveMessage,
                                     SystemMessage, ToolMessage)
from langchain_core.tools import BaseTool, StructuredTool
from langgraph.graph.message import REMOVE_ALL_MESSAGES

from eam.adapters.base import MemoryHooks

__all__ = ["AutoMemoryMiddleware", "memory_tools", "prompt_tokens", "to_dicts", "from_dicts", "compact_update"]


# ---- helpers (also usable in a hand-built graph) -------------------------------------------------------------
def memory_tools(hooks: MemoryHooks) -> list[BaseTool]:
    """write_note, read_notes and read_artifact as LangChain tools that call `hooks`."""
    def make(spec: dict[str, Any]) -> BaseTool:
        name = spec["name"]
        return StructuredTool(name=name, description=spec["description"], args_schema=spec["input_schema"],
                              func=lambda **args: hooks.call_tool(name, args))
    return [make(spec) for spec in hooks.tool_specs()]


def prompt_tokens(message: Any) -> int | None:
    """The prompt size of a model call from `AIMessage.usage_metadata` (None when the provider sent no usage).
    LangChain's `input_tokens` already counts cache reads and writes; if a provider reports cache details larger
    than `input_tokens`, they were left out, and are added."""
    usage = getattr(message, "usage_metadata", None)
    if not usage:
        return None
    total = int(usage.get("input_tokens") or 0)
    details = usage.get("input_token_details") or {}
    cached = int(details.get("cache_read") or 0) + int(details.get("cache_creation") or 0)
    return total + cached if cached > total else total


def _text(content: Any) -> str | None:
    """The text of a message content, or None if it holds anything but text (images, files...)."""
    if isinstance(content, str):
        return content
    if isinstance(content, list) and all(isinstance(b, str) or (isinstance(b, dict) and b.get("type") == "text")
                                         for b in content):
        return "".join(b if isinstance(b, str) else str(b.get("text", "")) for b in content)
    return None


def _role(m: BaseMessage) -> str:
    return {"human": "user", "ai": "assistant"}.get(m.type, m.type)


def to_dicts(messages: list[AnyMessage]) -> list[dict[str, Any]]:
    """LangChain messages as the OpenAI-style dicts MemoryHooks reads (tool calls rendered as text)."""
    out = []
    for m in messages:
        text = m.text if isinstance(m, BaseMessage) else str(m)
        if isinstance(m, AIMessage) and m.tool_calls:
            text += "".join(f"\n[tool call {c['name']} {c.get('args')}]" for c in m.tool_calls)
        out.append({"role": _role(m), "content": text})
    return out


def from_dicts(messages: list[dict[str, Any]]) -> list[AnyMessage]:
    """MemoryHooks' dicts back as LangChain messages (system, user and plain assistant turns)."""
    kinds = {"system": SystemMessage, "assistant": AIMessage}
    return [kinds.get(m.get("role"), HumanMessage)(content=str(m.get("content") or "")) for m in messages]


def compact_update(hooks: MemoryHooks, messages: list[AnyMessage]) -> dict[str, Any] | None:
    """The state update that resets `messages` to the task, a summary and the notes once the prompt reached the
    trigger, or None. It removes every message (REMOVE_ALL_MESSAGES) and adds the reset, so no tool call or tool
    result is left half-paired."""
    if not hooks.should_compact():
        return None
    old = to_dicts(messages)
    new = hooks.compact(old)
    if new is old:
        return None
    return {"messages": [RemoveMessage(id=REMOVE_ALL_MESSAGES), *from_dicts(new)]}


# ---- the middleware ---------------------------------------------------------------------------------------
class AutoMemoryMiddleware(AgentMiddleware):
    """AutoMemory for `langchain.agents.create_agent`. Give a memory directory (and MemoryHooks / MemorySkill
    options such as window, summarize, store) or a ready `hooks`. One agent run at a time per instance: the hooks
    hold the current session."""

    def __init__(self, root: Any = None, *, hooks: MemoryHooks | None = None,
                 summarize: Callable[[str], str] | None = None, **skill_kwargs: Any):
        super().__init__()
        self.hooks = hooks if hooks is not None else MemoryHooks(root, summarize=summarize, **skill_kwargs)
        self.tools = memory_tools(self.hooks)

    # session start: recall goes into the thread's first user message
    def before_agent(self, state: Any, runtime: Any) -> dict[str, Any] | None:
        humans = [m for m in state["messages"] if isinstance(m, HumanMessage)]
        if not humans:
            return None
        last = humans[-1]
        task = last.text
        first = self.hooks.start_session(task)
        if len(humans) > 1 or first == task:  # a continued thread already has its recall; or nothing to recall
            return None
        recall = first[: len(first) - len(task)]
        content = (recall + last.content if isinstance(last.content, str)
                   else [{"type": "text", "text": recall}, *last.content])
        return {"messages": [last.model_copy(update={"content": content})]}  # same id: add_messages replaces it

    # the rare reset, before the next model call
    def before_model(self, state: Any, runtime: Any) -> dict[str, Any] | None:
        return compact_update(self.hooks, state["messages"])

    # system rules on the way in, the real prompt size on the way out
    def _request(self, request: Any) -> Any:
        base = request.system_message
        if base is not None and not isinstance(base.content, str):
            system = SystemMessage(content=[*base.content, {"type": "text", "text": self.hooks.system_text()}])
        else:
            system = SystemMessage(content=self.hooks.system_text(base.content if base is not None else ""))
        return request.override(system_message=system)

    def _record(self, response: Any) -> Any:
        ai = next((m for m in reversed(getattr(response, "result", None) or [response]) if isinstance(m, AIMessage)),
                  None)
        if ai is not None:
            self.hooks.after_call(prompt_tokens(ai), ai.text)
        return response

    def wrap_model_call(self, request: Any, handler: Callable[[Any], Any]) -> Any:
        return self._record(handler(self._request(request)))

    async def awrap_model_call(self, request: Any, handler: Callable[[Any], Any]) -> Any:
        return self._record(await handler(self._request(request)))

    # previews and the in-step guard on tool outputs (the memory tools' own outputs pass as they are)
    def _ingest(self, request: Any, result: Any) -> Any:
        name = request.tool_call.get("name", "")
        if not isinstance(result, ToolMessage) or self.hooks.is_memory_tool(name):
            return result
        text = _text(result.content)
        if text is None:
            return result
        shown = self.hooks.on_tool_result(name, text)
        return result if shown == text else result.model_copy(update={"content": shown})

    def wrap_tool_call(self, request: Any, handler: Callable[[Any], Any]) -> Any:
        return self._ingest(request, handler(request))

    async def awrap_tool_call(self, request: Any, handler: Callable[[Any], Any]) -> Any:
        return self._ingest(request, await handler(request))

    # autosave the final answer
    def after_agent(self, state: Any, runtime: Any) -> dict[str, Any] | None:
        last = state["messages"][-1] if state["messages"] else None
        if isinstance(last, AIMessage) and not last.tool_calls:
            self.hooks.end_session(last.text)
        return None
