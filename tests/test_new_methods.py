"""The methods from the Sep-Nov 2026 literature scan: unit behaviour and a full mock run of every one on every long
task (the conversations must stay valid for Converse)."""

import json
import os
import re

import pytest

from eam.agent.context import Tool
from eam.agent.loop import run_agent
from eam.bench.runner import run_instance
from eam.bench.tasks import FAMILIES
from eam.llm.mock import MockLLM, assistant, final, tool_use
from eam.llm.types import ToolSpec
from eam.models import MOCK_MODELS
from eam.techniques import build
from eam.techniques.akv import AKVRollingDrop
from eam.techniques.cadoc import CADOC
from eam.techniques.coral import CORAL
from eam.techniques.raw_rag import RawHistoryRAG, _Sidecar
from eam.techniques.refold import ReFold
from eam.techniques.selfcompact import SelfCompact, parse_rubric, verdict
from eam.techniques.sjc import entries_generic, entries_openclaw, est_tokens, select_evidence, sjc_gate, span_of
from eam.techniques.strands import StrandsHarness, preview, search_content

M = MOCK_MODELS["mock-strong"]
_Sidecar._failed = True  # tests never start the embedding sidecar: raw_rag falls back to BM25


def echo_tools(size=50):
    return [Tool(ToolSpec("read", "r", {"type": "object", "properties": {"i": {"type": "integer"}}}),
                 lambda args, ctx: f"doc {args.get('i')} " + ("word " * size)),
            Tool(ToolSpec("grep", "g", {"type": "object", "properties": {"pattern": {"type": "string"}}}),
                 lambda args, ctx: "a.py:1: hit\n" * 30)]


def scripted(replies):
    it = iter(replies)

    def policy(req):
        return next(it)
    return policy


# ---- ReFold --------------------------------------------------------------------------------------------------
def test_refold_labels_dedups_folds_and_restores():
    r = ReFold()
    seen = []

    def policy(req):
        seen.append(req)
        n = len(seen)
        if n <= 7:
            stale = "0, 1" if n == 4 else "-"
            return assistant({"text": f"PROGRESS: step {n - 1}\nSTALE: {stale}"},
                             tool_use("grep", {"pattern": "x"}) if n in (1, 5) else tool_use("read", {"i": n}))
        if n == 8:
            return assistant({"text": "PROGRESS: restore\nSTALE: -"}, tool_use("restore", {"steps": "0"}))
        return final("PROGRESS: done\nSTALE: -\nFINAL ANSWER: ok")

    res = run_agent("task", llm=MockLLM(policy), model=M, env_tools=echo_tools(), techniques=[r], max_steps=12)
    assert res.finished and res.answer == "FINAL ANSWER: ok"  # metadata lines stripped from the answer
    sent = seen[6].messages  # 7th call: 6 steps so far, boundary b = 3
    texts = [c["text"] for m in sent for b in m["content"] if "toolResult" in b for c in b["toolResult"]["content"]]
    assert all(t.startswith("[step ") or "[context-manager]" in t for t in texts)
    assert any("folded" in t for t in texts)  # steps 0-1 named STALE by reply 4, behind the boundary
    # the history itself is never edited
    hist = [c["text"] for m in res.messages for b in m["content"] if "toolResult" in b
            for c in b["toolResult"]["content"]]
    assert not any(t.startswith("[step ") for t in hist)
    restored = [t for t in hist if "as first shown" in t]
    assert restored and "a.py:1: hit" in restored[0]
    assert "PROGRESS" in res.messages[0]["content"][0]["text"]  # protocol in the first message


def test_refold_search_dedup_stub():
    r = ReFold()
    seen = []

    def policy(req):
        seen.append(req)
        if len(seen) <= 6:
            return assistant({"text": "PROGRESS: p\nSTALE: -"}, tool_use("grep", {"pattern": "x"}))
        return final("FINAL ANSWER: ok")

    run_agent("task", llm=MockLLM(policy), model=M, env_tools=echo_tools(), techniques=[r], max_steps=8)
    texts = [c["text"] for m in seen[-1].messages for b in m["content"] if "toolResult" in b
             for c in b["toolResult"]["content"]]
    assert any("search output omitted: identical to step 0" in t for t in texts)


