import pytest

from eam.agent.loop import run_agent
from eam.bench.experiments import COMBINED, INDIVIDUAL
from eam.bench.runner import run_instance
from eam.bench.tasks import FAMILIES
from eam.llm.mock import MockLLM
from eam.techniques import build
from eam.techniques.tiered_memory import TieredMemory

CASES = sorted({(fam, spec) for suite in (INDIVIDUAL, COMBINED) for fam, specs in suite.items() for spec in specs})


@pytest.mark.parametrize("family,spec", CASES)
def test_every_spec_runs_and_produces_valid_conversations(models, family, spec):
    # MockLLM validates each request shape, so rewritten histories that Bedrock would reject fail here.
    inst = FAMILIES[family](0)
    row = run_instance(inst, spec, backend="mock", model=models["mock-strong"], aux_model=models["mock-cheap"],
                       models=models)
    assert row["cost_usd"] > 0


def run(models, family, spec, seed=0):
    inst = FAMILIES[family](seed)
    res = run_agent(inst.prompt, llm=MockLLM(inst.oracle()), model=models["mock-strong"],
                    aux_model=models["mock-cheap"], models=models, env_tools=inst.tools, techniques=build(spec),
                    resources=inst.resources, max_steps=inst.max_steps)
    return inst, res


def test_baseline_solves_tasks(models):
    for family in ("needle_research", "inventory_ops", "long_document_qa"):
        inst, res = run(models, family, "full")
        assert inst.check(res.answer), family


def test_cache_layout_is_cheaper_and_append_only(models):
    _, full = run(models, "needle_research", "full")
    _, cached = run(models, "needle_research", "cache_layout")
    assert cached.meter.cost < full.meter.cost * 0.5
    assert cached.meter.cache_hit_rate() > 0.5
    assert cached.history_rewrites == 0


def test_offload_leaves_pointer_and_is_recoverable(models):
    inst, res = run(models, "needle_research", "offload")
    assert inst.check(res.answer)
    assert any("artifact://" in b["toolResult"]["content"][0]["text"]
               for m in res.messages for b in m["content"] if "toolResult" in b)
    assert any(b["toolUse"]["name"] == "read_artifact" for m in res.messages for b in m["content"] if "toolUse" in b)


def test_keep_last_n_rewrites_history_in_batches(models):
    _, res = run(models, "inventory_ops", "keep_last_n:keep=3,batch=4")
    assert 0 < res.history_rewrites < res.steps / 2


def test_resum_bounds_context(models):
    _, full = run(models, "inventory_ops", "full")
    inst, res = run(models, "inventory_ops", "resum:trigger_tokens=4000")
    assert res.peak_prompt_tokens < full.peak_prompt_tokens
    assert any(e["kind"] == "resum_rebuild" for e in res.events)
    assert "aux" in res.meter.by_tag()


def test_folding_keeps_main_context_small(models):
    _, full = run(models, "needle_research", "full")
    inst, res = run(models, "needle_research", "folding")
    assert inst.check(res.answer)
    main_peak = max(r.usage.prompt_tokens for r in res.meter.records if r.tag == "main")
    assert main_peak < full.peak_prompt_tokens / 3


def test_memagent_reads_document_in_one_tool_call(models):
    inst, res = run(models, "long_document_qa", "memagent")
    assert inst.check(res.answer) and res.steps == 2


def test_tiered_memory_persists_across_runs(models, tmp_path):
    inst = FAMILIES["multi_session_profile"](0)
    path = tmp_path / "mem.json"
    for session in inst.sessions:
        run_agent(session, llm=MockLLM(inst.oracle()), model=models["mock-strong"], env_tools=[],
                  techniques=[TieredMemory(path=str(path))], max_steps=2)
    assert path.exists()
    res = run_agent(inst.prompt, llm=MockLLM(inst.oracle()), model=models["mock-strong"], env_tools=[],
                    techniques=[TieredMemory(path=str(path))], max_steps=2)  # fresh instance, loads from disk
    assert inst.check(res.answer)


def test_auto_picks_preset_by_cache_support(models):
    for key, preset in (("mock-strong", "cache_first"), ("mock-nocache", "lean")):
        inst = FAMILIES["needle_research"](0)
        res = run_agent(inst.prompt, llm=MockLLM(inst.oracle()), model=models[key], env_tools=inst.tools,
                        techniques=build("auto"), max_steps=inst.max_steps)
        assert any(e["kind"] == "auto_selected" and e["preset"] == preset for e in res.events)


def test_spec_parsing():
    (t,) = build("offload:max_tokens=123,preview_tokens=7")
    assert t.max_tokens == 123 and t.preview_tokens == 7
    assert [x.name for x in build("cache_layout+todo")] == ["cache_layout", "todo"]
    with pytest.raises(KeyError):
        build("nope")
