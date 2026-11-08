"""EoCC handoff compaction (NVIDIA, arXiv 2611.05306): the technique, its AutoMemory switch, the library and MCP."""

import json

import pytest

from eam.agent.context import Tool
from eam.agent.loop import run_agent
from eam.bench.runner import run_instance
from eam.bench.tasks import FAMILIES
from eam.llm.mock import MockLLM, assistant, final, tool_use
from eam.llm.types import ToolSpec
from eam.memory_skill import MemorySkill
from eam.models import MOCK_MODELS
from eam.techniques import build
from eam.techniques.eocc import HandoffCompaction, compaction_prompt

M = MOCK_MODELS["mock-strong"]
RECAP = "1. Objective - fix x\n6. Remaining plan - next: read_file a.py"


def tools(size=400):
    return [Tool(ToolSpec("read", "r", {"type": "object", "properties": {"i": {"type": "integer"}}}),
                 lambda args, ctx: f"doc {args.get('i')} " + ("word " * size))]


def test_prompt_is_the_papers_with_placeholders_filled():
    p = compaction_prompt("swe")
    assert p.startswith("Stop work. Write only a concise handoff recap") and "5. Dead ends" in p
    assert "{" not in p and "FINAL ANSWER:" in p
    assert "Do not invent observations" in compaction_prompt("general")


def test_brief_variant_is_short_and_capped():
    p = compaction_prompt("brief")
    assert "at most 150 words" in p and "6. Next" in p and "{" not in p
    assert HandoffCompaction(variant="brief").recap_tokens == 600
    assert HandoffCompaction(variant="swe").recap_tokens == 4096


@pytest.mark.parametrize("writer", ["agent", "aux"])
def test_handoff_resets_to_task_and_recap(writer):
    side = []

    def policy(req):
        if req.tag == "main":
            n = sum(1 for m in req.messages if m["role"] == "assistant")
            return assistant(tool_use("read", {"i": n})) if len(side) == 0 or n < 2 else final("FINAL ANSWER: ok")
        raise AssertionError(req.tag)

    def aux(req):
        side.append(req)
        return final(RECAP)

    t = HandoffCompaction(threshold=0.5, writer=writer)
    res = run_agent("fix the bug", llm=MockLLM(policy, aux_policy=aux), model=M, env_tools=tools(), techniques=[t],
                    max_steps=20, context_limit=6000)
    assert any(e["kind"] == "handoff_rebuild" for e in res.events)
    req = side[0]
    assert req.tag == "aux:handoff"
    last = req.messages[-1]["content"][-1]["text"]
    if writer == "agent":  # the agent's own next turn: same system prompt and tools, history kept as is
        assert req.model is M and req.tools and req.system[0]["text"] and last.startswith("Stop work.")
        assert any("toolResult" in b for m in req.messages for b in m["content"])
    else:  # the summariser gets a transcript
        assert "<conversation>" in last and "Stop work." in last
    first = "\n".join(b.get("text", "") for b in res.messages[0]["content"])
    assert first.startswith("Task: fix the bug") and "<recap>\n" + RECAP in first
    assert res.answer.endswith("ok")


def test_handoff_skips_when_the_recap_is_empty():
    calls = {"n": 0}

    def policy(req):
        calls["n"] += 1
        return assistant(tool_use("read", {"i": calls["n"]})) if calls["n"] < 6 else final("FINAL ANSWER: ok")

    t = HandoffCompaction(threshold=0.01)
    res = run_agent("t", llm=MockLLM(policy, aux_policy=lambda req: final("")), model=M, env_tools=tools(400),
                    techniques=[t], max_steps=10, context_limit=100_000)
    kinds = [e["kind"] for e in res.events]
    assert "handoff_failed" in kinds and "handoff_rebuild" not in kinds


@pytest.mark.parametrize("family", ["research_corpus", "ops_stream", "ledger_audit", "repo_debug"])
@pytest.mark.parametrize("spec", ["eocc", "eocc:writer=aux", "automem:ingest=0.1,compact=handoff",
                                  "automem:workspace=false,ingest=0.1,compact=handoff_aux,handoff_variant=swe",
                                  "automem:workspace=false,ingest=0.1,compact=handoff,handoff_variant=brief,keep_recent=0"])
def test_handoff_runs_on_every_long_task(family, spec):
    out = run_instance(FAMILIES[family](0), spec, backend="mock", model=M, aux_model=M, models=MOCK_MODELS)
    assert "steps" in out
    assert out.get("error") is None or "context_overflow" in str(out.get("error")), out.get("error")


def test_automem_handoff_keeps_notes_and_recent_steps():
    from eam.techniques.auto_memory import AutoMemory

    a = AutoMemory(compact="handoff", trigger=0.3, guard=0)
    a._ws.notes["plan"] = "remember 7"
    n = {"i": 0}

    def policy(req):
        n["i"] += 1
        return assistant(tool_use("read", {"i": n["i"]})) if n["i"] < 12 else final("FINAL ANSWER: x")

    res = run_agent("audit task", llm=MockLLM(policy, aux_policy=lambda req: final(RECAP)), model=M,
                    env_tools=tools(), techniques=[a], max_steps=16, context_limit=8_000)
    kinds = [e["kind"] for e in res.events]
    assert "handoff_rebuild" in kinds and "automem_kept_recent" in kinds
    text = "\n".join(b.get("text", "") for b in res.messages[0]["content"])
    assert text.startswith("Task: audit task") and "<recap>" in text and "remember 7" in text


def test_lean_handoff_preset():
    from eam.techniques.auto_memory import AutoMemory

    (t,) = build("automem_v2_lean_handoff")
    assert isinstance(t, AutoMemory) and not t.workspace and t.compact == "handoff" and t.handoff_variant == "swe"


def test_build_registers_eocc():
    (t,) = build("eocc:threshold=0.6,writer=aux,variant=swe")
    assert isinstance(t, HandoffCompaction) and t.writer == "aux" and t.variant == "swe"


def test_memory_skill_handoff(tmp_path):
    s = MemorySkill(tmp_path, window=1000, compaction="handoff", summarize=lambda prompt: RECAP)
    s.write_note("plan", "remember 7")
    assert s.handoff_prompt().startswith("Stop work.")
    msgs = [{"role": "system", "content": "sys"}, {"role": "user", "content": "go"},
            {"role": "assistant", "content": "x" * 3000}]
    out = s.maybe_compact(msgs, context_tokens=900, question="fix it")
    assert out[0] == msgs[0] and len(out) == 2
    assert out[1]["content"].startswith("Task: fix it") and "remember 7" in out[1]["content"] and RECAP in out[1]["content"]
    assert s.maybe_compact(msgs, context_tokens=100, question="fix it") is msgs


def test_mcp_handoff_tool(tmp_path):
    from eam.mcp_server import TOOLS, Server

    assert any(t["name"] == "handoff" for t in TOOLS)
    srv = Server(MemorySkill(tmp_path))
    assert srv.call("handoff", {"question": "q", "variant": "swe"}).startswith("Stop work.")
    reset = srv.call("handoff", {"question": "q", "recap": RECAP})
    assert reset.startswith("Task: q") and RECAP in reset
    json.dumps(TOOLS)
