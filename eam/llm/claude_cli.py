"""Claude Code CLI as a stateless LLM backend (no Bedrock or API key needed).

Each ``converse`` call runs ``claude -p`` once with Claude Code's own tools,
MCP servers and settings switched off, and the system prompt replaced by ours.
The conversation is sent as a stream-json user message with one text block
per conversation block, so Claude Code's automatic prompt caching can hit
across calls (verified: a second call with an extended transcript read the
earlier blocks from cache). Our own CachePlan is not applied on this route —
Claude Code places cache breakpoints itself.

Tools are exposed through the text protocol in ``eam.llm.text_tools``.
Token usage and Claude Code's own ``total_cost_usd`` are recorded.
"""

from __future__ import annotations

import json
import os
import subprocess
import time
from typing import Any

from eam.llm.text_tools import parse_tool_calls, render_message_blocks, tool_instructions, transcript_preamble
from eam.llm.types import Request, Response, Usage


class ClaudeCLIError(RuntimeError):
    pass


class ClaudeCLIClient:
    route = "claude-cli"

    def __init__(self, binary: str | None = None, *, timeout_s: float | None = None, retries: int = 2,
                 extra_args: list[str] | None = None, env: dict[str, str] | None = None):
        self.binary = binary or os.environ.get("EAM_CLAUDE_BIN", "claude")
        self.timeout_s = timeout_s or float(os.environ.get("EAM_CLAUDE_TIMEOUT", 240))
        self.retries = retries
        self.extra_args = extra_args or []
        self.env = env

    def build_command(self, req: Request) -> tuple[list[str], str]:
        system = "\n\n".join(b["text"] for b in req.system if "text" in b)
        parts = [system, transcript_preamble()]
        if req.tools:
            parts.append(tool_instructions(req.tools))
        if req.prefill:  # no assistant prefill on this route: ask for the same opening instead
            parts.append(f"Begin your reply exactly with: {req.prefill}")
        system_prompt = "\n\n".join(p for p in parts if p)
        blocks = render_message_blocks(req.messages)
        payload = {"type": "user", "message": {"role": "user",
                                                "content": [{"type": "text", "text": b} for b in blocks]}}
        cmd = [
            self.binary, "-p",
            "--input-format", "stream-json", "--output-format", "stream-json", "--verbose",
            "--tools", "",
            "--system-prompt", system_prompt,
            "--model", req.model.id_for(self.route),
            "--no-session-persistence", "--strict-mcp-config", "--setting-sources", "",
            *self.extra_args,
        ]
        return cmd, json.dumps(payload) + "\n"

    def _run(self, cmd: list[str], stdin: str, max_tokens: int = 8192) -> dict[str, Any]:
        # Cap the reply length: without it a degenerate (repeating) reply can run to the model's 128K-token
        # maximum and time out. Generous floor so that normal replies are never cut.
        env = {**os.environ, "CLAUDE_CODE_MAX_OUTPUT_TOKENS": str(max(8192, max_tokens)), **(self.env or {})}
        last = ""
        for attempt in range(self.retries + 1):
            try:
                proc = subprocess.run(cmd, input=stdin, capture_output=True, text=True,
                                      timeout=self.timeout_s, env=env)
            except subprocess.TimeoutExpired:
                last = f"timed out after {self.timeout_s}s"
                continue
            result = None
            for line in proc.stdout.splitlines():
                try:
                    obj = json.loads(line)
                except json.JSONDecodeError:
                    continue
                if obj.get("type") == "result":
                    result = obj
            if result and not result.get("is_error"):
                return result
            last = (result or {}).get("result") or proc.stderr[-500:] or proc.stdout[-500:]
            if attempt < self.retries:
                time.sleep(2 * (attempt + 1))
        raise ClaudeCLIError(f"claude -p failed: {last}")

    def converse(self, req: Request) -> Response:
        cmd, stdin = self.build_command(req)
        t0 = time.perf_counter()
        result = self._run(cmd, stdin, req.max_tokens)
        text = result.get("result") or ""
        visible, uses = self._parse(req, text)
        usage = self._usage(result)
        cost = result.get("total_cost_usd") or 0.0
        if req.tools and not uses and not visible:
            # Empty or unparseable reply (rare): ask once more instead of ending the run with no answer.
            cmd2 = list(cmd)
            i = cmd2.index("--system-prompt") + 1
            cmd2[i] += ("\n\nYour previous reply could not be parsed. Reply with either <tool_call> blocks "
                        "in the exact format above, or your final answer as plain text.")
            result = self._run(cmd2, stdin, req.max_tokens)
            text = result.get("result") or ""
            visible, uses = self._parse(req, text)
            usage = usage + self._usage(result)
            cost += result.get("total_cost_usd") or 0.0
        wall_ms = (time.perf_counter() - t0) * 1000
        content: list[dict[str, Any]] = ([{"text": visible}] if visible else []) + uses
        if not content:
            content = [{"text": ""}]
        stop = "tool_use" if uses else ("max_tokens" if result.get("stop_reason") == "max_tokens" else "end_turn")
        return Response({"role": "assistant", "content": content}, stop, usage,
                        float(result.get("duration_api_ms") or wall_ms), req.model.key,
                        reported_cost_usd=cost, raw_text=text)

    @staticmethod
    def _parse(req: Request, text: str) -> tuple[str, list[dict[str, Any]]]:
        if req.prefill and text.startswith(req.prefill):
            text = text[len(req.prefill):]
        for s in req.stop:  # emulate stop sequences
            text = text.split(s, 1)[0]
        return parse_tool_calls(text, req.tools) if req.tools else (text.strip(), [])

    @staticmethod
    def _usage(result: dict[str, Any]) -> Usage:
        u = result.get("usage") or {}
        return Usage(int(u.get("input_tokens") or 0), int(u.get("output_tokens") or 0),
                     int(u.get("cache_read_input_tokens") or 0), int(u.get("cache_creation_input_tokens") or 0))
