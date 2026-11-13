"""Always-on run traces for failure analysis (the research store; standard library only).

Every bench run writes one gzipped JSONL file, ``<EAM_TRACES>/<run_id>.jsonl.gz`` (default ``results/traces``;
``EAM_TRACES=off`` turns traces off). Each line is one record with a ``table`` field and the ``run_id`` that also
appears in the run's result row:

    run       spec, task, model, score, cost (one line)
    session   per session: score, finished, answer
    message   per message of every session: role, text, tool calls and tool results (long text cut, length kept)
    tool_call per tool call: name, input, output size, error flag (joined to its result by tool_use_id)
    event     per harness event (compaction, recall with note names, preview, guard offload, overflow); `fields`
              is a JSON string (DuckDB: json_extract(fields, '$.notes'))
    call      per LLM call: tag, tokens (input, output, cache read and write), cost, latency
    grade     per graded session where the task provides one (SWE-bench: the agent's patch and the test report)

Text is redacted (`eam.safety.redact`) before it is written. Query with DuckDB, for example
``SELECT * FROM read_json('results/traces/*.jsonl.gz') WHERE "table" = 'event'``.
"""

from __future__ import annotations

import gzip
import json
import os
import uuid
from pathlib import Path
from typing import Any, Iterable

from eam.safety import redact

TEXT_CAP = 8_000  # characters kept per text block; the full length is recorded


def new_run_id() -> str:
    return uuid.uuid4().hex[:16]


def trace_dir() -> Path | None:
    d = os.environ.get("EAM_TRACES", "results/traces")
    return None if d.lower() in ("off", "0", "false", "no", "") else Path(d)


def _text(s: Any) -> dict[str, Any]:
    s = s if isinstance(s, str) else json.dumps(s, default=str)
    return {"text": redact(s[:TEXT_CAP]), "chars": len(s)}


def _blocks(content: Any) -> Iterable[dict[str, Any]]:
    if isinstance(content, str):
        yield {"text": content}
    elif isinstance(content, list):
        yield from (b for b in content if isinstance(b, dict))


def _message_records(session: int, messages: list[dict[str, Any]]) -> Iterable[dict[str, Any]]:
    results: dict[str, dict[str, Any]] = {}
    for m in messages:
        for b in _blocks(m.get("content")):
            tr = b.get("toolResult")
            if tr:
                out = "".join(c.get("text", "") for c in tr.get("content", []) if isinstance(c, dict))
                results[tr.get("toolUseId", "")] = {"chars": len(out), "error": tr.get("status") == "error"}
    for i, m in enumerate(messages):
        texts, uses, outs = [], [], []
        for b in _blocks(m.get("content")):
            if "text" in b:
                texts.append(b["text"])
            elif "toolUse" in b:
                tu = b["toolUse"]
                uses.append({"tool_use_id": tu.get("toolUseId"), "name": tu.get("name")})
                res = results.get(tu.get("toolUseId", ""), {})
                yield {"table": "tool_call", "session": session, "message": i, "tool_use_id": tu.get("toolUseId"),
                       "name": tu.get("name"), "input": _text(tu.get("input") or {})["text"],
                       "output_chars": res.get("chars"), "error": res.get("error")}
            elif "toolResult" in b:
                tr = b["toolResult"]
                out = "".join(c.get("text", "") for c in tr.get("content", []) if isinstance(c, dict))
                outs.append({"tool_use_id": tr.get("toolUseId"), **_text(out)})
        yield {"table": "message", "session": session, "index": i, "role": m.get("role"),
               **_text("\n".join(texts)), "tool_uses": uses, "tool_results": outs}


def write_trace(run_id: str, *, row: dict[str, Any], sessions: list[list[dict[str, Any]]],
                events: list[dict[str, Any]], calls: list[Any], grades: list[dict[str, Any]] | None = None
                ) -> Path | None:
    """Write one run's trace; returns its path (None when traces are off). Never raises: a trace must not fail a run."""
    d = trace_dir()
    if d is None:
        return None
    try:
        d.mkdir(parents=True, exist_ok=True)
        recs: list[dict[str, Any]] = [{"table": "run", **{k: row.get(k) for k in (
            "family", "instance", "spec", "model", "aux_model", "backend", "score", "round_scores", "success",
            "finished", "cost_usd", "steps", "tool_calls", "sessions", "peak_prompt_tokens", "context_limit",
            "backend_settings")}}]
        answers = row.get("round_answers") or [row.get("answer", "")]
        scores = row.get("round_scores") or [row.get("score")]
        for k, msgs in enumerate(sessions):
            recs.append({"table": "session", "session": k, "score": scores[k] if k < len(scores) else None,
                         **_text(answers[k] if k < len(answers) else "")})
            recs.extend(_message_records(k, msgs))
        for e in events:
            fields = {key: (_text(v)["text"] if isinstance(v, str) else v) for key, v in e.items()
                      if key not in ("kind", "session", "step", "raw")}
            recs.append({"table": "event", "session": e.get("session"), "step": e.get("step"), "kind": e.get("kind"),
                         "fields": json.dumps(fields, default=str)})  # a JSON string: one schema for every kind
        for i, c in enumerate(calls):
            u = c.usage
            recs.append({"table": "call", "index": i, "tag": c.tag, "model": c.model_key,
                         "input_tokens": u.input_tokens, "output_tokens": u.output_tokens,
                         "cache_read_tokens": u.cache_read_tokens, "cache_write_tokens": u.cache_write_tokens,
                         "cost_usd": c.cost, "latency_ms": c.latency_ms})
        for k, g in enumerate(grades or []):
            if g:
                recs.append({"table": "grade", "session": g.get("session", k), "resolved": g.get("resolved"),
                             "patch": _text(g.get("patch", "")), "report": _text(g.get("detail", ""))})
        path = d / f"{run_id}.jsonl.gz"
        tmp = path.with_suffix(".tmp")
        with gzip.open(tmp, "wt", encoding="utf-8") as fh:
            for r in recs:
                fh.write(json.dumps({"run_id": run_id, **r}, default=str) + "\n")
        os.replace(tmp, path)
        return path
    except Exception as exc:  # noqa: BLE001
        print(f"trace not written for run {run_id}: {exc}")
        return None
