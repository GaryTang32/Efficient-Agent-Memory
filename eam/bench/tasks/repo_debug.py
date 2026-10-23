"""Repository debugging with real test execution (SWE-style; AgentDiet's and Trae Agent's setting is SWE-bench).

A generated but real Python library (`ledgerkit`: ~30 modules, ≈50K tokens with its tests) with planted bugs.
The agent reads code, greps, edits files and runs the real test suite (pytest in an isolated temporary copy).
Bug behaviour is only covered by end-to-end scenarios (`tests/test_pipeline.py::test_scenario_NN`, docstrings in
business terms), so a failing test does not name the faulty module: the agent has to trace the flow through the
pipeline into the library. Three sessions, each a fresh conversation with its own issue report and two bugs:
knowledge of the codebase from earlier sessions (the pipeline's structure, where things live) saves work later.

Scoring per session: the fraction of that session's scenarios that pass when the *pristine* test suite is run
against the agent's code at the end of the session (editing tests does not help), halved if a test that passed
before the session now fails (a regression). `success` = every session 1.0.
"""

from __future__ import annotations

import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

from eam.agent.context import Tool
from eam.bench.tasks.common import TaskInstance
from eam.llm.mock import assistant, context_text, final, tool_use
from eam.llm.types import ToolSpec

# ---- the library ------------------------------------------------------------------------------------------
# Each bug: module, correct snippet, buggy snippet, the test that exposes it, and the issue text a user would file.
BUGS = {
    "rounding": ("ledgerkit/money.py",
                 "return (value * 100 + Decimal('0.5')).to_integral_value(rounding=ROUND_FLOOR) / 100",
                 "return (value * 100).to_integral_value(rounding=ROUND_FLOOR) / 100",
                 "test_pipeline.py::test_scenario_01",
                 "Invoice totals are sometimes one cent too low, e.g. 10.005 is shown as 10.00 instead of 10.01."),
    "tax_basis": ("ledgerkit/config.py", "TAX_RATE_BASIS_POINTS = 750", "TAX_RATE_BASIS_POINTS = 75",
                  "test_pipeline.py::test_scenario_02",
                  "Tax on orders is ten times too small: a 100.00 order shows 0.75 tax instead of 7.50."),
    "pages": ("ledgerkit/pagination.py", "return (total + per_page - 1) // per_page", "return total // per_page",
              "test_pipeline.py::test_scenario_04",
              "The report viewer drops the last page when the item count is not a multiple of the page size."),
    "weekend": ("ledgerkit/dates.py", "if day.weekday() >= 5:", "if day.weekday() > 5:",
                "test_pipeline.py::test_scenario_06",
                "Due dates computed in business days sometimes land on a Saturday."),
    "negative": ("ledgerkit/parsing.py", "sign = -1 if text.startswith('-') else 1", "sign = 1",
                 "test_pipeline.py::test_scenario_07",
                 "Credit notes imported from CSV show positive amounts: '-12.50' is parsed as 12.50."),
    "reserve": ("ledgerkit/inventory.py", "if qty > self.available(sku):", "if qty > self.on_hand.get(sku, 0):",
                "test_pipeline.py::test_scenario_08",
                "Two orders could reserve the same last unit of stock; reservations are not taken into account."),
    "top_n": ("ledgerkit/reports.py", "return sorted(totals.items(), key=lambda kv: (-kv[1], kv[0]))[:n]",
              "return sorted(totals.items(), key=lambda kv: (kv[1], kv[0]))[:n]",
              "test_pipeline.py::test_scenario_05",
              "The 'top customers' report lists the smallest customers instead of the largest."),
    "discount_cap": ("ledgerkit/pricing.py", "return min(rate, MAX_DISCOUNT)", "return max(rate, MAX_DISCOUNT)",
                     "test_pipeline.py::test_scenario_03",
                     "Every customer gets the maximum discount, even when they qualify for a small one."),
}

