"""The research store: DuckDB over the result rows and run traces, queried in place (no loading, no server).

    pip install duckdb                       # research tooling only; AutoMemory itself needs no dependency
    python scripts/research_store.py invariants          # measurement checks on every evidence row
    python scripts/research_store.py disagreements       # issues where a setting and its ceiling disagree
    python scripts/research_store.py sql "SELECT ..."    # any query over the views below

Views:
    runs      every result row of the evidence files (corrected grading: the validation round onward), with `file`
    issues    one row per graded session: file, spec, model, task instance, session index, issue id (SWE), score
    traces    every trace record (results/traces/*.jsonl.gz), with its `table` field
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
RESULTS = ROOT / "results"
# rows with the corrected grading (validation round, 2026-11-08, onward); older rows suggest hypotheses only
EVIDENCE = ["sameday_*.jsonl", "oos_*.jsonl", "recheck_*.jsonl", "rank3_*.jsonl", "wrap_syn-*.jsonl"]
CEILING = "naive@native"
# the row fields the views use, with nested ones kept as JSON (inferring their varying structure costs gigabytes)
RUN_COLUMNS = {
    "run_id": "VARCHAR", "family": "VARCHAR", "instance": "VARCHAR", "spec": "VARCHAR", "model": "VARCHAR",
    "aux_model": "VARCHAR", "backend": "VARCHAR", "backend_settings": "JSON", "success": "BOOLEAN", "score": "DOUBLE",
    "round_scores": "DOUBLE[]", "overflow": "BOOLEAN", "context_limit": "BIGINT", "finished": "BOOLEAN",
    "unfinished_sessions": "BIGINT", "steps": "BIGINT", "tool_calls": "BIGINT", "sessions": "BIGINT",
    "cost_usd": "DOUBLE", "usage": "JSON", "calls": "BIGINT", "by_tag": "JSON", "peak_prompt_tokens": "BIGINT",
    "events": "JSON", "gold": "VARCHAR",
}


def connect():
    import duckdb

    con = duckdb.connect(config={"threads": 4, "memory_limit": "2GB"})
    files = sorted(str(p) for pat in EVIDENCE for p in RESULTS.glob(pat) if p.stat().st_size)
    if not files:
        sys.exit("no evidence files in results/")
    cols = ", ".join(f"'{k}': '{v}'" for k, v in RUN_COLUMNS.items())
    con.execute(f"""CREATE VIEW runs AS SELECT *, regexp_extract(filename, '[^/]+$') AS file
                    FROM read_json({files}, format='newline_delimited', filename=true, columns={{{cols}}})""")
    con.execute("""CREATE VIEW issues AS
        WITH x AS (SELECT file, split_part(spec, '#', 1) AS spec, model, family, instance, gold, round_scores,
                          generate_subscripts(round_scores, 1) AS i FROM runs)
        SELECT file, spec, model, family, instance, i - 1 AS session,
               CASE WHEN family = 'swe_workday' THEN trim(split_part(gold, ',', i)) ELSE instance END AS issue,
               round_scores[i] AS score
        FROM x""")
    traces = sorted((RESULTS / "traces").glob("*.jsonl.gz"))
    if traces:
        con.execute(f"""CREATE VIEW traces AS SELECT * FROM read_json('{RESULTS / "traces"}/*.jsonl.gz',
                        format='newline_delimited', union_by_name=true)""")
    return con


INVARIANTS = {
    "cost equals the sum of the per-tag costs":
        """SELECT file, instance, spec, cost_usd, by_tag FROM runs
           WHERE abs(cost_usd - coalesce(CAST(by_tag->>'$.main.cost' AS DOUBLE), 0)
                     - coalesce(CAST(by_tag->>'$.aux.cost' AS DOUBLE), 0)) > 1e-6 AND by_tag IS NOT NULL""",
    "every session of a run has a score":
        """SELECT file, instance, spec, sessions, len(round_scores) AS scored FROM runs
           WHERE sessions > 1 AND len(round_scores) <> sessions""",
    "no prompt beyond the window unless the run reports an overflow":
        """SELECT file, instance, spec, peak_prompt_tokens, context_limit FROM runs
           WHERE context_limit IS NOT NULL AND peak_prompt_tokens > context_limit AND NOT overflow""",
    "scores are fractions in [0, 1]":
        """SELECT file, instance, spec, score FROM runs WHERE score < 0 OR score > 1""",
    "rows since the 8K reply cap record their settings":
        """SELECT file, instance, spec FROM runs WHERE file LIKE 'rank3_%' AND backend_settings IS NULL""",
    "every same-day set has a ceiling on the same workdays":
        f"""WITH cells AS (SELECT file, model, split_part(spec, '#', 1) AS spec, list(DISTINCT instance) AS days
                           FROM runs WHERE family = 'swe_workday' GROUP BY ALL)
            SELECT c.file, c.model, c.spec, len(c.days) AS days, len(list_filter(c.days, lambda d: NOT
                   list_contains(coalesce(ceil.days, []), d))) AS days_without_ceiling
            FROM cells c LEFT JOIN cells ceil ON ceil.file = c.file AND ceil.model = c.model AND ceil.spec = '{CEILING}'
            WHERE c.spec <> '{CEILING}' AND c.file NOT LIKE '%_rep-%'
                  AND (ceil.days IS NULL OR len(list_filter(c.days, lambda d: NOT list_contains(ceil.days, d))) > 0)""",
}


# files that break an invariant on purpose, with the reason (the first column of a failing row is the file)
KNOWN = {"recheck_eocc16k-haiku.jsonl": "EoCC alone re-graded alone, compared with another day's cells; superseded by "
                                        "rank3 run 2, where it ran next to its ceiling"}


def invariants(con) -> int:
    failed = 0
    for name, sql in INVARIANTS.items():
        rows = con.execute(sql).fetchall()
        known = [r for r in rows if r[0] in KNOWN]
        rows = [r for r in rows if r[0] not in KNOWN]
        failed += bool(rows)
        print(f"{'FAIL' if rows else 'ok  '}  {name}" + (f": {len(rows)} rows, e.g. {rows[0]}" if rows else ""))
        for r in known:
            print(f"      known: {r[0]}: {KNOWN[r[0]]}")
    n = con.execute("SELECT count(*) FROM runs").fetchone()[0]
    print(f"\n{n} evidence rows; {failed} of {len(INVARIANTS)} checks failed")
    return failed


def show(cur) -> None:
    """Print a query result as a Markdown table (no pandas needed)."""
    cols = [d[0] for d in cur.description]
    print("| " + " | ".join(cols) + " |\n|" + "---|" * len(cols))
    for row in cur.fetchall():
        print("| " + " | ".join("" if v is None else f"{v:.4g}" if isinstance(v, float) else str(v) for v in row) + " |")


def disagreements(con, model: str | None, limit: int) -> None:
    """Per SWE issue and setting: how many runs the setting resolved it and how many its same-file ceiling did."""
    where = f"AND s.model = '{model}'" if model else ""
    show(con.execute(f"""
        WITH s AS (SELECT * FROM issues WHERE family = 'swe_workday')
        SELECT s.model, s.spec, s.issue, sum(s.score) AS setting_resolved, sum(c.score) AS ceiling_resolved,
               count(*) AS runs
        FROM s JOIN s c ON c.file = s.file AND c.model = s.model AND c.issue = s.issue AND c.spec = '{CEILING}'
        WHERE s.spec <> '{CEILING}' {where}
        GROUP BY ALL HAVING sum(s.score) <> sum(c.score)
        ORDER BY abs(sum(s.score) - sum(c.score)) DESC, s.model, s.spec, s.issue LIMIT {limit}"""))


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    sub.add_parser("invariants")
    d = sub.add_parser("disagreements")
    d.add_argument("--model")
    d.add_argument("--limit", type=int, default=60)
    q = sub.add_parser("sql")
    q.add_argument("query")
    a = ap.parse_args()
    con = connect()
    if a.cmd == "invariants":
        sys.exit(1 if invariants(con) else 0)
    if a.cmd == "disagreements":
        disagreements(con, a.model, a.limit)
    else:
        show(con.execute(a.query))


if __name__ == "__main__":
    main()
