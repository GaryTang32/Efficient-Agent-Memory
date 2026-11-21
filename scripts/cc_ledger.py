"""F1 of the Claude Code test plan (docs/plans/2026-11-21-automem-vs-claude-code-autocompact.md): a 10-day stock ledger.

Built on the benchmark's ops_stream design (it predates the plugin). A warehouse runs for D days and the agent tracks
six SKUs. Each day the warehouse system publishes three reports, available on that day only (the system replaces
them overnight, so earlier days cannot be re-read from disk unless the agent saved them itself):

    receipts   about 15K characters: RECEIPT and RETURN events (+qty) for about 30 SKUs
    shipments  about 15K characters: SHIPMENT events (-qty)
    audit      about 60K characters: cycle-count lines that change nothing, then, at the end, today's corrections:
               AMEND (an event's quantity becomes a new value) and VOID (an event is cancelled), by event id only,
               often for events of earlier days

Sizes are chosen around the two thresholds of the test: Claude Code shows up to 30,000 characters of a command's
output and cuts the rest; the plugin previews anything above 6,000. Day 1 also has an `opening` report.

The day's question: the closing stock of the six SKUs and the one with the lowest stock (7 exact checks). Answering
needs yesterday's closing stock and, for corrections, the SKU and quantity behind every earlier event they name.

    python scripts/cc_ledger.py check            # generate a few instances and verify them
"""

from __future__ import annotations

import base64
import gzip
import json
import random
import re
import sys
from pathlib import Path

SIGN = {"RECEIPT": 1, "RETURN": 1, "SHIPMENT": -1}
LETTERS = "ABCDEFGHKMNPRSTVWX"
CARRIERS = ["Nordfreight", "Bluewave", "Kestrel Haulage", "Orbis Cargo", "Lindqvist", "TransAlp"]
CUSTOMERS = ["Acme Ltd", "Brightline", "Corvel", "Dunmore & Sons", "Elbe Retail", "Fjordkraft", "Granite Works"]
REASONS = ["damaged", "wrong item", "surplus", "late delivery", "customer change"]
STAFF = ["S1", "S2", "S4", "S7", "S9", "S12"]

REPORT_TOOL = '''#!/usr/bin/env python3
"""Today's warehouse reports. Usage: python tools/report.py [list|opening|receipts|shipments|audit]"""
import base64, gzip, json, sys
from pathlib import Path
data = json.loads(gzip.decompress(base64.b64decode((Path(__file__).resolve().parents[1] / "data" / "today.bin").read_bytes())))
kind = sys.argv[1] if len(sys.argv) > 1 else "list"
if kind == "list" or kind not in data["reports"]:
    print(f"Day {data['day']}: reports available today: " + ", ".join(data["reports"]))
    sys.exit(0 if kind == "list" else 1)
print(data["reports"][kind])
'''


def _sku(rng: random.Random, used: set) -> str:
    while True:
        s = f"{rng.choice(LETTERS)}{rng.choice(LETTERS)}-{rng.randint(10, 99)}"
        if s not in used:
            used.add(s)
            return s


def _clock(rng: random.Random, i: int, n: int) -> str:
    minutes = 6 * 60 + int(i * (12 * 60) / max(1, n)) + rng.randint(0, 3)
    return f"{minutes // 60:02d}:{minutes % 60:02d}"


