"""Technique registry and spec parsing (eam/techniques/registry.py), loaded on first use.

Lazy so that the AutoMemory library and adapters can import a prompt module from this package (for example
`eam.techniques.third_party.resum`) without loading every bench technique.
"""

from __future__ import annotations

import importlib
import importlib.util


def __getattr__(name: str):
    if not name.startswith("__") and importlib.util.find_spec(f"{__name__}.{name}") is None:  # not a submodule
        registry = importlib.import_module(f"{__name__}.registry")
        if hasattr(registry, name):
            return getattr(registry, name)
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
