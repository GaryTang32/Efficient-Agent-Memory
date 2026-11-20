"""The Claude Agent SDK adapter, offline. The SDK runs the Claude Code CLI, which cannot run here, so `SimulatedCLI`
plays its part: it registers the options' hooks the way the SDK does (`_hooks_to_internal_format`), calls them with
the SDK's own hook-input TypedDicts, serializes their answers as the SDK does (`_convert_hook_output_for_cli`), and
talks JSON-RPC to the SDK MCP servers through the SDK's own bridge (`SdkMcpBridge`). The model is shown only what
those answers inject in Claude Code: UserPromptSubmit `additionalContext` next to the prompt, PostToolUse
`updatedToolOutput` in place of the tool result and its `additionalContext` after it."""

from __future__ import annotations

import asyncio
import json
import re
import uuid

import pytest

pytest.importorskip("claude_agent_sdk")

from claude_agent_sdk import (AssistantMessage, ClaudeAgentOptions, HookMatcher, PostToolUseHookInput,  # noqa: E402
                              PostToolUseHookSpecificOutput, PreCompactHookInput, StopHookInput, TextBlock,
                              ToolUseBlock, UserPromptSubmitHookInput, UserPromptSubmitHookSpecificOutput,
                              create_sdk_mcp_server, tool)
from claude_agent_sdk._internal.query import _convert_hook_output_for_cli  # noqa: E402
from claude_agent_sdk._internal.sdk_mcp_bridge import SdkMcpBridge  # noqa: E402
from claude_agent_sdk.types import SyncHookJSONOutput, _hooks_to_internal_format  # noqa: E402

from adapters.conformance import (REPORT, TOOL_SPECS, Seen, check_all, fake_summarize,  # noqa: E402
                                  run_tool)
from eam.adapters.claude_agent_sdk import HANDOFF, AgentMemory  # noqa: E402
from eam.automem import JsonStore  # noqa: E402

PRESET = "[Claude Code's system prompt]"
SPECIFIC = {"UserPromptSubmit": UserPromptSubmitHookSpecificOutput, "PostToolUse": PostToolUseHookSpecificOutput}


def keys(td) -> set[str]:
    return set(td.__required_keys__ | td.__optional_keys__)


def check_shape(out: dict, event: str) -> dict:
    """The answer is a SyncHookJSONOutput with the event's own hookSpecificOutput, and survives the wire."""
    assert isinstance(out, dict) and set(out) <= keys(SyncHookJSONOutput), out
    spec = out.get("hookSpecificOutput")
    if spec is not None:
        assert spec["hookEventName"] == event and set(spec) <= keys(SPECIFIC[event]), spec
    return json.loads(json.dumps(_convert_hook_output_for_cli(out)))


def user_tools(mem: AgentMemory | None):
    """fetch_report and lookup as the user's own @tool functions (wrapped with mem.wrap when mem is given)."""
    made = []
    for spec in TOOL_SPECS:
        async def handler(args, name=spec["name"]):
            return {"content": [{"type": "text", "text": run_tool(name, args)}]}
        t = tool(spec["name"], spec["description"], spec["input_schema"])(handler)
        made.append(mem.wrap(t) if mem else t)
    return create_sdk_mcp_server("work", tools=made)


