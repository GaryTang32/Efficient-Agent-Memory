#!/usr/bin/env bash
# AutoMemory v2 candidates (fold / ingest switches) on the four long tasks through the Claude Code CLI.
#   scripts/run_automem_v2.sh [model] [n_seeds] [workers per task] [aux suffix, e.g. "#aux=cc-haiku"] [extra specs...]
set -u
cd "$(dirname "$0")/.."
MODEL=${1:-cc-haiku}; N=${2:-4}; W=${3:-2}; AUX=${4:-}; shift 4 2>/dev/null || shift $#
SPECS=("automem:fold=true" "automem:ingest=0.1" "automem:fold=true,ingest=0.1" "$@")
export EAM_CLAUDE_TIMEOUT=${EAM_CLAUDE_TIMEOUT:-600}
for t in research_corpus ops_stream ledger_audit repo_debug; do
  args=(); for s in "${SPECS[@]}"; do args+=(-t "$s$AUX"); done
  .venv/bin/python -m eam.bench run --task "$t" "${args[@]}" --n "$N" --workers "$W" --resume --backend claude-cli \
    --model "$MODEL" --aux-model "$MODEL" --out "results/automem_v2-$t-${MODEL#cc-}.jsonl" \
    > "results/automem_v2-$t-${MODEL#cc-}.log" 2>&1 &
  sleep 2
done
wait
