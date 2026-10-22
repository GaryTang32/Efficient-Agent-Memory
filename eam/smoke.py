"""Route compatibility smoke test: `python -m eam.smoke --route <route> --model <profile>`.

Checks, for one model on one route: plain chat, a tool-call round trip, prompt-cache
reuse across two calls with the same long prefix, and (OpenAI-style routes) embeddings.
Prints a result row and appends it to results/compat.jsonl, so the compatibility of
LiteLLM, Mantle, bedrock-runtime /openai/v1, native Converse and the Claude Code CLI
can be compared side by side.
"""

from __future__ import annotations

import argparse
import json
import time
from pathlib import Path

from eam.cost import usage_cost
from eam.llm.routes import ROUTES, make_client
from eam.llm.types import CachePlan, Request, ToolSpec
from eam.models import load_models

WEATHER = ToolSpec("get_weather", "Get the current weather for a city.",
                   {"type": "object", "properties": {"city": {"type": "string"}}, "required": ["city"]})
PREFIX = "Reference notes. " + " ".join(f"Record {i}: sensor S{i % 13} reported value {i * 7 % 101}." for i in range(900))


def _user(text):
    return {"role": "user", "content": [{"text": text}]}


def run(route: str, model_key: str, embed_model: str | None, region: str | None) -> dict:
    model = load_models()[model_key]
    client = make_client(route, region=region)
    row: dict = {"route": route, "model": model_key, "model_id": model.id_for(route), "ts": time.strftime("%Y-%m-%d %H:%M:%S")}

    def call(req: Request):
        resp = client.converse(req)
        cost = resp.reported_cost_usd if resp.reported_cost_usd is not None else usage_cost(resp.usage, model)
        return resp, cost

    try:
        r, c = call(Request(model=model, system=[{"text": "You are terse."}],
                            messages=[_user("Reply with the single word: pong")], max_tokens=20))
        row["chat"] = "ok" if "pong" in r.text.lower() else f"unexpected: {r.text[:60]!r}"
        row["chat_usage"] = r.usage.to_dict()
    except Exception as exc:
        row["chat"] = f"error: {exc}"[:300]
        return row

    try:
        msgs = [_user("What is the weather in Paris right now? Use the tool.")]
        r, _ = call(Request(model=model, system=[{"text": "Use tools when needed."}], messages=msgs, tools=[WEATHER],
                            max_tokens=300))
        uses = r.tool_uses
        if not uses or uses[0]["name"] != "get_weather":
            row["tools"] = f"no tool call: {r.text[:80]!r}"
        else:
            msgs += [r.message, {"role": "user", "content": [{"toolResult": {
                "toolUseId": uses[0]["toolUseId"], "content": [{"text": "18 C and sunny"}]}}]}]
            r2, _ = call(Request(model=model, system=[{"text": "Use tools when needed."}], messages=msgs,
                                 tools=[WEATHER], max_tokens=200))
            row["tools"] = "ok" if "18" in r2.text else f"bad final answer: {r2.text[:80]!r}"
    except Exception as exc:
        row["tools"] = f"error: {exc}"[:300]

    try:
        # Agent-loop pattern: the second call appends to the first call's conversation (append-only),
        # with a rolling cache point on the newest message. A cache read on call 2 means caching works.
        msgs = [{"role": "user", "content": [{"text": PREFIX}, {"text": "Which sensor reported record 5? Id only."}]}]
        reads = []
        for follow_up in (None, "Which sensor reported record 6? Id only."):
            if follow_up:
                msgs = msgs + [r.message, _user(follow_up)]
            r, _ = call(Request(model=model, system=[{"text": "Answer from the notes."}], messages=msgs,
                                cache=CachePlan(system=True, message_indices=[len(msgs) - 1]), max_tokens=20))
            reads.append(r.usage.to_dict())
        row["cache"] = "hit" if reads[1]["cache_read_tokens"] > 0 else "no cache read on the follow-up call"
        row["cache_usage"] = reads
    except Exception as exc:
        row["cache"] = f"error: {exc}"[:300]

    if hasattr(client, "embed"):
        try:
            vec = client.embed(["hello world"], model=embed_model or "titan-embed")[0]
            row["embeddings"] = f"ok (dim {len(vec)})"
        except Exception as exc:
            row["embeddings"] = f"error: {exc}"[:300]
    else:
        row["embeddings"] = "n/a on this route"
    return row


def main(argv: list[str] | None = None) -> None:
    ap = argparse.ArgumentParser(prog="python -m eam.smoke")
    ap.add_argument("--route", required=True, choices=[r for r in ROUTES if r != "mock"])
    ap.add_argument("--model", required=True, help="profile key from config/models*.json, e.g. cc-haiku or haiku")
    ap.add_argument("--embed-model", default=None)
    ap.add_argument("--region", default=None)
    ap.add_argument("--out", default="results/compat.jsonl")
    args = ap.parse_args(argv)
    row = run(args.route, args.model, args.embed_model, args.region)
    Path(args.out).parent.mkdir(parents=True, exist_ok=True)
    with open(args.out, "a") as fh:
        fh.write(json.dumps(row) + "\n")
    for k in ("route", "model", "model_id", "chat", "tools", "cache", "embeddings"):
        print(f"{k:11s} {row.get(k, '-')}")
    if "cache_usage" in row:
        print(f"{'':11s} cache usage per call: {row['cache_usage']}")


if __name__ == "__main__":
    main()
