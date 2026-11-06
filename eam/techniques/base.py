"""Technique interface.

Every context/memory technique is a set of optional hooks on the agent loop.
Testing a technique alone = running with ``[technique]``; combining techniques
= passing several (or a ``Pipeline``). Hooks run in list order.

Hook order per step::

    before_call -> render -> (LLM) -> after_call -> [tool runs] -> on_tool_result

Design rule worth keeping in mind: anything done in ``on_tool_result``
(ingestion time) is cache-safe because it shapes content *before* it enters
the history. Anything that edits earlier messages in ``before_call`` breaks
the prompt cache from that point on; set ``cache_safe = False``.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from eam.agent.context import AgentContext, Tool, ToolOutcome
    from eam.llm.types import Request, Response


class Technique:
    name = "base"
    source = ""  # paper / lab the idea comes from
    provenance = "provisional (our implementation, not yet checked against an official source)"
    cache_safe = True

    def tools(self, ctx: "AgentContext") -> list["Tool"]:
        return []

    def system_addendum(self) -> str | None:
        """Static instructions appended to the system prompt (must not vary per call)."""
        return None

    def on_session_start(self, ctx: "AgentContext") -> None:
        pass

    def before_call(self, ctx: "AgentContext") -> None:
        pass

    def render(self, ctx: "AgentContext", req: "Request") -> "Request":
        return req

    def after_call(self, ctx: "AgentContext", resp: "Response") -> None:
        pass

    def on_tool_result(self, ctx: "AgentContext", outcome: "ToolOutcome") -> "ToolOutcome":
        return outcome

    def on_session_end(self, ctx: "AgentContext", answer: str) -> None:
        pass

    def describe(self) -> str:
        params = {k: v for k, v in vars(self).items() if not k.startswith("_")}
        return f"{self.name}({', '.join(f'{k}={v}' for k, v in params.items())})"


class Pipeline(Technique):
    """Run several techniques as one; the unit for building combined memory skills."""

    name = "pipeline"

    def __init__(self, *techniques: Technique, name: str | None = None):
        self.techniques = list(techniques)
        if name:
            self.name = name
        self.cache_safe = all(t.cache_safe for t in self.techniques)

    def tools(self, ctx):
        seen, out = set(), []
        for t in self.techniques:
            for tool in t.tools(ctx):
                if tool.spec.name not in seen:
                    seen.add(tool.spec.name)
                    out.append(tool)
        return out

    def system_addendum(self):
        parts = [a for a in (t.system_addendum() for t in self.techniques) if a]
        return "\n\n".join(parts) or None

    def on_session_start(self, ctx):
        for t in self.techniques:
            t.on_session_start(ctx)

    def before_call(self, ctx):
        for t in self.techniques:
            t.before_call(ctx)

    def render(self, ctx, req):
        for t in self.techniques:
            req = t.render(ctx, req)
        return req

    def after_call(self, ctx, resp):
        for t in self.techniques:
            t.after_call(ctx, resp)

    def on_tool_result(self, ctx, outcome):
        for t in self.techniques:
            outcome = t.on_tool_result(ctx, outcome)
        return outcome

    def on_session_end(self, ctx, answer):
        for t in self.techniques:
            t.on_session_end(ctx, answer)

    def describe(self) -> str:
        return f"{self.name}[{', '.join(t.describe() for t in self.techniques)}]"
