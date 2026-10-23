"""Long-horizon state tracking over many sessions, with corrections to earlier facts (knowledge updates).

A warehouse runs for D days; each day is a fresh session. Each day brings 3 new event files (~3K tokens each,
45 events, only a few about the 6 tracked SKUs): receipts (+), shipments (−), returns (+), and AMEND / VOID lines
that correct an *earlier* event — often one from a previous day — by event id only, without naming its SKU. To
report end-of-day stock for the tracked SKUs, an agent must carry the stock levels across sessions *and* remember
which earlier events belong to which SKU and with what quantity (or re-read old files, which no longer fit in the
window after a few days). This is the "knowledge update" ability of long-term-memory benchmarks (LongMemEval,
ICLR'25) and the update operation of Mem0/MemoryOS-style memories, inside an agent loop.

Scoring per day: 6 stock levels + the tracked SKU with the lowest stock = 7 checks. `score` = mean over days,
`success` = every day exact.
"""

from __future__ import annotations

import random
import re

from eam.agent.context import Tool
from eam.bench.tasks.common import TaskInstance, filler_paragraphs
from eam.llm.mock import assistant, context_text, final, tool_exchanges, tool_use
from eam.llm.types import ToolSpec

PARTS = ["valve", "gasket", "bearing", "coupler", "flange", "sprocket", "bushing", "piston", "nozzle", "spindle",
         "bracket", "hinge", "pulley", "shim", "clamp"]
EVENT_RE = re.compile(r"(EV-\d+) \| day (\d+) \| (RECEIPT|SHIPMENT|RETURN) \| sku=([A-Z]+-\d+) \| qty=(\d+)")
AMEND_RE = re.compile(r"(EV-\d+) \| day (\d+) \| AMEND (EV-\d+) \| qty=(\d+)")
VOID_RE = re.compile(r"(EV-\d+) \| day (\d+) \| VOID (EV-\d+)")
SIGN = {"RECEIPT": 1, "RETURN": 1, "SHIPMENT": -1}


