#!/usr/bin/env python3
"""Completeness audit for one publication window (SQL only, no model, $0).

Window membership is ``papers.published_at::date BETWEEN --from AND --until``,
the same rule the pipeline uses. "The quality row" for a paper is its latest
``task_type='quality'`` row by ``created_at``; defect 9 looks at every row.

Every defect with a count above zero is listed; nothing is filtered out.

Usage:
    PYTHONPATH=src python scripts/audit_window_completeness.py \
        --from 2026-09-21 --until 2026-09-23 [--out reports/.../audit.md] [--json out.json]

Exit code: 0 when the window is publishable, 2 when it is not.
"""
from __future__ import annotations

import argparse
import json
import sys
from datetime import date
from pathlib import Path

from paper_intelligence.db import connect

DIMENSIONS = (
    "technical_significance",
    "apparent_novelty",
    "practical_applicability",
    "professional_value",
    "learning_value",
    "evidence_strength",
)
BAD_QUALITY_STATUSES = ("failed", "pending", "stale_content", "inconsistent_attempt_without_result")
PROSE_MISSING_MAX_RATE = 0.10
MAX_EXAMPLES = 10

BASE_CTES = """
WITH win AS (
    SELECT paper_id, raw_metadata
    FROM paper_intelligence.papers
    WHERE published_at::date BETWEEN %(from)s AND %(until)s
),
screen_latest AS (
    SELECT DISTINCT ON (r.content_item_id) r.content_item_id, r.result_json
    FROM paper_intelligence.paper_classification_results r
    JOIN win ON win.paper_id = r.content_item_id
    WHERE r.task_type = 'screen'
    ORDER BY r.content_item_id, r.created_at DESC
),
screen_passed AS (
    SELECT content_item_id FROM screen_latest
    WHERE (result_json->'gate'->>'passed')::boolean IS TRUE
),
q_all AS (
    SELECT r.*
    FROM paper_intelligence.paper_classification_results r
    JOIN win ON win.paper_id = r.content_item_id
    WHERE r.task_type = 'quality'
),
q_cur AS (
    SELECT DISTINCT ON (content_item_id) *
    FROM q_all
    ORDER BY content_item_id, created_at DESC
),
cur AS (
    SELECT c.*
    FROM paper_intelligence.paper_intelligence_current c
    JOIN win ON win.paper_id = c.content_item_id
),
attempt_latest AS (
    SELECT DISTINCT ON (a.content_item_id) a.content_item_id, a.status, a.error_summary, a.attempted_at
    FROM paper_intelligence.quality_attempts a
    JOIN win ON win.paper_id = a.content_item_id
    ORDER BY a.content_item_id, a.attempted_at DESC
)
"""


def _txt(*path: str) -> str:
    """SQL text accessor, e.g. _txt('composite', 'quality') -> result_json->'composite'->>'quality'."""
    head = "".join(f"->'{k}'" for k in path[:-1])
    return f"result_json{head}->>'{path[-1]}'"


def _blank(expr: str) -> str:
    return f"(NULLIF(btrim({expr}), '') IS NULL)"


def _num(expr: str) -> str:
    return f"(CASE WHEN ({expr}) ~ '^-?[0-9]+(\\.[0-9]+)?$' THEN ({expr})::numeric END)"


