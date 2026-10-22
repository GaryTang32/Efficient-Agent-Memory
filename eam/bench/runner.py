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
from eam.llm.routes import make_client
from eam.llm.types import LLMClient
from eam.models import ModelProfile, load_models
from eam.store import ArtifactStore
from eam.techniques import build


def make_llm(backend: str, inst: TaskInstance, region: str | None = None) -> LLMClient:
    if backend == "mock":
        return MockLLM(inst.oracle())
    return make_client(backend, region=region)


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
    if inst.context_limit:
        common["system_prompt"] = (common["system_prompt"] + f"\n\nContext window: your conversation can hold at most "
                                   f"{inst.context_limit:,} tokens in total. If it grows beyond that, the task fails.")
        common["context_limit"] = inst.context_limit
    for session in inst.sessions:  # earlier sessions of multi-session tasks: costs count, answers don't
        r = run_agent(session, max_steps=inst.max_steps, final_marker=None, **common)
        rewrites += r.history_rewrites
        events.update(e["kind"] for e in r.events)
    round_scores: list[float] = []
    round_answers: list[str] = []
    if inst.rounds:  # multi-round tasks: one fresh session per round; technique objects (memory) persist
        steps, peak, finished = 0, 0, True
        for k, prompt in enumerate(inst.rounds):
            r = run_agent(prompt, max_steps=inst.max_steps, **common)
            round_scores.append(inst.round_score(k, r.answer) if r.finished else 0.0)
            round_answers.append(r.answer[:1500])
            rewrites += r.history_rewrites
            events.update(e["kind"] for e in r.events)
            steps += r.steps
            peak = max(peak, r.peak_prompt_tokens)
            finished = finished and r.finished
        res = r
        res.steps, res.peak_prompt_tokens, res.finished = steps, peak, finished
        rewrites -= res.history_rewrites  # counted in the loop above
    else:
        res = run_agent(inst.prompt, max_steps=inst.max_steps, **common)
        events.update(e["kind"] for e in res.events)
    summary = meter.summary()
    return {
        "family": inst.family,
        "instance": inst.instance_id,
        "spec": spec,
        "techniques": [t.describe() for t in techniques],
        "provenance": [getattr(t, "provenance", "") for t in techniques],
        "backend": backend,
        "model": model.key,
        "aux_model": aux_model.key,
        "success": (all(x == 1.0 for x in round_scores) if inst.rounds else bool(res.finished and inst.check(res.answer))),
        "score": (sum(round_scores) / len(round_scores) if inst.rounds else
                  (inst.score(res.answer) if inst.score else float(inst.check(res.answer))) if res.finished else 0.0),
        "round_scores": round_scores,
        "round_answers": round_answers,
        "overflow": events.get("context_overflow", 0) > 0,
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
        "nudges": sum(1 for e in res.events if e["kind"] == "nudge"),
        "events": dict(events),
        "answer": res.answer[:500],
        "gold": inst.gold,
    }


def run_suite(families_specs: dict[str, list[str]], *, backend: str, model_key: str, aux_key: str | None,
              n: int, seed: int, out: str | Path, models_path: str | None = None, region: str | None = None,
              task_kwargs: dict[str, dict[str, Any]] | None = None, echo: bool = True,
              workers: int = 1) -> list[dict[str, Any]]:
    """Run every (task instance × spec). With workers > 1, runs execute concurrently (each run is independent:
    own client, meter and technique instances), which matters for slow backends such as the Claude Code CLI."""
    from concurrent.futures import ThreadPoolExecutor, as_completed
    import threading

    models = load_models(models_path)
    model = models[model_key]
    aux = models[aux_key] if aux_key else model
    out = Path(out)
    out.parent.mkdir(parents=True, exist_ok=True)
    jobs = []
    for family, specs in families_specs.items():
        gen = FAMILIES[family]
        for i in range(n):
            for spec in specs:
                jobs.append((family, seed + i, spec))
    lock = threading.Lock()
    rows: list[dict[str, Any]] = []

    def one(job):
        family, s, spec = job
        inst = FAMILIES[family](s, **(task_kwargs or {}).get(family, {}))
        try:
            row = run_instance(inst, spec, backend=backend, model=model, aux_model=aux, models=models, region=region)
        except Exception as exc:  # keep the suite going; record the failure
            row = {"family": family, "instance": inst.instance_id, "spec": spec, "backend": backend,
                   "model": model.key, "error": f"{type(exc).__name__}: {exc}"[:500]}
        with lock:
            with out.open("a") as fh:
                fh.write(json.dumps(row) + "\n")
            rows.append(row)
            if echo:
                if "error" in row:
                    print(f"{family:22s} {row['instance']:14s} {spec:40s} ERROR {row['error'][:80]}", flush=True)
                else:
                    print(f"{family:22s} {row['instance']:14s} {spec:40s} "
                          f"{'OK ' if row['success'] else 'FAIL'} score={row['score']:.2f} ${row['cost_usd']:.4f} "
                          f"steps={row['steps']} hit={row['cache_hit_rate']:.2f}", flush=True)
        return row

    if workers <= 1:
        for job in jobs:
            one(job)
    else:
        with ThreadPoolExecutor(max_workers=workers) as pool:
            for fut in as_completed([pool.submit(one, j) for j in jobs]):
                fut.result()
    return [r for r in rows if "error" not in r]


def load_rows(paths: Iterable[str | Path]) -> list[dict[str, Any]]:
    rows = []
    for p in paths:
        rows.extend(json.loads(line) for line in Path(p).read_text().splitlines() if line.strip())
    return [r for r in rows if "error" not in r]
