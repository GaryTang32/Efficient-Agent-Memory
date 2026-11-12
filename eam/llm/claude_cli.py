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

import datetime
import json
import os
import re
import subprocess
import time
from typing import Any

from eam.llm.text_tools import parse_tool_calls, render_message_blocks, tool_instructions, transcript_preamble
from eam.cost import usage_cost
from eam.llm.types import Request, Response, Usage


DEFAULT_OUTPUT_CAP = 8192


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
        self.wait_for_limit = os.environ.get("EAM_CLAUDE_WAIT_FOR_LIMIT", "1") != "0"
        self.output_cap = int(os.environ.get("EAM_CLAUDE_MAX_OUTPUT", DEFAULT_OUTPUT_CAP))

    # our variable -> the Claude Code variable it pins for the child processes
    PINS = {"EAM_CLAUDE_THINKING_TOKENS": "MAX_THINKING_TOKENS", "EAM_CLAUDE_EFFORT": "CLAUDE_EFFORT"}

    def child_env(self, max_tokens: int = 0) -> dict[str, str]:
        """Environment of a ``claude -p`` call. The reply cap bounds what a runaway reply costs (see ``_run``).
        Thinking budget and effort are inherited from the launching process unless pinned: ``EAM_CLAUDE_THINKING_TOKENS``
        and ``EAM_CLAUDE_EFFORT`` set them, and the value ``unset`` removes them."""
        env = {**os.environ, **(self.env or {})}
        env["CLAUDE_CODE_MAX_OUTPUT_TOKENS"] = str(max(self.output_cap, max_tokens))
        for ours, theirs in self.PINS.items():
            pin = os.environ.get(ours)
            if pin is None:
                continue
            if pin.strip().lower() in ("", "unset", "none"):
                env.pop(theirs, None)
            else:
                env[theirs] = pin.strip()
        return env

    _versions: dict[str, str | None] = {}

    def cli_version(self) -> str | None:
        if self.binary not in self._versions:
            try:
                out = subprocess.run([self.binary, "--version"], capture_output=True, text=True, timeout=30).stdout
                self._versions[self.binary] = out.strip().split()[0] if out.strip() else None
            except (OSError, subprocess.SubprocessError):
                self._versions[self.binary] = None
        return self._versions[self.binary]

    def run_settings(self) -> dict[str, Any]:
        """What changes a run's cost and behaviour besides the request, recorded in every result row: the CLI
        version (it updates itself), the reply cap, and the thinking settings the child processes run with."""
        env = self.child_env()
        return {"cli_version": self.cli_version(), "output_cap": self.output_cap,
                "thinking_tokens": env.get("MAX_THINKING_TOKENS"), "effort": env.get("CLAUDE_EFFORT")}

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

    @staticmethod
    def _seconds_until_reset(message: str, now: datetime.datetime | None = None) -> float | None:
        """For Claude Code's usage-limit message ("You've hit your session limit · resets 8:10pm (UTC)"), the
        seconds until the stated reset (next occurrence, UTC); None for any other error."""
        m = re.search(r"limit\W+resets (\d{1,2})(?::(\d{2}))?\s*(am|pm)", message, re.I)
        if not m:
            return None
        hour, minute = int(m.group(1)) % 12 + (12 if m.group(3).lower() == "pm" else 0), int(m.group(2) or 0)
        now = now or datetime.datetime.now(datetime.timezone.utc)
        reset = now.replace(hour=hour, minute=minute, second=0, microsecond=0)
        if reset <= now:
            reset += datetime.timedelta(days=1)
        return (reset - now).total_seconds()

    def _run(self, cmd: list[str], stdin: str, max_tokens: int = 8192) -> dict[str, Any]:
        # Cap the reply length. Tools are text on this route, and in about 1% of calls the model loops (it repeats
        # a tool call in its native syntax) until it reaches the cap; Claude Code then continues in a second
        # internal turn and the loop's output is billed and discarded. At the earlier 32K cap these replies were
        # 22-26% of all measured cost (2026-11 validation round); at 8K one costs about a quarter as much and the
        # second turn still returns a usable reply (measured). Replies that reach the cap are counted (`_cap_hits`).
        # The prompt size is read from the first request, so the continuation's summed usage does not inflate it.
        env = self.child_env(max_tokens)
        last = ""
        # what failed attempts used: error results (usage and reported cost) and timed-out calls (usage of the
        # assistant messages streamed before the timeout, priced from usage); added to the returned result
        failed = dict(self._NO_FAILURES)
        for attempt in range(self.retries + 1):
            try:
                proc = subprocess.run(cmd, input=stdin, capture_output=True, text=True,
                                      timeout=self.timeout_s, env=env)
            except subprocess.TimeoutExpired as exc:
                last = f"timed out after {self.timeout_s}s"
                out = exc.stdout.decode(errors="replace") if isinstance(exc.stdout, bytes) else (exc.stdout or "")
                failed["_failed_attempts"] += 1
                failed["_unpriced_usage"] = failed["_unpriced_usage"] + self._scan(out)[2]
                continue
            result, first_prompt, _ = self._scan(proc.stdout)
            if result is not None:
                result = {**result, "_first_prompt": first_prompt}
            if result and not result.get("is_error"):
                # with tools off, every extra internal turn is a continuation after a reply that reached the cap
                return {**result, **failed, "_cap_hits": int(result.get("num_turns") or 1) - 1}
            if result and "output token maximum" in str(result.get("result", "")):
                # A runaway reply hit the output cap. Hand back an empty, truncated reply (its usage is still
                # billed) so the agent loop handles it like any other malformed turn instead of failing the run.
                return {**result, "result": "", "is_error": False, "stop_reason": "max_tokens", **failed,
                        "_cap_hits": max(1, int(result.get("num_turns") or 1) - 1)}
            if result:
                failed["_failed_attempts"] += 1
                failed["_failed_usage"] = failed["_failed_usage"] + self._usage(result)
                failed["_failed_cost"] += float(result.get("total_cost_usd") or 0.0)
            last = (result or {}).get("result") or proc.stderr[-500:] or proc.stdout[-500:]
            wait = self._seconds_until_reset(str(last))
            if wait is not None and self.wait_for_limit and wait < 6 * 3600:
                # usage-limit window: sleep until the stated reset and try again (not counted as an attempt), so a
                # batch pauses instead of turning every queued run into an error row
                time.sleep(wait + 120)
                again = self._run(cmd, stdin, max_tokens)
                return {**again, "_failed_attempts": again["_failed_attempts"] + failed["_failed_attempts"] - 1,
                        "_failed_usage": again["_failed_usage"] + failed["_failed_usage"],
                        "_failed_cost": again["_failed_cost"] + failed["_failed_cost"],
                        "_unpriced_usage": again["_unpriced_usage"] + failed["_unpriced_usage"]}
            if attempt < self.retries:
                time.sleep(2 * (attempt + 1))
        raise ClaudeCLIError(f"claude -p failed: {last}")

    _NO_FAILURES = {"_failed_attempts": 0, "_failed_usage": Usage(), "_failed_cost": 0.0, "_unpriced_usage": Usage(),
                    "_cap_hits": 0}

    @classmethod
    def _scan(cls, stdout: str) -> tuple[dict[str, Any] | None, int | None, Usage]:
        """The stream's result event; the prompt size of its first request (from the first assistant message's
        usage); and the summed usage of its assistant messages (one per message id)."""
        result, first_prompt, per_message = None, None, {}
        for line in stdout.splitlines():
            try:
                obj = json.loads(line)
            except json.JSONDecodeError:
                continue
            if obj.get("type") == "result":
                result = obj
            elif obj.get("type") == "assistant" and isinstance(obj.get("message"), dict):
                msg = obj["message"]
                u = cls._usage({"usage": msg.get("usage")})
                per_message[msg.get("id") or len(per_message)] = u
                if first_prompt is None and u.prompt_tokens:
                    first_prompt = u.prompt_tokens
        total = Usage()
        for u in per_message.values():
            total = total + u
        return result, first_prompt, total

    def converse(self, req: Request) -> Response:
        cmd, stdin = self.build_command(req)
        t0 = time.perf_counter()
        result = {**self._NO_FAILURES, **self._run(cmd, stdin, req.max_tokens)}
        text = result.get("result") or ""
        visible, uses = self._parse(req, text)
        usage = self._usage(result) + result["_failed_usage"] + result["_unpriced_usage"]
        context_tokens = self._context_size(result)
        # internal continuation turns and failed attempts count as retries
        retries = int(result.get("num_turns") or 1) - 1 + result["_failed_attempts"]
        cap_hits = result["_cap_hits"]
        reported = result.get("total_cost_usd")  # None (not 0) when absent, so the meter prices the usage
        cost = (None if reported is None else
                float(reported) + result["_failed_cost"] + usage_cost(result["_unpriced_usage"], req.model))
        if req.tools and not uses and not visible:
            # Empty or unparseable reply (rare): ask once more instead of ending the run with no answer.
            cmd2 = list(cmd)
            i = cmd2.index("--system-prompt") + 1
            cmd2[i] += ("\n\nYour previous reply could not be parsed. Reply with either <tool_call> blocks "
                        "in the exact format above, or your final answer as plain text.")
            result = {**self._NO_FAILURES, **self._run(cmd2, stdin, req.max_tokens)}
            text = result.get("result") or ""
            visible, uses = self._parse(req, text)
            context_tokens = self._context_size(result)
            retries += int(result.get("num_turns") or 1) + result["_failed_attempts"]
            cap_hits += result["_cap_hits"]
            extra = self._usage(result) + result["_failed_usage"] + result["_unpriced_usage"]
            reported2 = result.get("total_cost_usd")
            cost2 = (usage_cost(extra, req.model) if reported2 is None else float(reported2) + result["_failed_cost"]
                     + usage_cost(result["_unpriced_usage"], req.model))
            cost = (usage_cost(usage, req.model) if cost is None else cost) + cost2
            usage = usage + extra
        wall_ms = (time.perf_counter() - t0) * 1000
        content: list[dict[str, Any]] = ([{"text": visible}] if visible else []) + uses
        if not content:
            content = [{"text": ""}]
        stop = "tool_use" if uses else ("max_tokens" if result.get("stop_reason") == "max_tokens" else "end_turn")
        return Response({"role": "assistant", "content": content}, stop, usage,
                        float(result.get("duration_api_ms") or wall_ms), req.model.key,
                        reported_cost_usd=cost, raw_text=text, context_tokens=context_tokens, retries=retries,
                        cap_hits=cap_hits)

    @staticmethod
    def _parse(req: Request, text: str) -> tuple[str, list[dict[str, Any]]]:
        if req.prefill and text.startswith(req.prefill):
            text = text[len(req.prefill):]
        for s in req.stop:  # emulate stop sequences
            text = text.split(s, 1)[0]
        return parse_tool_calls(text, req.tools) if req.tools else (text.strip(), [])

    @classmethod
    def _context_size(cls, result: dict[str, Any]) -> int:
        """Prompt size of the request itself: the first assistant message's prompt usage when the stream has it.
        Otherwise, with T internal turns Claude Code reports T·P + (earlier turns' output) prompt tokens, so
        P ≈ (prompt − output) / T (biased when the last turn's output is large)."""
        if result.get("_first_prompt"):
            return int(result["_first_prompt"])
        u = cls._usage(result)
        turns = max(1, int(result.get("num_turns") or 1))
        if turns == 1:
            return u.prompt_tokens
        return max(0, u.prompt_tokens - u.output_tokens) // turns

    @staticmethod
    def _usage(result: dict[str, Any]) -> Usage:
        u = result.get("usage") or {}
        return Usage(int(u.get("input_tokens") or 0), int(u.get("output_tokens") or 0),
                     int(u.get("cache_read_input_tokens") or 0), int(u.get("cache_creation_input_tokens") or 0))
