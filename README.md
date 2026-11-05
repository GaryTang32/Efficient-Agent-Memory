# Efficient-Agent-Memory

A test bench for agent memory and context-window techniques — taken from tier-1 papers by Chinese AI labs — for
agents that call LLMs through **Amazon Bedrock** (no self-hosted models). Goal: measure each technique on its own
(accuracy, tokens, $ with prompt caching on, latency), then combine the best into a reusable memory skill.

- `docs/problem_statement.md` — **why this matters**: what agent memory and token optimisation mean for everyday coding agents (Codex, Claude Code), their users' pain points, and how each is addressed here.
- `docs/plans/2026-11-05-next-steps.md` — **plan and proposal**: more Sonnet seeds for `compact=sjc` (running), and a realistic coding benchmark on SWE-bench Verified (Django) workdays, with cost estimates (≈ $95–215 together).
- `docs/new_methods.md` — the eight methods from the 2026-11 scan (Strands, CADOC, ReFold, SJC, AKV, raw-history RAG, CORAL, SelfCompact): sources and deviations.
- `docs/literature/2026-11-scan/` — **literature scan, Sep–Nov 2026**: a sweep of 1,515 arXiv papers (40% of the most relevant have Chinese authors, 9% big US labs), plus the US labs, Chinese labs, repos and practitioners, and what it means for AutoMemory v2 and Bedrock.
- `docs/literature_review.md` — verified list of papers (venue, lab, repo, licence, Bedrock fit) and the implementation shortlist.
- `docs/papers/` — deep-reading notes for individual papers.
- `docs/methodology.md` — tasks, environment rules, metric definitions, procedure.
- `docs/automem.md` — **AutoMemory v1**, the combined memory skill: bench technique, framework-agnostic library (`eam/memory_skill.py`), MCP server (`python -m eam.mcp_server`).
- **Presets** (`eam/presets.py`): `automem_v2` (default; multi-session work that builds on earlier results), `automem_v2_strong` (strong agent models), `automem_v2_slim` (smallest working context), `automem_v2_lean` (independent tasks such as coding issues: no note workspace).
- `docs/backends.md` — how to run: Claude Code CLI (no Bedrock), Bedrock Converse, LiteLLM, Bedrock OpenAI-compatible endpoints, and a local gateway for third-party repos.
- `eam/` — harness: Bedrock Converse client, offline mock backend with a prompt-cache simulator, cost meter, agent loop with technique hooks, scored sample tasks.
- `papers/` — local PDF copies (git-ignored).

Status:
- Phase 1 (each method alone) has been measured on the Claude Code CLI route.
- Phase 2 (combinations, AutoMemory v1/v2, the 2026-11 methods, SWE-bench Verified workdays) has been measured too. Result reports, raw rows and logs are kept locally and are not part of the repository (`docs/results/`, `results/` are git-ignored).
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
