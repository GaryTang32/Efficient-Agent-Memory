"""Long-horizon aggregation: many small tool calls, exact arithmetic at the end.
Stresses carrying state across a long trajectory (ReSum, IterResearch, masking)."""

from __future__ import annotations

import random
import re

from eam.agent.context import Tool
from eam.bench.tasks.common import TaskInstance, filler_paragraphs
from eam.bench.tasks.oracle import EntityOracle, EntitySpec
from eam.llm.types import ToolSpec

CATEGORIES = ["tools", "garden", "kitchen", "lighting"]
WAREHOUSES = ["north", "south", "east"]
LINE = re.compile(r"(SKU-\d{4}) \| category=(\w+) \| warehouse=(\w+) \| stock=(\d+) \| unit_price=(\d+\.\d{2})")


def parse_facts(text: str) -> dict[str, dict[str, str]]:
    return {m.group(1): {"category": m.group(2), "warehouse": m.group(3), "stock": m.group(4),
                         "unit_price": m.group(5)} for m in LINE.finditer(text)}


def generate(seed: int, n_in_category: int = 16, notes_tokens: int = 350) -> TaskInstance:
    rng = random.Random(seed)
    category = rng.choice(CATEGORIES)
    warehouse, threshold = rng.choice(WAREHOUSES), rng.randint(20, 60)
    items, n = {}, 0
    for cat in CATEGORIES:
        for _ in range(n_in_category if cat == category else rng.randint(4, 8)):
            n += 1
            sku = f"SKU-{n:04d}"
            items[sku] = {"category": cat, "warehouse": rng.choice(WAREHOUSES), "stock": rng.randint(0, 99),
                          "unit_price": round(rng.uniform(2, 250), 2)}
    gold = round(sum(it["stock"] * it["unit_price"] for it in items.values()
                     if it["category"] == category and it["warehouse"] == warehouse and it["stock"] < threshold), 2)
    notes = {sku: " ".join(filler_paragraphs(rng, notes_tokens)) for sku in items}

    def list_skus(args, ctx):
        cat = str(args.get("category", ""))
        skus = [s for s, it in items.items() if it["category"] == cat]
        if not skus:
            raise ValueError(f"unknown category '{cat}'; categories: {CATEGORIES}")
        return f"SKUs in category {cat}: " + ", ".join(skus)

    def get_item(args, ctx):
        sku = str(args.get("sku", ""))
        if sku not in items:
            raise ValueError(f"unknown sku '{sku}'")
        it = items[sku]
        return (f"{sku} | category={it['category']} | warehouse={it['warehouse']} | stock={it['stock']} | "
                f"unit_price={it['unit_price']:.2f}\nNotes: {notes[sku]}")

    tools = [
        Tool(ToolSpec("list_skus", "List the SKU ids in a product category.",
                      {"type": "object", "properties": {"category": {"type": "string", "enum": CATEGORIES}},
                       "required": ["category"]}), list_skus),
        Tool(ToolSpec("get_item", "Get stock level, unit price, warehouse and notes for one SKU.",
                      {"type": "object", "properties": {"sku": {"type": "string"}}, "required": ["sku"]}), get_item),
    ]
    prompt = (f"Compute the total inventory value (stock × unit_price) of all items in the '{category}' category "
              f"that are stored in the {warehouse} warehouse and have stock below {threshold}. Check every item. "
              "Answer with the number rounded to 2 decimals.")

    def check(answer: str) -> bool:
        nums = [float(x.replace(",", "")) for x in re.findall(r"\d[\d,]*\.?\d*", answer)]
        return any(abs(x - gold) < 0.01 for x in nums)

    def answer(facts, entities):
        total = sum(int(f["stock"]) * float(f["unit_price"]) for sku, f in facts.items()
                    if sku in entities and f["warehouse"] == warehouse and int(f["stock"]) < threshold)
        return f"{total:.2f}"

    spec = EntitySpec(
        list_call=("list_skus", {"category": category}),
        parse_list=lambda text: {m: m for m in re.findall(r"SKU-\d{4}", text.split(f"category {category}: ", 1)[-1].split("\n", 1)[0])}
        if f"category {category}: " in text else {},
        read_tool="get_item", read_arg="sku",
        parse_facts=parse_facts, fields=("warehouse", "stock", "unit_price"),
        fact_lines=lambda text: list(dict.fromkeys(m.group(0) for m in LINE.finditer(text))),
        answer=answer,
        subtask=lambda eid, key: f"Look up item {eid} ({key}) and state its full record line.",
        subtask_re=re.compile(r"Look up item (SKU-\d{4}) \((SKU-\d{4})\)"),
    )
    return TaskInstance(
        family="inventory_ops", instance_id=f"inventory-{seed}", prompt=prompt, tools=tools, check=check,
        gold=f"{gold:.2f}", oracle=lambda: EntityOracle(spec), max_steps=45,
    )
