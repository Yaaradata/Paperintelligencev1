"""Queries for candidate selection and append-only classification results."""

from __future__ import annotations

import json
from typing import Any, Iterable, Sequence

from psycopg import Connection

# Papers already filtered by the upstream relevance stage are excluded here:
# 'REJECTED' items never enter a paid PaperIntelligence stage. Prefer RELEVANT.
EXCLUDED_UPSTREAM_STATUSES = ("REJECTED",)
REQUIRED_UPSTREAM_STATUS = "RELEVANT"

PAPER_FIELDS_SQL = """
SELECT
    ci.id AS content_item_id,
    ci.title,
    COALESCE(pm.abstract, ci.summary, '') AS abstract,
    COALESCE(
        NULLIF(pm.categories, '[]'::jsonb),
        ci.categories_raw,
        '[]'::jsonb
    ) AS categories,
    ci.published_at
FROM research_radar.content_items ci
LEFT JOIN research_radar.paper_metadata pm ON pm.content_id = ci.id
WHERE ci.id = ANY(%s)
ORDER BY ci.id
"""


def fetch_papers(conn: Connection, content_item_ids: Sequence[int]) -> list[dict[str, Any]]:
    with conn.cursor() as cur:
        cur.execute(PAPER_FIELDS_SQL, (list(content_item_ids),))
        return list(cur.fetchall())


def select_window_candidates(
    conn: Connection,
    *,
    date_from: str,
    date_until: str,
    stage_task_type: str,
    limit: int | None = None,
    skip_done: bool = True,
) -> list[int]:
    """Content ids in the published_at window that still need `stage_task_type`.

    `date_until` is inclusive of the whole day. Upstream-REJECTED papers are
    excluded so paid stages never spend on them.
    """
    clauses = [
        "ci.published_at >= %s::timestamptz",
        "ci.published_at < (%s::timestamptz + interval '1 day')",
        "ci.status = %s",
    ]
    params: list[Any] = [date_from, date_until, REQUIRED_UPSTREAM_STATUS]

    if skip_done:
        clauses.append(
            """NOT EXISTS (
                SELECT 1 FROM paper_intelligence.paper_classification_results r
                WHERE r.content_item_id = ci.id AND r.task_type = %s
            )"""
        )
        params.append(stage_task_type)

    sql = f"""
        SELECT ci.id
        FROM research_radar.content_items ci
        WHERE {" AND ".join(clauses)}
        ORDER BY ci.id
    """
    if limit:
        sql += " LIMIT %s"
        params.append(limit)

    with conn.cursor() as cur:
        cur.execute(sql, params)
        return [int(row["id"]) for row in cur.fetchall()]


def count_window(conn: Connection, *, date_from: str, date_until: str) -> int:
    with conn.cursor() as cur:
        cur.execute(
            """
            SELECT COUNT(*) AS n
            FROM research_radar.content_items ci
            WHERE ci.published_at >= %s::timestamptz
              AND ci.published_at < (%s::timestamptz + interval '1 day')
              AND ci.status = %s
            """,
            (date_from, date_until, REQUIRED_UPSTREAM_STATUS),
        )
        return int(cur.fetchone()["n"])


def ids_with_result(
    conn: Connection, content_item_ids: Sequence[int], task_type: str
) -> set[int]:
    if not content_item_ids:
        return set()
    with conn.cursor() as cur:
        cur.execute(
            """
            SELECT DISTINCT content_item_id
            FROM paper_intelligence.paper_classification_results
            WHERE task_type = %s AND content_item_id = ANY(%s)
            """,
            (task_type, list(content_item_ids)),
        )
        return {int(row["content_item_id"]) for row in cur.fetchall()}


def insert_classification_results(
    conn: Connection,
    rows: Iterable[dict[str, Any]],
) -> int:
    """Append-only insert into paper_classification_results."""
    payload = list(rows)
    if not payload:
        return 0
    with conn.cursor() as cur:
        for row in payload:
            cur.execute(
                """
                INSERT INTO paper_intelligence.paper_classification_results
                    (content_item_id, task_type, result_json, method, provider, model,
                     prompt_version, policy_version, stage_version, confidence, run_id)
                VALUES (%s, %s, %s::jsonb, %s, %s, %s, %s, %s, %s, %s, %s)
                """,
                (
                    row["content_item_id"],
                    row["task_type"],
                    json.dumps(row.get("result_json") or {}, default=str),
                    row.get("method", "llm"),
                    row.get("provider"),
                    row.get("model"),
                    row.get("prompt_version"),
                    row.get("policy_version"),
                    row.get("stage_version"),
                    row.get("confidence"),
                    row.get("run_id"),
                ),
            )
    return len(payload)


def latest_screen_scores(
    conn: Connection, *, date_from: str, date_until: str
) -> list[dict[str, Any]]:
    """Most recent screen row per paper in the window."""
    with conn.cursor() as cur:
        cur.execute(
            """
            SELECT DISTINCT ON (r.content_item_id)
                r.content_item_id,
                r.result_json,
                r.created_at
            FROM paper_intelligence.paper_classification_results r
            JOIN research_radar.content_items ci ON ci.id = r.content_item_id
            WHERE r.task_type = 'screen'
              AND ci.status = %s
              AND ci.published_at >= %s::timestamptz
              AND ci.published_at < (%s::timestamptz + interval '1 day')
            ORDER BY r.content_item_id, r.created_at DESC
            """,
            (REQUIRED_UPSTREAM_STATUS, date_from, date_until),
        )
        return list(cur.fetchall())
