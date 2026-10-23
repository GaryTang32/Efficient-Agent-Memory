"""Technique registry and spec parsing.

A spec string selects techniques for a run::

    "full"                                  baseline (full history, provider caching, harness offload)
    "naive"                                 no memory, no caching, no offload
    "naive@native"                          ... without the emulated context window (see bench/runner.py)
    "offload:max_tokens=600"                one technique with parameters
    "cache_layout+offload+keep_last_n:keep=3"  a combination
"""

from __future__ import annotations

from eam.techniques.agentdiet import AgentDiet
from eam.techniques.auto_memory import AutoMemory
from eam.techniques.base import Pipeline, Technique
from eam.techniques.baseline import FullContext
from eam.techniques.cache_layout import CacheLayout
from eam.techniques.compression import PromptCompression
from eam.techniques.folding import ContextFolding
from eam.techniques.iter_research import IterResearch
from eam.techniques.masking import KeepLastN
from eam.techniques.memagent import MemAgentReader
from eam.techniques.naive import NoOptimization
from eam.techniques.obs_mask import ObservationMasking
from eam.techniques.offload import ToolResultOffload
from eam.techniques.resum import ReSum
from eam.techniques.router import ThinkingRouter
from eam.techniques.tiered_memory import FullCarryover, TieredMemory
from eam.techniques.todo import TodoRecitation
from eam.techniques.turn_control import TurnControl
from eam.techniques.workspace import NoteWorkspace

REGISTRY: dict[str, type[Technique]] = {
    # paper-faithful (official prompts / algorithms)
    "agentdiet": AgentDiet,
    "turn_control": TurnControl,
    "folding": ContextFolding,
    "memagent": MemAgentReader,
    "resum": ReSum,
    # baselines and engineering rules
    "full": FullContext,
    "naive": NoOptimization,
    "obs_mask": ObservationMasking,
    "cache_layout": CacheLayout,
    "todo": TodoRecitation,
    "offload": ToolResultOffload,
    "compression": PromptCompression,
    "iter_research": IterResearch,
    "carryover": FullCarryover,
    "fs_workspace": NoteWorkspace,
    # this project's combined skill (phase 2), built from the phase-1 measurements
    "automem": AutoMemory,
    # provisional (ours, not yet backed by an official source)
    "tiered_memory": TieredMemory,
    "keep_last_n": KeepLastN,
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
