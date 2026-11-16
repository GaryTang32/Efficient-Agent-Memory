# Changelog

## Unreleased

**Layers.** AutoMemory is split into a pure core, pluggable storage and thin host adapters (`eam/automem/`):
- `eam.automem.core`: the decisions as pure functions (recall selection within a token budget, previews, the in-step
  guard, the compaction trigger), shared by the library and the MCP server.
- `eam.automem.storage`: `JsonStore` (the default, the same files as before), `SQLiteStore` (one owner-only file,
  WAL journal, safe under concurrent writers) and `MemoryStore`, behind one interface and one conformance test suite.
- `MemorySkill(store=...)` takes any of them; `MemorySkill(root)` works as before.

**Typed notes.** Notes carry a type (fact, decision, dead_end, command, result, handoff or note), source, time, files
and an optional `supersedes` link; a superseded note is no longer recalled. Recall headings show the type and date.
The notes file moves to schema version 2; version 1 files are read as they are and rewritten on the next write. The
MCP `write_note` tool and the library tool spec accept `type`, `files` and `supersedes`. The plugin tags its autosaved
notes as `result`.

## 0.2.0 (2026-11-13): security release

A review of what AutoMemory keeps between sessions found two high-severity issues and several smaller ones. All are
fixed in the library, the MCP server and the Claude Code plugin. See [SECURITY.md](SECURITY.md) for the threat model.

**High**
- Recalled notes, summaries and recaps reached the model as plain text, so instructions saved from a web page or a
  tool output could be obeyed in a later session ("memory poisoning"). They now arrive inside a `<memory>` block marked
  as data, with escaped tags and a system line telling the model never to follow instructions found there.
- Nothing was redacted: secrets printed by a command were saved to output files and notes, with default (often
  world-readable) permissions, and kept forever. Secrets are now replaced with `[REDACTED:kind]` before anything is
  written. Files are owner-only, and saved outputs are deleted after 14 days or beyond 200 MB per project.

**Medium**
- Concurrent sessions could lose notes or overwrite each other's artifacts, and a damaged notes file silently
  disabled recall. Writes are now atomic, notes are updated under a lock, artifact ids are created exclusively, and a
  damaged store is moved aside or skipped line by line.
- The library recalled every note into every session, without limit. Recall now takes at most 10% of the window
  (newest notes first; older ones are listed by name, and `read_notes(name=...)` fetches them).

**Low**
- The MCP server now enforces the allowed handoff variants and says when `write_note` replaces an existing note.
- The plugin reads Claude Code's saved copy of an output only if it is a regular file, not a symlink, and reads a
  very large one as head and tail only.

**Other**
- New: `eam/safety.py` (standard library only), `SECURITY.md`, `tests/test_security.py` (26 adversarial tests).
- The bench technique gains `wrap=true`; it stays off by default so benchmark results remain comparable.
