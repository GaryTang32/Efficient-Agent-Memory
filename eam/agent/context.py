"""Shared state handed to every technique hook during an agent run."""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any, Callable

from eam.cost import CostMeter
from eam.llm.types import LLMClient, Message, Request, ToolSpec
from eam.models import ModelProfile
from eam.store import ArtifactStore
from eam.tokens import estimate_block_tokens

if TYPE_CHECKING:
    from eam.techniques.base import Technique


@dataclass
class Tool:
    spec: ToolSpec
    handler: Callable[[dict[str, Any], "AgentContext"], str]


@dataclass
class ToolOutcome:
    tool_use_id: str
    name: str
    input: dict[str, Any]
    text: str
    is_error: bool = False

    def to_block(self) -> dict[str, Any]:
        # `status` is omitted on purpose: not every Bedrock model accepts it.
        return {"toolResult": {"toolUseId": self.tool_use_id, "content": [{"text": self.text}]}}


@dataclass
class AgentContext:
    task: str
    llm: LLMClient
    model: ModelProfile
    aux_model: ModelProfile
    models: dict[str, ModelProfile]
    env_tools: list[Tool]
    meter: CostMeter = field(default_factory=CostMeter)
    store: ArtifactStore = field(default_factory=ArtifactStore)
    resources: dict[str, Any] = field(default_factory=dict)
    techniques: list["Technique"] = field(default_factory=list)
    messages: list[Message] = field(default_factory=list)
    preamble: list[str] = field(default_factory=list)  # extra sections for the first user message
    state: dict[str, Any] = field(default_factory=dict)  # per-technique scratch space
    events: list[dict[str, Any]] = field(default_factory=list)
    tag: str = "main"
    step: int = 0
    last_prompt_tokens: int = 0
    peak_prompt_tokens: int = 0
    last_tool_error: bool = False
    context_limit: int | None = None  # simulated context window (tokens)
    system_text: str = ""  # the run's full system prompt (FoldAgent branches reuse it)
    stop_reason: str | None = None  # a technique sets this to end the run (turn limit, branch return)
    final_answer: str | None = None  # answer to report when a technique ends the run

    def task_header(self) -> str:
        """First line of every rebuilt context; keeps the task statement stable."""
        return f"Task: {self.task}"

    def log(self, kind: str, **data: Any) -> None:
        self.events.append({"step": self.step, "kind": kind, **data})

    def call_aux(self, prompt: str, *, purpose: str, max_tokens: int = 1024,
                 system: str = "You are a precise assistant. Follow the instructions exactly.",
                 temperature: float | None = 0.0, prefill: str | None = None, stop: list[str] | None = None) -> str:
        """Side call on the (usually cheaper) auxiliary model, e.g. for summaries."""
        req = Request(
            model=self.aux_model,
            system=[{"text": system}] if system else [],
            messages=[{"role": "user", "content": [{"text": prompt}]}],
            max_tokens=max_tokens,
            temperature=temperature,
            tag=f"aux:{purpose}",
            prefill=prefill,
            stop=list(stop or []),
        )
        resp = self.llm.converse(req)
        self.meter.record(req.tag, self.aux_model, resp.usage, resp.latency_ms, resp.reported_cost_usd)
        return resp.text

    def estimate_context_tokens(self) -> int:
        return sum(estimate_block_tokens(b) for m in self.messages for b in m["content"])

    def transcript(self, messages: list[Message] | None = None, max_result_chars: int | None = None) -> str:
        """Plain-text rendering of the conversation, for summarisation prompts."""
        lines: list[str] = []
        for msg in messages if messages is not None else self.messages:
            for b in msg["content"]:
                if "text" in b:
                    lines.append(f"[{msg['role']}] {b['text']}")
                elif "toolUse" in b:
                    tu = b["toolUse"]
                    lines.append(f"[call] {tu['name']}({json.dumps(tu['input'], sort_keys=True)})")
                elif "toolResult" in b:
                    text = "\n".join(c.get("text", "") for c in b["toolResult"]["content"])
                    if max_result_chars and len(text) > max_result_chars:
                        text = text[:max_result_chars] + " …"
                    lines.append(f"[result] {text}")
        return "\n".join(lines)
