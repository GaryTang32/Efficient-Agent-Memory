"""Model profiles: Bedrock model id + pricing + capabilities.

Prices and model ids change; nothing here is authoritative. Copy
``config/models.example.json`` to ``config/models.json`` and fill in the
current values from the Bedrock console / pricing page for your region.
"""

from __future__ import annotations

import json
import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_CONFIG = REPO_ROOT / "config" / "models.json"
EXAMPLE_CONFIG = REPO_ROOT / "config" / "models.example.json"


@dataclass(frozen=True)
class ModelProfile:
    key: str
    model_id: str
    price_in: float  # USD per 1M uncached input tokens
    price_out: float  # USD per 1M output tokens
    price_cache_write: float | None = None  # None => model has no prompt caching on Bedrock
    price_cache_read: float | None = None
    min_cache_tokens: int = 1024
    context_window: int = 200_000
    thinking_fields: dict[str, Any] | None = field(default=None, hash=False)
    # Model name to use on each non-Converse route, e.g. {"claude-cli": "haiku", "litellm": "haiku"}.
    route_ids: dict[str, str] | None = field(default=None, hash=False)

    @property
    def supports_cache(self) -> bool:
        return self.price_cache_read is not None

    def id_for(self, route: str) -> str:
        return (self.route_ids or {}).get(route, self.model_id)


# Offline profiles for the mock backend. Prices mirror a typical
# "strong cached model" / "cheap model" / "uncached open-weight model" split so
# cost comparisons are meaningful in shape, not in absolute dollars.
MOCK_MODELS = {
    "mock-strong": ModelProfile("mock-strong", "mock-strong", 3.0, 15.0, 3.75, 0.30, 1024),
    "mock-cheap": ModelProfile("mock-cheap", "mock-cheap", 1.0, 5.0, 1.25, 0.10, 2048),
    "mock-nocache": ModelProfile("mock-nocache", "mock-nocache", 0.6, 1.7, None, None),
}


def load_models(path: str | os.PathLike[str] | None = None) -> dict[str, ModelProfile]:
    models = dict(MOCK_MODELS)
    cfg = Path(path) if path else Path(os.environ.get("EAM_MODELS", DEFAULT_CONFIG))
    if not cfg.exists():
        cfg = EXAMPLE_CONFIG
    if cfg.exists():
        for key, spec in json.loads(cfg.read_text()).get("models", {}).items():
            if str(spec.get("model_id", "")).startswith("<"):
                continue  # unfilled placeholder
            spec = {k: v for k, v in spec.items() if not k.startswith("_")}
            models[key] = ModelProfile(key=key, **spec)
    return models
