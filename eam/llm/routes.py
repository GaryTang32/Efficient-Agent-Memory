"""Backend routes: how a run reaches a model.

| route            | what it is                                                     | auth                         |
|------------------|----------------------------------------------------------------|------------------------------|
| `converse`       | native Bedrock Converse API (boto3); full cachePoint control   | AWS credentials (IAM)        |
| `litellm`        | option (a): local LiteLLM proxy in front of Bedrock            | AWS creds on the proxy       |
| `mantle`         | option (b): Bedrock OpenAI-compatible endpoint (bedrock-mantle) | Bedrock API key              |
| `bedrock-openai` | option (b): bedrock-runtime `/openai/v1` Chat Completions       | Bedrock API key              |
| `claude-cli`     | Claude Code CLI (`claude -p`), no Bedrock needed               | your Claude Code login       |
| `gateway`        | this repo's OpenAI-compatible gateway (`python -m eam.gateway`) | none (local)                 |
| `mock`           | offline scripted policies + cache simulator                    | none                         |

Environment variables (all optional):
  AWS_REGION / AWS_DEFAULT_REGION   region for Bedrock routes (default us-east-1)
  AWS_BEARER_TOKEN_BEDROCK          Bedrock API key for `mantle` / `bedrock-openai`
  EAM_LITELLM_URL, LITELLM_API_KEY  LiteLLM proxy URL (default http://localhost:4000/v1) and key
  EAM_GATEWAY_URL                   gateway URL (default http://localhost:4100/v1)
  EAM_CLAUDE_BIN                    path to the `claude` binary
  EAM_CLAUDE_TIMEOUT                seconds per `claude -p` call (default 240)
  EAM_CLAUDE_MAX_OUTPUT             reply cap passed as CLAUDE_CODE_MAX_OUTPUT_TOKENS (default 32000)
"""

from __future__ import annotations

import os

from eam.llm.types import LLMClient

ROUTES = ("mock", "converse", "litellm", "mantle", "bedrock-openai", "claude-cli", "gateway")


def _region(region: str | None) -> str:
    return region or os.environ.get("AWS_REGION") or os.environ.get("AWS_DEFAULT_REGION") or "us-east-1"


def route_base_url(route: str, region: str | None = None) -> str:
    r = _region(region)
    return {
        "litellm": os.environ.get("EAM_LITELLM_URL", "http://localhost:4000/v1"),
        "mantle": f"https://bedrock-mantle.{r}.api.aws/v1",
        "bedrock-openai": f"https://bedrock-runtime.{r}.amazonaws.com/openai/v1",
        "gateway": os.environ.get("EAM_GATEWAY_URL", "http://localhost:4100/v1"),
    }[route]


def make_client(route: str, *, region: str | None = None, policy=None, prompt_cache: bool = True) -> LLMClient:
    """``prompt_cache=False`` switches provider-side caching off where the route caches on its own (Claude Code
    CLI, mock simulator). Converse/OpenAI routes cache only at the cache points a technique adds."""
    if route == "mock":
        from eam.llm.mock import MockLLM

        if policy is None:
            raise ValueError("the mock route needs a scripted policy")
        return MockLLM(policy, prompt_cache=prompt_cache)
    if route in ("converse", "bedrock"):
        from eam.llm.bedrock import BedrockClient

        return BedrockClient(region=_region(region))
    if route == "claude-cli":
        from eam.llm.claude_cli import ClaudeCLIClient

        return ClaudeCLIClient(env=None if prompt_cache else {"DISABLE_PROMPT_CACHING": "1"})
    if route in ("litellm", "mantle", "bedrock-openai", "gateway"):
        from eam.llm.openai_compat import OpenAICompatClient

        if route == "litellm":
            key = os.environ.get("LITELLM_API_KEY", "sk-local")
        elif route == "gateway":
            key = None
        else:
            key = os.environ.get("AWS_BEARER_TOKEN_BEDROCK")
            if not key:
                raise ValueError(f"route '{route}' needs a Bedrock API key in AWS_BEARER_TOKEN_BEDROCK")
        # LiteLLM translates Anthropic-style cache_control markers into Bedrock cache points.
        return OpenAICompatClient(route_base_url(route, region), key, route=route,
                                  cache_control=route in ("litellm", "gateway"))
    raise ValueError(f"unknown route '{route}'; choose from {ROUTES}")
