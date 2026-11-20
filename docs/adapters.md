# AutoMemory adapters

AutoMemory works in the agent framework you already use. Each adapter wires the same rules into its host:

- recall of earlier sessions' notes
- note tools
- a preview of long tool outputs
- the in-step guard
- one reset when the window is 75% full
- an autosave of each session's answer

The core needs only the Python standard library. Each adapter imports its framework only when you use it.

```bash
pip install "efficient-agent-memory[langgraph]"        # or [anthropic], [claude-agent-sdk], [openai-agents]
pip install "efficient-agent-memory[adapters]"         # all of them, plus the MCP client used in the tests
```

> **Status:** every adapter passes the same offline conformance suite, driven by a fake model in each framework.
> The suite proves the wiring, not the savings. The savings were measured on this repo's bench
> ([automem_v2.md](automem_v2.md)). They have not been re-measured inside these frameworks with real models; that
> needs API keys (step 7 of the roadmap).

## Which one?

| You use | Adapter | Compaction by |
|---|---|---|
| The Claude API with your own loop | `eam.adapters.anthropic.MemoryMiddleware` | AutoMemory |
| Claude's memory tool (`memory_20250818`) | `eam.adapters.anthropic.NoteMemoryTool` | — |
| The Claude Agent SDK | `eam.adapters.claude_agent_sdk.AgentMemory` | Claude Code (AutoMemory adds the handoff instructions) |
| LangChain v1 agents / LangGraph | `eam.adapters.langgraph.AutoMemoryMiddleware` | AutoMemory |
| The OpenAI Agents SDK | `eam.adapters.openai_agents.OpenAIAgentsMemory` | AutoMemory |
| Claude Code | the plugin, `claude --plugin-dir plugins/automem` | Claude Code |
| Any MCP client | `automem-mcp` (or `python -m eam.mcp_server`) | the client |
| Anything else | `eam.adapters.MemoryHooks` (below) | AutoMemory |

Every adapter takes the same options as the library: a memory directory, `window` (your model's context window),
and `summarize` (any cheap LLM call, used for the rare reset). Notes from one adapter are readable from any other,
because they share the same store.

## Claude API

```python
import anthropic
from eam.adapters.anthropic import MemoryMiddleware

client = anthropic.Anthropic()
mem = MemoryMiddleware("~/.eam-memory/project-x", window=200_000, summarize=cheap_llm)
params = mem.start(task, system="You are a careful analyst.", tools=my_tools)
while True:
    response = client.messages.create(model=MODEL, max_tokens=16000, **params)
    if not mem.step(response, params["messages"], run_tool):   # run_tool(name, input) -> str
        break
```

`step` does the following on each response:
- It records the prompt size from `usage`: input, cache-read and cache-write tokens.
- It runs the tool calls: memory tools in process, yours through `run_tool`, with previews of long outputs.
- Once the window is 75% full, it resets the history to one user message.
- On the final answer, it autosaves.

Pass `memory_tool=True` to also offer Claude's own memory tool, backed by the same notes.

`NoteMemoryTool` on its own is storage for Claude's memory tool, and works in the SDK's tool runner:

```python
runner = client.beta.messages.tool_runner(model=MODEL, max_tokens=16000, tools=[NoteMemoryTool(root)], messages=...)
```

- **Files:** each file under `/memories` is a note, so what Claude saves there is recalled in later sessions.
- **Path checks:** paths outside `/memories`, or with `..` in them, are refused.
- **Writes:** contents are redacted, and each write is one transaction.
- **Views:** file views come back marked as data.

## Claude Agent SDK

```python
from claude_agent_sdk import ClaudeAgentOptions, query
from eam.adapters.claude_agent_sdk import AgentMemory

mem = AgentMemory("~/.eam-memory/project-x")
options = mem.apply(ClaudeAgentOptions())
async for message in query(prompt="Count the widgets for day 2.", options=options):
    mem.observe(message)            # optional: real prompt sizes for the in-step guard
```

What `apply` adds:
- **Memory tools:** an in-process MCP server.
- **Recall:** at a session's first prompt, through `UserPromptSubmit` (the Python SDK has no `SessionStart`
  hook).
