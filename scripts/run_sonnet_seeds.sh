#!/usr/bin/env bash
# Extra Sonnet seeds (instances up to 3) for v2 vs v2 + compact=sjc, and the anchors / v1 they are normalised against.
set -u
cd "$(dirname "$0")/.."
export EAM_CLAUDE_TIMEOUT=${EAM_CLAUDE_TIMEOUT:-600}
B=(--backend claude-cli --model cc-sonnet --aux-model cc-sonnet --resume --workers 2)
for t in research_corpus ops_stream ledger_audit repo_debug; do
  out="results/seeds_sonnet-$t.jsonl"; log="results/seeds_sonnet-$t.log"
  case $t in research_corpus|ledger_audit) as=3; an=1;; *) as=2; an=2;; esac  # anchors: v4 already has 3 / 2 seeds
  ( .venv/bin/python -m eam.bench run --task "$t" -t "automem:ingest=0.1#aux=cc-haiku" \
      -t "automem:ingest=0.1,compact=sjc#aux=cc-haiku" --seed 2 --n 2 "${B[@]}" --out "$out" >> "$log" 2>&1
    .venv/bin/python -m eam.bench run --task "$t" -t naive -t naive@native -t "automem#aux=cc-haiku" \
      --seed "$as" --n "$an" "${B[@]}" --out "$out" >> "$log" 2>&1 ) &
  sleep 2
done
wait
