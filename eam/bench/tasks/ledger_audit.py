"""Multi-round audit whose data does not fit in the context window.

Round 1 (session 1): total the payments to 5 vendors across 24 long monthly ledgers (~4K tokens each).
Round 2 (new session): 10 refund files arrive; using round-1 totals, report every vendor's net spend and the
                        vendor with the highest net.
Round 3 (new session): apply the discount schedule to the round-2 nets; report each payable and the sum.

Every round starts from an empty conversation, so earlier results survive only through a memory mechanism
(otherwise the agent must re-read the data). Run with a context limit (TaskInstance.context_limit, default
48K tokens): a request above it ends the run as a context overflow, as a real API would, so keeping the context
bounded *and* keeping the facts are both required. Scoring is exact per number; `score` is the fraction of the
16 required numbers/names that are right.
"""

from __future__ import annotations

import ast
import operator
import random
import re

from eam.agent.context import Tool
from eam.bench.tasks.common import TaskInstance, filler_paragraphs
from eam.llm.mock import assistant, context_text, final, tool_exchanges, tool_use
from eam.llm.types import ToolSpec

VENDORS = ["Acme Supply", "Birch Logistics", "Cobalt Foods", "Delta Print", "Ember Energy", "Falcon Freight",
           "Granite Tools", "Harbor Health", "Ionic Media", "Juniper Cloud", "Kestrel Farms", "Lumen Labs",
           "Meridian Metals", "Nimbus Travel", "Onyx Security", "Pioneer Paper", "Quartz Optics", "Redwood Rentals",
           "Summit Staffing", "Tidal Water"]
MEMOS = ["quarterly order", "service fee", "replacement parts", "consulting", "shipping", "maintenance",
         "license renewal", "bulk purchase", "rush delivery", "subscription"]
TXN_RE = re.compile(r"TXN-\d+ \| [\d-]+ \| vendor=([A-Za-z ]+?) \| amount=(\d+)")
REF_RE = re.compile(r"REF-\d+ \| vendor=([A-Za-z ]+?) \| refund=(\d+)")
DISC_RE = re.compile(r"([A-Za-z ]+?): (\d+)% discount")

_OPS = {ast.Add: operator.add, ast.Sub: operator.sub, ast.Mult: operator.mul, ast.Div: operator.truediv,
        ast.USub: operator.neg, ast.UAdd: operator.pos}


def safe_eval(expr: str) -> float:
    def ev(node):
        if isinstance(node, ast.Expression):
            return ev(node.body)
        if isinstance(node, ast.Constant) and isinstance(node.value, (int, float)):
            return node.value
        if isinstance(node, ast.BinOp) and type(node.op) in _OPS:
            return _OPS[type(node.op)](ev(node.left), ev(node.right))
        if isinstance(node, ast.UnaryOp) and type(node.op) in _OPS:
            return _OPS[type(node.op)](ev(node.operand))
        raise ValueError("only + - * / and numbers are allowed")
    return ev(ast.parse(expr, mode="eval"))


def _numbers(answer: str) -> list[float]:
    return [float(x.replace(",", "")) for x in re.findall(r"\d[\d,]*\.?\d*", answer)]


def _has(answer: str, value: float) -> bool:
    return any(abs(x - value) < 0.011 for x in _numbers(answer))


def _vendor_value(answer: str, vendor: str, value: float) -> bool:
    """True if `value` appears on a line (or clause) that names `vendor`."""
    for line in re.split(r"[\n;]|(?<=\d)\s*,\s*(?=[A-Z])", answer):
        if vendor.lower() in line.lower() and _has(line, value):
            return True
    return False


