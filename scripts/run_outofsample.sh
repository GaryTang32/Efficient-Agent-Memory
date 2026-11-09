#!/usr/bin/env bash
# Out-of-sample checks at the 16K window, both models.
#   Related Django workdays: each workday stays in one subsystem (scripts/swe_related.py), so later sessions can reuse
#   what earlier ones learned; tests whether the note workspace pays when that is so (lean vs v2 vs adaptive).
#   SymPy: a second repository (SWE-bench Verified sympy/sympy, validated with scripts/swe_validate.py); the
#   recommended presets (lean, handoff) against the ceiling.
#   scripts/run_outofsample.sh [all|related|sympy]
# Sonnet runs fewer workdays (cost): REL_DAYS_SONNET (default 10 of 16) and SYM_DAYS_SONNET (default 8 of 15).
set -u
PART=${1:-all}
cd "$(dirname "$0")/.."
export EAM_CLAUDE_TIMEOUT=${EAM_CLAUDE_TIMEOUT:-900}
L="automem:workspace=false,ingest=0.1"
REL=results/swe_validation_related.jsonl
SYM=results/swe_validation_sympy.jsonl
[ -f "$REL" ] || .venv/bin/python scripts/swe_related.py results/swe_validation_wide.jsonl "$REL" 5
nrel=$(( $(wc -l < "$REL") / 5 ))
days() { [ "$1" = sonnet ] && [ "$3" -lt "$2" ] && echo "$3" || echo "$2"; }
for m in haiku sonnet; do
  [ "$PART" = sympy ] && break
  .venv/bin/python scripts/run_swe.py --model cc-$m --aux-model cc-haiku --workdays "$(days $m $nrel ${REL_DAYS_SONNET:-10})" --issues 5 --window 16000 \
    --workers 2 --validation "$REL" --specs naive@native "$L" automem:ingest=0.1 automem_v2_adaptive \
    --out results/oos_related-$m.jsonl > results/oos_related-$m.log 2>&1 &
done
[ "$PART" = related ] && { wait; exit 0; }
while pgrep -f "swe_validate.py $SYM" > /dev/null; do sleep 60; done
nsym=$(( $(.venv/bin/python -c "import json; print(sum(1 for l in open('$SYM') if (r:=json.loads(l))['fails_before'] and r['passes_with_gold']))") / 5 ))
for m in haiku sonnet; do
  .venv/bin/python scripts/run_swe.py --model cc-$m --aux-model cc-haiku --workdays "$(days $m $nsym ${SYM_DAYS_SONNET:-8})" --issues 5 --window 16000 \
    --workers 2 --validation "$SYM" --specs naive@native "$L" "$L,compact=handoff,handoff_variant=swe" \
    --out results/oos_sympy-$m.jsonl > results/oos_sympy-$m.log 2>&1 &
done
wait
