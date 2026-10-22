"""Backend-neutral request/response types.

Messages are kept in the Bedrock Converse wire format so that what techniques
manipulate is exactly what Bedrock receives::

    {"role": "user" | "assistant",
     "content": [{"text": ...} | {"toolUse": {...}} | {"toolResult": {...}}]}

Cache points are *not* stored in the history; they are a render-time plan
(``CachePlan``) so techniques can move them every step without rewriting
history.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any, Protocol

if TYPE_CHECKING:
    from eam.models import ModelProfile

Message = dict[str, Any]


@dataclass
class ToolSpec:
    name: str
    description: str
    input_schema: dict[str, Any]

    def to_converse(self) -> dict[str, Any]:
        return {
            "toolSpec": {
                "name": self.name,
                "description": self.description,
                "inputSchema": {"json": self.input_schema},
            }
        }


@dataclass
class CachePlan:
    """Where to place Converse ``cachePoint`` blocks (Bedrock allows at most 4)."""

    tools: bool = False
    system: bool = False
    message_indices: list[int] = field(default_factory=list)

    def count(self) -> int:
        return int(self.tools) + int(self.system) + len(self.message_indices)


@dataclass
class Request:
    model: "ModelProfile"
    system: list[dict[str, Any]]
    messages: list[Message]
    tools: list[ToolSpec] = field(default_factory=list)
    max_tokens: int = 2048
    temperature: float | None = 0.0
    cache: CachePlan = field(default_factory=CachePlan)
    extra: dict[str, Any] = field(default_factory=dict)  # additionalModelRequestFields
    tag: str = "main"  # metering label: main | aux:<purpose> | subagent
    prefill: str | None = None  # start of the assistant reply (sent as a trailing assistant message where supported)
    stop: list[str] = field(default_factory=list)  # stop sequences


@dataclass
class Usage:
    input_tokens: int = 0  # uncached input
    output_tokens: int = 0
    cache_read_tokens: int = 0
    cache_write_tokens: int = 0

    @property
    def prompt_tokens(self) -> int:
        return self.input_tokens + self.cache_read_tokens + self.cache_write_tokens

    def __add__(self, other: "Usage") -> "Usage":
        return Usage(
            self.input_tokens + other.input_tokens,
            self.output_tokens + other.output_tokens,
            self.cache_read_tokens + other.cache_read_tokens,
            self.cache_write_tokens + other.cache_write_tokens,
        )

    def to_dict(self) -> dict[str, int]:
        return {
            "input_tokens": self.input_tokens,
            "output_tokens": self.output_tokens,
            "cache_read_tokens": self.cache_read_tokens,
            "cache_write_tokens": self.cache_write_tokens,
        }


@dataclass
class Response:
    message: Message
    stop_reason: str
    usage: Usage
    latency_ms: float
    model_key: str
    reported_cost_usd: float | None = None  # set when the backend reports its own cost (Claude Code CLI)

    @property
    def text(self) -> str:
        return "".join(b["text"] for b in self.message.get("content", []) if "text" in b)

    @property
    def tool_uses(self) -> list[dict[str, Any]]:
        return [b["toolUse"] for b in self.message.get("content", []) if "toolUse" in b]


class LLMClient(Protocol):
    def converse(self, req: Request) -> Response: ...
