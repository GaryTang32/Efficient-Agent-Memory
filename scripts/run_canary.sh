#!/usr/bin/env bash
# Canary cell: the same 10 Django issues (the first two workdays of the wide set), ceiling and lean, both models, on
# every experiment day. `python scripts/research_store.py canary` flags drift in the model, the CLI or prices: the
# ceiling moving by more than 2 issues or 15% in cost from its running median. About $3 per day.
set -u
cd "$(dirname "$0")/.."
export EAM_CLAUDE_TIMEOUT=${EAM_CLAUDE_TIMEOUT:-900}
day=$(date -u +%Y-%m-%d)
for m in haiku sonnet; do
  .venv/bin/python scripts/run_swe.py --model cc-$m --aux-model cc-haiku --specs naive@native \
    "automem:workspace=false,ingest=0.1" --workdays 2 --issues 5 --window 16000 --workers 2 \
    --validation results/swe_validation_wide.jsonl --out "results/canary-$day-$m.jsonl" \
    > "results/canary-$day-$m.log" 2>&1 &
done
wait
