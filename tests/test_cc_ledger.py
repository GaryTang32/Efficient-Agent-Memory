"""F1 of the Claude Code test plan: the 10-day stock ledger is answerable from its reports, sized around the two
thresholds, released one day at a time, and graded exactly."""

import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
import cc_ledger as L  # noqa: E402


def test_reports_alone_determine_the_key():
    for seed in range(30):
        inst = L.generate(seed)
        assert L.solve(inst) == inst["key"], seed


def test_sizes_sit_around_the_thresholds():
    inst = L.generate(3)
    for d, rep in enumerate(inst["reports"], 1):
        assert 6_000 < len(rep["receipts"]) < 30_000 and 6_000 < len(rep["shipments"]) < 30_000  # plugin previews
        assert len(rep["audit"]) > 30_000                                                        # Claude Code cuts
        if d > 1:
            assert rep["audit"].index("CORRECTIONS POSTED TODAY") > 30_000  # corrections only in the tail


def test_corrections_mostly_reach_back_to_earlier_days():
    inst = L.generate(5)
    day_of = {}
    earlier = total = 0
    for d, rep in enumerate(inst["reports"], 1):
        for kind in ("receipts", "shipments"):
            for eid, *_ in L.EVENT_RE.findall(rep[kind]):
                day_of[eid] = d
        for eid, *_ in L.FIX_RE.findall(rep["audit"].split("CORRECTIONS POSTED TODAY", 1)[1]):
            total += 1
            earlier += day_of[eid] < d
    assert total >= 30 and earlier / total > 0.6


def test_one_day_at_a_time_and_the_key_is_not_in_the_folder(tmp_path):
    inst = L.generate(1)
    L.release_day(tmp_path, inst, 1)
    L.release_day(tmp_path, inst, 2)
    out = subprocess.run([sys.executable, str(tmp_path / "tools" / "report.py"), "receipts"], capture_output=True,
                         text=True, check=True).stdout
    assert out.startswith("RECEIPTS AND RETURNS, day 2")
    missing = subprocess.run([sys.executable, str(tmp_path / "tools" / "report.py"), "opening"], capture_output=True,
                             text=True)
    assert missing.returncode == 1 and "Day 2" in missing.stdout  # day 1's opening report is gone
    files = {p.name for p in tmp_path.rglob("*") if p.is_file()}
    assert files == {"report.py", "today.bin"}
    key_values = [str(v) for v in inst["key"][1]["stock"].values()]
    blob = "".join(p.read_text(errors="replace") for p in tmp_path.rglob("*") if p.is_file())
    assert "closing" not in blob.lower() and not all(v in blob for v in key_values)


def test_grader_and_prompt():
    inst = L.generate(2)
    k = inst["key"][4]
    right = json.dumps({"day": 5, "stock": k["stock"], "lowest": k["lowest"]})
    assert L.grade(f"Summary first.\n```json\n{right}\n```", k) == {**L.grade(right, k)} and L.grade(right, k)["correct"] == 7
    stale = json.dumps({"day": 5, "stock": inst["key"][3]["stock"], "lowest": inst["key"][3]["lowest"]})
    assert L.grade(stale, k)["correct"] < 7
    assert L.grade("no JSON here", k) == {"parsed": False, "checks": {**{s: False for s in k["stock"]}, "lowest": False},
                                          "correct": 0, "total": 7}
    assert L.NOTES_LINE in L.prompt(inst, 3, notes_prompt=True) and L.NOTES_LINE not in L.prompt(inst, 3)
    assert "day 3 of 10" in L.prompt(inst, 3) and "opening" in L.prompt(inst, 1) and "opening" not in L.prompt(inst, 2)


# ---- the inbox (long-session cells) ---------------------------------------------------------------------------
def test_without_an_inbox_nothing_changed():
    """Cell N was piloted on these instances and this prompt: the inbox must not move them."""
    import hashlib
    keys = json.dumps([L.generate(s)["key"] for s in (1000, 1001)]).encode()
    assert hashlib.sha256(keys).hexdigest()[:16] == "c732ebaa047aea59"
    assert hashlib.sha256(L.prompt(L.generate(1000), 2).encode()).hexdigest()[:16] == "76aa1a7b15b7bb3b"
    assert "inbox" not in L.generate(1000) and "inbox" not in L.prompt(L.generate(1000), 2)


def test_what_the_agent_sees_determines_the_key_with_an_inbox():
    for seed in range(20):
        inst = L.generate(seed, inbox_chars=100_000)
        assert L.solve(inst) == inst["key"], seed


def test_the_inbox_changes_answers_and_reaches_back():
    inst = L.generate(4, inbox_chars=100_000)
    blind = L.solve({k: v for k, v in inst.items() if k != "inbox"})  # an agent that never reads the inbox
    assert sum(b != k for b, k in zip(blind, inst["key"])) >= 8      # most days come out wrong
    first_day = {}
    earlier = 0
    for d, rep in enumerate(inst["reports"], 1):
        for kind in ("receipts", "shipments"):
            for _, ref in L.LINE_REF_RE.findall(rep[kind]):
                first_day.setdefault(ref, d)
        earlier += sum(first_day[x] < d for what, x, _ in L.read_inbox(inst["inbox"][d - 1], inst["names"])
                       if what == "event")
    assert earlier >= 5  # short shipments and deliveries of earlier days: they need memory


def test_inbox_size_and_wording():
    inst = L.generate(9, inbox_chars=100_000)
    for msgs in inst["inbox"]:
        assert 10 <= len(msgs) <= 14
        assert 80_000 < sum(len(t) for _, t in msgs) < 125_000  # about 25K tokens a day to read
        text = "".join(t for _, t in msgs)
        assert not any(s in text for s in inst["tracked"])     # products by description only
    assert set(inst["names"]) == set(inst["tracked"])
    heads = {n.split(",")[0] for n in inst["names"].values()}
    assert len(heads) == 6                                     # material and type tell the products apart


def test_inbox_released_one_day_at_a_time_and_prompted(tmp_path):
    inst = L.generate(2, inbox_chars=100_000)
    L.release_day(tmp_path, inst, 1)
    L.release_day(tmp_path, inst, 2)
    names = sorted(p.name for p in (tmp_path / "inbox").iterdir())
    assert names == sorted(n for n, _ in inst["inbox"][1]) and all(n.startswith("day02-") for n in names)
    p = L.prompt(inst, 2)
    assert "inbox/" in p and "Read every message" in p
    assert all(f"{s} ({inst['names'][s]})" in p for s in inst["tracked"])
