"""Turn control — Gao & Peng, "More with Less: An Empirical Study of Turn-Control Strategies for
Efficient Coding Agents", ICSE 2026 (ByteDance). Reminder strings are verbatim from the paper (§2.4);
the per-turn reminder is also in the AgentDiet artifact's expert.py.

* fixed:   hard limit; every call is preceded by "You have X turns left"; the run ends at the limit.
* dynamic: start with `limit`; when it is used up without finishing, grant `extension` more turns once.
* Set limits from percentiles of the model's own unlimited-run turn counts (the paper's sweet spot is the
  75th percentile for fixed, 25th→50th or 50th→75th for dynamic): `python -m eam.bench calibrate <results>`.
"""

from __future__ import annotations

from eam.techniques.base import Technique

REMINDER = "ENVIRONMENT REMINDER: You have {left} turns left to complete the task."
EXTENSION = ("ENVIRONMENT REMINDER: You have used up all turns but have not yet completed the task. "
             "You are granted an additional {extra} turns to continue and complete the task.")


class TurnControl(Technique):
    name = "turn_control"
    source = "Gao & Peng, ICSE 2026 (ByteDance)"
    provenance = "official reminder strings from the paper"

    def __init__(self, limit: int = 30, mode: str = "fixed", extension: int = 0, reminder: bool = True):
        if mode not in ("fixed", "dynamic"):
            raise ValueError("mode must be 'fixed' or 'dynamic'")
        self.limit = int(limit)
        self.mode = mode
        self.extension = int(extension)
        self.reminder = reminder in (True, "true", "1", 1)
        self._limit = self.limit
        self._extended = False

    def on_session_start(self, ctx):
        self._limit, self._extended = self.limit, False

    def before_call(self, ctx):
        used = ctx.step - 1
        latest = ctx.messages[-1]
        if used >= self._limit:
            if self.mode == "dynamic" and not self._extended and self.extension > 0:
                self._extended = True
                self._limit += self.extension
                latest["content"].append({"text": EXTENSION.format(extra=self.extension)})
                ctx.log("turn_extension", limit=self._limit)
                return
            ctx.stop_reason = "turn_limit"
            return
        if self.reminder:
            latest["content"].append({"text": REMINDER.format(left=self._limit - used)})
