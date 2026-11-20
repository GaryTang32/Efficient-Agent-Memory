"""The LangGraph / LangChain adapter through the conformance suite, offline: a scripted chat model stands in for the
provider, and the agent is the real `create_agent` graph with AutoMemoryMiddleware."""

from __future__ import annotations

import asyncio
from typing import Any

import pytest

pytest.importorskip("langchain")

from langchain.agents import create_agent  # noqa: E402
from langchain_core.language_models.chat_models import BaseChatModel  # noqa: E402
from langchain_core.messages import AIMessage, HumanMessage, RemoveMessage, SystemMessage, ToolMessage  # noqa: E402
from langchain_core.outputs import ChatGeneration, ChatResult  # noqa: E402
from langchain_core.tools import tool  # noqa: E402
from langgraph.graph.message import REMOVE_ALL_MESSAGES, add_messages  # noqa: E402

from adapters.conformance import (OLD_TURN, SUMMARY, WINDOW, Seen, Step, check_all, check_compaction,  # noqa: E402
                                  fake_summarize, run_tool, session_one)
from eam.adapters.langgraph import AutoMemoryMiddleware, compact_update, prompt_tokens  # noqa: E402


class ScriptedModel(BaseChatModel):
    """Answers with the script's steps in order and records what it was shown."""
    script: list[Any]
    seen: Any
    calls: int = 0
    bound: list[str] = []

    @property
    def _llm_type(self) -> str:
        return "scripted"

    def bind_tools(self, tools, **kwargs):
        self.bound = [getattr(t, "name", None) or t.get("name") for t in tools]
        return self

    def _generate(self, messages, stop=None, run_manager=None, **kwargs) -> ChatResult:
        self.seen.system.append("\n".join(m.text for m in messages if isinstance(m, SystemMessage)))
        rest = []
        for m in messages:
            if isinstance(m, SystemMessage):
                continue
            rest.append(m.text)
            if isinstance(m, AIMessage):
                rest += [f"[tool call {c['name']} {c['args']}]" for c in m.tool_calls]
        self.seen.inputs.append("\n".join(rest))
        step: Step = self.script[self.calls]
        self.calls += 1
        n = step.prompt_tokens or 0
        usage = {"input_tokens": n, "output_tokens": 10, "total_tokens": n + 10}
        if step.kind == "tool":
            ai = AIMessage(content="", usage_metadata=usage, tool_calls=[
                {"name": step.name_or_text, "args": step.args, "id": f"call_{self.calls}", "type": "tool_call"}])
        else:
            ai = AIMessage(content=step.name_or_text, usage_metadata=usage)
        return ChatResult(generations=[ChatGeneration(message=ai)])


@tool
def fetch_report() -> str:
    """Fetch today's stock report."""
    return run_tool("fetch_report", {})


@tool
def lookup(q: str) -> str:
    """Look something up."""
    return run_tool("lookup", {"q": q})


def build(root, script, *, window, checkpointer=None):
    seen = Seen()
    model = ScriptedModel(script=script, seen=seen)
    memory = AutoMemoryMiddleware(root, window=window, summarize=fake_summarize)
    agent = create_agent(model, tools=[fetch_report, lookup], system_prompt="You count widgets.",
                         middleware=[memory], checkpointer=checkpointer)
    return agent, memory, model, seen


class LangGraphDriver:
    name = "langgraph"
    compacts = True

    def __init__(self):
        self.results: list[dict] = []

    def run(self, root, task, script, *, window):
        agent, memory, model, seen = build(root, script, window=window)
        self.results.append(agent.invoke({"messages": [{"role": "user", "content": task}]}))
        assert {"write_note", "read_notes", "read_artifact", "fetch_report", "lookup"} <= set(model.bound)
        return seen, memory.hooks


def test_langgraph_conforms(tmp_path):
    check_all(LangGraphDriver(), tmp_path)


