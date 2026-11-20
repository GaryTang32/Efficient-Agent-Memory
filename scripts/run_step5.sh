#!/usr/bin/env bash
# Step 5, targeted fixes (no extra model calls), each against a baseline from the same day:
#   recall   recall_results=latest (older autosaved answers leave recall), then + note_ids (ids with their values in
#            notes), on the two tasks with facts carried between sessions; baseline: step 4's automem_v2 runs
#            (results/recall-*.jsonl, same instances). Haiku 4 runs, Sonnet 3 with Haiku as the summariser.
#   verify   lean + verify=true (a final answer goes back once while the last test run still fails) against lean, on
#            step 3's Django issues, three runs each.
#   scripts/run_step5.sh [recall|verify|both]        about $18 + $16
set -u
cd "$(dirname "$0")/.."
export EAM_CLAUDE_TIMEOUT=${EAM_CLAUDE_TIMEOUT:-900}
part=${1:-both}
if [ "$part" != verify ]; then
  for m in haiku sonnet; do
    n=$([ $m = haiku ] && echo 4 || echo 3); aux=$([ $m = sonnet ] && echo "#aux=cc-haiku" || echo "")
    for t in ops_stream ledger_audit; do
      .venv/bin/python -m eam.bench run --task "$t" -t "automem:ingest=0.1,recall_results=latest$aux" \
        -t "automem:ingest=0.1,recall_results=latest,note_ids=true$aux" --n "$n" --workers 2 --resume \
        --backend claude-cli --model "cc-$m" --aux-model "cc-$m" --out "results/step5-$t-$m.jsonl" \
        > "results/step5-$t-$m.log" 2>&1 &
      sleep 2
    done
  done
fi
if [ "$part" != recall ]; then
  L="automem:workspace=false,ingest=0.1"
  for m in haiku sonnet; do
    days=5; [ "$m" = sonnet ] && days=3
    for r in 1 2 3; do
      .venv/bin/python scripts/run_swe.py --model cc-$m --aux-model cc-haiku --specs "$L" "$L,verify=true" \
        --workdays $days --issues 5 --window 16000 --workers 1 --validation results/swe_validation_traced-$m.jsonl \
        --out results/step5_swe-$m-r$r.jsonl > results/step5_swe-$m-r$r.log 2>&1 &
    done
  done
fi
wait
