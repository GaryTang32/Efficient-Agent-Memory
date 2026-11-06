"""AutoMemory v1: each component on its own, and the whole skill on the long tasks (offline mock)."""

from eam.agent.context import Tool
from eam.agent.loop import run_agent
from eam.bench.runner import run_instance
from eam.bench.tasks import FAMILIES
from eam.llm.mock import MockLLM, assistant, final, tool_use
from eam.llm.types import ToolSpec
from eam.models import MOCK_MODELS
from eam.techniques import build
from eam.techniques.auto_memory import AutoMemory

M = MOCK_MODELS["mock-strong"]


def run(inst, spec):
    return run_instance(inst, spec, backend="mock", model=M, aux_model=M, models=MOCK_MODELS)


def test_registered_with_switches():
    (a,) = build("automem:guard=0,recall=false,compact=mask")
    assert isinstance(a, AutoMemory) and a.guard == 0 and not a.recall and a.compact == "mask"


def test_guard_stops_a_greedy_parallel_step_from_overflowing():
    inst = FAMILIES["ledger_audit"](0)

    def greedy(req):  # reads every file in one step, then answers from whatever is visible
        if not any("toolResult" in b for m in req.messages for b in m["content"]):
            return assistant(*[tool_use("open_file", {"file_id": f"L-{i:02d}"}) for i in range(1, 17)])
        return final("FINAL ANSWER: done")

    def go(techniques):
        return run_agent(inst.rounds[0], llm=MockLLM(greedy), model=M, env_tools=inst.tools, techniques=techniques,
                         context_limit=48_000, max_steps=5)

    unguarded = go([AutoMemory(guard=0, compact="none")])
    guarded = go([AutoMemory(compact="none")])
    assert any(e["kind"] == "context_overflow" for e in unguarded.events)
    assert not any(e["kind"] == "context_overflow" for e in guarded.events)
    assert sum(e["kind"] == "automem_guard_offload" for e in guarded.events) >= 8
    assert guarded.finished


def test_recall_and_autosave_carry_results_across_sessions():
    a = AutoMemory(compact="none")
    seen = []

    def policy(req):
        seen.append(req.messages[0]["content"][0]["text"])
        return final("FINAL ANSWER: total = 42")

    tools = [Tool(ToolSpec("noop", "n", {"type": "object", "properties": {}}), lambda args, ctx: "ok")]
    for task in ("session one", "session two"):
        run_agent(task, llm=MockLLM(policy), model=M, env_tools=tools, techniques=[a], max_steps=3)
    assert "total = 42" not in seen[0]
    assert "session 1 final answer" in seen[1] and "total = 42" in seen[1]


def test_trigger_follows_the_window():
    from types import SimpleNamespace

    a = AutoMemory(trigger=0.75)
    comp = a._make_compactor(SimpleNamespace(context_limit=32_000, model=M))
    assert abs(comp.trigger_tokens - 24_000) < 50


def test_solves_both_long_tasks_under_their_windows():
    ops = run(FAMILIES["ops_stream"](0), "automem")
    assert not ops["overflow"] and all(s == 1.0 for s in ops["round_scores"])
    # The mock's extractive summariser drops facts, so ReSum itself cannot be exercised offline (fs_workspace+resum
    # fails the same way); with a large window, recall + autosave alone must carry the three rounds.
    led = run(FAMILIES["ledger_audit"](0, context_limit=10**7), "automem")
    assert led["success"] and led["events"].get("automem_recall") == 2


def test_edit_boundary_cache_point_keeps_agentdiet_cacheable():
    inst = FAMILIES["chain_hunt"](0)
    plain = run(inst, "cache_layout+agentdiet")
    boundary = run(FAMILIES["chain_hunt"](0), "cache_layout:edit_boundary=true+agentdiet")
    assert boundary["score"] == plain["score"] == 1.0
    assert boundary["cache_hit_rate"] > plain["cache_hit_rate"] + 0.1
    assert boundary["by_tag"]["main"]["cost"] < 0.8 * plain["by_tag"]["main"]["cost"]


def test_edit_boundary_renders_converse_cache_points():
    """What Bedrock receives: cachePoints on tools, system, the stable boundary and the newest message (≤ 4)."""
    from eam.agent.loop import run_agent
    from eam.llm.render import render_converse

    sent = []

    class Capture(MockLLM):
        def converse(self, req):
            sent.append(render_converse(req))
            return super().converse(req)

    inst = FAMILIES["chain_hunt"](0)
    run_agent(inst.prompt, llm=Capture(inst.oracle()), model=M, env_tools=inst.tools,
              techniques=build("cache_layout:edit_boundary=true+obs_mask"), max_steps=8)
    last = sent[-1]
    n_points = (sum("cachePoint" in t for t in last["toolConfig"]["tools"]) + sum("cachePoint" in b for b in last["system"])
                + sum("cachePoint" in b for m in last["messages"] for b in m["content"]))
    assert n_points == 4
    marked = [i for i, m in enumerate(last["messages"]) if any("cachePoint" in b for b in m["content"])]
    assert marked[-1] == len(last["messages"]) - 1 and marked[0] < len(last["messages"]) - 3
