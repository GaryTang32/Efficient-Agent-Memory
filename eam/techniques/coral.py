"""CORAL — agent-managed working memory with context resets (CUHK + Tencent + HKUST; COLM 2026; arXiv 2610.40350),
the prompting-only variant (the paper's +8.0 on BrowseComp with Claude Sonnet 4, no training).

The agent gets two tools besides the environment's: ``memory-management-tool`` (ADD / UPDATE / DELETE knowledge
units of type task_progress — a YAML plan — or verified_fact) and ``context-optimization-tool``. The agent alone
decides when to optimise; the prompt suggests after 3-5 tool calls, at a milestone or a dead end. A context
optimisation clears the conversation: the next episode starts from the system prompt and the reset template (the
user task, the rendered working memory, the agent's ``task_checkpoint``). Nothing else is kept.

System prompt, tool descriptions and reset template are verbatim from the paper (third_party/coral.py). The code
is not public (the linked repo returns 404), so unit ids, the memory rendering and the tool's return text are ours.
Deviations: the paper's prompt was the whole system prompt and refers to web search/browse tools; here it is
appended after the benchmark's own system prompt (which carries the FINAL ANSWER rule) and the environment's tools
are the task's. Working memory is per task (session), as in the paper.
"""

from __future__ import annotations

import json

from eam.agent.context import Tool
from eam.llm.types import ToolSpec
from eam.techniques.base import Technique
from eam.techniques.third_party import coral as P

MM_SCHEMA = {
    "type": "object",
    "properties": {"operations": {"type": "array", "items": {
        "type": "object",
        "properties": {
            "operation": {"type": "string", "enum": ["ADD", "UPDATE", "DELETE"]},
            "knowledge_unit": {"type": "object", "properties": {
                "type": {"type": "string", "description": "task_progress | verified_fact"},
                "content": {"type": "string", "description": "Concise, actionable description"},
                "relevance": {"type": "string", "description": "Why this is important"},
                "source": {"type": "array", "items": {"type": "string"}, "description": "Source references"}}},
            "unit_id": {"type": "string", "description": "ID for UPDATE/DELETE"},
            "rationale": {"type": "string", "description": "Why this operation is necessary"}},
        "required": ["operation"]}}},
    "required": ["operations"],
}
CO_SCHEMA = {
    "type": "object",
    "properties": {
        "optimization_reason": {"type": "string",
                                "description": "Detailed explanation of why context optimization is needed now"},
        "task_checkpoint": {"type": "string",
                            "description": "Detailed description of current task state and what needs to be done "
                                           "next"}},
    "required": ["task_checkpoint"],
}


class CORAL(Technique):
    name = "coral"
    source = "CORAL (CUHK + Tencent + HKUST), arXiv 2610.40350, prompting-only"
    provenance = "paper prompts and tools verbatim; code not public (memory rendering ours)"
    cache_safe = False  # a context optimisation replaces the history

    def __init__(self, max_units: int = 200):
        self.max_units = int(max_units)

    def system_addendum(self):
        return P.SYSTEM_PROMPT

    def on_session_start(self, ctx):
        ctx.state["coral"] = {"units": {}, "next_id": 1, "mm": 0, "co": 0, "episodes": 1, "pending": None,
                              "user_query": None}

    @staticmethod
    def render_memory(units: dict) -> str:
        def part(kind, title):
            rows = []
            for uid, u in units.items():
                if u.get("type") != kind:
                    continue
                extra = "; ".join(x for x in (u.get("relevance") or "", ", ".join(map(str, u.get("source") or [])))
                                  if x)
                rows.append(f"[{uid}] {u.get('content', '')}" + (f" ({extra})" if extra else ""))
            return f"## {title}\n" + ("\n".join(rows) if rows else "(empty)")

        return part("task_progress", "Task Progress") + "\n\n" + part("verified_fact", "Verified Facts")

    def tools(self, ctx):
        def mm(args, ctx):
            st = ctx.state["coral"]
            st["mm"] += 1
            ops = args.get("operations")
            if isinstance(ops, dict):
                ops = [ops]
            if not isinstance(ops, list) or not ops:
                raise ValueError("operations must be a non-empty list")
            done = []
            for op in ops:
                kind = str(op.get("operation", "")).upper()
                unit = op.get("knowledge_unit") or {}
                uid = str(op.get("unit_id") or "").strip()
                if kind == "ADD":
                    if len(st["units"]) >= self.max_units:
                        raise ValueError("working memory is full; DELETE or UPDATE units")
                    uid = f"U{st['next_id']}"
                    st["next_id"] += 1
                    st["units"][uid] = {k: unit.get(k) for k in ("type", "content", "relevance", "source")}
                    st["units"][uid]["type"] = str(unit.get("type") or "verified_fact").strip()
                    done.append(f"ADD {uid}")
                elif kind == "UPDATE":
                    if uid not in st["units"]:
                        raise ValueError(f"no unit '{uid}' (units: {', '.join(st['units']) or 'none'})")
                    st["units"][uid].update({k: v for k, v in unit.items() if v is not None})
                    done.append(f"UPDATE {uid}")
                elif kind == "DELETE":
                    if uid not in st["units"]:
                        raise ValueError(f"no unit '{uid}' (units: {', '.join(st['units']) or 'none'})")
                    del st["units"][uid]
                    done.append(f"DELETE {uid}")
                else:
                    raise ValueError(f"unknown operation '{kind}'")
            return "Memory updated (" + ", ".join(done) + ").\n\n" + self.render_memory(st["units"])

        def co(args, ctx):
            st = ctx.state["coral"]
            st["co"] += 1
            text = P.RESET_TEMPLATE.replace("{user_query}", st["user_query"] or ctx.task_header()) \
                .replace("{memory_summary}", self.render_memory(st["units"])) \
                .replace("{task_checkpoint}", str(args.get("task_checkpoint", "")))
            st["pending"] = text
            ctx.log("coral_optimize", reason=str(args.get("optimization_reason", ""))[:300])
            return text

        return [Tool(ToolSpec("memory-management-tool", P.MEMORY_TOOL_DESCRIPTION, MM_SCHEMA), mm),
                Tool(ToolSpec("context-optimization-tool", P.CONTEXT_TOOL_DESCRIPTION, CO_SCHEMA), co)]

    def before_call(self, ctx):
        st = ctx.state["coral"]
        if st["user_query"] is None and ctx.messages:
            # the session's first message (task header and any recalled notes), without the context gauge
            st["user_query"] = "\n".join(b["text"] for b in ctx.messages[0]["content"]
                                         if "text" in b and not b["text"].startswith("[Context used:"))
        if st["pending"]:
            ctx.messages[:] = [{"role": "user", "content": [{"text": st["pending"]}]}]
            st["pending"] = None
            st["episodes"] += 1
            ctx.log("coral_reset", episode=st["episodes"], units=len(st["units"]))

    def on_session_end(self, ctx, answer):
        st = ctx.state["coral"]
        ctx.log("coral_record", mm_calls=st["mm"], co_calls=st["co"], episodes=st["episodes"],
                units=len(st["units"]))
