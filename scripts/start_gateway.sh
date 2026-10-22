#!/usr/bin/env bash
# Start this repo's OpenAI-compatible gateway backed by the Claude Code CLI (no Bedrock needed).
# Third-party repos then use OPENAI_BASE_URL=http://localhost:4100/v1 OPENAI_API_KEY=unused
set -euo pipefail
cd "$(dirname "$0")/.."
PY="${PYTHON:-.venv/bin/python}"
exec "$PY" -m eam.gateway --chat "${CHAT:-claude-cli}" --embed "${EMBED:-hashing}" --port "${PORT:-4100}"
