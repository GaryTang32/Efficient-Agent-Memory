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

`summarize(prompt) -> str` is any LLM call (a cheaper model is fine: the summary prompt is ReSum's official
prompt). Tool specs for write_note / read_notes / read_artifact come from `tool_specs()`; route those calls to
`call_tool`. The MCP server (`eam/mcp_server.py`) exposes the same store as MCP tools.
"""

from __future__ import annotations

import json
import re
import time
from pathlib import Path
from typing import Any, Callable

from eam.techniques.auto_memory import GUARDED, RECALL
from eam.techniques.third_party import resum as P
from eam.techniques.workspace import NoteWorkspace
from eam.tokens import estimate_tokens


class MemorySkill:
    def __init__(self, root: str | Path, *, window: int = 200_000, trigger: float = 0.75, guard: float = 0.9,
                 token_ratio: float = 1.5, summarize: Callable[[str], str] | None = None,
                 max_note_chars: int = 20_000):
        self.root = Path(root).expanduser()
        (self.root / "artifacts").mkdir(parents=True, exist_ok=True)
        self.window, self.trigger, self.guard, self.token_ratio = int(window), trigger, guard, token_ratio
        self.summarize = summarize
        self.max_note_chars = max_note_chars
        self._step_used: int | None = None
        self._last_summary: str | None = None

    # ---- persistent notes ----------------------------------------------------------------------------------
    @property
    def _notes_path(self) -> Path:
        return self.root / "notes.json"

    def notes(self) -> dict[str, str]:
        return json.loads(self._notes_path.read_text()) if self._notes_path.exists() else {}

    def write_note(self, name: str, content: str) -> str:
        notes = self.notes()
        name = (name or "note").strip() or "note"
        notes[name] = str(content)[: self.max_note_chars]
        self._notes_path.write_text(json.dumps(notes, indent=1))
        return f"Saved note '{name}' ({len(notes[name])} chars). Notes: {', '.join(sorted(notes))}"

    def read_notes(self) -> str:
        notes = self.notes()
        return "\n\n".join(f"## {k}\n{v}" for k, v in sorted(notes.items())) if notes else "The workspace is empty."

    def system_addendum(self) -> str:
        return NoteWorkspace().system_addendum()

    def session_preamble(self) -> str:
        """Recall: the notes, to put at the top of a new session's first message (empty if there are none)."""
        return RECALL.format(notes=self.read_notes()) + "\n\n" if self.notes() else ""

    def save_session(self, answer: str, label: str | None = None) -> None:
        """Autosave: keep a session's final answer as a note."""
        if answer:
            self.write_note(label or f"session {time.strftime('%Y-%m-%d %H:%M:%S')} final answer", answer)

    # ---- artifacts (recoverable offload) -------------------------------------------------------------------
    def offload(self, text: str, label: str = "") -> str:
        aid = f"a{len(list((self.root / 'artifacts').glob('*.txt'))) + 1:05d}"
        (self.root / "artifacts" / f"{aid}.txt").write_text(text)
        if label:
            (self.root / "artifacts" / f"{aid}.label").write_text(label)
        return f"artifact://{aid}"

    def read_artifact(self, artifact_id: str, offset: int = 0, length: int = 12_000) -> str:
        aid = artifact_id.removeprefix("artifact://")
        path = self.root / "artifacts" / f"{aid}.txt"
        if not re.fullmatch(r"a\d{5}", aid) or not path.exists():
            raise ValueError(f"no artifact '{artifact_id}'")
        text = path.read_text()
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
        n = int(estimate_tokens(text) * self.token_ratio)
        if self.guard and self._step_used + n > self.guard * self.window and n > 200:
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
        return context_tokens >= self.trigger * self.window

    def maybe_compact(self, messages: list[dict[str, Any]], *, context_tokens: int, question: str
                      ) -> list[dict[str, Any]]:
        """If the context reached `trigger` × window, replace the history with ReSum's reset message
        (question + summary) plus the notes. Messages are OpenAI-style dicts; the first one is kept as the
        system message if its role is 'system'."""
        if not self.should_compact(context_tokens) or self.summarize is None:
            return messages
        system = [m for m in messages[:1] if m.get("role") == "system"]
        history = "\n".join(str({"role": m.get("role"), "content": m.get("content")}) for m in messages[len(system):])
        template = P.QUERY_SUMMARY_PROMPT_LAST if self._last_summary else P.QUERY_SUMMARY_PROMPT
        prompt = (template.replace("{{{question}}}", question).replace("{{{recent_history_messages}}}", history)
                  .replace("{{{last_summary}}}", self._last_summary or ""))
        out = re.sub(r"<think>.*?</think>", "", self.summarize(prompt) or "", flags=re.S).strip()
        if not out:
            return messages
        if "<summary>" in out and "</summary>" in out:
            out = out.split("<summary>")[1].split("</summary>")[0]
        self._last_summary = f"<summary>{out}</summary>"
        reset = P.NEW_OBSERVATION.format(question=question, summary=self._last_summary)
        if self.notes():
            reset += "\n\n" + RECALL.format(notes=self.read_notes())
        return system + [{"role": "user", "content": reset}]

    # ---- tools for the agent -------------------------------------------------------------------------------
    @staticmethod
    def tool_specs() -> list[dict[str, Any]]:
        return [
            {"name": "write_note", "description": "Create or overwrite a named note in your persistent workspace.",
             "input_schema": {"type": "object", "properties": {"name": {"type": "string"},
                                                               "content": {"type": "string"}},
                              "required": ["name", "content"]}},
            {"name": "read_notes", "description": "Read all notes in your persistent workspace.",
             "input_schema": {"type": "object", "properties": {}}},
            {"name": "read_artifact", "description": "Read content that was moved out of the context "
             "(artifact://ID), paging with offset/length in characters.",
             "input_schema": {"type": "object", "properties": {"artifact_id": {"type": "string"},
                                                               "offset": {"type": "integer"},
                                                               "length": {"type": "integer"}},
                              "required": ["artifact_id"]}},
        ]

    def call_tool(self, name: str, args: dict[str, Any]) -> str:
        if name == "write_note":
            return self.write_note(str(args.get("name", "note")), str(args.get("content", "")))
        if name == "read_notes":
            return self.read_notes()
        if name == "read_artifact":
            return self.read_artifact(str(args.get("artifact_id", "")), int(args.get("offset", 0) or 0),
                                      int(args.get("length", 12_000) or 12_000))
        raise ValueError(f"unknown memory tool '{name}'")