class SimulatedCLI:
    """What Claude Code does with ClaudeAgentOptions, minus the model."""

    def __init__(self, options: ClaudeAgentOptions, ignore: str = ""):
        self.options, self.ignore = options, ignore
        self.hooks = _hooks_to_internal_format(options.hooks or {})
        self.bridges = {n: SdkMcpBridge(n, c["instance"]) for n, c in options.mcp_servers.items() if c["type"] == "sdk"}
        self.session = {"session_id": str(uuid.uuid4()), "transcript_path": "/tmp/t.jsonl", "cwd": "/tmp"}
        self.ids = 0

    def system(self) -> str:
        sp = self.options.system_prompt
        return f"{PRESET}\n\n{sp.get('append', '')}" if isinstance(sp, dict) else str(sp or "")

    async def fire(self, event: str, data: dict, match: str = "", tool_use_id: str | None = None) -> list[dict]:
        outs = []
        for m in self.hooks.get(event, []):
            if m["matcher"] in (None, "", "*") or re.fullmatch(m["matcher"], match):
                for cb in m["hooks"]:
                    outs.append(check_shape(await cb(data, tool_use_id, {"signal": None}), event))
        return outs

    def context(self, outs: list[dict]) -> list[str]:
        if self.ignore == "additionalContext":
            return []
        return [o["hookSpecificOutput"]["additionalContext"] for o in outs
                if o.get("hookSpecificOutput", {}).get("additionalContext")]

    async def rpc(self, server: str, method: str, params: dict | None = None) -> dict:
        self.ids += 1
        msg = {"jsonrpc": "2.0", "id": self.ids, "method": method, **({"params": params} if params else {})}
        return (await self.bridges[server].handle(msg))["result"]

    async def connect(self) -> dict[str, list[str]]:
        tools = {}
        for name, bridge in self.bridges.items():
            await self.rpc(name, "initialize", {"protocolVersion": "2025-06-18", "capabilities": {},
                                                "clientInfo": {"name": "claude-code", "version": "sim"}})
            await bridge.handle({"jsonrpc": "2.0", "method": "notifications/initialized"})
            tools[name] = [t["name"] for t in (await self.rpc(name, "tools/list"))["tools"]]
        return tools

    async def prompt(self, text: str) -> list[str]:
        """The user prompt as the model receives it: UserPromptSubmit context, then the prompt."""
        outs = await self.fire("UserPromptSubmit", UserPromptSubmitHookInput(
            **self.session, hook_event_name="UserPromptSubmit", prompt=text))
        return self.context(outs) + [text]

    async def call_tool(self, full_name: str, args: dict) -> list[str]:
        """An MCP tool call, then PostToolUse: what the model receives as the tool result."""
        _, server, name = full_name.split("__", 2)
        result = await self.rpc(server, "tools/call", {"name": name, "arguments": args})
        response = result["content"]
        tid = f"toolu_{self.ids}"
        outs = await self.fire("PostToolUse", PostToolUseHookInput(
            **self.session, hook_event_name="PostToolUse", tool_name=full_name, tool_input=args,
            tool_response=response, tool_use_id=tid), match=full_name, tool_use_id=tid)
        for o in outs:
            new = o.get("hookSpecificOutput", {}).get("updatedToolOutput")
            if new is not None and self.ignore != "updatedToolOutput":
                response = new
        shown = response if isinstance(response, str) else "\n".join(b["text"] for b in response)
        return [f"[tool result {full_name}] {shown}"] + self.context(outs)

    async def stop(self, text: str) -> list[dict]:
        return await self.fire("Stop", StopHookInput(**self.session, hook_event_name="Stop", stop_hook_active=False,
                                                     last_assistant_message=text))

    async def close(self):
        for b in self.bridges.values():
            await b.aclose()