CORE = {
"ledgerkit/__init__.py": '''"""ledgerkit — small accounting and inventory toolkit used by the order service."""
__version__ = "2.4.1"
''',
"ledgerkit/config.py": '''"""Static configuration. Values are integers to avoid float rounding surprises."""

# Tax is expressed in basis points: 750 = 7.50 %.
TAX_RATE_BASIS_POINTS = 750
# Reduced rate for books and food, in basis points.
REDUCED_TAX_BASIS_POINTS = 250
# Maximum discount a customer can receive, in percent.
MAX_DISCOUNT_PERCENT = 30
# Default page size for paginated reports.
DEFAULT_PAGE_SIZE = 25
CURRENCY = "EUR"
''',
"ledgerkit/money.py": '''"""Money helpers. All amounts are Decimal; rounding is half-up to the cent, as required by the auditors."""

from decimal import Decimal, ROUND_FLOOR


def to_decimal(value) -> Decimal:
    """Convert int/float/str to Decimal without binary float artefacts."""
    if isinstance(value, Decimal):
        return value
    return Decimal(str(value))


def round_half_up(value) -> Decimal:
    """Round to two decimals, halves away from zero for positive amounts (10.005 -> 10.01)."""
    value = to_decimal(value)
    return (value * 100 + Decimal('0.5')).to_integral_value(rounding=ROUND_FLOOR) / 100


def add(*amounts) -> Decimal:
    total = Decimal("0")
    for a in amounts:
        total += to_decimal(a)
    return round_half_up(total)


def format_amount(value, currency: str = "EUR") -> str:
    value = round_half_up(value)
    return f"{value:.2f} {currency}"
''',
"ledgerkit/tax.py": '''"""Tax computation for order lines."""

from ledgerkit.config import REDUCED_TAX_BASIS_POINTS, TAX_RATE_BASIS_POINTS
from ledgerkit.money import round_half_up, to_decimal

REDUCED_CATEGORIES = {"books", "food"}


def rate_for(category: str) -> int:
    """Tax rate in basis points for a product category."""
    return REDUCED_TAX_BASIS_POINTS if category in REDUCED_CATEGORIES else TAX_RATE_BASIS_POINTS


def tax_amount(net, category: str = "general"):
    """Tax on a net amount, rounded half-up to the cent."""
    return round_half_up(to_decimal(net) * rate_for(category) / 10000)
''',
"ledgerkit/pricing.py": '''"""Customer discounts."""

from ledgerkit.config import MAX_DISCOUNT_PERCENT
from ledgerkit.money import round_half_up, to_decimal

MAX_DISCOUNT = MAX_DISCOUNT_PERCENT


def discount_rate(years_as_customer: int, annual_volume) -> int:
    """Discount in percent: 2 % per loyal year plus 1 % per 10,000 of annual volume, capped."""
    rate = 2 * max(0, years_as_customer) + int(to_decimal(annual_volume) // 10000)
    return min(rate, MAX_DISCOUNT)


def apply_discount(amount, rate_percent: int):
    return round_half_up(to_decimal(amount) * (100 - rate_percent) / 100)
''',
"ledgerkit/pagination.py": '''"""Pagination for report views."""

from ledgerkit.config import DEFAULT_PAGE_SIZE


def page_count(total: int, per_page: int = DEFAULT_PAGE_SIZE) -> int:
    """Number of pages needed to show `total` items."""
    if per_page <= 0:
        raise ValueError("per_page must be positive")
    return (total + per_page - 1) // per_page


def page(items, number: int, per_page: int = DEFAULT_PAGE_SIZE):
    """Items on page `number` (1-based)."""
    start = (number - 1) * per_page
    return list(items)[start:start + per_page]
''',
"ledgerkit/dates.py": '''"""Business-day arithmetic for due dates (Saturday and Sunday are not business days)."""

import datetime as dt


def add_business_days(start: dt.date, days: int) -> dt.date:
    day = start
    added = 0
    while added < days:
        day += dt.timedelta(days=1)
        if day.weekday() >= 5:
            continue
        added += 1
    return day


def is_business_day(day: dt.date) -> bool:
    return day.weekday() < 5
''',
"ledgerkit/parsing.py": '''"""Parsing of amounts exported by the bank and by spreadsheet tools."""

from decimal import Decimal


def parse_amount(text: str) -> Decimal:
    """Parse '1.234,56', '1,234.56', '-12.50' or '12' into a Decimal."""
    text = text.strip()
    sign = -1 if text.startswith('-') else 1
    text = text.lstrip("+-").replace(" ", "")
    if "," in text and "." in text:
        if text.rfind(",") > text.rfind("."):
            text = text.replace(".", "").replace(",", ".")
        else:
            text = text.replace(",", "")
    elif "," in text:
        text = text.replace(",", ".")
    return sign * Decimal(text)


def parse_row(line: str, sep: str = ";"):
    customer, amount, category = (p.strip() for p in line.split(sep))
    return customer, parse_amount(amount), category
''',
"ledgerkit/inventory.py": '''"""Stock levels and reservations."""


class Inventory:
    def __init__(self):
        self.on_hand: dict[str, int] = {}
        self.reserved: dict[str, int] = {}

    def receive(self, sku: str, qty: int) -> None:
        self.on_hand[sku] = self.on_hand.get(sku, 0) + qty

    def available(self, sku: str) -> int:
        return self.on_hand.get(sku, 0) - self.reserved.get(sku, 0)

    def reserve(self, sku: str, qty: int) -> None:
        """Reserve stock for an order; raises if not enough stock is available."""
        if qty > self.available(sku):
            raise ValueError(f"not enough {sku}")
        self.reserved[sku] = self.reserved.get(sku, 0) + qty

    def ship(self, sku: str, qty: int) -> None:
        self.reserved[sku] = self.reserved.get(sku, 0) - qty
        self.on_hand[sku] = self.on_hand.get(sku, 0) - qty
''',
"ledgerkit/reports.py": '''"""Aggregated reports."""

from collections import defaultdict


def totals_by_customer(rows):
    totals = defaultdict(lambda: 0)
    for customer, amount, _ in rows:
        totals[customer] += amount
    return dict(totals)


def top_customers(rows, n: int = 3):
    """The n customers with the largest totals, largest first (ties by name)."""
    totals = totals_by_customer(rows)
    return sorted(totals.items(), key=lambda kv: (-kv[1], kv[0]))[:n]
''',
"ledgerkit/pipeline.py": '''"""End-to-end flows used by the order service: import, invoice, report, due dates and fulfilment."""

import datetime as dt
import importlib

from ledgerkit.dates import add_business_days
from ledgerkit.inventory import Inventory
from ledgerkit.money import add
from ledgerkit.pagination import page_count
from ledgerkit.pricing import apply_discount, discount_rate
from ledgerkit.reports import top_customers
from ledgerkit.tax import tax_amount


def load_rows(records, connector: str = "abacus"):
    """Import third-party records through one of the connectors."""
    mod = importlib.import_module(f"ledgerkit.connectors.{connector}")
    return getattr(mod, f"{connector}_batch")(records)


def invoice(net, category: str = "general", years_as_customer: int = 0, annual_volume=0) -> dict:
    """Discounted net, tax and total of one invoice."""
    rate = discount_rate(years_as_customer, annual_volume)
    discounted = apply_discount(net, rate)
    tax = tax_amount(discounted, category)
    return {"discount_percent": rate, "net": discounted, "tax": tax, "total": add(discounted, tax)}


def report_summary(rows, per_page: int = 25, top: int = 3) -> dict:
    return {"pages": page_count(len(rows), per_page), "top": top_customers(rows, top)}


def due_date(invoice_date: dt.date, terms_business_days: int) -> dt.date:
    return add_business_days(invoice_date, terms_business_days)


def fulfil(stock: dict, orders: list) -> list:
    """Reserve stock for each (order_id, sku, qty) in turn; returns the ids of the orders that could be reserved."""
    inv = Inventory()
    for sku, qty in stock.items():
        inv.receive(sku, qty)
    accepted = []
    for order_id, sku, qty in orders:
        try:
            inv.reserve(sku, qty)
            accepted.append(order_id)
        except ValueError:
            pass
    return accepted
''',
}

