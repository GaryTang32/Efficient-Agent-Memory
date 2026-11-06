"""SelfCompact — "Self-Compacting Language Model Agents" (Apple + JHU; arXiv 2606.23525; NeurIPS 2026).
Official code: https://github.com/tianjianl/selfcompact (agentic-search variant, MIT); prompts verbatim in
third_party/selfcompact.py.

The agent is its own judge and its own summariser. After a tool round, once the gates hold (round ≥ 3, prompt ≥
``min_tokens``, fewer than ``cap`` compactions, ≥ ``period`` rounds since the last probe), the *agent's own model*
answers a four-question rubric about its trajectory (C1 closed unit, C2 summarisable into 3-5 facts, C3 progress
since the last compaction, N1 stuck). It compacts iff C1=C2=C3=Y and N1=N: the same model writes a summary (the
WebResummer-style prompt) and the history becomes [task, assistant "Here is my research so far: …", user
"Continue your research…"]. Nothing else is kept.

Deviations (API, Converse):
* the probe/summary prompt is appended as a text block to the last user message (Converse needs alternating roles)
  and the same tools are sent (a history with tool calls needs a tool config), so the cached prefix is identical;
  a probe reply that calls a tool counts as "incomplete" → continue, as a missing field does in the code;
* ``min_tokens`` is 40,000 in the code for 128K–262K windows; on this benchmark's emulated windows the gate is
  ``min_frac`` × window (0.31 ≈ 40K/128K) when that is smaller;
* a backstop at ``backstop`` × window (default 0.8, the point where the other compactors here fire) forces a
  compaction regardless of the rubric, so a run is not lost to an overflow the paper's 108K budget would have
  ended differently (the paper describes a 0.30 backstop; the code has none). Both kinds are logged separately.
"""

from __future__ import annotations

import copy
import re

from eam.llm.types import Request
from eam.techniques.base import Technique
from eam.techniques.third_party import selfcompact as P

FIELDS = ("C1", "C2", "C3", "N1")


def parse_rubric(raw: str) -> dict[str, str | None]:
    """selfcompact agent.py::parse_rubric (last matching line per field, its first Y/N)."""
    cleaned = re.sub(r"<think>.*?</think>", "", raw or "", flags=re.DOTALL)
    answers: dict[str, str | None] = dict.fromkeys(FIELDS)
    for field in FIELDS:
        matches = list(re.finditer(rf"(?im)^\s*{field}\s*[:\.\)]\s*(.*)$", cleaned))
        if not matches:
            continue
        m = re.search(r"\b(Y(?:es)?|N(?:o)?)\b", matches[-1].group(1), re.IGNORECASE)
        if m:
            answers[field] = m.group(1)[0].upper()
    return answers


def verdict(answers: dict[str, str | None]) -> tuple[str, str]:
    if any(answers.get(f) is None for f in FIELDS):
        return "CONTINUE", "incomplete"
    if answers["C1"] == "Y" and answers["C2"] == "Y" and answers["C3"] == "Y" and answers["N1"] == "N":
        return "COMPRESS", "first_principles_pass"
    failed = [f for f in ("C1", "C2", "C3") if answers[f] != "Y"]
    if answers["N1"] == "Y":
        failed.append("N1=Y")
    return "CONTINUE", "fp_fail:" + ",".join(failed)


class SelfCompact(Technique):
    name = "selfcompact"
    source = "SelfCompact (Apple + JHU), arXiv 2606.23525"
    provenance = "official prompts + gates (MIT); probe/summary on the agent's own model"
    cache_safe = False

    def __init__(self, min_round: int = 3, min_tokens: int = 40_000, min_frac: float = 0.31, period: int = 2,
                 cap: int = 1000, backstop: float = 0.8, summary_tokens: int = 8192, probe_tokens: int = 1024,
                 default_window: int = 200_000):
        self.min_round = int(min_round)
        self.min_tokens = int(min_tokens)
        self.min_frac = float(min_frac)
        self.period = int(period)
        self.cap = int(cap)
        self.backstop = float(backstop)
        self.summary_tokens = int(summary_tokens)
        self.probe_tokens = int(probe_tokens)
        self.default_window = int(default_window)

    def _window(self, ctx) -> int:
        return ctx.context_limit or getattr(ctx.model, "context_window", None) or self.default_window

    def on_session_start(self, ctx):
        ctx.state["sc"] = {"total": 0, "last_probe": None, "first": None, "round0": 0}

    def _call(self, ctx, text: str, max_tokens: int, tag: str):
        """The agent's own model on the live history + one appended instruction (same system prompt and tools)."""
        from eam.agent.loop import collect_tools

        msgs = copy.deepcopy(ctx.messages)
        msgs[-1]["content"].append({"text": text})
        tools = collect_tools(ctx.env_tools, ctx.techniques, ctx)
        req = Request(model=ctx.model, system=[{"text": ctx.system_text}], messages=msgs,
                      tools=[t.spec for t in tools], max_tokens=max_tokens, tag=tag)
        resp = ctx.llm.converse(req)
        ctx.meter.record(tag, ctx.model, resp.usage, resp.latency_ms, resp.reported_cost_usd)
        return resp

    def before_call(self, ctx):
        st = ctx.state["sc"]
        if ctx.step == 1:
            st["first"] = copy.deepcopy(ctx.messages[0])
            return
        last = ctx.messages[-1]
        if last["role"] != "user" or not any("toolResult" in b for b in last["content"]):
            return  # only after a tool round
        iteration = ctx.step - 1 - st["round0"]
        tokens = max(ctx.last_prompt_tokens, ctx.estimate_context_tokens())
        window = self._window(ctx)
        min_tokens = min(self.min_tokens, int(self.min_frac * window))
        forced = self.backstop > 0 and tokens >= self.backstop * window
        if not forced:
            gates = (iteration >= self.min_round and tokens >= min_tokens and st["total"] < self.cap
                     and (st["last_probe"] is None or iteration - st["last_probe"] >= self.period))
            if not gates:
                return
            st["last_probe"] = iteration
            resp = self._call(ctx, P.SELFCHECK_PROMPT, self.probe_tokens, "selfcompact:probe")
            answers = parse_rubric(resp.text) if not resp.tool_uses else dict.fromkeys(FIELDS)
            v, reason = verdict(answers)
            ctx.log("selfcompact_probe", answers=answers, verdict=v, reason=reason, tokens=tokens,
                    raw=resp.text[:600])
            if v != "COMPRESS":
                return
        summary = ""
        for _ in range(3):
            resp = self._call(ctx, f"{P.SUMMARIZE_PROMPT}\n\nQuestion being researched: {ctx.task}",
                              self.summary_tokens, "selfcompact:summary")
            raw = re.sub(r"<think>.*?</think>", "", resp.text or "", flags=re.DOTALL).strip()
            m = re.search(r"<summary>\s*(.*?)\s*</summary>", raw, flags=re.DOTALL | re.IGNORECASE)
            summary = m.group(1).strip() if m else raw
            if summary and not resp.tool_uses:
                break
            summary = ""
        if not summary:
            return
        first = copy.deepcopy(st["first"]) if st["first"] else copy.deepcopy(ctx.messages[0])
        ctx.messages[:] = [first,
                           {"role": "assistant", "content": [{"text": f"Here is my research so far:\n{summary}"}]},
                           {"role": "user", "content": [{"text": P.CONTINUE_AFTER_SUMMARY}]}]
        st["total"] += 1
        ctx.log("selfcompact_rebuild", tokens_before=tokens, forced=forced, n=st["total"])
