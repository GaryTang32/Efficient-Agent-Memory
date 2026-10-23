"""Fill a results document's generated sections from result rows.

    python scripts/fill_report.py docs/results/<doc>.md results/a.jsonl results/b.jsonl ...

Replaces the text between `<!-- NAME -->` and `<!-- /NAME -->` (or a bare `<!-- NAME -->` marker) for
NAME in HEADLINE (analyze --summary), ROBUST (--robust), METRICS (--metrics) and SPEND, so the numbers in the
document are always exactly what `python -m eam.bench.analyze` prints for the same files.
"""

import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from eam.bench.analyze import load, metrics, robustness, summary, totals  # noqa: E402


def main(doc: str, paths: list[str]) -> None:
    rows, errors = load(paths)
    sections = {"HEADLINE": summary(rows), "ROBUST": robustness(rows), "METRICS": metrics(rows, errors),
                "SPEND": totals(rows)}
    text = Path(doc).read_text()
    for name, body in sections.items():
        block = f"<!-- {name} -->\n{body.strip()}\n<!-- /{name} -->"
        paired = re.compile(rf"<!-- {name} -->.*?<!-- /{name} -->", re.S)
        text = paired.sub(lambda _: block, text) if paired.search(text) else text.replace(f"<!-- {name} -->", block)
    Path(doc).write_text(text)


if __name__ == "__main__":
    main(sys.argv[1], sys.argv[2:])
