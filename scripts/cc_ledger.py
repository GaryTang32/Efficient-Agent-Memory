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

With `inbox_chars` > 0 (the long-session cells, R100), each day also brings an inbox: 10 to 14 messages from staff,
suppliers, carriers and customers, about `inbox_chars` characters in all (100,000, about 25K tokens). Messages name
products by description ("ball valves in cobalt"), never by SKU. A few change stock in plain words: a write-off, stock
found in a recount, or a shipment or delivery that turned out short (named by its order or PO number, often from an
earlier day; its quantity becomes the stated number). Others only mention products (an arrival next week, a
reservation request, a false alarm, a move between bins). They have to be read, not searched: this is what makes a
resumed session fill up, as real sessions do through reading. The inbox has its own random stream, so instances
without it are unchanged.

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


# ---- the inbox (long-session cells) ---------------------------------------------------------------------------
MATERIALS = ["cobalt", "brass", "copper", "matte black", "stainless", "galvanised", "chrome", "bronze", "nickel",
             "white nylon"]
TYPES = ["ball valve", "gate valve", "check valve", "pipe clamp", "hose coupling", "pressure gauge", "flange gasket",
         "elbow joint", "drain trap", "filter housing"]
SIZES = ["15 mm", "22 mm", "28 mm", "35 mm", "2-inch", "3-inch"]
REF_RE = re.compile(r"\| (?:po|order)=((?:PO|SO)-\d+)")
PEOPLE = ["Maria Lindgren", "Tom Okafor", "Priya Nair", "Jonas Weber", "Aisha Rahman", "Luca Bianchi", "Sofia Duarte",
          "Ben Carter", "Mei Chen", "Oskar Nilsson", "Hannah Becker", "Dev Patel"]
ROLES = ["warehouse supervisor", "inbound team lead", "dispatch coordinator", "inventory clerk", "account manager",
         "customer service", "quality inspector", "night shift lead"]
WEEKDAYS = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday"]
# what a message can say about stock; {ref} names a product by description, {so}/{po} an earlier order or delivery.
# Effects change stock; mentions do not. Each effect template is matched exactly by the oracle (EFFECT_RES).
EFFECTS = {
    "writeoff": [("{who} found {n} {ref} damaged in the racking this morning. They cannot be sold, so please write them "
                 "off."),
                 "Please write off {n} {ref}: the cartons were crushed when a pallet came down in aisle {aisle}.",
                 "We have to scrap {n} {ref} after the leak by aisle {aisle}, so please take them off the books today."],
    "found": ["During the recount we found {n} {ref} that were never booked in. Please add them to stock.",
              "There were {n} extra {ref} on the overflow shelf. They are ours, so please book them into stock.",
              "The night shift turned up {n} {ref} behind the returns cage; they belong in stock, please add them."],
    "short_ship": [("About order {so}: only {k} units actually left the dock and the rest is still on our shelves. "
                   "Please correct that shipment to {k} units."),
                   ("The driver for order {so} could only take {k} units, so that shipment was really {k} units; the "
                   "remainder never left the building.")],
    "short_receipt": [("The delivery on {po} was short. We counted {k} units, not the quantity on the paperwork, so "
                      "please correct that receipt to {k} units."),
                      ("Our check of the delivery on {po} found only {k} units on the pallet. Please book that receipt "
                      "as {k} units.")],
}
MENTIONS = ["{supplier} confirms that {n} {ref} will arrive next week. There is nothing to book until they are here.",
            "{customer} asked whether we could hold {n} {ref} for them next month. Nothing is reserved yet.",
            "The {n} {ref} that looked damaged earlier were inspected and are fine, so nothing needs writing off.",
            "We moved {n} {ref} from bin B-{b1} to bin B-{b2}. The count is unchanged.",
            "A customer asked for a quote on {n} {ref}; could someone check the price list before Friday?",
            "{who} wants to know whether the {n} {ref} on the picking list for next week are confirmed. No change yet."]
