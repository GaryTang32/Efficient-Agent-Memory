"""Deep, sequential task for real models: follow a chain of long files, keep a fragment from every stage,
and handle one correction that points back to an earlier file.

Why this shape:
* the next file id is only revealed inside the current file, so reads cannot be batched in parallel and the
  context grows step by step (real models finished the wide tasks in ~3 parallel steps);
* every stage's fragment must survive until the final answer, so a technique that drops earlier tool
  output without the agent having noted it shows up as a wrong answer (`score` = fraction of fragments right);
* the correction ("use the alternate fragment for stage j") makes an earlier observation relevant again —
  the focus-shift case that motivates AttnCompress's rolling window; agents whose context still holds that
  file answer directly, others must re-open it (more steps and cost).
"""

from __future__ import annotations

import random
import re
import string

from eam.agent.context import Tool
from eam.bench.tasks.common import TaskInstance, filler_paragraphs
from eam.llm.mock import assistant, context_text, final, tool_exchanges, tool_use
from eam.llm.types import ToolSpec

FRAG_RE = re.compile(r"the access fragment for stage (\d+) is '([A-Z0-9]{4})'")
ALT_RE = re.compile(r"alternate fragment for stage (\d+) is '([A-Z0-9]{4})'")
NEXT_RE = re.compile(r"Next: open file (F-\d{3})")
CORR_RE = re.compile(r"use the alternate fragment for stage (\d+)")


def _frag(rng: random.Random) -> str:
    return "".join(rng.choice(string.ascii_uppercase + string.digits) for _ in range(4))


def generate(seed: int, n_stages: int = 20, doc_tokens: int = 1500, n_files: int = 60,
             correction_at: float = 0.6) -> TaskInstance:
    rng = random.Random(seed)
    ids = [f"F-{i:03d}" for i in rng.sample(range(100, 1000), n_files)]
    chain = ids[:n_stages]
    frags = [_frag(rng) for _ in range(n_stages)]
    alts = [_frag(rng) for _ in range(n_stages)]
    corr_stage = max(1, int(n_stages * correction_at))          # stage whose file carries the correction
    target = rng.randrange(0, max(1, corr_stage - 3))            # an early stage to revisit
    expected = list(frags)
    expected[target] = alts[target]

    files: dict[str, str] = {}
    for i, fid in enumerate(chain):
        paras = filler_paragraphs(rng, doc_tokens)
        facts = [f"Clue {i + 1}: the access fragment for stage {i + 1} is '{frags[i]}'.",
                 f"Archive note: the alternate fragment for stage {i + 1} is '{alts[i]}' (ignore it unless a later "
                 "file instructs otherwise)."]
        if i == corr_stage:
            facts.append(f"Correction: for stage {target + 1}, use the alternate fragment for stage {target + 1} "
                         f"recorded in file {chain[target]} instead of its regular fragment.")
        facts.append(f"Next: open file {chain[i + 1]}." if i + 1 < n_stages
                     else "This is the final stage of the chain. No further files are needed.")
        slots = sorted(rng.sample(range(len(paras)), min(len(facts), len(paras))))
        for slot, fact in zip(slots, facts):
            paras[slot] = f"{paras[slot]} {fact}"
        files[fid] = f"File {fid}\n\n" + "\n\n".join(paras)
    for fid in ids[n_stages:]:  # distractors: never on the chain
        files[fid] = f"File {fid}\n\n" + "\n\n".join(filler_paragraphs(rng, doc_tokens))

    def list_files(args, ctx):
        return "Files in the archive: " + ", ".join(sorted(ids))

    def open_file(args, ctx):
        fid = str(args.get("file_id", "")).strip()
        if fid not in files:
            raise ValueError(f"no file '{fid}'")
        return files[fid]

    tools = [
        Tool(ToolSpec("list_files", "List the ids of all files in the archive.", {"type": "object", "properties": {}}),
             list_files),
        Tool(ToolSpec("open_file", "Open one file by id and return its full text. Files are long.",
                      {"type": "object", "properties": {"file_id": {"type": "string"}}, "required": ["file_id"]}),
             open_file),
    ]
    prompt = (f"An access code is split across a chain of {n_stages} files in the archive. Start with file "
              f"{chain[0]}. Each file states the access fragment for its stage and which file to open next. "
              "Follow the chain to the end, and obey any corrections you find along the way. Report the full access "
              f"code: the {n_stages} stage fragments in stage order, joined with '-'.")
    gold = "-".join(expected)

    def score(answer: str) -> float:
        found = re.findall(r"[A-Z0-9]{4}(?:-[A-Z0-9]{4})+", answer.upper())
        if not found:
            return 0.0
        got = max(found, key=len).split("-")
        return sum(1 for i, f in enumerate(expected) if i < len(got) and got[i] == f) / len(expected)

    def oracle():
        state = {"opened": [], "recovered": set()}

        def policy(req):
            text = context_text(req)
            names = {t.name for t in req.tools}
            known = {int(s): f for s, f in FRAG_RE.findall(text)}
            alts_seen = {int(s): f for s, f in ALT_RE.findall(text)}
            corr = [int(s) for s in CORR_RE.findall(text)]
            if not state["opened"]:
                state["opened"].append(chain[0])
                return assistant(tool_use("open_file", {"file_id": chain[0]}))
            # recover truncated/cleared content we still need (offload / masking pointers)
            for name, inp, result in tool_exchanges(req.messages):
                m = re.search(r"artifact://(a\d+)", result)
                if m and "read_artifact" in names and m.group(1) not in state["recovered"] and name == "open_file":
                    state["recovered"].add(m.group(1))
                    return assistant(tool_use("read_artifact", {"artifact_id": m.group(1), "length": 100000}))
            nxt = NEXT_RE.findall(text)
            last = state["opened"][-1]
            pending = [n for n in nxt if n not in state["opened"]]
            if pending:
                state["opened"].append(pending[-1])
                return assistant(tool_use("open_file", {"file_id": pending[-1]}))
            if corr and corr[-1] not in alts_seen and chain[corr[-1] - 1] != last:
                state["opened"].append(chain[corr[-1] - 1])  # re-open the earlier file
                return assistant(tool_use("open_file", {"file_id": chain[corr[-1] - 1]}))
            code = []
            for s in range(1, n_stages + 1):
                code.append(alts_seen.get(s, "????") if s in corr else known.get(s, "????"))
            return final("FINAL ANSWER: " + "-".join(code))

        return policy

    return TaskInstance(
        family="chain_hunt", instance_id=f"chain-{seed}", prompt=prompt, tools=tools,
        check=lambda a: score(a) == 1.0, gold=gold, oracle=oracle, max_steps=n_stages + 15, score=score,
    )