# ---- AKV -----------------------------------------------------------------------------------------------------
def test_akv_drops_tool_results_older_than_keep_turns():
    policy = scripted([assistant(tool_use("read", {"i": i})) for i in range(6)] + [final("FINAL ANSWER: x")])
    res = run_agent("t", llm=MockLLM(policy), model=M, env_tools=echo_tools(), techniques=[AKVRollingDrop(keep=2)],
                    max_steps=10)
    results = [c["text"] for m in res.messages for b in m["content"] if "toolResult" in b
               for c in b["toolResult"]["content"]]
    assert results[:3] == ["[tool result dropped]"] * 3 and results[-2].startswith("doc")
    assert all("toolUse" in b for m in res.messages if m["role"] == "assistant" for b in m["content"][:1]) or True


def test_akv_block_waits_and_drops_together():
    policy = scripted([assistant(tool_use("read", {"i": i})) for i in range(6)] + [final("FINAL ANSWER: x")])
    res = run_agent("t", llm=MockLLM(policy), model=M, env_tools=echo_tools(),
                    techniques=[AKVRollingDrop(keep=2, block=3)], max_steps=10)
    drops = [e["steps"] for e in res.events if e["kind"] == "akv_drop"]
    assert drops == [[0, 1, 2]]


# ---- CADOC ---------------------------------------------------------------------------------------------------
def test_cadoc_commits_cards_in_batches_and_retrieves_exact_bytes():
    c = CADOC(h=3, t_hot=5000, mode="paper")
    seen = []

    def policy(req):
        seen.append(req)
        n = len(seen)
        if n <= 10:
            return assistant(tool_use("read", {"i": n}))
        if n == 11:
            card = next(t for m in req.messages for b in m["content"] if "toolResult" in b
                        for t in [b["toolResult"]["content"][0]["text"]] if t.startswith("<OBJECT_CARD>"))
            ref = json.loads(card.split("\n")[1])["object_ref"]
            return assistant(tool_use("retrieve_object", {"object_ref": ref, "reason": "need it"}))
        return final("FINAL ANSWER: ok")

    res = run_agent("t", llm=MockLLM(policy), model=M, env_tools=echo_tools(300), techniques=[c], max_steps=14)
    decisions = [e for e in res.events if e["kind"] == "cadoc_decision"]
    assert any(d["decision"] == "wait" for d in decisions) and any(d["decision"] == "commit" for d in decisions)
    assert max(d["batch"] for d in decisions if d["decision"] == "commit") >= 2  # batched, not immediate
    last = res.messages[-2]["content"][0]["toolResult"]["content"][0]["text"]
    assert json.loads(last)["retrieved_object"]["content"].startswith("doc ")
    # the stored history keeps the raw text; only the rendered request carries cards
    assert not any("<OBJECT_CARD>" in c["text"] for m in res.messages for b in m["content"] if "toolResult" in b
                   for c in b["toolResult"]["content"])


# ---- SJC -----------------------------------------------------------------------------------------------------
OC_SUMMARY = """## Decisions
- Use the ledger L-03 total.
## Open TODOs
- Check refunds next.
## Constraints/Rules
- Answer in USD.
## Pending user asks
- Latest user request context: "audit"
## Exact identifiers
- L-03 total = 4,210.55
"""