def test_langgraph_compacts(tmp_path):
    driver = LangGraphDriver()
    check_compaction(driver, tmp_path)
    messages = driver.results[0]["messages"]
    # the state after the reset: the reset message, then the final answer; no old turns, no orphan tool results
    assert isinstance(messages[0], HumanMessage) and SUMMARY in messages[0].text
    assert not any(OLD_TURN in m.text for m in messages)
    assert not any(isinstance(m, ToolMessage) for m in messages)
    assert isinstance(messages[-1], AIMessage) and messages[-1].text == "Done after the reset."


def test_compact_update_replaces_the_whole_state(tmp_path):
    memory = AutoMemoryMiddleware(tmp_path, window=WINDOW, summarize=fake_summarize)
    memory.hooks.start_session("the task")
    state = add_messages([], [HumanMessage("the task"),
                              AIMessage("", tool_calls=[{"name": "lookup", "args": {"q": OLD_TURN}, "id": "c1"}]),
                              ToolMessage(f"lookup result: {OLD_TURN}", tool_call_id="c1")])
    assert compact_update(memory.hooks, state) is None  # below the trigger: nothing to do
    memory.hooks.after_call(int(0.8 * WINDOW))
    update = compact_update(memory.hooks, state)
    assert isinstance(update["messages"][0], RemoveMessage) and update["messages"][0].id == REMOVE_ALL_MESSAGES
    new = add_messages(state, update["messages"])
    assert len(new) == 1 and isinstance(new[0], HumanMessage)
    assert SUMMARY in new[0].text and "the task" in new[0].text and OLD_TURN not in new[0].text
    assert memory.hooks.compactions == 1 and not memory.hooks.should_compact()


def test_a_second_agent_recalls(tmp_path):
    root = tmp_path / "memory"
    agent, *_ = build(root, session_one(), window=WINDOW)
    agent.invoke({"messages": [{"role": "user", "content": "Day 1."}]})
    agent2, _, _, seen2 = build(root, [Step("final", "ok")], window=WINDOW)
    out = agent2.invoke({"messages": [{"role": "user", "content": "Day 2."}]})
    assert "stock of widgets is 42" in seen2.inputs[0] and "<memory" in seen2.inputs[0]
    assert out["messages"][0].text.endswith("Day 2.")  # recall sits in the first user message, before the task


def test_a_continued_thread_is_not_recalled_twice(tmp_path):
    from langgraph.checkpoint.memory import InMemorySaver

    root = tmp_path / "memory"
    agent, *_ = build(root, session_one(), window=WINDOW)
    agent.invoke({"messages": [{"role": "user", "content": "Day 1."}]})
    agent2, _, _, seen = build(root, [Step("final", "one"), Step("final", "two")], window=WINDOW,
                               checkpointer=InMemorySaver())
    config = {"configurable": {"thread_id": "t"}}
    agent2.invoke({"messages": [{"role": "user", "content": "first"}]}, config)
    agent2.invoke({"messages": [{"role": "user", "content": "second"}]}, config)
    assert seen.inputs[1].count("<memory") == seen.inputs[0].count("<memory") > 0


def test_async_run_previews(tmp_path):
    agent, _, _, seen = build(tmp_path / "memory", session_one(), window=WINDOW)
    asyncio.run(agent.ainvoke({"messages": [{"role": "user", "content": "Day 1."}]}))
    after = next(s for s in seen.inputs if "REPORT-HEAD" in s)
    assert "artifact://" in after and "row 1200:" not in after
    assert "write_note" in seen.system[0]


def test_prompt_tokens_from_usage():
    assert prompt_tokens(AIMessage("x")) is None
    usage = {"input_tokens": 1000, "output_tokens": 1, "total_tokens": 1001,
             "input_token_details": {"cache_read": 600, "cache_creation": 300}}
    assert prompt_tokens(AIMessage("x", usage_metadata=usage)) == 1000  # LangChain's input_tokens counts the cache
    usage = {"input_tokens": 50, "output_tokens": 1, "total_tokens": 51,
             "input_token_details": {"cache_read": 900}}
    assert prompt_tokens(AIMessage("x", usage_metadata=usage)) == 950  # a provider that left the cache out
