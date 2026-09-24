"""Guards for adjudication vs date-mapped quality models."""

from __future__ import annotations

from psycopg import Connection

from paper_intelligence.common.config import PI_USE_PAPERS_CATALOG
from paper_intelligence.quality.model_policy import (
    load_quality_model_policy,
    mapped_quality_model,
    quality_model_env_override,
)
from paper_intelligence.quality.stage import (
    STAGE_VERSION as QUALITY_STAGE_VERSION,
    active_policy_version,
    active_prompt_version,
)


def count_quality_rows_staled_by_model(
    conn: Connection,
    *,
    date_from: str,
    date_until: str,
    stage_version: str | None = None,
    prompt_version: str | None = None,
    policy_version: str | None = None,
) -> dict[str, int | str | None]:
    """Compare latest version-matched quality rows to the date→model mapping.

    A row is "mapping_mismatch" when its model differs from
    ``mapped_quality_model(published_at)``. Env QUALITY_MODEL alone no longer
    false-alarms on Sol-scored Sep 1–15 windows.

    Returns counts plus whether an env override is active.
    """
    stage_version = stage_version or QUALITY_STAGE_VERSION
    prompt_version = prompt_version or active_prompt_version()
    policy_version = policy_version or active_policy_version()
    policy = load_quality_model_policy()
    if PI_USE_PAPERS_CATALOG:
        sql = """
            SELECT r.content_item_id, r.model, p.published_at
            FROM (
                SELECT DISTINCT ON (r.content_item_id)
                    r.content_item_id, r.model, r.stage_version,
                    r.prompt_version, r.policy_version
                FROM paper_intelligence.paper_classification_results r
                JOIN paper_intelligence.papers p ON p.paper_id = r.content_item_id
                WHERE r.task_type = 'quality'
                  AND p.published_at >= %s::timestamptz
                  AND p.published_at < (%s::timestamptz + interval '1 day')
                ORDER BY r.content_item_id, r.created_at DESC
            ) r
            JOIN paper_intelligence.papers p ON p.paper_id = r.content_item_id
            WHERE r.stage_version = %s
              AND r.prompt_version = %s
              AND r.policy_version = %s
            """
    else:
        sql = """
            SELECT r.content_item_id, r.model, ci.published_at
            FROM (
                SELECT DISTINCT ON (r.content_item_id)
                    r.content_item_id, r.model, r.stage_version,
                    r.prompt_version, r.policy_version
                FROM paper_intelligence.paper_classification_results r
                JOIN research_radar.content_items ci ON ci.id = r.content_item_id
                WHERE r.task_type = 'quality'
                  AND ci.published_at >= %s::timestamptz
                  AND ci.published_at < (%s::timestamptz + interval '1 day')
                ORDER BY r.content_item_id, r.created_at DESC
            ) r
            JOIN research_radar.content_items ci ON ci.id = r.content_item_id
            WHERE r.stage_version = %s
              AND r.prompt_version = %s
              AND r.policy_version = %s
            """
    with conn.cursor() as cur:
        cur.execute(
            sql,
            (date_from, date_until, stage_version, prompt_version, policy_version),
        )
        rows = list(cur.fetchall())

    mismatch = 0
    for row in rows:
        expected = mapped_quality_model(row["published_at"], policy=policy)
        if str(row["model"] or "") != expected:
            mismatch += 1

    override = quality_model_env_override()
    return {
        "mapping_mismatch": mismatch,
        "version_matched_quality_rows": len(rows),
        "env_override": override,
        "cutover_date": str(policy["cutover_date"]),
        "pre_cutover_model": policy["pre_cutover_model"],
        "post_cutover_model": policy["post_cutover_model"],
    }
