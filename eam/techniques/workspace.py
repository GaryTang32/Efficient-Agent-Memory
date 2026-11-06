"""Persistent note workspace — the file-system-as-memory idea of FS-Researcher (Ignoramus0817 et al.,
ACL 2026 main; USTC + Metastone) and Manus's "file system as context". The agent writes notes that outlive the
context window *and* the session, and reads them back at the start of a new session.

FS-Researcher's code has no licence file, so this is our own minimal implementation of the idea (three tools),
not a port of its code. Notes persist for the life of the technique object, i.e. across the rounds of a
multi-round task.
"""

from __future__ import annotations

from eam.agent.context import Tool
from eam.llm.types import ToolSpec
from eam.techniques.base import Technique


class NoteWorkspace(Technique):
    name = "fs_workspace"
    source = "FS-Researcher (ACL'26, USTC) file-system workspace; Manus file system as context"
    provenance = "ported from the paper's idea (repo has no licence); our minimal implementation"

    def __init__(self, max_note_chars: int = 20000):
        self.max_note_chars = int(max_note_chars)
        self.notes: dict[str, str] = {}

    def system_addendum(self):
        return ("Workspace: you have a persistent note workspace that survives beyond this conversation and across "
                "sessions (tools write_note, read_notes). Save every intermediate result you may need later — "
                "running totals, findings, which files are done — and at the start of a session read your notes "
                "before doing anything else.")

    def tools(self, ctx):
        def write(args, ctx):
            name = str(args.get("name", "note")).strip() or "note"
            content = str(args.get("content", ""))[: self.max_note_chars]
            self.notes[name] = content
            return f"Saved note '{name}' ({len(content)} chars). Notes: {', '.join(sorted(self.notes))}"

        def read(args, ctx):
            if not self.notes:
                return "The workspace is empty."
            return "\n\n".join(f"## {k}\n{v}" for k, v in sorted(self.notes.items()))

        return [
            Tool(ToolSpec("write_note", "Create or overwrite a named note in your persistent workspace.",
                          {"type": "object", "properties": {"name": {"type": "string"}, "content": {"type": "string"}},
                           "required": ["name", "content"]}), write),
            Tool(ToolSpec("read_notes", "Read all notes in your persistent workspace.",
                          {"type": "object", "properties": {}}), read),
        ]
