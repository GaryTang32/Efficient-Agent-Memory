"""Question answering over one very long document read page by page.
Stresses huge inputs (MemAgent, offload, folding, ReSum)."""

from __future__ import annotations

import random
import re

from eam.agent.context import Tool
from eam.bench.tasks.common import TaskInstance, contains_all, filler_paragraphs
from eam.llm.mock import assistant, context_text, final, tool_use
from eam.llm.types import ToolSpec

CODENAMES = ["BLUEFIN", "KESTREL", "MARIGOLD", "OBSIDIAN", "SAFFRON", "TUNDRA", "ZEPHYR", "CITADEL"]
MONTHS = ["March", "April", "May", "June", "July", "August", "September", "October"]
CODE_RE = re.compile(r"codename is ([A-Z]+-\d+)")
DATE_RE = re.compile(r"launch date was moved to (\w+ \d+)")


def generate(seed: int, n_pages: int = 30, page_tokens: int = 900) -> TaskInstance:
    rng = random.Random(seed)
    codename = f"{rng.choice(CODENAMES)}-{rng.randint(2, 99)}"
    date = f"{rng.choice(MONTHS)} {rng.randint(1, 28)}"
    p_code, p_date = rng.sample(range(1, n_pages + 1), 2)
    pages = {}
    for p in range(1, n_pages + 1):
        paras = filler_paragraphs(rng, page_tokens)
        if p == p_code:
            paras[rng.randrange(len(paras))] += f" For internal use, the project codename is {codename}."
        if p == p_date:
            paras[rng.randrange(len(paras))] += f" After the supplier review, the launch date was moved to {date}."
        pages[p] = f"Page {p}\n\n" + "\n\n".join(paras)
    document = "\n\n".join(pages[p] for p in sorted(pages))

    def read_page(args, ctx):
        p = int(args.get("page", 0))
        if p not in pages:
            raise ValueError(f"page must be between 1 and {n_pages}")
        return pages[p]

    tools = [Tool(ToolSpec(
        "read_page", f"Read one page (1-{n_pages}) of the project handbook 'handbook'.",
        {"type": "object", "properties": {"page": {"type": "integer"}}, "required": ["page"]}), read_page)]
    prompt = (f"The project handbook ('handbook', {n_pages} pages) mentions the project's codename and the date the "
              "launch was moved to. Find both and answer with the codename and the new launch date.")

    def oracle():
        read: list[int] = []
        used_memory = [False]

        def policy(req):
            text = context_text(req)
            code, when = CODE_RE.search(text), DATE_RE.search(text)
            if code and when:
                return final(f"FINAL ANSWER: codename {code.group(1)}, launch moved to {when.group(1)}")
            tools_ = {t.name for t in req.tools}
            if "read_with_memory" in tools_ and not used_memory[0]:
                used_memory[0] = True
                return assistant(tool_use("read_with_memory", {"source_id": "handbook", "question": prompt}))
            # Recover content hidden by truncation; trust compressed views (that is their point).
            for m in re.finditer(r"output truncated[^\n]*?artifact://(a\d+)", text):
                if "read_artifact" in tools_ and f"art:{m.group(1)}" not in read:
                    read.append(f"art:{m.group(1)}")
                    return assistant(tool_use("read_artifact", {"artifact_id": m.group(1), "length": 100000}))
            nxt = len([r for r in read if isinstance(r, int)]) + 1
            if nxt <= n_pages:
                read.append(nxt)
                blocks = [tool_use("read_page", {"page": nxt})]
                if "update_report" in tools_:
                    notes = [f"The project codename is {code.group(1)}." if code else "",
                             f"The launch date was moved to {when.group(1)}." if when else "",
                             f"Pages 1-{nxt - 1} read."]
                    blocks.append(tool_use("update_report", {"report": " ".join(n for n in notes if n)}))
                return assistant(*blocks)
            return final("FINAL ANSWER: " + (code.group(1) if code else "unknown") + ", "
                         + (when.group(1) if when else "unknown"))
        return policy

    return TaskInstance(
        family="long_document_qa", instance_id=f"longdoc-{seed}", prompt=prompt, tools=tools,
        check=contains_all(codename, date), gold=f"{codename}, {date}", oracle=oracle,
        resources={"documents": {"handbook": document}}, max_steps=n_pages + 10,
    )
