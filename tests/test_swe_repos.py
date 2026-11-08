"""SWE environment beyond Django: SymPy's test directives and log parser, and explicit workday orders."""

import json

from eam.bench.tasks import swe_env as E
from eam.bench.tasks import swe_workday as W

PATCH = ("diff --git a/sympy/core/tests/test_basic.py b/sympy/core/tests/test_basic.py\n"
         "diff --git a/sympy/core/tests/data.json b/sympy/core/tests/data.json\n")

SYMPY_LOG = """============================= test process starts ==============================
sympy/core/tests/test_basic.py[3]
test_subs ok
test_issue_11617 F
test_atoms E
________________________________________________________________________________
__________ sympy/core/tests/test_basic.py:test_issue_11617 _____________________
AssertionError
"""


def test_sympy_directives_are_test_file_paths():
    assert E.directives(PATCH, "sympy/sympy") == ["sympy/core/tests/test_basic.py"]
    assert E.directives(PATCH) == ["sympy.core.tests.test_basic"]  # Django labels unchanged


def test_sympy_log_parser_matches_swe_bench():
    st = E.parse_log(SYMPY_LOG, "sympy/sympy")
    assert st["test_subs"] == "PASSED" and st["test_issue_11617"] == "FAILED" and st["test_atoms"] == "ERROR"
    inst = {"FAIL_TO_PASS": json.dumps(["test_issue_11617"]), "PASS_TO_PASS": json.dumps(["test_subs"])}
    rep = E.report(st, inst)
    assert rep["f2p_failed"] == ["test_issue_11617"] and not rep["p2p_failed"]


def test_profiles_name_their_own_clone_and_venv():
    assert E.repo_dir() == E.REPO and E.venv_py() == E.VENV_PY
    assert E.repo_dir("sympy/sympy").name == "sympy.git" and "venv-sympy" in str(E.venv_py("sympy/sympy"))


def test_validated_follows_an_explicit_order(tmp_path, monkeypatch):
    monkeypatch.setattr(E, "instances", lambda: {i: {"created_at": c} for i, c in (("a", "1"), ("b", "2"), ("c", "3"))})
    rows = [{"instance_id": i, "fails_before": True, "passes_with_gold": True} for i in "abc"]
    plain = tmp_path / "plain.jsonl"
    plain.write_text("\n".join(json.dumps(r) for r in rows))
    assert W.validated(plain) == ["a", "b", "c"]
    ordered = tmp_path / "ordered.jsonl"
    ordered.write_text("\n".join(json.dumps({**r, "order": o}) for r, o in zip(rows, (2, 0, 1))))
    assert W.validated(ordered) == ["b", "c", "a"]
