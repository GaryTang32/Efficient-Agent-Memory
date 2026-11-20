# Changelog

## Unreleased

**Large windows and per-session settings.**
- `MemoryHooks(..., compact_at=400_000)` sets the reset point in tokens.
- `preview_max_tokens` (default 16,000) caps the preview threshold, so that with a 1M-token window, 100K-token
  outputs no longer enter whole. Windows up to 160K are unchanged, including every measured setting.
- Settings can change per session, through `start_session(task, **settings)` or `next_session(**settings)`. A
  session that sets nothing goes back to the defaults. `next_session` works with every adapter.
- The MCP server reads `EAM_MEMORY_COMPACT_AT` and `EAM_MEMORY_PREVIEW_MAX_TOKENS`.
- Every library setting has an accepted range (`eam/automem/settings.py`). `MemorySkill` and `MemoryHooks` refuse a
  value outside it, with an error naming the range. The plugin falls back to the default instead.
- The plugin's sizes can be given in tokens (`AUTOMEM_PREVIEW_TOKENS`, `AUTOMEM_PREVIEW_KEEP_TOKENS`,
  `AUTOMEM_RECALL_TOKENS`), or as a share of Claude Code's compaction window (`AUTOMEM_PREVIEW_SHARE`).
- `docs/settings.md` lists all 54 settings with their defaults, ranges and where each default comes from.

## 0.3.0 (2026-11-20): framework adapters

AutoMemory in the agent framework you already use (Claude API, Claude Agent SDK, LangGraph, OpenAI Agents SDK), a
refreshed MCP server, a lighter install, and a recall fix measured on a ten-day job. The core still needs only the
Python standard library.

**Docs.** The README is now a practical guide: what the repo does, install, a quick start per agent framework, how
AutoMemory works, the methodology, results at a glance and how to use the bench. The full results, validation
round, plugin pilots and methods moved to [docs/results.md](docs/results.md). The overview diagram shows the adapters.

**Framework adapters** (`eam/adapters/`, `pip install "efficient-agent-memory[<extra>]"`). Each adapter wires recall,
the note tools, previews, the guard, compaction and autosave into its host, and imports its framework only when used.
- **Claude API:** `MemoryMiddleware` wraps a Messages API loop. `NoteMemoryTool` stores the files of Claude's memory
  tool as notes.
- **Claude Agent SDK:** `AgentMemory` provides hooks and in-process memory tools. Claude Code keeps its own
  compaction.
- **LangChain v1 / LangGraph:** `AutoMemoryMiddleware`.
- **OpenAI Agents SDK:** `OpenAIAgentsMemory`.
- **Your own loop:** `MemoryHooks`, the framework-neutral hooks the adapters share.

Every adapter passes the same offline conformance suite (`tests/adapters/conformance.py`, run with fake models). The
library, the MCP server and the adapters no longer load the bench code when imported. Guide:
[docs/adapters.md](docs/adapters.md).

**MCP server.**
- It agrees on protocol revisions up to 2025-11-25 with the client.
- It sends instructions: recall first, and treat `<memory>` content as data.
- It marks each tool as read-only or writing.
- It is tested against the official MCP client.
- It is installed as the `automem-mcp` command.

**Fix.** Two sessions ending in the same second no longer overwrite each other's autosaved answer.

**Recall keeps only the newest session answer.** Autosaved session answers used to pile up in recall: by day 8–10 of a
ten-day job they filled about a quarter of Sonnet's prompt, mostly as copies of earlier answers. Now each autosave
supersedes the previous one; older answers stay readable by name.
- The library (`MemorySkill.save_session`) does this by default.
- The note-keeping bench presets (`automem_v2`, `_strong`, `_slim`, `_adaptive`) set `recall_results=latest`.
- Step 5 measured it against step 4's runs. On ops_stream the notes fell from 26% to 16% of Sonnet's prompt at 95%
  of the cost, with 99% of needed facts carried. Haiku cost 82% of baseline, carried 82% of needed facts instead of
  73%, and re-opened fewer old files. On the three-round audit task the changes were within run-to-run noise.

**New bench switches, off by default.**
- `note_ids=true` asks for ids alongside the values noted. It cut Haiku's re-reading of old files, but not its
  cost or score.
- `verify=true` sends a final answer back once while the agent's last test run still fails. It uses a new
  `Technique.on_final` hook.

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