TESTS = {
"tests/test_units.py": """from decimal import Decimal
import datetime as dt
from ledgerkit.dates import is_business_day
from ledgerkit.inventory import Inventory
from ledgerkit.money import add, format_amount
from ledgerkit.pagination import page, page_count
from ledgerkit.parsing import parse_amount, parse_row
from ledgerkit.pricing import apply_discount
from ledgerkit.reports import totals_by_customer
from ledgerkit.tax import rate_for


def test_add():
    assert add("0.10", "0.20") == Decimal("0.30")


def test_format():
    assert format_amount("3.5") == "3.50 EUR"


def test_reduced_tax():
    assert rate_for("books") == 250


def test_apply_discount():
    assert apply_discount("200.00", 10) == Decimal("180.00")


def test_page_count_exact():
    assert page_count(50, 25) == 2


def test_page_slice():
    assert page(range(10), 2, 4) == [4, 5, 6, 7]


def test_weekday():
    assert is_business_day(dt.date(2025, 3, 5))


def test_european_format():
    assert parse_amount("1.234,56") == Decimal("1234.56")


def test_row():
    assert parse_row("acme; 10,00 ; food") == ("acme", Decimal("10.00"), "food")


def test_ship():
    inv = Inventory()
    inv.receive("A1", 5)
    inv.reserve("A1", 2)
    inv.ship("A1", 2)
    assert inv.on_hand["A1"] == 3 and inv.available("A1") == 3


def test_totals():
    rows = [("acme", Decimal("10"), "x"), ("acme", Decimal("5"), "y")]
    assert totals_by_customer(rows)["acme"] == Decimal("15")
""",
"tests/test_pipeline.py": """\"\"\"End-to-end scenarios from the order service's acceptance suite.\"\"\"
from decimal import Decimal
import datetime as dt
from ledgerkit import pipeline

ROWS = [("acme", Decimal("10"), "x"), ("bolt", Decimal("50"), "x"), ("acme", Decimal("5"), "y"),
        ("cord", Decimal("1"), "x")]


def test_scenario_01():
    \"\"\"Loyal customer buys books: invoice total.\"\"\"
    assert pipeline.invoice("28.86", "books", 15, 0) == {
        "discount_percent": 30, "net": Decimal("20.20"), "tax": Decimal("0.51"), "total": Decimal("20.71")}


def test_scenario_02():
    \"\"\"Loyal customer buys standard goods: invoice total.\"\"\"
    assert pipeline.invoice("100.00", "general", 15, 0) == {
        "discount_percent": 30, "net": Decimal("70.00"), "tax": Decimal("5.25"), "total": Decimal("75.25")}


def test_scenario_03():
    \"\"\"New small customer buys books: invoice total.\"\"\"
    assert pipeline.invoice("200.00", "books", 1, 5000) == {
        "discount_percent": 2, "net": Decimal("196.00"), "tax": Decimal("4.90"), "total": Decimal("200.90")}


def test_scenario_04():
    \"\"\"Monthly report over 51 rows.\"\"\"
    rows = [(f"c{i}", Decimal("1"), "x") for i in range(51)]
    assert pipeline.report_summary(rows, per_page=25)["pages"] == 3


def test_scenario_05():
    \"\"\"Top customers in the monthly report.\"\"\"
    assert pipeline.report_summary(ROWS, top=2)["top"] == [("bolt", Decimal("50")), ("acme", Decimal("15"))]


def test_scenario_06():
    \"\"\"Invoice issued on a Friday with one business day of payment terms.\"\"\"
    assert pipeline.due_date(dt.date(2025, 3, 7), 1) == dt.date(2025, 3, 10)


def test_scenario_07():
    \"\"\"Credit note imported from an Abacus export.\"\"\"
    rows = pipeline.load_rows([{"abacus_customer": "acme", "abacus_amount": "-12.50", "abacus_category": "x"}])
    assert rows == [("acme", Decimal("-12.50"), "x")]


def test_scenario_08():
    \"\"\"Two orders for the last unit in stock.\"\"\"
    assert pipeline.fulfil({"A1": 1}, [("o1", "A1", 1), ("o2", "A1", 1)]) == ["o1"]
""",
}

