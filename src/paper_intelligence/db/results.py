"""Queries for candidate selection and append-only classification results."""

from __future__ import annotations

import json
from typing import Any, Iterable, Sequence

from psycopg import Connection

from paper_intelligence.common.config import PI_USE_PAPERS_CATALOG

# Radar statuses that must never enter paid PI stages (legacy rollback path only).
EXCLUDED_UPSTREAM_STATUSES = ("REJECTED",)

# Legacy Radar-backed eligibility ONLY when PI_USE_PAPERS_CATALOG=0.
# Must NOT be used by the PI-catalog eligibility path.
# Deprecated after final cutover: Radar status allow-list for the
# PI_USE_PAPERS_CATALOG=0 emergency reader branch only. Not authoritative.
PI_ELIGIBLE_STATUSES = (
    "RELEVANT",
    "ENRICHED",
    "ENTITY_RESOLVED",
    "SCORED",
    "CANDIDATE",
)

REQUIRED_UPSTREAM_STATUS = "RELEVANT"

PAPER_FIELDS_SQL_RADAR = """
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

PAPER_FIELDS_SQL_PI = """
SELECT
    p.paper_id AS content_item_id,
    p.title,
    COALESCE(p.abstract, p.summary, '') AS abstract,
    COALESCE(p.categories, '[]'::jsonb) AS categories,
    p.published_at,
    p.content_hash
