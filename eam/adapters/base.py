"""MemoryHooks: AutoMemory as a handful of hooks any agent loop can call. Standard library only.

One object per agent; one session per task. The hooks, in the order a loop calls them:

    hooks = MemoryHooks("~/.eam-memory/project-x", window=200_000, summarize=cheap_llm)

    system = hooks.system_text(base_system)         # the note rules and the rule that <memory> is data
    first = hooks.start_session(task)               # recalled notes + the task: the session's first user message
    tools = my_tools + hooks.tool_specs()           # write_note, read_notes, read_artifact

    # after each model call
    hooks.after_call(prompt_tokens, reply_text)     # the real prompt size, from the provider's usage
    for call in tool_calls:
        if hooks.is_memory_tool(call.name):
            out = hooks.call_tool(call.name, call.args)
        else:
            out = hooks.on_tool_result(call.name, run(call))   # preview of long outputs + the in-step guard
    messages = hooks.compact(messages)              # the rare reset, only once the window is 75% full

    hooks.end_session(final_answer)                 # autosave (replaces the previous session's answer in recall)

Messages for `compact` are OpenAI-style dicts (role, content). Adapters translate their framework's messages.
`stats` records the time spent in the hooks, so adapters can check the <5 ms per step budget.
"""

from __future__ import annotations

import time
from contextlib import contextmanager
from pathlib import Path
from typing import Any, Callable, Iterator

from eam.automem.settings import check_all
from eam.memory_skill import MemorySkill

MEMORY_TOOLS = ("write_note", "read_notes", "read_artifact")
# what a session may set for itself; anything it does not set keeps the agent's defaults
SESSION_SETTINGS = ("window", "trigger", "guard", "preview", "preview_tokens", "preview_max_tokens", "recall_budget",
                    "compaction", "handoff_variant")


def _check(values: dict[str, Any]) -> dict[str, Any]:
    """Validate session settings against eam/automem/settings.py; `compact_at` (tokens) becomes `trigger` later."""
    unknown = set(values) - set(SESSION_SETTINGS) - {"compact_at"}
    if unknown:
        raise ValueError(f"unknown setting(s) {sorted(unknown)}; choose from {list(SESSION_SETTINGS) + ['compact_at']}")
    return check_all(values)


