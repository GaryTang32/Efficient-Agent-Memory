"""swe_workday: a working day on a real repository. Consecutive real GitHub issues from SWE-bench Verified (Django:
4.2 / 5.0 in the 40-issue set, 4.0–5.0 in the wider set; SymPy as the out-of-sample repository), one session per issue; each session starts from a fresh working copy at that issue's base commit, and
the conversation of earlier sessions is gone. Only the memory method's own store (notes, retrieved history) carries
over, which is what a daily Codex or Claude Code user lives with.

Instances are the issues that `scripts/swe_validate.py` confirmed in this environment (the ``validation`` file) (FAIL_TO_PASS fails without
the official fix; everything passes with it), ordered by creation date; workday `seed` takes issues
`seed*n_issues … seed*n_issues + n_issues − 1`. Each issue is graded as SWE-bench does: the issue's test patch is
applied to the agent's working copy and the issue is resolved iff all FAIL_TO_PASS and PASS_TO_PASS tests pass.
"""

from __future__ import annotations

import json
import re
from pathlib import Path

from eam.agent.context import Tool
from eam.bench.tasks import swe_env as E
from eam.bench.tasks.common import TaskInstance
from eam.llm.mock import final
from eam.llm.types import ToolSpec

VALIDATION = Path(__file__).resolve().parents[3] / "results" / "swe_validation.jsonl"
_ISSUE = re.compile(r"ISSUE (\d+) of (\d+)")
PROFILES = {
    "django/django": {"title": "Django", "runner": "Django's own test runner (tests/runtests.py)",
                      "example": "'sitemaps_tests' or 'sitemaps_tests.test_http.HTTPSitemapTests'"},
    "sympy/sympy": {"title": "SymPy", "runner": "SymPy's own test runner (bin/test)",
                    "example": "'sympy/core/tests/test_basic.py' or 'sympy/core/tests/test_basic.py -k test_subs'"},
}


def validated(path: Path = VALIDATION) -> list[str]:
    if not path.exists():
        return []
    rows = [json.loads(line) for line in path.read_text().splitlines() if line.strip()]
    ok = {r["instance_id"]: r for r in rows if r["fails_before"] and r["passes_with_gold"]}
    inst = E.instances()
    if all("order" in r for r in ok.values()):  # an explicit order (scripts/swe_related.py)
        return sorted(ok, key=lambda i: ok[i]["order"])
    return sorted(ok, key=lambda i: (inst[i]["created_at"], i))


