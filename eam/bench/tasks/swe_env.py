"""Real-repository environment for the SWE workday task: SWE-bench Verified issues on Django (and SymPy).

Data: SWE-bench Verified (Jimenez et al., ICLR 2024; Chowdhury et al., OpenAI 2024), downloaded at run time from the
Hugging Face datasets server into ``~/.cache/eam/swe`` (not redistributed). Repository: a blobless clone of
https://github.com/django/django; every session works in its own git worktree at the issue's base commit. Tests run
with Django's own runner (``tests/runtests.py``) under a Python 3.11 virtualenv with Django's runtime
dependencies, no Docker. Grading follows SWE-bench (github.com/SWE-bench/SWE-bench, MIT): the issue's test patch is
applied to the agent's working copy; the test modules it touches are run (SWE-bench's Django test directives); the
verbose log is parsed with SWE-bench's Django log parser (ported below); the issue counts as resolved iff every
FAIL_TO_PASS and PASS_TO_PASS test passed (skipped tests do not count against it, as in SWE-bench).

Many of SWE-bench's Django test ids are the first line of a test's docstring (unittest prints it in place of the
name at verbosity 2), so they are matched in the log, not turned into labels. Names are compared without the
method suffix that Python 3.11 adds ("test_x (mod.Class.test_x)" = "test_x (mod.Class)"): the dataset uses the
older form for Django < 5.0, and every version runs on Python 3.11 here.

SymPy (the out-of-sample repository) follows SWE-bench's SymPy spec: Python 3.9 with mpmath 1.3.0, the test files
the test patch touches run with ``bin/test -C --verbose``, and the log is read with SWE-bench's ``parse_log_sympy``
(ported below). Every function takes the repository name (default Django); `evaluate` and `resolved` read it from
the instance.
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
DJANGO = "django/django"
PROFILES = {
    DJANGO: {"name": "django", "python": "3.11", "deps": ["asgiref>=3.7", "sqlparse>=0.3.1", "pytz"]},
    "sympy/sympy": {"name": "sympy", "python": "3.9", "deps": ["mpmath==1.3.0"]},
}
DATA = CACHE / "verified.json"
ROWS_URL = ("https://datasets-server.huggingface.co/rows?dataset=princeton-nlp/SWE-bench_Verified&config=default"
            "&split=test&offset={offset}&length=100")
_TEST_ID = re.compile(r"^(\w+) \(([\w.]+)\)")


def repo_dir(repo: str = DJANGO) -> Path:
    return CACHE / f"{PROFILES[repo]['name']}.git"


def venv_py(repo: str = DJANGO) -> Path:
    return CACHE / f"venv-{PROFILES[repo]['name']}" / "bin" / "python"


def _interpreter(version: str) -> str:
    """A `python<version>` on PATH, else one installed by uv (`uv python install <version>`)."""
    found = shutil.which(f"python{version}")
    if found:
        return found
    subprocess.run(["uv", "python", "install", version], check=True, capture_output=True)
    return subprocess.run(["uv", "python", "find", version], check=True, capture_output=True,
                          text=True).stdout.strip()


def ensure_setup(repo: str = DJANGO) -> None:
    """Download the dataset, clone the repository and create its test virtualenv (once)."""
    CACHE.mkdir(parents=True, exist_ok=True)
    if not DATA.exists():
        rows = []
        for offset in range(0, 500, 100):
            with urllib.request.urlopen(ROWS_URL.format(offset=offset), timeout=120) as resp:
                rows += [r["row"] for r in json.load(resp)["rows"]]
        DATA.write_text(json.dumps(rows))
    prof, rdir, py = PROFILES[repo], repo_dir(repo), venv_py(repo)
    if not rdir.exists():
        subprocess.run(["git", "clone", "-q", "--filter=blob:none", "--no-checkout",
                        f"https://github.com/{repo}", str(rdir)], check=True)
    if not py.exists():
        subprocess.run([_interpreter(prof["python"]), "-m", "venv", str(py.parent.parent)], check=True)
        subprocess.run([str(py), "-m", "pip", "-q", "install", *prof["deps"]], check=True)


def instances() -> dict[str, dict]:
    return {r["instance_id"]: r for r in json.loads(DATA.read_text())}


def worktree(commit: str, repo: str = DJANGO) -> Path:
    """A fresh working copy at `commit` (remove with `drop_worktree`)."""
    d = Path(tempfile.mkdtemp(prefix="eam-swe-"))
    shutil.rmtree(d)
    subprocess.run(["git", "-C", str(repo_dir(repo)), "worktree", "add", "-q", "--detach", str(d), commit],
                   check=True, capture_output=True)
    return d


def _main_repo(d: Path) -> Path:
    """The clone a worktree belongs to (its `.git` file reads "gitdir: <clone>/worktrees/<name>")."""
    try:
        gitdir = Path((d / ".git").read_text().split("gitdir:", 1)[1].strip())
        return gitdir.parent.parent
    except (OSError, IndexError):
        return REPO


def drop_worktree(d: Path) -> None:
    subprocess.run(["git", "-C", str(_main_repo(d)), "worktree", "remove", "--force", str(d)], capture_output=True)
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


_NON_TEST_EXTS = (".json", ".png", "csv", ".txt", ".md", ".jpg", ".jpeg", ".pkl", ".yml", ".yaml", ".toml")
_PY311_NAME = re.compile(r"^(\w+) \(([\w.]+)\.\1\)$")


def directives(test_patch: str, repo: str = DJANGO) -> list[str]:
    """SWE-bench's test directives: the files the test patch touches (for Django as runtests.py module labels)."""
    out = []
    for f in re.findall(r"diff --git a/.* b/(.*)", test_patch):
        if any(f.endswith(ext) for ext in _NON_TEST_EXTS):
            continue
        if repo != DJANGO:
            out.append(f)
            continue
        f = f[:-3] if f.endswith(".py") else f
        f = f[len("tests/"):] if f.startswith("tests/") else f
        out.append(f.replace("/", "."))
    return list(dict.fromkeys(out))


