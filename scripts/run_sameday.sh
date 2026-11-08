#!/usr/bin/env bash
# Validation, same day: every decision cell re-run together (no reused baselines), plus one repeated cell per workload
# to measure run-to-run spread. Django: 100 SWE-bench Verified issues at 16K. Synthetic: four long tasks, instances 0-3.
set -u
cd "$(dirname "$0")/.."
export EAM_CLAUDE_TIMEOUT=${EAM_CLAUDE_TIMEOUT:-900}
V=results/swe_validation_wide.jsonl
L="automem:workspace=false,ingest=0.1"
SWE=(naive@native "$L" "$L,compact=handoff,handoff_variant=swe" "$L,compact=handoff,handoff_variant=brief" automem_v2_adaptive)
for m in haiku sonnet; do
  aux=cc-haiku
  .venv/bin/python scripts/run_swe.py --model cc-$m --aux-model $aux --specs "${SWE[@]}" --workdays 20 --issues 5 \
    --window 16000 --workers 2 --validation "$V" --out results/sameday_swe-$m.jsonl > results/sameday_swe-$m.log 2>&1 &
  .venv/bin/python scripts/run_swe.py --model cc-$m --aux-model $aux --specs "$L" --workdays 20 --issues 5 \
    --window 16000 --workers 1 --validation "$V" --out results/sameday_swe_rep-$m.jsonl > results/sameday_swe_rep-$m.log 2>&1 &
done
for t in research_corpus ops_stream ledger_audit repo_debug; do
  .venv/bin/python -m eam.bench run --task "$t" -t naive@native -t automem:ingest=0.1 -t "$L" -t automem_v2_adaptive \
    --n 4 --workers 1 --resume --backend claude-cli --model cc-haiku --aux-model cc-haiku \
    --out "results/sameday_syn-$t-haiku.jsonl" > "results/sameday_syn-$t-haiku.log" 2>&1 &
  .venv/bin/python -m eam.bench run --task "$t" -t naive@native -t "automem:ingest=0.1#aux=cc-haiku" -t "$L#aux=cc-haiku" \
    -t "automem_v2_adaptive#aux=cc-haiku" --n 4 --workers 1 --resume --backend claude-cli --model cc-sonnet \
    --aux-model cc-sonnet --out "results/sameday_syn-$t-sonnet.jsonl" > "results/sameday_syn-$t-sonnet.log" 2>&1 &
  .venv/bin/python -m eam.bench run --task "$t" -t automem:ingest=0.1 --n 4 --workers 1 --resume --backend claude-cli \
    --model cc-haiku --aux-model cc-haiku --out "results/sameday_syn_rep-$t-haiku.jsonl" \
    > "results/sameday_syn_rep-$t-haiku.log" 2>&1 &
  .venv/bin/python -m eam.bench run --task "$t" -t "automem:ingest=0.1#aux=cc-haiku" --n 4 --workers 1 --resume \
    --backend claude-cli --model cc-sonnet --aux-model cc-sonnet --out "results/sameday_syn_rep-$t-sonnet.jsonl" \
    > "results/sameday_syn_rep-$t-sonnet.log" 2>&1 &
  sleep 2
done
wait
