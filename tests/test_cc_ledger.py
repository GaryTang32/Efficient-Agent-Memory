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
