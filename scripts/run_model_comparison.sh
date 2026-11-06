#!/usr/bin/env bash
# Model comparison through the Claude Code CLI: same suites, seeds and techniques on haiku / sonnet / opus.
# Usage: scripts/run_model_comparison.sh <suite> <model profile> [n] [workers]
set -euo pipefail
cd "$(dirname "$0")/.."
SUITE="$1"; MODEL="$2"; N="${3:-3}"; W="${4:-6}"
OUT="results/${SUITE}-cli-${MODEL#cc-}.jsonl"
exec .venv/bin/python -m eam.bench suite "$SUITE" --n "$N" --workers "$W" --backend claude-cli \
  --model "$MODEL" --aux-model "$MODEL" --out "$OUT"
