"""Deep research over a corpus far larger than the context window (BrowseComp-Plus style).

BrowseComp-Plus (fixed corpus + search tool, multi-hop questions) is the benchmark on which ReSum, Context-Folding
and IterResearch report their long-horizon results; this is a small, synthetic, automatically scored version.

World: invented people, companies, cities and products (no model has priors about them), each with one long
profile document (~2K tokens). Facts are single sentences buried at random positions in filler text, so a search
snippet never reveals them: every hop needs a search and an open. Names are built from a small pool of roots,
so most entities have namesakes (same surname / root) with different facts — opening the wrong profile gives a
wrong chain, as in BrowseComp's confusable entities.

Task (one long session): 8 questions, revealed one at a time via `submit_answer`, each a chain of 3–4 hops over functional relations (designer, maker,
founder, headquarters, birthplace, twin city) ending in an attribute (a year or a river), plus Q9 = the sum of the
year answers, which needs every earlier answer to survive until the end. ~8 × (search + open) × 3.5 hops ≈ 60+
steps; the documents read add up to ≈2× the window. Scoring: `score` = fraction of the 9 answers right.
"""

from __future__ import annotations

import math
import random
import re
from collections import Counter

from eam.agent.context import Tool
from eam.bench.tasks.common import TaskInstance, filler_paragraphs
from eam.llm.mock import assistant, context_text, final, tool_exchanges, tool_use
from eam.llm.types import ToolSpec

GIVEN = ["Ilka", "Oren", "Mavi", "Tasso", "Edda", "Rune", "Sefa", "Calix", "Nadia", "Bruno", "Yara", "Ivo", "Lene",
         "Dario", "Sanne", "Teo", "Mira", "Aske", "Zora", "Pelle"]
FAMILY = ["Varmo", "Kestly", "Orvane", "Tulsk", "Brandel", "Quist", "Halvar", "Ferro", "Lindqvar", "Moskel",
          "Penhal", "Rask"]
ROOTS = ["Tess", "Varn", "Oxle", "Brem", "Calder", "Duna", "Ferrow", "Gale", "Hollin", "Ister", "Jarro", "Kell",
         "Lomb", "Merr", "Norr"]
CITY_SUFFIX = ["by", "holm", "ford", "vale", "stad", "mouth"]
COMPANY_SUFFIX = ["Instruments", "Textiles", "Foundry", "Labs", "Holdings", "Optics", "Works"]
PRODUCT_NOUN = ["Loom", "Compass", "Kettle", "Lantern", "Sextant", "Press", "Dial", "Bellows", "Prism", "Winch"]
RIVERS = ["Ostra", "Velka", "Marn", "Sille", "Torva", "Ebbin", "Quell", "Dravo", "Lysa", "Narre", "Pellin", "Ruva",
          "Skarn", "Umber", "Wend"]

# (start type, relation path, answer attribute, question template)
TEMPLATES = [
    ("product", ["designer", "birth_city", "twin"], "museum_year",
     "In what year did the museum open in the twin city of the birthplace of the designer of the {x}?"),
    ("company", ["founder", "birth_city", "twin"], "river",
     "Which river runs through the twin city of the birthplace of the founder of {x}?"),
    ("product", ["maker", "hq", "twin"], "museum_year",
     "In what year did the museum open in the twin city of the city where the maker of the {x} is headquartered "
     "today?"),
    ("product", ["maker", "founder"], "birth_year",
     "In what year was the founder of the company that manufactures the {x} born?"),
    ("company", ["hq", "twin"], "river",
     "Which river runs through the twin city of the city where {x} is headquartered today?"),
    ("product", ["designer", "birth_city"], "river",
     "Which river runs through the birthplace of the designer of the {x}?"),
    ("company", ["founder", "birth_city"], "museum_year",
     "In what year did the museum open in the birthplace of the founder of {x}?"),
    ("product", ["maker", "hq"], "museum_year",
     "In what year did the museum open in the city where the maker of the {x} is headquartered today?"),
]


