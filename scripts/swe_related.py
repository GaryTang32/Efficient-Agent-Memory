"""Related-issue workdays: reorder validated SWE-bench issues so that each workday stays in one subsystem.

The default workdays take issues by creation date, so consecutive sessions rarely touch the same code and notes
have little to carry. Here issues are grouped by the subsystem their official fix touches (the first three path
parts, e.g. ``django/db/models``, or two for a package's own modules, e.g. ``django/forms``), sorted inside a group
by the finer module (four parts) and then by date, and cut into workdays of `n`; a group's remainder that does not
fill a workday is left out. Writes a validation file with an ``order`` field, which `swe_workday.validated` follows.

    python scripts/swe_related.py results/swe_validation_wide.jsonl results/swe_validation_related.jsonl 5
"""

import json
import re
import sys
from collections import defaultdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from eam.bench.tasks import swe_env as E  # noqa: E402

SRC, OUT = Path(sys.argv[1]), Path(sys.argv[2])
N = int(sys.argv[3]) if len(sys.argv) > 3 else 5
I = E.instances()
rows = [json.loads(line) for line in SRC.read_text().splitlines() if line.strip()]
ok = [r for r in rows if r["fails_before"] and r["passes_with_gold"]]


def key(iid: str, depth: int) -> str:
    files = sorted(re.findall(r"diff --git a/.* b/(.*)", I[iid]["patch"]))
    parts = files[0].split("/") if files else []
    if len(parts) > 2 and depth == 3 and parts[2].endswith(".py"):
        depth = 2  # a package's top-level modules form one subsystem (django/forms, django/utils)
    return "/".join(parts[:depth])


groups = defaultdict(list)
for r in ok:
    groups[key(r["instance_id"], 3)].append(r)
days = []
for g, members in sorted(groups.items(), key=lambda kv: (-len(kv[1]), kv[0])):
    members.sort(key=lambda r: (key(r["instance_id"], 4), I[r["instance_id"]]["created_at"]))
    for k in range(len(members) // N):
        days.append((g, members[k * N:(k + 1) * N]))
with OUT.open("w") as f:
    for d, (g, members) in enumerate(days):
        for j, r in enumerate(members):
            f.write(json.dumps({**r, "order": d * N + j, "workday": d, "subsystem": g}) + "\n")
        print(d, g, [key(r["instance_id"], 4).split("/", 2)[-1] for r in members])
print(f"{len(days)} workdays of {N} ({len(days) * N} of {len(ok)} issues)")
