# AutoMemory plugin for Claude Code

The memory rules that measured best in this repository, as Claude Code hooks. Everything runs in the harness, with
no extra model calls, and nothing rewrites history that is already in the prompt cache.

| Hook | What it does | Evidence in this repository |
|---|---|---|
| `PostToolUse` (Bash) | Output longer than 6,000 characters per stream reaches the model as head + tail (1,500 characters each); the full text is saved to a file the model can `Read` or `Grep` | Previews at ingestion: Haiku solved 11/16 long-task runs vs 7/16 at the same cost |
| `PreCompact` | Compaction keeps NVIDIA's handoff recap: objective, facts, applied changes, checks, dead ends, next step | At a 16K window: 81 vs 76 (Haiku) and 88 vs 86 (Sonnet) of 100 SWE-bench issues against a generic summary |
| `SessionStart` | Recalls this project's notes (earlier sessions' final messages); runs again after compaction | Recall was essential for multi-session work (Haiku 0.34 without it vs 0.99 for Sonnet) |
| `Stop` | Saves the turn's final message as a project note | Autosave of each session's result |

A skill (`automem`) tells the model how to use previews and notes, and `/automem:handoff` writes a recap on demand.

## Install

From a clone of this repository:

```bash
claude --plugin-dir plugins/automem          # one session
```

or add the repository as a plugin marketplace in Claude Code and install `automem` from it.

## Settings

| Variable | Default | Meaning |
|---|---|---|
| `AUTOMEM_PREVIEW_CHARS` | `6000` | Preview threshold per output stream, in characters; `0` turns previews off |
| `AUTOMEM_PREVIEW_KEEP` | `1500` | Characters kept at the head and at the tail |
| `AUTOMEM_PREVIEW_TOKENS` | — | The preview threshold in tokens (about 4 characters each); overrides `AUTOMEM_PREVIEW_CHARS` |
| `AUTOMEM_PREVIEW_SHARE` | — | The threshold as a share of Claude Code's compaction window (`CLAUDE_CODE_AUTO_COMPACT_WINDOW`, or `AUTOMEM_WINDOW`), e.g. `0.02` of 500,000 = 10,000 tokens |
| `AUTOMEM_PREVIEW_MAX_TOKENS` | `16000` | Caps the threshold that `AUTOMEM_PREVIEW_SHARE` gives (`0`: no cap) |
| `AUTOMEM_PREVIEW_KEEP_TOKENS` | — | Head and tail size in tokens; overrides `AUTOMEM_PREVIEW_KEEP` |
| `AUTOMEM_NOTES` | `on` | `off` disables recall and autosave (independent tasks such as one issue per session gain nothing from notes) |
| `AUTOMEM_RECALL_CHARS` | `3000` | Most recent notes recalled at session start |
| `AUTOMEM_RECALL_TOKENS` | — | The same in tokens; overrides `AUTOMEM_RECALL_CHARS` |
| `AUTOMEM_DATA` | `$CLAUDE_PLUGIN_DATA` | Where notes and saved outputs live, one folder per project (git top level) |
| `AUTOMEM_REDACT` | `on` | Replace secrets with `[REDACTED:kind]` before saving outputs and notes |
| `AUTOMEM_RETENTION_DAYS` | `14` | Saved outputs older than this are deleted; `0` keeps them |
| `AUTOMEM_OUTPUT_MB` | `200` | Saved outputs per project are kept under this size, oldest deleted first |

Saved files are owner-only and written atomically. Recalled notes reach the model as a `<memory>` block marked as
data, never as instructions. See [SECURITY.md](../../SECURITY.md).

Set them in your shell or in the `env` block of Claude Code's `settings.json`. Hooks inherit Claude Code's environment.

Claude Code compacts only near the model's context limit by default. For long sessions you can compact earlier with
`CLAUDE_CODE_AUTO_COMPACT_WINDOW` (Claude Code's own setting); the handoff recap then applies sooner. On a 1M-token
model with compaction at 500K, for example:

```json
{"env": {"CLAUDE_CODE_AUTO_COMPACT_WINDOW": "500000",
         "AUTOMEM_PREVIEW_SHARE": "0.02", "AUTOMEM_PREVIEW_MAX_TOKENS": "16000", "AUTOMEM_RECALL_TOKENS": "4000"}}
```

With that, Bash outputs above 10,000 tokens reach the model as head and tail. Claude Code itself cuts a Bash output
at about 30,000 characters and saves the rest. The plugin then shows the head and the real tail from that saved copy,
whatever the threshold.

## Measured inside Claude Code

See the pilot in the main README: headless Claude Code on SWE-bench Verified Django issues, with and without this
plugin, on the same issues.
