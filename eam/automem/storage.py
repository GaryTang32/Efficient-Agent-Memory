"""Where AutoMemory keeps notes and offloaded outputs: interchangeable stores behind one small interface (standard
library only).

    JsonStore(root)    the default: notes.json (schema v2) and artifacts/*.txt in a directory
    SQLiteStore(path)  one SQLite file (sqlite3 is in the standard library), for many notes or many writers
    MemoryStore()      in memory, for tests and short-lived agents

Every store gives the same guarantees: notes are read and changed inside `transaction()` (no lost updates between
concurrent sessions), files are owner-only, artifact ids never collide, and `prune` bounds artifacts by age and size.
A graph or vector store would plug in here, behind the same interface.
"""

from __future__ import annotations

import contextlib
import json
import os
import re
import sqlite3
import sys
import time
from pathlib import Path
from typing import Iterator, Protocol

from eam import safety as S
from eam.automem.notes import Note, dump_document, load_document

ARTIFACT_ID = re.compile(r"a\d{5}")


class Store(Protocol):
    def load(self) -> list[Note]: ...

    def transaction(self) -> contextlib.AbstractContextManager[list[Note]]:
        """Yields the notes (oldest first) for reading and changing in place; saved when the block exits cleanly."""
        ...

    def put_artifact(self, text: str, label: str = "") -> str: ...

    def get_artifact(self, aid: str) -> str: ...

    def prune(self, max_age_days: float, max_bytes: int) -> int: ...


def check_artifact_id(aid: str) -> str:
    aid = aid.removeprefix("artifact://")
    if not ARTIFACT_ID.fullmatch(aid):
        raise ValueError(f"no artifact '{aid}'")
    return aid


# ---- JSON files (default) -------------------------------------------------------------------------------------------
class JsonStore:
    def __init__(self, root: str | Path):
        self.root = S.private_dir(root)
        self.art = S.private_dir(self.root / "artifacts")
        self.path = self.root / "notes.json"

    def load(self) -> list[Note]:
        if not self.path.exists():
            return []
        try:
            return load_document(json.loads(self.path.read_text(encoding="utf-8")))
        except (ValueError, UnicodeDecodeError):  # unreadable (JSONDecodeError is a ValueError): set aside, start over
            aside = self.path.with_name(f"notes.json.corrupt-{time.strftime('%Y%m%d-%H%M%S')}")
            os.replace(self.path, aside)
            print(f"automem: unreadable notes store moved to {aside}", file=sys.stderr)
            return []

    @contextlib.contextmanager
    def transaction(self) -> Iterator[list[Note]]:
        with S.locked(self.path):
            notes = self.load()
            yield notes
            S.write_private(self.path, json.dumps(dump_document(notes), indent=1))

    def put_artifact(self, text: str, label: str = "") -> str:
        n = len(list(self.art.glob("*.txt"))) + 1
        while not S.create_private(self.art / f"a{n:05d}.txt", text):  # exclusive create: writers never collide
            n += 1
        if label:
            S.write_private(self.art / f"a{n:05d}.label", label)
        return f"a{n:05d}"

    def get_artifact(self, aid: str) -> str:
        path = self.art / f"{check_artifact_id(aid)}.txt"
        if not path.exists():
            raise ValueError(f"no artifact '{aid}'")
        return path.read_text(encoding="utf-8")

    def prune(self, max_age_days: float, max_bytes: int) -> int:
        return S.prune(self.art, max_age_days=max_age_days, max_bytes=max_bytes)