class SdkHost:
    """Conformance driver. Claude Code owns compaction in this host, so `check_compaction` does not apply."""
    compacts = False

    def __init__(self, wrap: bool = False, ignore: str = ""):
        self.wrap, self.ignore = wrap, ignore
        self.name = f"claude agent sdk ({'wrapped tools' if wrap else 'PostToolUse'})"

    def run(self, root, task, script, *, window):
        return asyncio.run(self._run(root, task, script, window))

    async def _run(self, root, task, script, window):
        mem = AgentMemory(root, window=window, summarize=fake_summarize)
        base = ClaudeAgentOptions(mcp_servers={"work": user_tools(mem if self.wrap else None)},
                                  allowed_tools=["mcp__work__fetch_report", "mcp__work__lookup"])
        cli, seen = SimulatedCLI(mem.apply(base), self.ignore), Seen()
        listed = await cli.connect()
        assert set(listed["automem"]) == {"write_note", "read_notes", "read_artifact"}
        transcript = await cli.prompt(task)
        try:
            for step in script:
                seen.system.append(cli.system())
                seen.inputs.append("\n".join(transcript))
                full = step.name_or_text if step.kind == "final" else (
                    f"mcp__automem__{step.name_or_text}" if mem.hooks.is_memory_tool(step.name_or_text)
                    else f"mcp__work__{step.name_or_text}")
                block = TextBlock(full) if step.kind == "final" else ToolUseBlock(f"toolu_{len(transcript)}", full,
                                                                                    step.args)
                usage = {"input_tokens": step.prompt_tokens} if step.prompt_tokens is not None else None
                mem.observe(AssistantMessage(content=[block], model="sim", usage=usage))
                if step.kind == "final":
                    assert all(o.get("decision") != "block" for o in await cli.stop(step.name_or_text))
                    break
                transcript.append(f"[tool call {full} {json.dumps(step.args)}]")
                transcript += await cli.call_tool(full, step.args)
        finally:
            await cli.close()
        return seen, mem.hooks


# ---- conformance ---------------------------------------------------------------------------------------------
@pytest.mark.parametrize("wrap", [False, True])
def test_sdk_conforms(tmp_path, wrap):
    check_all(SdkHost(wrap=wrap), tmp_path)


@pytest.mark.parametrize("ignore", ["additionalContext", "updatedToolOutput"])
def test_simulation_only_shows_what_hooks_inject(tmp_path, ignore):
    """Recall and previews reach the model only through the hook outputs: drop one and the suite fails."""
    with pytest.raises(AssertionError):
        check_all(SdkHost(ignore=ignore), tmp_path)


# ---- focused tests -------------------------------------------------------------------------------------------
def base_input(sid: str = "s1") -> dict:
    return {"session_id": sid, "transcript_path": "/tmp/t.jsonl", "cwd": "/tmp"}


def run(coro):
    return asyncio.run(coro)


def test_hook_outputs_have_the_sdk_shape(tmp_path):
    mem = AgentMemory(tmp_path, window=40_000)
    mem.hooks.call_tool("write_note", {"name": "n", "content": "remember the widgets"})
    out = run(mem.on_user_prompt(UserPromptSubmitHookInput(**base_input(), hook_event_name="UserPromptSubmit",
                                                           prompt="go"), None, {"signal": None}))
    ctx = check_shape(out, "UserPromptSubmit")["hookSpecificOutput"]["additionalContext"]
    assert "<memory" in ctx and "remember the widgets" in ctx and not ctx.endswith("go"), "the prompt is not repeated"
    again = run(mem.on_user_prompt(UserPromptSubmitHookInput(**base_input(), hook_event_name="UserPromptSubmit",
                                                             prompt="next turn"), None, {"signal": None}))
    assert again == {}, "recall is injected once per session"
    long = run(mem.on_post_tool_use(PostToolUseHookInput(
        **base_input(), hook_event_name="PostToolUse", tool_name="mcp__work__fetch_report", tool_input={},
        tool_response=[{"type": "text", "text": REPORT}], tool_use_id="t1"), "t1", {"signal": None}))
    new = check_shape(long, "PostToolUse")["hookSpecificOutput"]["updatedToolOutput"]
    assert new[0]["type"] == "text" and "artifact://" in new[0]["text"] and "REPORT-TAIL" in new[0]["text"]
    short = run(mem.on_post_tool_use(PostToolUseHookInput(
        **base_input(), hook_event_name="PostToolUse", tool_name="Read", tool_input={},
        tool_response={"type": "text", "file": {"content": "x"}}, tool_use_id="t2"), "t2", {"signal": None}))
    assert short == {}, "built-in outputs of unknown shape are left alone"
    assert check_shape(run(mem.on_pre_compact(PreCompactHookInput(
        **base_input(), hook_event_name="PreCompact", trigger="auto", custom_instructions=None), None,
        {"signal": None})), "PreCompact") == {"systemMessage": HANDOFF}