def _world(rng: random.Random, n_people=40, n_companies=28, n_cities=30, n_products=32):
    people = []
    while len(people) < n_people:
        n = f"{rng.choice(GIVEN)} {rng.choice(FAMILY)}"
        if n not in people:
            people.append(n)
    cities = []
    while len(cities) < n_cities:
        n = f"{rng.choice(ROOTS)}{rng.choice(CITY_SUFFIX)}"
        if n not in cities:
            cities.append(n)
    companies = []
    while len(companies) < n_companies:
        n = f"{rng.choice(ROOTS + FAMILY)} {rng.choice(COMPANY_SUFFIX)}"
        if n not in companies:
            companies.append(n)
    products = []
    while len(products) < n_products:
        n = f"{rng.choice(ROOTS)} {rng.choice(PRODUCT_NOUN)}"
        if n not in products:
            products.append(n)
    order = cities[:]
    rng.shuffle(order)
    twin = {}
    for a, b in zip(order[0::2], order[1::2]):
        twin[a], twin[b] = b, a
    rel = {
        "person": {p: {"birth_city": rng.choice(cities), "birth_year": rng.randint(1890, 1985)} for p in people},
        "city": {c: {"twin": twin[c], "museum_year": rng.randint(1800, 2015), "river": rng.choice(RIVERS)}
                 for c in cities},
        "company": {},
        "product": {},
    }
    for c in companies:
        old, new = rng.sample(cities, 2)
        rel["company"][c] = {"founder": rng.choice(people), "founded_year": rng.randint(1900, 2010), "hq": new,
                             "former_hq": old}
    for d in products:
        rel["product"][d] = {"designer": rng.choice(people), "maker": rng.choice(companies),
                             "launch_year": rng.randint(1950, 2020)}
    return {"person": people, "city": cities, "company": companies, "product": products}, rel


def _facts(kind: str, name: str, r: dict) -> list[str]:
    if kind == "person":
        return [f"{name} was born in {r['birth_city']} in {r['birth_year']}."]
    if kind == "city":
        return [f"{name} is twinned with {r['twin']}.", f"The museum of {name} opened in {r['museum_year']}.",
                f"The river that runs through {name} is the {r['river']}."]
    if kind == "company":
        return [f"{name} was founded by {r['founder']} in {r['founded_year']}.",
                f"{name} was headquartered in {r['former_hq']} until it moved its headquarters to {r['hq']}."]
    return [f"The {name} was designed by {r['designer']}.", f"The {name} is manufactured by {r['maker']}.",
            f"The {name} was first sold in {r['launch_year']}."]


TITLE = {"person": "{n} — biography", "city": "{n} — city guide", "company": "{n} — company profile",
         "product": "The {n} — product history"}


def _tokenize(text: str) -> list[str]:
    return re.findall(r"[a-z]+", text.lower())


class BM25:
    def __init__(self, docs: dict[str, str], k1: float = 1.2, b: float = 0.75):
        self.ids = list(docs)
        self.tf = [Counter(_tokenize(docs[i])) for i in self.ids]
        self.len = [sum(t.values()) for t in self.tf]
        self.avg = sum(self.len) / len(self.len)
        df = Counter(w for t in self.tf for w in t)
        n = len(self.ids)
        self.idf = {w: math.log(1 + (n - c + 0.5) / (c + 0.5)) for w, c in df.items()}
        self.k1, self.b = k1, b

    def search(self, query: str, k: int = 6) -> list[str]:
        q = [w for w in _tokenize(query) if w in self.idf]
        scores = []
        for j, tf in enumerate(self.tf):
            s = 0.0
            for w in q:
                f = tf.get(w, 0)
                if f:
                    s += self.idf[w] * f * (self.k1 + 1) / (f + self.k1 * (1 - self.b + self.b * self.len[j] / self.avg))
            if s > 0:
                scores.append((s, j))
        scores.sort(key=lambda x: (-x[0], self.ids[x[1]]))
        return [self.ids[j] for _, j in scores[:k]]


