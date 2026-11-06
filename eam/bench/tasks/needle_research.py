"""Research over long reports: read many long documents, keep a few facts each,
aggregate. Stresses tool-output size (offload, compression, folding, masking)."""

from __future__ import annotations

import random
import re

from eam.agent.context import Tool
from eam.bench.tasks.common import TaskInstance, contains_all, filler_paragraphs
from eam.bench.tasks.oracle import EntityOracle, EntitySpec
from eam.llm.types import ToolSpec

PREFIXES = ["Arbor", "Cobalt", "Delta", "Ember", "Falcon", "Granite", "Harbor", "Ionic", "Juniper", "Kestrel",
            "Lumen", "Meridian", "Nimbus", "Onyx", "Pioneer", "Quartz", "Redwood", "Summit", "Tidal", "Vertex"]
SUFFIXES = ["Systems", "Labs", "Dynamics", "Works", "Industries", "Analytics"]
FIRST = ["Alice", "Bruno", "Chen", "Dalia", "Emeka", "Farah", "Goran", "Hana", "Ivan", "Jia", "Kofi", "Lena",
         "Mateo", "Noor", "Oskar", "Priya", "Rui", "Sana", "Tomas", "Yuki"]
LAST = ["Andersen", "Borges", "Castillo", "Dubois", "Eriksen", "Fischer", "Gupta", "Haddad", "Ito", "Jensen",
        "Kowalski", "Lindqvist", "Moreau", "Nakamura", "Okafor", "Petrov", "Quinn", "Rossi", "Silva", "Tanaka"]
SECTORS = ["logistics", "healthcare", "energy"]

NAME = r"([A-Z][a-z]+ [A-Z][a-z]+)"
FACT_RES = {
    "sector": re.compile(NAME + r" operates in the (\w+) sector"),
    "founded": re.compile(NAME + r" was founded in (\d{4})"),
    "revenue": re.compile(r"In 2023, " + NAME + r" reported revenue of \$(\d+) million"),
    "ceo": re.compile(r"The chief executive officer of " + NAME + r" is " + NAME),
}
FACT_LINE = re.compile(r"[^.\n]*(?:operates in the \w+ sector|was founded in \d{4}|reported revenue of \$\d+ million"
                       r"|The chief executive officer of [A-Z][a-z]+ [A-Z][a-z]+ is [A-Z][a-z]+ [A-Z][a-z]+)[^.\n]*\.")


def parse_facts(text: str) -> dict[str, dict[str, str]]:
    out: dict[str, dict[str, str]] = {}
    for field_, rx in FACT_RES.items():
        for m in rx.finditer(text):
            out.setdefault(m.group(1), {})[field_] = m.group(2)
    return out


def generate(seed: int, n_companies: int = 10, doc_tokens: int = 1500) -> TaskInstance:
    rng = random.Random(seed)
    names = rng.sample([f"{p} {s}" for p in PREFIXES for s in SUFFIXES], n_companies)
    while True:
        companies = []
        for i, name in enumerate(names, 1):
            companies.append({
                "id": f"C{i:02d}", "name": name, "sector": rng.choice(SECTORS),
                "founded": rng.randint(1985, 2020), "revenue": rng.randint(40, 990),
                "ceo": f"{rng.choice(FIRST)} {rng.choice(LAST)}",
            })
        sector, year = rng.choice(SECTORS), rng.randint(2002, 2014)
        cands = [c for c in companies if c["sector"] == sector and c["founded"] < year]
        revs = [c["revenue"] for c in cands]
        if len(cands) >= 2 and len(set(revs)) == len(revs):
            break
    best = max(cands, key=lambda c: c["revenue"])

    reports = {}
    for c in companies:
        paras = filler_paragraphs(rng, doc_tokens)
        facts = [f"{c['name']} operates in the {c['sector']} sector.",
                 f"{c['name']} was founded in {c['founded']}.",
                 f"In 2023, {c['name']} reported revenue of ${c['revenue']} million.",
                 f"The chief executive officer of {c['name']} is {c['ceo']}."]
        slots = sorted(rng.sample(range(len(paras)), min(len(facts), len(paras))))
        for slot, fact in zip(slots, facts):
            paras[slot] = f"{paras[slot]} {fact}"
        reports[c["id"]] = f"Annual report — {c['name']}\n\n" + "\n\n".join(paras)

    def list_companies(args, ctx):
        return "Companies in the database:\n" + "\n".join(f"{c['id']}: {c['name']}" for c in companies)

    def read_report(args, ctx):
        cid = str(args.get("company_id", ""))
        if cid not in reports:
            raise ValueError(f"unknown company_id '{cid}'")
        return reports[cid]

    tools = [
        Tool(ToolSpec("list_companies", "List all companies (id and name) in the database.",
                      {"type": "object", "properties": {}}), list_companies),
        Tool(ToolSpec("read_company_report", "Return the full annual report of one company. Reports are long.",
                      {"type": "object", "properties": {"company_id": {"type": "string"}}, "required": ["company_id"]}),
             read_report),
    ]
    prompt = (f"Among the companies in the {sector} sector that were founded before {year}, which one reported the "
              "highest revenue in 2023? Give the company name and the name of its CEO. The sector, founding year, "
              "revenue and CEO are only stated inside each company's annual report.")

    def answer(facts, entities):
        pool = [(int(f["revenue"]), k, f.get("ceo", "?")) for k, f in facts.items()
                if f.get("sector") == sector and "founded" in f and int(f["founded"]) < year and "revenue" in f]
        if not pool:
            return "unknown"
        _, name, ceo = max(pool)
        return f"{name}, CEO {ceo}"

    spec = EntitySpec(
        list_call=("list_companies", {}),
        parse_list=lambda text: {m.group(1): m.group(2) for m in re.finditer(r"(C\d{2}): " + NAME, text)},
        read_tool="read_company_report", read_arg="company_id",
        parse_facts=parse_facts, fields=("sector", "founded", "revenue", "ceo"),
        fact_lines=lambda text: list(dict.fromkeys(m.group(0).strip() for m in FACT_LINE.finditer(text))),
        answer=answer,
        subtask=lambda eid, key: (f"Read the report for company {eid} ({key}) and state its sector, founding year, "
                                  "2023 revenue and CEO."),
        subtask_re=re.compile(r"Read the report for company (C\d{2}) \(" + NAME + r"\)"),
    )
    return TaskInstance(
        family="needle_research", instance_id=f"needle-{seed}", prompt=prompt, tools=tools,
        check=contains_all(best["name"], best["ceo"]), gold=f"{best['name']}, CEO {best['ceo']}",
        oracle=lambda: EntityOracle(spec), max_steps=40,
    )
