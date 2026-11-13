#!/usr/bin/env bash
# Follow-up to the validation round: two more runs of the coding cells the presets are chosen from (ceiling, lean,
# lean + handoff) on the 100 Django issues at 16K, so each cell has three runs and cost can be ranked with an
# interval; and EoCC alone under the corrected grading on both models (in run 2, next to its same-day ceiling).
# Runs 2 and 3 use the 8K reply cap and record their settings; run 1 (results/sameday_swe-*.jsonl) used the 32K cap.
#   scripts/run_rank3.sh            # resumes from the rows already written
set -u
cd "$(dirname "$0")/.."
export EAM_CLAUDE_TIMEOUT=${EAM_CLAUDE_TIMEOUT:-900}
V=results/swe_validation_wide.jsonl
L="automem:workspace=false,ingest=0.1"
CELLS=(naive@native "$L" "$L,compact=handoff,handoff_variant=swe")
for m in haiku sonnet; do
  w=2; [ "$m" = sonnet ] && w=3
  .venv/bin/python scripts/run_swe.py --model cc-$m --aux-model cc-haiku --specs "${CELLS[@]}" eocc:variant=swe \
    --workdays 20 --issues 5 --window 16000 --workers $w --validation "$V" \
    --out results/rank3_swe-$m-r2.jsonl > results/rank3_swe-$m-r2.log 2>&1 &
  .venv/bin/python scripts/run_swe.py --model cc-$m --aux-model cc-haiku --specs "${CELLS[@]}" \
    --workdays 20 --issues 5 --window 16000 --workers $w --validation "$V" \
    --out results/rank3_swe-$m-r3.jsonl > results/rank3_swe-$m-r3.log 2>&1 &
done
wait
