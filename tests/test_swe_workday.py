"""swe_workday on the real Django checkout (skipped when the SWE-bench cache or validation file is absent)."""

import json

import pytest

from eam.bench.tasks import swe_env as E

pytestmark = pytest.mark.skipif(not (E.REPO.exists() and E.DATA.exists()), reason="SWE-bench cache not set up")


def test_workday_tools_and_grading(tmp_path):
    from eam.bench.tasks import swe_workday as W

    inst = E.instances()
    iid = "django__django-16255"
    val = tmp_path / "v.jsonl"
    val.write_text(json.dumps({"instance_id": iid, "fails_before": True, "passes_with_gold": True}) + "\n")
    t = W.generate(0, n_issues=1, validation=str(val))

    class Ctx:
        task = t.rounds[0]

    tools = {x.spec.name: x.handler for x in t.tools}
    assert "django/" in tools["list_files"]({}, Ctx())
    assert "class Sitemap" in tools["grep"]({"pattern": "^class Sitemap", "path": "django/contrib/sitemaps"}, Ctx())
    assert t.round_score(0, "") == 0.0  # unchanged code: the hidden tests fail
    t2 = W.generate(0, n_issues=1, validation=str(val))
    t2.tools[0].handler({}, Ctx())  # the first tool call creates the session's worktree
    # apply the official fix through the agent's own edit tool, as an agent would
    patch = inst[iid]["patch"]
    old = [l[1:] for l in patch.splitlines() if l.startswith("-") and not l.startswith("---")]
    new = [l[1:] for l in patch.splitlines() if l.startswith("+") and not l.startswith("+++")]
    edit = {x.spec.name: x.handler for x in t2.tools}["replace_in_file"]
    edit({"path": "django/contrib/sitemaps/__init__.py", "old": "\n".join(old), "new": "\n".join(new)}, Ctx())
    assert t2.round_score(0, "") == 1.0