def generate(seed: int, n_questions: int = 8, doc_tokens: int = 2000, context_limit: int = 40_000,
             step_observation_budget: int | None = 6000, disclose_limit: bool = False,
             incremental: bool = True) -> TaskInstance:
    """``incremental=True`` (default) reveals one question at a time through `submit_answer`, so the questions
    cannot be researched in parallel and the session is long (≥ ~65 sequential steps); the final answer must
    list every answer again, so all of them have to survive until the end."""
    rng = random.Random(seed)
    names, rel = _world(rng)
    all_names = [(k, n) for k in names for n in names[k]]

    docs: dict[str, str] = {}
    titles: dict[str, str] = {}
    doc_of: dict[str, str] = {}
    for i, (kind, name) in enumerate(all_names):
        did = f"D{i + 1:03d}"
        doc_of[name] = did
        facts = _facts(kind, name, rel[kind][name])
        others = rng.sample([n for _, n in all_names if n != name], 3)  # passing mentions: noisy search hits
        facts += [f"A trade report once mentioned {name} alongside {o}." for o in others]
        paras = filler_paragraphs(rng, doc_tokens)
        for f in facts:
            p = rng.randrange(1, len(paras))  # never in the first paragraph, which the snippet shows
            paras[p] = paras[p] + " " + f
        titles[did] = TITLE[kind].format(n=name)
        docs[did] = titles[did] + "\n\n" + "\n\n".join(paras)
    index = BM25(docs)

    def follow(kind: str, name: str, path: list[str]) -> tuple[str, str, list[str]]:
        chain = [name]
        for step in path:
            name = rel[kind][name][step]
            kind = {"designer": "person", "founder": "person", "maker": "company", "hq": "city",
                    "birth_city": "city", "twin": "city"}[step]
            chain.append(name)
        return kind, name, chain

    questions, answers, chains = [], [], []
    templates = TEMPLATES[:n_questions] if n_questions <= len(TEMPLATES) else \
        [TEMPLATES[i % len(TEMPLATES)] for i in range(n_questions)]
    used: set[str] = set()
    for start, path, attr, text in templates:
        x = rng.choice([n for n in names[start] if n not in used])
        used.add(x)
        kind, end, chain = follow(start, x, path)
        questions.append(text.format(x=x))
        answers.append(rel[kind][end][attr])
        chains.append(chain)
    year_qs = [i for i, a in enumerate(answers) if isinstance(a, int)]
    total = sum(answers[i] for i in year_qs)
    q_labels = ", ".join(f"Q{i + 1}" for i in year_qs)
    all_qs = [f"Q{i + 1}. {q}" for i, q in enumerate(questions)] + [
        f"Q{len(questions) + 1}. What is the sum of your answers to {q_labels}?"]
    intro = ("You are a research assistant with a search engine over a private document collection "
             f"({len(docs)} long documents about people, companies, cities and products). None of these entities "
             "are known to you: rely only on the documents. Many names are similar, so make sure each document is "
             "about exactly the entity you need.")
    if incremental:
        prompt = (f"{intro}\n\nThere are {len(all_qs)} questions, revealed one at a time. When you have the "
                  "answer to the current question, call submit_answer with it; the tool replies with the next "
                  "question. Submitted answers are not graded until the end. After the last question, give your "
                  f"final answer listing every answer again, one line per question as 'Q<n>: <answer>' for Q1 to "
                  f"Q{len(all_qs)}.\n\n{all_qs[0]}")
    else:
        prompt = (f"{intro} Answer every question:\n\n" + "\n".join(all_qs)
                  + "\n\nReport one line per question as 'Q<n>: <answer>'.")
    progress: dict[int, int] = {}  # questions submitted, per run (keyed by the run's cost meter, which the
    #                                main agent and its sub-agents share)

    def submit_answer(args, ctx):
        if not str(args.get("answer", "")).strip():
            raise ValueError("submit_answer needs a non-empty 'answer'; the current question is unchanged")
        k = progress.get(id(ctx.meter), 0) + 1
        progress[id(ctx.meter)] = k
        if k < len(all_qs):
            return f"Answer to Q{k} recorded. Next question:\n{all_qs[k]}"
        return ("All questions have been revealed. Give your final answer now: one line per question, "
                f"'Q<n>: <answer>' for Q1 to Q{len(all_qs)}.")

    def search(args, ctx):
        q = str(args.get("query", ""))
        hits = index.search(q)
        if not hits:
            return "No results."
        out = []
        for did in hits:
            first = docs[did].split("\n\n")[1]
            out.append(f"[{did}] {titles[did]}\n    {' '.join(first.split()[:25])} ...")
        return "\n".join(out)

    def open_doc(args, ctx):
        did = str(args.get("doc_id", "")).strip().strip("[]")
        if did not in docs:
            raise ValueError(f"no document '{did}'")
        return docs[did]

    def calc(args, ctx):
        from eam.bench.tasks.ledger_audit import safe_eval
        return str(round(safe_eval(str(args.get("expression", ""))), 6))

    tools = [
        Tool(ToolSpec("search", "Search the document collection. Returns up to 6 hits: id, title and the opening "
                      "words (facts are inside the documents, not in the snippets).",
                      {"type": "object", "properties": {"query": {"type": "string"}}, "required": ["query"]}), search),
        Tool(ToolSpec("open_doc", "Open one document by id (e.g. D042) and return its full text (~2K tokens).",
                      {"type": "object", "properties": {"doc_id": {"type": "string"}}, "required": ["doc_id"]}),
             open_doc),
        Tool(ToolSpec("calc", "Evaluate an arithmetic expression (+ - * / and parentheses).",
                      {"type": "object", "properties": {"expression": {"type": "string"}}, "required": ["expression"]}),
             calc),
    ]
    if incremental:
        tools.append(Tool(ToolSpec("submit_answer", "Submit your answer to the current question; returns the next "
                                   "question.", {"type": "object", "properties": {"answer": {"type": "string"}},
                                                 "required": ["answer"]}), submit_answer))
    gold_answers = [str(a) for a in answers] + [str(total)]

    def line_for(answer: str, k: int) -> str:
        m = re.search(rf"(?im)^\W*Q{k}\W*[:.)-]\s*(.+)$", answer)
        return m.group(1) if m else ""

    def score(answer: str) -> float:
        hits = 0
        for k, g in enumerate(gold_answers, start=1):
            line = line_for(answer, k)
            if g.isdigit():
                hits += g in re.findall(r"\d+", line.replace(",", ""))
            else:
                hits += bool(re.search(rf"\b{re.escape(g)}\b", line, re.I))
        return hits / len(gold_answers)

    gold = " | ".join(f"Q{i + 1}: {g} (chain: {' > '.join(chains[i])})" if i < len(chains) else f"Q{i + 1}: {g}"
                      for i, g in enumerate(gold_answers))

    def oracle():
        """Mock researcher: for each question, searches the next entity's exact name, opens its profile and
        reads the needed fact from the visible context. Answers from whatever survived in the context."""
        kind_after = {"designer": "person", "founder": "person", "maker": "company", "hq": "city",
                      "birth_city": "city", "twin": "city"}

        def fact(text: str, name: str, key: str):
            n = re.escape(name)
            pat, grp, cast = {
                "designer": (rf"The {n} was designed by (.+?)\.", 1, str),
                "maker": (rf"The {n} is manufactured by (.+?)\.", 1, str),
                "founder": (rf"{n} was founded by (.+?) in \d{{4}}\.", 1, str),
                "hq": (rf"{n} was headquartered in .+? until it moved its headquarters to (.+?)\.", 1, str),
                "birth_city": (rf"{n} was born in (.+?) in \d{{4}}\.", 1, str),
                "birth_year": (rf"{n} was born in .+? in (\d{{4}})\.", 1, int),
                "twin": (rf"{n} is twinned with (.+?)\.", 1, str),
                "museum_year": (rf"The museum of {n} opened in (\d{{4}})\.", 1, int),
                "river": (rf"The river that runs through {n} is the (.+?)\.", 1, str),
            }[key]
            m = re.search(pat, text)
            return cast(m.group(grp)) if m else None

        def policy(req):
            text = context_text(req)
            got: list[str] = []
            submitted = [inp.get("answer", "") for n, inp, _ in tool_exchanges(req.messages) if n == "submit_answer"]
            for q, ((start, path, attr, _), chain) in enumerate(zip(templates, chains)):
                if incremental and q < len(submitted):
                    got.append(submitted[q])
                    continue
                kind, name = start, chain[0]
                for step in path + [attr]:
                    val = fact(text, name, step)
                    if val is None:
                        did = doc_of[name]
                        if f"[{did}]" not in text:
                            return assistant(tool_use("search", {"query": name}))
                        return assistant(tool_use("open_doc", {"doc_id": did}))
                    if step == attr:
                        if incremental:
                            return assistant(tool_use("submit_answer", {"answer": str(val)}))
                        got.append(str(val))
                    else:
                        kind, name = kind_after[step], val
            years = [int(g) for i, g in enumerate(got) if i in year_qs and g.isdigit()]
            if incremental and len(submitted) == len(questions):
                return assistant(tool_use("submit_answer", {"answer": str(sum(years))}))
            return final("FINAL ANSWER:\n" + "\n".join(f"Q{i + 1}: {g}" for i, g in enumerate(got))
                         + f"\nQ{len(got) + 1}: {sum(years)}")

        return policy

    return TaskInstance(
        family="research_corpus", instance_id=f"research-{seed}", prompt=prompt, tools=tools,
        check=lambda a: score(a) == 1.0, score=score, gold=gold, oracle=oracle, max_steps=160,
        context_limit=context_limit, step_observation_budget=step_observation_budget, disclose_limit=disclose_limit,
    )
