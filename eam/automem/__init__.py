"""AutoMemory, split into layers (standard library only):

    eam.automem.notes    typed notes and the store document schema (version 2, migrates version 1)
    eam.automem.core     the decisions, as pure functions: recall selection, previews, guard, compaction trigger
    eam.automem.storage  where notes and artifacts live: JsonStore (default), SQLiteStore, MemoryStore

Host adapters sit on top: the library (`eam.memory_skill.MemorySkill`), the MCP server (`eam.mcp_server`) and the
Claude Code plugin (`plugins/automem`, which ships its own copy of the safety helpers).
"""

from eam.automem.notes import NOTE_TYPES, SCHEMA_VERSION, Note
from eam.automem.storage import JsonStore, MemoryStore, SQLiteStore, Store

__all__ = ["NOTE_TYPES", "SCHEMA_VERSION", "JsonStore", "MemoryStore", "Note", "SQLiteStore", "Store"]
