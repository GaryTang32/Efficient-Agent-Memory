"""Typed notes: what AutoMemory keeps between sessions, with provenance (standard library only).

A note is a named text plus metadata that costs no extra model call: its type (set by the harness from where the
note came from, or by the agent), its source, when it was written, the files it concerns, and whether a newer note
replaced it. Recall skips replaced notes, so a decision that was revised does not come back.

Store document, schema version 2 (``notes.json``)::

    {"version": 2, "notes": [{"name": ..., "text": ..., "type": ..., "source": ..., "time": ..., "session": ...,
                              "files": [...], "supersedes": ..., "status": "active" | "superseded"}, ...]}

Version 1, the plain ``{name: text}`` mapping written before 0.3.0, is read as notes of type ``note`` with source
``migrated`` and rewritten as version 2 on the next write.
"""

from __future__ import annotations

import time
from dataclasses import asdict, dataclass, field
from typing import Any

SCHEMA_VERSION = 2
# fact: an observed value or finding; decision: a choice and its reason; dead_end: an approach that failed;
# command: how to reproduce or check something; result: a session's final answer; handoff: a compaction recap
NOTE_TYPES = ("note", "fact", "decision", "dead_end", "command", "result", "handoff")


def now() -> str:
    return time.strftime("%Y-%m-%d %H:%M:%S")


@dataclass
class Note:
    name: str
    text: str
    type: str = "note"
    source: str = "agent"  # agent (write_note) | autosave | handoff | migrated | user
    time: str = ""
    session: str = ""
    files: list[str] = field(default_factory=list)
    supersedes: str = ""  # name of the note this one replaces
    status: str = "active"  # active | superseded

    def __post_init__(self) -> None:
        if self.type not in NOTE_TYPES:
            self.type = "note"

    @property
    def active(self) -> bool:
        return self.status == "active"

    def heading(self) -> str:
        """The note's heading in recall: its name, plus its type and date when they say something."""
        meta = [t for t in (self.type if self.type != "note" else "", self.time[:10]) if t]
        return f"## {self.name}" + (f" ({', '.join(meta)})" if meta else "")

    def render(self) -> str:
        files = f"\nFiles: {', '.join(self.files)}" if self.files else ""
        return f"{self.heading()}\n{self.text}{files}"

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> "Note":
        known = {k: d[k] for k in cls.__dataclass_fields__ if k in d}
        known["files"] = [str(f) for f in known.get("files") or []]
        return cls(**{**known, "name": str(known.get("name", "note")), "text": str(known.get("text", ""))})


def load_document(data: Any) -> list[Note]:
    """Notes from a store document of either schema version, oldest first."""
    if isinstance(data, dict) and data.get("version") == SCHEMA_VERSION:
        return [Note.from_dict(n) for n in data.get("notes", []) if isinstance(n, dict)]
    if isinstance(data, dict):  # version 1: {name: text}
        return [Note(name=str(k), text=str(v), source="migrated") for k, v in data.items()]
    raise ValueError("not a notes document")


def dump_document(notes: list[Note]) -> dict[str, Any]:
    return {"version": SCHEMA_VERSION, "notes": [n.to_dict() for n in notes]}