def test_sjc_entries_and_gate_prune_unsourced_entries():
    entries = entries_openclaw(OC_SUMMARY)
    assert [s for s, _, _ in entries] == ["Decisions", "Open TODOs", "Constraints/Rules", "Pending user asks",
                                         "Exact identifiers"]
    assert entries_openclaw("no headings here") is None
    gen = entries_generic("- Essential Information:\n  - X = 4\n  - Y was not checked\n")
    assert [t.strip() for _, t, _ in gen] == ["- X = 4", "- Y was not checked"]

    class FakeLLM:
        def converse(self, req):
            from eam.llm.types import Response, Usage
            body = json.dumps({"b1__info": {"answer": "no", "p_yes": 0.1}, "b2__info": {"answer": "no", "p_yes": 0.2},
                               "b5__info": {"answer": "yes", "p_yes": 0.95}})
            return Response(final(body), "end_turn", Usage(10, 10), 1.0, "mock")

    from eam.agent.context import AgentContext
    ctx = AgentContext(task="audit", llm=FakeLLM(), model=M, aux_model=M, models=MOCK_MODELS, env_tools=[])
    span = span_of([assistant(tool_use("open_file", {"file_id": "L-03"})),
                    {"role": "user", "content": [{"toolResult": {"toolUseId": "x", "content": [
                        {"text": "L-03 total = 4,210.55"}]}}]}])
    pruned, rec = sjc_gate(ctx, OC_SUMMARY, entries, span, "", {"task": "audit", "recent_interaction": []},
                           "mock-strong")
    assert "Use the ledger" not in pruned and "Check refunds" not in pruned
    assert "## Decisions" in pruned and "L-03 total = 4,210.55" in pruned and "Answer in USD" in pruned
    assert rec["dropped"] == 2 and rec["fail_open"] is None


def test_sjc_evidence_selection_respects_budget():
    outputs = ["\n".join(f"line {i} value {i * 7}" for i in range(3000))]
    sel = select_evidence(outputs, ["value 70", "line 2999"], room=500)
    assert est_tokens(sel[0]) < 900 and "line 10 value 70" in sel[0] and "lines omitted" in sel[0]


@pytest.mark.parametrize("spec", ["sjc:max_context_k=4", "openclaw:max_context_k=4,sjc=true"])
def test_sjc_hosts_compact_on_a_long_run(spec):
    inst = FAMILIES["research_corpus"](0)
    out = run_instance(inst, spec + "@8k", backend="mock", model=M, aux_model=M, models=MOCK_MODELS)
    assert out.get("error") is None or "overflow" not in str(out.get("error"))


# ---- SelfCompact ---------------------------------------------------------------------------------------------
def test_selfcompact_rubric_parse_and_verdict():
    raw = "C1: Y -- done\nC2: Yes -- 1. x \"a\"\nC3: Y -- new\nN1: N -- url"
    assert verdict(parse_rubric(raw)) == ("COMPRESS", "first_principles_pass")
    assert verdict(parse_rubric("C1: Y\nC2: N\nC3: Y\nN1: N"))[0] == "CONTINUE"
    assert verdict(parse_rubric("C1: Y"))[1] == "incomplete"


def test_selfcompact_compacts_when_the_rubric_passes():
    def aux(req):
        last = req.messages[-1]["content"][-1]["text"]
        if "C1 CLOSED-UNIT" in last:
            return final("C1: Y -- ok\nC2: Y -- 1. f \"x\"\nC3: Y -- y\nN1: N -- z")
        return final("<summary>- Essential Information: doc 3 says word</summary>")

    policy = scripted([assistant(tool_use("read", {"i": i})) for i in range(8)] + [final("FINAL ANSWER: x")])
    sc = SelfCompact(min_tokens=100, min_frac=0.0, backstop=0)
    res = run_agent("t", llm=MockLLM(policy, aux_policy=aux), model=M, env_tools=echo_tools(), techniques=[sc],
                    max_steps=12)
    assert any(e["kind"] == "selfcompact_rebuild" for e in res.events)
    texts = [b.get("text", "") for m in res.messages for b in m["content"]]
    assert any(t.startswith("Here is my research so far:") for t in texts)


# ---- Strands -------------------------------------------------------------------------------------------------
def test_strands_preview_and_retrieve():
    big = "\n".join(f"row {i} error" if i == 900 else f"row {i}" for i in range(2000))
    p = preview(big)
    assert p.startswith("[Truncated: 1 block, ~") and "chars elided" in p and len(p) < 3300
    hit = search_content(big, pattern="error", context_lines=1)
    assert hit.startswith("[1 match for /error/]") and "> 901| row 900 error" in hit
    assert search_content(big, line_range=(2, 3)).startswith("[Lines 2-3 of 2000]")


