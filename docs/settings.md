# Settings reference

AutoMemory has **59 settings** in four places. None is hard-coded: each has a default, and each can be set by the
user. The ranges are wide on purpose. They refuse values that cannot work, such as a reset after the window is full
or a negative size, not values that are merely unmeasured. The library refuses an out-of-range value with an error
naming the accepted range. The Claude Code plugin falls back to the default instead, because a hook must never break
a session.

| Where | Settings | How you set them |
|---|---|---|
| [Library and adapters](#library-and-adapters) (`MemorySkill`, `MemoryHooks`, every adapter) | 16 | Keyword arguments; per session with `start_session(task, ...)` or `next_session(...)` |
| [MCP server](#mcp-server) (`automem-mcp`) | 8 | Environment variables |
| [Claude Code plugin](#claude-code-plugin) | 18 | Environment variables, in your shell or the `env` block of Claude Code's `settings.json` |
| [Bench technique](#bench-technique-research) (`automem:...` specs) | 17 | Spec options, for research runs on the bench |

**Measured or chosen.**
- **Measured:** the default was tested against an alternative on the bench (results: [results.md](results.md)).
- **Chosen:** a design or safety choice that was not swept.
- **What was compared directly:**
  - previews on (10%) against off;
  - the guard on (90%) against off;
  - a reset at 75% against none;
  - two steps kept after a reset against none;
  - ReSum against NVIDIA's handoff recap.
- **Everything else:** no other threshold was swept, so the ranges below are limits, not tuned optima.

## Library and adapters

These settings apply to `MemorySkill(root, **settings)`, `MemoryHooks(root, **settings)` and every adapter
(`MemoryMiddleware`, `AgentMemory`, `AutoMemoryMiddleware`, `OpenAIAgentsMemory`). The source of truth is
[`eam/automem/settings.py`](../eam/automem/settings.py). Shares are of `window`.

| Setting | Default | Accepted range | Unit | Where the default comes from |
|---|---|---|---|---|
| `window` | 200,000 | 1,000 – 10,000,000 | tokens | Chosen: your model's context window, or the budget you manage. Every share below is of it |
| `trigger` | 0.75 | 0.05 – 1 | share of window | Measured: one reset at 75% kept accuracy on four long tasks and SWE-bench (12K of a 16K window); with no reset, scores were 0.04–0.62. Other values not swept |
| `compact_at` | — | 1,000 – the window | tokens | Chosen: the reset point in tokens, the same as `trigger` × `window` |
| `guard` | 0.9 | 0.1 – 1, or `0` = off | share of window | Measured against off: removed the overflows of parallel tool calls |
| `preview` | 0.1 | 0.005 – 0.5, or `0` = off | share of window | Measured against off: Haiku solved 11 of 16 runs instead of 7 at the same cost; without previews, NVIDIA's recap alone lost 5 of 100 Django issues |
| `preview_tokens` | 750 | 50 – 20,000 | tokens | Chosen: Strands' head and tail size, used in every measured run |
| `preview_max_tokens` | 16,000 | 500 – 1,000,000, or `0` = no cap | tokens | Chosen: caps the preview threshold above a 160K window. Not measured: no measured window reached it |
| `recall_budget` | 0.1 | 0.001 – 0.5 | share of window | Measured: with newest-answer recall, 10% kept every needed fact on a ten-day job (the cap alone dropped 5 of 258) |
| `compaction` | `resum` | `resum` / `handoff` | — | Measured: ReSum and NVIDIA's handoff recap were level over three Django runs |
| `handoff_variant` | `general` | `general` / `swe` / `brief` | — | Chosen: the paper's prompts; `brief` was level in cost and accuracy |
| `token_ratio` | 1.5 | 1 – 3 | real tokens per estimated token | Chosen: conservative for dense text, so the guard errs on the safe side |
| `max_note_chars` | 20,000 | 100 – 1,000,000 | characters | Chosen: one note stays small next to the recall budget |
| `retention_days` | 14 | 0.01 – 3,650, or `0` = keep | days | Chosen (security): saved outputs do not pile up |
| `max_artifact_mb` | 200 | 0.001 – 100,000 | MB | Chosen (security): size limit for one project's saved outputs |
| `max_artifact_chars` | 10,000,000 | 1,000 – 1,000,000,000 | characters | Chosen (security): one saved output is cut beyond this |
| `wrap` | `True` | `True` / `False` | — | Measured: 0 of 20 planted instructions obeyed with wrapping, 4 of 20 without |

**Settings a session can change on its own:**
- `window`;
- `trigger` or `compact_at`;
- `guard`;
- `preview`, `preview_tokens` and `preview_max_tokens`;
- `recall_budget`;
- `compaction` and `handoff_variant`.

```python
hooks = MemoryHooks(root, window=1_000_000, compact_at=500_000)     # the defaults
hooks.start_session(task, compact_at=200_000)                        # this session only
hooks.next_session(preview_max_tokens=8_000)                         # the next session, for adapters
```

A session that sets nothing gets the defaults again.

**Wiring, not settings:**
- `root` or `store`: where the notes live;
- `summarize`: the LLM call for the reset.

### Suggested values

| Your setup | `window` | Reset | `preview` / `preview_max_tokens` | `recall_budget` |
|---|---|---|---|---|
| Up to a 200K window (as measured) | the model's window | `trigger=0.75` | 0.1 / 16,000 | 0.1 |
| A 1M model, managed as 500K | 1,000,000 | `compact_at=500_000` | 0.1 / 16,000 (the cap applies) | 0.02 |
| A 1M model, cost first | 1,000,000 | `compact_at=200_000` to `400_000` | 0.1 / 8,000–16,000 | 0.02 |
| A small window (16–48K) | the model's window | `trigger=0.75` | 0.1 / 16,000 (the cap never binds) | 0.1 |

At 1M, the reset point decides most of the cost, because each call re-reads the whole cached history. For an
estimate, see [adapters.md](adapters.md#large-context-windows-and-per-session-settings).

## MCP server

| Variable | Default | Accepted range | Meaning |
|---|---|---|---|
| `EAM_MEMORY_DIR` | `~/.eam-memory/default` | a directory | Where the notes and saved outputs live |
| `EAM_MEMORY_WINDOW` | 200,000 | 1,000 – 10,000,000 | `window` |
| `EAM_MEMORY_COMPACT_AT` | unset (75% of the window) | 1,000 – the window | `compact_at`, as reported by `context_budget` |
| `EAM_MEMORY_PREVIEW_MAX_TOKENS` | 16,000 | 500 – 1,000,000, or `0` = no cap | `preview_max_tokens` |
| `EAM_MEMORY_ROUTE` | unset | a bench route, e.g. `claude-cli` | When set, the `compact` tool runs the summary itself |
| `EAM_MEMORY_MODEL` | `cc-haiku` | a model key in the models config | The model for that summary |
| `EAM_MODELS_CONFIG` | `config/models.json` | a path | Where model keys are defined |
| `EAM_MEMORY_TOOLS` | all tools | comma-separated tool names | List only these tools, e.g. `write_note,read_notes,read_artifact`, so clients that allow only the note tools don't carry the other schemas |

In the MCP server, the other library settings keep their defaults.

## Claude Code plugin

The plugin cannot import the package, so it has its own settings and checks its own ranges. An out-of-range value
falls back to the default. Claude Code's own `CLAUDE_CODE_AUTO_COMPACT_WINDOW` decides when it compacts, and
`AUTOMEM_PREVIEW_SHARE` can follow it.

| Variable | Default | Accepted range | Where the default comes from |
|---|---|---|---|
| `AUTOMEM_PREVIEW_CHARS` | 6,000 | 500 – 2,000,000, or `0` = previews off | Measured in the pilots: neutral inside Claude Code (same accuracy, cost within ±10%) |
| `AUTOMEM_PREVIEW_KEEP` | 1,500 | 100 – 200,000 | The same pilots: a head and tail of 1,500 characters each |
| `AUTOMEM_PREVIEW_TOKENS` | unset | 125 – 500,000, or `0` = off | The threshold in tokens (× 4 characters); overrides `AUTOMEM_PREVIEW_CHARS` |
| `AUTOMEM_PREVIEW_SHARE` | unset | 0.001 – 0.5 | The threshold as a share of `CLAUDE_CODE_AUTO_COMPACT_WINDOW` (or `AUTOMEM_WINDOW`) |
| `AUTOMEM_PREVIEW_MAX_TOKENS` | 16,000 | 500 – 1,000,000, or `0` = no cap | Caps the threshold that `AUTOMEM_PREVIEW_SHARE` gives |
| `AUTOMEM_PREVIEW_KEEP_TOKENS` | unset | 25 – 50,000 | The head and tail in tokens; overrides `AUTOMEM_PREVIEW_KEEP` |
| `AUTOMEM_WINDOW` | unset | 1,000 – 10,000,000 | The window for `AUTOMEM_PREVIEW_SHARE` when Claude Code's is not set |
| `AUTOMEM_NOTES` | `on` | `on` / `off` | Recall and autosave; `off` for independent tasks, where notes are overhead |
| `AUTOMEM_RECALL_CHARS` | 3,000 | 100 – 200,000, or `0` = no recall | Measured: raising it to 4,000 tokens cost Sonnet 12–19% more with no gain, because Claude Code recalls again on every resumed turn |
| `AUTOMEM_RECALL_TOKENS` | unset | 25 – 50,000, or `0` = no recall | The same in tokens; overrides `AUTOMEM_RECALL_CHARS` |
| `AUTOMEM_DATA` | `$CLAUDE_PLUGIN_DATA`, else `~/.automem` | a directory | Where state lives, one folder per project |
| `AUTOMEM_RETENTION_DAYS` | 14 | 1 – 3,650, or `0` = keep | Chosen (security) |
| `AUTOMEM_OUTPUT_MB` | 200 | 1 – 100,000 | Chosen (security) |
| `AUTOMEM_REDACT` | `on` | `on` / `off` | Chosen (security): secrets are replaced before anything is saved |
| `AUTOMEM_WORKSPACE` | `off` | `on` / `off` | Full AutoMemory v2 mode: the note rule, recall of the shared note store at session start (skipped on resume), autosave into it. Pair with the `automem-mcp` server for the note tools |
| `AUTOMEM_STORE` | this project's folder `/store` | a directory | The shared note store; give the MCP server the same directory as `EAM_MEMORY_DIR` |
| `AUTOMEM_FULL_RECALL_CHARS` | 12,000 | 500 – 400,000 | Chosen: the recall budget in full mode (about 3,000 tokens), newest notes first, the rest listed by name |
| `AUTOMEM_TIMING_LOG` | unset | a file | One JSON line per hook call: event, milliseconds, what it did |

**Precedence for the preview threshold:**
1. `AUTOMEM_PREVIEW_TOKENS`;
2. then `AUTOMEM_PREVIEW_SHARE`, capped by `AUTOMEM_PREVIEW_MAX_TOKENS`;
3. then `AUTOMEM_PREVIEW_CHARS`.

For a 1M model compacting at 500K:

```json
{"env": {"CLAUDE_CODE_AUTO_COMPACT_WINDOW": "500000", "AUTOMEM_PREVIEW_SHARE": "0.02",
         "AUTOMEM_PREVIEW_MAX_TOKENS": "16000"}}
```

Keep the recall size at its default unless sessions need more. Claude Code runs the session-start hook again on
every resumed turn, so a larger recall is re-sent each time. In the settings check, 4,000 tokens of recall (against
the default 3,000 characters) cost Sonnet 12–19% more, with no gain in issues fixed.

## Bench technique (research)

For research runs, `-t "automem:..."` exposes the same rules, plus switches for ablations. These options are not
range-checked, since the bench is meant for experiments.

| Option | Default | Values tested | Meaning |
|---|---|---|---|
| `workspace` | `true` | `true`, `false` (lean), `adaptive` | Note tools and recall |
| `recall` | `true` | `true`, `false` | Recall at session start |
| `autosave` | `true` | `true` | Save each session's answer |
| `ingest` | `0` (presets: 0.1) | 0, 0.1 | `preview` |
| `ingest_preview` | 750 | 750 | `preview_tokens` |
| `guard` | 0.9 | 0, 0.9 | `guard` |
| `compact` | `resum` | `resum`, `handoff`, `handoff_aux`, `sjc`, `openclaw`, `openclaw+sjc`, `mask`, `none` | The compactor |
| `trigger` | 0.75 | 0.75 | `trigger` |
| `keep_recent` | 2 | 0, 2 | Complete steps kept after a reset |
| `handoff_variant` | `general` | `general`, `swe`, `brief` | `handoff_variant` |
| `fold` | `false` | `false`, `true` (slim) | ReFold's de-duplication and folding |
| `wrap` | `false` (library: `true`) | `false`, `true` | `wrap` |
| `recall_results` | `all` (presets: `latest`) | `all`, `latest` | Recall only the newest autosaved answer |
| `note_ids` | `false` | `false`, `true` | Ask for ids with the values noted |
| `verify` | `false` | `false`, `true` | Send a final answer back once while tests still fail |
| `default_window` | 200,000 | — | The window when the task gives none |
| `token_ratio` | 1.5 | 1.5 | `token_ratio` |
