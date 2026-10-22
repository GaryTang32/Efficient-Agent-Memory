"""ReSum — periodic context summarisation (Alibaba Tongyi Lab; arXiv 2509.13313; not accepted at ICLR 2026,
kept as a labelled baseline). Trigger, prompts, summary extraction and reset message follow the official
WebResummer code (third_party/resum.py):

* summarise when the context reaches 0.9 × (MAX_CONTEXT·1024 − 1000) tokens (MAX_CONTEXT=32k by default),
  or every `every` rounds (the code's --summary_iteration, default 1000 = effectively off);
* the summariser sees the question, the previous summary (if any) and every message since the last reset;
  sampling temperature 0.6, 4096 max tokens, `<think>` stripped, `<summary>` extracted;
* the history is replaced by one user message: "Question: … Below is a summary … Summary: …".
"""

from __future__ import annotations

import json
import re

from eam.techniques.base import Technique
from eam.techniques.third_party import resum as P


def _as_message_str(msg) -> str:
    """Mirror `str(msg)` of the official OpenAI-format messages (assistant tool calls / tool responses inline)."""
    parts = []
    for b in msg["content"]:
        if "text" in b:
            parts.append(b["text"])
        elif "toolUse" in b:
            tu = b["toolUse"]
            parts.append("<tool_call>\n" + json.dumps({"name": tu["name"], "arguments": tu.get("input") or {}})
                         + "\n</tool_call>")
        elif "toolResult" in b:
            text = "\n".join(c.get("text", "") for c in b["toolResult"]["content"])
            parts.append(f"<tool_response>{text}</tool_response>")
    return str({"role": msg["role"], "content": "\n".join(parts)})


class ReSum(Technique):
    name = "resum"
    source = "ReSum (Alibaba Tongyi Lab)"
    provenance = "official prompts + trigger (MIT); not tier-1"
    cache_safe = False

    def __init__(self, max_context_k: float = 32, every: int = 1000, summary_tokens: int = 4096,
                 temperature: float = 0.6):
        self.max_context_k = float(max_context_k)
        self.every = int(every)
        self.summary_tokens = int(summary_tokens)
        self.temperature = float(temperature)

    @property
    def trigger_tokens(self) -> float:
        return 0.9 * (self.max_context_k * 1024 - 1000)

    def before_call(self, ctx):
        if len(ctx.messages) < 3:
            return
        rounds = ctx.step - 1
        tokens = max(ctx.last_prompt_tokens, ctx.estimate_context_tokens())
        if not (tokens >= self.trigger_tokens or (self.every > 0 and rounds % self.every == 0)):
            return
        last = ctx.state.get("resum_last_summary")
        history = "\n".join(_as_message_str(m) for m in ctx.messages[1:])
        template = P.QUERY_SUMMARY_PROMPT_LAST if last else P.QUERY_SUMMARY_PROMPT
        prompt = (template.replace("{{{question}}}", ctx.task).replace("{{{recent_history_messages}}}", history)
                  .replace("{{{last_summary}}}", last or ""))
        out = ctx.call_aux(prompt, purpose="resum", system="", temperature=self.temperature,
                           max_tokens=self.summary_tokens)
        out = re.sub(r"<think>.*?</think>", "", out, flags=re.S).strip()
        if not out:
            return
        if "<summary>" in out and "</summary>" in out:
            out = out.split("<summary>")[1].split("</summary>")[0]
        summary = f"<summary>{out}</summary>"
        ctx.state["resum_last_summary"] = summary
        ctx.messages[:] = [{"role": "user", "content": [
            {"text": P.NEW_OBSERVATION.format(question=ctx.task, summary=summary)}]}]
        ctx.log("resum_rebuild", tokens_before=tokens)