PLUGIN_TEMPLATE = '''"""Connector for the {name} export format ({kind}).

The connector converts {name} records into ledgerkit rows. It is kept for compatibility with older
deployments; new integrations should use the generic CSV importer. None of these functions touch money
rounding, taxes, dates or inventory: they only reshape records.
"""

from ledgerkit.parsing import parse_amount

FIELD_MAP_{upper} = {fields}


def normalise_{lower}_record(record: dict) -> dict:
    """Rename the {name} fields to ledgerkit's names and strip whitespace from string values."""
    out = {{}}
    for src, dst in FIELD_MAP_{upper}.items():
        value = record.get(src)
        if isinstance(value, str):
            value = value.strip()
        out[dst] = value
    return out


def {lower}_to_row(record: dict):
    """Return (customer, amount, category) for one {name} record."""
    r = normalise_{lower}_record(record)
    return r.get("customer", ""), parse_amount(str(r.get("amount", "0"))), r.get("category", "general")


def {lower}_batch(records):
    """Convert a batch, skipping records without a customer (logged upstream)."""
    rows = []
    for record in records:
        row = {lower}_to_row(record)
        if row[0]:
            rows.append(row)
    return rows


def describe_{lower}() -> str:
    """Human-readable description used by the admin console."""
    return "{name} connector: maps " + ", ".join(sorted(FIELD_MAP_{upper})) + " to ledgerkit fields."
{extra}
'''

