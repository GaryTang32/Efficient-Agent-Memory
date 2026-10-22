"""Prompt compression of tool outputs — LLMLingua-2 (Microsoft Research Asia).

Runs at ingestion (cache-safe). Uses LLMLingua-2 if ``llmlingua`` is installed
(a small token-classification model on CPU — not LLM hosting); otherwise a
crude extractive fallback that keeps the most information-dense sentences.
The original is kept in the artifact store and a pointer appended.
"""

from __future__ import annotations

import re

from eam.techniques.base import Technique
from eam.techniques.common import read_artifact_tool
from eam.tokens import estimate_tokens


def heuristic_compress(text: str, rate: float) -> str:
    seen: set[str] = set()
    lines = []
    for line in text.splitlines():
        key = " ".join(line.split()).lower()
        if key and key not in seen:
            seen.add(key)
            lines.append(" ".join(line.split()))
    sentences = [s for line in lines for s in re.split(r"(?<=[.!?])\s+", line) if s]
    budget = max(1, int(estimate_tokens(text) * rate))

    def density(s: str) -> float:
        words = re.findall(r"\w+", s)
        if not words:
            return 0.0
        return (3.0 * bool(re.search(r"\d", s)) + 0.3 * len(re.findall(r"\b[A-Z][a-zA-Z]+", s))
                + len(set(w.lower() for w in words)) / len(words))

    order = sorted(range(len(sentences)), key=lambda i: -density(sentences[i]))
    keep, used = set(), 0
    for i in order:
        cost = estimate_tokens(sentences[i])
        if used + cost > budget:
            continue
        keep.add(i)
        used += cost
    return " ".join(sentences[i] for i in sorted(keep))


class PromptCompression(Technique):
    name = "compression"
    source = "LLMLingua-2 (Microsoft Research Asia)"
    provenance = "official llmlingua library if installed (Findings ACL'24); the fallback heuristic is ours"

    def __init__(self, min_tokens: int = 600, rate: float = 0.4, backend: str = "auto"):
        self.min_tokens = int(min_tokens)
        self.rate = float(rate)
        self.backend = backend
        self._lingua = None

    def tools(self, ctx):
        return [read_artifact_tool()]

    def _compress(self, text: str) -> str:
        if self.backend in ("auto", "llmlingua") and self._lingua is None:
            try:
                from llmlingua import PromptCompressor

                self._lingua = PromptCompressor(
                    model_name="microsoft/llmlingua-2-xlm-roberta-large-meetingbank",
                    use_llmlingua2=True, device_map="cpu")
            except ImportError:
                if self.backend == "llmlingua":
                    raise
                self.backend = "heuristic"
        if self._lingua is not None:
            return self._lingua.compress_prompt(text, rate=self.rate, force_tokens=["\n", ".", "?"])["compressed_prompt"]
        return heuristic_compress(text, self.rate)

    def on_tool_result(self, ctx, outcome):
        if outcome.name == "read_artifact" or estimate_tokens(outcome.text) < self.min_tokens:
            return outcome
        aid = ctx.store.put(outcome.text, label=f"{outcome.name} {outcome.input}")
        outcome.text = (f"{self._compress(outcome.text)}\n[compressed view; original at "
                        f"{ctx.store.pointer(aid)} — call read_artifact if a detail is missing]")
        ctx.log("compressed", artifact=aid)
        return outcome
