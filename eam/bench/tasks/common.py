"""Shared pieces for synthetic, automatically-scored tasks."""

from __future__ import annotations

import random
from dataclasses import dataclass, field
from typing import Any, Callable

from eam.agent.context import Tool
from eam.llm.mock import Policy
from eam.tokens import estimate_tokens

SUBJECTS = ["The operations team", "Management", "The regional office", "The board", "Analysts", "The product group",
            "Customer support", "The logistics unit", "Engineering", "The finance department", "Procurement",
            "The compliance office"]
VERBS = ["reviewed", "expanded", "streamlined", "reorganized", "evaluated", "documented", "prioritized",
         "revisited", "consolidated", "piloted", "discussed", "audited"]
OBJECTS = ["its supplier relationships", "the onboarding process", "internal reporting standards",
           "the partner program", "quality assurance procedures", "long-term hiring plans",
           "the sustainability roadmap", "warehouse safety practices", "customer feedback channels",
           "the vendor scorecard", "travel and expense policies", "the knowledge base"]
TAILS = ["across several markets", "during the period under review", "in line with earlier guidance",
         "with mixed results", "as part of a broader initiative", "after consultation with stakeholders",
         "without major disruption", "ahead of the planned schedule", "following a short pilot",
         "at the request of the leadership team"]


def filler_sentence(rng: random.Random) -> str:
    return f"{rng.choice(SUBJECTS)} {rng.choice(VERBS)} {rng.choice(OBJECTS)} {rng.choice(TAILS)}."


def filler_paragraphs(rng: random.Random, n_tokens: int, per_paragraph: int = 5) -> list[str]:
    """Digit-free, fact-free text used to make tool outputs realistically long."""
    paragraphs, used = [], 0
    while used < n_tokens:
        para = " ".join(filler_sentence(rng) for _ in range(per_paragraph))
        paragraphs.append(para)
        used += estimate_tokens(para)
    return paragraphs


def contains_all(*needles: str) -> Callable[[str], bool]:
    lowered = [n.lower() for n in needles]
    return lambda answer: all(n in answer.lower() for n in lowered)


@dataclass
class TaskInstance:
    family: str
    instance_id: str
    prompt: str
    tools: list[Tool]
    check: Callable[[str], bool]
    gold: str
    oracle: Callable[[], Policy]  # factory: fresh mock policy per run
    resources: dict[str, Any] = field(default_factory=dict)
    sessions: list[str] = field(default_factory=list)  # earlier sessions (multi-session tasks)
    system_prompt: str | None = None
    max_steps: int = 30
    score: Callable[[str], float] | None = None  # partial credit in [0, 1]; defaults to check()
    rounds: list[str] = field(default_factory=list)  # multi-round tasks: one fresh session per prompt, all scored
    round_score: Callable[[int, str], float] | None = None
    context_limit: int | None = None  # requests above this many tokens end the run (simulated window)
    step_observation_budget: int | None = None  # harness cap on tool output per step (recoverable offload)
    disclose_limit: bool = False  # aware condition: state the limit and show a context gauge; unaware: silent
