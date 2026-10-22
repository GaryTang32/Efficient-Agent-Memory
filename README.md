# Efficient-Agent-Memory

A test bench for agent memory and context-window techniques — taken from tier-1 papers by Chinese AI labs — for
agents that call LLMs through **Amazon Bedrock** (no self-hosted models). Goal: measure each technique on its own
(accuracy, tokens, $ with prompt caching on, latency), then combine the best into a reusable memory skill.

- `docs/literature_review.md` — verified list of papers (venue, lab, repo, licence, Bedrock fit) and the implementation shortlist.
- `docs/papers/` — deep-reading notes for individual papers.
- `eam/` — harness: Bedrock Converse client, offline mock backend with a prompt-cache simulator, cost meter, agent loop with technique hooks, scored sample tasks.
- `papers/` — local PDF copies (git-ignored).

Status: the harness works (offline mock; `python -m pytest`), the technique modules in `eam/techniques/` are
provisional and are being replaced by implementations that follow the official code/prompts listed in the review.

Quick start (offline):

```bash
python -m venv .venv && .venv/bin/pip install pytest boto3
.venv/bin/python -m pytest -q
.venv/bin/python -m eam.bench run --task needle_research -t full -t cache_layout --n 2
```

On Bedrock: copy `config/models.example.json` to `config/models.json`, fill in model ids and prices, then
`python -m eam.bench suite individual --backend bedrock --model sonnet --aux-model haiku`.
