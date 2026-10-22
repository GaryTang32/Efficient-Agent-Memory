"""Context-Folding — Sun et al., "Scaling Long-Horizon LLM Agent via Context-Folding" (FoldGRPO), ICML 2026
(ByteDance Seed). Branch/return protocol from the official FoldAgent repo (third_party/foldagent.py):

* MAIN gets a `branch(description, prompt)` tool. A branch **inherits MAIN's full context**, receives
  BRANCH_MESSAGE, works with the normal tools plus `return(message)`, and ends when it calls `return`.
* MAIN's context then gets only "Branch has finished its task, the returned message is: …" — the branch's
  own steps are folded away. At most MAX_SESSION=5 branches per task.
* Because a branch starts from MAIN's exact history, it reuses MAIN's prompt cache.

Adaptations (documented): the paper trains Seed-OSS-36B with FoldGRPO; here the protocol is used prompt-only
(the repo's README also evaluates it with off-the-shelf models). FoldAgent's role section of the system prompt
is search/coding specific; the short MAIN/BRANCH guidance below is condensed from its SEARCH_SYSTEM_PROMPT_BRANCH.
"""

from __future__ import annotations

import copy

from eam.agent.context import Tool
from eam.llm.types import ToolSpec
from eam.techniques.base import Technique
from eam.techniques.third_party import foldagent as P

ROLE_GUIDE = (
    "You operate in one of two modes: MAIN or BRANCH. As MAIN you plan, break the problem into independent "
    "sub-tasks, and assign each one to a branch with the `branch` tool — one task at a time, with highly "
    "specific instructions and the format you need back — then synthesise the returned findings. As a BRANCH "
    "you execute only the assigned sub-task and deliver your report with the `return` tool."
)


def _branch_spec() -> ToolSpec:
    return ToolSpec("branch", P.BRANCH_DESCRIPTION, {
        "type": "object",
        "properties": {"description": {"type": "string", "description": P.BRANCH_PARAM_DESCRIPTION},
                       "prompt": {"type": "string", "description": P.BRANCH_PARAM_PROMPT}},
        "required": ["description", "prompt"]})


class ContextFolding(Technique):
    name = "folding"
    source = "Context-Folding / FoldGRPO, ICML 2026 (ByteDance Seed)"
    provenance = "official branch/return protocol (Apache-2.0), prompt-only"

    def __init__(self, max_sub_steps: int = 20, max_session: int = P.MAX_SESSION, sub_techniques: list | None = None):
        self.max_sub_steps = int(max_sub_steps)
        self.max_session = int(max_session)
        self.sub_techniques = sub_techniques or []

    def system_addendum(self):
        return ROLE_GUIDE

    def tools(self, ctx):
        def branch(args, ctx):
            from eam.agent.loop import run_agent

            count = ctx.state.get("fold_branches", 0)
            if count + 1 > self.max_session:
                return P.LIMIT_REACHED.format(n=count)
            ctx.state["fold_branches"] = count + 1
            description = str(args.get("description", "Agent"))
            prompt = str(args.get("prompt", "Empty prompt"))
            history = copy.deepcopy(ctx.messages)
            pending = [b["toolUse"] for b in history[-1]["content"] if "toolUse" in b]
            results = []
            for tu in pending:  # close the open tool calls so the branch history is valid
                is_this = tu["name"] == "branch" and tu.get("input", {}).get("prompt") == prompt
                text = (P.BRANCH_MESSAGE + "\n\n" + P.BRANCH_OBSERVATION.format(description=description)
                        if is_this else "(not executed: MAIN is waiting for a branch)")
                results.append({"toolResult": {"toolUseId": tu["toolUseId"], "content": [{"text": text}]}})
            history.append({"role": "user", "content": results})

            # Same tool list as MAIN (env tools, branch, return) so the cached prefix is shared, as in FoldAgent.
            sub_tools = [*ctx.env_tools, Tool(_branch_spec(), lambda a, sub: P.NO_NESTING), self._return_tool()]
            sub = run_agent(ctx.task, llm=ctx.llm, model=ctx.model, aux_model=ctx.aux_model, models=ctx.models,
                            env_tools=sub_tools, techniques=list(self.sub_techniques),
                            system_prompt=ctx.system_text, max_steps=self.max_sub_steps, resources=ctx.resources,
                            meter=ctx.meter, store=ctx.store, tag="subagent", initial_messages=history)
            ctx.log("folded", description=description, sub_steps=sub.steps, returned=sub.finished)
            if sub.finished and sub.answer:
                return P.RETURNED.format(message=sub.answer)
            return P.RETURNED_NO_MESSAGE.format(last=sub.answer or "(no message)")

        return [Tool(_branch_spec(), branch), self._return_tool()]

    @staticmethod
    def _return_tool() -> Tool:
        def ret(args, ctx):
            if ctx.tag != "subagent":
                return "You are MAIN: `return` is only for branches. Give your final answer when you are done."
            ctx.stop_reason = "returned"
            ctx.final_answer = str(args.get("message", "Empty message"))
            return "Returned to MAIN."

        return Tool(ToolSpec("return", P.RETURN_DESCRIPTION, {
            "type": "object", "properties": {"message": {"type": "string", "description": P.RETURN_PARAM_MESSAGE}},
            "required": ["message"]}), ret)
