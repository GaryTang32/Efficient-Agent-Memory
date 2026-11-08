#!/usr/bin/env python3
"""AutoMemory hooks for Claude Code (standard library only).

The rules come from this repository's measurements (README, docs/automem.md): steps the harness applies by itself
held up on weak and strong models; steps that rely on the model managing its own memory did not. Every hook here
runs without a model call and never rewrites history that is already in the prompt cache.

    session_start  SessionStart  recall: this project's notes (earlier sessions' results) as additional context;
                                 runs again after compaction, so the notes survive it
    post_tool_use  PostToolUse   previews at ingestion: a Bash stream longer than AUTOMEM_PREVIEW_CHARS reaches the
                                 model as head + tail, and the full text is saved to a file it can Read or Grep.
                                 For outputs Claude Code itself truncated (about 30,000 characters and up), its
                                 saved copy (`persistedOutputPath`) is used, so the tail is the real end of the
                                 output, not the end of the truncated part
    pre_compact    PreCompact    the handoff recap of NVIDIA's "You don't need long context" (arXiv 2611.05306,
                                 App. G) as the compaction instructions
    stop           Stop          autosave: the turn's final message is kept as a project note (no extra turn)

Settings (environment variables):
    AUTOMEM_PREVIEW_CHARS  preview threshold per stream, characters (default 6000; 0 turns previews off)
    AUTOMEM_PREVIEW_KEEP   characters kept at the head and at the tail (default 1500 each)
    AUTOMEM_NOTES          on | off: recall and autosave (default on)
    AUTOMEM_RECALL_CHARS   most recent notes recalled, characters (default 3000)
    AUTOMEM_DATA           where state lives (default: $CLAUDE_PLUGIN_DATA, else ~/.automem)
"""

from __future__ import annotations

import hashlib
import json
import os
import re
import subprocess
import sys
import time
from pathlib import Path

HANDOFF = """When summarising this conversation, write a concise handoff recap; the conversation will continue from \
the system prompt, the task and this recap. Record:
1. Objective - one line describing the required result.
2. Established facts - exact paths, relevant symbols or commands, observed values, and important errors/output. \
Separate observations from unverified ideas.
3. Applied changes - each changed/created file, what changed, and whether verified.
4. Verification - exact checks run, outcomes, failures, obstacles, and workarounds.
5. Dead ends - failed approaches that should not be repeated.
6. Remaining plan - outstanding subgoals, in execution order; the immediate next command or edit; and the condition \
for completion.
Copy exact identifiers, numbers, file paths and line numbers as they appear. If needed output was truncated or saved \
to a file by AutoMemory, give the file path and a narrow command to retrieve it."""
# Fields and wording from the paper's mini-swe-agent compaction prompt (App. G); framed here as instructions for
# Claude Code's own compaction, which the PreCompact hook may extend but not replace.


def _env_int(name: str, default: int) -> int:
    try:
        return int(os.environ.get(name, default))
    except ValueError:
        return default


def data_dir() -> Path:
    root = os.environ.get("AUTOMEM_DATA") or os.environ.get("CLAUDE_PLUGIN_DATA") or str(Path.home() / ".automem")
    p = Path(root).expanduser()
    p.mkdir(parents=True, exist_ok=True)
    return p


def project_dir(cwd: str) -> Path:
    """State is kept per project: the git top level of `cwd` (or `cwd` itself)."""
    top = cwd
    try:
        r = subprocess.run(["git", "-C", cwd, "rev-parse", "--show-toplevel"], capture_output=True, text=True,
                           timeout=5)
        if r.returncode == 0 and r.stdout.strip():
            top = r.stdout.strip()
    except (OSError, subprocess.SubprocessError):
        pass
    key = hashlib.sha1(top.encode()).hexdigest()[:12]
    p = data_dir() / "projects" / f"{Path(top).name or 'root'}-{key}"
    p.mkdir(parents=True, exist_ok=True)
    return p


def notes_on() -> bool:
    return os.environ.get("AUTOMEM_NOTES", "on").lower() not in ("off", "0", "false", "no")


# ---- previews at ingestion ----------------------------------------------------------------------------------
def preview(text: str, keep: int, path: Path) -> str:
    head, tail = text[:keep], text[-keep:]
    head = head[: head.rfind("\n") + 1] or head  # cut at line ends where possible
    nl = tail.find("\n")
    tail = tail[nl + 1:] if 0 <= nl < len(tail) - 1 else tail
    omitted = text[len(head): len(text) - len(tail)]
    lines = omitted.count("\n") + (0 if omitted.endswith("\n") or not omitted else 1)
    note = (f"\n[AutoMemory: {lines} lines ({len(omitted):,} characters) omitted here. "
            f"Full output saved to {path} - Read it with offset/limit, or Grep it.]\n")
    return head + note + tail


