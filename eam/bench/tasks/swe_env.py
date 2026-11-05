"""Real-repository environment for the SWE workday task: SWE-bench Verified issues on Django.

Data: SWE-bench Verified (Jimenez et al., ICLR 2024; Chowdhury et al., OpenAI 2024), downloaded at run time from the
Hugging Face datasets server into ``~/.cache/eam/swe`` (not redistributed). Repository: a blobless clone of
https://github.com/django/django; every session works in its own git worktree at the issue's base commit. Tests run
with Django's own runner (``tests/runtests.py``) under a Python 3.11 virtualenv with Django's two runtime
dependencies, no Docker. Grading follows SWE-bench: the issue's test patch is applied to the agent's working copy,
and the issue counts as resolved iff every FAIL_TO_PASS and PASS_TO_PASS test passes.
"""

from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
import tempfile
import urllib.request
from pathlib import Path

CACHE = Path(os.environ.get("EAM_SWE_CACHE", Path.home() / ".cache" / "eam" / "swe"))
REPO = CACHE / "django.git"
VENV_PY = CACHE / "venv-django" / "bin" / "python"
DATA = CACHE / "verified.json"
ROWS_URL = ("https://datasets-server.huggingface.co/rows?dataset=princeton-nlp/SWE-bench_Verified&config=default"
            "&split=test&offset={offset}&length=100")
_TEST_ID = re.compile(r"^(\w+) \(([\w.]+)\)")


def ensure_setup() -> None:
    """Download the dataset, clone Django and create the test virtualenv (once)."""
    CACHE.mkdir(parents=True, exist_ok=True)
    if not DATA.exists():
        rows = []
        for offset in range(0, 500, 100):
            with urllib.request.urlopen(ROWS_URL.format(offset=offset), timeout=120) as resp:
                rows += [r["row"] for r in json.load(resp)["rows"]]
        DATA.write_text(json.dumps(rows))
    if not REPO.exists():
        subprocess.run(["git", "clone", "-q", "--filter=blob:none", "--no-checkout",
                        "https://github.com/django/django", str(REPO)], check=True)
    if not VENV_PY.exists():
        subprocess.run(["python3.11", "-m", "venv", str(VENV_PY.parent.parent)], check=True)
        subprocess.run([str(VENV_PY), "-m", "pip", "-q", "install", "asgiref>=3.7", "sqlparse>=0.3.1"], check=True)


def instances() -> dict[str, dict]:
    return {r["instance_id"]: r for r in json.loads(DATA.read_text())}


def worktree(commit: str) -> Path:
    """A fresh working copy at `commit` (remove with `drop_worktree`)."""
    d = Path(tempfile.mkdtemp(prefix="eam-swe-"))
    shutil.rmtree(d)
    subprocess.run(["git", "-C", str(REPO), "worktree", "add", "-q", "--detach", str(d), commit], check=True,
                   capture_output=True)
    return d


def drop_worktree(d: Path) -> None:
    subprocess.run(["git", "-C", str(REPO), "worktree", "remove", "--force", str(d)], capture_output=True)
    shutil.rmtree(d, ignore_errors=True)


def apply_patch(d: Path, patch: str) -> bool:
    r = subprocess.run(["git", "-C", str(d), "apply", "--whitespace=nowarn", "-"], input=patch, text=True,
                       capture_output=True)
    return r.returncode == 0


def labels(test_ids: list[str]) -> list[str]:
    """SWE-bench's Django test ids ("test_x (module.Class)") as runtests.py labels ("module.Class.test_x")."""
    out = []
    for t in test_ids:
        m = _TEST_ID.match(t)
        if m:  # newer ids already end with the method: "test_x (module.Class.test_x)"
            name, path = m.group(1), m.group(2)
            out.append(path if path.endswith("." + name) else f"{path}.{name}")
    return out


def run_tests(d: Path, selector: str | list[str] = "", timeout: int = 600) -> tuple[int, str]:
    """Django's own test runner in working copy `d`; returns (exit code, output)."""
    args = selector if isinstance(selector, list) else selector.split()
    cmd = [str(VENV_PY), "tests/runtests.py", "--parallel", "1", "-v", "2", *args]
    env = {**os.environ, "PYTHONDONTWRITEBYTECODE": "1", "PYTHONPATH": str(d)}
    try:
        r = subprocess.run(cmd, cwd=d, capture_output=True, text=True, timeout=timeout, env=env)
    except subprocess.TimeoutExpired:
        return 124, f"[test run timed out after {timeout}s]"
    return r.returncode, (r.stdout + r.stderr)


def resolved(d: Path, inst: dict) -> tuple[bool, str]:
    """SWE-bench grading on a working copy that may contain the agent's edits (modifies `d`)."""
    if not apply_patch(d, inst["test_patch"]):
        return False, "test patch did not apply"
    tests = labels(json.loads(inst["FAIL_TO_PASS"])) + labels(json.loads(inst["PASS_TO_PASS"]))
    code, out = run_tests(d, tests)
    return code == 0, out[-3000:]