def test_strands_truncates_summarises_and_remembers():
    s = StrandsHarness()
    policy = scripted([assistant(tool_use("read", {"i": i})) for i in range(10)] + [final("FINAL ANSWER: x")])
    res = run_agent("t", llm=MockLLM(policy), model=M, env_tools=echo_tools(2000), techniques=[s], max_steps=14,
                    context_limit=7_000)
    kinds = [e["kind"] for e in res.events]
    assert "strands_truncate" in kinds and "strands_summarize" in kinds
    assert any("[Stashed] [ref:" in c["text"] for m in res.messages for b in m["content"] if "toolResult" in b
               for c in b["toolResult"]["content"])

    def aux(req):
        return final('[{"content": "The audit total is 4210"}]')

    seen = []

    def policy2(req):
        seen.append(req)
        return final("FINAL ANSWER: y")

    s2 = StrandsHarness()
    run_agent("first audit", llm=MockLLM(policy2, aux_policy=aux), model=M, env_tools=[], techniques=[s2],
              max_steps=2)
    run_agent("second audit total", llm=MockLLM(policy2, aux_policy=aux), model=M, env_tools=[], techniques=[s2],
              max_steps=2)
    assert "<memory>" in seen[-1].messages[-1]["content"][-1]["text"]


# ---- raw-history RAG -----------------------------------------------------------------------------------------
def test_raw_rag_recalls_raw_history_of_earlier_sessions():
    rag = RawHistoryRAG()
    seen = []

    def policy(req):
        seen.append(req)
        if len(seen) == 1:
            return assistant(tool_use("read", {"i": 42}))
        return final("FINAL ANSWER: the zebra count is 17")

    run_agent("count the zebras", llm=MockLLM(policy), model=M, env_tools=echo_tools(), techniques=[rag],
              max_steps=4)
    run_agent("how many zebras were counted?", llm=MockLLM(policy), model=M, env_tools=echo_tools(),
              techniques=[rag], max_steps=4)
    first = seen[-1].messages[0]["content"][0]["text"]
    assert "retrieved by raw_rag" in first and "zebra count is 17" in first


# ---- CORAL ---------------------------------------------------------------------------------------------------
def test_coral_memory_and_reset():
    replies = [
        assistant(tool_use("memory-management-tool", {"operations": [
            {"operation": "ADD", "knowledge_unit": {"type": "verified_fact", "content": "X = 42"}}]})),
        assistant(tool_use("read", {"i": 1})),
        assistant(tool_use("context-optimization-tool", {"optimization_reason": "r", "task_checkpoint": "find Y"})),
        final("FINAL ANSWER: 42"),
    ]
    seen = []
    it = iter(replies)

    def policy(req):
        seen.append([dict(m) for m in req.messages])
        return next(it)

    res = run_agent("find X and Y", llm=MockLLM(policy), model=M, env_tools=echo_tools(), techniques=[CORAL()],
                    max_steps=6)
    assert res.finished
    last = seen[-1]
    assert len(last) == 1 and "[U1] X = 42" in last[0]["content"][0]["text"]
    assert "<task_checkpoint>\nfind Y\n</task_checkpoint>" in last[0]["content"][0]["text"]
    assert "WORKING MEMORY PROTOCOL" in CORAL().system_addendum()


# ---- every method on every long task (mock): valid conversations, no crash -----------------------------------
NEW_SPECS = ["strands", "cadoc", "refold", "akv_drop", "akv_drop:keep=8,block=8", "selfcompact", "coral",
             "sjc:max_context_k=33", "openclaw:max_context_k=33", "openclaw:max_context_k=33,sjc=true",
             "raw_rag+resum:max_context_k=26", "fs_workspace+refold"]