FILLER = {
    "carriers": ["{carrier} will collect from dock D{dock} at {time} instead of the usual slot.",
                 "Their driver asked us to have the delivery notes ready at the gate before the truck is loaded.",
                 "{carrier} has a new booking portal, and slots now have to be confirmed a day ahead.",
                 "The {weekday} run to {customer} is moving to the afternoon because of road works near their site.",
                 "If a collection is missed, please log it in the carrier sheet so accounts can query the charge.",
                 "Two of the trailers this week are double-deckers, so the loading order matters more than usual."],
    "staff": ["{who} is on leave from {weekday} to {weekday2}, so {who2} covers the early shift.",
              "The forklift refresher course is booked for {weekday}; please let me know if you cannot make it.",
              "We welcome two agency colleagues this week, and they will shadow the picking team first.",
              "Overtime for the weekend stocktake is optional, but please tell your lead by {weekday}.",
              "The canteen is closed on {weekday} for the deep clean, and sandwiches will be brought in instead.",
              "{who2} has moved to the inbound team, so questions about deliveries go to them from now on."],
    "safety": ["Please keep the fire exits by aisle {aisle} clear; the inspector walks through on {weekday}.",
               "High-visibility vests are compulsory in the yard, including for visiting drivers.",
               "We had a near miss at dock D{dock} when a pallet jack was left on the ramp, so please park them away.",
               "The first-aid kit in the dispatch office has been restocked, and the logbook is beside it.",
               "Racking inspections continue this month, and bays with a red tag must not be loaded.",
               "Please report spills straight away, even small ones, so the floor team can deal with them."],
    "systems": ["The scanner firmware update is scheduled for {time}, so expect the handhelds to restart once.",
                "The label printer at packing station {dock} is jamming; IT has a replacement on order.",
                "The stock system will be read-only for about twenty minutes at {time} while the backup runs.",
                "If a handheld shows an old pick list, log out and in again before raising a ticket.",
                "The new dashboard for dock bookings is live, and the old spreadsheet is retired on {weekday}.",
                "Password resets now go through the self-service page rather than the help desk."],
    "customers": ["{customer} thanked the team for the quick turnaround on last week's orders.",
                  "{customer} has asked for photos of each pallet before it leaves, starting next week.",
                  "We received a complaint from {customer} about torn shrink wrap, so please double-wrap their loads.",
                  "{customer} is changing their delivery address for the next quarter; the new one is in the system.",
                  "The account review with {customer} went well, and they expect volumes to stay steady.",
                  "{customer} prefers morning deliveries, so please put their orders at the front of the queue."],
    "facilities": ["The roller door on dock D{dock} is sticking again, and maintenance has been called.",
                   "Lights in aisle {aisle} will be replaced with LED panels over the weekend.",
                   "The yard will be resurfaced on {weekday}, so trucks will queue on the side road for the morning.",
                   "Heating in the packing area has been fixed, but tell facilities if it drops again.",
                   "The compressor for the shrink-wrap machine is being serviced on {weekday} afternoon.",
                   "Please do not stack empty pallets against the north wall; the drain there needs access."],
    "admin": ["Accounts asked that all delivery notes are scanned by the end of each day.",
              "The weekly planning call moves to {time} on {weekday}.",
              "Please use the new template for damage reports; the old one is missing the photo field.",
              "Month-end is next week, so invoices for any extra handling need to be with accounts by {weekday}.",
              "The audit firm will visit later this month and may ask to see the cycle-count records.",
              "Minutes from the last operations meeting are on the shared drive, under this month's folder."],
    "weather": ["Heavy rain is forecast for the afternoon, so expect some carriers to run late.",
                "Frost is likely overnight; the yard will be gritted before the first trucks arrive.",
                "Strong winds are expected on {weekday}, so keep the dock doors closed when not loading.",
                "Traffic on the ring road has been bad all week, and drivers are building in extra time.",
                "It will be hot later this week, so please take breaks and keep water at the stations.",
                "Fog this morning delayed two inbound trucks by about an hour; both are now unloaded."],
}
GREETINGS = ["Hi all,", "Hello,", "Hi team,", "Good morning,", "Dear stock control,", "Hi,"]
SIGNOFFS = ["Thanks,", "Best regards,", "Cheers,", "Many thanks,", "Kind regards,", "Thanks again,"]


