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


def test_uncached_counterfactual_and_robust_verdict():
    from eam.bench.analyze import robustness, uncached_cost

    u = {"input_tokens": 1_000_000, "output_tokens": 0, "cache_read_tokens": 1_000_000, "cache_write_tokens": 0}
    r = {"model": "cc-sonnet", "cost_usd": 2.0 + 0.1, "usage": u, "prompt_cache": True}
    assert abs(uncached_cost(r) - 4.0) < 1e-9  # the cached megatoken is re-billed at the input rate

    def row(model, inst, spec, score, cost=1.0):
        return {"family": "t", "model": model, "instance": inst, "spec": spec, "score": score, "success": score == 1,
                "cost_usd": cost, "usage": dict(u, cache_read_tokens=0), "prompt_cache": spec != "naive"}

    rows = []
    for m in ("cc-haiku", "cc-sonnet"):
        rows += [row(m, "i0", "naive", 0.2), row(m, "i0", "full@native", 1.0), row(m, "i0", "good", 0.9),
                 row(m, "i0", "weak", 0.3)]
    rows += [row("cc-opus", "i0", "naive", 0.9), row("cc-opus", "i0", "full@native", 1.0),
             row("cc-opus", "i0", "good", 1.0)]  # no headroom on opus: recovery undefined there
    text = robustness(rows)
    assert "| `good` |" in text and "model-robust" in text.split("| `good` |")[1].splitlines()[0]
    assert "not effective" in text.split("| `weak` |")[1].splitlines()[0]
    assert "n/a (no headroom)" in text


def test_prompt_sizer_treats_fixed_overhead_as_overhead():
    from eam.agent.loop import _PromptSizer

    s = _PromptSizer()
    s.observe(1000, 2400)  # tiny first call; the CLI adds ~1.3K tokens of its own
    assert s.predict(13000) < 16000  # not 13000 × 2.4 = 31K
    s.observe(14000, 1400 + int(1.4 * 14000))
    s.observe(20000, 1400 + int(1.4 * 20000))
    assert abs(s.predict(30000) - (1400 + 1.4 * 30000)) < 1500  # dense-text undercount is still corrected


def test_a_retried_call_is_billed_twice_but_not_counted_twice_as_context():
    from eam.agent.loop import run_agent
    from eam.llm.mock import MockLLM, final, tool_use, assistant
    from eam.llm.types import Response, Usage

    class Retrying(MockLLM):  # like the CLI client after an empty reply: usage of two attempts, one prompt
        def converse(self, req):
            r = super().converse(req)
            size = r.usage.prompt_tokens
            return Response(r.message, r.stop_reason, r.usage + r.usage, r.latency_ms, r.model_key,
                            context_tokens=size, retries=1)

    inst = FAMILIES["ledger_audit"](0)
    steps = iter([assistant(tool_use("open_file", {"file_id": f"L-0{i}"})) for i in range(1, 5)])
    res = run_agent(inst.rounds[0], llm=Retrying(lambda req: next(steps, final("FINAL ANSWER: x"))), model=M,
                    env_tools=inst.tools, context_limit=30_000, max_steps=8)
    assert not any(e["kind"] == "context_overflow" for e in res.events)  # ~20K real, billed ~40K
    assert sum(e["kind"] == "llm_retry" for e in res.events) >= 4
    assert res.peak_prompt_tokens < 30_000 and res.meter.usage.prompt_tokens > 2 * res.peak_prompt_tokens


def test_repo_debug_scoring_uses_pristine_tests_and_penalises_regressions():
    from types import SimpleNamespace

    from eam.bench.tasks import repo_debug as rd

    inst = FAMILIES["repo_debug"](0)
    tools = {t.spec.name: t.handler for t in inst.tools}
    ctx = SimpleNamespace(meter=object(), task=inst.rounds[0])
    session1 = inst.gold.split(" | ")[0].removeprefix("session 1: ").split(", ")
    bug_ids = [b.split(" ")[0] for b in session1]
    # "fix" by editing the tests: does not count
    for b in bug_ids:
        test_file, test_name = rd.BUGS[b][3].split("::")
        tools["replace_in_file"]({"path": f"tests/{test_file}", "old": f"def {test_name}():",
                                  "new": f"def {test_name}():\n    return"}, ctx)
    assert inst.round_score(0, "") == 0.0
    # a real fix of both bugs: full score
    for b in bug_ids:
        path, good, bad, _, _ = rd.BUGS[b]
        tools["replace_in_file"]({"path": path, "old": bad, "new": good}, ctx)
    assert inst.round_score(0, "") == 1.0
    # breaking something that worked halves it
    tools["replace_in_file"]({"path": "ledgerkit/pagination.py", "old": "start = (number - 1) * per_page",
                              "new": "start = number * per_page"}, ctx)
    assert inst.round_score(0, "") == 0.5
    assert "FAILED" in tools["run_tests"]({}, ctx)
