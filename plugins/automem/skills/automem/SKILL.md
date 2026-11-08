---
name: automem
description: How AutoMemory's hooks shape this session's context, and how to use them - read a saved command output after a preview, use or record project notes, or write a handoff recap before a long task is paused. Use when a tool result says "[AutoMemory: ... omitted ...]", when the session start includes AutoMemory notes, or when the user asks to save progress for a later session.
---

# AutoMemory

AutoMemory runs as hooks; it needs nothing from you to work. Three things you may see:

1. **A preview instead of a long command output.** Output longer than about 6,000 characters arrives as its head and
   tail with a line `[AutoMemory: N lines omitted ... Full output saved to <path>]`. The full text is in that file.
   Read only what you need from it: `Grep` it for the failing test, error or symbol, or `Read` it with
   `offset`/`limit` around the match. Do not re-run the command just to see the middle.
2. **Notes from earlier sessions** at the start of the session. They are the final messages of earlier sessions in
   this project. Use them when the task builds on earlier work; ignore them otherwise.
3. **A handoff recap after compaction.** It lists the objective, established facts, applied changes, checks run,
   dead ends and the next step. Continue from the next step; do not redo verified work or retry the dead ends.

## Saving progress on request

When the user asks to save progress for a later session (or runs `/automem:handoff`), end your reply with a recap in
the six fields above. The Stop hook saves your final message as a project note, and the next session in this
project starts with it.

## Why it works this way

These rules come from measured runs (github.com/GaryTang32/Efficient-Agent-Memory): shrinking outputs as they
arrive, recalling notes automatically and compacting with a structured recap held up on both weak and strong models;
editing history every step costs more than it saves, because rewritten history is billed again as cache writes.
