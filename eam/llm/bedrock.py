"""Amazon Bedrock Converse backend."""

from __future__ import annotations

import time
from typing import Any

from eam.llm.render import render_converse
from eam.llm.types import Request, Response, Usage


class BedrockClient:
    def __init__(self, region: str | None = None, client: Any = None, profile: str | None = None):
        if client is None:
            import boto3
            from botocore.config import Config

            session = boto3.Session(profile_name=profile, region_name=region)
            client = session.client(
                "bedrock-runtime",
                config=Config(retries={"max_attempts": 8, "mode": "adaptive"}, read_timeout=300),
            )
        self._client = client

    def converse(self, req: Request) -> Response:
        kwargs = render_converse(req)
        t0 = time.perf_counter()
        out = self._client.converse(**kwargs)
        latency_ms = out.get("metrics", {}).get("latencyMs", (time.perf_counter() - t0) * 1000)
        u = out.get("usage", {})
        # Converse reports inputTokens excluding cache reads/writes (as Anthropic does).
        usage = Usage(
            input_tokens=u.get("inputTokens", 0),
            output_tokens=u.get("outputTokens", 0),
            cache_read_tokens=u.get("cacheReadInputTokens", 0),
            cache_write_tokens=u.get("cacheWriteInputTokens", 0),
        )
        return Response(
            message=out["output"]["message"],
            stop_reason=out.get("stopReason", "end_turn"),
            usage=usage,
            latency_ms=float(latency_ms),
            model_key=req.model.key,
        )
