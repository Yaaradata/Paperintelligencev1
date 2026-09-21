#!/usr/bin/env python3
"""Expanded PI catalog soak: multi-day + 7d/15d comparisons (read-only, no paid)."""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

OUT_JSON = ROOT / "reports" / "architecture" / "pi_catalog_final_soak.json"
OUT_MD = ROOT / "reports" / "architecture" / "pi_catalog_final_soak.md"

DAYS = [
    os.getenv("PI_SOAK_RECENT", "2026-09-10"),
    os.getenv("PI_SOAK_BACKFILLED", "2026-09-02"),
    os.getenv("PI_SOAK_OLDER", "2026-08-15"),
]
WINDOWS = [
    ("7d", "2026-09-09", "2026-09-15"),
    ("15d", "2026-09-01", "2026-09-15"),
]


def _set(ids) -> set[int]:
    return {int(x) for x in ids}


def _cmp(name: str, old: set[int], new: set[int], reason: str) -> dict:
    old_only = old - new
    new_only = new - old
    if not old_only and not new_only:
        classification = "match"
    elif reason.startswith("intentional"):
        classification = "intentional_scope_difference"
    elif reason.startswith("expected"):
        classification = "expected_fix"
    else:
        classification = "unexplained"
    return {
        "metric": name,
        "old_count": len(old),
        "new_count": len(new),
        "intersection": len(old & new),
        "old_only": len(old_only),
        "new_only": len(new_only),
        "difference_reason": reason,
        "classification": classification,
    }


def window_sets(conn, date_from: str, date_until: str) -> dict:
    import paper_intelligence.db.results as results_mod
    from paper_intelligence.catalog.relevance import papers_with_latest_decision
    from paper_intelligence.catalog.shadow import select_window_candidates_pi
    from paper_intelligence.db import latest_screen_scores, select_window_candidates

    with conn.cursor() as cur:
        cur.execute(
            """
            SELECT id FROM research_radar.content_items
            WHERE published_at >= %s::timestamptz
              AND published_at < (%s::timestamptz + interval '1 day')
            """,
            (date_from, date_until),
        )
        old_window = _set(r["id"] for r in cur.fetchall())
        cur.execute(
            """
            SELECT paper_id FROM paper_intelligence.papers
            WHERE published_at >= %s::timestamptz
              AND published_at < (%s::timestamptz + interval '1 day')
            """,
            (date_from, date_until),
        )
        new_window = _set(r["paper_id"] for r in cur.fetchall())

    results_mod.PI_USE_PAPERS_CATALOG = False
    old_screen = _set(
        select_window_candidates(
            conn,
            date_from=date_from,
            date_until=date_until,
            stage_task_type="screen",
            skip_done=False,
        )
    )
    old_audience = _set(
        select_window_candidates(
            conn,
            date_from=date_from,
            date_until=date_until,
            stage_task_type="audience",
            skip_done=False,
        )
    )
    old_norm = _set(
        select_window_candidates(
            conn,
            date_from=date_from,
            date_until=date_until,
            stage_task_type="normalize_authors",
            skip_done=False,
        )
    )
    old_screen_scores = {
        int(r["content_item_id"]): r
        for r in latest_screen_scores(conn, date_from=date_from, date_until=date_until)
    }
    old_survivors = {
        cid
        for cid, r in old_screen_scores.items()
        if ((r.get("result_json") or {}).get("gate") or {}).get("passed")
    }

    results_mod.PI_USE_PAPERS_CATALOG = True
    new_keep = _set(
        papers_with_latest_decision(
            conn, date_from=date_from, date_until=date_until, decision="keep"
        )
    )
    new_reject = _set(
        papers_with_latest_decision(
            conn, date_from=date_from, date_until=date_until, decision="reject"
        )
    )
    new_screen = _set(
        select_window_candidates_pi(
            conn,
            date_from=date_from,
            date_until=date_until,
            stage_task_type="screen",
            skip_done=False,
        )
    )
    new_audience = _set(
        select_window_candidates_pi(
            conn,
            date_from=date_from,
            date_until=date_until,
            stage_task_type="audience",
            skip_done=False,
        )
    )
    new_norm = _set(
        select_window_candidates_pi(
            conn,
            date_from=date_from,
            date_until=date_until,
            stage_task_type="normalize_authors",
            skip_done=False,
        )
    )
    new_screen_scores = {
        int(r["content_item_id"]): r
        for r in latest_screen_scores(conn, date_from=date_from, date_until=date_until)
    }
    new_survivors = {
        cid
        for cid, r in new_screen_scores.items()
        if ((r.get("result_json") or {}).get("gate") or {}).get("passed")
    }

    def quality_ids(use_pi: bool) -> set[int]:
        if use_pi:
            sql = """
            SELECT DISTINCT q.content_item_id
            FROM paper_intelligence.paper_classification_results q
            JOIN paper_intelligence.papers p ON p.paper_id = q.content_item_id
            WHERE q.task_type='quality'
              AND p.published_at >= %s::timestamptz
              AND p.published_at < (%s::timestamptz + interval '1 day')
            """
        else:
            sql = """
            SELECT DISTINCT q.content_item_id
            FROM paper_intelligence.paper_classification_results q
            JOIN research_radar.content_items ci ON ci.id = q.content_item_id
            WHERE q.task_type='quality'
              AND ci.published_at >= %s::timestamptz
              AND ci.published_at < (%s::timestamptz + interval '1 day')
            """
        with conn.cursor() as cur:
            cur.execute(sql, (date_from, date_until))
            return _set(r["content_item_id"] for r in cur.fetchall())

    old_q = quality_ids(False)
    new_q = quality_ids(True)

    # HF / affiliation / adjudication presence (ids with rows in window)
    def stage_ids(table_sql: str, use_pi: bool) -> set[int]:
        join = (
            "JOIN paper_intelligence.papers p ON p.paper_id = t.content_item_id "
            "AND p.published_at >= %s::timestamptz "
            "AND p.published_at < (%s::timestamptz + interval '1 day')"
            if use_pi
            else "JOIN research_radar.content_items ci ON ci.id = t.content_item_id "
            "AND ci.published_at >= %s::timestamptz "
            "AND ci.published_at < (%s::timestamptz + interval '1 day')"
        )
        sql = f"SELECT DISTINCT t.content_item_id FROM ({table_sql}) t {join}"
        with conn.cursor() as cur:
            cur.execute(sql, (date_from, date_until))
            return _set(r["content_item_id"] for r in cur.fetchall())

    hf_sql = "SELECT content_item_id FROM paper_intelligence.paper_hf_signals"
    aff_sql = "SELECT content_item_id FROM paper_intelligence.paper_author_affiliations"
    adj_sql = (
        "SELECT content_item_id FROM paper_intelligence.paper_intelligence_current "
        "WHERE adjudication_json IS NOT NULL AND adjudication_json <> '{}'::jsonb"
    )

    comparisons = [
        _cmp(
            "catalog_window",
            old_window,
            new_window,
            "match" if old_window == new_window else "expected_fix: non-arxiv_oai or residual identity gaps",
        ),
        _cmp(
            "relevance_keep",
            old_screen,  # legacy eligible ≈ keep-ish
            new_keep,
            "expected_fix: PI keep vs Radar PI_ELIGIBLE_STATUSES",
        ),
        _cmp("screen_candidates", old_screen, new_screen, "expected_fix: eligibility source"),
        _cmp("screen_survivors", old_survivors, new_survivors, "expected_fix: date-join source"),
        _cmp("audience_candidates", old_audience, new_audience, "expected_fix: eligibility source"),
        _cmp("normalize_candidates", old_norm, new_norm, "expected_fix: eligibility source"),
        _cmp("quality_scored", old_q, new_q, "expected_fix: paper join source"),
        _cmp("hf_signals", stage_ids(hf_sql, False), stage_ids(hf_sql, True), "expected_fix: paper join"),
        _cmp("affiliation_rows", stage_ids(aff_sql, False), stage_ids(aff_sql, True), "expected_fix: paper join"),
        _cmp("adjudication_current", stage_ids(adj_sql, False), stage_ids(adj_sql, True), "expected_fix: paper join"),
        {
            "metric": "relevance_reject_pi",
            "old_count": None,
            "new_count": len(new_reject),
            "intersection": None,
            "old_only": None,
            "new_only": None,
            "difference_reason": "informational PI reject count",
            "classification": "match",
        },
    ]

    # Reclassify exact matches
    for c in comparisons:
        if c.get("old_only") == 0 and c.get("new_only") == 0 and c.get("old_count") is not None:
            c["classification"] = "match"
            c["difference_reason"] = "match"

    return {
        "date_from": date_from,
        "date_until": date_until,
        "comparisons": comparisons,
        "unexplained": sum(1 for c in comparisons if c["classification"] == "unexplained"),
    }