FROM paper_intelligence.papers p
WHERE p.paper_id = ANY(%s)
ORDER BY p.paper_id
"""


def fetch_papers(conn: Connection, content_item_ids: Sequence[int]) -> list[dict[str, Any]]:
    sql = PAPER_FIELDS_SQL_PI if PI_USE_PAPERS_CATALOG else PAPER_FIELDS_SQL_RADAR
    with conn.cursor() as cur:
        cur.execute(sql, (list(content_item_ids),))
        return list(cur.fetchall())


def select_window_candidates(
    conn: Connection,
    *,
    date_from: str,
    date_until: str,
    stage_task_type: str,
    limit: int | None = None,
    skip_done: bool = True,
    stage_version: str | None = None,
    prompt_version: str | None = None,
    policy_version: str | None = None,
    model: str | None = None,
) -> list[int]:
    """Content ids in the published_at window that still need `stage_task_type`.

    When ``PI_USE_PAPERS_CATALOG`` is on: PI relevance keep (no Radar status).
    When off: legacy ``PI_ELIGIBLE_STATUSES`` on Radar content_items.
    """
    if PI_USE_PAPERS_CATALOG:
        from paper_intelligence.catalog.shadow import select_window_candidates_pi

        return select_window_candidates_pi(
            conn,
            date_from=date_from,
            date_until=date_until,
            stage_task_type=stage_task_type,
            limit=limit,
            skip_done=skip_done,
            stage_version=stage_version,
            prompt_version=prompt_version,
            policy_version=policy_version,
            model=model,
        )

    clauses = [
        "ci.published_at >= %s::timestamptz",
        "ci.published_at < (%s::timestamptz + interval '1 day')",
        "ci.status = ANY(%s)",
    ]
    params: list[Any] = [date_from, date_until, list(PI_ELIGIBLE_STATUSES)]

    if skip_done:
        done_clauses = ["r.content_item_id = ci.id", "r.task_type = %s"]
        done_params: list[Any] = [stage_task_type]
        if stage_version is not None:
            done_clauses.append("r.stage_version = %s")
            done_params.append(stage_version)
        if prompt_version is not None:
            done_clauses.append("r.prompt_version = %s")
            done_params.append(prompt_version)
        if policy_version is not None:
            done_clauses.append("r.policy_version = %s")
            done_params.append(policy_version)
        if model is not None:
            done_clauses.append("r.model = %s")
            done_params.append(model)
        # Legacy NULL input_content_hash counts as reusable; mismatch does not.
        done_clauses.append(
            """(
                r.input_content_hash IS NULL
                OR EXISTS (
                    SELECT 1 FROM paper_intelligence.papers p
                    WHERE p.paper_id = r.content_item_id
                      AND p.content_hash = r.input_content_hash
                )
            )"""
        )
        clauses.append(
            f"""NOT EXISTS (
                SELECT 1 FROM paper_intelligence.paper_classification_results r
                WHERE {" AND ".join(done_clauses)}
            )"""
        )
        params.extend(done_params)

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
    if PI_USE_PAPERS_CATALOG:
        from paper_intelligence.catalog.shadow import count_window_pi

        return count_window_pi(conn, date_from=date_from, date_until=date_until)

    with conn.cursor() as cur:
        cur.execute(
            """
            SELECT COUNT(*) AS n
            FROM research_radar.content_items ci
            WHERE ci.published_at >= %s::timestamptz
              AND ci.published_at < (%s::timestamptz + interval '1 day')
              AND ci.status = ANY(%s)
            """,
            (date_from, date_until, list(PI_ELIGIBLE_STATUSES)),
        )
        return int(cur.fetchone()["n"])


def _content_reusable_sql(alias_r: str = "r", alias_p: str = "p") -> str:
    """Result reusable when hash NULL (legacy) or matches current paper content_hash."""
    return (
        f"({alias_r}.input_content_hash IS NULL "
        f"OR {alias_r}.input_content_hash = {alias_p}.content_hash)"
    )


def ids_with_result(
    conn: Connection,
    content_item_ids: Sequence[int],
    task_type: str,
    *,
    stage_version: str | None = None,
    prompt_version: str | None = None,
    policy_version: str | None = None,
    model: str | None = None,
) -> set[int]:
    """Ids that already have a reusable result for this task/version/model.

    Reusable = version+model match AND (input_content_hash IS NULL OR equals
    papers.content_hash). Legacy NULL hashes do not force a mass rescore.
    """
    if not content_item_ids:
        return set()
    clauses = ["r.task_type = %s", "r.content_item_id = ANY(%s)"]
    params: list[Any] = [task_type, list(content_item_ids)]
    if stage_version is not None:
        clauses.append("r.stage_version = %s")
        params.append(stage_version)
    if prompt_version is not None:
        clauses.append("r.prompt_version = %s")
        params.append(prompt_version)
    if policy_version is not None:
        clauses.append("r.policy_version = %s")
        params.append(policy_version)
    if model is not None:
        clauses.append("r.model = %s")
        params.append(model)
    clauses.append(_content_reusable_sql())
    with conn.cursor() as cur:
        cur.execute(
            f"""
            SELECT DISTINCT r.content_item_id
            FROM paper_intelligence.paper_classification_results r
            LEFT JOIN paper_intelligence.papers p ON p.paper_id = r.content_item_id
            WHERE {" AND ".join(clauses)}
            """,
            params,
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
            params = (
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
                row.get("input_content_hash"),
            )
            try:
                cur.execute(
                    """
                    INSERT INTO paper_intelligence.paper_classification_results
                        (content_item_id, task_type, result_json, method, provider, model,
                         prompt_version, policy_version, stage_version, confidence, run_id,
                         input_content_hash)
                    VALUES (%s, %s, %s::jsonb, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                    """,
                    params,
                )
            except Exception as exc:
                if "input_content_hash" not in str(exc):
                    raise
                # Migration 016 not applied yet.
                cur.execute(
                    """
                    INSERT INTO paper_intelligence.paper_classification_results
                        (content_item_id, task_type, result_json, method, provider, model,
                         prompt_version, policy_version, stage_version, confidence, run_id)
                    VALUES (%s, %s, %s::jsonb, %s, %s, %s, %s, %s, %s, %s, %s)
                    """,
                    params[:11],
                )
    return len(payload)


def latest_screen_scores(
    conn: Connection, *, date_from: str, date_until: str
) -> list[dict[str, Any]]:
    """Most recent PI screen row per paper in the published_at window.

    Quality routing uses PI screen ``gate.passed`` only — never Radar status.
    Date window comes from PI papers when catalog flag is on, else Radar items.
    """
    if PI_USE_PAPERS_CATALOG:
        from paper_intelligence.catalog.shadow import latest_screen_scores_pi

        return latest_screen_scores_pi(conn, date_from=date_from, date_until=date_until)

    with conn.cursor() as cur:
        cur.execute(
            """
            SELECT DISTINCT ON (r.content_item_id)
                r.content_item_id,
                r.result_json,
                r.created_at,
                r.stage_version,
                r.prompt_version,
                r.policy_version,
                r.model,
                ci.published_at
            FROM paper_intelligence.paper_classification_results r
            JOIN research_radar.content_items ci ON ci.id = r.content_item_id
            LEFT JOIN paper_intelligence.papers p ON p.paper_id = r.content_item_id
            WHERE r.task_type = 'screen'
              AND ci.published_at >= %s::timestamptz
              AND ci.published_at < (%s::timestamptz + interval '1 day')
              AND (r.input_content_hash IS NULL OR r.input_content_hash = p.content_hash)
            ORDER BY r.content_item_id, r.created_at DESC
            """,
            (date_from, date_until),
        )
        return list(cur.fetchall())
