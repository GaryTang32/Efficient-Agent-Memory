"""Settings per session (with defaults for every session that sets nothing), the reset point in tokens, and the cap
on the preview threshold for large windows."""

from __future__ import annotations

import pytest

from eam.adapters import MemoryHooks
from eam.automem import core as C


def test_compact_at_sets_the_reset_point_in_tokens(tmp_path):
    hooks = MemoryHooks(tmp_path, window=1_000_000, compact_at=400_000)
    assert hooks.settings["trigger"] == 0.4
    assert not hooks.should_compact(399_999) and hooks.should_compact(400_000)


def test_session_settings_apply_once_then_defaults_return(tmp_path):
    hooks = MemoryHooks(tmp_path, window=1_000_000, compact_at=500_000)
    hooks.start_session("day 1", window=400_000, trigger=0.9)
    assert (hooks.settings["window"], hooks.settings["trigger"]) == (400_000, 0.9)
    assert hooks.should_compact(360_000) and not hooks.should_compact(359_999)
    hooks.end_session("day 1 done, long enough to keep")

    hooks.next_session(compact_at=200_000, preview_max_tokens=4_000)  # for adapters, which start sessions themselves
    hooks.start_session("day 2")
    assert hooks.settings["trigger"] == 0.2 and hooks.settings["preview_max_tokens"] == 4_000

    hooks.start_session("day 3")  # nothing set: the defaults
    assert hooks.settings == hooks.defaults
    assert (hooks.settings["window"], hooks.settings["trigger"]) == (1_000_000, 0.5)


def test_bad_settings_are_refused(tmp_path):
    hooks = MemoryHooks(tmp_path)
    for bad in ({"trigger": 1.5}, {"windw": 10}, {"compaction": "magic"}, {"window": 0}):
        with pytest.raises(ValueError):
            hooks.next_session(**bad)
    with pytest.raises(ValueError):
        hooks.start_session("t", guard=1.5)


def test_preview_cap_for_large_windows(tmp_path):
    text = "x" * 200_000  # about 50K tokens
    assert not C.needs_preview(text, 1_000_000, 0.1)          # 10% of 1M lets 100K-token outputs in whole
    assert C.needs_preview(text, 1_000_000, 0.1, max_tokens=8_000)
    assert C.needs_preview(text, 16_000, 0.1, max_tokens=8_000)  # small windows: the share decides, as measured
    hooks = MemoryHooks(tmp_path, window=1_000_000)  # the default cap: 16K tokens
    assert hooks.settings["preview_max_tokens"] == 16_000
    hooks.start_session("t")
    shown = hooks.on_tool_result("cat_log", text)
    assert "artifact://" in shown and len(shown) < 10_000


def test_adapters_pick_up_next_session(tmp_path):
    """An adapter starts its sessions itself; next_session settings still reach that session."""
    hooks = MemoryHooks(tmp_path, window=1_000_000)
    hooks.next_session(compact_at=300_000)
    first = hooks.start_session("task")  # what an adapter calls internally
    assert first.endswith("task") and hooks.settings["trigger"] == 0.3


def test_default_cap_only_changes_large_windows(tmp_path):
    """16K tokens is 10% of a 160K window: windows up to 160K (every measured setting) preview exactly as before."""
    for window in (16_000, 32_000, 48_000, 160_000):
        for tokens in (1_000, 4_000, 12_000, 15_900, 16_100, 40_000):
            text = "x" * (4 * tokens)
            assert C.needs_preview(text, window, 0.1, 16_000) == C.needs_preview(text, window, 0.1), (window, tokens)
    over = "x" * (4 * 17_000)  # about 17K tokens
    assert "artifact://" in MemoryHooks(tmp_path / "b", window=1_000_000).on_tool_result("t", over)
    assert MemoryHooks(tmp_path / "d", window=1_000_000, preview_max_tokens=0).on_tool_result("t", over) == over


def test_settings_reference_covers_every_setting():
    """docs/settings.md lists every library setting with its default, and every plugin variable."""
    import re
    from pathlib import Path

    from eam.automem.settings import SETTINGS

    root = Path(__file__).resolve().parents[2]
    doc = (root / "docs" / "settings.md").read_text()
    for name in [*SETTINGS, "compact_at"]:
        assert f"| `{name}` |" in doc, name
    plugin = (root / "plugins/automem/hooks/automem_hook.py").read_text()
    for var in sorted(set(re.findall(r"AUTOMEM_[A-Z_]+", plugin))):
        assert f"`{var}`" in doc, var


def test_library_refuses_values_outside_the_range(tmp_path):
    from eam.memory_skill import MemorySkill

    for bad in ({"trigger": 1.5}, {"window": 10}, {"preview": 0.9}, {"compaction": "x"}, {"preview_max_tokens": 10}):
        with pytest.raises(ValueError, match="must be"):
            MemorySkill(tmp_path, **bad)
    s = MemorySkill(tmp_path, guard=0, preview=0, preview_max_tokens=0)  # 0 turns each off
    assert (s.guard, s.preview, s.preview_max_tokens) == (0, 0, None)
    with pytest.raises(ValueError, match="compact_at"):
        MemoryHooks(tmp_path, window=100_000, compact_at=200_000)
