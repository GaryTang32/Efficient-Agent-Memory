#!/usr/bin/env bash
# Cheaper handoff recap: the brief variant (terse, pointers instead of code, at most 150 words), with and without the
# two recent steps AutoMemory keeps after a reset; 100 SWE-bench Verified issues at 16K, compared with run_swe_16k.sh.
set -u
cd "$(dirname "$0")/.."
V=results/swe_validation_wide.jsonl
B="automem:workspace=false,ingest=0.1,compact=handoff,handoff_variant=brief"
SPECS=("$B" "$B,keep_recent=0")
nohup .venv/bin/python scripts/run_swe.py --model cc-haiku --specs "${SPECS[@]}" --workdays 20 --issues 5 --window 16000 \
  --workers 3 --validation "$V" --out results/swe_16k_brief-haiku.jsonl > results/swe_16k_brief-haiku.log 2>&1 &
sleep 3
nohup .venv/bin/python scripts/run_swe.py --model cc-sonnet --aux-model cc-haiku --specs "${SPECS[@]}" --workdays 20 \
  --issues 5 --window 16000 --workers 3 --validation "$V" --out results/swe_16k_brief-sonnet.jsonl \
  > results/swe_16k_brief-sonnet.log 2>&1 &
wait
