#!/usr/bin/env bash
# SWE-bench Verified workdays on the wider Django set (4.0-5.0, all difficulties, SWE-bench-faithful grading),
# a 32K emulated window (the NVIDIA paper's 32K / 24K setting) plus native-window references.
#   scripts/run_swe_wide.sh [workdays]
set -u
cd "$(dirname "$0")/.."
N=${1:-16}
V=results/swe_validation_wide.jsonl
LEAN="automem:workspace=false,ingest=0.1"
H=(naive@native full@native full "$LEAN" "$LEAN,compact=handoff,handoff_variant=swe" "eocc:variant=swe")
S=("${H[@]}" "$LEAN,compact=handoff_aux,handoff_variant=swe")
nohup .venv/bin/python scripts/run_swe.py --model cc-haiku --specs "${H[@]}" --workdays "$N" --issues 5 --window 32000 \
  --workers 3 --validation "$V" --out results/swe_wide-haiku.jsonl > results/swe_wide-haiku.log 2>&1 &
sleep 3
nohup .venv/bin/python scripts/run_swe.py --model cc-sonnet --aux-model cc-haiku --specs "${S[@]}" --workdays "$N" \
  --issues 5 --window 32000 --workers 3 --validation "$V" --out results/swe_wide-sonnet.jsonl \
  > results/swe_wide-sonnet.log 2>&1 &
wait