def test_bash_output_is_previewed_in_its_own_schema(tmp_path):
    mem = AgentMemory(tmp_path, window=40_000)
    resp = {"stdout": REPORT, "stderr": "warn", "interrupted": False, "isImage": False, "extra": 1}
    out = run(mem.on_post_tool_use(PostToolUseHookInput(
        **base_input(), hook_event_name="PostToolUse", tool_name="Bash", tool_input={"command": "cat r"},
        tool_response=resp, tool_use_id="t"), "t", {"signal": None}))
    new = check_shape(out, "PostToolUse")["hookSpecificOutput"]["updatedToolOutput"]
    assert set(new) == {"stdout", "stderr", "interrupted", "isImage"} and new["stderr"] == "warn"
    assert "artifact://" in new["stdout"] and "row 1200:" not in new["stdout"]


def test_persisted_bash_output_is_read_whole(tmp_path):
    saved = tmp_path / "out.txt"
    saved.write_text(REPORT)
    mem = AgentMemory(tmp_path / "mem", window=40_000)
    resp = {"stdout": REPORT[:3000], "stderr": "", "interrupted": False, "persistedOutputPath": str(saved)}
    out = run(mem.on_post_tool_use(PostToolUseHookInput(
        **base_input(), hook_event_name="PostToolUse", tool_name="Bash", tool_input={"command": "x"},
        tool_response=resp, tool_use_id="t"), "t", {"signal": None}))
    stdout = out["hookSpecificOutput"]["updatedToolOutput"]["stdout"]
    assert "REPORT-TAIL" in stdout, "the tail is the real end of the output, not the end of Claude Code's cut"


def test_memory_tools_work_through_the_mcp_server(tmp_path):
    async def go():
        mem = AgentMemory(tmp_path, window=40_000)
        cli = SimulatedCLI(ClaudeAgentOptions(**mem.options()))
        try:
            assert (await cli.connect())["automem"] == ["write_note", "read_notes", "read_artifact"]
            saved = await cli.rpc("automem", "tools/call", {"name": "write_note", "arguments": {
                "name": "plan", "content": "ship on friday", "type": "decision"}})
            assert not saved["isError"] and "Saved note 'plan'" in saved["content"][0]["text"]
            read = await cli.rpc("automem", "tools/call", {"name": "read_notes", "arguments": {"name": "plan"}})
            assert "ship on friday" in read["content"][0]["text"]
            bad = await cli.rpc("automem", "tools/call", {"name": "read_artifact", "arguments": {"artifact_id": "x"}})
            assert bad["isError"] and bad["content"][0]["text"].startswith("Error:")
            invalid = await cli.rpc("automem", "tools/call", {"name": "write_note", "arguments": {"name": "n"}})
            assert invalid["isError"], "the SDK validates arguments against the memory tool's schema"
            # memory tools' own outputs are never previewed by the hook
            assert await cli.call_tool("mcp__automem__read_notes", {}) == [
                "[tool result mcp__automem__read_notes] " + mem.hooks.call_tool("read_notes", {})]
        finally:
            await cli.close()
        assert [n.type for n in JsonStore(tmp_path).load()] == ["decision"]
    run(go())


def test_autosave_on_stop(tmp_path):
    mem = AgentMemory(tmp_path, window=40_000)
    stop = StopHookInput(**base_input(), hook_event_name="Stop", stop_hook_active=False,
                         last_assistant_message="All 42 widgets counted and filed.")
    assert run(mem.on_stop(stop, None, {"signal": None})) == {}
    run(mem.on_stop({**stop, "stop_hook_active": True, "last_assistant_message": "a forced continuation"}, None,
                    {"signal": None}))
    results = [n for n in JsonStore(tmp_path).load() if n.source == "autosave"]
    assert [n.text for n in results] == ["All 42 widgets counted and filed."]


