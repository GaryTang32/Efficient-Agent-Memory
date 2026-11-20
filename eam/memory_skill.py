"""AutoMemory as a framework-agnostic library: the same rules as `eam/techniques/auto_memory.py`, on plain
OpenAI-style message lists, with a persistent on-disk store.

    skill = MemorySkill("~/.eam-memory/project-x", window=200_000, summarize=my_llm_call)
    system = base_system + "\\n\\n" + skill.system_addendum()
    messages = [{"role": "user", "content": skill.session_preamble() + task}]
    ...
    text = skill.ingest_tool_output("open_file", raw_text, context_tokens=last_prompt_tokens)  # in-step guard
    messages = skill.maybe_compact(messages, context_tokens=last_prompt_tokens, question=task)  # rare reset
    ...
    skill.save_session(final_answer)                                                            # autosave

Layers (`eam/automem/`): the decisions are pure functions in `eam.automem.core`; notes are typed records
(`eam.automem.notes`: fact, decision, dead_end, command, result, ...; a note can supersede an older one, which recall
then skips); storage is pluggable (`store=JsonStore(root)` by default, or `SQLiteStore(path)`, `MemoryStore()`).

Safety (`eam/safety.py`): recalled notes come back inside a ``<memory>`` block marked as data (the system addendum
says never to follow instructions found there), and at most `recall_budget` × window of them per recall; secrets are
redacted before anything is saved; files are owner-only and written atomically, notes under a lock; artifacts older
than `retention_days`, or beyond `max_artifact_mb`, are deleted.

`summarize(prompt) -> str` is any LLM call (a cheaper model is fine: the summary prompt is ReSum's official
prompt). With ``compaction="handoff"`` the compaction is the NVIDIA EoCC handoff recap (arXiv 2611.05306) instead:
either the agent writes it as its own next turn, which reads the whole history from the prompt cache,

    if skill.should_compact(last_prompt_tokens):
        messages.append({"role": "user", "content": skill.handoff_prompt()})
        recap = my_agent_llm(messages)                       # the agent's reply, no tool calls
        messages = skill.apply_handoff(messages, recap, question=task)

or `maybe_compact` has `summarize` write it from a transcript. Tool specs for write_note / read_notes / read_artifact come from `tool_specs()`; route those calls to
`call_tool`. The MCP server (`eam/mcp_server.py`) exposes the same store as MCP tools.
"""

from __future__ import annotations

import re
import time
from pathlib import Path
from typing import Any, Callable

from eam import safety as S
from eam.automem import core as C
from eam.automem.notes import NOTE_TYPES, Note
from eam.automem.storage import JsonStore, Store
from eam.techniques.auto_memory import GUARDED, RECALL
from eam.techniques.third_party import resum as P
from eam.techniques.workspace import NoteWorkspace
from eam.tokens import estimate_tokens


