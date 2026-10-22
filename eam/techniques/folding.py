"""Context folding — branch a sub-task into its own context, keep only its result.

ByteDance Seed "Scaling Long-Horizon LLM Agent via Context-Folding" (FoldGRPO)
and Tongyi AgentFold train this behaviour with RL; here it is exposed as a
``branch`` tool to a prompted agent. The sub-agent's whole trajectory folds
into one short tool result.
"""

from __future__ import annotations

from eam.agent.context import Tool
from eam.llm.types import ToolSpec
from eam.techniques.base import Technique

SUB_SYSTEM = (
    "You are handling a sub-task delegated by another agent. Use tools to gather what is asked, then reply "
    "without calling tools, starting with 'FINAL ANSWER:', giving every requested fact with exact values."
)


class ContextFolding(Technique):
    name = "folding"
    source = "Context-Folding / FoldGRPO (ByteDance Seed); AgentFold (Tongyi)"

    def __init__(self, max_sub_steps: int = 10, sub_techniques: list | None = None):
        self.max_sub_steps = int(max_sub_steps)
        self.sub_techniques = sub_techniques or []

    def tools(self, ctx):
        def handler(args, ctx):
            from eam.agent.loop import run_agent

            sub = run_agent(
                str(args.get("subtask", "")),
                llm=ctx.llm, model=ctx.model, aux_model=ctx.aux_model, models=ctx.models,
                env_tools=ctx.env_tools, techniques=list(self.sub_techniques), system_prompt=SUB_SYSTEM,
                max_steps=self.max_sub_steps, resources=ctx.resources, meter=ctx.meter, store=ctx.store,
                tag="subagent",
            )
            ctx.log("folded", sub_steps=sub.steps, finished=sub.finished)
            if not sub.finished:
                return f"Sub-task stopped after {sub.steps} steps without finishing."
            return f"Sub-task result: {sub.answer}"

        return [Tool(ToolSpec(
            "branch",
            "Delegate a self-contained sub-task (e.g. 'read report X and extract A, B, C') to a helper that "
            "works in a separate context. Only its final answer comes back, which keeps your context small.",
            {"type": "object", "properties": {"subtask": {"type": "string", "description": "Precise, self-contained instruction."}},
             "required": ["subtask"]},
        ), handler)]

    def system_addendum(self):
        return ("Context: for sub-tasks that need several tool calls or read long outputs to extract a few facts, "
                "use branch with a precise instruction instead of doing it yourself.")
