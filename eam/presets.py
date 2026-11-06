"""Phase 2: combined memory skills built from the individual techniques.

These are *starting hypotheses* for combinations, to be validated with the
bench (``eam-bench --techniques auto``), not recommendations.

* ``cache_first`` — for models with prompt caching: never rewrite the prefix
  except in large, infrequent batches; shrink content at ingestion instead.
* ``lean`` — for models without caching: every resent token is paid in full,
  so keep the context bounded and compress aggressively.
* ``auto`` — picks one of the above from the model's capabilities.
"""

from __future__ import annotations

from typing import Callable

from eam.techniques.base import Pipeline, Technique
from eam.techniques.cache_layout import CacheLayout
from eam.techniques.compression import PromptCompression
from eam.techniques.folding import ContextFolding
from eam.techniques.iter_research import IterResearch
from eam.techniques.obs_mask import ObservationMasking
from eam.techniques.offload import ToolResultOffload
from eam.techniques.todo import TodoRecitation


# Ordering matters inside a pipeline: on_tool_result hooks run in list order, so
# compression must come before offload (otherwise it only ever sees previews),
# and observation masking is left out by default because it drops facts that
# aggregation tasks need at the end (see the individual-suite results).


def cache_first() -> Pipeline:
    return Pipeline(
        CacheLayout(),
        TodoRecitation(),
        ToolResultOffload(max_tokens=3000),
        ContextFolding(sub_techniques=[CacheLayout()]),
        name="cache_first",
    )


def lean() -> Pipeline:
    return Pipeline(
        PromptCompression(min_tokens=400, rate=0.5),
        ToolResultOffload(max_tokens=2000),
        IterResearch(round_steps=5),
        name="lean",
    )


def cache_first_masked() -> Pipeline:
    """cache_first plus observation masking, to measure masking inside a combination."""
    return Pipeline(cache_first(), ObservationMasking(), name="cache_first_masked")


class AutoMemory(Technique):
    """Chooses a combination from the model profile the first time a hook runs."""

    name = "auto"
    source = "this project: cache-aware policy selection"

    def __init__(self, with_cache: Callable[[], Technique] = cache_first,
                 without_cache: Callable[[], Technique] = lean):
        self._factories = (with_cache, without_cache)
        self._inner: Technique | None = None

    def _resolve(self, ctx) -> Technique:
        if self._inner is None:
            self._inner = (self._factories[0] if ctx.model.supports_cache else self._factories[1])()
            self.cache_safe = self._inner.cache_safe
            ctx.log("auto_selected", preset=self._inner.name)
        return self._inner

    def tools(self, ctx):
        return self._resolve(ctx).tools(ctx)

    def system_addendum(self):
        return self._inner.system_addendum() if self._inner else None

    def on_session_start(self, ctx):
        self._resolve(ctx).on_session_start(ctx)

    def before_call(self, ctx):
        self._resolve(ctx).before_call(ctx)

    def render(self, ctx, req):
        return self._resolve(ctx).render(ctx, req)

    def after_call(self, ctx, resp):
        self._resolve(ctx).after_call(ctx, resp)

    def on_tool_result(self, ctx, outcome):
        return self._resolve(ctx).on_tool_result(ctx, outcome)

    def on_session_end(self, ctx, answer):
        self._resolve(ctx).on_session_end(ctx, answer)

    def describe(self) -> str:
        return f"auto->{self._inner.describe() if self._inner else '?'}"


def automem_v2() -> Technique:
    """AutoMemory v2 default (docs/results/2026-11-04-automemory-v2.md): v1 + head/tail previews at ingestion for
    outputs above 10% of the window."""
    from eam.techniques.auto_memory import AutoMemory as AM

    return AM(ingest=0.1)


def automem_v2_slim() -> Technique:
    """AutoMemory v2 "slim" mode: v2 + ReFold dedup/folding; smallest peak context, a little more cost."""
    from eam.techniques.auto_memory import AutoMemory as AM

    return AM(ingest=0.1, fold=True)


def automem_v2_strong() -> Technique:
    """AutoMemory v2 for strong agent models (docs/results/2026-11-04-automemory-v3-ablation.md, Sonnet at 4 seeds):
    v2 with ReSum summaries pruned by SJC's source judge. Pair it with a cheaper summariser/judge model (``#aux=``).
    Not for weaker agent models: on Haiku it lowered research_corpus and ledger_audit."""
    from eam.techniques.auto_memory import AutoMemory as AM

    return AM(ingest=0.1, compact="sjc")


def automem_v2_lean() -> Technique:
    """AutoMemory v2 without the note workspace, for sessions that do not depend on each other's results (one coding
    issue per session): previews at ingestion, the in-step guard and ReSum compaction only
    (docs/results/2026-11-05-swe-bench-workdays.md). Not for multi-session work that builds on earlier results."""
    from eam.techniques.auto_memory import AutoMemory as AM

    return AM(workspace=False, ingest=0.1)


def automem_v2_lean_handoff() -> Technique:
    """`automem_v2_lean` with NVIDIA's EoCC handoff recap (arXiv 2611.05306) in place of ReSum's summary, written by
    the agent model itself (docs/results/2026-11-06-handoff-and-swe-100.md). On 100 SWE-bench Verified issues at a
    16K window it resolved 81 (Haiku) and 88 (Sonnet) against 76 and 86 with ReSum, at 6–16 points more cost:
    the accuracy-first choice for coding work under a tight window; `automem_v2_lean` stays the cheapest."""
    from eam.techniques.auto_memory import AutoMemory as AM

    return AM(workspace=False, ingest=0.1, compact="handoff", handoff_variant="swe")


PRESETS: dict[str, Callable[[], Technique]] = {
    "automem_v2": automem_v2,
    "automem_v2_lean": automem_v2_lean,
    "automem_v2_lean_handoff": automem_v2_lean_handoff,
    "automem_v2_strong": automem_v2_strong,
    "automem_v2_slim": automem_v2_slim,
    "cache_first": cache_first,
    "lean": lean,
    "cache_first_masked": cache_first_masked,
    "auto": AutoMemory,
}