EXTRA_FUNCS = [
    "\n\ndef {lower}_checksum(records) -> int:\n    \"\"\"Order-independent checksum of customer names, for reconciliation.\"\"\"\n"
    "    return sum(sum(map(ord, str(r.get('customer', '')))) for r in records) % 65521\n",
    "\n\ndef {lower}_categories(records) -> list:\n    \"\"\"Distinct categories in a batch, sorted.\"\"\"\n"
    "    return sorted({{str(r.get('category', 'general')) for r in records}})\n",
    "\n\ndef {lower}_split(records, size: int = 100):\n    \"\"\"Split a batch into chunks of at most `size` records.\"\"\"\n"
    "    return [records[i:i + size] for i in range(0, len(records), size)]\n",
]

PLUGIN_NAMES = ["Abacus", "Brightbooks", "Cashline", "Dineros", "Exactly", "Finmark", "Grootboek", "Hyperledger",
                "Invoicely", "Journalix", "Kontor", "Ledgerly", "Moneta", "Numera", "Orderbird", "Payroller",
                "Quickfile", "Receiptor", "Saldo", "Tallyman"]
KINDS = ["CSV", "JSON lines", "fixed-width", "XML", "spreadsheet"]


def _build(seed: int, bugs: list[str]) -> dict[str, str]:
    import random

    rng = random.Random(seed)
    files = dict(CORE)
    for b in bugs:
        path, good, bad, _, _ = BUGS[b]
        assert good in files[path], (b, path)
        files[path] = files[path].replace(good, bad)
    for i, name in enumerate(PLUGIN_NAMES):
        fields = {f"{name.lower()}_{k}": k for k in ("customer", "amount", "category", "reference", "date")}
        extra = "".join(t.format(lower=name.lower()) for t in rng.sample(EXTRA_FUNCS, 2))
        # long docstring padding so the connectors look like the real thing (and fill the context)
        doc = "\n".join(f"# Compatibility note {k}: field '{f}' maps to '{v}' since version {1 + k % 3}.{k}."
                        for k, (f, v) in enumerate(fields.items()) for _ in range(18))
        files[f"ledgerkit/connectors/{name.lower()}.py"] = (
            PLUGIN_TEMPLATE.format(name=name, kind=rng.choice(KINDS), upper=name.upper(), lower=name.lower(),
                                   fields=repr(fields), extra=extra) + "\n" + doc + "\n")
    files["ledgerkit/connectors/__init__.py"] = '"""Import connectors for third-party bookkeeping exports."""\n'
    files.update(TESTS)
    files["setup.cfg"] = "[tool:pytest]\ntestpaths = tests\npythonpath = .\n"
    return files


def _run_pytest(root: Path, selector: str = "", timeout: int = 90) -> tuple[str, dict[str, bool]]:
    # -B: never write bytecode. An edit of the same size within the same second as an earlier run would otherwise
    # be shadowed by the stale .pyc (mtime + size check), and agents often edit and run the tests in one step.
    for cache in root.rglob("__pycache__"):
        shutil.rmtree(cache, ignore_errors=True)
    args = [sys.executable, "-I", "-B", "-m", "pytest", "-q", "-rA", "--no-header", "-p", "no:cacheprovider"]
    args += [selector] if selector else ["tests"]
    try:
        proc = subprocess.run(args, cwd=root, capture_output=True, text=True, timeout=timeout,
                              env={"PATH": "/usr/bin:/bin"})
        out = proc.stdout + proc.stderr
    except subprocess.TimeoutExpired:
        return "Test run timed out.", {}
    results = {}
    for status, test in re.findall(r"^(PASSED|FAILED|ERROR) (tests/\S+)", out, re.M):
        results[test.removeprefix("tests/").split(" ")[0]] = status == "PASSED"
    return out, results


