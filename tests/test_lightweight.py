"""The lightweight limits AutoMemory promises (README, SECURITY.md): no runtime dependencies, a standard-library-only
plugin, little time added per agent step, and few tokens for the safety wrapping."""

import ast
import re
import sys
import time
from pathlib import Path

from eam import safety as S
from eam.memory_skill import MemorySkill
from eam.tokens import estimate_tokens

ROOT = Path(__file__).resolve().parents[1]


def test_no_runtime_dependencies():
    text = (ROOT / "pyproject.toml").read_text()  # no tomllib: it is not in Python 3.10
    assert re.search(r"^dependencies = \[\]$", text, re.M)


def test_shipped_files_import_only_the_standard_library():
    files = [ROOT / "eam/safety.py", *sorted((ROOT / "plugins/automem/hooks").glob("*.py"))]
    local = {"automem_safety", "eam"}
    for f in files:
        for node in ast.walk(ast.parse(f.read_text())):
            names = ([a.name for a in node.names] if isinstance(node, ast.Import)
                     else [node.module] if isinstance(node, ast.ImportFrom) and node.level == 0 else [])
            for name in names:
                top = name.split(".")[0]
                assert top in sys.stdlib_module_names or top in local or top == "__future__", (f.name, name)


def _per_call_ms(fn, n=200):
    fn()
    t = time.perf_counter()
    for _ in range(n):
        fn()
    return (time.perf_counter() - t) / n * 1000


def test_time_added_per_step_is_under_5_ms(tmp_path):
    skill = MemorySkill(tmp_path / "m", window=16_000)
    output = "\n".join(f"line {i} of an ordinary tool output" for i in range(150))  # about 5 KB, no preview

    def step():
        skill.start_step(8_000)
        skill.ingest_tool_output("bash", output)
        skill.end_step()

    for i in range(200):
        skill.write_note(f"note {i}", "a saved result " * 20)
    assert _per_call_ms(step) < 5
    assert _per_call_ms(skill.session_preamble, n=20) < 5        # recall selection with 200 notes
    assert _per_call_ms(lambda: S.redact("a 1.5 KB note " * 100)) < 5


def test_safety_wrapping_costs_under_2_percent_of_a_small_window():
    overhead = estimate_tokens(S.MEMORY_RULE) + estimate_tokens(S.wrap_memory("", "workspace notes from earlier sessions"))
    assert overhead < 0.02 * 16_000