def generate(seed: int, n_issues: int = 5, context_limit: int | None = 64_000,
             step_observation_budget: int | None = 12_000, disclose_limit: bool = False,
             validation: str | None = None) -> TaskInstance:
    E.ensure_setup()
    inst = E.instances()
    ids = validated(Path(validation) if validation else VALIDATION)
    issues = ids[seed * n_issues: (seed + 1) * n_issues]
    if len(issues) < n_issues:
        raise ValueError(f"only {len(ids)} validated issues; workday {seed} needs {(seed + 1) * n_issues}")
    repo = inst[issues[0]]["repo"]
    prof = PROFILES[repo]
    E.ensure_setup(repo)
    state: dict = {"k": None, "root": None, "roots": {}}

    def current(ctx) -> int:
        m = _ISSUE.search(ctx.task)
        return int(m.group(1)) - 1 if m else 0

    def root(ctx) -> Path:
        k = current(ctx)
        if k not in state["roots"]:
            state["roots"][k] = E.worktree(inst[issues[k]]["base_commit"], repo)
        return state["roots"][k]

    def safe(ctx, path: str) -> Path:
        r = root(ctx)
        p = (r / str(path or ".").strip().lstrip("/")).resolve()
        if not str(p).startswith(str(r.resolve())):
            raise ValueError("path outside the repository")
        return p

    def list_files(args, ctx):
        r, base = root(ctx), safe(ctx, args.get("path", "."))
        if not base.is_dir():
            raise ValueError(f"no directory '{args.get('path')}'")
        items = sorted(base.iterdir(), key=lambda p: (not p.is_dir(), p.name))
        out = [f"{p.relative_to(r)}{'/' if p.is_dir() else ''}" for p in items if not p.name.startswith(".")]
        return "\n".join(out[:400]) + (f"\n… [{len(out) - 400} more]" if len(out) > 400 else "")

    def read_file(args, ctx):
        p = safe(ctx, args.get("path", ""))
        if not p.is_file():
            raise ValueError(f"no file '{args.get('path')}'")
        lines = p.read_text(errors="replace").splitlines()
        start = max(1, int(args.get("start_line", 1) or 1))
        end = min(len(lines), int(args.get("end_line", start + 199) or start + 199), start + 199)
        body = "\n".join(f"{i:5d}  {lines[i - 1]}" for i in range(start, end + 1))
        more = (f"\n… [{len(lines) - end} more lines; next: read_file start_line={end + 1}]" if end < len(lines)
                else "")
        return f"{args.get('path')} (lines {start}-{end} of {len(lines)})\n{body}{more}"

    def grep(args, ctx):
        r = root(ctx)
        try:
            pattern = re.compile(str(args.get("pattern", "")))
        except re.error as exc:
            raise ValueError(f"invalid regular expression: {exc}")
        hits = []
        for p in sorted(safe(ctx, args.get("path", ".")).rglob("*.py")):
            try:
                for i, line in enumerate(p.read_text(errors="replace").splitlines(), 1):
                    if pattern.search(line):
                        hits.append(f"{p.relative_to(r)}:{i}: {line.strip()[:200]}")
                        if len(hits) > 150:
                            break
            except OSError:
                continue
            if len(hits) > 150:
                break
        return "\n".join(hits[:150]) + ("\n… [more matches; narrow the path or pattern]" if len(hits) > 150 else "") \
            or "No matches."

    def replace_in_file(args, ctx):
        p = safe(ctx, args.get("path", ""))
        old, new = str(args.get("old", "")), str(args.get("new", ""))
        text = p.read_text() if p.is_file() else ""
        if not old or text.count(old) != 1:
            raise ValueError(f"'old' must occur exactly once in {args.get('path')} (found {text.count(old)})")
        p.write_text(text.replace(old, new))
        return f"Edited {args.get('path')}."

    def run_tests(args, ctx):
        selector = str(args.get("labels", "") or "").strip()
        if not selector:
            raise ValueError(f"give test labels, e.g. {prof['example']}")
        code, out = E.run_tests(root(ctx), selector, timeout=600, repo=repo)
        return f"[exit code {code}]\n" + out[-12000:]

    tools = [
        Tool(ToolSpec("list_files", f"List one directory of the {prof['title']} repository (directories end with '/').",
                      {"type": "object", "properties": {"path": {"type": "string", "description": "default: the root"}}}),
             list_files),
        Tool(ToolSpec("read_file", "Read a file with line numbers, at most 200 lines per call.",
                      {"type": "object", "properties": {"path": {"type": "string"}, "start_line": {"type": "integer"},
                                                        "end_line": {"type": "integer"}}, "required": ["path"]}),
             read_file),
        Tool(ToolSpec("grep", "Search Python files under a path for a regular expression; returns file:line: text "
                      "(at most 150 matches).",
                      {"type": "object", "properties": {"pattern": {"type": "string"}, "path": {"type": "string"}},
                       "required": ["pattern"]}), grep),
        Tool(ToolSpec("replace_in_file", "Replace an exact snippet (must occur once) in a file.",
                      {"type": "object", "properties": {"path": {"type": "string"}, "old": {"type": "string"},
                                                        "new": {"type": "string"}},
                       "required": ["path", "old", "new"]}), replace_in_file),
        Tool(ToolSpec("run_tests", f"Run {prof['runner']} on test labels, e.g. {prof['example']}; returns the output.",
                      {"type": "object", "properties": {"labels": {"type": "string"}}, "required": ["labels"]}),
             run_tests),
    ]
    intro = (f"You are a maintainer of {prof['title']} (the repository is checked out at the commit the issue was reported "
             "against). Today you work through a queue of real issues, one per session. Each session is a separate "
             "conversation; the conversation of earlier sessions is not available. Fix the issue in the library code "
             "(do not edit or add tests; hidden tests will check the fix), check it with run_tests, and finish with "
             "'FINAL ANSWER:' followed by a short summary of the change.")
    rounds = [f"{intro}\n\nISSUE {k + 1} of {n_issues} ({issues[k]}):\n\n{inst[i]['problem_statement'].strip()}"
              for k, i in enumerate(issues)]

    def round_score(k: int, answer: str) -> float:
        d = state["roots"].pop(k, None)
        if d is None:  # the agent never touched the repository
            return 0.0
        try:
            ok, _ = E.resolved(d, inst[issues[k]])
        finally:
            E.drop_worktree(d)
        return 1.0 if ok else 0.0

    def oracle():
        return lambda req: final("FINAL ANSWER: no change")

    return TaskInstance(
        family="swe_workday", instance_id=f"swe-{seed}", prompt=rounds[-1], tools=tools, check=lambda a: False,
        gold=", ".join(issues), oracle=oracle, max_steps=60, rounds=rounds, round_score=round_score,
        context_limit=context_limit, step_observation_budget=step_observation_budget, disclose_limit=disclose_limit,
        grade_unfinished=True,
    )
