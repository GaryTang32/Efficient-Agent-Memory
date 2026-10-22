# Backends: how a run reaches a model

Every bench run, smoke test and gateway call picks a **route** (`eam/llm/routes.py`).
You can work entirely without Bedrock through your **Claude Code CLI**, and switch to Bedrock later without changing anything else.

| Route | Use it when | Needs | Prompt caching |
|---|---|---|---|
| `claude-cli` | You have no Bedrock access; development and early experiments | A logged-in `claude` CLI | Automatic. Claude Code places the breakpoints, and our cache points are ignored. Append-only histories hit the cache. |
| `converse` | The main Bedrock route for experiments | AWS credentials, `pip install boto3` | Full control through Converse `cachePoint` (`cache_layout` technique) |
| `litellm` (option a) | Third-party repos that speak OpenAI and must reach *any* Bedrock model, or need embeddings | `pip install 'litellm[proxy]'`, AWS credentials, `scripts/start_litellm.sh` | `cache_control` markers, which LiteLLM translates into Bedrock cache points (messages only; tool caching not yet supported per a LiteLLM issue) |
| `mantle` (option b) | Bedrock-hosted open-weight and OpenAI models through AWS's own OpenAI-compatible endpoint | Bedrock API key in `AWS_BEARER_TOKEN_BEDROCK` | Depends on the model (documented explicitly for GPT-5.6) |
| `bedrock-openai` (option b) | Same, through `bedrock-runtime …/openai/v1` | Bedrock API key | Depends on the model |
| `gateway` | Calling this repo's gateway from the bench (mostly for tests) | `python -m eam.gateway` running | Whatever its backend provides |
| `mock` | Offline unit tests and mechanics checks | Nothing | Simulated |

## Running on your Claude Code CLI (no Bedrock)

```bash
python -m venv .venv && .venv/bin/pip install pytest
.venv/bin/python -m eam.smoke --route claude-cli --model cc-haiku            # chat, tools and cache check
.venv/bin/python -m eam.bench run --task needle_research -t full -t offload \
    --backend claude-cli --model cc-haiku --aux-model cc-haiku --n 1
```

How it works (`eam/llm/claude_cli.py`):
- Each LLM call is one `claude -p --input-format stream-json --output-format stream-json`.
- Claude Code's own tools, MCP servers and settings are switched off (`--tools "" --strict-mcp-config --setting-sources ""`).
- Our system prompt replaces Claude Code's (`--system-prompt`).
- The conversation is sent as one text block per message block, so Claude Code's automatic prompt cache hits across calls.
- Tools use a text protocol: `<tool_call>{"name": …, "arguments": …}</tool_call>`.
- Cost is the `total_cost_usd` that Claude Code reports, at list price.

Measured on 2026-10-22 with `cc-haiku`:
- Chat ✓ and tool round-trip ✓.
- Cache: a follow-up call read 15,901 of 16,759 prompt tokens from cache.
- Claude Code adds roughly 1.3K tokens of fixed overhead per call, which is the same for every technique.

Limitations of this route:
- There is no temperature or max-tokens control.
- Our explicit cache points have no effect, so the `cache_layout` technique can only be evaluated on Bedrock routes.
- Calls are sequential, and each one costs ≈1–2 s of CLI start-up time.

## Running third-party repos (MemoryOS, LightMem, …) without Bedrock

Start the gateway and point the repo's OpenAI settings at it:

```bash
scripts/start_gateway.sh                       # = python -m eam.gateway --chat claude-cli --embed hashing --port 4100
export OPENAI_BASE_URL=http://localhost:4100/v1 OPENAI_API_KEY=unused
```

- `/v1/chat/completions` is forwarded to the Claude Code CLI. Use the `--chat converse` flag to send it to Bedrock instead.
- `/v1/embeddings` is served locally:
  - `hashing`: zero-dependency and low quality, good for wiring tests.
  - `st:all-MiniLM-L6-v2`: needs `sentence-transformers` and runs on CPU.
  - `titan`: Bedrock.
- Every call's tokens and cost are logged to `results/gateway_calls.jsonl`, so experiments that use a repo's own code are metered too.

## Bedrock

1. **Native Converse.** Copy `config/models.example.json` to `config/models.json` and check the ids and prices. Then run `--backend converse --model sonnet --aux-model haiku`.
2. **LiteLLM (option a).**
   - Copy `config/litellm.example.yaml` to `config/litellm.yaml`, fill in the model ids, then run `scripts/start_litellm.sh`.
   - Repos: set `OPENAI_BASE_URL=http://localhost:4000/v1` and `OPENAI_API_KEY=$LITELLM_API_KEY`.
   - Bench: `--backend litellm`. The model name comes from each profile's `route_ids.litellm`.
3. **Bedrock OpenAI-compatible endpoints (option b).**
   - Set `AWS_BEARER_TOKEN_BEDROCK` to a Bedrock API key, then use `--backend mantle` (`https://bedrock-mantle.{region}.api.aws/v1`) or `--backend bedrock-openai` (`https://bedrock-runtime.{region}.amazonaws.com/openai/v1`).
   - Which models each endpoint serves, and whether it serves embeddings, has **not been verified yet**. Run `python -m eam.smoke --route mantle --model <profile>` and commit the row from `results/compat.jsonl` to the table below.

## Compatibility results

| Route | Model | Chat | Tools | Cache on follow-up | Embeddings | Date |
|---|---|---|---|---|---|---|
| claude-cli | haiku (Claude Code alias) | ✓ | ✓ (text protocol) | ✓ 15,901 read | n/a (use the gateway) | 2026-10-22 |
| converse | — | not yet run (no AWS credentials in this environment) | | | | |
| litellm | — | not yet run | | | | |
| mantle | — | not yet run | | | | |
| bedrock-openai | — | not yet run | | | | |
