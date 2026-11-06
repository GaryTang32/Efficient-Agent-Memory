#!/usr/bin/env bash
# Start the LiteLLM proxy (option a). Requires: pip install 'litellm[proxy]' and AWS credentials.
set -euo pipefail
cd "$(dirname "$0")/.."
CONFIG="${1:-config/litellm.yaml}"
[ -f "$CONFIG" ] || { echo "copy config/litellm.example.yaml to $CONFIG and fill in model ids" >&2; exit 1; }
export LITELLM_API_KEY="${LITELLM_API_KEY:-sk-local}"
export AWS_REGION="${AWS_REGION:-us-east-1}"
exec litellm --config "$CONFIG" --port "${PORT:-4000}"