def generate(seed: int, n_days: int = 10, files_per_day: int = 3, events_per_file: int = 45,
             file_tokens: int = 3000, amends_per_file: int = 2, context_limit: int = 32_000,
             step_observation_budget: int | None = 6000,
             disclose_limit: bool = False) -> TaskInstance:
    rng = random.Random(seed)
    skus = [f"{rng.choice('ABCDEFGHKMNPRSTVWX')}{rng.choice('ABCDEFGHKMNPRSTVWX')}-{n}"
            for n in rng.sample(range(10, 99), 30)]
    tracked = rng.sample(skus, 6)
    stock = {s: rng.randint(300, 900) for s in skus}
    initial = dict(stock)
    events: dict[str, list] = {}  # id -> [sku, type, qty]
    files: dict[str, str] = {"INITIAL": "Opening stock (start of day 1)\n" + "\n".join(
        f"sku={s} | on_hand={stock[s]} | item={rng.choice(PARTS)}" for s in skus)}
    day_files: list[list[str]] = []
    expected: list[dict[str, int]] = []
    ev = 50000

    def apply(eid, new_qty):
        sku, typ, old = events[eid]
        stock[sku] += SIGN[typ] * (new_qty - old)
        events[eid][2] = new_qty

    for d in range(1, n_days + 1):
        ids = []
        for f in range(files_per_day):
            fid = f"D{d:02d}-{'ABC'[f]}"
            ids.append(fid)
            lines = []
            relevant = set(rng.sample(range(events_per_file), rng.randint(2, 4)))
            free = sorted(set(range(events_per_file)) - relevant)
            amend_slots = set(rng.sample(free, amends_per_file)) if d > 1 else set()
            for j in range(events_per_file):
                ev += rng.randint(1, 7)
                eid = f"EV-{ev}"
                past_tracked = [e for e, v in events.items() if v[0] in tracked and v[2] > 0]
                if j in amend_slots and past_tracked and rng.random() < 0.7:
                    # correct an earlier tracked event (usually from a previous day), by id only
                    target = rng.choice(past_tracked)
                    sku, typ, old = events[target]
                    if rng.random() < 0.25:
                        lines.append(f"{eid} | day {d} | VOID {target}")
                        new = 0
                    else:
                        new = max(1, old + rng.choice([-1, 1]) * rng.randint(5, 40))
                        lines.append(f"{eid} | day {d} | AMEND {target} | qty={new}")
                    if stock[sku] + SIGN[typ] * (new - old) >= 0:
                        apply(target, new)
                    else:  # would make stock negative: keep the original, drop the line
                        lines.pop()
                    continue
                if j in amend_slots:  # amendment of an untracked event (noise)
                    target = rng.choice([e for e, v in events.items() if v[0] not in tracked] or [eid])
                    if target in events:
                        new = max(1, events[target][2] + rng.randint(-20, 20))
                        lines.append(f"{eid} | day {d} | AMEND {target} | qty={new}")
                        apply(target, new)
                        continue
                sku = rng.choice(tracked) if j in relevant else rng.choice([s for s in skus if s not in tracked])
                typ = rng.choices(["RECEIPT", "SHIPMENT", "RETURN"], [3, 5, 1])[0]
                qty = rng.randint(5, 120)
                if typ == "SHIPMENT":
                    qty = min(qty, stock[sku])
                    if qty == 0:
                        typ, qty = "RECEIPT", rng.randint(20, 120)
                events[eid] = [sku, typ, qty]
                stock[sku] += SIGN[typ] * qty
                lines.append(f"{eid} | day {d} | {typ} | sku={sku} | qty={qty}")
            filler = filler_paragraphs(rng, max(0, file_tokens - events_per_file * 22))
            files[fid] = (f"Warehouse events {fid} (day {d})\n\n" + "\n\n".join(filler[: len(filler) // 2])
                          + "\n\nEvents:\n" + "\n".join(lines) + "\n\n" + "\n\n".join(filler[len(filler) // 2:]))
        day_files.append(ids)
        expected.append({s: stock[s] for s in tracked})

    names = ", ".join(tracked)

    def today(ctx) -> int:  # files of later days do not exist yet
        m = re.search(r"DAY (\d+) of", ctx.task)
        return int(m.group(1)) if m else n_days

    def list_files(args, ctx):
        return "\n".join(["INITIAL (opening stock)"] + [f"day {d + 1}: {', '.join(ids)}"
                                                       for d, ids in enumerate(day_files[: today(ctx)])])

    def open_file(args, ctx):
        fid = str(args.get("file_id", "")).strip()
        visible = {"INITIAL"} | {f for ids in day_files[: today(ctx)] for f in ids}
        if fid not in files or fid not in visible:
            raise ValueError(f"no file '{fid}' (yet)")
        return files[fid]

    def calc(args, ctx):
        from eam.bench.tasks.ledger_audit import safe_eval
        return str(round(safe_eval(str(args.get("expression", ""))), 6))

    intro = (f"You are the stock controller of a warehouse over {n_days} working days. Each day is a separate "
             "session: the conversation of earlier days is not available to you. You track six SKUs: "
             f"{names}. Event files contain RECEIPT (+qty), SHIPMENT (−qty) and RETURN (+qty) events for many SKUs, "
             "plus corrections of earlier events: 'AMEND EV-x | qty=q' replaces the quantity of event EV-x, and "
             "'VOID EV-x' cancels it. Corrections may refer to events from earlier days and do not repeat the "
             "SKU. Opening stock is in file INITIAL; all earlier files stay available.")
    rounds = [f"{intro}\n\nDAY {d + 1} of {n_days}: today's event files are {', '.join(ids)}. Report the stock on "
              "hand at the end of today for each tracked SKU, one line per SKU as '<SKU> = <units>', then name the "
              "tracked SKU with the lowest stock." for d, ids in enumerate(day_files)]

    def score_round(k: int, answer: str) -> float:
        exp = expected[k]
        hits = []
        for s in tracked:
            ok = False
            for line in answer.splitlines():
                if s in line:
                    nums = [int(x) for x in re.findall(r"(?<![\w-])\d+", line.replace(s, " ").replace(",", ""))]
                    ok = ok or exp[s] in nums
            hits.append(ok)
        low = min(tracked, key=lambda s: (exp[s], s))
        tail = answer.lower().split("lowest")[-1] if "lowest" in answer.lower() else answer.lower()[-200:]
        hits.append(low.lower() in tail)
        return sum(hits) / len(hits)

    gold = " || ".join(f"day {k + 1}: " + ", ".join(f"{s}={v}" for s, v in e.items()) for k, e in enumerate(expected))

    def oracle():
        """Mock controller: re-derives everything from visible files, or continues from notes if a workspace is
        offered (notes hold the stock and the tracked events)."""
        st = {"day": None, "queue": [], "noted": False}

        def policy(req):
            text = context_text(req)
            first = req.messages[0]["content"][0].get("text", "")
            k = int(re.search(r"DAY (\d+) of", first).group(1)) - 1
            tools_ = {t.name for t in req.tools}
            if st["day"] != k:
                st.update(day=k, queue=[], noted=False)
                if "read_notes" in tools_:
                    return assistant(tool_use("read_notes", {}))
            if not st["queue"] and not any(n == "open_file" for n, _, _ in tool_exchanges(req.messages)):
                have = re.findall(r"state day (\d+)", text)
                start = int(have[-1]) if have else 0
                st["queue"] = ([] if have else ["INITIAL"]) + [f for ids in day_files[start: k + 1] for f in ids]
            if st["queue"]:
                return assistant(tool_use("open_file", {"file_id": st["queue"].pop(0)}))
            # rebuild state: notes first, then events visible in the context
            cur = {s: 0 for s in tracked}
            evs: dict[str, list] = {}
            notes = re.findall(r"stock (\S+) = (-?\d+)", text)
            if notes:
                for s, v in notes:
                    cur[s] = int(v)
                for e, s, t, q in re.findall(r"event (EV-\d+) (\S+) (\w+) (\d+)", text):
                    evs[e] = [s, t, int(q)]
            else:
                for s, v in re.findall(r"sku=([A-Z]+-\d+) \| on_hand=(\d+)", text):
                    if s in cur:
                        cur[s] = int(v)
            seen = set()
            for line in text.splitlines():
                m = EVENT_RE.search(line)
                if m and m.group(1) not in seen and m.group(1) not in evs:
                    seen.add(m.group(1))
                    e, _, t, s, q = m.groups()
                    if s in cur:
                        evs[e] = [s, t, int(q)]
                        cur[s] += SIGN[t] * int(q)
                    continue
                m = AMEND_RE.search(line) or VOID_RE.search(line)
                if m and m.group(1) not in seen:
                    seen.add(m.group(1))
                    target = m.group(3)
                    new = int(m.group(4)) if len(m.groups()) > 3 else 0
                    if target in evs:
                        s, t, old = evs[target]
                        cur[s] += SIGN[t] * (new - old)
                        evs[target][2] = new
            if "write_note" in tools_ and not st["noted"]:
                st["noted"] = True
                body = (f"state day {k + 1}\n" + "\n".join(f"stock {s} = {v}" for s, v in cur.items()) + "\n"
                        + "\n".join(f"event {e} {s} {t} {q}" for e, (s, t, q) in evs.items()))
                return assistant(tool_use("write_note", {"name": "state", "content": body}))
            low = min(tracked, key=lambda s: (cur[s], s))
            return final("FINAL ANSWER:\n" + "\n".join(f"{s} = {v}" for s, v in cur.items()) + f"\nLowest: {low}")

        return policy

    return TaskInstance(
        family="ops_stream", instance_id=f"ops-{seed}", prompt=rounds[-1], tools=[
            Tool(ToolSpec("list_files", "List the event files available so far.",
                          {"type": "object", "properties": {}}), list_files),
            Tool(ToolSpec("open_file", "Open one file by id (e.g. D03-B or INITIAL) and return its full text.",
                          {"type": "object", "properties": {"file_id": {"type": "string"}}, "required": ["file_id"]}),
                 open_file),
            Tool(ToolSpec("calc", "Evaluate an arithmetic expression (+ - * / and parentheses).",
                          {"type": "object", "properties": {"expression": {"type": "string"}},
                           "required": ["expression"]}), calc),
        ],
        check=lambda a: False, gold=gold, oracle=oracle, max_steps=40, rounds=rounds, round_score=score_round,
        context_limit=context_limit, step_observation_budget=step_observation_budget, disclose_limit=disclose_limit,
    )