def post_tool_use(d: dict) -> dict | None:
    limit, keep = _env_int("AUTOMEM_PREVIEW_CHARS", 6000), _env_int("AUTOMEM_PREVIEW_KEEP", 1500)
    resp = d.get("tool_response")
    if not limit or d.get("tool_name") != "Bash" or not isinstance(resp, dict):
        return None
    store = project_dir(d.get("cwd") or os.getcwd()) / "outputs"
    command = str((d.get("tool_input") or {}).get("command", ""))
    if str(data_dir() / "projects") in command and "/outputs/" in command:
        return None  # the agent is reading a saved output: never preview it again
    changed, out = False, dict(resp)
    saved = resp.get("persistedOutputPath")
    if isinstance(saved, str) and Path(saved).is_file():
        # Claude Code already cut this output to its first characters and saved the whole of it (stdout and stderr
        # merged); its own preview shows only the head. Build head + tail from the complete file, where test
        # summaries and failures usually are.
        text = Path(saved).read_text(errors="replace")
        out["stdout"], out["stderr"] = preview(text, keep, Path(saved)), ""
        return {"hookSpecificOutput": {"hookEventName": "PostToolUse", "updatedToolOutput": {
            k: out[k] for k in ("stdout", "stderr", "interrupted", "isImage") if k in out}}}
    for stream in ("stdout", "stderr"):
        text = resp.get(stream)
        if isinstance(text, str) and len(text) > limit and len(text) > 2 * keep + 200:
            store.mkdir(parents=True, exist_ok=True)
            stamp = time.strftime("%Y%m%d-%H%M%S")
            tid = re.sub(r"[^A-Za-z0-9]", "", str(d.get("tool_use_id", "")))[-8:]
            path = store / f"bash-{stamp}-{tid}-{stream}.log"
            path.write_text(f"$ {command}\n\n{text}")
            out[stream] = preview(text, keep, path)
            changed = True
    if not changed:
        return None
    updated = {k: out[k] for k in ("stdout", "stderr", "interrupted", "isImage") if k in out}
    return {"hookSpecificOutput": {"hookEventName": "PostToolUse", "updatedToolOutput": updated}}


# ---- notes: recall and autosave -----------------------------------------------------------------------------
def notes_file(cwd: str) -> Path:
    return project_dir(cwd) / "notes.jsonl"


def session_start(d: dict) -> dict | None:
    if not notes_on():
        return None
    f = notes_file(d.get("cwd") or os.getcwd())
    if not f.exists():
        return None
    notes = [json.loads(line) for line in f.read_text().splitlines() if line.strip()]
    budget, picked = _env_int("AUTOMEM_RECALL_CHARS", 3000), []
    for n in reversed(notes):  # most recent first, within the budget
        entry = f"- {n.get('time', '')}: {n.get('text', '').strip()}"
        if sum(len(e) for e in picked) + len(entry) > budget:
            break
        picked.append(entry)
    if not picked:
        return None
    text = ("AutoMemory notes from earlier sessions in this project (oldest first). Use them when the task builds on "
            "earlier work; otherwise ignore them.\n" + "\n".join(reversed(picked)))
    return {"hookSpecificOutput": {"hookEventName": "SessionStart", "additionalContext": text}}


def stop(d: dict) -> None:
    if not notes_on() or d.get("stop_hook_active"):
        return None
    text = str(d.get("last_assistant_message") or "").strip()
    if len(text) < 40:  # acknowledgements and empty turns are not worth recalling
        return None
    f = notes_file(d.get("cwd") or os.getcwd())
    with f.open("a") as fh:
        fh.write(json.dumps({"time": time.strftime("%Y-%m-%d %H:%M"), "session": d.get("session_id", ""),
                             "text": text[:1500]}) + "\n")
    lines = f.read_text().splitlines()
    if len(lines) > 50:  # keep the store small
        f.write_text("\n".join(lines[-50:]) + "\n")
    return None


def main() -> None:
    event = sys.argv[1] if len(sys.argv) > 1 else ""
    try:
        d = json.load(sys.stdin)
    except (json.JSONDecodeError, ValueError):
        d = {}
    try:
        if event == "pre_compact":
            print(HANDOFF)  # stdout becomes instructions for the compaction summary
            return
        out = {"post_tool_use": post_tool_use, "session_start": session_start, "stop": stop}.get(event, lambda _: None)(d)
        if out:
            print(json.dumps(out))
    except Exception as exc:  # a memory hook must never break the session
        print(f"automem hook error ({event}): {exc}", file=sys.stderr)


if __name__ == "__main__":
    main()