# ---- SQLite -----------------------------------------------------------------------------------------------------------
class SQLiteStore:
    """One file, WAL journal; `transaction()` holds a write lock (BEGIN IMMEDIATE), so writers queue, readers don't."""

    def __init__(self, path: str | Path):
        self.path = Path(path).expanduser()
        S.private_dir(self.path.parent)
        if not self.path.exists():
            S.create_private(self.path, "")  # owner-only from the start; sqlite fills the empty file
        with contextlib.closing(self._connect()) as db:
            db.execute("PRAGMA journal_mode=WAL")  # persistent: set once, not on every connection
            db.executescript("""
                CREATE TABLE IF NOT EXISTS notes (seq INTEGER PRIMARY KEY AUTOINCREMENT, name TEXT UNIQUE NOT NULL,
                                                  doc TEXT NOT NULL);
                CREATE TABLE IF NOT EXISTS artifacts (id INTEGER PRIMARY KEY AUTOINCREMENT, text TEXT NOT NULL,
                                                      label TEXT, created REAL NOT NULL, bytes INTEGER NOT NULL);""")

    def _connect(self) -> sqlite3.Connection:
        db = sqlite3.connect(self.path, timeout=30, isolation_level=None)
        db.execute("PRAGMA busy_timeout=30000")
        return db

    def load(self) -> list[Note]:
        with contextlib.closing(self._connect()) as db:
            return [Note.from_dict(json.loads(d)) for (d,) in db.execute("SELECT doc FROM notes ORDER BY seq")]

    @contextlib.contextmanager
    def transaction(self) -> Iterator[list[Note]]:
        with contextlib.closing(self._connect()) as db:
            db.execute("BEGIN IMMEDIATE")
            try:
                notes = [Note.from_dict(json.loads(d)) for (d,) in db.execute("SELECT doc FROM notes ORDER BY seq")]
                yield notes
                db.execute("DELETE FROM notes")
                db.executemany("INSERT INTO notes (name, doc) VALUES (?, ?)",
                               [(n.name, json.dumps(n.to_dict())) for n in notes])
                db.execute("COMMIT")
            except BaseException:
                if db.in_transaction:
                    db.execute("ROLLBACK")
                raise

    def put_artifact(self, text: str, label: str = "") -> str:
        with contextlib.closing(self._connect()) as db:
            cur = db.execute("INSERT INTO artifacts (text, label, created, bytes) VALUES (?, ?, ?, ?)",
                             (text, label, time.time(), len(text.encode())))
            return f"a{cur.lastrowid:05d}"

    def get_artifact(self, aid: str) -> str:
        n = int(check_artifact_id(aid)[1:])
        with contextlib.closing(self._connect()) as db:
            row = db.execute("SELECT text FROM artifacts WHERE id = ?", (n,)).fetchone()
        if row is None:
            raise ValueError(f"no artifact '{aid}'")
        return row[0]

    def prune(self, max_age_days: float, max_bytes: int) -> int:
        with contextlib.closing(self._connect()) as db:
            gone = 0
            if max_age_days:
                gone += db.execute("DELETE FROM artifacts WHERE created < ?",
                                   (time.time() - max_age_days * 86400,)).rowcount
            if max_bytes:
                total = db.execute("SELECT coalesce(sum(bytes), 0) FROM artifacts").fetchone()[0]
                for aid, size in db.execute("SELECT id, bytes FROM artifacts ORDER BY id").fetchall():
                    if total <= max_bytes:
                        break
                    db.execute("DELETE FROM artifacts WHERE id = ?", (aid,))
                    total, gone = total - size, gone + 1
            return gone


# ---- memory -----------------------------------------------------------------------------------------------------------
class MemoryStore:
    def __init__(self):
        self.notes: list[Note] = []
        self.artifacts: dict[str, tuple[str, float]] = {}
        self._next = 1

    def load(self) -> list[Note]:
        return [Note.from_dict(n.to_dict()) for n in self.notes]

    @contextlib.contextmanager
    def transaction(self) -> Iterator[list[Note]]:
        notes = self.load()
        yield notes
        self.notes = notes

    def put_artifact(self, text: str, label: str = "") -> str:
        aid, self._next = f"a{self._next:05d}", self._next + 1
        self.artifacts[aid] = (text, time.time())
        return aid

    def get_artifact(self, aid: str) -> str:
        aid = check_artifact_id(aid)
        if aid not in self.artifacts:
            raise ValueError(f"no artifact '{aid}'")
        return self.artifacts[aid][0]

    def prune(self, max_age_days: float, max_bytes: int) -> int:
        cutoff = time.time() - max_age_days * 86400 if max_age_days else None
        gone = [a for a, (_, t) in self.artifacts.items() if cutoff and t < cutoff]
        for a in gone:
            del self.artifacts[a]
        total = sum(len(x.encode()) for x, _ in self.artifacts.values())
        for a in list(self.artifacts):  # oldest first (insertion order)
            if not max_bytes or total <= max_bytes:
                break
            total -= len(self.artifacts.pop(a)[0].encode())
            gone.append(a)
        return len(gone)