def canonical(name: str) -> str:
    return _PY311_NAME.sub(r"\1 (\2)", name.strip())


def parse_log_sympy(log: str) -> dict[str, str]:
    """SWE-bench's `parse_log_sympy` (harness/log_parsers), ported: test function name -> status."""
    status: dict[str, str] = {}
    for m in re.findall(r"(_*) (.*)\.py:(.*) (_*)", log):
        status[f"{m[1]}.py:{m[2]}"] = "FAILED"
    for line in log.split("\n"):
        line = line.strip()
        if line.startswith("test_"):
            if line.endswith(" E"):
                status[line.split()[0]] = "ERROR"
            if line.endswith(" F"):
                status[line.split()[0]] = "FAILED"
            if line.endswith(" ok"):
                status[line.split()[0]] = "PASSED"
    return status


def parse_log(log: str, repo: str = DJANGO) -> dict[str, str]:
    """SWE-bench's `parse_log_django` (harness/log_parsers), ported: test name or docstring line -> status."""
    if repo != DJANGO:
        return parse_log_sympy(log)
    status: dict[str, str] = {}
    prev = None
    for line in log.split("\n"):
        line = line.strip()
        if "--version is equivalent to version" in line:
            status["--version is equivalent to version"] = "PASSED"
        if " ... " in line:
            prev = line.split(" ... ")[0]
        for suffix in (" ... ok", " ... OK", " ...  OK"):
            if line.endswith(suffix):
                if line.startswith("Applying sites.0002_alter_domain_unique...test_no_migrations"):
                    line = line.split("...", 1)[-1].strip()
                status[line.rsplit(suffix, 1)[0]] = "PASSED"
                break
        if " ... skipped" in line:
            status[line.split(" ... skipped")[0]] = "SKIPPED"
        if line.endswith(" ... FAIL"):
            status[line.split(" ... FAIL")[0]] = "FAILED"
        if line.startswith("FAIL:"):
            status[line.split()[1].strip()] = "FAILED"
        if line.endswith(" ... ERROR"):
            status[line.split(" ... ERROR")[0]] = "ERROR"
        if line.startswith("ERROR:"):
            status[line.split()[1].strip()] = "ERROR"
        if line.lstrip().startswith("ok") and prev is not None:
            status[prev] = "PASSED"
    for pattern in (r"^(.*?)\s\.\.\.\sTesting\ against\ Django\ installed\ in\ ((?s:.*?))\ silenced\)\.\nok$",
                    r"^(.*?)\s\.\.\.\sInternal\ Server\ Error:\ \/(.*)\/\nok$",
                    r"^(.*?)\s\.\.\.\sSystem check identified no issues \(0 silenced\)\nok$"):
        for m in re.finditer(pattern, log, re.MULTILINE):
            status[m.group(1)] = "PASSED"
    return {canonical(k): v for k, v in status.items()}