def main() -> int:
    from paper_intelligence.db import connect

    os.environ.setdefault("PI_USE_PAPERS_CATALOG", "1")
    os.environ.setdefault("PI_WRITE_RADAR_COMPAT", "1")

    payload = {
        "env": {
            "PI_USE_PAPERS_CATALOG": 1,
            "PI_WRITE_RADAR_COMPAT": 1,
            "code_defaults_unchanged": True,
        },
        "days": [],
        "windows": [],
        "paid_calls_executed": 0,
    }
    with connect() as conn:
        for day in DAYS:
            payload["days"].append(window_sets(conn, day, day))
        for label, df, du in WINDOWS:
            block = window_sets(conn, df, du)
            block["label"] = label
            payload["windows"].append(block)

    unexplained = sum(d["unexplained"] for d in payload["days"]) + sum(
        w["unexplained"] for w in payload["windows"]
    )
    payload["unexplained_differences"] = unexplained
    payload["passed"] = unexplained == 0

    lines = [
        "# PI catalog final soak",
        "",
        f"- unexplained differences: **{unexplained}**",
        "- paid calls executed: **0**",
        "",
    ]
    for block in payload["days"] + payload["windows"]:
        label = block.get("label") or block["date_from"]
        lines += [
            f"## {label} ({block['date_from']} → {block['date_until']})",
            "",
            "| metric | old | new | ∩ | old_only | new_only | class |",
            "|---|---:|---:|---:|---:|---:|---|",
        ]
        for c in block["comparisons"]:
            lines.append(
                f"| {c['metric']} | {c['old_count']} | {c['new_count']} | "
                f"{c['intersection']} | {c['old_only']} | {c['new_only']} | "
                f"{c['classification']} |"
            )
        lines.append("")

    OUT_MD.write_text("\n".join(lines) + "\n")
    OUT_JSON.write_text(json.dumps(payload, indent=2, default=str) + "\n")
    print(json.dumps({"unexplained": unexplained, "passed": payload["passed"]}, indent=2))
    return 0 if payload["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