def build_checks() -> list[tuple[str, str, str]]:
    """Return (key, label, SELECT yielding content_item_id[, reason])."""
    checks: list[tuple[str, str, str]] = [
        (
            "1_passed_screen_no_quality",
            "Passed screen, no quality row",
            "SELECT s.content_item_id FROM screen_passed s "
            "WHERE NOT EXISTS (SELECT 1 FROM q_all q WHERE q.content_item_id = s.content_item_id)",
        )
    ]
    for dim in DIMENSIONS:
        checks.append(
            (
                f"2_null_{dim}",
                f"Quality row with NULL {dim}",
                f"SELECT content_item_id FROM q_cur WHERE {_num(_txt(dim))} IS NULL",
            )
        )
    composite_null = (
        "jsonb_typeof(result_json->'composite') IS NULL "
        "OR jsonb_typeof(result_json->'composite') = 'null' "
        "OR (jsonb_typeof(result_json->'composite') = 'object' AND ("
        f"{_num(_txt('composite', 'quality'))} IS NULL)) "
        "OR (jsonb_typeof(result_json->'composite') = 'string' AND "
        f"{_blank(_txt('composite'))})"
    )
    checks += [
        (
            "3_null_composite",
            "Quality row with NULL/empty composite",
            f"SELECT content_item_id FROM q_cur WHERE {composite_null}",
        ),
        (
            "4a_null_so_what",
            "Quality row with NULL/empty so_what",
            f"SELECT content_item_id FROM q_cur WHERE {_blank(_txt('so_what'))}",
        ),
        (
            "4b_null_reason_not_higher",
            "Quality row with NULL/empty reason_not_higher",
            "SELECT content_item_id FROM q_cur WHERE "
            f"{_blank(_txt('reason_not_higher'))}",
        ),
    ]
    out_of_range = " OR ".join(
        f"{_num(_txt(d))} NOT BETWEEN 0 AND 10" for d in DIMENSIONS
    )
    comp_out = (
        "(jsonb_typeof(result_json->'composite') = 'object' AND ("
        f"{_num(_txt('composite', 'quality'))} NOT BETWEEN 0 AND 10 OR "
        f"{_num(_txt('composite', 'final'))} NOT BETWEEN 0 AND 10)) "
        "OR (jsonb_typeof(result_json->'composite') = 'number' AND "
        "(result_json->>'composite')::numeric NOT BETWEEN 0 AND 10)"
    )
    checks += [
        (
            "4c_prose_missing_no_failure_record",
            "NULL so_what with no recorded prose failure (quality_attempts, quality_prose_v001)",
            "SELECT q.content_item_id FROM q_cur q "
            f"WHERE {_blank(_txt('so_what'))} "
            "AND NOT EXISTS (SELECT 1 FROM paper_intelligence.quality_attempts a "
            "WHERE a.content_item_id = q.content_item_id AND a.stage_version = 'quality_prose_v001' "
            "AND a.status = 'failed' AND a.attempted_at >= q.created_at)",
        ),
        (
            "5_out_of_range",
            "Dimension or composite outside 0-10",
            f"SELECT content_item_id FROM q_cur WHERE {out_of_range} OR {comp_out}",
        ),
        (
            "6_quality_no_adjudication",
            "Quality row but no paper_intelligence_current row",
            "SELECT q.content_item_id FROM q_cur q "
            "WHERE NOT EXISTS (SELECT 1 FROM cur c WHERE c.content_item_id = q.content_item_id)",
        ),
        (
            "7a_bad_quality_status",
            "quality_status in failed/pending/stale_content/inconsistent_attempt_without_result",
            "SELECT c.content_item_id, c.quality_status || ': ' || COALESCE("
            "a.error_summary, c.adjudication_json->>'quality_selection_reason', 'no reason recorded') "
            "FROM cur c LEFT JOIN attempt_latest a ON a.content_item_id = c.content_item_id "
            f"WHERE c.quality_status IN {BAD_QUALITY_STATUSES!r}",
        ),
        (
            "7b_latest_attempt_failed_no_result",
            "Latest quality attempt failed and no quality row exists",
            "SELECT a.content_item_id, 'attempt failed: ' || left(COALESCE(a.error_summary, ''), 160) "
            "FROM attempt_latest a WHERE a.status = 'failed' "
            "AND NOT EXISTS (SELECT 1 FROM q_all q WHERE q.content_item_id = a.content_item_id)",
        ),
        (
            "8a_scoring_engine_unstamped",
            "Quality row without scoring_engine stamp",
            f"SELECT content_item_id FROM q_cur WHERE {_blank(_txt('scoring_engine'))}",
        ),
        (
            "8b_prose_model_unstamped",
            "Quality row without prose_model stamp",
            f"SELECT content_item_id FROM q_cur WHERE {_blank(_txt('prose_model'))}",
        ),
        (
            "9_scored_under_multiple_engines",
            "Paper scored more than once under different engines",
            "SELECT content_item_id, string_agg(DISTINCT COALESCE(result_json->>'quality_engine', model), ' + ') "
            "FROM q_all GROUP BY content_item_id "
            "HAVING count(DISTINCT COALESCE(result_json->>'quality_engine', model)) > 1",
        ),
        (
            "10_v1_before_window",
            "arXiv v1 (raw_metadata.created) before window start",
            "SELECT paper_id, 'v1=' || (raw_metadata->>'created') || ' updated=' || COALESCE(raw_metadata->>'updated', '') "
            "FROM win WHERE (raw_metadata->>'created') ~ '^[0-9]{4}-[0-9]{2}-[0-9]{2}' "
            "AND (raw_metadata->>'created')::date < %(from)s",
        ),
    ]
    return checks


