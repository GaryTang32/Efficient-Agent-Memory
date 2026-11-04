"""AKV tool-response rolling drop — "Cache Engineering for Agents" (Fu, Wang, Min, …, Yu Wang; Tsinghua + CUHK;
arXiv 2610.28577; code https://github.com/thu-nics/AKV, Apache-2.0), at the prompt level.

AKV's main policy keeps the KV states of the latest 12 tool-response turns and *drops* older tool responses from
attention inside the serving engine (no re-prefill; the text stays in the request; positions are re-packed only past
a token threshold). Over a hosted API the KV cache is not ours to edit, so this is the closest reproducible version:
the same selection policy (``TurnTrigger`` every turn + ``TurnSelection(12, target="tool")``: every tool-result
message older than the latest 12 tool turns; assistant messages, the task and user messages are never touched), with
the dropped text actually removed. Converse needs a result for every tool call, so a dropped result becomes a short
constant placeholder (AKV has none).

The paper measured this text-level variant itself (§3.2): trimming to the latest 12 rounds "costs 1.85× as much as
the full-context baseline", because each drop edits the prompt about 13 turns from the end and every later turn is
re-prefilled. ``block`` > 1 is our cache-aware variant (not in the paper): wait until ``block`` turns are past the
window and drop them together, so the cache breaks once every ``block`` turns (retained turns oscillate between
``keep`` and ``keep + block``).
"""

from __future__ import annotations

from eam.techniques.base import Technique
from eam.techniques.steps import stable_prefix_len, step_indices

PLACEHOLDER = "[tool result dropped]"


class AKVRollingDrop(Technique):
    name = "akv_drop"
    source = "AKV / Cache Engineering for Agents (Tsinghua + CUHK), arXiv 2610.28577"
    provenance = "official selection policy (TurnTrigger + TurnSelection(12, tool)); prompt-level drop (API-only)"
    cache_safe = False

    def __init__(self, keep: int = 12, block: int = 1, placeholder: str = PLACEHOLDER):
        self.keep = int(keep)
        self.block = max(1, int(block))
        self.placeholder = placeholder

    def before_call(self, ctx):
        tool_steps = [(k, u) for k, (_, u) in enumerate(step_indices(ctx.messages))
                      if u is not None and any("toolResult" in b for b in ctx.messages[u]["content"])]
        dropped = ctx.state.setdefault("akv_dropped", set())
        expired = tool_steps[: max(0, len(tool_steps) - self.keep)]
        pending = [(k, u) for k, u in expired if k not in dropped]
        if not pending or len(pending) < self.block:
            return
        for k, u in pending:
            for b in ctx.messages[u]["content"]:
                if "toolResult" in b:
                    b["toolResult"]["content"] = [{"text": self.placeholder}]
            dropped.add(k)
        ctx.log("akv_drop", steps=[k for k, _ in pending])
        # everything up to the last dropped step is final: a cache point can sit there (Bedrock edit_boundary)
        ctx.state["stable_upto"] = stable_prefix_len(ctx.messages, max(dropped))
