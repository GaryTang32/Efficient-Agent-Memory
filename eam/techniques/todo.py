"""Plan recitation — Manus todo.md.

The agent keeps a checklist through a tool; each update's result re-states the
whole plan at the *end* of the context, where attention is strongest, without
ever editing earlier messages (cache-safe).
"""

from __future__ import annotations

from eam.agent.context import Tool
from eam.llm.types import ToolSpec
from eam.techniques.base import Technique


class TodoRecitation(Technique):
    name = "todo"
    source = "Manus todo.md recitation"
    provenance = "engineering rules from the Manus blog (no paper)"

    def tools(self, ctx):
        def handler(args, ctx):
            items = args.get("items") or []
            ctx.state["todo"] = items
            lines = [f"- [{'x' if it.get('done') else ' '}] {it.get('text', '')}" for it in items]
            return "Current plan:\n" + "\n".join(lines)

        return [Tool(ToolSpec(
            "todo_write",
            "Record or update your step-by-step plan. Send the complete list every time; mark finished items done.",
            {"type": "object", "properties": {"items": {"type": "array", "items": {
                "type": "object", "properties": {"text": {"type": "string"}, "done": {"type": "boolean"}},
                "required": ["text"]}}}, "required": ["items"]},
        ), handler)]

    def system_addendum(self):
        return ("Planning: at the start call todo_write with your plan, and call it again whenever you finish "
                "a step, so the current plan stays at the end of your context.")
