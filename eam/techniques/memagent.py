"""MemAgent reader — fixed-size overwrite memory over a long input.

ByteDance Seed + Tsinghua, "MemAgent": read a long document chunk by chunk and
keep overwriting a bounded memory with what matters for the question. The main
context only ever sees the final memory, so cost is linear in document length
and the main context stays small. (Paper trains this with RL; here it is
prompted on the auxiliary model.)
"""

from __future__ import annotations

from eam.agent.context import Tool
from eam.llm.types import ToolSpec
from eam.techniques.base import Technique
from eam.tokens import CHARS_PER_TOKEN

MEMAGENT_PROMPT = """You are reading a long document in chunks while keeping a bounded memory.

Question: {question}

Current memory:
{memory}

Chunk {index} of {total}:
{chunk}

Rewrite the memory so it contains everything from the old memory and this chunk that could help answer the
question (exact names, numbers, dates). Drop irrelevant details. Output only the new memory."""


def chunk_text(text: str, chunk_tokens: int) -> list[str]:
    limit = int(chunk_tokens * CHARS_PER_TOKEN)
    chunks, current = [], ""
    for para in text.split("\n\n"):
        if current and len(current) + len(para) > limit:
            chunks.append(current)
            current = ""
        current = f"{current}\n\n{para}" if current else para
    if current:
        chunks.append(current)
    return chunks


class MemAgentReader(Technique):
    name = "memagent"
    source = "MemAgent (ByteDance Seed + Tsinghua)"

    def __init__(self, chunk_tokens: int = 3000, memory_tokens: int = 800):
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
            chunks = chunk_text(text, self.chunk_tokens)
            memory = "(empty)"
            for i, chunk in enumerate(chunks, 1):
                memory = ctx.call_aux(
                    MEMAGENT_PROMPT.format(question=args.get("question", ""), memory=memory, index=i,
                                           total=len(chunks), chunk=chunk),
                    purpose="memagent", max_tokens=self.memory_tokens)
            ctx.log("memagent_read", chunks=len(chunks))
            return f"Memory after reading all {len(chunks)} chunks of '{source}':\n{memory}"

        return [Tool(ToolSpec(
            "read_with_memory",
            f"Read an entire long document ({', '.join(sorted(docs))}) chunk by chunk with a bounded memory and "
            "return only the information relevant to your question. Much cheaper than reading it page by page.",
            {"type": "object", "properties": {"source_id": {"type": "string"}, "question": {"type": "string"}},
             "required": ["source_id", "question"]},
        ), handler)]
