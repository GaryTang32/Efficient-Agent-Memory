#!/usr/bin/env python3
"""A stand-in for `claude -p` for the offline rehearsal of scripts/run_cc_test.py: no model is called.

It speaks the parts of Claude Code's command line and stream-json output the runner uses, and exercises the same
plumbing a real session would: it runs the day's report commands, cuts outputs above 30,000 characters the way Claude
Code does (head plus a saved copy), calls the plugin's real hook script (session start, post tool use, pre compact,
stop) when --plugin-dir is given, writes Claude Code auto memory when it is on, writes notes through the AutoMemory
store in full mode and NOTES.md when asked, compacts when its synthetic context passes the window, keeps a transcript
in ~/.claude/projects/<folder>/, and answers. FAKE_MODE=oracle answers from FAKE_KEY (rehearsal only); stale repeats
day 1's answer; anything else answers nothing useful.
"""

from __future__ import annotations

import json
import os
import re
import subprocess
import sys
import uuid
from pathlib import Path

CUT = 30_000


def arg(flag: str, default=None):
    a = sys.argv
    return a[a.index(flag) + 1] if flag in a and a.index(flag) + 1 < len(a) else default


def project_dir() -> Path:
    return Path.home() / ".claude" / "projects" / re.sub(r"[^A-Za-z0-9]", "-", str(Path.cwd()))