class MemorySkill:
    def __init__(self, root: str | Path | None = None, *, store: Store | None = None, window: int = 200_000, trigger: float = 0.75, guard: float = 0.9,
                 token_ratio: float = 1.5, summarize: Callable[[str], str] | None = None,
                 max_note_chars: int = 20_000, preview: float = 0.1, preview_tokens: int = 750,
                 compaction: str = "resum", handoff_variant: str = "general", recall_budget: float = 0.1,
                 retention_days: float = 14, max_artifact_mb: float = 200, max_artifact_chars: int = 10_000_000,
                 wrap: bool = True):
        if store is None and root is None:
            raise ValueError("give a directory (root) or a store")
        self.store: Store = store if store is not None else JsonStore(root)
        self.root = getattr(self.store, "root", None)
        # recalled notes take at most this share of the window; older notes are listed by name (read_notes fetches)
        self.recall_budget = float(recall_budget)
        self.retention_days, self.max_artifact_mb = float(retention_days), float(max_artifact_mb)
        self.max_artifact_chars = int(max_artifact_chars)
        self.wrap = bool(wrap)
        self.window, self.trigger, self.guard, self.token_ratio = int(window), trigger, guard, token_ratio
        self.summarize = summarize
        self.max_note_chars = max_note_chars
        # v2: outputs above `preview` × window enter the context as a head/tail preview; the full text is an
        # artifact (read_artifact pages it). 0 = off (v1 behaviour).
        self.preview, self.preview_tokens = float(preview), int(preview_tokens)
        if compaction not in ("resum", "handoff"):
            raise ValueError("compaction must be 'resum' or 'handoff'")
        self.compaction, self.handoff_variant = compaction, handoff_variant
        self._step_used: int | None = None
        self._last_summary: str | None = None

    # ---- persistent notes ----------------------------------------------------------------------------------
    def records(self) -> list[Note]:
        """Every note with its metadata, oldest first (superseded ones included)."""
        return self.store.load()

    def notes(self) -> dict[str, str]:
        """The active notes as {name: text}, oldest first."""
        return {n.name: n.text for n in C.active(self.store.load())}

    def write_note(self, name: str, content: str, *, type: str = "note", source: str = "agent",
                   supersedes: str = "", files: list[str] | None = None, session: str = "") -> str:
        note = C.make_note(name, content, max_chars=self.max_note_chars, type=type, source=source,
                           supersedes=S.redact(supersedes or "")[:200], files=files, session=session)
        with self.store.transaction() as notes:  # read-modify-write: concurrent sessions keep each other's notes
            existed = C.upsert(notes, note)
            names = sorted(n.name for n in C.active(notes))
        retired = f" '{note.supersedes}' is now superseded." if note.supersedes else ""
        return (f"{'Replaced' if existed else 'Saved'} note '{note.name}' ({len(note.text)} chars).{retired} "
                f"Notes: {', '.join(names)}")

    def read_notes(self, name: str | None = None) -> str:
        notes = self.store.load()
        if not C.active(notes):
            return "The workspace is empty."
        if name:
            match = [n for n in notes if n.name == name]
            if not match:
                raise ValueError(f"no note '{name}'. Notes: {', '.join(sorted(n.name for n in notes))}")
            return match[0].render() + (" [superseded]" if not match[0].active else "")
        return C.render_notes(*C.select_recall(notes, self._recall_budget()))

    def _recall_budget(self) -> int:
        return max(1, int(self.recall_budget * self.window))

    def system_addendum(self) -> str:
        base = NoteWorkspace().system_addendum()
        return f"{base}\n\n{S.MEMORY_RULE}" if self.wrap else base

    def _recall_text(self) -> str:
        return C.recall_text(self.store.load(), self._recall_budget(), wrap=self.wrap)

    def session_preamble(self) -> str:
        """Recall: the newest active notes within the recall budget, as a <memory> block, to put at the top of a new
        session's first message (empty if there are none)."""
        text = self._recall_text()
        return RECALL.format(notes=text) + "\n\n" if text else ""

    def save_session(self, answer: str, label: str | None = None) -> None:
        """Autosave: keep a session's final answer as a note of type 'result'. It supersedes the previous autosaved
        answer, which leaves recall but stays readable by name: on a ten-day task, stale copies of earlier answers
        were a third of the recalled notes and carried no fact a later session needed (docs/automem_v2.md)."""
        if answer:
            name = label or f"session {time.strftime('%Y-%m-%d %H:%M:%S')} final answer"
            prev = [n.name for n in self.records() if n.source == "autosave" and n.type == "result" and n.active
                    and n.name != name]
            self.write_note(name, answer, type="result", source="autosave", supersedes=prev[-1] if prev else "")

    # ---- artifacts (recoverable offload) -------------------------------------------------------------------
    def offload(self, text: str, label: str = "") -> str:
        self.store.prune(self.retention_days, int(self.max_artifact_mb * 2**20))
        text = S.redact(str(text))
        if len(text) > self.max_artifact_chars:
            text = text[: self.max_artifact_chars] + f"\n…[cut at {self.max_artifact_chars:,} characters]"
        return f"artifact://{self.store.put_artifact(text, S.redact(str(label))[:500] if label else '')}"

    def read_artifact(self, artifact_id: str, offset: int = 0, length: int = 12_000) -> str:
        text = self.store.get_artifact(artifact_id)
        chunk = text[offset: offset + length]
        rest = len(text) - offset - len(chunk)
        return chunk + (f"\n…[{rest} more chars; call read_artifact with offset={offset + len(chunk)}]" if rest > 0
                        else "")

    # ---- in-step guard -------------------------------------------------------------------------------------
    def start_step(self, context_tokens: int, reply_text: str = "") -> None:
        """Call once per step, before ingesting its tool outputs: `context_tokens` = the real prompt size of the
        call just made (from the provider's usage), `reply_text` = the reply that issued the tool calls."""
        self._step_used = int(context_tokens) + int(estimate_tokens(reply_text) * self.token_ratio)

    def ingest_tool_output(self, name: str, text: str, context_tokens: int | None = None) -> str:
        """Returns the text to put in the context: the output itself, or a pointer if it would push the next
        prompt past `guard` × window."""
        if self._step_used is None:
            self.start_step(context_tokens or 0)
        if C.needs_preview(text, self.window, self.preview):
            short = C.preview(text, self.preview_tokens)
            if short != text:
                text = f"{short}\n\n[Full output stored at {self.offload(text, name)}; page it with read_artifact.]"
        n = int(estimate_tokens(text) * self.token_ratio)
        if C.guard_exceeded(self._step_used, n, self.window, self.guard):
            text = GUARDED.format(name=name, tokens=estimate_tokens(text), pointer=self.offload(text, name))
            n = int(estimate_tokens(text) * self.token_ratio)
        self._step_used += n
        return text

    def end_step(self) -> int:
        """Predicted size of the next prompt (real tokens); resets the step."""
        used, self._step_used = self._step_used or 0, None
        return used

    # ---- compaction (ReSum's official prompts) -------------------------------------------------------------
    def should_compact(self, context_tokens: int) -> bool:
        return C.should_compact(context_tokens, self.window, self.trigger)

    def maybe_compact(self, messages: list[dict[str, Any]], *, context_tokens: int, question: str
                      ) -> list[dict[str, Any]]:
        """If the context reached `trigger` × window, replace the history with ReSum's reset message
        (question + summary) plus the notes. Messages are OpenAI-style dicts; the first one is kept as the
        system message if its role is 'system'."""
        if not self.should_compact(context_tokens) or self.summarize is None:
            return messages
        system = [m for m in messages[:1] if m.get("role") == "system"]
        if self.compaction == "handoff":
            transcript = "\n".join(f"[{m.get('role')}] {m.get('content')}" for m in messages[len(system):])
            recap = self.summarize(f"<conversation>\n{transcript}\n</conversation>\n\n{self.handoff_prompt()}")
            return self.apply_handoff(messages, recap, question=question) if (recap or "").strip() else messages
        history = "\n".join(str({"role": m.get("role"), "content": m.get("content")}) for m in messages[len(system):])
        template = P.QUERY_SUMMARY_PROMPT_LAST if self._last_summary else P.QUERY_SUMMARY_PROMPT
        prompt = (template.replace("{{{question}}}", question).replace("{{{recent_history_messages}}}", history)
                  .replace("{{{last_summary}}}", self._last_summary or ""))
        out = re.sub(r"<think>.*?</think>", "", self.summarize(prompt) or "", flags=re.S).strip()
        if not out:
            return messages
        if "<summary>" in out and "</summary>" in out:
            out = out.split("<summary>")[1].split("</summary>")[0]
        self._last_summary = f"<summary>{S.escape_tags(out, 'summary')}</summary>"
        reset = P.NEW_OBSERVATION.format(question=question, summary=self._last_summary)
        if self.notes():
            reset += "\n\n" + RECALL.format(notes=self._recall_text())
        return system + [{"role": "user", "content": reset}]

    # ---- handoff compaction (NVIDIA EoCC, arXiv 2611.05306) -------------------------------------------------
    def handoff_prompt(self) -> str:
        """The paper's compaction prompt (App. G), to send as a user message; the reply is the recap."""
        from eam.techniques.eocc import compaction_prompt

        return compaction_prompt(self.handoff_variant)

    def apply_handoff(self, messages: list[dict[str, Any]], recap: str, *, question: str
                      ) -> list[dict[str, Any]]:
        """Reset to the system message, the task, the notes and the recap (nothing else is kept)."""
        from eam.techniques.eocc import RECAP_SECTION

        system = [m for m in messages[:1] if m.get("role") == "system"]
        text = f"Task: {question}"
        if self.notes():
            text += "\n\n" + RECALL.format(notes=self._recall_text())
        text += "\n\n" + RECAP_SECTION.format(recap=S.escape_tags(str(recap).strip(), "recap"))
        return system + [{"role": "user", "content": text}]

    # ---- tools for the agent -------------------------------------------------------------------------------
    @staticmethod
    def tool_specs() -> list[dict[str, Any]]:
        return [
            {"name": "write_note", "description": "Create or overwrite a named note in your persistent workspace. "
             "Optionally give its type, the files it concerns, and the name of an older note it replaces (that note "
             "is then no longer recalled).",
             "input_schema": {"type": "object", "properties": {
                 "name": {"type": "string"}, "content": {"type": "string"},
                 "type": {"type": "string", "enum": list(NOTE_TYPES)},
                 "files": {"type": "array", "items": {"type": "string"}},
                 "supersedes": {"type": "string"}},
                 "required": ["name", "content"]}},
            {"name": "read_notes", "description": "Read the notes in your persistent workspace (the newest that fit; "
             "older ones are listed by name), or one note by name.",
             "input_schema": {"type": "object", "properties": {"name": {"type": "string"}}}},
            {"name": "read_artifact", "description": "Read content that was moved out of the context "
             "(artifact://ID), paging with offset/length in characters.",
             "input_schema": {"type": "object", "properties": {"artifact_id": {"type": "string"},
                                                               "offset": {"type": "integer"},
                                                               "length": {"type": "integer"}},
                              "required": ["artifact_id"]}},
        ]

    def call_tool(self, name: str, args: dict[str, Any]) -> str:
        if name == "write_note":
            files = args.get("files") if isinstance(args.get("files"), list) else None
            return self.write_note(str(args.get("name", "note")), str(args.get("content", "")),
                                   type=str(args.get("type") or "note"), supersedes=str(args.get("supersedes") or ""),
                                   files=[str(f) for f in files] if files else None)
        if name == "read_notes":
            return self.read_notes(str(args["name"]) if args.get("name") else None)
        if name == "read_artifact":
            return self.read_artifact(str(args.get("artifact_id", "")), int(args.get("offset", 0) or 0),
                                      int(args.get("length", 12_000) or 12_000))
        raise ValueError(f"unknown memory tool '{name}'")
