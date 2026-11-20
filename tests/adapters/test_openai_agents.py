"""The OpenAI Agents SDK adapter through the conformance suite, with a scripted fake model (no network, no key)."""

from __future__ import annotations

import pytest

pytest.importorskip("agents")

from agents import Agent, Model, ModelResponse, Runner, Usage, function_tool, set_tracing_disabled  # noqa: E402
from agents.run_config import CallModelData, ModelInputData  # noqa: E402
from agents.testing import assistant_message, function_call  # noqa: E402

from adapters.conformance import (OLD_TURN, SUMMARY, WINDOW, Seen, Step, check_all, check_compaction,  # noqa: E402
                                  fake_summarize, run_tool)
from eam.adapters.openai_agents import OpenAIAgentsMemory, item_text  # noqa: E402

set_tracing_disabled(True)


def flatten(items) -> str:
    return items if isinstance(items, str) else "\n".join(item_text(i) for i in items)


def assert_valid_input(items) -> None:
    """Every function_call_output answers an earlier function_call."""
    calls = set()
    for item in items:
        if item.get("type") == "function_call":
            calls.add(item["call_id"])
        elif item.get("type") == "function_call_output":
            assert item["call_id"] in calls, f"orphan function_call_output {item['call_id']}"


class FakeModel(Model):
    """Follows the conformance script: a function call per tool step, a message for the final step."""

    def __init__(self, script: list[Step], seen: Seen):
        self.script, self.seen, self.n = list(script), seen, 0

    async def get_response(self, system_instructions, input, model_settings, tools, output_schema, handoffs,
                           tracing, **kwargs):
        self.seen.system.append(system_instructions or "")
        self.seen.inputs.append(flatten(input))
        if not isinstance(input, str):
            assert_valid_input(input)
        step = self.script[self.n]
        self.n += 1
        if step.kind == "final":
            out = [assistant_message(step.name_or_text, item_id=f"msg-{self.n}")]
        else:
            out = [function_call(step.name_or_text, step.args, call_id=f"call-{self.n}")]
        tokens = step.prompt_tokens or 0
        return ModelResponse(output=out, usage=Usage(requests=1, input_tokens=tokens, total_tokens=tokens),
                             response_id=None)

    def stream_response(self, *args, **kwargs):
        raise NotImplementedError


@function_tool
def fetch_report() -> str:
    """Fetch today's stock report."""
    return run_tool("fetch_report", {})


@function_tool
def lookup(q: str) -> str:
    """Look something up."""
    return run_tool("lookup", {"q": q})


def run_session(mem: OpenAIAgentsMemory, task: str, script: list[Step]) -> Seen:
    seen = Seen()
    agent = Agent(name="counter", instructions="You count widgets.", model=FakeModel(script, seen),
                  tools=mem.tools(fetch_report, lookup))
    result = Runner.run_sync(agent, task, hooks=mem.run_hooks(), run_config=mem.run_config(tracing_disabled=True))
    assert result.final_output == script[-1].name_or_text
    return seen


class AgentsDriver:
    name = "openai agents"
    compacts = True

    def run(self, root, task, script, *, window):
        mem = OpenAIAgentsMemory(root, window=window, summarize=fake_summarize)
        return run_session(mem, task, script), mem.hooks


def test_conforms(tmp_path):
    check_all(AgentsDriver(), tmp_path)


def test_compacts(tmp_path):
    check_compaction(AgentsDriver(), tmp_path)


def test_one_object_recalls_across_two_runs(tmp_path):
    mem = OpenAIAgentsMemory(tmp_path, window=WINDOW, summarize=fake_summarize)
    run_session(mem, "Day 1.", [Step("tool", "write_note", {"name": "stock", "content": "widgets: 42"}),
                                Step("final", "Day 1 finished with 42 widgets.")])
    seen = run_session(mem, "Day 2.", [Step("tool", "lookup", {"q": "x"}), Step("final", "Day 2 finished.")])
    assert "widgets: 42" in seen.inputs[0] and "Day 1 finished" in seen.inputs[0]
    # the recall sits before the task, once per call, and does not pile up across turns
    assert all(s.count("<memory") == 1 and s.index("<memory") < s.index("Day 2.") for s in seen.inputs)
    assert mem.hooks.task == "Day 2."


def call_data(items, instructions="base"):
    return CallModelData(model_data=ModelInputData(input=list(items), instructions=instructions), agent=None,
                         context=None)


def test_compaction_filter_output_is_valid(tmp_path):
    mem = OpenAIAgentsMemory(tmp_path, window=WINDOW, summarize=fake_summarize)
    mem.hooks.start_session("the task")
    history = [{"role": "user", "content": "the task"},
               {"type": "function_call", "call_id": "c1", "name": "lookup", "arguments": "{}", "id": "c1"},
               {"type": "function_call_output", "call_id": "c1", "output": OLD_TURN}]
    mem.hooks.after_call(int(0.8 * WINDOW))
    out = mem.input_filter(call_data(history))
    assert len(out.input) == 1 and out.input[0]["role"] == "user"
    assert SUMMARY in out.input[0]["content"] and OLD_TURN not in flatten(out.input)
    assert "write_note" in out.instructions and out.instructions.startswith("base")

    # the next turn: the SDK sends the full history again; the reset replaces the old part, new items follow it
    mem.hooks.after_call(1_000)
    later = history + [{"type": "function_call", "call_id": "c2", "name": "lookup", "arguments": "{}", "id": "c2"},
                       {"type": "function_call_output", "call_id": "c2", "output": "new result"}]
    out2 = mem.input_filter(call_data(later))
    assert out2.input[0] == out.input[0] and [i.get("call_id") for i in out2.input[1:]] == ["c2", "c2"]
    assert_valid_input(out2.input)
    assert OLD_TURN not in flatten(out2.input) and mem.hooks.compactions == 1


def test_wrapped_tool_keeps_its_schema(tmp_path):
    mem = OpenAIAgentsMemory(tmp_path, window=WINDOW)
    tools = mem.tools(lookup)
    assert [t.name for t in tools] == ["lookup", "write_note", "read_notes", "read_artifact"]
    assert tools[0].params_json_schema == lookup.params_json_schema and tools[0] is not lookup
    assert mem.wrap(tools[1]) is tools[1]


def test_user_filter_runs_first(tmp_path):
    from agents import RunConfig

    def mark(data):
        return ModelInputData(input=data.model_data.input, instructions="USER-FILTER")

    mem = OpenAIAgentsMemory(tmp_path, window=WINDOW)
    cfg = mem.run_config(RunConfig(call_model_input_filter=mark))
    import asyncio
    out = asyncio.run(cfg.call_model_input_filter(call_data([{"role": "user", "content": "t"}])))
    assert out.instructions.startswith("USER-FILTER") and "write_note" in out.instructions
