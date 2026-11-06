"""Cross-session memory: facts revealed in earlier chats must be used later.
Stresses long-term memory (TieredMemory vs. carrying full transcripts vs. nothing)."""

from __future__ import annotations

import random
import re

from eam.bench.tasks.common import TaskInstance, contains_all
from eam.llm.mock import assistant, context_text, final, tool_use

AIRLINES = ["SkyWays", "Nordwind", "Aerolux", "BlueCrest", "Pacifica"]
ALLERGIES = ["peanuts", "shellfish", "sesame", "gluten", "kiwi"]
CHITCHAT = [
    "I watched a documentary about volcanoes last night and it was fascinating.",
    "My neighbour is learning to play the cello, which is lovely most of the time.",
    "Can you recommend a good way to organise my email inbox?",
    "I finally cleaned the garage over the weekend.",
    "Do you think it is better to read fiction or non-fiction before bed?",
    "My team switched to a new project tracker and everyone is still adjusting.",
    "I tried a new coffee shop near the office and the pastries were great.",
    "Is it worth learning a second programming language this year?",
    "My cousin is visiting next month and wants to see the museums.",
    "I have been trying to walk more instead of taking the bus.",
]
CHAT_SYSTEM = "You are a helpful personal assistant. Answer briefly. When asked a question, start with 'FINAL ANSWER:'."

AIR_RE = re.compile(r"I always fly with (\w+)")
ALL_RE = re.compile(r"I am allergic to (\w+)")
BUD_RE = re.compile(r"hotel budget is (\d+) dollars")


def generate(seed: int, n_sessions: int = 6, chatter: int = 3) -> TaskInstance:
    rng = random.Random(seed)
    airline, allergy, budget = rng.choice(AIRLINES), rng.choice(ALLERGIES), rng.randrange(90, 400, 10)
    facts = [f"By the way, I always fly with {airline} when I can.", f"Note that I am allergic to {allergy}.",
             f"For work trips my hotel budget is {budget} dollars per night."]
    fact_sessions = sorted(rng.sample(range(n_sessions), len(facts)))
    sessions = []
    for s in range(n_sessions):
        lines = rng.sample(CHITCHAT, chatter)
        if s in fact_sessions:
            lines.insert(rng.randrange(len(lines) + 1), facts[fact_sessions.index(s)])
        sessions.append(" ".join(lines))
    prompt = ("I'm planning a work trip next week. Which airline do I fly with, what food am I allergic to, and what "
              "is my hotel budget per night?")

    def oracle():
        searched = set()

        def policy(req):
            text = context_text(req)
            header = req.messages[0]["content"][0].get("text", "").split("\n", 1)[0]
            if "planning a work trip" not in header:
                return final("Noted — thanks for sharing!")
            if "memory_search" in {t.name for t in req.tools} and header not in searched:
                searched.add(header)
                return assistant(tool_use("memory_search", {"query": prompt}))
            a, b, c = AIR_RE.search(text), ALL_RE.search(text), BUD_RE.search(text)
            parts = [a.group(1) if a else "unknown airline", b.group(1) if b else "unknown allergy",
                     f"{c.group(1)} dollars" if c else "unknown budget"]
            return final("FINAL ANSWER: " + ", ".join(parts))
        return policy

    return TaskInstance(
        family="multi_session_profile", instance_id=f"profile-{seed}", prompt=prompt, tools=[],
        check=contains_all(airline, allergy, str(budget)), gold=f"{airline}, {allergy}, {budget}",
        oracle=oracle, sessions=sessions, system_prompt=CHAT_SYSTEM, max_steps=3,
    )
