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
from eam.techniques.masking import KeepLastN
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
    """cache_first plus batched observation masking, to measure masking inside a combination."""
    return Pipeline(cache_first(), KeepLastN(keep=8, batch=8), name="cache_first_masked")


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


PRESETS: dict[str, Callable[[], Technique]] = {
    "cache_first": cache_first,
    "lean": lean,
    "cache_first_masked": cache_first_masked,
    "auto": AutoMemory,
}
