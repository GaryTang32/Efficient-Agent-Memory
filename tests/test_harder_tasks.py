"""The long-horizon tasks (research_corpus, ops_stream) and the no-optimisation baseline (naive, @native)."""

from eam.bench.runner import run_instance, split_window
from eam.bench.tasks import FAMILIES
from eam.models import MOCK_MODELS
from eam.techniques import build

M = MOCK_MODELS["mock-strong"]


def run(inst, spec):
    return run_instance(inst, spec, backend="mock", model=M, aux_model=M, models=MOCK_MODELS)


def test_generation_is_deterministic():
    for family in ("research_corpus", "ops_stream"):
        a, b = FAMILIES[family](3), FAMILIES[family](3)
        assert a.gold == b.gold and (a.prompt == b.prompt)


def test_research_corpus_solvable_and_overflows_without_memory():
    inst = FAMILIES["research_corpus"](0)
    assert run(inst, "full@native")["score"] == 1.0  # oracle solves it when nothing is lost
    r = run(inst, "full")
    assert r["overflow"] and r["score"] == 0.0  # the documents it needs do not fit in the window


def test_research_corpus_scoring_is_per_question():
    inst = FAMILIES["research_corpus"](1)
    golds = [g.split(" (")[0].split(": ")[1] for g in inst.gold.split(" | ")]
    full = "\n".join(f"Q{i + 1}: {g}" for i, g in enumerate(golds))
    assert inst.score(full) == 1.0
    half = "\n".join(f"Q{i + 1}: {g if i % 2 == 0 else 'unknown'}" for i, g in enumerate(golds))
    assert 0.4 < inst.score(half) < 0.7


def test_ops_stream_needs_cross_session_memory():
    inst = FAMILIES["ops_stream"](0)
    assert all(s == 1.0 for s in run(inst, "full@native")["round_scores"])
    r = run(inst, "full")  # re-deriving from all files stops fitting after a few days
    assert r["overflow"] and r["round_scores"][0] == 1.0 and r["round_scores"][-1] == 0.0
    ws = run(inst, "fs_workspace")  # notes carry stock and tracked events across days
    assert all(s == 1.0 for s in ws["round_scores"]) and ws["steps"] < r["steps"]


def test_naive_disables_caching_and_offload():
    (t,) = build("naive")
    assert t.disable_prompt_cache and t.disable_offload
    inst = FAMILIES["ledger_audit"](0)
    r_naive, r_full = run(inst, "naive@native"), run(inst, "full@native")
    assert r_naive["prompt_cache"] is False and r_naive["offload"] is False and r_naive["context_limit"] is None
    # with caching off the simulator bills every prompt token as fresh input, even where cache points are set
    r = run_instance(inst, "naive+cache_layout@native", backend="mock", model=M, aux_model=M, models=MOCK_MODELS)
    assert r["cache_hit_rate"] == 0.0
    assert run(inst, "cache_layout@native")["cache_hit_rate"] > 0.3
    assert r_full["prompt_cache"] is True and r_full["offload"] is True


def test_window_suffix():
    assert split_window("fs_workspace+resum:max_context_k=40@native") == ("fs_workspace+resum:max_context_k=40",
                                                                          "native")
    assert split_window("full") == ("full", None)
    inst = FAMILIES["ledger_audit"](0)
    assert run(inst, "full@200k")["context_limit"] == 200_000
