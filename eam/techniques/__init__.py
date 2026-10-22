"""Technique registry and spec parsing.

A spec string selects techniques for a run::

    "full"                                  baseline
    "offload:max_tokens=600"                one technique with parameters
    "cache_layout+offload+keep_last_n:keep=3"  a combination
"""

from __future__ import annotations

from eam.techniques.base import Pipeline, Technique
from eam.techniques.baseline import FullContext
from eam.techniques.cache_layout import CacheLayout
from eam.techniques.compression import PromptCompression
from eam.techniques.folding import ContextFolding
from eam.techniques.iter_research import IterResearch
from eam.techniques.masking import KeepLastN
from eam.techniques.memagent import MemAgentReader
from eam.techniques.offload import ToolResultOffload
from eam.techniques.resum import ReSum
from eam.techniques.router import ThinkingRouter
from eam.techniques.tiered_memory import FullCarryover, TieredMemory
from eam.techniques.todo import TodoRecitation

REGISTRY: dict[str, type[Technique]] = {
    "full": FullContext,
    "cache_layout": CacheLayout,
    "todo": TodoRecitation,
    "offload": ToolResultOffload,
    "keep_last_n": KeepLastN,
    "compression": PromptCompression,
    "resum": ReSum,
    "iter_research": IterResearch,
    "folding": ContextFolding,
    "memagent": MemAgentReader,
    "tiered_memory": TieredMemory,
    "carryover": FullCarryover,
    "router": ThinkingRouter,
}


def _value(raw: str):
    low = raw.lower()
    if low in ("true", "false"):
        return low == "true"
    for cast in (int, float):
        try:
            return cast(raw)
        except ValueError:
            pass
    return raw


def build_one(spec: str) -> Technique:
    name, _, params = spec.strip().partition(":")
    if name not in REGISTRY:
        from eam.presets import PRESETS

        if name in PRESETS:
            return PRESETS[name]()
        raise KeyError(f"unknown technique '{name}'. Known: {sorted(REGISTRY)} + presets {sorted(PRESETS)}")
    kwargs = {}
    for part in filter(None, params.split(";" if ";" in params else ",")):
        k, _, v = part.partition("=")
        kwargs[k.strip()] = _value(v.strip())
    return REGISTRY[name](**kwargs)


def build(spec: str) -> list[Technique]:
    return [build_one(s) for s in spec.split("+") if s.strip()]


__all__ = ["REGISTRY", "Pipeline", "Technique", "build", "build_one"]
