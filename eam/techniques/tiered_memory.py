"""Cross-session memory.

* ``TieredMemory`` — MemoryOS (BUPT): short-term = the live session; facts
  extracted at session end go to a mid tier; memories retrieved often get
  promoted to a long tier that is always loaded. Retrieval *scheduling*
  follows MemOS (MemTensor/SJTU): ``session_start`` retrieves once up front,
  ``every_step`` retrieves on each call, ``on_demand`` exposes a
  ``memory_search`` tool instead.
* ``FullCarryover`` — baseline that pastes all previous transcripts.

Memories are injected into the first *user* message, never the system prompt,
so the cached system/tools prefix is shared across sessions.
"""

from __future__ import annotations

from eam.agent.context import Tool
from eam.llm.types import ToolSpec
from eam.memory.tiered import TieredMemoryStore
from eam.techniques.base import Technique

EXTRACT_PROMPT = """Below is a conversation between a user and an assistant.

{transcript}

List the durable facts worth remembering for future conversations: user preferences, personal constraints,
decisions, and important project facts. One fact per line, written as a standalone sentence. Do not include
small talk or anything that only mattered for this conversation. If there is nothing, output NONE."""

MODES = ("session_start", "every_step", "on_demand")


def _bullets(records) -> str:
    return "\n".join(f"- {r.text}" for r in records)


class TieredMemory(Technique):
    name = "tiered_memory"
    source = "MemoryOS (BUPT) tiers/heat + MemOS (MemTensor, SJTU) retrieval scheduling"
    provenance = "provisional re-implementation; to be replaced by the official MemoryOS package"

    def __init__(self, path: str | None = None, retrieval: str = "session_start", top_k: int = 5,
                 promote_hits: int = 2, store: TieredMemoryStore | None = None):
        if retrieval not in MODES:
            raise ValueError(f"retrieval must be one of {MODES}")
        self.retrieval = retrieval
        self.top_k = int(top_k)
        self.store = store or TieredMemoryStore(path, promote_hits=int(promote_hits))
        self._shown: set[str] = set()

    def tools(self, ctx):
        if self.retrieval != "on_demand":
            return []

        def handler(args, ctx):
            hits = self.store.search(str(args.get("query", "")), self.top_k)
            return _bullets(hits) or "No matching memories."

        return [Tool(ToolSpec(
            "memory_search",
            "Search long-term memory from earlier sessions (user preferences, past decisions, facts).",
            {"type": "object", "properties": {"query": {"type": "string"}}, "required": ["query"]},
        ), handler)]

    def system_addendum(self):
        if self.retrieval == "on_demand":
            return "Memory: you may know things about the user from earlier sessions; use memory_search when relevant."
        return None

    def on_session_start(self, ctx):
        self.store.session += 1
        self._shown = set()
        long = self.store.long_term()
        mid = self.store.search(ctx.task, self.top_k) if self.retrieval != "on_demand" else []
        self._shown = {r.id for r in long + mid}
        if long or mid:
            ctx.preamble.append("## What you remember from earlier sessions\n" + _bullets(long + mid))
        ctx.log("memory_loaded", long=len(long), mid=len(mid))

    def before_call(self, ctx):
        if self.retrieval != "every_step" or ctx.step <= 1:
            return
        latest = ctx.messages[-1]
        query = ctx.transcript([latest], max_result_chars=2000)
        hits = self.store.search(query, self.top_k, exclude=self._shown)
        if hits:
            self._shown |= {r.id for r in hits}
            latest["content"].append({"text": "Relevant memories:\n" + _bullets(hits)})  # append-only

    def on_session_end(self, ctx, answer):
        out = ctx.call_aux(EXTRACT_PROMPT.format(transcript=ctx.transcript(max_result_chars=1500)),
                           purpose="memory_extract", max_tokens=600)
        added = 0
        for line in out.splitlines():
            line = line.strip().lstrip("-*• ").strip()
            if line and line.upper() != "NONE":
                self.store.add(line)
                added += 1
        self.store.maintain()
        self.store.save()
        ctx.log("memory_written", added=added, total=len(self.store.records))


class FullCarryover(Technique):
    name = "carryover"
    source = "baseline: paste every previous session transcript"
    provenance = "baseline"

    def __init__(self):
        self._transcripts: list[str] = []

    def on_session_start(self, ctx):
        if self._transcripts:
            joined = "\n\n".join(f"### Session {i}\n{t}" for i, t in enumerate(self._transcripts, 1))
            ctx.preamble.append("## Transcripts of earlier sessions\n" + joined)

    def on_session_end(self, ctx, answer):
        self._transcripts.append(ctx.transcript())
