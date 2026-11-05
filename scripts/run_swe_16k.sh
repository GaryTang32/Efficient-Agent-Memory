#!/usr/bin/env bash
# The NVIDIA paper's tightest setting (16K window, compaction at 12K) on the wider SWE set, where compaction fires:
# AutoMemory lean with ReSum vs with the EoCC handoff recap, and EoCC alone. Ceiling rows come from run_swe_wide.sh.
#   scripts/run_swe_16k.sh [workdays]
set -u
cd "$(dirname "$0")/.."
N=${1:-20}
V=results/swe_validation_wide.jsonl
LEAN="automem:workspace=false,ingest=0.1"
SPECS=("$LEAN" "$LEAN,compact=handoff,handoff_variant=swe" "eocc:variant=swe")
nohup .venv/bin/python scripts/run_swe.py --model cc-haiku --specs "${SPECS[@]}" --workdays "$N" --issues 5 \
  --window 16000 --workers 2 --validation "$V" --out results/swe_16k-haiku.jsonl > results/swe_16k-haiku.log 2>&1 &
sleep 3
nohup .venv/bin/python scripts/run_swe.py --model cc-sonnet --aux-model cc-haiku --specs "${SPECS[@]}" --workdays "$N" \
  --issues 5 --window 16000 --workers 2 --validation "$V" --out results/swe_16k-sonnet.jsonl \
  > results/swe_16k-sonnet.log 2>&1 &
wait