def generate(seed: int, n_ledgers: int = 16, n_refund_files: int = 8, ledger_tokens: int = 4000,
             refund_tokens: int = 3500, context_limit: int = 48_000, relevant_per_file: tuple[int, int] = (1, 2)
             ) -> TaskInstance:
    rng = random.Random(seed)
    targets = rng.sample(VENDORS, 5)
    others = [v for v in VENDORS if v not in targets]
    files: dict[str, str] = {}
    paid = {v: 0 for v in targets}
    refunds = {v: 0 for v in targets}
    txn = 10000
    for m in range(1, n_ledgers + 1):
        fid = f"L-{m:02d}"
        lines = []
        hits = set(rng.sample(range(60), rng.randint(*relevant_per_file)))  # only a few lines matter per file
        for j in range(60):
            txn += rng.randint(1, 9)
            v = rng.choice(targets) if j in hits else rng.choice(others)
            amt = rng.randint(50, 2500)
            if v in paid:
                paid[v] += amt
            lines.append(f"TXN-{txn} | 2025-{(m - 1) % 12 + 1:02d}-{rng.randint(1, 28):02d} | vendor={v} | amount={amt} "
                         f"| memo={rng.choice(MEMOS)}")
        filler = filler_paragraphs(rng, max(0, ledger_tokens - 60 * 30))
        files[fid] = (f"Monthly ledger {fid}\n\n" + "\n\n".join(filler[: len(filler) // 2]) + "\n\nTransactions:\n"
                      + "\n".join(lines) + "\n\n" + "\n\n".join(filler[len(filler) // 2:]))
    for r in range(1, n_refund_files + 1):
        fid = f"R-{r:02d}"
        lines = []
        hits = set(rng.sample(range(40), rng.randint(*relevant_per_file)))
        for j in range(40):
            v = rng.choice(targets) if j in hits else rng.choice(others)
            amt = rng.randint(10, 400)
            if v in refunds:
                refunds[v] += amt
            lines.append(f"REF-{rng.randint(100000, 999999)} | vendor={v} | refund={amt}")
        filler = filler_paragraphs(rng, max(0, refund_tokens - 40 * 20))
        files[fid] = f"Refund notices {fid}\n\n" + "\n\n".join(filler) + "\n\nRefunds:\n" + "\n".join(lines)
    discount = {v: rng.choice([3, 5, 8, 10, 12, 15]) for v in targets}
    files["DISCOUNTS"] = "Discount schedule 2025\n" + "\n".join(f"{v}: {d}% discount" for v, d in discount.items())

    net = {v: paid[v] - refunds[v] for v in targets}
    best = max(targets, key=lambda v: net[v])
    payable = {v: round(net[v] * (1 - discount[v] / 100), 2) for v in targets}
    total_payable = round(sum(payable.values()), 2)
    ledger_ids = [f"L-{m:02d}" for m in range(1, n_ledgers + 1)]
    refund_ids = [f"R-{r:02d}" for r in range(1, n_refund_files + 1)]
    names = ", ".join(targets)

    def list_files(args, ctx):
        return ("Ledgers: " + ", ".join(ledger_ids) + "\nRefund notices: " + ", ".join(refund_ids)
                + "\nOther: DISCOUNTS")

    def open_file(args, ctx):
        fid = str(args.get("file_id", "")).strip()
        if fid not in files:
            raise ValueError(f"no file '{fid}'")
        return files[fid]

    def calc(args, ctx):
        return str(round(safe_eval(str(args.get("expression", ""))), 6))

    tools = [
        Tool(ToolSpec("list_files", "List the files in the audit archive.", {"type": "object", "properties": {}}),
             list_files),
        Tool(ToolSpec("open_file", "Open one file by id and return its full text (ledgers are ~4K tokens each).",
                      {"type": "object", "properties": {"file_id": {"type": "string"}}, "required": ["file_id"]}),
             open_file),
        Tool(ToolSpec("calc", "Evaluate an arithmetic expression (+ - * / and parentheses).",
                      {"type": "object", "properties": {"expression": {"type": "string"}}, "required": ["expression"]}),
             calc),
    ]
    intro = (f"You are running a three-round vendor audit. Each round is a separate session: the conversation of "
             f"earlier rounds is not available to you. The five vendors under audit are: {names}.")
    rounds = [
        f"{intro}\n\nROUND 1 of 3: Compute the total amount paid to each of the five vendors across all "
        f"{n_ledgers} monthly ledgers ({ledger_ids[0]} to {ledger_ids[-1]}). Report one line per vendor as "
        "'<vendor> = <total>'.",
        f"{intro}\n\nROUND 2 of 3: Refund notices have arrived in files {refund_ids[0]} to {refund_ids[-1]}. Each "
        "vendor's net spend = its round-1 total paid minus its total refunds. Report one line per vendor as "
        "'<vendor> = <net spend>', then name the vendor with the highest net spend.",
        f"{intro}\n\nROUND 3 of 3: Apply the discount schedule in file DISCOUNTS to the round-2 net spends: "
        "payable = net × (1 − discount), rounded to 2 decimals. Report one line per vendor as "
        "'<vendor> = <payable>', then the sum of all five payables.",
    ]

    def score_round(k: int, answer: str) -> float:
        if k == 0:
            hits = [_vendor_value(answer, v, paid[v]) for v in targets]
        elif k == 1:
            hits = [_vendor_value(answer, v, net[v]) for v in targets] + [best.lower() in answer.lower()]
        else:
            hits = [_vendor_value(answer, v, payable[v]) for v in targets] + [_has(answer, total_payable)]
        return sum(hits) / len(hits)

    gold = (" | ".join(f"{v}: paid {paid[v]}, net {net[v]}, payable {payable[v]}" for v in targets)
            + f" | best {best} | total payable {total_payable}")

    def oracle():
        """Mock agent: reads files one at a time, keeps running facts in notes if a workspace is offered,
        and answers from whatever is visible (notes, memory preamble or tool results)."""
        st = {"round": None, "queue": [], "noted": False}

        def visible_sums(text, rx):
            out: dict[str, int] = {v: 0 for v in targets}
            for v, a in rx.findall(text):
                if v in out:
                    out[v] += int(a)
            return out

        def policy(req):
            text = context_text(req)
            first = req.messages[0]["content"][0].get("text", "")
            k = 0 if "ROUND 1 of 3" in first else 1 if "ROUND 2 of 3" in first else 2
            tools_ = {t.name for t in req.tools}
            if st["round"] != k:
                st.update(round=k, queue=[], noted=False)
                if "read_notes" in tools_:
                    return assistant(tool_use("read_notes", {}))
                need = ledger_ids if k == 0 else refund_ids if k == 1 else ["DISCOUNTS"]
                if k >= 1 and "round1" not in text:
                    need = ledger_ids + need  # no memory of round 1: recompute
                if k == 2 and "round2" not in text:
                    need = ledger_ids + refund_ids + need
                st["queue"] = list(need)
            if not st["queue"] and not st["noted"] and "read_notes" in tools_ and not any(
                    n == "open_file" for n, _, _ in tool_exchanges(req.messages)):
                need = ledger_ids if k == 0 else refund_ids if k == 1 else ["DISCOUNTS"]
                if k >= 1 and "round1" not in text:
                    need = ledger_ids + need
                st["queue"] = list(need)
            if st["queue"]:
                fid = st["queue"].pop(0)
                return assistant(tool_use("open_file", {"file_id": fid}))
            p1 = visible_sums(text, TXN_RE)
            r1 = re.findall(r"round1 (.+?) = (\d+)", text)
            totals = {v: int(a) for v, a in r1} if r1 else p1
            if k == 0:
                body = "\n".join(f"{v} = {totals.get(v, 0)}" for v in targets)
                if "write_note" in tools_ and not st["noted"]:
                    st["noted"] = True
                    return assistant(tool_use("write_note", {"name": "round1", "content": "\n".join(
                        f"round1 {v} = {totals.get(v, 0)}" for v in targets)}))
                return final("FINAL ANSWER:\n" + body)
            refs = visible_sums(text, REF_RE)
            r2 = re.findall(r"round2 (.+?) = (-?\d+)", text)
            nets = {v: int(a) for v, a in r2} if r2 else {v: totals.get(v, 0) - refs[v] for v in targets}
            if k == 1:
                if "write_note" in tools_ and not st["noted"]:
                    st["noted"] = True
                    return assistant(tool_use("write_note", {"name": "round2", "content": "\n".join(
                        f"round2 {v} = {nets[v]}" for v in targets)}))
                top = max(targets, key=lambda v: nets[v])
                return final("FINAL ANSWER:\n" + "\n".join(f"{v} = {nets[v]}" for v in targets)
                             + f"\nHighest net spend: {top}")
            disc = {v: int(d) for v, d in DISC_RE.findall(text)}
            pay = {v: round(nets[v] * (1 - disc.get(v, 0) / 100), 2) for v in targets}
            return final("FINAL ANSWER:\n" + "\n".join(f"{v} = {pay[v]:.2f}" for v in targets)
                         + f"\nSum = {round(sum(pay.values()), 2):.2f}")

        return policy

    return TaskInstance(
        family="ledger_audit", instance_id=f"ledger-{seed}", prompt=rounds[-1], tools=tools,
        check=lambda a: False, gold=gold, oracle=oracle, max_steps=60,
        rounds=rounds, round_score=score_round, context_limit=context_limit,
    )
