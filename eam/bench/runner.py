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


def make_llm(backend: str, inst: TaskInstance, region: str | None = None, prompt_cache: bool = True) -> LLMClient:
    if backend == "mock":
        return MockLLM(inst.oracle(), prompt_cache=prompt_cache)
    return make_client(backend, region=region, prompt_cache=prompt_cache)


def split_window(spec: str) -> tuple[str, str | None]:
    """``"<techniques>@native"`` runs without the emulated context window (the model's own window applies);
    ``"<techniques>@64k"`` overrides the task's window. Returns (technique spec, window override)."""
    base, _, window = spec.partition("@")
    return base, (window.strip().lower() or None)


def _window_limit(window: str | None, default: int | None) -> int | None:
    if window is None:
        return default
    if window == "native":
        return None
    return int(float(window.rstrip("k")) * 1000) if window.endswith("k") else int(window)


def run_instance(inst: TaskInstance, spec: str, *, backend: str, model: ModelProfile, aux_model: ModelProfile,
                 models: dict[str, ModelProfile], region: str | None = None) -> dict[str, Any]:
    tech_spec, window = split_window(spec)
    techniques = build(tech_spec)
    prompt_cache = not any(getattr(t, "disable_prompt_cache", False) for t in techniques)
    offload = not any(getattr(t, "disable_offload", False) for t in techniques)
    context_limit = _window_limit(window, inst.context_limit)
    llm = make_llm(backend, inst, region, prompt_cache=prompt_cache)
    meter, store = CostMeter(), ArtifactStore()
    common = dict(llm=llm, model=model, aux_model=aux_model, models=models, env_tools=inst.tools,
                  techniques=techniques, system_prompt=inst.system_prompt or DEFAULT_SYSTEM,
                  resources=inst.resources, meter=meter, store=store)
    t0 = time.perf_counter()
    rewrites, events = 0, Counter()
    tool_calls = 0
    if context_limit:
        common["context_limit"] = context_limit
        common["context_gauge"] = inst.disclose_limit
    if inst.step_observation_budget and offload:
        common["step_observation_budget"] = inst.step_observation_budget
    if context_limit and inst.disclose_limit:
        common["system_prompt"] = (common["system_prompt"] + f"\n\nContext window: your conversation can hold at "
                                   f"most {context_limit:,} tokens in total. If it grows beyond that, the task fails.")
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
            tool_calls += r.tool_calls
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
        tool_calls += res.tool_calls
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
        "limit_disclosed": inst.disclose_limit if context_limit else None,
        "context_limit": context_limit,
        "prompt_cache": prompt_cache,
        "offload": bool(inst.step_observation_budget and offload),
        "finished": res.finished,
        "steps": res.steps,
        "tool_calls": tool_calls,
        "sessions": len(inst.rounds) or 1,
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
              workers: int = 1, resume: bool = False) -> list[dict[str, Any]]:
    """Run every (task instance × spec). With workers > 1, runs execute concurrently (each run is independent:
    own client, meter and technique instances), which matters for slow backends such as the Claude Code CLI."""
    from concurrent.futures import ThreadPoolExecutor, as_completed
    import threading

    models = load_models(models_path)
    model = models[model_key]
    aux = models[aux_key] if aux_key else model
    out = Path(out)
    out.parent.mkdir(parents=True, exist_ok=True)
    done: set[tuple] = set()
    if resume and out.exists():  # skip runs already recorded without error
        for row in load_rows([out]):
            done.add((row["family"], row["instance"], row["spec"]))
    jobs = []
    for family, specs in families_specs.items():
        gen = FAMILIES[family]
        for i in range(n):
            for spec in specs:
                if (family, FAMILIES[family](seed + i, **(task_kwargs or {}).get(family, {})).instance_id,
                        spec) not in done:
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