def generate(seed: int, n_sessions: int = 3, context_limit: int = 32_000,
             step_observation_budget: int | None = 6000, disclose_limit: bool = False) -> TaskInstance:
    import random

    rng = random.Random(seed)
    chosen = rng.sample(sorted(BUGS), 2 * n_sessions)
    sessions = [chosen[2 * k: 2 * k + 2] for k in range(n_sessions)]
    files = _build(seed, chosen)
    state: dict = {"root": None, "owner": None}

    def root(ctx) -> Path:
        """One working copy per run (keyed by the run's cost meter, shared with sub-agents)."""
        if state["owner"] != id(ctx.meter) or state["root"] is None:
            if state["root"]:
                shutil.rmtree(state["root"], ignore_errors=True)
            r = Path(tempfile.mkdtemp(prefix="eam-repo-"))
            for path, text in files.items():
                (r / path).parent.mkdir(parents=True, exist_ok=True)
                (r / path).write_text(text)
            state.update(root=r, owner=id(ctx.meter))
        return state["root"]

    def safe(ctx, path: str) -> Path:
        r = root(ctx)
        p = (r / path.strip().lstrip("/")).resolve()
        if not str(p).startswith(str(r.resolve())):
            raise ValueError("path outside the repository")
        return p

    def list_files(args, ctx):
        r = root(ctx)
        base = safe(ctx, str(args.get("path", "") or "."))
        return "\n".join(sorted(str(p.relative_to(r)) for p in base.rglob("*") if p.is_file()))

    def read_file(args, ctx):
        p = safe(ctx, str(args.get("path", "")))
        if not p.is_file():
            raise ValueError(f"no file '{args.get('path')}'")
        lines = p.read_text().splitlines()
        start = max(1, int(args.get("start_line", 1) or 1))
        end = min(len(lines), int(args.get("end_line", start + 199) or start + 199), start + 199)
        body = "\n".join(f"{i:4d}  {lines[i - 1]}" for i in range(start, end + 1))
        more = f"\n… [{len(lines) - end} more lines]" if end < len(lines) else ""
        return f"{args.get('path')} (lines {start}-{end} of {len(lines)})\n{body}{more}"

    def grep(args, ctx):
        r = root(ctx)
        pattern = re.compile(str(args.get("pattern", "")))
        hits = []
        for p in sorted(safe(ctx, str(args.get("path", "") or ".")).rglob("*.py")):
            for i, line in enumerate(p.read_text().splitlines(), 1):
                if pattern.search(line):
                    hits.append(f"{p.relative_to(r)}:{i}: {line.strip()}")
        return "\n".join(hits[:200]) + (f"\n… [{len(hits) - 200} more]" if len(hits) > 200 else "") or "No matches."

    def replace_in_file(args, ctx):
        p = safe(ctx, str(args.get("path", "")))
        old, new = str(args.get("old", "")), str(args.get("new", ""))
        text = p.read_text() if p.is_file() else ""
        if not old or text.count(old) != 1:
            raise ValueError(f"'old' must occur exactly once in {args.get('path')} (found {text.count(old)})")
        p.write_text(text.replace(old, new))
        return f"Edited {args.get('path')}."

    def run_tests(args, ctx):
        out, _ = _run_pytest(root(ctx), str(args.get("selector", "") or ""))
        return out[-12000:]

    tools = [
        Tool(ToolSpec("list_files", "List files under a directory of the repository (default: the root).",
                      {"type": "object", "properties": {"path": {"type": "string"}}}), list_files),
        Tool(ToolSpec("read_file", "Read a file with line numbers, at most 200 lines per call.",
                      {"type": "object", "properties": {"path": {"type": "string"}, "start_line": {"type": "integer"},
                                                        "end_line": {"type": "integer"}}, "required": ["path"]}),
             read_file),
        Tool(ToolSpec("grep", "Search Python files for a regular expression; returns file:line: text.",
                      {"type": "object", "properties": {"pattern": {"type": "string"}, "path": {"type": "string"}},
                       "required": ["pattern"]}), grep),
        Tool(ToolSpec("replace_in_file", "Replace an exact snippet (must occur once) in a file.",
                      {"type": "object", "properties": {"path": {"type": "string"}, "old": {"type": "string"},
                                                        "new": {"type": "string"}},
                       "required": ["path", "old", "new"]}), replace_in_file),
        Tool(ToolSpec("run_tests", "Run the test suite with pytest (optionally one file or test id, e.g. "
                      "'tests/test_tax.py'); returns the output, including tracebacks of failures.",
                      {"type": "object", "properties": {"selector": {"type": "string"}}}), run_tests),
    ]

    intro = ("You maintain `ledgerkit`, a Python accounting library (package `ledgerkit/`, tests in `tests/`). "
             "Each session is a separate conversation; the conversation of earlier sessions is not available. "
             "Fix bugs in the library code (do not edit the tests), run the tests to check, and finish with "
             "'FINAL ANSWER:' followed by a one-paragraph summary of what you changed.")
    rounds = []
    for k, bs in enumerate(sessions):
        issues = "\n".join(f"- {BUGS[b][4]}" for b in bs)
        rounds.append(f"{intro}\n\nSESSION {k + 1} of {len(sessions)}. New issue reports:\n{issues}")

    baseline: dict = {}

    def round_score(k: int, answer: str) -> float:
        r = state["root"]
        if r is None:
            return 0.0
        check = Path(tempfile.mkdtemp(prefix="eam-check-"))
        try:
            shutil.copytree(r / "ledgerkit", check / "ledgerkit")
            shutil.copy(r / "setup.cfg", check / "setup.cfg")
            for path, text in TESTS.items():  # the pristine tests
                (check / path).parent.mkdir(parents=True, exist_ok=True)
                (check / path).write_text(text)
            _, results = _run_pytest(check)
        finally:
            shutil.rmtree(check, ignore_errors=True)
        targets = [BUGS[b][3] for b in sessions[k]]
        fixed = sum(results.get(t, False) for t in targets) / len(targets)
        if not baseline:  # tests that pass on the unmodified repo (minus the planted bugs' tests)
            orig = Path(tempfile.mkdtemp(prefix="eam-orig-"))
            for path, text in files.items():
                (orig / path).parent.mkdir(parents=True, exist_ok=True)
                (orig / path).write_text(text)
            baseline.update(_run_pytest(orig)[1])
            shutil.rmtree(orig, ignore_errors=True)
        regressed = any(ok and not results.get(t, False) for t, ok in baseline.items())
        return fixed * (0.5 if regressed else 1.0)

    gold = " | ".join(f"session {k + 1}: " + ", ".join(f"{b} ({BUGS[b][0]})" for b in bs)
                      for k, bs in enumerate(sessions))

    def oracle():
        """Mock maintainer: greps for the buggy line of each reported bug, fixes it, runs the tests, answers."""
        def policy(req):
            first = req.messages[0]["content"][0].get("text", "")
            k = int(re.search(r"SESSION (\d+) of", first).group(1)) - 1
            text = context_text(req)
            for b in sessions[k]:
                path, good, bad, _, _ = BUGS[b]
                if f"Edited {path}." in text:
                    continue
                return assistant(tool_use("replace_in_file", {"path": path, "old": bad, "new": good}))
            if "passed" not in text.split("Edited")[-1]:
                return assistant(tool_use("run_tests", {}))
            return final("FINAL ANSWER: fixed " + ", ".join(sessions[k]))

        return policy

    return TaskInstance(
        family="repo_debug", instance_id=f"repo-{seed}", prompt=rounds[-1], tools=tools, check=lambda a: False,
        gold=gold, oracle=oracle, max_steps=60, rounds=rounds, round_score=round_score,
        context_limit=context_limit, step_observation_budget=step_observation_budget, disclose_limit=disclose_limit,
    )
