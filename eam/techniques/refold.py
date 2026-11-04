"""ReFold — training-free reversible inter-turn context folding (Su, Tian, Zhang [UCSB], Kundu [Intel];
arXiv 2610.07863). Deduplication and folding at the rendering layer: the history is never edited, the prompt is
rebuilt from it before every call.

* every reply starts with ``PROGRESS:`` / ``STALE:`` lines; steps the agent names STALE (only the last k=3 can be
  named) are folded, once they fall behind the chunked boundary b_t = k·⌊(t−k)/k⌋, into one ``[context-manager]``
  note that keeps their PROGRESS lines and mechanical details (signatures of files read, first search hits);
* repeated reads (line-level), searches and outputs ≥200 chars are replaced by stubs naming the step that still
  holds them; passing-test lines are filtered from test runs;
* everything is reversible: ``restore <step>`` shows the original turn again, answered from the history.

The official engine (https://github.com/YupengSu/ReFold, commit 017328f, Apache-2.0) is vendored in
``third_party/refold`` (dedup, fold, parse, filters, prompts.json — unchanged apart from import paths). This module
is the adapter that the official ``strategies/refold/agent.py`` is for mini-swe-agent; it re-implements
``engine.py``'s OBSERVE/RENDER/restore over Converse messages. Deviations (all forced by the structured-tool API):

* the paper's single bash tool → this harness's structured tools: each tool call is one step, its "command" is
  ``name args``; reads, searches and test runs are classified by tool name instead of by parsing shell commands;
* ``restore`` is a tool (``steps="7"`` / ``"3-5"``) rather than a bash command; the prompt text says so, the
  rest of the protocol and every note is verbatim;
* Converse cannot drop one tool result of a multi-call reply: a partly folded reply keeps its call, and the folded
  result becomes a one-line pointer. A fully folded reply is dropped with its results (as in the official code).
"""

from __future__ import annotations

import copy
import hashlib
import json
import re
from dataclasses import dataclass

from eam.agent.context import Tool
from eam.llm.types import ToolSpec
from eam.techniques.base import Technique
from eam.techniques.steps import step_indices
from eam.techniques.third_party.refold import dedup, fold, parse
from eam.techniques.third_party.refold.dedup import ReadMark, Rendered, Turn

_PROMPTS: dict[str, str] = json.loads(
    (__import__("pathlib").Path(dedup.__file__).parent / "prompts.json").read_text())
_RESTORE_MAX = 10
_RESTORE_CLAUSE = re.compile(r" `restore \{\w+\}` shows (?:it|them|all of it|\{them\}) again\.")

# tool name -> kind (this harness's tasks); anything else falls back to the exact-output rule
READ_TOOLS = {"read_file"}
SEARCH_TOOLS = {"search", "grep", "list_files"}
TEST_TOOLS = {"run_tests"}
_READ_LINE = re.compile(r"^\s*(\d+)  ")


def _tool_protocol(text: str) -> str:
    """The official prompt layer, with the bash-command wording changed to this harness's `restore` tool."""
    return (text.replace("your bash tool call", "your tool call")
            .replace("run `restore <step>` as your bash command (for example `restore 7` or `restore 3-5`)",
                     "call the `restore` tool (for example steps=\"7\" or steps=\"3-5\")")
            .replace("never let them replace your bash tool call", "never let them replace your tool call")
            .replace("The bash command `restore <step>`", "The `restore` tool (steps=\"<step>\")"))


def prompt_layer(k: int, reversible: bool = True) -> tuple[str, str]:
    window = _PROMPTS["protocol_window"].replace("{k}", str(k)).replace("{plural}", "" if k == 1 else "s")
    protocol = (_PROMPTS["protocol"].replace("{restore}", _PROMPTS["protocol_restore"] if reversible else "")
                .replace("{window}", window))
    disclosure = _PROMPTS["disclosure" if reversible else "disclosure_irreversible"]
    return _tool_protocol(disclosure).strip(), _tool_protocol(protocol).strip()


@dataclass
class _Loc:
    reply: int  # index of the assistant message that issued the step
    msg: int  # index of the user message holding its result
    block: int  # index of the toolResult block in that message