def test_notes_are_recalled_again_after_compaction(tmp_path):
    mem = AgentMemory(tmp_path, window=40_000)
    sid = base_input("s9")
    run(mem.on_user_prompt(UserPromptSubmitHookInput(**sid, hook_event_name="UserPromptSubmit", prompt="t"), None,
                           {"signal": None}))
    mem.hooks.call_tool("write_note", {"name": "progress", "content": "12 widgets so far"})
    post = PostToolUseHookInput(**sid, hook_event_name="PostToolUse", tool_name="mcp__work__lookup", tool_input={},
                                tool_response=[{"type": "text", "text": "ok"}], tool_use_id="t")
    assert run(mem.on_post_tool_use(post, "t", {"signal": None})) == {}
    run(mem.on_pre_compact(PreCompactHookInput(**sid, hook_event_name="PreCompact", trigger="auto",
                                               custom_instructions=None), None, {"signal": None}))
    after = check_shape(run(mem.on_post_tool_use(post, "t", {"signal": None})), "PostToolUse")
    assert "12 widgets so far" in after["hookSpecificOutput"]["additionalContext"]
    assert "updatedToolOutput" not in after["hookSpecificOutput"]
    assert run(mem.on_post_tool_use(post, "t", {"signal": None})) == {}, "recalled once per compaction"


def test_apply_merges_into_existing_options(tmp_path):
    async def mine(data, tool_use_id, context):
        return {}
    mem = AgentMemory(tmp_path, window=40_000)
    base = ClaudeAgentOptions(system_prompt="You count widgets.", allowed_tools=["Read"],
                              mcp_servers={"work": user_tools(None)},
                              hooks={"Stop": [HookMatcher(hooks=[mine])]})
    opts = mem.apply(base)
    assert opts.system_prompt.startswith("You count widgets.") and "<memory>" in opts.system_prompt
    assert set(opts.mcp_servers) == {"work", "automem"} and opts.allowed_tools[0] == "Read"
    assert "mcp__automem__write_note" in opts.allowed_tools
    assert len(opts.hooks["Stop"]) == 2 and opts.hooks["Stop"][0].hooks == [mine]
    assert base.hooks["Stop"] == [base.hooks["Stop"][0]] and base.allowed_tools == ["Read"], "base is unchanged"
    preset = mem.system_prompt({"type": "preset", "preset": "claude_code", "append": "Be brief."})
    assert preset["append"].startswith("Be brief.") and "write_note" in preset["append"]
    assert "write_note" in mem.system_prompt({"type": "custom", "prompt": "x"})["prompt"]
    with pytest.raises(TypeError):
        mem.system_prompt({"type": "file", "path": "p.md"})


def test_wrapped_tool_is_not_previewed_twice(tmp_path):
    async def go():
        mem = AgentMemory(tmp_path, window=40_000)
        cli = SimulatedCLI(mem.apply(ClaudeAgentOptions(mcp_servers={"work": user_tools(mem)})))
        try:
            await cli.connect()
            raw = await cli.rpc("work", "tools/call", {"name": "fetch_report", "arguments": {}})
            assert "artifact://" in raw["content"][0]["text"], "the wrapped tool returns the preview itself"
            calls = mem.hooks.stats["calls"]
            outs = await cli.fire("PostToolUse", PostToolUseHookInput(
                **cli.session, hook_event_name="PostToolUse", tool_name="mcp__work__fetch_report", tool_input={},
                tool_response=raw["content"], tool_use_id="t"), match="mcp__work__fetch_report")
            assert outs == [{}] and mem.hooks.stats["calls"] == calls
        finally:
            await cli.close()
    run(go())
