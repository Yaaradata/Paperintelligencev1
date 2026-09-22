"""Guards for adjudication vs configured QUALITY_MODEL."""

from __future__ import annotations

from psycopg import Connection

from paper_intelligence.common.config import PI_USE_PAPERS_CATALOG, QUALITY_MODEL
from paper_intelligence.quality.stage import (
    POLICY_VERSION as QUALITY_POLICY_VERSION,
    PROMPT_VERSION as QUALITY_PROMPT_VERSION,
    STAGE_VERSION as QUALITY_STAGE_VERSION,
)


def count_quality_rows_staled_by_model(
    conn: Connection,
    *,
    date_from: str,
    date_until: str,
    quality_model: str = QUALITY_MODEL,
    stage_version: str = QUALITY_STAGE_VERSION,
    prompt_version: str = QUALITY_PROMPT_VERSION,
    policy_version: str = QUALITY_POLICY_VERSION,
) -> int:
    """Count latest quality rows matching current versions but a different model.

    Re-running adjudication with ``quality_model`` would stop treating these as
    ``scored`` (Phase 1 current-version+model rule).
    """
    if PI_USE_PAPERS_CATALOG:
        sql = """
            SELECT COUNT(*) AS n
            FROM (
                SELECT DISTINCT ON (r.content_item_id)
                    r.model, r.stage_version, r.prompt_version, r.policy_version
                FROM paper_intelligence.paper_classification_results r
                JOIN paper_intelligence.papers p ON p.paper_id = r.content_item_id
                WHERE r.task_type = 'quality'
                  AND p.published_at >= %s::timestamptz
                  AND p.published_at < (%s::timestamptz + interval '1 day')
                ORDER BY r.content_item_id, r.created_at DESC
            ) latest
            WHERE latest.stage_version = %s
              AND latest.prompt_version = %s
              AND latest.policy_version = %s
              AND latest.model IS DISTINCT FROM %s
            """
    else:
        sql = """
            SELECT COUNT(*) AS n
            FROM (
                SELECT DISTINCT ON (r.content_item_id)
                    r.model, r.stage_version, r.prompt_version, r.policy_version
                FROM paper_intelligence.paper_classification_results r
                JOIN research_radar.content_items ci ON ci.id = r.content_item_id
                WHERE r.task_type = 'quality'
                  AND ci.published_at >= %s::timestamptz
                  AND ci.published_at < (%s::timestamptz + interval '1 day')
                ORDER BY r.content_item_id, r.created_at DESC
            ) latest
            WHERE latest.stage_version = %s
              AND latest.prompt_version = %s
              AND latest.policy_version = %s
              AND latest.model IS DISTINCT FROM %s
            """
    with conn.cursor() as cur:
        cur.execute(
            sql,
            (
                date_from,
                date_until,
                stage_version,
                prompt_version,
                policy_version,
                quality_model,
            ),
        )
        row = cur.fetchone()
        return int(row["n"] if row else 0)
