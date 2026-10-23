# AutoMemory v1: a memory skill for agent loops

AutoMemory combines the methods that held up in this project's measurements, and fixes the failure modes they showed:
- `docs/results/2026-10-22-ledger_audit-cross-model.md`
- `docs/results/2026-10-23-long-horizon-cross-model.md`

It comes in three forms with the same rules:

| Form | Use it when | Entry point |
|---|---|---|
| Bench technique | measuring it in this repo's agent loop | spec `automem` (`eam/techniques/auto_memory.py`) |
| Library | your own agent loop (any framework, OpenAI-style messages) | `eam.memory_skill.MemorySkill` |
| MCP server | an MCP client (Claude Code, Strands, LangGraph MCP adapters, …) | `python -m eam.mcp_server` |

## Components and the evidence for each

Every component has a switch, so it can be ablated.

| Component | Switch (bench spec) | What it does | Why (measured) |
|---|---|---|---|
| Persistent workspace | `workspace=` | `write_note` / `read_notes`, kept across sessions | Only the workspace (with compaction) was model-robust on multi-session tasks. FS-Researcher, ACL'26. |
| Recall | `recall=` | Notes are put into the first message of every session, and after every compaction | Haiku re-read old files instead of its notes: 0.34 vs Sonnet 0.99 |
| Autosave | `autosave=` | Each session's final answer is saved as a note, with no LLM call | Later sessions most often need an earlier session's result |
| In-step guard | `guard=0.9` (0 = off) | While a step's tool outputs arrive, any output that would push the next prompt past 0.9 × window goes to the artifact store; a pointer stays | ReSum checks only between calls. One Haiku step of parallel calls added 13–18K tokens and overflowed whatever the trigger margin. |
| Compaction | `compact=resum\|mask\|none`, `trigger=0.75` | ReSum's official summary prompt at 0.75 × window; until then the context is kept whole | Rare resets keep the prompt cache alive. Cached full context is cheapest while it fits (17–27% of uncached cost). |
| Cheaper summariser | `--aux-model` | The summary runs on the auxiliary model | Summary calls were ~40% of the recipe's cost on Sonnet |

Cache-awareness is a design rule, not a switch. Edits happen only at ingestion (guard, offload) or at rare resets (compaction, recall). Nothing rewrites earlier history every step, because on the Claude Code route each rewrite is billed as a cache write at 2× the input price.

## Bench

```bash
python -m eam.bench run --task ops_stream -t automem -t "automem:guard=0" -t "automem:recall=false" \
    --backend claude-cli --model cc-sonnet --aux-model cc-haiku --n 2
```

## Library

```python
from eam.memory_skill import MemorySkill

skill = MemorySkill("~/.eam-memory/my-project", window=200_000, summarize=lambda prompt: cheap_llm(prompt))
system = BASE_SYSTEM + "\n\n" + skill.system_addendum()
messages = [{"role": "system", "content": system},
            {"role": "user", "content": skill.session_preamble() + task}]
tools = my_tools + skill.tool_specs()          # write_note, read_notes, read_artifact → skill.call_tool(...)

while True:
    reply, usage = llm(messages, tools)        # usage.prompt_tokens: the real size of this prompt
    if done(reply):
        skill.save_session(reply.text)
        break
    skill.start_step(usage.prompt_tokens, reply.text)
    for call in reply.tool_calls:
        out = skill.call_tool(call.name, call.args) if call.name in {"write_note", "read_notes", "read_artifact"} \
            else run_tool(call)
        messages.append(tool_message(call, skill.ingest_tool_output(call.name, out)))   # in-step guard
    predicted = skill.end_step()
    messages = skill.maybe_compact(messages, context_tokens=predicted, question=task)  # rare reset
```

## MCP server

Add it to `.mcp.json` (Claude Code) or to your client's MCP configuration:

```json
{"mcpServers": {"automem": {"command": "python", "args": ["-m", "eam.mcp_server"],
                            "env": {"EAM_MEMORY_DIR": "/path/to/project-memory", "EAM_MEMORY_WINDOW": "200000"}}}}
```

**Tools:**

| Tool | Purpose |
|---|---|
| `recall` | call first in each session |
| `write_note`, `read_notes` | persistent notes |
| `save_session` | autosave a session's result |
| `offload`, `read_artifact` | keep large text out of the context and page it back |
| `context_budget` | whether to compact now, and how much the next step may add |
| `compact` | ReSum's summary prompt for your model; or a ready reset message, if `EAM_MEMORY_ROUTE` (e.g. `claude-cli`) and `EAM_MEMORY_MODEL` (e.g. `cc-haiku`) are set |

An MCP server cannot rewrite its client's context. The client applies the reset, or uses its own compaction, and keeps the rest.
