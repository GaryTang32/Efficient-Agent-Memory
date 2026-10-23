# Bedrock validation: what is ready, what the re-pricing shows, what is blocked

**Date:** 2026-10-24.

**Status: blocked on credentials. No Bedrock call was made, and nothing in this document is a Bedrock measurement.**
The AWS keys present in this session's environment are rejected by STS and Bedrock ("The security token included in the request is invalid").

**To run the validation**, add working credentials in the environment settings (cloud environment menu → Edit) and start a new session. Either of these works:
- `AWS_BEARER_TOKEN_BEDROCK`;
- `AWS_ACCESS_KEY_ID` + `AWS_SECRET_ACCESS_KEY`, plus `AWS_SESSION_TOKEN` if the keys are temporary.

Also set `AWS_REGION`, and fill `config/models.json` (copy `config/models.example.json`) with your account's model ids and prices, including the Chinese-lab models you can use. Then:

```bash
AWS_REGION=us-east-1 scripts/run_bedrock_validation.sh 3
```

## 1. What was prepared and tested offline

| Piece | Where | Tested |
|---|---|---|
| Converse route with explicit `cachePoint`s (≤ 4: tools, system, two message points) | `eam/llm/bedrock.py`, `eam/llm/render.py` | unit tests and the prefix-cache simulator (`eam/llm/cache_sim.py`) |
| **Edit-boundary cache point.** Masking and AgentDiet publish how many leading messages they will never edit again; `cache_layout:edit_boundary=true` puts a cache point there, plus one at the end. | `eam/techniques/cache_layout.py`, `obs_mask.py`, `agentdiet.py` | `tests/test_auto_memory.py::test_edit_boundary_*`: renders exactly 4 cache points, the boundary point before the edited tail |
| Runbook | `scripts/run_bedrock_validation.sh` | syntax only (no account) |
| Chinese-lab model profiles (kimi, deepseek, qwen, glm) | `config/models.example.json` | placeholders: ids must be filled from your account |

### Why the edit boundary matters

With one breakpoint at the end of the conversation, which is all the Claude Code CLI places, every cached prefix still contains steps that masking or AgentDiet rewrite a moment later. So no cache entry survives the next edit, which matches the 2–20% hit rates measured on the CLI. A cache point at the boundary of the never-edited part keeps that part readable; only the tail after it is rewritten.

**Simulator** (mock model, 2 seeds, not Bedrock):
- AgentDiet on `chain_hunt`: hit rate 1% → 22%, agent cost −39%.
- AgentDiet on `needle_research`: hit rate 2% → 14%, agent cost −24%.
- Masking gains little (−5% on `chain_hunt`), because the prefix it keeps stable is already small: masked steps are placeholders.

The real test is step 1 of the runbook.

## 2. Re-pricing the recorded runs at Bedrock's cache multipliers

`python -m eam.bench.analyze --reprice <rows>` re-prices each run's own token counts with Bedrock-style multipliers:
- cache write 1.25× input (5-minute TTL);
- cache read 0.1×;
- output 5×.

The Claude Code CLI bills writes at 2× (1-hour TTL) and, for Sonnet, reads at 0.05×. The re-pricing keeps the CLI model's input price and the CLI's cache behaviour (one breakpoint at the end). It isolates the effect of the write price, not Bedrock's list prices or explicit cache points.

Sonnet rows (they are not affected by the harness bugs; see the 2026-10-23 erratum):

**`ops_stream` · Sonnet** (cost relative to `naive@native` under the same pricing)

| Method | Accuracy | CLI (2× write) | Bedrock multipliers (1.25× write) |
|---|---|---|---|
| `fs_workspace` | 0.99 | 72% | **54%** |
| `fs_workspace+resum` | 0.99 | 81% | **59%** |
| `resum` | 1.00 | 384% | 266% |
| `folding` | 0.20 | 309% | 227% |
| `obs_mask` | 0.38 | 1616% | 1050% |

**`research_corpus` · Sonnet**

| Method | Accuracy | CLI | Bedrock multipliers |
|---|---|---|---|
| `full@native` (cached long context) | 1.00 | **17%** | **17%** |
| Context-Folding | 1.00 | 20% | **16%** |
| ReSum | 1.00 | 22% | 17% |
| `fs_workspace+resum` | 1.00 | 31% | 24% |
| `obs_mask` | 1.00 | 37% | 24% |

**What changes at Bedrock-style prices:**
1. **The ranking does not change.**
   - The workspace methods stay the cheapest correct option across sessions.
   - Cached long context, Folding and ReSum stay the cheapest in one long session.
2. **History-editing methods become about one third cheaper relative to the baseline.** Masking goes from 37% to 24%, and ReSum on `ops_stream` from 384% to 266%. They are still dominated where something equally accurate is cheaper.
3. **Cached long context gains nothing.** Its cost is almost all cache reads, and the CLI's Sonnet read rate (0.05×) is lower than Bedrock's 0.1×.

Haiku rows are re-priced in `2026-10-24-automem-evaluation.md`, on the corrected harness.

## 3. What the Bedrock runs would decide

1. **Edit-boundary cache point:** does it turn masking or AgentDiet's token savings into cost savings on a real provider? This is the step the CLI cannot test.
2. **Bedrock prices and the 5-minute TTL:** do the long-task conclusions (§2) survive? In particular, does a long agent step that waits more than 5 minutes lose the cache?
3. **Chinese-lab models on Bedrock**, most without prompt caching: is the method ranking the same when every resent token is paid in full? Methods that bound the context (ReSum, masking, AutoMemory's guard) should gain relative to long context.
