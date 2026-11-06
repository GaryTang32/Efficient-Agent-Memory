"""IterResearch — periodic workspace reconstruction (Alibaba Tongyi Lab).

The agent maintains an evolving report itself (``update_report`` tool). Every
``round_steps`` calls the workspace is rebuilt to exactly: task + report +
latest observation. Unlike ReSum there is no extra summarisation call — the
agent's own report is the memory — and context size stays roughly constant.
"""

from __future__ import annotations

from eam.agent.context import Tool
from eam.llm.types import ToolSpec
from eam.techniques.base import Technique
from eam.techniques.common import last_results_text


class IterResearch(Technique):
    name = "iter_research"
    source = "IterResearch / WebResearcher (Alibaba Tongyi DeepResearch)"
    provenance = "ported from the paper description (no official code released)"
    cache_safe = False

    def __init__(self, round_steps: int = 4, observation_chars: int = 4000):
        self.round_steps = int(round_steps)
        self.observation_chars = int(observation_chars)

    def tools(self, ctx):
        def handler(args, ctx):
            ctx.state["report"] = str(args.get("report", ""))
            return f"Report saved ({len(ctx.state['report'])} chars)."

        return [Tool(ToolSpec(
            "update_report",
            "Replace your evolving report with an updated version. The report is the only thing that "
            "survives workspace resets, so include every fact you will need for the final answer.",
            {"type": "object", "properties": {"report": {"type": "string"}}, "required": ["report"]},
        ), handler)]

    def system_addendum(self):
        return (f"Memory: your working context is reset every {self.round_steps} steps to just the task, your "
                "report, and the latest observation. After each useful observation, call update_report with the "
                "full updated report (all facts with exact values, what is done, what is next).")

    def before_call(self, ctx):
        if ctx.step <= 1 or (ctx.step - 1) % self.round_steps:
            return
        report = ctx.state.get("report") or "(empty — you have not saved a report yet)"
        observation = last_results_text(ctx, self.observation_chars) or "(none)"
        ctx.messages[:] = [{"role": "user", "content": [{"text": (
            f"{ctx.task_header()}\n\n## Your report so far\n{report}\n\n## Latest observation\n{observation}\n\n"
            "Continue the task.")}]}]
        ctx.log("workspace_rebuild")
