"""Client for any OpenAI-compatible /chat/completions endpoint.

Routes this covers (see ``eam/llm/routes.py``):
  * a LiteLLM proxy in front of Bedrock (option a)
  * Bedrock's own OpenAI-compatible endpoints, bedrock-mantle and
    bedrock-runtime /openai/v1 (option b)
  * the local gateway in ``eam.gateway`` (Claude Code CLI behind an OpenAI API)

Standard library only (urllib), so it adds no dependency.
"""

from __future__ import annotations

import json
import time
import urllib.error
import urllib.request
from typing import Any

from eam.llm.openai_format import from_openai_response, to_openai_payload
from eam.llm.types import Request, Response


class OpenAICompatError(RuntimeError):
    pass


class OpenAICompatClient:
    def __init__(self, base_url: str, api_key: str | None = None, *, route: str = "openai",
                 cache_control: bool = False, max_tokens_field: str = "max_tokens",
                 timeout_s: float = 600, retries: int = 4, extra_headers: dict[str, str] | None = None):
        self.base_url = base_url.rstrip("/")
        self.api_key = api_key
        self.route = route
        self.cache_control = cache_control
        self.max_tokens_field = max_tokens_field
        self.timeout_s = timeout_s
        self.retries = retries
        self.extra_headers = extra_headers or {}

    def _post(self, path: str, body: dict[str, Any]) -> dict[str, Any]:
        headers = {"Content-Type": "application/json", **self.extra_headers}
        if self.api_key:
            headers["Authorization"] = f"Bearer {self.api_key}"
        data = json.dumps(body).encode()
        delay = 2.0
        for attempt in range(self.retries + 1):
            req = urllib.request.Request(f"{self.base_url}{path}", data=data, headers=headers, method="POST")
            try:
                with urllib.request.urlopen(req, timeout=self.timeout_s) as resp:
                    return json.loads(resp.read())
            except urllib.error.HTTPError as exc:
                detail = exc.read().decode(errors="replace")[:500]
                if exc.code in (429, 500, 502, 503, 504) and attempt < self.retries:
                    time.sleep(delay)
                    delay *= 2
                    continue
                raise OpenAICompatError(f"{self.route}: HTTP {exc.code} from {path}: {detail}") from exc
            except urllib.error.URLError as exc:
                if attempt < self.retries:
                    time.sleep(delay)
                    delay *= 2
                    continue
                raise OpenAICompatError(f"{self.route}: cannot reach {self.base_url}: {exc.reason}") from exc
        raise AssertionError("unreachable")

    def converse(self, req: Request) -> Response:
        body = to_openai_payload(req, req.model.id_for(self.route), cache_control=self.cache_control,
                                 max_tokens_field=self.max_tokens_field)
        t0 = time.perf_counter()
        data = self._post("/chat/completions", body)
        return from_openai_response(data, req.model.key, (time.perf_counter() - t0) * 1000)

    def embed(self, texts: list[str], model: str) -> list[list[float]]:
        data = self._post("/embeddings", {"model": model, "input": texts})
        return [d["embedding"] for d in sorted(data["data"], key=lambda d: d.get("index", 0))]
