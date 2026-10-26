# Running the official memory systems (MemoryOS, LightMem, Nemori)

They are used through their own packages, in a separate virtualenv (`.venv-memory`, git-ignored), by the sidecar `scripts/memory_sidecar.py`; the bench technique is `ext_memory:backend=…` (`eam/techniques/ext_memory.py`). Their LLM calls go to a private `eam.gateway` (Claude Code CLI) that each run starts on a free port.

Verified setup (2026-10-24):
- Python 3.13, CPU only.
- 1.6 GB virtualenv, plus 0.8 GB of Hugging Face models: LLMLingua-2 and all-MiniLM-L6-v2.

## Install

```bash
V=.venv-memory/bin
python3 -m venv .venv-memory && $V/pip install -U pip
$V/pip install torch --index-url https://download.pytorch.org/whl/cpu
$V/pip install faiss-cpu sentence-transformers openai python-dotenv regex flask
$V/pip download memoryos-pro --no-deps -d /tmp/pkgs && $V/pip install --no-deps /tmp/pkgs/memoryos_pro-0.1.0-py3-none-any.whl
$V/pip install llmlingua qdrant-client tiktoken accelerate nltk rank-bm25 httpx pillow distro pysocks
git clone --depth 1 https://github.com/zjunlp/LightMem /tmp/src/LightMem      # tested at 8449d57
$V/pip install --no-deps --ignore-requires-python /tmp/src/LightMem
git clone --depth 1 https://github.com/nemori-ai/nemori /tmp/src/nemori       # tested at d2a6dff (v0.2.0)
$V/pip install asyncpg && $V/pip install --no-deps /tmp/src/nemori
```

MemoryOS and LightMem pin old dependencies: numpy 1.24, faiss-gpu, and Python < 3.12 for LightMem. They are installed `--no-deps`; nothing that was exercised needed the pinned versions.

**Nemori needs Postgres** with `pg_trgm`. The sidecar connects to `EAM_NEMORI_DSN`, default `postgresql://nemori:nemori@127.0.0.1:55432/nemori`. A throwaway local cluster:

```bash
mkdir -p /tmp/nemori-pg && chown postgres:postgres /tmp/nemori-pg && chmod 700 /tmp/nemori-pg
su postgres -c "/usr/lib/postgresql/16/bin/initdb -D /tmp/nemori-pg/data -A trust -U postgres"
su postgres -c "/usr/lib/postgresql/16/bin/pg_ctl -D /tmp/nemori-pg/data -o '-p 55432 -k /tmp/nemori-pg -c listen_addresses=127.0.0.1' -l /tmp/nemori-pg/log.txt start"
psql -h 127.0.0.1 -p 55432 -U postgres -c "CREATE ROLE nemori LOGIN PASSWORD 'nemori';" -c "CREATE DATABASE nemori OWNER nemori;"
```

## Runtime fixes

These are applied by the sidecar; the installed packages are not edited.

| System | Problem | Fix |
|---|---|---|
| MemoryOS 0.1.0 | Keyword extraction ignores `llm_model` and asks for `gpt-4o-mini` (5 call sites in `mid_term.py` / `updater.py`) | Pass the configured model (`functools.partial`) |
| LightMem 0.1.0 | With transformers ≥ 5, BERT loads with SDPA attention, which returns no attentions; the topic segmenter crashes | `lm.segmenter.model.set_attn_implementation("eager")` |
| LightMem | `messages_use="user_only"` (the example default) would ignore the agent's answers | `messages_use="hybrid"` |
| Nemori 0.2.0 | Needs a Qdrant server and OpenAI embeddings | Embedded Qdrant (`QdrantClient(path=…)`) and local all-MiniLM-L6-v2 embeddings (384 dims) |

**Known upstream quirks, left as they are:**
- MemoryOS prints heavily to stdout; the sidecar sends that to stderr.
- Nemori's `health()` reports only the database.
- Nemori uses a hard-coded 30 s LLM timeout.
- Nemori stores message content JSON-quoted (no JSONB codec).

## Run

```bash
scripts/run_extmem.sh 3 cc-haiku          # one process per backend and task; results/extmem-<backend>-haiku.jsonl
```

Results: `docs/results/2026-10-24-automem-evaluation.md`, finding 5.
