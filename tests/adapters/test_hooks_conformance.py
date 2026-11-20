"""The reference driver: a plain agent loop over MemoryHooks (what eam.adapters.base documents), run through the
conformance suite. It also checks the suite itself: a loop that skips a hook must fail."""

from __future__ import annotations

import json

import pytest

from adapters.conformance import (TOOL_SPECS, Seen, Step, check_all, check_compaction, fake_summarize, run_tool)
from eam.adapters import MemoryHooks
from eam.automem import JsonStore


def flatten(messages: list[dict]) -> str:
    return "\n".join(str(m.get("content")) for m in messages)


class PlainLoop:
    name = "plain loop"
    compacts = True

    def __init__(self, skip: str = ""):
        self.skip = skip

    def run(self, root, task, script, *, window):
        hooks = MemoryHooks(root, window=window, summarize=fake_summarize)
        seen = Seen()
        system = hooks.system_text("You count widgets.") if self.skip != "rules" else "You count widgets."
        tools = TOOL_SPECS + hooks.tool_specs()
        assert {t["name"] for t in tools} >= {"write_note", "read_notes", "read_artifact", "fetch_report"}
        first = hooks.start_session(task) if self.skip != "recall" else task
        messages = [{"role": "system", "content": system}, {"role": "user", "content": first}]
        for step in script:
            seen.system.append(messages[0]["content"])
            seen.inputs.append(flatten(messages[1:]))
            hooks.after_call(step.prompt_tokens, "")
            if step.kind == "final":
                if self.skip != "autosave":
                    hooks.end_session(step.name_or_text)
                break
            args = step.args
            messages.append({"role": "assistant", "content": f"[tool call {step.name_or_text} {json.dumps(args)}]"})
            if hooks.is_memory_tool(step.name_or_text):
                out = hooks.call_tool(step.name_or_text, args)
            else:
                raw = run_tool(step.name_or_text, args)
                out = hooks.on_tool_result(step.name_or_text, raw) if self.skip != "preview" else raw
            messages.append({"role": "user", "content": f"[tool result] {out}"})
            if self.skip != "compact":
                messages = hooks.compact(messages)
        return seen, hooks


def test_plain_loop_conforms(tmp_path):
    check_all(PlainLoop(), tmp_path)


def test_plain_loop_compacts(tmp_path):
    check_compaction(PlainLoop(), tmp_path)


@pytest.mark.parametrize("skip", ["rules", "recall", "preview", "autosave"])
def test_suite_catches_a_skipped_hook(tmp_path, skip):
    with pytest.raises(AssertionError):
        check_all(PlainLoop(skip), tmp_path)


def test_suite_catches_missing_compaction(tmp_path):
    with pytest.raises(AssertionError):
        check_compaction(PlainLoop("compact"), tmp_path)


def test_memory_tool_errors_come_back_as_text(tmp_path):
    hooks = MemoryHooks(tmp_path, window=40_000)
    assert hooks.call_tool("read_notes", {"name": "missing"}).startswith("Error:") or \
        "empty" in hooks.call_tool("read_notes", {"name": "missing"})
    assert hooks.call_tool("read_artifact", {"artifact_id": "nope"}).startswith("Error:")


def test_light_import():
    """The library and the adapters' shared layer load no bench code and no third-party package."""
    import subprocess
    import sys

    code = ("import sys, eam.adapters, eam.memory_skill, eam.mcp_server\n"
            "bad = [m for m in sys.modules if m.startswith(('eam.bench', 'eam.agent', 'eam.llm', 'eam.techniques.'))\n"
            "       and not m.startswith('eam.techniques.third_party')]\n"
            "third = [m for m in sys.modules if m.split('.')[0] in ('anthropic', 'langgraph', 'langchain_core', "
            "'agents', 'claude_agent_sdk', 'pydantic', 'httpx')]\n"
            "print(bad, third)\nassert not bad and not third, (bad, third)")
    subprocess.run([sys.executable, "-c", code], check=True)


def test_core_size():
    """Lightweight limit: the core AutoMemory modules stay under 200 KB of source."""
    from pathlib import Path

    import eam

    base = Path(eam.__file__).parent
    files = [*base.glob("automem/*.py"), base / "memory_skill.py", base / "safety.py", base / "tokens.py",
             base / "mcp_server.py", base / "adapters" / "base.py", base / "techniques/third_party/resum.py",
             base / "techniques/third_party/nvidia_eocc.py"]
    assert sum(f.stat().st_size for f in files) < 200_000


def test_store_is_json(tmp_path):
    hooks = MemoryHooks(tmp_path, window=40_000)
    hooks.start_session("t")
    hooks.end_session("an answer long enough to keep")
    assert [n.type for n in JsonStore(tmp_path).load()] == ["result"]