class ReFold(Technique):
    name = "refold"
    source = "ReFold (UCSB + Intel), arXiv 2610.07863"
    provenance = "official engine vendored (Apache-2.0); adapter for structured tools"
    cache_safe = False  # the rendered prefix changes at boundary advances (every k steps)

    def __init__(self, k: int = 3, dedup: bool = True, fold: bool = True, chunked: bool = True,
                 reversible: bool = True):
        self.k = int(k)
        self.dedup = bool(dedup)
        self.fold = bool(fold)
        self.chunked = bool(chunked)
        self.reversible = bool(reversible)
        self.notes = _PROMPTS if self.reversible else {
            n: _RESTORE_CLAUSE.sub("", t) if n.startswith("note_") else t for n, t in _PROMPTS.items()}
        self._reset()

    def _reset(self):
        self.turns: list[Turn] = []
        self.locs: list[_Loc] = []
        self.progress: list[str] = []
        self.has_progress: list[bool] = []
        self.stale: set[int] = set()
        self.folds: list[fold.Fold] = []
        self.removed: dict[int, str] = {}
        self._observed_msgs: set[int] = set()
        self.labels = {"replies": 0, "progress_missing": 0, "stale_out_of_window": 0}
        self.restores = dict.fromkeys(("calls", "folded", "compressed", "shown", "invalid"), 0)

    # ---- prompt layer --------------------------------------------------------------------------------------
    def system_addendum(self):
        return prompt_layer(self.k, self.reversible)[0]

    def on_session_start(self, ctx):
        self._reset()
        ctx.preamble.append(prompt_layer(self.k, self.reversible)[1])

    def tools(self, ctx):
        if not self.reversible:
            return []

        def handler(args, ctx):
            raw = str(args.get("steps", "")).strip()
            steps = parse.parse_restore_command(raw if raw.startswith("restore") else f"restore {raw}")
            if not steps:
                raise ValueError("give step numbers, e.g. steps=\"7\" or steps=\"3-5\"")
            return self.restore(ctx, steps)

        return [Tool(ToolSpec(
            "restore",
            "Show the original agent message, call and tool output of earlier steps exactly as first shown "
            "(steps folded or omitted by the context manager), without running anything.",
            {"type": "object", "properties": {"steps": {"type": "string", "description": "e.g. \"7\", \"3-5\" or "
                                                        "\"3, 9\""}}, "required": ["steps"]}), handler)]

    # ---- OBSERVE -------------------------------------------------------------------------------------------
    @staticmethod
    def _reply_text(msg) -> str:
        return "\n".join(b["text"] for b in msg["content"] if "text" in b)

    def _command(self, tu) -> str:
        name, args = tu["name"], tu.get("input") or {}
        if name == "run_tests":
            return f"pytest {args.get('selector', '') or ''}".strip()
        if name == "grep":
            return f"grep {args.get('pattern', '')} {args.get('path', '') or ''}".strip()
        if name == "list_files":
            return f"ls {args.get('path', '') or ''}".strip()
        return f"{name} {json.dumps(args, sort_keys=True)}"

    def _turn(self, index: int, tu, obs: str) -> Turn:
        name, args = tu["name"], tu.get("input") or {}
        cmd = self._command(tu)
        if name in READ_TOOLS:
            body = obs.split("\n")[1:]  # first line is the "path (lines a-b of n)" header
            lines = [ln + "\n" for ln in body if _READ_LINE.match(ln)]
            m = _READ_LINE.match(lines[0]) if lines else None
            if m:
                start = int(m.group(1))
                read = ReadMark(path="/" + str(args.get("path", "")).lstrip("/"), line_start=start,
                                line_end=start + len(lines) - 1, content=tuple(lines))
                return Turn(index=index, command=cmd, observation=obs, read=read)
        if name in TEST_TOOLS:
            return Turn(index=index, command=cmd, observation=obs, pytest=True)
        if name in SEARCH_TOOLS:
            return Turn(index=index, command=cmd, observation=obs,
                        search=(cmd, hashlib.sha1(obs.encode("utf-8")).hexdigest()))
        return Turn(index=index, command=cmd, observation=obs)

    def _observe(self, ctx):
        for a, u in step_indices(ctx.messages):
            if u is None or u in self._observed_msgs:
                continue
            results = [(j, b) for j, b in enumerate(ctx.messages[u]["content"]) if "toolResult" in b]
            if not results:
                continue
            self._observed_msgs.add(u)
            uses = {b["toolUse"]["toolUseId"]: b["toolUse"] for b in ctx.messages[a]["content"] if "toolUse" in b}
            for j, b in results:
                tr = b["toolResult"]
                tu = uses.get(tr["toolUseId"], {"name": "?", "input": {}})
                obs = "\n".join(c.get("text", "") for c in tr["content"])
                self.turns.append(self._turn(len(self.turns), tu, obs))
                self.locs.append(_Loc(a, u, j))
            t = len(self.turns)
            content = self._reply_text(ctx.messages[a])
            progress = parse.parse_progress(content)
            self.labels["replies"] += 1
            self.labels["progress_missing"] += progress is None
            while len(self.progress) < t:
                self.progress.append(progress or "")
                self.has_progress.append(progress is not None)
            lo, hi = t - 1 - self.k, t - 2
            named = parse.parse_stale(content)
            self.labels["stale_out_of_window"] += sum(not lo <= s <= hi for s in named)
            self.stale.update(s for s in named if lo <= s <= hi)
            self.folds = fold.folds(self.turns, self.stale, self.progress, self.boundary(), self.notes)

    def boundary(self) -> int:
        k, t = self.k, len(self.turns)
        return max(0, k * ((t - k) // k)) if self.chunked else max(0, t - k)

    def folded_steps(self) -> set[int]:
        if not self.fold:
            return set()
        return {i for f in self.folds for i in range(f.start, f.end + 1)}

    # ---- RENDER --------------------------------------------------------------------------------------------
    def render(self, ctx, req):
        if req.messages is not ctx.messages:
            return req  # another technique already rendered a copy; ReFold works on the history
        self._observe(ctx)
        if not self.turns:
            return req
        folded = self.folded_steps()
        if self.dedup:
            rendered = dedup.render(self.turns, folded, self.boundary(), self.notes, reversible=self.reversible)
        else:
            rendered = [Rendered(t.index) for t in self.turns]
        body = {r.index: r.body for r in rendered}
        self.removed = {**{r.index: "compressed" for r in rendered if r.body is not None},
                        **dict.fromkeys(folded, "folded")}
        steps_of_reply: dict[int, set[int]] = {}
        for s, loc in enumerate(self.locs):
            steps_of_reply.setdefault(loc.reply, set()).add(s)
        drop_msgs: set[int] = set()
        for reply, steps in steps_of_reply.items():
            if steps <= folded:  # the whole reply is folded: it leaves with its results
                drop_msgs |= {reply, self.locs[min(steps)].msg}
        notes = self._fold_notes(folded)
        remind_step, remind = self._reminder()

        edits: dict[tuple[int, int], str] = {}
        for s, loc in enumerate(self.locs):
            if loc.msg in drop_msgs:
                continue
            if s in folded:
                text = f"[step {s}]\n[context-manager] step {s} folded." + (
                    f" `restore {s}` shows it again." if self.reversible else "")
            else:
                text = body.get(s)
                text = f"[step {s}]\n{text if text is not None else self.turns[s].observation}"
            if s in notes:
                text = f"{notes[s]}\n{text}"
            if s == remind_step:
                text = f"{text}\n\n{remind}"
            edits[(loc.msg, loc.block)] = text

        out = []
        for i, msg in enumerate(ctx.messages):
            if i in drop_msgs:
                continue
            blocks = [(j, b) for j, b in enumerate(msg["content"]) if (i, j) in edits]
            if not blocks:
                out.append(msg)  # unchanged messages are shared, not copied
                continue
            new = {**msg, "content": list(msg["content"])}
            for j, b in blocks:
                tr = b["toolResult"]
                new["content"][j] = {"toolResult": {**tr, "content": [{"text": edits[(i, j)]}]}}
            out.append(new)
        if drop_msgs:
            ctx.log("refold_render", folded=sorted(folded), dropped_messages=len(drop_msgs),
                    compressed=sorted(s for s, how in self.removed.items() if how == "compressed"))
        req.messages = out
        return req

    def _fold_notes(self, folded: set[int]) -> dict[int, str]:
        notes: dict[int, str] = {}
        if not self.fold:
            return notes
        for f in self.folds:
            after = f.end + 1
            while after < len(self.locs) and after in folded:
                after += 1
            if after >= len(self.locs):
                continue
            notes[after] = f"{notes[after]}\n{f.note}" if after in notes else f.note
        return notes

    def _reminder(self) -> tuple[int, str]:
        if not self.has_progress or self.has_progress[-1]:
            return -1, ""
        misses = len(self.has_progress) - 1 - max((i for i, ok in enumerate(self.has_progress) if ok), default=-1)
        text = self.notes["remind_gentle"] if misses <= 1 else self.notes["remind_harsh"].format(misses=misses)
        return len(self.locs) - 1, text

    # ---- restore -------------------------------------------------------------------------------------------
    def restore(self, ctx, steps: list[int]) -> str:
        self.restores["calls"] += 1
        blocks = []
        for s in steps[:_RESTORE_MAX]:
            how = self.removed.get(s) if 0 <= s < len(self.turns) else "invalid"
            self.restores[how or "shown"] += 1
            if how == "invalid":
                blocks.append(_PROMPTS["restore_invalid"].format(step=s, last=len(self.turns) - 1))
            elif how is None:
                blocks.append(_PROMPTS["restore_shown"].format(step=s))
            else:
                reply = self._reply_text(ctx.messages[self.locs[s].reply]).strip()
                reply = "\n".join(ln for ln in reply.splitlines() if not ln.startswith("[Context used:"))
                blocks.append("\n".join([_PROMPTS["restore_head"].format(step=s), *([reply] if reply else []),
                                         f"$ {self.turns[s].command}", self.turns[s].observation]))
        if len(steps) > _RESTORE_MAX:
            blocks.append(_PROMPTS["restore_cap"].format(max=_RESTORE_MAX))
        ctx.log("refold_restore", steps=steps[:_RESTORE_MAX])
        return "\n\n".join(blocks)

    def after_call(self, ctx, resp):
        if resp.tool_uses:
            return
        for b in resp.message["content"]:  # the final answer: drop the metadata lines
            if "text" in b:
                b["text"] = "\n".join(ln for ln in b["text"].splitlines()
                                      if not re.match(r"\s*`?(PROGRESS|STALE)`?\s*[-:–]", ln, re.I)).strip()

    def on_session_end(self, ctx, answer):
        ctx.log("refold_record", steps=len(self.turns), stale=sorted(self.stale), **self.labels,
                folds=[[f.start, f.end] for f in self.folds], restores=dict(self.restores))

    def describe(self) -> str:
        return (f"refold(k={self.k}, dedup={self.dedup}, fold={self.fold}, chunked={self.chunked}, "
                f"reversible={self.reversible})")
