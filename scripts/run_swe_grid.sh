#!/usr/bin/env bash
# SWE-bench Verified workdays: 8 workdays x 5 issues, Haiku and Sonnet, the model's own window and a tight 16K window.
set -u
cd "$(dirname "$0")/.."
H=(naive@native full@native automem_v2@native naive full automem automem_v2)
S=("${H[@]}" automem_v2_strong@native automem_v2_strong)
nohup .venv/bin/python scripts/run_swe.py --model cc-haiku --specs "${H[@]}" --workdays 8 --issues 5 --window 16000 \
  --workers 3 --out results/swe-haiku.jsonl > results/swe-haiku.log 2>&1 &
sleep 3
nohup .venv/bin/python scripts/run_swe.py --model cc-sonnet --aux-model cc-haiku --specs "${S[@]}" --workdays 8 --issues 5 \
  --window 16000 --workers 3 --out results/swe-sonnet.jsonl > results/swe-sonnet.log 2>&1 &
wait
