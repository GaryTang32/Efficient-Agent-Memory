"""MemAgent — Yu et al., ICLR 2026 Oral (ByteDance Seed + Tsinghua AIR). The official quickstart workflow
(third_party/memagent.py): read a long input in 5000-token chunks, overwrite a memory (≤1024 new tokens) with
TEMPLATE after each chunk, then answer from the memory with TEMPLATE_FINAL. Exposed as a `read_with_memory`
tool over task documents. The paper's RL-trained weights need a GPU; here any API model runs the workflow
(the paper reports the untrained workflow still works, with more degradation at extreme lengths).
"""

from __future__ import annotations

from eam.agent.context import Tool
from eam.llm.types import ToolSpec
from eam.techniques.base import Technique
from eam.techniques.third_party import memagent as P
from eam.tokens import CHARS_PER_TOKEN


def chunk_text(text: str, chunk_tokens: int) -> list[str]:
    limit = int(chunk_tokens * CHARS_PER_TOKEN)
    return [text[i:i + limit] for i in range(0, len(text), limit)] or [""]


class MemAgentReader(Technique):
    name = "memagent"
    source = "MemAgent, ICLR 2026 (ByteDance Seed + Tsinghua)"
    provenance = "official templates + workflow (Apache-2.0)"

    def __init__(self, chunk_tokens: int = P.CHUNK_TOKENS, memory_tokens: int = P.MAX_NEW_TOKENS):
        self.chunk_tokens = int(chunk_tokens)
        self.memory_tokens = int(memory_tokens)

    def tools(self, ctx):
        docs = ctx.resources.get("documents")
        if not docs:
            return []

        def handler(args, ctx):
            source = str(args.get("source_id", ""))
            text = ctx.resources["documents"].get(source)
            if text is None:
                raise ValueError(f"unknown source '{source}'; available: {sorted(ctx.resources['documents'])}")
            problem = str(args.get("question", ""))
            memory = P.NO_MEMORY
            chunks = chunk_text(text, self.chunk_tokens)
            for chunk in chunks:
                memory = ctx.call_aux(P.TEMPLATE.format(prompt=problem, chunk=chunk, memory=memory),
                                      purpose="memagent", system="", max_tokens=self.memory_tokens)
            answer = ctx.call_aux(P.TEMPLATE_FINAL.format(prompt=problem, memory=memory), purpose="memagent",
                                  system="", max_tokens=self.memory_tokens)
            ctx.log("memagent_read", chunks=len(chunks))
            return f"Memory after reading {source} ({len(chunks)} chunks):\n{memory}\n\nAnswer from memory: {answer}"

        return [Tool(ToolSpec(
            "read_with_memory",
            f"Read a whole long document ({', '.join(sorted(docs))}) chunk by chunk with a bounded memory and answer "
            "a question from it. Much cheaper than reading it page by page.",
            {"type": "object", "properties": {"source_id": {"type": "string"}, "question": {"type": "string"}},
             "required": ["source_id", "question"]}), handler)]