def report(status: dict[str, str], inst: dict) -> dict[str, list[str]]:
    """SWE-bench's per-test outcome: a test fails if it is missing from the log or FAILED/ERROR."""
    out: dict[str, list[str]] = {"f2p_failed": [], "p2p_failed": [], "f2p_passed": []}
    for key, tag in (("FAIL_TO_PASS", "f2p"), ("PASS_TO_PASS", "p2p")):
        for t in json.loads(inst[key]):
            st = status.get(canonical(t))
            if st in ("PASSED", "XFAIL"):
                if tag == "f2p":
                    out["f2p_passed"].append(t)
            elif st is None or st in ("FAILED", "ERROR"):
                out[f"{tag}_failed"].append(t)
    return out


def run_tests(d: Path, selector: str | list[str] = "", timeout: int = 600, repo: str = DJANGO) -> tuple[int, str]:
    """The repository's own test runner in working copy `d`; returns (exit code, output)."""
    args = selector if isinstance(selector, list) else selector.split()
    env = {**os.environ, "PYTHONDONTWRITEBYTECODE": "1", "PYTHONPATH": str(d)}
    if repo == DJANGO:
        cmd = [str(VENV_PY), "tests/runtests.py", "--parallel", "1", "-v", "2", *args]
    else:  # SWE-bench's SymPy test command
        cmd = [str(venv_py(repo)), "bin/test", "-C", "--verbose", *args]
        env["PYTHONWARNINGS"] = "ignore::UserWarning,ignore::SyntaxWarning"
    try:
        r = subprocess.run(cmd, cwd=d, capture_output=True, text=True, timeout=timeout, env=env)
    except subprocess.TimeoutExpired:
        return 124, f"[test run timed out after {timeout}s]"
    return r.returncode, (r.stdout + r.stderr)


def evaluate(d: Path, inst: dict, timeout: int = 1200) -> dict | None:
    """Apply the test patch to `d` (modifies it), run the touched test modules, return SWE-bench's report
    (None if the patch does not apply)."""
    if not apply_patch(d, inst["test_patch"]):
        return None
    repo = inst.get("repo", DJANGO)
    mods = directives(inst["test_patch"], repo)
    if not mods:
        return {"f2p_failed": json.loads(inst["FAIL_TO_PASS"]), "p2p_failed": [], "f2p_passed": [], "log": ""}
    code, out = run_tests(d, mods, timeout=timeout, repo=repo)
    return {**report(parse_log(out, repo), inst), "log": out[-3000:]}


def resolved(d: Path, inst: dict) -> tuple[bool, str]:
    """SWE-bench grading on a working copy that may contain the agent's edits (modifies `d`)."""
    rep = evaluate(d, inst)
    if rep is None:
        return False, "test patch did not apply"
    ok = not rep["f2p_failed"] and not rep["p2p_failed"]
    detail = "" if ok else f"failed: {(rep['f2p_failed'] + rep['p2p_failed'])[:5]}\n{rep['log'][-1500:]}"
    return ok, detail
