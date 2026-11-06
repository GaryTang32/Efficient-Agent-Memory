"""Scripted mock policy for "list entities, read each, aggregate" tasks.

It behaves like a competent agent that (a) uses whatever technique tools are
offered (branch, update_report, todo_write, read_artifact), and (b) answers
*only* from facts visible in the context it is given. Lost facts therefore
lead to wrong answers, which is the offline retention signal.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any, Callable

from eam.llm.mock import assistant, context_text, final, tool_exchanges, tool_use
from eam.llm.types import Request


@dataclass
class EntitySpec:
    list_call: tuple[str, dict[str, Any]]
    parse_list: Callable[[str], dict[str, str]]  # context text -> {entity_id: fact key}
    read_tool: str
    read_arg: str
    parse_facts: Callable[[str], dict[str, dict[str, str]]]  # context text -> {fact key: {field: value}}
    fields: tuple[str, ...]
    fact_lines: Callable[[str], list[str]]
    answer: Callable[[dict[str, dict[str, str]], dict[str, str]], str]
    subtask: Callable[[str, str], str]
    subtask_re: re.Pattern[str]


@dataclass
class _State:
    listed: bool = False
    todo: bool = False
    entities: dict[str, str] = field(default_factory=dict)
    read: list[str] = field(default_factory=list)
    recovered: set[str] = field(default_factory=set)
    no_branch: bool = False


def _header(req: Request) -> str:
    first = req.messages[0]["content"][0].get("text", "")
    line = first.split("\n", 1)[0]
    for prefix in ("Task: ", "Question: "):
        if line.startswith(prefix):
            return line[len(prefix):]
    return line


class EntityOracle:
    def __init__(self, spec: EntitySpec):
        self.spec = spec
        self.states: dict[tuple[str, str], _State] = {}

    def __call__(self, req: Request):
        spec = self.spec
        header = _header(req)
        st = self.states.setdefault((req.tag, header), _State())
        text = context_text(req)
        tools = {t.name for t in req.tools}
        facts = spec.parse_facts(text)

        def complete(key: str) -> bool:
            return all(f in facts.get(key, {}) for f in spec.fields)

        # FoldAgent branch: it inherits MAIN's history; its assignment is the prompt of the last `branch` call.
        sub = None
        if req.tag == "subagent":
            prompts = [b["toolUse"]["input"].get("prompt", "") for m in req.messages for b in m["content"]
                       if "toolUse" in b and b["toolUse"]["name"] == "branch"]
            if prompts:
                st = self.states.setdefault(("subagent", prompts[-1]), _State())
                sub = spec.subtask_re.search(prompts[-1])
        if sub:
            eid, key = sub.group(1), sub.group(2)
            st.entities[eid] = key
            if not st.read:
                st.read.append(eid)
                return assistant(tool_use(spec.read_tool, {spec.read_arg: eid}))
            recover = self._recover(req, st, lambda k: k == key and not complete(key))
            if recover:
                return recover
            lines = [l for l in spec.fact_lines(text) if key in l]
            if "return" in tools:
                return assistant(tool_use("return", {"message": " ".join(lines)}))
            return final("FINAL ANSWER: " + " ".join(lines))

        if not st.listed:
            st.listed = True
            blocks = [tool_use(*spec.list_call)]
            if "todo_write" in tools:
                blocks.insert(0, tool_use("todo_write", {"items": [
                    {"text": "List all entities"}, {"text": "Read every entity and extract the facts"},
                    {"text": "Aggregate and answer"}]}))
            return assistant(*blocks)

        st.entities.update(spec.parse_list(text))
        recover = self._recover(req, st, lambda k: not complete(k))
        if recover:
            return recover

        # FoldAgent caps branches (MAX_SESSION); after the cap, read the rest directly.
        exchanges = list(tool_exchanges(req.messages))
        if exchanges and exchanges[-1][0] == "branch" and "already reached the limit" in exchanges[-1][2]:
            st.no_branch = True
            missing = str(exchanges[-1][1].get("description", "")).removeprefix("Read ")
            if missing in st.read:
                st.read.remove(missing)
        unread = [e for e in st.entities if e not in st.read]
        if unread:
            eid = unread[0]
            st.read.append(eid)
            if "branch" in tools and not st.no_branch:
                blocks = [tool_use("branch", {"description": f"Read {eid}",
                                              "prompt": spec.subtask(eid, st.entities[eid])})]
            else:
                blocks = [tool_use(spec.read_tool, {spec.read_arg: eid})]
            if "update_report" in tools:
                blocks.append(tool_use("update_report", {"report": "\n".join(spec.fact_lines(text))}))
            return assistant(*blocks)

        return final("FINAL ANSWER: " + spec.answer(facts, st.entities))

    def _recover(self, req: Request, st: _State, needs: Callable[[str], bool]):
        """Read back an artifact when a truncated/cleared result hides facts we need."""
        if "read_artifact" not in {t.name for t in req.tools}:
            return None
        for name, inp, result in tool_exchanges(req.messages):
            m = re.search(r"artifact://(a\d+)", result)
            if not m or m.group(1) in st.recovered:
                continue
            if name == self.spec.read_tool:
                key = st.entities.get(str(inp.get(self.spec.read_arg)), str(inp.get(self.spec.read_arg)))
                if not needs(key):
                    continue
            elif name != self.spec.list_call[0] or st.entities:
                continue
            st.recovered.add(m.group(1))
            return assistant(tool_use("read_artifact", {"artifact_id": m.group(1), "length": 100000}))
        return None