def run_audit(date_from: date, date_until: date) -> dict:
    params = {"from": date_from, "until": date_until}
    results = []
    with connect() as conn, conn.cursor() as cur:
        cur.execute(
            BASE_CTES
            + """
            SELECT
              (SELECT count(*) FROM win) AS window_papers,
              (SELECT count(*) FROM screen_passed) AS screen_passed,
              (SELECT count(*) FROM q_cur) AS papers_with_quality,
              (SELECT count(*) FROM q_all) AS quality_rows_total
            """,
            params,
        )
        totals = dict(cur.fetchone())
        for key, label, select in build_checks():
            cur.execute(BASE_CTES + f"SELECT * FROM ({select}) x ORDER BY 1", params)
            rows = cur.fetchall()
            examples = []
            for row in rows[:MAX_EXAMPLES]:
                vals = list(row.values()) if hasattr(row, "values") else list(row)
                examples.append(str(vals[0]) + (f" ({vals[1]})" if len(vals) > 1 and vals[1] else ""))
            results.append({"key": key, "defect": label, "count": len(rows), "examples": examples})

    window = totals["window_papers"] or 0
    scored = totals["papers_with_quality"] or 0
    by_key = {r["key"]: r for r in results}
    for r in results:
        r["pct_window"] = (100.0 * r["count"] / window) if window else 0.0

    prose_missing = max(by_key["4a_null_so_what"]["count"], by_key["4b_null_reason_not_higher"]["count"])
    prose_rate = (prose_missing / scored) if scored else 1.0
    blocking = []
    if prose_rate > PROSE_MISSING_MAX_RATE:
        blocking.append(
            f"prose missing on {prose_missing}/{scored} scored papers ({prose_rate:.1%}) > "
            f"{PROSE_MISSING_MAX_RATE:.0%}"
        )
    for key in ("1_passed_screen_no_quality", "3_null_composite", "5_out_of_range", "6_quality_no_adjudication"):
        if by_key[key]["count"]:
            blocking.append(f"{by_key[key]['defect']}: {by_key[key]['count']}")
    for key in (k for k in by_key if k.startswith("2_null_")):
        if by_key[key]["count"]:
            blocking.append(f"{by_key[key]['defect']}: {by_key[key]['count']}")
    return {
        "from": date_from.isoformat(),
        "until": date_until.isoformat(),
        "totals": totals,
        "prose_missing": prose_missing,
        "prose_missing_rate": prose_rate,
        "publishable": not blocking,
        "blocking_reasons": blocking,
        "defects": results,
    }


def render_markdown(audit: dict) -> str:
    t = audit["totals"]
    lines = [
        f"# Window completeness audit {audit['from']} .. {audit['until']}",
        "",
        f"Window papers: {t['window_papers']} · passed screen: {t['screen_passed']} · "
        f"papers with a quality row: {t['papers_with_quality']} · quality rows (all engines/runs): "
        f"{t['quality_rows_total']}",
        "",
        "| defect | count | % of window | example ids (up to 10) |",
        "|---|---:|---:|---|",
    ]
    for r in audit["defects"]:
        ex = "<br>".join(r["examples"]) if r["examples"] else "—"
        lines.append(f"| {r['defect']} | {r['count']} | {r['pct_window']:.1f}% | {ex} |")
    lines += ["", f"Prose missing: {audit['prose_missing']} of {t['papers_with_quality']} scored papers "
              f"({audit['prose_missing_rate']:.1%}); threshold {PROSE_MISSING_MAX_RATE:.0%}.", ""]
    if audit["publishable"]:
        lines.append("**Complete enough to publish: YES.**")
    else:
        lines.append("**Complete enough to publish: NO.**")
        lines += [f"- {reason}" for reason in audit["blocking_reasons"]]
    return "\n".join(lines) + "\n"


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--from", dest="date_from", required=True, type=date.fromisoformat)
    ap.add_argument("--until", dest="date_until", required=True, type=date.fromisoformat)
    ap.add_argument("--out", type=Path, help="write markdown here as well as stdout")
    ap.add_argument("--json", type=Path, help="write machine-readable result here")
    from paper_intelligence.common.v1_floor import add_v1_floor_argument, apply_v1_floor

    add_v1_floor_argument(ap)
    args = ap.parse_args()
    if not apply_v1_floor(args):
        return 0

    audit = run_audit(args.date_from, args.date_until)
    md = render_markdown(audit)
    print(md)
    if args.out:
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_text(md)
    if args.json:
        args.json.parent.mkdir(parents=True, exist_ok=True)
        args.json.write_text(json.dumps(audit, indent=2, default=str))
    return 0 if audit["publishable"] else 2


if __name__ == "__main__":
    sys.exit(main())
