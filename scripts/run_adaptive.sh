#!/usr/bin/env bash
# Adaptive workspace (automem_v2_adaptive) on both workloads: the four long tasks (instances 0-3, compared with the
# automem_v2 rows) and the 100 SWE-bench Verified issues at 16K (compared with automem_v2_lean).
set -u
cd "$(dirname "$0")/.."
export EAM_CLAUDE_TIMEOUT=${EAM_CLAUDE_TIMEOUT:-600}
for t in research_corpus ops_stream ledger_audit repo_debug; do
  .venv/bin/python -m eam.bench run --task "$t" -t automem_v2_adaptive --n 4 --workers 2 --resume --backend claude-cli \
    --model cc-haiku --aux-model cc-haiku --out "results/adaptive-$t-haiku.jsonl" > "results/adaptive-$t-haiku.log" 2>&1 &
  .venv/bin/python -m eam.bench run --task "$t" -t "automem_v2_adaptive#aux=cc-haiku" --n 4 --workers 2 --resume \
    --backend claude-cli --model cc-sonnet --aux-model cc-sonnet --out "results/adaptive-$t-sonnet.jsonl" \
    > "results/adaptive-$t-sonnet.log" 2>&1 &
  sleep 2
done
V=results/swe_validation_wide.jsonl
.venv/bin/python scripts/run_swe.py --model cc-haiku --specs automem_v2_adaptive --workdays 20 --issues 5 --window 16000 \
  --workers 2 --validation "$V" --out results/swe_16k_adaptive-haiku.jsonl > results/swe_16k_adaptive-haiku.log 2>&1 &
.venv/bin/python scripts/run_swe.py --model cc-sonnet --aux-model cc-haiku --specs automem_v2_adaptive --workdays 20 \
  --issues 5 --window 16000 --workers 2 --validation "$V" --out results/swe_16k_adaptive-sonnet.jsonl \
  > results/swe_16k_adaptive-sonnet.log 2>&1 &
wait
