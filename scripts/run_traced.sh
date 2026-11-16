#!/usr/bin/env bash
# Step 3 of the weakness hunt: re-run, with traces on, the Django issues where a setting and its ceiling disagreed
# in earlier runs (plus two stable control issues per model), three runs per cell, both models, 8K reply cap.
# Issue lists: results/swe_validation_traced-{haiku,sonnet}.jsonl (built from scripts/research_store.py
# disagreements). Traces: results/traces/. Re-running resumes.
set -u
cd "$(dirname "$0")/.."
export EAM_CLAUDE_TIMEOUT=${EAM_CLAUDE_TIMEOUT:-900}
L="automem:workspace=false,ingest=0.1"
CELLS=(naive@native "$L" "$L,compact=handoff,handoff_variant=swe" eocc:variant=swe)
for m in haiku sonnet; do
  days=5; [ "$m" = sonnet ] && days=3
  for r in 1 2 3; do
    .venv/bin/python scripts/run_swe.py --model cc-$m --aux-model cc-haiku --specs "${CELLS[@]}" \
      --workdays $days --issues 5 --window 16000 --workers 2 --validation results/swe_validation_traced-$m.jsonl \
      --out results/traced_swe-$m-r$r.jsonl > results/traced_swe-$m-r$r.log 2>&1 &
  done
done
wait