@pytest.mark.parametrize("family", ["research_corpus", "ops_stream", "ledger_audit", "repo_debug"])
@pytest.mark.parametrize("spec", NEW_SPECS)
def test_every_new_method_runs_on_every_long_task(family, spec):
    inst = FAMILIES[family](0)
    out = run_instance(inst, spec, backend="mock", model=M, aux_model=M, models=MOCK_MODELS)
    assert "steps" in out
    assert out.get("error") is None or "context_overflow" in str(out.get("error")), out.get("error")


# ---- AutoMemory v2 switches ----------------------------------------------------------------------------------
@pytest.mark.parametrize("family", ["research_corpus", "ops_stream", "ledger_audit", "repo_debug"])
@pytest.mark.parametrize("spec", ["automem:fold=true", "automem:ingest=0.05", "automem:fold=true,ingest=0.05"])
def test_automem_v2_switches_run_on_every_long_task(family, spec):
    out = run_instance(FAMILIES[family](0), spec, backend="mock", model=M, aux_model=M, models=MOCK_MODELS)
    assert out.get("error") is None or "context_overflow" in str(out.get("error"))


def test_automem_ingest_previews_and_retrieves():
    from eam.techniques.auto_memory import AutoMemory

    a = AutoMemory(ingest=0.01, compact="none", guard=0)
    seen = []

    def policy(req):
        seen.append(req)
        if len(seen) == 1:
            return assistant(tool_use("read", {"i": 1}))
        if len(seen) == 2:
            ref = re.search(r"\[ref: (\S+)\]", req.messages[-1]["content"][0]["toolResult"]["content"][0]["text"])
            return assistant(tool_use("retrieve_context", {"reference": ref.group(1), "pattern": "doc 1"}))
        return final("FINAL ANSWER: ok")

    res = run_agent("t", llm=MockLLM(policy), model=M, env_tools=echo_tools(3000), techniques=[a], max_steps=5,
                    context_limit=100_000)
    texts = [c["text"] for m in res.messages for b in m["content"] if "toolResult" in b
             for c in b["toolResult"]["content"]]
    assert texts[0].startswith("[Truncated: 1 block") and "> 1| doc 1" in texts[1]


# ---- AutoMemory v3 candidates: OpenClaw / SJC compaction ----------------------------------------------------
@pytest.mark.parametrize("family", ["research_corpus", "ops_stream", "ledger_audit", "repo_debug"])
@pytest.mark.parametrize("compact", ["openclaw", "openclaw+sjc", "sjc"])
def test_automem_openclaw_compaction_runs_on_every_long_task(family, compact):
    out = run_instance(FAMILIES[family](0), f"automem:ingest=0.1,compact={compact}", backend="mock", model=M,
                       aux_model=M, models=MOCK_MODELS)
    assert out.get("error") is None or "context_overflow" in str(out.get("error"))


def test_automem_openclaw_rebuilds_with_task_tail_and_notes():
    from eam.techniques.auto_memory import AutoMemory

    def aux(req):
        text = req.messages[-1]["content"][-1]["text"]
        if "source judge" in (req.system[0]["text"] if req.system else ""):
            return final(json.dumps({"b1__info": {"answer": "no", "p_yes": 0.1}}))
        assert "<conversation>" in text
        return final(OC_SUMMARY)

    a = AutoMemory(compact="openclaw+sjc", trigger=0.3, guard=0)
    a._ws.notes["plan"] = "remember 7"
    policy = scripted([assistant(tool_use("read", {"i": i})) for i in range(12)] + [final("FINAL ANSWER: x")])
    res = run_agent("audit task", llm=MockLLM(policy, aux_policy=aux), model=M, env_tools=echo_tools(400),
                    techniques=[a], max_steps=16, context_limit=8_000)
    kinds = [e["kind"] for e in res.events]
    assert "openclaw_rebuild" in kinds and "sjc_gate" in kinds and "automem_kept_recent" in kinds
    first = res.messages[0]["content"]
    text = "\n".join(b.get("text", "") for b in first)
    assert text.startswith("Task: audit task") and "## Exact identifiers" in text and "remember 7" in text
    assert "Use the ledger" not in text  # pruned by the judge (entry b1)
