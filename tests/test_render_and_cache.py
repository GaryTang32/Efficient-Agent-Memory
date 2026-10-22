import pytest

from eam.llm.cache_sim import PrefixCacheSimulator
from eam.llm.render import render_converse, validate_messages
from eam.llm.types import CachePlan, Request, ToolSpec

BIG = "lorem ipsum dolor sit amet " * 400  # ~2.7k tokens


def user(text):
    return {"role": "user", "content": [{"text": text}]}


def asst(text):
    return {"role": "assistant", "content": [{"text": text}]}


def req(models, messages, cache=None, system=BIG):
    return Request(model=models["mock-strong"], system=[{"text": system}], messages=messages,
                   tools=[ToolSpec("t", "a tool", {"type": "object", "properties": {}})], cache=cache or CachePlan())


def test_render_places_cache_points(models):
    kwargs = render_converse(req(models, [user("hi")], CachePlan(tools=True, system=True, message_indices=[0])))
    assert kwargs["toolConfig"]["tools"][-1] == {"cachePoint": {"type": "default"}}
    assert kwargs["system"][-1] == {"cachePoint": {"type": "default"}}
    assert kwargs["messages"][0]["content"][-1] == {"cachePoint": {"type": "default"}}


def test_render_does_not_mutate_history(models):
    msgs = [user("hi")]
    render_converse(req(models, msgs, CachePlan(message_indices=[0])))
    assert msgs == [user("hi")]


def test_render_rejects_too_many_cache_points(models):
    with pytest.raises(ValueError):
        render_converse(req(models, [user("a"), asst("b"), user("c")],
                            CachePlan(tools=True, system=True, message_indices=[0, 1, 2])))


def test_validate_catches_orphan_tool_result():
    msgs = [user("q"), {"role": "assistant", "content": [{"toolUse": {"toolUseId": "x", "name": "t", "input": {}}}]},
            {"role": "user", "content": [{"toolResult": {"toolUseId": "y", "content": [{"text": "r"}]}}]}]
    with pytest.raises(ValueError):
        validate_messages(msgs, has_tools=True)


def test_validate_catches_role_alternation():
    with pytest.raises(ValueError):
        validate_messages([user("a"), user("b")], has_tools=False)


def test_cache_hit_on_identical_prefix(models):
    sim = PrefixCacheSimulator(min_tokens=1024)
    plan = CachePlan(system=True)
    _, read1, write1 = sim.account(render_converse(req(models, [user("one")], plan)))
    _, read2, write2 = sim.account(render_converse(req(models, [user("two")], plan)))
    assert read1 == 0 and write1 > 1024
    assert read2 == write1 and write2 == 0


def test_rolling_cache_point_reads_previous_turns(models):
    sim = PrefixCacheSimulator(min_tokens=1024)
    msgs = [user(BIG)]
    sim.account(render_converse(req(models, msgs, CachePlan(message_indices=[0]), system="s")))
    msgs = msgs + [asst("ok"), user("next")]
    uncached, read, write = sim.account(render_converse(req(models, msgs, CachePlan(message_indices=[2]), system="s")))
    assert read > 2000 and uncached == 0 and write < 50


def test_changed_prefix_misses(models):
    sim = PrefixCacheSimulator(min_tokens=1024)
    sim.account(render_converse(req(models, [user("q")], CachePlan(system=True))))
    _, read, _ = sim.account(render_converse(req(models, [user("q")], CachePlan(system=True), system="Now: 12:01 " + BIG)))
    assert read == 0


def test_below_min_tokens_is_not_cached(models):
    sim = PrefixCacheSimulator(min_tokens=1024)
    _, _, write = sim.account(render_converse(req(models, [user("q")], CachePlan(system=True), system="short")))
    assert write == 0
