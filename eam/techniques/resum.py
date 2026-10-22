"""ReSum — periodic context summarisation (Alibaba Tongyi Lab, Tongyi DeepResearch).

When the context grows past ``trigger_tokens``, a (cheap) auxiliary model
summarises the trajectory into a compact state — verified evidence, open gaps,
next steps — and the conversation restarts from task + summary. Bounded
context, at the price of a cache break and possible detail loss per rebuild.
"""

from __future__ import annotations

from eam.techniques.base import Technique

RESUM_PROMPT = """You are compressing the working history of an agent so it can continue with a much shorter context.

Task the agent is solving:
{task}

Working history:
{history}

Write a summary the agent can continue from. Include, as compact bullet points:
1. Verified facts and evidence gathered so far, with every exact value (names, numbers, dates, ids) needed for the task.
2. What has already been checked (so it is not repeated).
3. Open questions and the next steps.
Do not add information that is not in the history."""


class ReSum(Technique):
    name = "resum"
    source = "ReSum (Alibaba Tongyi DeepResearch)"
    cache_safe = False

    def __init__(self, trigger_tokens: int = 12000, summary_tokens: int = 1000):
        self.trigger_tokens = int(trigger_tokens)
        self.summary_tokens = int(summary_tokens)

    def before_call(self, ctx):
        size = max(ctx.last_prompt_tokens, ctx.estimate_context_tokens())
        if size < self.trigger_tokens or len(ctx.messages) < 3:
            return
        summary = ctx.call_aux(
            RESUM_PROMPT.format(task=ctx.task, history=ctx.transcript()),
            purpose="summarize", max_tokens=self.summary_tokens)
        ctx.messages[:] = [{"role": "user", "content": [{"text": (
            f"{ctx.task_header()}\n\n## Progress so far (summary of your earlier work)\n{summary}\n\n"
            "Continue the task from here.")}]}]
        ctx.log("resum_rebuild", tokens_before=size)
