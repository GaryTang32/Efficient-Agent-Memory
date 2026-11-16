"""AutoMemory's decisions as pure functions: no file access, no network, no model calls (standard library only).

Every host adapter (the library `MemorySkill`, the MCP server, later the SDK and framework adapters) calls these, so
the measured rules live in one place and are tested once:

* `upsert` adds or replaces a note, redacted, and retires the note it supersedes
* `select_recall` / `recall_text` choose the newest active notes within a token budget and render them, wrapped as
  data (`eam.safety.wrap_memory`) when asked
* `needs_preview` / `preview` decide when an output enters as head and tail, `guard_exceeded` when a step's outputs
  would overflow the window, `should_compact` when to reset
"""

from __future__ import annotations

from eam.automem.notes import Note, now
from eam.safety import redact, wrap_memory
from eam.tokens import estimate_tokens

RECALL_SOURCE = "workspace notes from earlier sessions"


# ---- notes ----------------------------------------------------------------------------------------------------------
def make_note(name: str, text: str, *, max_chars: int, **meta) -> Note:
    """A new note: name and text redacted and bounded, timestamped."""
    name = redact((name or "note").strip() or "note")[:200]
    files = [redact(str(f))[:300] for f in meta.pop("files", None) or []][:20]
    return Note(name=name, text=redact(str(text))[:max_chars], time=meta.pop("time", None) or now(), files=files,
                **meta)


def upsert(notes: list[Note], note: Note) -> bool:
    """Put `note` at the end of `notes` (the end is the newest), replacing a note of the same name, and mark the note it
    supersedes as superseded. Returns whether a note of that name existed. Mutates `notes`."""
    existed = any(n.name == note.name for n in notes)
    notes[:] = [n for n in notes if n.name != note.name]
    if note.supersedes:
        for n in notes:
            if n.name == note.supersedes:
                n.status = "superseded"
    notes.append(note)
    return existed


def active(notes: list[Note]) -> list[Note]:
    return [n for n in notes if n.active]


def select_recall(notes: list[Note], budget_tokens: int) -> tuple[list[Note], list[str]]:
    """The newest active notes whose rendered text fits in `budget_tokens` (always at least one), in their original
    order, and the names of the active notes left out."""
    pool, kept, used = active(notes), [], 0
    for n in reversed(pool):
        cost = estimate_tokens(n.render()) + 2
        if kept and used + cost > budget_tokens:
            break
        kept.append(n)
        used += cost
    names = {n.name for n in kept}
    return list(reversed(kept)), [n.name for n in pool if n.name not in names]


def render_notes(kept: list[Note], rest: list[str]) -> str:
    text = "\n\n".join(n.render() for n in kept)
    if rest:
        text += f"\n\n[Older notes not shown, read one with read_notes(name=...): {', '.join(rest)}]"
    return text


def recall_text(notes: list[Note], budget_tokens: int, *, wrap: bool = True) -> str:
    """Recall for the start of a session or after a reset: '' when there is no active note."""
    if not active(notes):
        return ""
    body = render_notes(*select_recall(notes, budget_tokens))
    return wrap_memory(body, RECALL_SOURCE) if wrap else body


# ---- context decisions ----------------------------------------------------------------------------------------------
def needs_preview(text: str, window: int, share: float) -> bool:
    """An output above `share` × window enters the context as a preview (v2 rule; share 0 turns it off)."""
    return bool(share) and estimate_tokens(text) > share * window


def preview(text: str, preview_tokens: int) -> str:
    """Head and tail of `text` (Strands' head_tail preview); `text` itself when it is short enough."""
    from eam.techniques.strands import preview as head_tail

    return head_tail(text, preview_tokens)


def guard_exceeded(step_used: int, adding: int, window: int, guard: float) -> bool:
    """Would adding `adding` tokens to this step push the next prompt past `guard` × window? Small outputs pass."""
    return bool(guard) and adding > 200 and step_used + adding > guard * window


def should_compact(context_tokens: int, window: int, trigger: float) -> bool:
    return context_tokens >= trigger * window