class Inbox:
    """Each day's messages, and the stock changes they carry (applied to the generator's state)."""

    def __init__(self, seed: int, skus: list[str]):
        self.rng = random.Random(seed * 7919 + 17)  # its own stream: instances without an inbox are unchanged
        pairs = [(m, t) for m in MATERIALS for t in TYPES]
        self.rng.shuffle(pairs)
        self.items = {s: (m, t, self.rng.choice(SIZES)) for s, (m, t) in zip(skus, pairs)}  # (material, type) unique

    def name(self, sku: str) -> str:
        m, t, size = self.items[sku]
        return f"{m} {t}, {size}"

    def ref(self, sku: str) -> str:
        m, t, size = self.items[sku]
        return self.rng.choice([f"{m} {t}s", f"{t}s in {m}", f"{size} {m} {t}s", f"{m} {t}s ({size})"])

    def _fill(self, text: str, **kw) -> str:
        r = self.rng
        who, who2 = r.sample(PEOPLE, 2)
        wd, wd2 = sorted(r.sample(range(len(WEEKDAYS)), 2))
        slots = {"who": who, "who2": who2, "carrier": r.choice(CARRIERS),
                 "customer": r.choice(CUSTOMERS), "supplier": r.choice(CARRIERS[:3]) + " Supply",
                 "dock": r.randint(1, 6), "aisle": r.randint(1, 24), "time": f"{r.randint(6, 17):02d}:{r.choice(['00', '15', '30', '45'])}",
                 "weekday": WEEKDAYS[wd], "weekday2": WEEKDAYS[wd2], "b1": r.randint(100, 399),
                 "b2": r.randint(400, 699), **kw}
        return text.format(**slots)

    def _paragraph(self) -> str:
        topic = self.rng.choice(list(FILLER))
        return " ".join(self._fill(x) for x in self.rng.sample(FILLER[topic], self.rng.randint(3, 5)))

    def day(self, d: int, chars: int, tracked: list, others: list, stock: dict, events: dict, refs: dict,
            targeted: set) -> list[tuple[str, str]]:
        """Pick the day's facts, apply the effects to `stock` and `events`, and write the messages."""
        r = self.rng
        facts = []

        def item_effect(kind: str, sku: str) -> None:
            if kind == "writeoff":
                n = min(r.randint(3, 30), stock[sku])
                if n <= 0:
                    return
                stock[sku] -= n
            else:
                n = r.randint(2, 25)
                stock[sku] += n
            facts.append(self._fill(r.choice(EFFECTS[kind]), n=n, ref=self.ref(sku)))

        def event_effect(kind: str, pool: list) -> None:
            typ = "SHIPMENT" if kind == "short_ship" else "RECEIPT"
            seen = {}
            for e, ref in refs.items():
                seen[ref] = seen.get(ref, 0) + 1
            cands = [e for e, v in events.items() if v[0] in pool and v[1] == typ and v[2] >= 10
                     and e not in targeted and e in refs and seen[refs[e]] == 1]
            if not cands:
                return
            e = r.choice(cands)
            sku, _, old, _ = events[e]
            k = r.randint(max(1, old // 4), old - 3)
            if stock[sku] + SIGN[typ] * (k - old) < 0:
                return
            stock[sku] += SIGN[typ] * (k - old)
            events[e][2] = k
            targeted.add(e)
            facts.append(self._fill(r.choice(EFFECTS[kind]), k=k, so=refs[e], po=refs[e]))

        for pool, n_eff in ((tracked, r.randint(2, 4)), (others, r.randint(1, 3))):
            for _ in range(n_eff):
                kind = r.choice(list(EFFECTS))
                if kind in ("writeoff", "found"):
                    item_effect(kind, r.choice(pool))
                else:
                    event_effect(kind, pool)
        for _ in range(r.randint(3, 6)):
            sku = r.choice(tracked if r.random() < 0.5 else others)
            facts.append(self._fill(r.choice(MENTIONS), n=r.randint(5, 80), ref=self.ref(sku)))
        r.shuffle(facts)
        n_msg = r.randint(10, 14)
        slots = [[] for _ in range(n_msg)]
        for f in facts:
            slots[r.randrange(n_msg)].append(f)
        out = []
        for i, mine in enumerate(slots, 1):
            target = chars / n_msg * r.uniform(0.6, 1.4)
            sender, role = r.choice(PEOPLE), r.choice(ROLES)
            paras = []
            while sum(len(p) for p in paras) < target - 400:
                paras.append(self._paragraph())
            for f in mine:  # a fact sits inside a paragraph, among ordinary sentences
                j = r.randrange(len(paras) + 1)
                paras.insert(j, f + " " + self._paragraph() if r.random() < 0.5 else f)
            subject = r.choice(["Update from the floor", "This week", "Quick note", "Dock and yard", "Follow-up",
                                "Notes from today", "Customer and carrier news", "Odds and ends", "Re: stock queries"])
            body = "\n\n".join([r.choice(GREETINGS), *paras, f"{r.choice(SIGNOFFS)}\n{sender}\n{role.capitalize()}"])
            head = f"From: {sender} ({role})\nTo: stock control\nDate: day {d}, {r.randint(7, 17):02d}:"
            out.append((f"day{d:02d}-msg{i:02d}.txt", f"{head}{r.randint(0, 59):02d}\nSubject: {subject}\n\n{body}\n"))
        return out


def generate(seed: int, days: int = 10, n_skus: int = 30, receipts_chars: int = 15_000,
             shipments_chars: int = 15_000, audit_chars: int = 60_000, inbox_chars: int = 0) -> dict:
    """One instance: the tracked SKUs, each day's three reports (and inbox), and the answer key (closing stock,
    lowest)."""
    rng = random.Random(seed)
    used: set = set()
    skus = [_sku(rng, used) for _ in range(n_skus)]
    tracked = sorted(rng.sample(skus, 6))
    others = [s for s in skus if s not in tracked]
    stock = {s: rng.randint(300, 900) for s in skus}
    mail = Inbox(seed, skus) if inbox_chars else None
    refs: dict[str, str] = {}  # event id -> its order (SO-) or delivery (PO-) number
    inbox_days: list[list] = []
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
        for line in lines_r + lines_s:
            m = REF_RE.search(line)
            if m:
                refs[line.split(" |", 1)[0]] = m.group(1)
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
        if mail:
            inbox_days.append(mail.day(d, inbox_chars, tracked, others, stock, events, refs, targeted))
        closing = {s: stock[s] for s in tracked}
        key.append({"day": d, "stock": closing, "lowest": min(tracked, key=lambda s: (closing[s], s))})
    inst = {"seed": seed, "days": days, "tracked": tracked, "reports": out_days, "key": key}
    if mail:
        inst.update({"inbox": inbox_days, "names": {s: mail.name(s) for s in tracked}})
    return inst


# ---- the working folder ------------------------------------------------------------------------------------------
def write_tool(cwd: Path) -> None:
    (cwd / "tools").mkdir(parents=True, exist_ok=True)
    (cwd / "tools" / "report.py").write_text(REPORT_TOOL)
    (cwd / "data").mkdir(exist_ok=True)


def release_day(cwd: Path, inst: dict, day: int) -> None:
    """Replace the reports (and the inbox) in `cwd` with day `day`'s; earlier days' are gone from the folder."""
    write_tool(cwd)
    blob = json.dumps({"day": day, "reports": inst["reports"][day - 1]}).encode()
    (cwd / "data" / "today.bin").write_bytes(base64.b64encode(gzip.compress(blob)))
    if inst.get("inbox"):
        box = cwd / "inbox"
        if box.exists():
            for f in box.iterdir():
                f.unlink()
        box.mkdir(exist_ok=True)
        for name, text in inst["inbox"][day - 1]:
            (box / name).write_text(text)


NOTES_LINE = ("Keep a file NOTES.md in this folder with everything later days will need (each day's closing stock, "
              "the events behind it with their ids, SKUs and quantities, and the corrections applied), and read it "
              "first each day.")


def prompt(inst: dict, day: int, notes_prompt: bool = False) -> str:
    """The day's task, the same in every arm (A+ adds NOTES_LINE)."""
    if inst.get("names"):
        names = ", ".join(f"{s} ({inst['names'][s]})" for s in inst["tracked"])
    else:
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
    if inst.get("inbox"):
        text += (f"The folder `inbox/` holds today's {len(inst['inbox'][day - 1])} messages from staff, suppliers, "
                 "carriers and customers; it is replaced overnight too. Messages name products by description, not by "
                 "SKU. Some change stock in plain words: a write-off, stock found in a recount, or a shipment or "
                 "delivery that turned out short (named by its order or PO number, possibly from an earlier day; its "
                 "quantity becomes the number stated). Others only mention products and change nothing. Read every "
                 "message.\n\n")
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


def _effect_re(template: str) -> re.Pattern:
    out, seen = re.escape(template), set()
    for slot, pat in (("who", r"[A-Z][a-z]+ [A-Z][a-z]+"), ("aisle", r"\d+"), ("n", r"(?P<n>\d+)"),
                      ("k", r"(?P<k>\d+)"), ("ref", r"(?P<ref>[^.:;]+?)"), ("so", r"(?P<so>SO-\d+)"),
                      ("po", r"(?P<po>PO-\d+)")):
        token = re.escape("{" + slot + "}")
        while token in out:
            out = out.replace(token, f"(?P={slot})" if slot in seen and pat.startswith("(?P") else pat, 1)
            seen.add(slot)
    return re.compile(out)


EFFECT_RES = [(kind, _effect_re(t)) for kind, ts in EFFECTS.items() for t in ts]
LINE_REF_RE = re.compile(r"^(EV-\d+) \|.*\| (?:po|order)=((?:PO|SO)-\d+)", re.M)


def read_inbox(messages: list[tuple[str, str]], names: dict) -> list[tuple]:
    """The stock changes in a day's messages: ("item", sku, delta) for tracked products named by description, and
    ("event", ref, new quantity) for short shipments and deliveries. Mentions match nothing."""
    out = []
    for _, text in messages:
        flat = " ".join(text.split())
        for kind, rx in EFFECT_RES:
            for m in rx.finditer(flat):
                if kind in ("writeoff", "found"):
                    hits = [s for s, n in names.items() if _names_match(n, m.group("ref"))]
                    if hits:
                        out.append(("item", hits[0], (-1 if kind == "writeoff" else 1) * int(m.group("n"))))
                else:
                    out.append(("event", m.group("so") if kind == "short_ship" else m.group("po"), int(m.group("k"))))
    return out


def _names_match(name: str, span: str) -> bool:
    """A product named "<material> <type>, <size>" is meant when both its material and its type appear."""
    head = name.split(",")[0]
    for t in TYPES:
        if head.endswith(t):
            return head[: -len(t)].strip() in span and t in span
    return False


def solve(inst: dict) -> list[dict]:
    """An oracle that reads only what the agent sees (reports, and the inbox with the tracked products' names), day
    by day, with perfect memory: proves the task is answerable."""
    stock = {s: int(n) for s, n in OPEN_RE.findall(inst["reports"][0]["opening"])}
    events: dict[str, list] = {}
    by_ref: dict[str, list] = {}
    answers = []
    for d, rep in enumerate(inst["reports"], 1):
        for kind in ("receipts", "shipments"):
            for eid, typ, sku, qty in EVENT_RE.findall(rep[kind]):
                events[eid] = [sku, typ, int(qty)]
                stock[sku] += SIGN[typ] * int(qty)
            for eid, ref in LINE_REF_RE.findall(rep[kind]):
                by_ref.setdefault(ref, []).append(eid)
        tail = rep["audit"].split("CORRECTIONS POSTED TODAY", 1)[1]
        for eid, what, qty in FIX_RE.findall(tail):
            sku, typ, old = events[eid]
            new = 0 if what == "VOID" else int(qty)
            stock[sku] += SIGN[typ] * (new - old)
            events[eid][2] = new
        for what, x, v in read_inbox(inst["inbox"][d - 1], inst["names"]) if inst.get("inbox") else []:
            if what == "item":
                stock[x] += v
            else:
                assert len(by_ref[x]) == 1, x
                eid = by_ref[x][0]
                sku, typ, old = events[eid]
                stock[sku] += SIGN[typ] * (v - old)
                events[eid][2] = v
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
