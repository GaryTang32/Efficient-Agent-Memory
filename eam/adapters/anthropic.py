"""AutoMemory for the Claude API (Anthropic Messages API, Python SDK `anthropic`).

Two parts, both on the same note store:

* `MemoryMiddleware` wraps your own `client.messages.create` loop: the memory rules go in `system`, recalled notes in
  the first user message, and the memory tools in `tools`; after each response it records the real prompt size, runs
  tool calls (long outputs become a preview, memory tools run in-process), resets the history once the window is 75%
  full, and saves the final answer.
* `NoteMemoryTool` is a backend for Claude's client-side memory tool (``memory_20250818``): each file under
  ``/memories`` is an AutoMemory note, so what Claude saves there is recalled in later sessions. It also plugs into the
  SDK's tool runner (``client.beta.messages.tool_runner(tools=[NoteMemoryTool(root)], ...)``).

    mem = MemoryMiddleware("~/.eam-memory/project-x", window=200_000, summarize=cheap_llm)
    params = mem.start(task, system="You are a careful analyst.", tools=my_tools)
    while True:
        response = client.messages.create(model=MODEL, max_tokens=16000, **params)
        if not mem.step(response, params["messages"], run_tool):   # run_tool(name, input) -> str
            break

`step` appends the reply and the tool results to `params["messages"]` in place. The parts (`record`, `tool_results`,
`compact`, `end`) are public for loops that need them separately.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Callable, Iterable

from anthropic.lib.tools import BetaAbstractMemoryTool, ToolError

from eam.adapters.base import MemoryHooks
from eam.automem import core as C
from eam.memory_skill import MemorySkill
from eam.safety import redact, wrap_memory

ROOT = "/memories"
MAX_PATH = 200  # note names are capped at 200 characters

__all__ = ["MemoryMiddleware", "NoteMemoryTool"]


def _block(b: Any) -> dict[str, Any]:
    return b if isinstance(b, dict) else b.to_dict()


def _content_text(content: Any) -> str:
    """Message content (a string or content blocks, as dicts or SDK objects) as plain text for the summarizer."""
    if isinstance(content, str):
        return content
    parts = []
    for b in map(_block, content or []):
        kind = b.get("type")
        if kind == "text":
            parts.append(b.get("text", ""))
        elif kind == "tool_use":
            parts.append(f"[tool call {b.get('name')} {json.dumps(b.get('input', {}))}]")
        elif kind == "tool_result":
            parts.append(f"[tool result] {_content_text(b.get('content', ''))}")
        elif kind not in ("thinking", "redacted_thinking"):
            parts.append(f"[{kind}]")
    return "\n".join(parts)


class MemoryMiddleware:
    """AutoMemory around a Messages API loop. `memory_tool=True` also offers Claude's memory tool, backed by the same
    notes. Other keyword arguments go to MemorySkill (window, summarize, store, ...)."""

    def __init__(self, root: str | Path | None = None, *, hooks: MemoryHooks | None = None,
                 memory_tool: bool = False, **skill_kwargs: Any):
        self.hooks = hooks if hooks is not None else MemoryHooks(root, **skill_kwargs)
        self.memory_tool = NoteMemoryTool(skill=self.hooks.skill) if memory_tool else None

    def start(self, task: str, *, system: str | Iterable[dict[str, Any]] = "",
              tools: Iterable[Any] = ()) -> dict[str, Any]:
        """Begin a session. Returns `system`, `messages` and `tools` to pass to `messages.create`."""
        if isinstance(system, str):
            system_param: Any = self.hooks.system_text(system)
        else:  # text blocks, e.g. with cache_control: the rules go in a block of their own at the end
            system_param = [*system, {"type": "text", "text": self.hooks.system_text()}]
        specs = [*tools, *self.hooks.tool_specs()]
        if self.memory_tool is not None:
            specs.append(self.memory_tool.to_dict())
        return {"system": system_param, "messages": [{"role": "user", "content": self.hooks.start_session(task)}],
                "tools": specs}

    def record(self, response: Any) -> None:
        """Record the prompt size from `response.usage` (input + cache read + cache write tokens)."""
        u = response.usage
        size = (u.input_tokens or 0) + (getattr(u, "cache_read_input_tokens", 0) or 0) + \
            (getattr(u, "cache_creation_input_tokens", 0) or 0)
        self.hooks.after_call(size, self._reply_text(response))

    def tool_results(self, response: Any, run_tool: Callable[[str, dict[str, Any]], Any] | None = None
                     ) -> dict[str, Any] | None:
        """Run the response's tool calls and return the user message of tool_result blocks (None without calls).
        Memory tools run here; other tools run through `run_tool(name, input)`, which returns a string or content
        blocks. Exceptions become error results."""
        uses = [b for b in response.content if b.type == "tool_use"]
        if not uses:
            return None
        return {"role": "user", "content": [self._run(b, run_tool) for b in uses]}

    def compact(self, messages: list[Any]) -> list[Any]:
        """The reset (task, summary and notes as one user message) once the prompt reached the trigger; otherwise
        `messages` itself."""
        flat = [{"role": m["role"], "content": _content_text(m["content"])} for m in messages]
        out = self.hooks.compact(flat)
        if out is flat:
            return messages
        reset = [{"role": "user", "content": m["content"]} for m in out if m["role"] != "system"]
        return reset or [{"role": "user", "content": self.hooks.task}]

    def end(self, answer: str) -> None:
        """Autosave the final answer."""
        self.hooks.end_session(answer)

    def step(self, response: Any, messages: list[Any],
             run_tool: Callable[[str, dict[str, Any]], Any] | None = None) -> bool:
        """Handle one response: append it and its tool results to `messages` (in place, compacting when due).
        Returns True while the loop should call the model again; on the final answer, autosaves and returns False."""
        self.record(response)
        messages.append({"role": "assistant", "content": response.content})
        results = self.tool_results(response, run_tool)
        if results is not None:
            messages.append(results)
            messages[:] = self.compact(messages)
            return True
        if response.stop_reason == "pause_turn":  # a server tool paused the turn: send it back as it is
            return True
        self.end(self._reply_text(response))
        return False

    @staticmethod
    def _reply_text(response: Any) -> str:
        return "\n".join(b.text for b in response.content if b.type == "text")

    def _run(self, block: Any, run_tool: Callable[[str, dict[str, Any]], Any] | None) -> dict[str, Any]:
        name, args = block.name, dict(block.input or {})
        result: dict[str, Any] = {"type": "tool_result", "tool_use_id": block.id}
        try:
            if self.memory_tool is not None and name == self.memory_tool.name:
                out: Any = self.memory_tool.call(args)
            elif self.hooks.is_memory_tool(name):
                out = self.hooks.call_tool(name, args)
            elif run_tool is None:
                raise ValueError(f"no runner for tool '{name}'")
            else:
                out = self._ingest(name, run_tool(name, args))
        except Exception as exc:  # the model sees the error and can recover
            return {**result, "content": f"Error: {exc}", "is_error": True}
        return {**result, "content": out}

    def _ingest(self, name: str, out: Any) -> Any:
        if isinstance(out, str):
            return self.hooks.on_tool_result(name, out)
        if isinstance(out, list):
            return [{**b, "text": self.hooks.on_tool_result(name, b["text"])}
                    if isinstance(b, dict) and b.get("type") == "text" else b for b in out]
        return self.hooks.on_tool_result(name, str(out))


def _size(n: int) -> str:
    return f"{n}B" if n < 1024 else f"{n / 1024:.1f}K" if n < 2**20 else f"{n / 2**20:.1f}M"


class NoteMemoryTool(BetaAbstractMemoryTool):
    """Claude's memory tool on the AutoMemory note store: the file ``/memories/a/b.md`` is the note of that name.
    Paths outside ``/memories``, with ``.``/``..`` parts or a secret in them are rejected; file contents are redacted
    on write and capped at the skill's `max_note_chars`; file views come back inside a ``<memory>`` block (data, not
    instructions). Each change is one store transaction, so concurrent sessions keep each other's edits."""

    def __init__(self, root: str | Path | None = None, *, skill: MemorySkill | None = None, max_files: int = 500,
                 cache_control: Any = None):
        super().__init__(cache_control=cache_control)
        self.skill = skill if skill is not None else MemorySkill(root)
        self.max_files = int(max_files)

    # ---- paths and notes ------------------------------------------------------------------------------------------
    @staticmethod
    def _path(path: Any) -> str:
        p = str(path or "").strip()
        parts = p.rstrip("/").split("/")
        if (len(p) > MAX_PATH or any(ord(c) < 32 or c == "\\" for c in p) or parts[:2] != ["", "memories"]
                or any(s in ("", ".", "..") for s in parts[2:])):
            raise ToolError(f"Invalid path {p[:MAX_PATH]!r}: use {ROOT} or a path under it, without '.' or '..' parts "
                            f"(at most {MAX_PATH} characters).")
        if redact(p) != p:
            raise ToolError("Invalid path: it looks like it contains a secret.")
        return "/".join(parts)

    @staticmethod
    def _files(notes: list[Any]) -> dict[str, Any]:
        return {n.name: n for n in notes if n.name.startswith(ROOT + "/")}

    @staticmethod
    def _under(files: dict[str, Any], path: str) -> list[str]:
        return [p for p in files if p.startswith(path + "/")] if path != ROOT else list(files)

    def _check_free(self, files: dict[str, Any], path: str) -> None:
        if path == ROOT or path in files or self._under(files, path):
            raise ToolError(f"The destination {path} already exists")
        parent = path.rsplit("/", 1)[0]
        while parent != ROOT:
            if parent in files:
                raise ToolError(f"{parent} is a file, not a directory")
            parent = parent.rsplit("/", 1)[0]

    def _write(self, notes: list[Any], path: str, text: str) -> str:
        if len(text) > self.skill.max_note_chars:
            raise ToolError(f"File {path} would have {len(text):,} characters; the limit is "
                            f"{self.skill.max_note_chars:,}.")
        note = C.make_note(path, text, max_chars=self.skill.max_note_chars, source="memory_tool")
        C.upsert(notes, note)
        return " Secrets in it were redacted." if note.text != text else ""

    def _file(self, files: dict[str, Any], path: str) -> Any:
        if path not in files:
            raise ToolError(f"The path {path} does not exist. Please provide a valid path.")
        return files[path]

    # ---- commands -------------------------------------------------------------------------------------------------
    def view(self, command: Any) -> str:
        path = self._path(command.path)
        files = self._files(self.skill.store.load())
        if path in files:
            lines = files[path].text.split("\n")
            start, end = 1, len(lines)
            if command.view_range and len(command.view_range) == 2:
                start = max(1, command.view_range[0])
                end = len(lines) if command.view_range[1] == -1 else min(len(lines), command.view_range[1])
            body = "\n".join(f"{i:>6}\t{lines[i - 1]}" for i in range(start, end + 1))
            text = f"Here's the content of {path} with line numbers:\n{body}"
            return wrap_memory(text, path) if self.skill.wrap else text
        under = self._under(files, path)
        if path != ROOT and not under:
            raise ToolError(f"The path {path} does not exist. Please provide a valid path.")
        sizes: dict[str, int] = {}
        for p in under:
            n, rel = len(files[p].text.encode()), p[len(path) + 1:].split("/")
            for depth in range(1, min(len(rel), 2) + 1):
                key = "/".join(rel[:depth]) + ("/" if depth < len(rel) else "")
                sizes[key] = sizes.get(key, 0) + n
        lines = [f"{_size(sum(len(files[p].text.encode()) for p in under))}\t{path}"]
        lines += [f"{_size(n)}\t{path}/{rel}" for rel, n in sorted(sizes.items())]
        return (f"Here're the files and directories up to 2 levels deep in {path}, excluding hidden items:\n"
                + "\n".join(lines))

    def create(self, command: Any) -> str:
        path = self._path(command.path)
        with self.skill.store.transaction() as notes:
            files = self._files(notes)
            if path in files:
                raise ToolError(f"File {path} already exists")
            self._check_free(files, path)
            if len(files) >= self.max_files:
                raise ToolError(f"Memory is full ({self.max_files} files); delete or merge files first.")
            extra = self._write(notes, path, str(command.file_text))
        return f"File created successfully at: {path}.{extra}"

    def str_replace(self, command: Any) -> str:
        path = self._path(command.path)
        with self.skill.store.transaction() as notes:
            text, old = self._file(self._files(notes), path).text, str(command.old_str)
            count = text.count(old) if old else 0
            if count != 1:
                raise ToolError(f"No replacement was performed: old_str appears {count} times in {path}; it must "
                                "appear exactly once.")
            extra = self._write(notes, path, text.replace(old, str(command.new_str), 1))
        return f"The memory file {path} has been edited.{extra}"

    def insert(self, command: Any) -> str:
        path = self._path(command.path)
        with self.skill.store.transaction() as notes:
            lines = self._file(self._files(notes), path).text.split("\n")
            if lines[-1] == "":
                lines.pop()
            at = int(command.insert_line)
            if not 0 <= at <= len(lines):
                raise ToolError(f"Invalid `insert_line` parameter: {at}. It should be within the range "
                                f"[0, {len(lines)}].")
            lines.insert(at, str(command.insert_text).rstrip("\n"))
            extra = self._write(notes, path, "\n".join(lines) + "\n")
        return f"The file {path} has been edited.{extra}"

    def delete(self, command: Any) -> str:
        path = self._path(command.path)
        if path == ROOT:
            raise ToolError(f"Cannot delete the {ROOT} directory itself")
        with self.skill.store.transaction() as notes:
            files = self._files(notes)
            gone = {path} if path in files else set(self._under(files, path))
            if not gone:
                raise ToolError(f"The path {path} does not exist")
            notes[:] = [n for n in notes if n.name not in gone]
        return f"Successfully deleted {path}"

    def rename(self, command: Any) -> str:
        old, new = self._path(command.old_path), self._path(command.new_path)
        if old == ROOT:
            raise ToolError(f"Cannot rename the {ROOT} directory itself")
        with self.skill.store.transaction() as notes:
            files = self._files(notes)
            moving = [old] if old in files else self._under(files, old)
            if not moving:
                raise ToolError(f"The path {old} does not exist")
            if new.startswith(old + "/"):
                raise ToolError(f"Cannot move {old} into itself")
            self._check_free(files, new)
            for p in moving:
                files[p].name = self._path(new + p[len(old):])
        return f"Successfully renamed {old} to {new}"

    def clear_all_memory(self) -> str:
        with self.skill.store.transaction() as notes:
            notes[:] = [n for n in notes if not n.name.startswith(ROOT + "/")]
        return "All memory cleared"