class MemoryHooks:
    def __init__(self, root: str | Path | None = None, *, skill: MemorySkill | None = None,
                 summarize: Callable[[str], str] | None = None, compact_at: int | None = None, **skill_kwargs: Any):
        """`compact_at` sets the reset point in tokens instead of as `trigger` (a share of `window`): with a 1M-token
        model, `window=1_000_000, compact_at=400_000` resets at 400K."""
        self.skill = skill if skill is not None else MemorySkill(root, summarize=summarize, **skill_kwargs)
        if summarize is not None and skill is not None:
            self.skill.summarize = summarize
        if compact_at is not None:
            self._set({"compact_at": compact_at})
        self.defaults = {k: getattr(self.skill, k) for k in SESSION_SETTINGS}  # what every session starts from
        self._next: dict[str, Any] = {}
        self.task = ""
        self.recalled = ""  # the recall block of the current session (start_session = recalled + task)
        self.prompt_tokens = 0
        self.compactions = 0
        self.stats = {"calls": 0, "seconds": 0.0}

    @contextmanager
    def _timed(self) -> Iterator[None]:
        t = time.perf_counter()
        try:
            yield
        finally:
            self.stats["calls"] += 1
            self.stats["seconds"] += time.perf_counter() - t

    # ---- session -------------------------------------------------------------------------------------------
    def system_text(self, base: str = "") -> str:
        """The base system prompt plus AutoMemory's rules (note-taking, and never obeying text inside <memory>)."""
        return f"{base}\n\n{self.skill.system_addendum()}" if base else self.skill.system_addendum()

    def recall(self) -> str:
        """The recalled notes as a block to put before the task (empty when there are none)."""
        with self._timed():
            return self.skill.session_preamble()

    def _set(self, settings: dict[str, Any]) -> None:
        settings = _check(settings)
        at = settings.pop("compact_at", None)
        for k, v in settings.items():
            setattr(self.skill, k, v)
        if at is not None:
            if at > self.skill.window:
                raise ValueError(f"compact_at ({at:,}) must not exceed window ({self.skill.window:,})")
            self.skill.trigger = max(0.05, int(at) / self.skill.window)

    def next_session(self, **settings: Any) -> None:
        """Settings for the next session only (window, trigger or compact_at, guard, preview, preview_tokens,
        preview_max_tokens, recall_budget, compaction, handoff_variant). The session after it goes back to the
        defaults. Works with every adapter, since they all start sessions through these hooks."""
        self._next.update(_check(settings))

    @property
    def settings(self) -> dict[str, Any]:
        """The settings of the current session."""
        return {k: getattr(self.skill, k) for k in SESSION_SETTINGS}

    def start_session(self, task: str, **settings: Any) -> str:
        """Begin a session: returns the first user message, the recalled notes followed by the task. Keyword
        settings (or those given to `next_session`) apply to this session only; the rest are the defaults."""
        overrides = {**self._next, **_check(settings)}
        self._next = {}
        for k, v in self.defaults.items():
            setattr(self.skill, k, v)
        if overrides:
            self._set(overrides)
        self.task, self.prompt_tokens, self.compactions = str(task), 0, 0
        self.skill.end_step()
        self.recalled = self.recall()
        return self.recalled + self.task

    def end_session(self, answer: str) -> None:
        """Autosave the final answer; it supersedes the previous session's answer in recall."""
        with self._timed():
            self.skill.save_session(str(answer or ""))
            self.skill.end_step()

    # ---- per model call ------------------------------------------------------------------------------------
    def after_call(self, prompt_tokens: int | None, reply_text: str = "") -> None:
        """Call after each model call, before its tool calls run: the real prompt size, from the provider's usage
        (input + cache read + cache write tokens). Unknown sizes count as 0: previews still apply, the guard and
        compaction need the size."""
        with self._timed():
            self.prompt_tokens = int(prompt_tokens or 0)
            self.skill.end_step()
            self.skill.start_step(self.prompt_tokens, reply_text or "")

    def on_tool_result(self, name: str, text: str) -> str:
        """The text to show the model for a tool's output: the output itself, a head/tail preview with the full text
        stored (long outputs), or a pointer (when it would push the next prompt past the guard)."""
        with self._timed():
            return self.skill.ingest_tool_output(str(name), str(text), context_tokens=self.prompt_tokens)

    def should_compact(self, prompt_tokens: int | None = None) -> bool:
        return self.skill.should_compact(self.prompt_tokens if prompt_tokens is None else int(prompt_tokens))

    def compact(self, messages: list[dict[str, Any]], prompt_tokens: int | None = None) -> list[dict[str, Any]]:
        """Reset the history to the task, a summary and the notes once the prompt reached the trigger (75% of the
        window by default); otherwise return `messages` unchanged. Needs `summarize`."""
        with self._timed():
            size = self.prompt_tokens if prompt_tokens is None else int(prompt_tokens)
            out = self.skill.maybe_compact(messages, context_tokens=size, question=self.task)
            if out is not messages:
                self.compactions += 1
                self.prompt_tokens = 0
            return out

    # ---- memory tools --------------------------------------------------------------------------------------
    def tool_specs(self) -> list[dict[str, Any]]:
        """write_note, read_notes and read_artifact as {name, description, input_schema} (Anthropic shape)."""
        return self.skill.tool_specs()

    @staticmethod
    def is_memory_tool(name: str) -> bool:
        return name in MEMORY_TOOLS

    def call_tool(self, name: str, args: dict[str, Any] | None) -> str:
        """Run a memory tool. Errors come back as text for the model, not as exceptions."""
        with self._timed():
            try:
                return self.skill.call_tool(name, dict(args or {}))
            except (ValueError, KeyError, FileNotFoundError) as exc:
                return f"Error: {exc}"

    def overhead_ms(self) -> float:
        """Mean time per hook call, in milliseconds."""
        return 1000 * self.stats["seconds"] / max(1, self.stats["calls"])
