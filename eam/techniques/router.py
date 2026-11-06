"""Per-step model / thinking routing.

Idea from hybrid-thinking models (Qwen3, DeepSeek V3.1+ think / non-think
modes) and MiniMax M2's interleaved thinking: spend reasoning where it pays —
planning and error recovery — and use a cheap model for routine tool calls.

Caveats (measure them!): prompt caches are per model, so every switch pays an
uncached prefix; and Claude requires the last assistant turn of a tool loop to
start with a thinking block when thinking is on, so thinking is only enabled
on the first (planning) step and its reasoning blocks are dropped afterwards.
"""

from __future__ import annotations

from eam.techniques.base import Technique


class ThinkingRouter(Technique):
    name = "router"
    source = "Qwen3 / DeepSeek hybrid thinking; MiniMax M2 interleaved thinking"
    provenance = "provisional (ours)"

    def __init__(self, strong: str | None = None, cheap: str | None = None, on: str = "plan,error",
                 thinking: bool = False):
        self.strong = strong
        self.cheap = cheap
        self.on = set(str(on).replace("|", ",").split(","))
        self.thinking = thinking in (True, "true", "1")
        self._thought = False

    def render(self, ctx, req):
        strong = ctx.models[self.strong] if self.strong else ctx.model
        cheap = ctx.models[self.cheap] if self.cheap else ctx.aux_model
        plan = ctx.step == 1 and "plan" in self.on
        error = ctx.last_tool_error and "error" in self.on
        req.model = strong if (plan or error) else cheap
        if plan and self.thinking and strong.thinking_fields:
            req.extra = {**req.extra, **strong.thinking_fields}
            req.temperature = None
            budget = strong.thinking_fields.get("thinking", {}).get("budget_tokens", 0)
            req.max_tokens = max(req.max_tokens, budget + 1024)
            self._thought = True
        ctx.log("route", model=req.model.key, reason="plan" if plan else "error" if error else "routine")
        return req

    def after_call(self, ctx, resp):
        if self._thought:
            msg = ctx.messages[-1]
            msg["content"] = [b for b in msg["content"] if "reasoningContent" not in b] or [{"text": "(thinking)"}]
            self._thought = False
