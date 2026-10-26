# Efficient-Agent-Memory

A test bench for agent memory and context-window techniques — taken from tier-1 papers by Chinese AI labs — for
agents that call LLMs through **Amazon Bedrock** (no self-hosted models). Goal: measure each technique on its own
(accuracy, tokens, $ with prompt caching on, latency), then combine the best into a reusable memory skill.

- `docs/literature_review.md` — verified list of papers (venue, lab, repo, licence, Bedrock fit) and the implementation shortlist.
- `docs/papers/` — deep-reading notes for individual papers.
- `docs/methodology.md` — tasks, environment rules, metric definitions, procedure.
- `docs/automem.md` — **AutoMemory v1**, the combined memory skill: bench technique, framework-agnostic library (`eam/memory_skill.py`), MCP server (`python -m eam.mcp_server`).
- `docs/results/` — measured results:
  - `2026-10-24-automem-evaluation.md` — **AutoMemory vs the published methods and the official memory systems (MemoryOS, LightMem, Nemori)** on four long tasks, Haiku and Sonnet. **Headline:**
    - AutoMemory and workspace + ReSum are the only methods that are model-robust on all four tasks.
    - With a Haiku summariser, AutoMemory solved 10/10 Sonnet runs (unlimited context: 8/10), at 19–122% of the unoptimised cost.
    - The official memory systems scored 0.2–0.5 lower than a plain note workspace.
  - `2026-10-24-bedrock-validation-plan.md` — Bedrock-ready experiments (blocked on credentials), plus a re-pricing at Bedrock cache rates.
  - `2026-10-22-ledger_audit-cross-model.md` — data larger than the window, three sessions, on Haiku/Sonnet/Opus. **Headline:** no single published method solves it; a persistent workspace plus ReSum resets solves 3/3 on Sonnet and Opus, and is the cheapest per success.
  - `2026-10-22-chain_hunt-cross-model.md` and `2026-10-22-chain_hunt-haiku-cli.md` — a long sequential trajectory.
- `docs/backends.md` — how to run: Claude Code CLI (no Bedrock), Bedrock Converse, LiteLLM, Bedrock OpenAI-compatible endpoints, and a local gateway for third-party repos.
- `eam/` — harness: Bedrock Converse client, offline mock backend with a prompt-cache simulator, cost meter, agent loop with technique hooks, scored sample tasks.
- `papers/` — local PDF copies (git-ignored).

Status:
- Phase 1 (each method alone) has been measured on the Claude Code CLI route.
- The first phase-2 combinations have been measured too (see `docs/results/`).
- Each technique carries a provenance label: official prompt/algorithm, ported, baseline, or provisional (`eam/techniques/__init__.py`).

Quick start with your Claude Code CLI (no Bedrock needed):

```bash
python -m venv .venv && .venv/bin/pip install pytest
.venv/bin/python -m eam.smoke --route claude-cli --model cc-haiku
.venv/bin/python -m eam.bench run --task needle_research -t full -t offload --backend claude-cli --model cc-haiku --aux-model cc-haiku --n 1
```

Quick start (offline):

```bash
python -m venv .venv && .venv/bin/pip install pytest boto3
.venv/bin/python -m pytest -q
.venv/bin/python -m eam.bench run --task needle_research -t full -t cache_layout --n 2
```

On Bedrock: copy `config/models.example.json` to `config/models.json`, fill in model ids and prices, then
`python -m eam.bench suite individual --backend converse --model sonnet --aux-model haiku`
(or `--backend litellm` / `mantle` / `bedrock-openai`; see `docs/backends.md`).
