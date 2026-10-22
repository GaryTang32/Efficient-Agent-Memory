"""Turn token usage into dollars, broken down by call purpose."""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass, field

from eam.llm.types import Usage
from eam.models import ModelProfile


def usage_cost(usage: Usage, model: ModelProfile) -> float:
    cost = usage.input_tokens * model.price_in + usage.output_tokens * model.price_out
    # A model without caching should never report cache tokens; price them as input if it does.
    cost += usage.cache_write_tokens * (model.price_cache_write if model.price_cache_write is not None else model.price_in)
    cost += usage.cache_read_tokens * (model.price_cache_read if model.price_cache_read is not None else model.price_in)
    return cost / 1_000_000


@dataclass
class CallRecord:
    tag: str
    model_key: str
    usage: Usage
    cost: float
    latency_ms: float


@dataclass
class CostMeter:
    records: list[CallRecord] = field(default_factory=list)

    def record(self, tag: str, model: ModelProfile, usage: Usage, latency_ms: float,
               reported_cost: float | None = None) -> None:
        # Prefer the backend's own figure when it reports one (e.g. Claude Code's total_cost_usd).
        cost = reported_cost if reported_cost is not None else usage_cost(usage, model)
        self.records.append(CallRecord(tag, model.key, usage, cost, latency_ms))

    @property
    def usage(self) -> Usage:
        total = Usage()
        for r in self.records:
            total = total + r.usage
        return total

    @property
    def cost(self) -> float:
        return sum(r.cost for r in self.records)

    @property
    def latency_ms(self) -> float:
        return sum(r.latency_ms for r in self.records)

    def cache_hit_rate(self) -> float:
        u = self.usage
        return u.cache_read_tokens / u.prompt_tokens if u.prompt_tokens else 0.0

    def by_tag(self) -> dict[str, dict[str, float]]:
        out: dict[str, dict[str, float]] = defaultdict(lambda: {"calls": 0, "cost": 0.0, "prompt_tokens": 0, "output_tokens": 0})
        for r in self.records:
            group = r.tag.split(":")[0]
            out[group]["calls"] += 1
            out[group]["cost"] += r.cost
            out[group]["prompt_tokens"] += r.usage.prompt_tokens
            out[group]["output_tokens"] += r.usage.output_tokens
        return dict(out)

    def summary(self) -> dict:
        return {
            "cost_usd": round(self.cost, 6),
            "calls": len(self.records),
            "usage": self.usage.to_dict(),
            "cache_hit_rate": round(self.cache_hit_rate(), 4),
            "latency_ms": round(self.latency_ms, 1),
            "by_tag": self.by_tag(),
        }
