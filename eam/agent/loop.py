"""Reference agent loop (ReAct-style tool use over Bedrock Converse).

Techniques plug in through hooks; the loop itself stays minimal so that any
difference between runs comes from the techniques under test.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field
from typing import Any, Iterable

from eam.agent.context import AgentContext, Tool, ToolOutcome
from eam.cost import CostMeter
from eam.llm.render import estimate_request_tokens
from eam.llm.types import LLMClient, Message, Request
from eam.models import ModelProfile
from eam.store import ArtifactStore

DEFAULT_SYSTEM = (
    "You are a methodical agent solving a task with tools. Use tools to gather the information "
    "you need instead of guessing, and request only what you need. When you have the answer, "
    "reply without calling any tool and start your reply with 'FINAL ANSWER:'."
)


NUDGE = ("Your last reply contained no tool call and no final answer. Continue the task: call a tool, or give "
         "your final answer starting with '{marker}'.")


@dataclass
class RunResult:
    answer: str
    finished: bool
    steps: int
    meter: CostMeter
    peak_prompt_tokens: int
    history_rewrites: int
    events: list[dict[str, Any]] = field(default_factory=list)
    messages: list[Message] = field(default_factory=list)


def _fingerprint(msg: Message) -> str:
    return hashlib.sha1(json.dumps(msg, sort_keys=True, default=str).encode()).hexdigest()


def collect_tools(env_tools: Iterable[Tool], techniques: Iterable[Any], ctx: AgentContext) -> list[Tool]:
    tools: dict[str, Tool] = {}
    for tool in env_tools:
        tools[tool.spec.name] = tool
    for tech in techniques:
        for tool in tech.tools(ctx):
            tools.setdefault(tool.spec.name, tool)
    return list(tools.values())


def run_agent(
    task: str,
    *,
    llm: LLMClient,
    model: ModelProfile,
    env_tools: list[Tool],
    techniques: Iterable[Any] = (),
    aux_model: ModelProfile | None = None,
    models: dict[str, ModelProfile] | None = None,
    system_prompt: str = DEFAULT_SYSTEM,
    max_steps: int = 30,
    max_tokens: int = 2048,
    resources: dict[str, Any] | None = None,
    meter: CostMeter | None = None,
    store: ArtifactStore | None = None,
    tag: str = "main",
    initial_messages: list[Message] | None = None,
    final_marker: str | None = "FINAL ANSWER:",
    max_nudges: int = 2,
    context_limit: int | None = None,
) -> RunResult:
    techniques = list(techniques)
    ctx = AgentContext(
        task=task,
        llm=llm,
        model=model,
        aux_model=aux_model or model,
        models=models or {model.key: model},
        env_tools=env_tools,
        meter=meter or CostMeter(),
        store=store or ArtifactStore(),
        resources=resources or {},
        techniques=techniques,
        tag=tag,
    )
    ctx.context_limit = context_limit
    tools = collect_tools(env_tools, techniques, ctx)
    tool_map = {t.spec.name: t for t in tools}
    # Static instructions only: the system prompt must not change between calls.
    addenda = [a for a in (t.system_addendum() for t in techniques) if a]
    system_text = "\n\n".join([system_prompt, *addenda])
    ctx.system_text = system_text

    for tech in techniques:
        tech.on_session_start(ctx)
    if initial_messages:  # continue from an existing history (e.g. a FoldAgent branch inherits MAIN's context)
        ctx.messages.extend(initial_messages)
    else:
        ctx.messages.append({"role": "user", "content": [{"text": "\n\n".join([ctx.task_header(), *ctx.preamble])}]})

    answer, finished, rewrites, nudges = "", False, 0, 0
    token_ratio = 1.0
    prev_snapshot: list[str] = []
    step = 0
    for step in range(1, max_steps + 1):
        ctx.step = step
        for tech in techniques:
            tech.before_call(ctx)
        if ctx.stop_reason:
            break

        snapshot = [_fingerprint(m) for m in ctx.messages]
        if prev_snapshot and snapshot[: len(prev_snapshot)] != prev_snapshot:
            rewrites += 1  # earlier context changed => any cached prefix past that point is lost
            ctx.log("history_rewrite")

        req = Request(
            model=ctx.model,
            system=[{"text": system_text}],
            messages=ctx.messages,
            tools=[t.spec for t in tools],
            max_tokens=max_tokens,
            tag=tag,
        )
        for tech in techniques:
            req = tech.render(ctx, req)
        estimate = estimate_request_tokens(req) if context_limit else 0
        if context_limit and estimate * token_ratio > context_limit:
            ctx.stop_reason = "context_overflow"  # what a real API does when the window is exceeded
            ctx.log("context_overflow", tokens=int(estimate * token_ratio), limit=context_limit, when="before_call")
            break

        resp = llm.converse(req)
        if context_limit:
            # The character-based estimate undercounts dense text (numbers, ids); calibrate it with the real count,
            # and treat a request whose real size exceeded the window as rejected.
            if estimate:
                token_ratio = max(1.0, resp.usage.prompt_tokens / estimate)
            if resp.usage.prompt_tokens > context_limit:
                ctx.meter.record(tag, req.model, resp.usage, resp.latency_ms, resp.reported_cost_usd)
                ctx.stop_reason = "context_overflow"
                ctx.log("context_overflow", tokens=resp.usage.prompt_tokens, limit=context_limit, when="actual")
                break
        ctx.meter.record(tag, req.model, resp.usage, resp.latency_ms, resp.reported_cost_usd)
        ctx.last_prompt_tokens = resp.usage.prompt_tokens
        ctx.peak_prompt_tokens = max(ctx.peak_prompt_tokens, ctx.last_prompt_tokens)
        prev_snapshot = snapshot + [_fingerprint(resp.message)]
        ctx.messages.append(resp.message)
        for tech in techniques:
            tech.after_call(ctx, resp)

        uses = resp.tool_uses
        if not uses:
            # A reply with no tool call and no final-answer marker is malformed (degenerate or truncated output).
            # Re-prompt a bounded number of times; this rule is identical for every technique and is counted.
            if final_marker and final_marker not in resp.text and nudges < max_nudges and tag == "main":
                nudges += 1
                ctx.log("nudge")
                ctx.messages.append({"role": "user", "content": [{"text": NUDGE.format(marker=final_marker)}]})
                continue
            answer, finished = resp.text, True
            break

        outcomes: list[ToolOutcome] = []
        for tu in uses:
            tool = tool_map.get(tu["name"])
            is_error = False
            if tool is None:
                text, is_error = f"Error: unknown tool '{tu['name']}'.", True
            else:
                try:
                    text = tool.handler(tu.get("input") or {}, ctx)
                except Exception as exc:  # tool errors are fed back to the model
                    text, is_error = f"Error: {exc}", True
            outcome = ToolOutcome(tu["toolUseId"], tu["name"], tu.get("input") or {}, text, is_error)
            for tech in techniques:
                outcome = tech.on_tool_result(ctx, outcome)
            outcomes.append(outcome)
        ctx.last_tool_error = any(o.is_error for o in outcomes)
        ctx.messages.append({"role": "user", "content": [o.to_block() for o in outcomes]})
        if ctx.stop_reason:
            if ctx.final_answer is not None:
                answer, finished = ctx.final_answer, True
            break

    for tech in techniques:
        tech.on_session_end(ctx, answer)
    if ctx.stop_reason:
        ctx.log("stopped", reason=ctx.stop_reason)

    return RunResult(
        answer=answer,
        finished=finished,
        steps=step,
        meter=ctx.meter,
        peak_prompt_tokens=ctx.peak_prompt_tokens,
        history_rewrites=rewrites,
        events=ctx.events,
        messages=ctx.messages,
    )
