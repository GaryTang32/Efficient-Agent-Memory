"""AutoMemory as an MCP server (stdio, JSON-RPC 2.0, no dependencies):

    python -m eam.mcp_server            # store: $EAM_MEMORY_DIR (default ~/.eam-memory/default)

Register it with any MCP client, e.g. Claude Code (`.mcp.json`):

    {"mcpServers": {"automem": {"command": "python", "args": ["-m", "eam.mcp_server"],
                                "env": {"EAM_MEMORY_DIR": "/path/to/project-memory"}}}}

Tools: write_note, read_notes, recall (notes for the start of a session), save_session (autosave a session's
result), offload / read_artifact (recoverable offload of large text), context_budget (should the caller compact,
how much may the next step add), compact (ReSum's official summary prompt: returned for the caller's own model to
run, or executed here when $EAM_MEMORY_ROUTE names a route such as claude-cli and $EAM_MEMORY_MODEL a model key).
"""

from __future__ import annotations

import json
import os
import sys
from typing import Any

from eam.memory_skill import MemorySkill
from eam.techniques.third_party import resum as P

PROTOCOL = "2024-11-05"

TOOLS: list[dict[str, Any]] = MemorySkill.tool_specs() + [
    {"name": "recall", "description": "Notes saved in earlier sessions, formatted for the start of a new session. "
     "Call this first in every session.", "input_schema": {"type": "object", "properties": {}}},
    {"name": "save_session", "description": "Save the final result of this session so later sessions recall it.",
     "input_schema": {"type": "object", "properties": {"answer": {"type": "string"}, "label": {"type": "string"}},
                      "required": ["answer"]}},
    {"name": "offload", "description": "Store a large text outside the context; returns an artifact:// pointer "
     "to keep in its place (read it back with read_artifact).",
     "input_schema": {"type": "object", "properties": {"text": {"type": "string"}, "label": {"type": "string"}},
                      "required": ["text"]}},
    {"name": "context_budget", "description": "Given the current prompt size and window (tokens): whether to "
     "compact now, and how many tokens the next step may add before reaching the safety margin.",
     "input_schema": {"type": "object", "properties": {"context_tokens": {"type": "integer"},
                                                       "window": {"type": "integer"}},
                      "required": ["context_tokens"]}},
    {"name": "compact", "description": "Compaction with ReSum's official prompt. Returns the summary prompt for "
     "your model (or, if the server has an LLM route configured, the reset message to replace the history with).",
     "input_schema": {"type": "object", "properties": {"question": {"type": "string"},
                                                       "history": {"type": "string"},
                                                       "last_summary": {"type": "string"}},
                      "required": ["question", "history"]}},
]


def _summarizer():
    route = os.environ.get("EAM_MEMORY_ROUTE")
    if not route:
        return None
    from eam.llm.routes import make_client
    from eam.llm.types import Request
    from eam.models import load_models

    model = load_models(os.environ.get("EAM_MODELS_CONFIG"))[os.environ.get("EAM_MEMORY_MODEL", "cc-haiku")]
    client = make_client(route)

    def summarize(prompt: str) -> str:
        req = Request(model=model, system=[], messages=[{"role": "user", "content": [{"text": prompt}]}],
                      max_tokens=4096, temperature=0.6, tag="aux:resum")
        return client.converse(req).text

    return summarize


class Server:
    def __init__(self, skill: MemorySkill):
        self.skill = skill

    def call(self, name: str, args: dict[str, Any]) -> str:
        s = self.skill
        if name in ("write_note", "read_notes", "read_artifact"):
            return s.call_tool(name, args)
        if name == "recall":
            return s.session_preamble() or "No notes yet."
        if name == "save_session":
            s.save_session(str(args["answer"]), args.get("label"))
            return "Saved."
        if name == "offload":
            return s.offload(str(args["text"]), str(args.get("label", "")))
        if name == "context_budget":
            window = int(args.get("window") or s.window)
            tokens = int(args["context_tokens"])
            return json.dumps({"compact_now": tokens >= s.trigger * window,
                               "next_step_may_add": max(0, int(s.guard * window) - tokens),
                               "trigger_tokens": int(s.trigger * window), "window": window})
        if name == "compact":
            last = args.get("last_summary") or ""
            template = P.QUERY_SUMMARY_PROMPT_LAST if last else P.QUERY_SUMMARY_PROMPT
            prompt = (template.replace("{{{question}}}", str(args["question"]))
                      .replace("{{{recent_history_messages}}}", str(args["history"]))
                      .replace("{{{last_summary}}}", last))
            if s.summarize is None:
                return ("Run this prompt with your model, then replace the conversation with:\n"
                        + P.NEW_OBSERVATION.format(question=args["question"], summary="<summary>…</summary>")
                        + "\n\n--- PROMPT ---\n" + prompt)
            msgs = s.maybe_compact([{"role": "user", "content": str(args["history"])}],
                                   context_tokens=10**12, question=str(args["question"]))
            return msgs[-1]["content"]
        raise ValueError(f"unknown tool '{name}'")

    def handle(self, msg: dict[str, Any]) -> dict[str, Any] | None:
        method, mid = msg.get("method"), msg.get("id")
        if mid is None:  # notification (e.g. notifications/initialized)
            return None
        try:
            if method == "initialize":
                result = {"protocolVersion": PROTOCOL, "capabilities": {"tools": {}},
                          "serverInfo": {"name": "eam-automem", "version": "1.0"}}
            elif method == "tools/list":
                result = {"tools": [{"name": t["name"], "description": t["description"],
                                     "inputSchema": t["input_schema"]} for t in TOOLS]}
            elif method == "tools/call":
                p = msg.get("params") or {}
                try:
                    text, err = self.call(p.get("name", ""), p.get("arguments") or {}), False
                except Exception as exc:  # tool errors go back to the model, not as protocol errors
                    text, err = f"Error: {exc}", True
                result = {"content": [{"type": "text", "text": text}], "isError": err}
            elif method == "ping":
                result = {}
            else:
                return {"jsonrpc": "2.0", "id": mid, "error": {"code": -32601, "message": f"unknown method {method}"}}
        except Exception as exc:
            return {"jsonrpc": "2.0", "id": mid, "error": {"code": -32603, "message": str(exc)}}
        return {"jsonrpc": "2.0", "id": mid, "result": result}


def main() -> None:
    root = os.environ.get("EAM_MEMORY_DIR", os.path.expanduser("~/.eam-memory/default"))
    window = int(os.environ.get("EAM_MEMORY_WINDOW", 200_000))
    server = Server(MemorySkill(root, window=window, summarize=_summarizer()))
    for line in sys.stdin:
        line = line.strip()
        if not line:
            continue
        try:
            msg = json.loads(line)
        except json.JSONDecodeError:
            out = {"jsonrpc": "2.0", "id": None, "error": {"code": -32700, "message": "parse error"}}
        else:
            out = server.handle(msg)
        if out is not None:
            sys.stdout.write(json.dumps(out) + "\n")
            sys.stdout.flush()


if __name__ == "__main__":
    main()
