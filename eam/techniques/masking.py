"""Observation masking — keep only the last N tool results verbatim.

From "Less Context, Better Agents" (keep last 5 tool calls: ~64% fewer tokens,
higher accuracy) and Claude context editing (``clear_tool_uses``). Older
results are replaced by a placeholder with an artifact pointer, so the
information stays recoverable. Clearing happens in batches (hysteresis) to
limit how often the prompt cache is broken.
"""

from __future__ import annotations

from eam.techniques.base import Technique
from eam.techniques.common import read_artifact_tool

CLEARED_PREFIX = "[cleared to save context"


class KeepLastN(Technique):
    name = "keep_last_n"
    source = "Less Context, Better Agents (2026); Claude context editing"
    provenance = "provisional (ours)"
    cache_safe = False

    def __init__(self, keep: int = 5, batch: int = 5, exclude: tuple[str, ...] = ("todo_write",)):
        self.keep = int(keep)
        self.batch = int(batch)  # clear only once `keep + batch` live results accumulate
        self.exclude = tuple(exclude)

    def tools(self, ctx):
        return [read_artifact_tool()]

    def before_call(self, ctx):
        live = []
        names = {}
        for msg in ctx.messages:
            for b in msg["content"]:
                if "toolUse" in b:
                    names[b["toolUse"]["toolUseId"]] = b["toolUse"]
                elif "toolResult" in b:
                    tu = names.get(b["toolResult"]["toolUseId"], {})
                    text = b["toolResult"]["content"][0].get("text", "")
                    if tu.get("name") not in self.exclude and not text.startswith(CLEARED_PREFIX):
                        live.append((b, tu))
        if len(live) <= self.keep + self.batch:
            return
        for block, tu in live[: len(live) - self.keep]:
            text = block["toolResult"]["content"][0].get("text", "")
            aid = ctx.store.put(text, label=f"{tu.get('name')} {tu.get('input')}")
            block["toolResult"]["content"] = [{"text": (
                f"{CLEARED_PREFIX}: output of {tu.get('name')}({tu.get('input')}) moved to "
                f"{ctx.store.pointer(aid)}; call read_artifact if you need it again]")}]
        ctx.log("cleared_results", count=len(live) - self.keep)
