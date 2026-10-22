"""Run (task × technique spec × model) experiments and record comparable metrics."""

from __future__ import annotations

import json
import time
from collections import Counter
from pathlib import Path
from typing import Any, Iterable

from eam.agent.loop import DEFAULT_SYSTEM, run_agent
from eam.bench.tasks import FAMILIES
from eam.bench.tasks.common import TaskInstance
from eam.cost import CostMeter
from eam.llm.mock import MockLLM
from eam.llm.types import LLMClient
from eam.models import ModelProfile, load_models
from eam.store import ArtifactStore
from eam.techniques import build


def make_llm(backend: str, inst: TaskInstance, region: str | None = None) -> LLMClient:
    if backend == "mock":
        return MockLLM(inst.oracle())
    if backend == "bedrock":
        from eam.llm.bedrock import BedrockClient

        return BedrockClient(region=region)
    raise ValueError(f"unknown backend '{backend}'")


def run_instance(inst: TaskInstance, spec: str, *, backend: str, model: ModelProfile, aux_model: ModelProfile,
                 models: dict[str, ModelProfile], region: str | None = None) -> dict[str, Any]:
    techniques = build(spec)
    llm = make_llm(backend, inst, region)
    meter, store = CostMeter(), ArtifactStore()
    common = dict(llm=llm, model=model, aux_model=aux_model, models=models, env_tools=inst.tools,
                  techniques=techniques, system_prompt=inst.system_prompt or DEFAULT_SYSTEM,
                  resources=inst.resources, meter=meter, store=store)
    t0 = time.perf_counter()
    rewrites, events = 0, Counter()
    for session in inst.sessions:  # earlier sessions of multi-session tasks: costs count, answers don't
        r = run_agent(session, max_steps=inst.max_steps, **common)
        rewrites += r.history_rewrites
        events.update(e["kind"] for e in r.events)
    res = run_agent(inst.prompt, max_steps=inst.max_steps, **common)
    events.update(e["kind"] for e in res.events)
    summary = meter.summary()
    return {
        "family": inst.family,
        "instance": inst.instance_id,
        "spec": spec,
        "techniques": [t.describe() for t in techniques],
        "backend": backend,
        "model": model.key,
        "aux_model": aux_model.key,
        "success": bool(res.finished and inst.check(res.answer)),
        "finished": res.finished,
        "steps": res.steps,
        "cost_usd": summary["cost_usd"],
        "usage": summary["usage"],
        "prompt_tokens": meter.usage.prompt_tokens,
        "cache_hit_rate": summary["cache_hit_rate"],
        "calls": summary["calls"],
        "by_tag": summary["by_tag"],
        "llm_latency_ms": summary["latency_ms"],
        "wall_s": round(time.perf_counter() - t0, 2),
        "peak_prompt_tokens": res.peak_prompt_tokens,
        "history_rewrites": rewrites + res.history_rewrites,
        "events": dict(events),
        "answer": res.answer[:500],
        "gold": inst.gold,
    }


def run_suite(families_specs: dict[str, list[str]], *, backend: str, model_key: str, aux_key: str | None,
              n: int, seed: int, out: str | Path, models_path: str | None = None, region: str | None = None,
              task_kwargs: dict[str, dict[str, Any]] | None = None, echo: bool = True) -> list[dict[str, Any]]:
    models = load_models(models_path)
    model = models[model_key]
    aux = models[aux_key] if aux_key else model
    out = Path(out)
    out.parent.mkdir(parents=True, exist_ok=True)
    rows = []
    with out.open("a") as fh:
        for family, specs in families_specs.items():
            gen = FAMILIES[family]
            for i in range(n):
                inst = gen(seed + i, **(task_kwargs or {}).get(family, {}))
                for spec in specs:
                    row = run_instance(inst, spec, backend=backend, model=model, aux_model=aux, models=models,
                                       region=region)
                    fh.write(json.dumps(row) + "\n")
                    fh.flush()
                    rows.append(row)
                    if echo:
                        print(f"{family:22s} {inst.instance_id:14s} {spec:40s} "
                              f"{'OK ' if row['success'] else 'FAIL'} ${row['cost_usd']:.4f} "
                              f"steps={row['steps']} hit={row['cache_hit_rate']:.2f}", flush=True)
    return rows


def load_rows(paths: Iterable[str | Path]) -> list[dict[str, Any]]:
    rows = []
    for p in paths:
        rows.extend(json.loads(line) for line in Path(p).read_text().splitlines() if line.strip())
    return rows