- **Previews:** through `PostToolUse` `updatedToolOutput`, for MCP tools, plain-text outputs and Bash.
- **Autosave:** on `Stop`.
- **Handoff instructions:** for Claude Code's own compaction, through `PreCompact`.
- **Rules:** appended to Claude Code's system prompt.

Claude Code compacts on its own here. As with the plugin, expect little change inside Claude Code: it already
caches, compacts and saves long outputs ([automem_v2.md](automem_v2.md#2-in-claude-code-plugin)).

## LangChain v1 agents and LangGraph

```python
from langchain.agents import create_agent
from eam.adapters.langgraph import AutoMemoryMiddleware

memory = AutoMemoryMiddleware("~/.eam-memory/project-x", window=200_000, summarize=cheap_llm)
agent = create_agent(model, tools=[search, run_tests], system_prompt="You fix bugs.", middleware=[memory])
agent.invoke({"messages": [{"role": "user", "content": "Fix the failing test."}]})
```

- **Sessions:** one invocation is one session.
- **Compaction:** one state update that removes every message (`RemoveMessage(REMOVE_ALL_MESSAGES)`) and adds the
  reset, so no tool call is left without its result.
- **Prompt size:** read from `AIMessage.usage_metadata`.
- **Hand-built graphs:** `memory_tools(hooks)`, `prompt_tokens(ai_message)` and `compact_update(hooks, messages)`
  cover a graph you build yourself.

## OpenAI Agents SDK

```python
from agents import Agent, Runner
from eam.adapters.openai_agents import OpenAIAgentsMemory

mem = OpenAIAgentsMemory("~/.eam-memory/project-x", window=200_000, summarize=cheap_llm)
agent = Agent(name="assistant", instructions="You count widgets.", tools=mem.tools(fetch_report, lookup))
result = await Runner.run(agent, "Count the widgets.", hooks=mem.run_hooks(), run_config=mem.run_config())
```

- **`call_model_input_filter`:** adds the rules and the recall, and applies the reset.
- **`RunHooks`:** record the prompt size and autosave.
- **Wrapped tools:** previews of long outputs.

Compaction needs the client to send the history, so it does not apply with `previous_response_id` or
`conversation_id`.

The SDK's `Session` replays the whole transcript on every run, which is the opposite of slim context. Use
AutoMemory's notes for what should carry over between runs.

## Your own loop: MemoryHooks

```python
from eam.adapters import MemoryHooks

hooks = MemoryHooks("~/.eam-memory/project-x", window=200_000, summarize=cheap_llm)
system = hooks.system_text(base_system)
messages = [{"role": "system", "content": system}, {"role": "user", "content": hooks.start_session(task)}]
tools = my_tools + hooks.tool_specs()
while True:
    reply = llm(messages, tools)
    hooks.after_call(reply.prompt_tokens, reply.text)          # real prompt size from the provider's usage
    if reply.is_final:
        hooks.end_session(reply.text)
        break
    for call in reply.tool_calls:
        out = (hooks.call_tool(call.name, call.args) if hooks.is_memory_tool(call.name)
               else hooks.on_tool_result(call.name, run(call)))
        messages.append(tool_message(call, out))
    messages = hooks.compact(messages)                          # unchanged until the window is 75% full
```

## Writing a new adapter

Build it on `MemoryHooks`, then pass the conformance suite in
[`tests/adapters/conformance.py`](../tests/adapters/conformance.py). Your test supplies a driver: the framework's
agent around a fake model that follows a script. The suite checks:

1. **Recall:** a note from session 1 is in session 2's first model input, inside a `<memory>` block.
2. **Rules:** the system text carries the note rules and the rule that `<memory>` content is data.
3. **Preview:** a long tool output reaches the model as head and tail, and `read_artifact` returns the full text.
4. **Redaction:** a secret in a tool output is stored redacted.
5. **Autosave:** each session's answer is saved, and only the newest one is recalled.
6. **Compaction:** past 75% of the window, the next model input is the task, the summary and the notes.
7. **Overhead:** the hooks cost under 5 ms per call.

The reference driver is [`tests/adapters/test_hooks_conformance.py`](../tests/adapters/test_hooks_conformance.py).
It also shows that the suite fails when a hook is skipped. Run every adapter's tests with:

```bash
pip install -e ".[adapters,dev]" && python -m pytest -q tests/adapters
```
