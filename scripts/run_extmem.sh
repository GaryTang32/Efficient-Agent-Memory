#!/usr/bin/env bash
# Official memory systems on the multi-session tasks, one process per (backend, task); LightMem's two later tasks
# run one after the other to bound memory use (its LLMLingua-2 model takes ~2-3 GB per process).
#   scripts/run_extmem.sh [n_seeds] [model]
set -u
cd "$(dirname "$0")/.."
N=${1:-3}
MODEL=${2:-cc-haiku}
export EAM_CLAUDE_TIMEOUT=${EAM_CLAUDE_TIMEOUT:-600}
k_for() { case $1 in ledger_audit) echo 40;; repo_debug) echo 13;; *) echo 26;; esac; }
one() { # backend task
  .venv/bin/python -m eam.bench run --task "$2" -t "ext_memory:backend=$1+resum:max_context_k=$(k_for "$2")" \
    --n "$N" --workers 1 --resume --backend claude-cli --model "$MODEL" --aux-model "$MODEL" \
    --out "results/extmem-$1-${MODEL#cc-}.jsonl" > "results/extmem-$1-$2-${MODEL#cc-}.log" 2>&1
}
for b in memoryos nemori; do
  for t in ops_stream ledger_audit repo_debug; do one "$b" "$t" & sleep 1; done
done
one lightmem ops_stream &
(one lightmem ledger_audit; one lightmem repo_debug) &
wait
