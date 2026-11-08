"""AutoMemory's adaptive workspace: one side question per session decides whether the note workspace is on."""

import pytest

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


def env():
    return [Tool(ToolSpec("read", "r", {"type": "object", "properties": {}}), lambda a, c: "data 42")]


def session(am, answer, task, seen):
    def aux(req):
        if req.tag == "aux:adaptive":
            seen.append("asked")
            return final(answer)
        return final("summary")

    def policy(req):
        seen.append(req)
        return final("FINAL ANSWER: stock of CG-71 is 42 units at the end of the day")

    return run_agent(task, llm=MockLLM(policy, aux_policy=aux), model=M, env_tools=env(), techniques=[am], max_steps=4)


def names(req):
    return {t.name for t in req.tools}


def test_independent_session_runs_lean_but_still_autosaves():
    am, seen = AutoMemory(workspace="adaptive", ingest=0.1), []
    res = session(am, "INDEPENDENT", "Fix issue 12345 in the repository.", seen)
    req = [x for x in seen if x != "asked"][0]
    assert "asked" in seen and "write_note" not in names(req) and "Workspace:" not in req.system[0]["text"]
    assert any(e["kind"] == "automem_adaptive" and e["workspace"] is False for e in res.events)
    assert am._ws.notes  # autosave kept the answer


def test_dependent_session_gets_tools_instruction_and_recall():
    am = AutoMemory(workspace="adaptive", ingest=0.1)
    session(am, "INDEPENDENT", "Day 1 of 10: stock of CG-71.", [])
    seen = []
    session(am, "DEPENDENT", "Day 2 of 10: continue from yesterday's stock.", seen)
    req = [x for x in seen if x != "asked"][0]
    assert "write_note" in names(req) and "Workspace:" in req.system[0]["text"]
    first = "\n".join(b.get("text", "") for b in req.messages[0]["content"])
    assert "CG-71 is 42 units" in first  # recall of the autosaved answer from day 1


def test_unclear_answer_keeps_the_workspace_on():
    am, seen = AutoMemory(workspace="adaptive"), []
    session(am, "maybe", "Some task.", seen)
    assert "write_note" in names([x for x in seen if x != "asked"][0])


def test_preset_and_fixed_modes_unchanged():
    (t,) = build("automem_v2_adaptive")
    assert t.adaptive and t.ingest == 0.1
    assert not AutoMemory(workspace=False).workspace and AutoMemory().workspace and not AutoMemory().adaptive


@pytest.mark.parametrize("family", ["research_corpus", "ops_stream", "ledger_audit", "repo_debug"])
def test_adaptive_runs_on_every_long_task(family):
    out = run_instance(FAMILIES[family](0), "automem_v2_adaptive", backend="mock", model=M, aux_model=M,
                       models=MOCK_MODELS)
    assert out.get("error") is None or "context_overflow" in str(out.get("error"))


def test_dependent_decision_is_sticky_for_the_rest_of_the_job():
    am = AutoMemory(workspace="adaptive")
    session(am, "DEPENDENT", "Day 1 of 10: stock.", [])
    seen = []
    session(am, "INDEPENDENT", "Day 2 of 10: stock.", seen)
    assert "write_note" in names([x for x in seen if x != "asked"][0]) and "asked" not in seen