def generate(seed: int, days: int = 10, n_skus: int = 30, receipts_chars: int = 15_000,
             shipments_chars: int = 15_000, audit_chars: int = 60_000) -> dict:
    """One instance: the tracked SKUs, each day's three reports, and the answer key (closing stock, lowest)."""
    rng = random.Random(seed)
    used: set = set()
    skus = [_sku(rng, used) for _ in range(n_skus)]
    tracked = sorted(rng.sample(skus, 6))
    others = [s for s in skus if s not in tracked]
    stock = {s: rng.randint(300, 900) for s in skus}
    opening = ("OPENING STOCK (start of day 1)\n"
               + "\n".join(f"sku={s} | on_hand={stock[s]} | bin=B-{rng.randint(100, 399)}" for s in skus))
    events: dict[str, list] = {}  # id -> [sku, type, qty, day]
    ev = 50000 + rng.randint(0, 900)
    out_days, key = [], []

    def new_event(day: int, typ: str, sku: str) -> tuple[str, int]:
        nonlocal ev
        ev += rng.randint(1, 4)
        qty = rng.randint(5, 120)
        if typ == "SHIPMENT":
            qty = min(qty, stock[sku])
            if qty == 0:
                typ, qty = "RECEIPT", rng.randint(20, 120)
        eid = f"EV-{ev}"
        events[eid] = [sku, typ, qty, day]
        stock[sku] += SIGN[typ] * qty
        return eid, qty

    for d in range(1, days + 1):
        # --- receipts and returns, then shipments: event ids rise through the day across both reports
        lines_r, lines_s = [], []
        n_r = receipts_chars // 92
        n_s = shipments_chars // 88
        tracked_r = set(rng.sample(range(n_r), rng.randint(3, 6)))
        tracked_s = set(rng.sample(range(n_s), rng.randint(3, 6)))
        plan = [("R", i) for i in range(n_r)] + [("S", i) for i in range(n_s)]
        rng.shuffle(plan)
        for k, (which, i) in enumerate(plan):
            t = _clock(rng, k, len(plan))
            if which == "R":
                sku = rng.choice(tracked) if i in tracked_r else rng.choice(others)
                typ = "RETURN" if rng.random() < 0.15 else "RECEIPT"
                eid, qty = new_event(d, typ, sku)
                typ = events[eid][1]
                if typ == "RETURN":
                    lines_r.append(f"{eid} | {t} | RETURN  | sku={sku} | qty={qty} | rma=RMA-{rng.randint(1000, 9999)}"
                                   f" | reason={rng.choice(REASONS)}")
                else:
                    lines_r.append(f"{eid} | {t} | RECEIPT | sku={sku} | qty={qty} | dock=D{rng.randint(1, 6)}"
                                   f" | carrier={rng.choice(CARRIERS)} | po=PO-{rng.randint(10000, 99999)}")
            else:
                sku = rng.choice(tracked) if i in tracked_s else rng.choice(others)
                eid, qty = new_event(d, "SHIPMENT", sku)
                typ = events[eid][1]
                if typ == "SHIPMENT":
                    lines_s.append(f"{eid} | {t} | SHIPMENT | sku={sku} | qty={qty} | order=SO-{rng.randint(10000, 99999)}"
                                   f" | customer={rng.choice(CUSTOMERS)}")
                else:  # nothing left to ship: the slot became a receipt
                    lines_r.append(f"{eid} | {t} | RECEIPT | sku={sku} | qty={qty} | dock=D{rng.randint(1, 6)}"
                                   f" | carrier={rng.choice(CARRIERS)} | po=PO-{rng.randint(10000, 99999)}")
        # --- corrections: tracked events of earlier days (mostly) by id only, plus untracked noise
        corrections, targeted = [], set()  # one correction per event per day: the published order then cannot matter
        if d > 1:
            past_tracked = [e for e, v in events.items() if v[0] in tracked and v[2] > 0]
            for _ in range(rng.randint(2, 4)):
                target = rng.choice(past_tracked)
                if target in targeted:
                    continue
                sku, typ, old, _day = events[target]
                if rng.random() < 0.25:
                    new = 0
                    line = f"{target} | VOID"
                else:
                    new = max(1, old + rng.choice([-1, 1]) * rng.randint(5, 40))
                    line = f"{target} | AMEND | qty={new}"
                if stock[sku] + SIGN[typ] * (new - old) < 0:
                    continue
                stock[sku] += SIGN[typ] * (new - old)
                events[target][2] = new
                corrections.append(line)
                targeted.add(target)
            for _ in range(rng.randint(2, 4)):
                target = rng.choice([e for e, v in events.items() if v[0] not in tracked and v[2] > 0])
                sku, typ, old, _day = events[target]
                new = max(1, old + rng.randint(-20, 20))
                if target in targeted or stock[sku] + SIGN[typ] * (new - old) < 0:
                    continue
                targeted.add(target)
                stock[sku] += SIGN[typ] * (new - old)
                events[target][2] = new
                corrections.append(f"{target} | AMEND | qty={new}")
            rng.shuffle(corrections)
        # --- the audit log: cycle counts (no stock change) first, today's corrections at the very end
        audit, size = [f"AUDIT LOG, day {d}. Cycle-count checks first: they verify bins and change no stock."], 0
        while size < audit_chars - 1500:
            sku = rng.choice(skus)
            line = (f"{_clock(rng, size, audit_chars)}:{rng.randint(0, 59):02d} cycle-count | scanner={rng.choice(STAFF)}"
                    f" | bin=B-{rng.randint(100, 399)} | sku={sku} | counted=ok | no stock change")
            audit.append(line)
            size += len(line) + 1
        audit.append("")
        audit.append("CORRECTIONS POSTED TODAY. These change stock. AMEND sets the named event's quantity to the new "
                     "value; VOID cancels the named event. Events are named by id only.")
        audit.extend(corrections or ["(none today)"])
        reports = {"receipts": f"RECEIPTS AND RETURNS, day {d} (add to stock)\n" + "\n".join(lines_r),
                   "shipments": f"SHIPMENTS, day {d} (subtract from stock)\n" + "\n".join(lines_s),
                   "audit": "\n".join(audit)}
        if d == 1:
            reports = {"opening": opening, **reports}
        out_days.append(reports)
        closing = {s: stock[s] for s in tracked}
        key.append({"day": d, "stock": closing, "lowest": min(tracked, key=lambda s: (closing[s], s))})
    return {"seed": seed, "days": days, "tracked": tracked, "reports": out_days, "key": key}


