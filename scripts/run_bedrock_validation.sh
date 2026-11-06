#!/usr/bin/env bash
# Bedrock validation of the CLI findings (docs/results/2026-10-24-bedrock-validation-plan.md).
#
# Needs: Bedrock access through boto3 (valid AWS_ACCESS_KEY_ID / AWS_SECRET_ACCESS_KEY [/ AWS_SESSION_TOKEN], or a
# profile), AWS_REGION, and config/models.json with the model ids and prices of your account
# (copy config/models.example.json; fill the Chinese-lab ids you have access to: kimi, deepseek, qwen, glm).
#
#   AWS_REGION=us-east-1 scripts/run_bedrock_validation.sh [n_seeds]
set -euo pipefail
cd "$(dirname "$0")/.."
N=${1:-3}
REGION=${AWS_REGION:?set AWS_REGION}
PY=.venv/bin/python
OUT=results/bedrock
mkdir -p "$OUT"
run() { # task, model, aux, out, specs...
  local task=$1 model=$2 aux=$3 out=$4; shift 4
  local args=(); for s in "$@"; do args+=(-t "$s"); done
  $PY -m eam.bench run --task "$task" "${args[@]}" --n "$N" --workers 4 --resume \
      --backend converse --region "$REGION" --model "$model" --aux-model "$aux" --out "$OUT/$out.jsonl"
}

# 0. The route works: chat, tools, append-only caching (cache read on the second call), embeddings.
$PY -m eam.smoke --route converse --model haiku --region "$REGION"

# 1. Cache-point placement: does a cache point at the boundary of the never-edited history let masking and
#    AgentDiet keep their token savings without the cache collapse measured on the CLI (one end breakpoint)?
for model in haiku sonnet; do
  run chain_hunt "$model" haiku "cachepoint-chain-$model" \
      naive cache_layout cache_layout+obs_mask "cache_layout:edit_boundary=true+obs_mask" \
      cache_layout+agentdiet "cache_layout:edit_boundary=true+agentdiet"
done

# 2. The long-horizon results at Bedrock prices and 5-minute cache writes (1.25×): anchors, best methods, AutoMemory.
for model in haiku sonnet; do
  run research_corpus "$model" haiku "research-$model" naive naive@native "cache_layout@native" \
      cache_layout+obs_mask "cache_layout+resum:max_context_k=33" automem automem+cache_layout
  run ops_stream "$model" haiku "ops-$model" naive naive@native "cache_layout+fs_workspace+resum:max_context_k=26" \
      automem automem+cache_layout
done

# 3. Chinese-lab models on Bedrock (no prompt caching on most of them: every resent token is paid in full).
for model in kimi deepseek qwen glm; do
  if $PY -c "import sys; from eam.models import load_models; sys.exit(0 if '$model' in load_models(None) else 1)"; then
    run research_corpus "$model" "$model" "research-$model" naive naive@native obs_mask "resum:max_context_k=33" automem
    run ops_stream "$model" "$model" "ops-$model" naive naive@native "fs_workspace+resum:max_context_k=26" automem
  else
    echo "skipping $model: no model id in config/models.json"
  fi
done

$PY -m eam.bench.analyze --summary "$OUT"/*.jsonl
$PY -m eam.bench.analyze --robust "$OUT"/*.jsonl
