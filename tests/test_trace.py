"""Every bench run writes a trace (eam/bench/trace.py): one gzipped JSONL file per run, joined to the result row by
run_id, with redacted text."""

import gzip
import json
from collections import Counter

from eam.bench.runner import run_instance
from eam.bench.tasks import FAMILIES
from eam.models import MOCK_MODELS

M = MOCK_MODELS["mock-strong"]


def _trace(tmp_path, monkeypatch, family, spec):
    monkeypatch.setenv("EAM_TRACES", str(tmp_path / "traces"))
    row = run_instance(FAMILIES[family](0), spec, backend="mock", model=M, aux_model=M, models=MOCK_MODELS)
    path = tmp_path / "traces" / f"{row['run_id']}.jsonl.gz"
    with gzip.open(path, "rt") as fh:
        recs = [json.loads(line) for line in fh]
    return row, recs


def test_a_multi_session_run_writes_every_table(tmp_path, monkeypatch):
    row, recs = _trace(tmp_path, monkeypatch, "ledger_audit", "automem:ingest=0.1")
    tables = Counter(r["table"] for r in recs)
    assert tables["run"] == 1 and tables["session"] == 3 and tables["message"] > 0 and tables["call"] == row["calls"]
    assert tables["tool_call"] == row["tool_calls"] and tables["event"] > 0
    assert all(r["run_id"] == row["run_id"] for r in recs)
    recall = [r for r in recs if r["table"] == "event" and r["kind"] == "automem_recall"]
    assert recall and all(isinstance(json.loads(r["fields"])["notes"], list) for r in recall)


def test_traces_can_be_switched_off(tmp_path, monkeypatch):
    monkeypatch.setenv("EAM_TRACES", "off")
    row = run_instance(FAMILIES["ledger_audit"](0), "naive", backend="mock", model=M, aux_model=M, models=MOCK_MODELS)
    assert row["run_id"] and not (tmp_path / "traces").exists()


def test_trace_text_is_redacted(tmp_path, monkeypatch):
    from eam.bench import trace

    monkeypatch.setenv("EAM_TRACES", str(tmp_path / "t"))
    key = "sk-ant-api03-AbCdEfGhIjKlMnOpQrStUvWxYz0123456789-_abcdEFGH"
    path = trace.write_trace("abc", row={"round_answers": [f"used {key}"]}, events=[], calls=[],
                             sessions=[[{"role": "user", "content": [{"text": f"export KEY={key}"}]}]])
    text = gzip.open(path, "rt").read()
    assert key not in text and "[REDACTED:anthropic_key]" in text


def test_the_trace_keeps_what_compaction_removed(tmp_path, monkeypatch):
    row, recs = _trace(tmp_path, monkeypatch, "ledger_audit", "automem:ingest=0.1,compact=resum,trigger=0.2")
    rebuilt = [r for r in recs if r["table"] == "event" and r["kind"] == "resum_rebuild"]
    msgs = [r for r in recs if r["table"] == "message"]
    assert [r for r in recs if r["table"] == "tool_call"].__len__() == row["tool_calls"]
    if rebuilt:  # the reset message holding the summary is in the record as well
        assert any("summary" in m["text"].lower() for m in msgs)
