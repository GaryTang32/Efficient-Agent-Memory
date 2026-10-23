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


GAUGE = "[Context used: about {used:,} of {limit:,} tokens]"
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
    tool_calls: int = 0  # tool calls issued by this agent (not by sub-agents), counted as they happen


def _fingerprint(msg: Message) -> str:
    return hashlib.sha1(json.dumps(msg, sort_keys=True, default=str).encode()).hexdigest()


OFFLOADED = ("{preview}\n…[This step's tool output exceeded the per-step budget of {budget:,} tokens. The full output "
             "({tokens:,} tokens) is stored at {pointer}; read it with read_artifact (use offset/length to page), "
             "preferably one item per step.]")


def _apply_step_budget(ctx: AgentContext, outcomes: list[ToolOutcome], budget: int) -> None:
    """Recoverable offload at the harness level (Manus "file system as context"; production harnesses such as
    Trae Agent cap tool output too): within one step, outputs are kept in full until `budget` tokens; any further
    output is stored in the artifact store and replaced by a short preview plus a pointer. Same rule for every
    technique; it runs after the techniques' own on_tool_result hooks."""
    from eam.tokens import estimate_tokens, truncate_to_tokens

    used = 0
    for o in outcomes:
        n = estimate_tokens(o.text)
        if used + n <= budget:
            used += n
            continue
        aid = ctx.store.put(o.text, label=f"{o.name} {o.input}")
        o.text = OFFLOADED.format(preview=truncate_to_tokens(o.text, 150), budget=budget, tokens=n,
                                  pointer=ctx.store.pointer(aid))
        used += estimate_tokens(o.text)
        ctx.log("step_budget_offload", artifact=aid, tokens=n)


def collect_tools(env_tools: Iterable[Tool], techniques: Iterable[Any], ctx: AgentContext) -> list[Tool]:
    tools: dict[str, Tool] = {}
    for tool in env_tools:
        tools[tool.spec.name] = tool
    for tech in techniques:
        for tool in tech.tools(ctx):
            tools.setdefault(tool.spec.name, tool)
    return list(tools.values())


class _PromptSizer:
    """Predicts a request's real prompt size from the character-based estimate: real ≈ a + b · estimate.

    `b` corrects the estimator's undercount of dense text (~1.4× for numeric tables); `a` is fixed per-call
    overhead the estimate does not see (Claude Code adds ~1.3K tokens per call). Fitted by least squares on this
    session's (estimate, real) pairs. With a single pair the whole gap is treated as overhead (b = 1): scaling a
    small first call's gap multiplicatively would wrongly reject the next, larger request.
    """

    def __init__(self):
        self.pairs: list[tuple[int, int]] = []

    def observe(self, estimate: int, real: int) -> None:
        self.pairs.append((estimate, real))

    def predict(self, estimate: int) -> int:
        if not self.pairs:
            return estimate
        xs = [e for e, _ in self.pairs[-20:]]
        ys = [r for _, r in self.pairs[-20:]]
        b = 1.0
        if len(xs) >= 2 and max(xs) - min(xs) >= 2000:
            mx, my = sum(xs) / len(xs), sum(ys) / len(ys)
            b = sum((x - mx) * (y - my) for x, y in zip(xs, ys)) / sum((x - mx) ** 2 for x in xs)
            b = min(2.0, max(1.0, b))
        a = max(0.0, sum(y - b * x for x, y in zip(xs, ys)) / len(xs))
        return int(a + b * estimate)


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
    context_gauge: bool = True,
    step_observation_budget: int | None = None,
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
    if step_observation_budget:  # harness-level offload needs a way back to the stored output
        from eam.techniques.common import read_artifact_tool

        env_tools = [*env_tools, read_artifact_tool()]
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
    n_tool_calls = 0
    sizer = _PromptSizer()
    prev_snapshot: list[str] = []
    step = 0
    for step in range(1, max_steps + 1):
        ctx.step = step
        for tech in techniques:
            tech.before_call(ctx)
        if ctx.stop_reason:
            break


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
        if context_limit and context_gauge:
            # Environment feedback, like the context meter real harnesses show: how full the window is right now.
            # Appended to the newest message only, so it never rewrites cached history; identical for every technique.
            used = sizer.predict(estimate)
            ctx.messages[-1]["content"].append({"text": GAUGE.format(used=used, limit=context_limit)})
            estimate = estimate_request_tokens(req)
        snapshot = [_fingerprint(m) for m in ctx.messages]
        if prev_snapshot and snapshot[: len(prev_snapshot)] != prev_snapshot:
            rewrites += 1  # earlier context changed => any cached prefix past that point is lost
            ctx.log("history_rewrite")
        if context_limit and sizer.predict(estimate) > context_limit:
            ctx.stop_reason = "context_overflow"  # what a real API does when the window is exceeded
            ctx.log("context_overflow", tokens=sizer.predict(estimate), limit=context_limit, when="before_call")
            break

        resp = llm.converse(req)
        if resp.retries:  # backend retries / internal continuation turns: billed more than one prompt
            ctx.log("llm_retry", retries=resp.retries, billed_prompt_tokens=resp.usage.prompt_tokens,
                    prompt_size=resp.prompt_size)
        if context_limit:
            # The character-based estimate undercounts dense text (numbers, ids); calibrate it with the real count,
            # and treat a request whose real size exceeded the window as rejected.
            if estimate:
                sizer.observe(estimate, resp.prompt_size)
            if resp.prompt_size > context_limit:
                ctx.meter.record(tag, req.model, resp.usage, resp.latency_ms, resp.reported_cost_usd)
                ctx.stop_reason = "context_overflow"
                ctx.log("context_overflow", tokens=resp.prompt_size, limit=context_limit, when="actual")
                break
        ctx.meter.record(tag, req.model, resp.usage, resp.latency_ms, resp.reported_cost_usd)
        ctx.last_prompt_tokens = resp.prompt_size
        ctx.peak_prompt_tokens = max(ctx.peak_prompt_tokens, ctx.last_prompt_tokens)
        prev_snapshot = snapshot + [_fingerprint(resp.message)]
        ctx.messages.append(resp.message)
        for tech in techniques:
            tech.after_call(ctx, resp)

        uses = resp.tool_uses
        n_tool_calls += len(uses)
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
        if step_observation_budget:
            _apply_step_budget(ctx, outcomes, step_observation_budget)
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
        tool_calls=n_tool_calls,
    )
