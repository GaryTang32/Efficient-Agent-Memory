#!/usr/bin/env bash
# Step 4, recall measurement: automem_v2 on the three multi-session tasks with traces on, the same instances as the
# v2 evaluation (Haiku 4, Sonnet 3 with Haiku as the summariser). Analyse with scripts/recall_report.py.
#   scripts/run_recall.sh [haiku|sonnet|both]     about $2 for Haiku, $8.50 for Sonnet
set -u
cd "$(dirname "$0")/.."
export EAM_CLAUDE_TIMEOUT=${EAM_CLAUDE_TIMEOUT:-900}
which=${1:-both}
for m in haiku sonnet; do
  [ "$which" = both ] || [ "$which" = "$m" ] || continue
  n=$([ $m = haiku ] && echo 4 || echo 3)
  aux=$([ $m = sonnet ] && echo "#aux=cc-haiku" || echo "")
  for t in ops_stream ledger_audit repo_debug; do
    .venv/bin/python -m eam.bench run --task "$t" -t "automem:ingest=0.1$aux" --n "$n" --workers 2 --resume \
      --backend claude-cli --model "cc-$m" --aux-model "cc-$m" --out "results/recall-$t-$m.jsonl" \
      > "results/recall-$t-$m.log" 2>&1 &
    sleep 2
  done
done
wait