def main() -> None:
    if "--version" in sys.argv:
        print("0.0.0 (fake Claude Code)")
        return
    prompt, resume = arg("-p", ""), arg("--resume")
    plugin = arg("--plugin-dir")
    hook = Path(plugin) / "hooks" / "automem_hook.py" if plugin else None
    sid = resume or str(uuid.uuid4())
    proj = project_dir()
    proj.mkdir(parents=True, exist_ok=True)
    state_f = proj / f"{sid}.state.json"
    state = json.loads(state_f.read_text()) if state_f.exists() else {"context": 12_000, "cost": 0.0, "turns": 0}
    window = int(os.environ.get("CLAUDE_CODE_AUTO_COMPACT_WINDOW", "200000"))
    transcript = proj / f"{sid}.jsonl"
    events = []

    def emit(ev: dict) -> None:
        ev.setdefault("session_id", sid)
        events.append(ev)
        print(json.dumps(ev), flush=True)

    def run_hook(event: str, payload: dict) -> dict | None:
        if not hook:
            return None
        r = subprocess.run([sys.executable, str(hook), event], input=json.dumps(payload), capture_output=True,
                           text=True, env=os.environ, timeout=30)
        try:
            return json.loads(r.stdout) if r.stdout.strip().startswith("{") else ({"text": r.stdout} if r.stdout else None)
        except json.JSONDecodeError:
            return None

    n_msg = [0]

    def call(content: list, add_tokens: int) -> None:
        n_msg[0] += 1
        state["context"] += add_tokens
        state["turns"] += 1
        read, write = state["context"] - 2_000, 2_000
        state["cost"] += read * 0.1e-6 + write * 2.5e-6 + 300 * 10e-6
        emit({"type": "assistant", "message": {"id": f"msg_{sid[:8]}_{state['turns']}", "role": "assistant",
              "content": content, "usage": {"input_tokens": 3, "cache_read_input_tokens": read,
                                            "cache_creation_input_tokens": write, "output_tokens": 300}}})
        if state["context"] > window - 33_000:
            pre = state["context"]
            run_hook("pre_compact", {"trigger": "auto", "session_id": sid})
            state["context"] = 15_000
            emit({"type": "system", "subtype": "compact_boundary", "compact_metadata": {"trigger": "auto", "pre_tokens": pre}})
            run_hook("session_start", {"cwd": str(Path.cwd()), "source": "compact", "session_id": sid})

    def tool(name: str, inp: dict, output: str, tid: str) -> str:
        call([{"type": "tool_use", "id": tid, "name": name, "input": inp}], 500)
        shown = output
        if name == "Bash" and len(output) > CUT:
            saved = Path(os.environ.get("TMPDIR", "/tmp")) / "tool-results" / f"{tid}.txt"
            saved.parent.mkdir(parents=True, exist_ok=True)
            saved.write_text(output)
            shown = output[:2000] + f"\n\nOutput too large ({len(output)} characters). Full output saved to: {saved}"
            resp = {"stdout": output[:CUT], "stderr": "", "interrupted": False, "isImage": False,
                    "persistedOutputPath": str(saved), "persistedOutputSize": len(output)}
        else:
            resp = {"stdout": output, "stderr": "", "interrupted": False, "isImage": False}
        if name == "Bash":
            out = run_hook("post_tool_use", {"tool_name": "Bash", "cwd": str(Path.cwd()), "tool_use_id": tid,
                                             "tool_input": inp, "tool_response": resp, "session_id": sid})
            upd = ((out or {}).get("hookSpecificOutput") or {}).get("updatedToolOutput")
            if upd:
                shown = (upd.get("stdout") or "") + (upd.get("stderr") or "")
        emit({"type": "user", "message": {"role": "user", "content": [
            {"type": "tool_result", "tool_use_id": tid, "content": shown}]}})
        state["context"] += len(shown) // 4
        return shown

    emit({"type": "system", "subtype": "init", "model": "claude-sonnet-5-5", "tools": ["Bash", "Read", "Write"],
          "mcp_servers": [{"name": "automem", "status": "connected"}] if arg("--mcp-config") else [], "plugins": []})
    run_hook("session_start", {"cwd": str(Path.cwd()), "source": "resume" if resume else "startup", "session_id": sid})

    day = int(m.group(1)) if (m := re.search(r"today is day (\d+) of", prompt)) else 1
    if "tools/report.py" in prompt:
        kinds = (["opening"] if day == 1 else []) + ["receipts", "shipments", "audit"]
        for i, kind in enumerate(kinds):
            out = subprocess.run([sys.executable, "tools/report.py", kind], capture_output=True, text=True).stdout
            tool("Bash", {"command": f"python tools/report.py {kind}"}, out, f"toolu_{sid[:6]}_{day}_{i}")
    if os.environ.get("CLAUDE_CODE_DISABLE_AUTO_MEMORY") == "0":
        mem = proj / "memory"
        mem.mkdir(exist_ok=True)
        with open(mem / "MEMORY.md", "a") as fh:
            fh.write(f"- day {day}: worked on the ledger\n")
        call([{"type": "tool_use", "id": f"toolu_mem_{day}", "name": "Write",
               "input": {"file_path": str(mem / "MEMORY.md"), "content": "..."}}], 100)
    if os.environ.get("AUTOMEM_WORKSPACE") == "on" and os.environ.get("AUTOMEM_STORE"):
        sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
        from eam.memory_skill import MemorySkill

        MemorySkill(os.environ["AUTOMEM_STORE"]).write_note(f"day {day} events", f"events seen on day {day}", type="fact")
        call([{"type": "tool_use", "id": f"toolu_note_{day}", "name": "mcp__automem__write_note",
               "input": {"name": f"day {day} events", "content": "..."}}], 100)
    if "NOTES.md" in prompt:
        with open("NOTES.md", "a") as fh:
            fh.write(f"day {day}\n")
        call([{"type": "tool_use", "id": f"toolu_notes_{day}", "name": "Write",
               "input": {"file_path": str(Path.cwd() / "NOTES.md"), "content": "..."}}], 100)

    mode, answer = os.environ.get("FAKE_MODE", ""), "I could not work it out."
    if mode in ("oracle", "stale") and os.environ.get("FAKE_KEY") and "report.py" in prompt:
        key = json.loads(Path(os.environ["FAKE_KEY"]).read_text())
        k = key[day - 1] if mode == "oracle" else key[0]
        answer = "Done.\n```json\n" + json.dumps({"day": day, "stock": k["stock"], "lowest": k["lowest"]}) + "\n```"
    elif "Fix the Django issue" in prompt:
        answer = "No change made (rehearsal)."
    call([{"type": "text", "text": answer}], 300)
    run_hook("stop", {"cwd": str(Path.cwd()), "session_id": sid, "last_assistant_message": answer,
                      "stop_hook_active": False})
    emit({"type": "result", "subtype": "success", "is_error": False, "num_turns": state["turns"], "result": answer,
          "total_cost_usd": round(state["cost"], 6), "usage": {"input_tokens": 3, "output_tokens": 300}})
    state_f.write_text(json.dumps(state))
    with open(transcript, "a") as fh:
        fh.write("".join(json.dumps(e) + "\n" for e in events))


if __name__ == "__main__":
    main()
