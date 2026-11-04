#!/usr/bin/env bash
# New methods (suite real_v5) on the four long tasks through the Claude Code CLI, one process per task.
#   scripts/run_v5.sh [model] [n_seeds] [workers per task] [tasks...]
set -u
cd "$(dirname "$0")/.."
MODEL=${1:-cc-haiku}; N=${2:-4}; W=${3:-3}; shift 3 2>/dev/null || shift $#
TASKS=${*:-research_corpus ops_stream ledger_audit repo_debug}
export EAM_CLAUDE_TIMEOUT=${EAM_CLAUDE_TIMEOUT:-600}
for t in $TASKS; do
  .venv/bin/python -m eam.bench suite real_v5 --only "$t" --n "$N" --workers "$W" --resume --backend claude-cli \
    --model "$MODEL" --aux-model "$MODEL" --out "results/real_v5-$t-${MODEL#cc-}.jsonl" \
    > "results/real_v5-$t-${MODEL#cc-}.log" 2>&1 &
  sleep 2
done
wait