# ---- the working folder ------------------------------------------------------------------------------------------
def write_tool(cwd: Path) -> None:
    (cwd / "tools").mkdir(parents=True, exist_ok=True)
    (cwd / "tools" / "report.py").write_text(REPORT_TOOL)
    (cwd / "data").mkdir(exist_ok=True)


def release_day(cwd: Path, inst: dict, day: int) -> None:
    """Replace the reports in `cwd` with day `day`'s; earlier days' reports are gone from the folder."""
    write_tool(cwd)
    blob = json.dumps({"day": day, "reports": inst["reports"][day - 1]}).encode()
    (cwd / "data" / "today.bin").write_bytes(base64.b64encode(gzip.compress(blob)))


NOTES_LINE = ("Keep a file NOTES.md in this folder with everything later days will need (each day's closing stock, "
              "the events behind it with their ids, SKUs and quantities, and the corrections applied), and read it "
              "first each day.")


def prompt(inst: dict, day: int, notes_prompt: bool = False) -> str:
    """The day's task, the same in every arm (A+ adds NOTES_LINE)."""
    names = ", ".join(inst["tracked"])
    opening = (" On day 1 there is also `python tools/report.py opening`: the opening stock." if day == 1 else "")
    text = (f"You are the stock controller of a warehouse. This job runs for {inst['days']} working days; today is "
            f"day {day} of {inst['days']}. Each day is a separate piece of work. Every day the warehouse system "
            "publishes three reports, which can be viewed only on that day (the system replaces them overnight): run "
            "`python tools/report.py receipts`, `python tools/report.py shipments` and `python tools/report.py "
            f"audit` in this folder.{opening}\n\n"
            f"You track six SKUs: {names}. RECEIPT and RETURN add to stock; SHIPMENT subtracts. The audit log ends "
            "with the corrections posted today: AMEND sets an earlier event's quantity to a new value, VOID cancels "
            "an event. Corrections name events by id only, and often correct events of earlier days. Later days "
            "build on earlier ones: each day's closing stock starts from the previous day's.\n\n")
    if notes_prompt:
        text += NOTES_LINE + "\n\n"
    text += ("When you are done, reply with today's closing stock of the six SKUs and the SKU with the lowest stock, "
             f'as a JSON object in this form: {{"day": {day}, "stock": {{"SKU": number, ...}}, "lowest": "SKU"}}')
    return text


