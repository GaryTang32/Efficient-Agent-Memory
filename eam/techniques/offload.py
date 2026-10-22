"""Recoverable compression at ingestion — Manus "file system as context".

Large tool outputs are stored in the artifact store; the context keeps a short
preview plus an ``artifact://`` pointer the agent can read back. Applied before
the result enters the history, so it never breaks the cache.
"""

from __future__ import annotations

from eam.techniques.base import Technique
from eam.techniques.common import read_artifact_tool
from eam.tokens import estimate_tokens, truncate_to_tokens


class ToolResultOffload(Technique):
    name = "offload"
    source = "Manus recoverable compression (file system as context)"

    def __init__(self, max_tokens: int = 800, preview_tokens: int = 200):
        self.max_tokens = int(max_tokens)
        self.preview_tokens = int(preview_tokens)

    def tools(self, ctx):
        return [read_artifact_tool()]

    def on_tool_result(self, ctx, outcome):
        if outcome.name == "read_artifact" or estimate_tokens(outcome.text) <= self.max_tokens:
            return outcome
        aid = ctx.store.put(outcome.text, label=f"{outcome.name} {outcome.input}")
        preview = truncate_to_tokens(outcome.text, self.preview_tokens)
        outcome.text = (f"{preview}\n…[output truncated: {estimate_tokens(outcome.text)} tokens total. "
                        f"Full output stored at {ctx.store.pointer(aid)} — call read_artifact to see it.]")
        ctx.log("offloaded", artifact=aid)
        return outcome
