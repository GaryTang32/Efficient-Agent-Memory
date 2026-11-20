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

## Large context windows and per-session settings

`window` is the context budget AutoMemory manages, not necessarily the model's maximum, and every threshold is a share
of it. On a 1M-token model, resetting at 75% means prompts of up to 750K tokens. Each call re-reads that whole cached
history, so the read cost per step grows with the reset point. Choose the reset point by cost:

```python
hooks = MemoryHooks(root, window=1_000_000, compact_at=400_000,   # reset at 400K, not 750K
                    preview_max_tokens=8_000,                      # outputs above 8K tokens enter as head + tail
                    recall_budget=0.02,                            # recalled notes: at most 20K tokens
                    summarize=cheap_llm)
```

These are equivalent ways to reset at 400K or 360K:
- `window=1_000_000, compact_at=400_000`, which resets at 400K;
- `window=1_000_000, trigger=0.4`, which also resets at 400K;
- `window=400_000, trigger=0.9`, which resets at 360K and also moves the guard to 90% of 400K.

**Per-session settings.** Settings given to `start_session(task, ...)`, or to `next_session(...)` before a session
begins, apply to that session only. A session that sets nothing gets the defaults the hooks were created with.
`next_session` works with every adapter, because the adapters start their sessions through these hooks:

```python
memory = AutoMemoryMiddleware(root, window=1_000_000, compact_at=500_000)   # the defaults
memory.hooks.next_session(compact_at=200_000, compaction="handoff")          # only the next run
agent.invoke(...)                     # this session resets at 200K
agent.invoke(...)                     # back to the defaults: 500K
```

| Setting | Default | For large windows |
|---|---|---|
| `window` | 200,000 | The model's window, or the budget you want to manage |
| `compact_at` / `trigger` | 0.75 × window | The reset point; lower is cheaper per step (see below) |
| `guard` | 0.9 | Share of the window one step may fill before outputs are moved out |
| `preview` / `preview_max_tokens` | 10% of the window / no cap | Cap it (for example 8,000): at 1M, 10% lets 100K-token outputs in whole |
| `recall_budget` | 0.1 | Lower it (for example 0.02): 10% of 1M is 100K tokens of notes |
| `compaction` | `resum` | `handoff` lets the agent write the recap as its own next turn, from the cache |
| `preview_tokens`, `handoff_variant` | 750, `general` | Size of a preview; `swe` for coding |

MCP server: `EAM_MEMORY_WINDOW`, `EAM_MEMORY_COMPACT_AT` and `EAM_MEMORY_PREVIEW_MAX_TOKENS`.

**What the reset point costs.** This is an estimate, not a measurement. The benchmark measured windows of 16–48K, and
nothing yet at 1M. It assumes a large-window model priced at $2 per million input tokens, cache reads at 0.05× and
writes at 1.25×, a reset that leaves about 20K tokens, and about 5K new tokens per step:

| Reset at | Average prompt | Cache reads per step | Steps between resets |
|---|---|---|---|
| 750K | ≈ 385K | ≈ $0.039 | ≈ 146 |
| 400K | ≈ 210K | ≈ $0.021 | ≈ 76 |
| 200K | ≈ 110K | ≈ $0.011 | ≈ 36 |

- **New tokens cost the same either way.** Writing each step's new tokens to the cache costs about $0.0125, whatever
  the reset point.
- **Reads.** Halving the reset point roughly halves the cache reads per step.
- **The reset itself.** A ReSum summary sends the whole history to the summariser as new, uncached text; a 400K
  history at $0.10–2 per million is $0.04–0.80 per reset. With `compaction="handoff"`, the agent writes the recap as
  its next turn, reading the history from the cache: about $0.04 at 400K, plus $0.01–0.02 for the recap's
  output tokens.
- **Accuracy.** What a lower reset point risks is accuracy, since each reset keeps a summary instead of the history.
  On this repository's coding tasks, a 16K window with resets at 12K resolved as many issues as the full window. Treat
  that as a hint for large windows, not a result.
- **Inside Claude Code or the Claude Agent SDK,** compaction is the host's own. Set its threshold there; AutoMemory
  only shapes what the summary keeps.

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