# ---- grading ---------------------------------------------------------------------------------------------------------
def parse_answer(text: str) -> dict | None:
    """The last JSON object in `text` that has a "stock" mapping."""
    found = None
    for m in re.finditer(r"\{", text or ""):
        depth = 0
        for j in range(m.start(), len(text)):
            depth += {"{": 1, "}": -1}.get(text[j], 0)
            if depth == 0:
                try:
                    obj = json.loads(text[m.start(): j + 1])
                except ValueError:
                    break
                if isinstance(obj, dict) and isinstance(obj.get("stock"), dict):
                    found = obj
                break
    return found


def grade(text: str, key_day: dict) -> dict:
    """7 checks: each tracked SKU's closing stock, and the lowest SKU."""
    ans = parse_answer(text)
    checks = {}
    for sku, value in key_day["stock"].items():
        got = (ans or {}).get("stock", {}).get(sku)
        try:
            checks[sku] = got is not None and int(round(float(got))) == value
        except (TypeError, ValueError):
            checks[sku] = False
    checks["lowest"] = bool(ans) and str(ans.get("lowest", "")).strip() == key_day["lowest"]
    return {"parsed": ans is not None, "checks": checks, "correct": sum(checks.values()), "total": len(checks)}


# ---- self-check: the reports alone determine the key ------------------------------------------------------------
EVENT_RE = re.compile(r"^(EV-\d+) \| \d\d:\d\d \| (RECEIPT|RETURN|SHIPMENT) *\| sku=([A-Z]+-\d+) \| qty=(\d+)", re.M)
FIX_RE = re.compile(r"^(EV-\d+) \| (AMEND \| qty=(\d+)|VOID)$", re.M)
OPEN_RE = re.compile(r"^sku=([A-Z]+-\d+) \| on_hand=(\d+)", re.M)


def solve(inst: dict) -> list[dict]:
    """An oracle that reads only the reports, day by day, with perfect memory: proves the task is answerable."""
    stock = {s: int(n) for s, n in OPEN_RE.findall(inst["reports"][0]["opening"])}
    events: dict[str, list] = {}
    answers = []
    for d, rep in enumerate(inst["reports"], 1):
        for kind in ("receipts", "shipments"):
            for eid, typ, sku, qty in EVENT_RE.findall(rep[kind]):
                events[eid] = [sku, typ, int(qty)]
                stock[sku] += SIGN[typ] * int(qty)
        tail = rep["audit"].split("CORRECTIONS POSTED TODAY", 1)[1]
        for eid, what, qty in FIX_RE.findall(tail):
            sku, typ, old = events[eid]
            new = 0 if what == "VOID" else int(qty)
            stock[sku] += SIGN[typ] * (new - old)
            events[eid][2] = new
        closing = {s: stock[s] for s in inst["tracked"]}
        answers.append({"day": d, "stock": closing, "lowest": min(inst["tracked"], key=lambda s: (closing[s], s))})
    return answers


def check(seeds=range(5)) -> None:
    for seed in seeds:
        inst = generate(seed)
        assert solve(inst) == inst["key"], f"seed {seed}: the reports do not determine the key"
        for d, rep in enumerate(inst["reports"], 1):
            sizes = {k: len(v) for k, v in rep.items()}
            assert 9_000 < sizes["receipts"] < 22_000 and 9_000 < sizes["shipments"] < 22_000, sizes
            assert 50_000 < sizes["audit"] < 70_000, sizes
            if d > 1:
                assert rep["audit"].index("CORRECTIONS POSTED TODAY") > 30_000  # beyond Claude Code's inline cut
        print(f"seed {seed}: ok; day sizes {[ {k: len(v) // 1000 for k, v in r.items()} for r in inst['reports'][:2]]}")


if __name__ == "__main__":
    if sys.argv[1:] == ["check"]:
        check()
