"""Local OpenAI-compatible gateway for third-party repos.

Official repos from the papers (MemoryOS, LightMem, Nemori, FoldAgent, ...)
expect an OpenAI-style endpoint. Point their base URL at this gateway and it
forwards each request to one of this repo's backends:

  * ``--chat claude-cli``  your Claude Code CLI (no Bedrock or API key needed)
  * ``--chat converse``    Bedrock Converse via boto3 (AWS credentials)

and serves ``/v1/embeddings`` from a local embedder (``hashing``, or
``st:<sentence-transformers model>`` if installed) or Bedrock Titan (``titan``).
Every call's tokens and cost are appended to ``--log`` (JSONL), so experiments
run through third-party code are metered the same way as the bench.

    python -m eam.gateway --chat claude-cli --port 4100
    export OPENAI_BASE_URL=http://localhost:4100/v1 OPENAI_API_KEY=unused
"""

from __future__ import annotations

import argparse
import json
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any, Callable

from eam.cost import usage_cost
from eam.llm.openai_format import openai_response_from, request_from_openai
from eam.llm.types import LLMClient
from eam.models import ModelProfile, load_models


def make_embedder(spec: str, region: str | None = None) -> Callable[[list[str]], list[list[float]]]:
    if spec == "hashing":
        from eam.memory.embed import HashingEmbedder

        return HashingEmbedder().embed
    if spec == "titan":
        from eam.memory.embed import BedrockTitanEmbedder

        return BedrockTitanEmbedder(region=region).embed
    if spec.startswith("st:"):
        from sentence_transformers import SentenceTransformer  # optional dependency

        model = SentenceTransformer(spec[3:], device="cpu")
        return lambda texts: [list(map(float, v)) for v in model.encode(texts, normalize_embeddings=True)]
    raise ValueError(f"unknown embedder '{spec}'")


class Gateway:
    def __init__(self, client: LLMClient, route: str, models: dict[str, ModelProfile],
                 embed: Callable[[list[str]], list[list[float]]], log_path: str | None = None):
        self.client = client
        self.route = route
        self.models = models
        self.embed = embed
        self.log_path = Path(log_path) if log_path else None
        self._lock = threading.Lock()

    def resolve(self, name: str) -> ModelProfile:
        if name in self.models:
            return self.models[name]
        for m in self.models.values():  # match a route-specific id such as "haiku"
            if m.id_for(self.route) == name:
                return m
        # Unknown name: pass it straight through to the backend; cost comes from the backend if it reports one.
        return ModelProfile(name, name, 0.0, 0.0, route_ids={self.route: name})

    def chat(self, body: dict[str, Any]) -> dict[str, Any]:
        model = self.resolve(str(body.get("model", "")))
        req = request_from_openai(body, model)
        resp = self.client.converse(req)
        cost = resp.reported_cost_usd if resp.reported_cost_usd is not None else usage_cost(resp.usage, model)
        self._log({"kind": "chat", "model": model.key, "usage": resp.usage.to_dict(), "cost_usd": cost,
                   "latency_ms": resp.latency_ms, "stop": resp.stop_reason})
        return openai_response_from(resp, str(body.get("model", model.key)))

    def embeddings(self, body: dict[str, Any]) -> dict[str, Any]:
        inputs = body.get("input", [])
        texts = [inputs] if isinstance(inputs, str) else list(inputs)
        vecs = self.embed(texts)
        self._log({"kind": "embeddings", "n": len(texts)})
        return {"object": "list", "model": body.get("model", "local"),
                "data": [{"object": "embedding", "index": i, "embedding": v} for i, v in enumerate(vecs)],
                "usage": {"prompt_tokens": 0, "total_tokens": 0}}

    def _log(self, row: dict[str, Any]) -> None:
        if not self.log_path:
            return
        row = {"ts": time.time(), **row}
        with self._lock, self.log_path.open("a") as fh:
            fh.write(json.dumps(row) + "\n")


def make_handler(gw: Gateway) -> type[BaseHTTPRequestHandler]:
    class Handler(BaseHTTPRequestHandler):
        protocol_version = "HTTP/1.1"

        def log_message(self, fmt: str, *args: Any) -> None:  # keep stdout quiet
            pass

        def _send(self, code: int, obj: Any, sse: bool = False) -> None:
            if sse:
                chunk = dict(obj, object="chat.completion.chunk")
                chunk["choices"] = [{"index": 0, "delta": c["message"], "finish_reason": c["finish_reason"]}
                                    for c in obj["choices"]]
                data = f"data: {json.dumps(chunk)}\n\ndata: [DONE]\n\n".encode()
                ctype = "text/event-stream"
            else:
                data = json.dumps(obj).encode()
                ctype = "application/json"
            self.send_response(code)
            self.send_header("Content-Type", ctype)
            self.send_header("Content-Length", str(len(data)))
            self.end_headers()
            self.wfile.write(data)

        def do_GET(self) -> None:
            if self.path.rstrip("/").endswith("/models"):
                self._send(200, {"object": "list", "data": [{"id": k, "object": "model"} for k in gw.models]})
            else:
                self._send(404, {"error": {"message": f"no route {self.path}"}})

        def do_POST(self) -> None:
            length = int(self.headers.get("Content-Length") or 0)
            try:
                body = json.loads(self.rfile.read(length) or b"{}")
                if self.path.rstrip("/").endswith("/chat/completions"):
                    self._send(200, gw.chat(body), sse=bool(body.get("stream")))
                elif self.path.rstrip("/").endswith("/embeddings"):
                    self._send(200, gw.embeddings(body))
                else:
                    self._send(404, {"error": {"message": f"no route {self.path}"}})
            except Exception as exc:  # report backend errors to the caller as OpenAI-style errors
                self._send(500, {"error": {"message": str(exc), "type": type(exc).__name__}})

    return Handler


def serve(gw: Gateway, host: str = "127.0.0.1", port: int = 4100) -> ThreadingHTTPServer:
    return ThreadingHTTPServer((host, port), make_handler(gw))


def main(argv: list[str] | None = None) -> None:
    ap = argparse.ArgumentParser(prog="python -m eam.gateway")
    ap.add_argument("--chat", default="claude-cli", choices=["claude-cli", "converse"])
    ap.add_argument("--embed", default="hashing", help="hashing | titan | st:<sentence-transformers model>")
    ap.add_argument("--host", default="127.0.0.1")
    ap.add_argument("--port", type=int, default=4100)
    ap.add_argument("--region", default=None)
    ap.add_argument("--models-config", default=None)
    ap.add_argument("--log", default="results/gateway_calls.jsonl")
    args = ap.parse_args(argv)

    from eam.llm.routes import make_client

    Path(args.log).parent.mkdir(parents=True, exist_ok=True)
    gw = Gateway(make_client(args.chat, region=args.region), args.chat, load_models(args.models_config),
                 make_embedder(args.embed, args.region), args.log)
    server = serve(gw, args.host, args.port)
    print(f"eam gateway on http://{args.host}:{args.port}/v1  chat={args.chat} embed={args.embed} log={args.log}")
    server.serve_forever()


if __name__ == "__main__":
    main()
