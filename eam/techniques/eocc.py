"""EoCC: end-of-conversation compaction with a handoff recap ("You don't need long context", Belcak et al., NVIDIA,
arXiv 2611.05306; prompts in third_party/nvidia_eocc.py, quoted from the paper's App. G).

The rule, as in the paper:

* when the running context reaches the *compaction threshold* (``threshold`` × the total context limit; the paper's
  settings are 48K/36K, 32K/24K, 24K/18K, 16K/12K, so 0.75), the agent is sent the compaction prompt as a user
  message and writes a handoff recap with no tool calls;
* the conversation then resets to the system prompt, the task and the recap. Nothing else is kept.

Writer. ``writer="agent"`` is the paper's setting: the agent model writes the recap as the next turn of its own
conversation, so the whole history is read from the prompt cache and only the recap is new output.
``writer="aux"`` is this project's variant: the run's summariser (``--aux-model``) gets the conversation as a
transcript plus the same prompt, as AutoMemory does with ReSum (a cheaper model summarising for a stronger agent).

Variants: ``swe`` and ``general`` are the paper's prompts; ``brief`` is this project's: the same six fields as terse
bullets, pointers instead of copied code or output, at most 150 words (600 output tokens).

Deviations (this project's, documented): the paper gives the prompts as outlines; the texts that fill
``{persistence}``, ``{handoff_details}``, ``{submission_reminder}`` and the recap section are ours (below). The
paper's harness counts tokens with the provider's usage; ours uses the last real prompt size, as every other method
here does. ``first="task"`` (used inside AutoMemory) restarts from the task statement alone, so AutoMemory can add
its notes and recent steps itself; the default ``first="message"`` keeps the session's whole first message.
"""

from __future__ import annotations

import copy

from eam.llm.types import Request
from eam.techniques.base import Technique
from eam.techniques.third_party import nvidia_eocc as P

from eam.automem.prompts import (BRIEF_PROMPT, HANDOFF_DETAILS, PERSISTENCE, RECAP_SECTION,  # noqa: F401
                                    SUBMISSION_REMINDER, compaction_prompt)

VARIANTS = (*P.PROMPTS, "brief")
RECAP_TOKENS = {"brief": 600}


def _is_gauge(block) -> bool:
    return "text" in block and block["text"].startswith("[Context used:")


class HandoffCompaction(Technique):
    name = "eocc"
    source = "EoCC handoff compaction (NVIDIA, arXiv 2611.05306)"
    provenance = "official prompt (paper App. G, quoted); re-implemented trigger and reset"
    cache_safe = False  # the reset rewrites history (rarely)

    def __init__(self, threshold: float = 0.75, writer: str = "agent", variant: str = "general",
                 recap_tokens: int = 4096, first: str = "message", default_window: int = 200_000,
                 trigger_tokens: float | None = None):
        if writer not in ("agent", "aux"):
            raise ValueError("writer must be 'agent' or 'aux'")
        if variant not in VARIANTS:
            raise ValueError(f"variant must be one of {sorted(VARIANTS)}")
        self.threshold = float(threshold)
        self.writer = writer
        self.variant = variant
        self.recap_tokens = min(int(recap_tokens), RECAP_TOKENS.get(variant, int(recap_tokens)))
        self.first = first
        self.default_window = int(default_window)
        self._trigger_tokens = trigger_tokens  # absolute override (AutoMemory passes its own trigger)

    def describe(self) -> str:
        return f"eocc(threshold={self.threshold}, writer={self.writer}, variant={self.variant})"

    def trigger_tokens(self, ctx) -> float:
        if self._trigger_tokens is not None:
            return float(self._trigger_tokens)
        window = ctx.context_limit or getattr(ctx.model, "context_window", None) or self.default_window
        return self.threshold * window

    def on_session_start(self, ctx):
        ctx.state["eocc"] = {"first": None, "recaps": 0}

    def _recap(self, ctx) -> str:
        prompt = compaction_prompt(self.variant)
        if self.writer == "aux":
            transcript = ctx.transcript()
            return ctx.call_aux(f"<conversation>\n{transcript}\n</conversation>\n\n{prompt}", purpose="handoff",
                                system=ctx.system_text, max_tokens=self.recap_tokens).strip()
        # the agent's own next turn: same system prompt, tools and history (a prompt-cache hit), plus the prompt
        msgs = list(ctx.messages)
        last = msgs[-1]
        if last["role"] == "user":
            msgs[-1] = {**last, "content": [*last["content"], {"text": prompt}]}
        else:
            msgs.append({"role": "user", "content": [{"text": prompt}]})
        req = Request(model=ctx.model, system=[{"text": ctx.system_text}], messages=msgs,
                      tools=list(getattr(ctx, "tool_specs", []) or []), max_tokens=self.recap_tokens,
                      tag="aux:handoff")
        resp = ctx.llm.converse(req)
        ctx.meter.record(req.tag, ctx.model, resp.usage, resp.latency_ms, resp.reported_cost_usd)
        if not ctx.own_history_response(resp):  # the recap request itself was over the window
            return ""
        return "\n".join(b["text"] for b in resp.message["content"] if "text" in b).strip()

    def before_call(self, ctx):
        st = ctx.state.setdefault("eocc", {"first": None, "recaps": 0})
        if st["first"] is None and ctx.messages:
            st["first"] = copy.deepcopy([b for b in ctx.messages[0]["content"] if not _is_gauge(b)])
        if len(ctx.messages) < 3:
            return
        tokens = max(ctx.last_prompt_tokens, ctx.estimate_context_tokens())
        if tokens < self.trigger_tokens(ctx):
            return
        recap = self._recap(ctx)
        if not recap:
            ctx.log("handoff_failed", tokens_before=tokens)
            return
        first = [{"text": ctx.task_header()}] if self.first == "task" else copy.deepcopy(st["first"])
        ctx.messages[:] = [{"role": "user", "content": [*first, {"text": RECAP_SECTION.format(recap=recap)}]}]
        st["recaps"] += 1
        ctx.log("handoff_rebuild", tokens_before=tokens, recap_chars=len(recap), writer=self.writer)
