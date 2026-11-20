#!/usr/bin/env bash
# The Claude Code plugin under different Claude Code settings: does it still work, and does it change results?
# One headless Claude Code session per workday of 5 Django issues (SWE-bench Verified, graded as SWE-bench grades),
# Claude Code's compaction window at 100K (compaction fires) and at 500K (a 1M model compacting at 500K: it rarely
# fires on this work), without the plugin, with its defaults, and with sizes scaled to the window.
#   scripts/run_cc_settings.sh            about $7-8 (Haiku and Sonnet, 3 workdays per cell)
set -u
cd "$(dirname "$0")/.."
SCALED="plugin+AUTOMEM_PREVIEW_SHARE=0.02,AUTOMEM_RECALL_TOKENS=4000"
for m in haiku sonnet; do
  for w in 100000 500000; do
    .venv/bin/python scripts/run_cc_long.py --model "$m" --compact-window "$w" --settings plain plugin "$SCALED" \
      --workdays 3 --issues 5 --first 20 --workers 2 --out "results/cc_settings-$m-$w.jsonl" \
      > "results/cc_settings-$m-$w.log" 2>&1 &
    sleep 3
  done
done
wait
