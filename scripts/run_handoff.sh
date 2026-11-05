#!/usr/bin/env bash
# NVIDIA EoCC handoff compaction (arXiv 2611.05306) on the four long tasks, instances 0-3, through the Claude Code
# CLI: the paper's method alone (eocc) and as AutoMemory v2's compactor (written by the agent model, or on Sonnet
# also by the Haiku summariser). References (floor, ceiling, v2) are the earlier rows on the same instances.
set -u
cd "$(dirname "$0")/.."
export EAM_CLAUDE_TIMEOUT=${EAM_CLAUDE_TIMEOUT:-600}
for t in research_corpus ops_stream ledger_audit repo_debug; do
  .venv/bin/python -m eam.bench run --task "$t" -t "automem:ingest=0.1,compact=handoff" -t eocc --n 4 --workers 2 \
    --resume --backend claude-cli --model cc-haiku --aux-model cc-haiku --out "results/handoff-$t-haiku.jsonl" \
    > "results/handoff-$t-haiku.log" 2>&1 &
  sleep 2
  .venv/bin/python -m eam.bench run --task "$t" -t "automem:ingest=0.1,compact=handoff#aux=cc-haiku" \
    -t "automem:ingest=0.1,compact=handoff_aux#aux=cc-haiku" -t eocc --n 4 --workers 2 --resume \
    --backend claude-cli --model cc-sonnet --aux-model cc-sonnet --out "results/handoff-$t-sonnet.jsonl" \
    > "results/handoff-$t-sonnet.log" 2>&1 &
  sleep 2
done
wait
