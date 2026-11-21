"""Every AutoMemory library setting in one table: its default, the range it accepts, and where the default comes from.

`MemorySkill` and `MemoryHooks` check their settings against this table, and docs/settings.md documents it. Ranges
are wide on purpose: they refuse values that cannot work (a reset after the window is full, a negative size), not
values that are merely unmeasured. "Measured" means the default was tested against an alternative on the bench;
"chosen" means it is a design or safety choice that was not swept.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class Setting:
    default: Any
    low: float | None = None       # inclusive bounds for numbers
    high: float | None = None
    choices: tuple = ()            # allowed values for strings
    off: Any = "unset"             # a value that turns the feature off, outside the bounds (0 or None)
    unit: str = ""
    evidence: str = ""


SETTINGS: dict[str, Setting] = {
    "window": Setting(200_000, 1_000, 10_000_000, unit="tokens",
                      evidence="chosen: your model's context window or the budget you manage; every share below is of it"),
    "trigger": Setting(0.75, 0.05, 1.0, unit="share of window",
                       evidence="measured: one reset at 75% held accuracy on four long tasks and SWE-bench (12K of a "
                                "16K window); no reset scored 0.04-0.62. Other values not swept"),
    "guard": Setting(0.9, 0.1, 1.0, off=0, unit="share of window",
                     evidence="measured against off: removed the overflows of parallel tool calls"),
    "preview": Setting(0.1, 0.005, 0.5, off=0, unit="share of window",
                       evidence="measured against off: Haiku solved 11/16 runs instead of 7/16 at the same cost; "
                                "without previews NVIDIA's recap alone lost 5 of 100 Django issues"),
    "preview_tokens": Setting(750, 50, 20_000, unit="tokens",
                              evidence="chosen: Strands' head/tail preview size, used in every measured run"),
    "preview_max_tokens": Setting(16_000, 500, 1_000_000, off=0, unit="tokens",
                                  evidence="chosen: caps the preview threshold above a 160K window; not measured "
                                           "(no measured window reached it)"),
    "recall_budget": Setting(0.1, 0.001, 0.5, unit="share of window",
                             evidence="measured: with newest-answer recall, 10% kept every needed fact on a "
                                      "ten-day job (the cap alone dropped 5 of 258)"),
    "compaction": Setting("resum", choices=("resum", "handoff"),
                          evidence="measured: ReSum and NVIDIA's handoff recap were level over three Django runs"),
    "handoff_variant": Setting("general", choices=("general", "swe", "brief"),
                               evidence="chosen: the paper's prompts; brief was level on cost and accuracy"),
    "token_ratio": Setting(1.5, 1.0, 3.0, unit="real tokens per estimated token",
                           evidence="chosen: conservative for dense text, so the guard errs on the safe side"),
    "max_note_chars": Setting(20_000, 100, 1_000_000, unit="characters",
                              evidence="chosen: one note stays small next to the recall budget"),
    "retention_days": Setting(14, 0.01, 3650, off=0, unit="days",
                              evidence="chosen (security): saved outputs do not pile up; 0 keeps them"),
    "max_artifact_mb": Setting(200, 0.001, 100_000, unit="MB",
                               evidence="chosen (security): per-project size limit for saved outputs"),
    "max_artifact_chars": Setting(10_000_000, 1_000, 1_000_000_000, unit="characters",
                                  evidence="chosen (security): one saved output is cut beyond this"),
    "wrap": Setting(True, choices=(True, False),
                    evidence="measured: 0 of 20 planted instructions obeyed with wrapping, 4 of 20 without"),
}

# not a MemorySkill argument: MemoryHooks turns it into `trigger` (compact_at / window)
COMPACT_AT = Setting(None, 1_000, 10_000_000, unit="tokens",
                     evidence="chosen: the reset point in tokens, the same as trigger x window")


def _fmt(x: float) -> str:
    return f"{int(x):,}" if float(x).is_integer() else f"{x:g}"


def check(name: str, value: Any) -> Any:
    """`value` for setting `name` if it is accepted (normalised: ints for token sizes, None for an off cap),
    else ValueError naming the accepted range."""
    s = SETTINGS.get(name) or (COMPACT_AT if name == "compact_at" else None)
    if s is None:
        raise ValueError(f"unknown setting {name!r}; settings: {sorted(SETTINGS) + ['compact_at']}")
    if s.choices:
        if value not in s.choices:
            raise ValueError(f"{name} must be one of {list(s.choices)}, not {value!r}")
        return value
    if s.off != "unset" and value in (0, None, s.off):
        return None if name == "preview_max_tokens" else s.off
    try:
        number = float(value)
    except (TypeError, ValueError):
        raise ValueError(f"{name} must be a number, not {value!r}") from None
    if not s.low <= number <= s.high:
        off = f" (or {s.off} to turn it off)" if s.off != "unset" else ""
        raise ValueError(f"{name} must be between {_fmt(s.low)} and {_fmt(s.high)} {s.unit}{off}, not {value!r}")
    return int(number) if isinstance(s.default, int) and not isinstance(s.default, bool) else number


def check_all(values: dict[str, Any]) -> dict[str, Any]:
    return {k: check(k, v) for k, v in values.items()}
