"""Run the affiliation stage over a published-at window with full run provenance."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from paper_intelligence.author_affiliation.stage import STAGE_NAME, AffiliationStage
from paper_intelligence.author_affiliation.policy import DEFAULT_POLICY_VERSION, policy_version
from paper_intelligence.common import RunContext
from paper_intelligence.common.config import PI_USE_PAPERS_CATALOG
from paper_intelligence.db import connect
from paper_intelligence.observability.runs import (
    code_commit_sha,
    finish_pipeline_run,
    finish_stage_run,
    record_item_stage_run,
    start_pipeline_run,
    start_stage_run,
)

SELECT_WINDOW_SQL_RADAR = """
SELECT ci.id
FROM research_radar.content_items ci
JOIN research_radar.paper_metadata pm ON pm.content_id = ci.id
JOIN paper_intelligence.paper_authors pa ON pa.content_item_id = ci.id
WHERE ci.published_at >= %s
  AND ci.published_at < %s
  AND (pm.affiliation_text <> '[]'::jsonb OR pm.doi IS NOT NULL)
GROUP BY ci.id
ORDER BY ci.id
"""

SELECT_WINDOW_SQL_PI = """
SELECT p.paper_id AS id
FROM paper_intelligence.papers p
JOIN paper_intelligence.paper_authors pa ON pa.content_item_id = p.paper_id
WHERE p.published_at >= %s
  AND p.published_at < %s
  AND (
    COALESCE(p.affiliation_text, '[]'::jsonb) <> '[]'::jsonb
    OR p.doi IS NOT NULL
  )
GROUP BY p.paper_id
ORDER BY p.paper_id
"""

SELECT_WINDOW_SQL = SELECT_WINDOW_SQL_RADAR


# item_stage_runs.status has its own CHECK vocabulary; StageResult.status does not
# map onto it one-to-one. "unresolved" is recorded as skipped, with the real
# stage status kept in the row metadata.
_ITEM_STATUS = {
    "success": "succeeded",
    "failed": "failed",
    "skipped": "skipped",
    "unresolved": "skipped",
}


def select_window(
    conn: Any, start: str | datetime, end: str | datetime, *, limit: int | None = None
) -> list[int]:
    """Content item ids in [start, end) that have authors and some affiliation signal."""
    base = SELECT_WINDOW_SQL_PI if PI_USE_PAPERS_CATALOG else SELECT_WINDOW_SQL_RADAR
    sql = base + (" LIMIT %s" if limit else "")
    params: tuple[Any, ...] = (start, end, limit) if limit else (start, end)
    with conn.cursor() as cur:
        cur.execute(sql, params)
        return [row["id"] for row in cur.fetchall()]


def run_window(
    start: str | datetime,
    end: str | datetime,
    *,
    limit: int | None = None,
    conn: Any | None = None,
    content_item_ids: list[int] | None = None,
    dry_run: bool = False,
    allow_ror: bool = True,
    allow_openalex: bool = True,
    mode: str = "deep",
    created_by: str | None = None,
) -> dict[str, Any]:
    """Create a pipeline_run + stage_run, process the window, and return a summary."""
    owns_conn = conn is None
    conn = conn or connect()
    try:
        item_ids = content_item_ids or select_window(conn, start, end, limit=limit)
        resolved_policy = policy_version(DEFAULT_POLICY_VERSION)

        stage = AffiliationStage(
            conn,
            allow_ror=allow_ror,
            allow_openalex=allow_openalex,
            mode=mode,
        )

        run_id = start_pipeline_run(
            conn,
            pipeline_name=stage.stage_name,
            trigger_type="manual",
            created_by=created_by,
            metadata={
                "start": str(start),
                "end": str(end),
                "items": len(item_ids),
                "mode": mode,
            },
        )
        stage_run_id = start_stage_run(
            conn,
            run_id,
            stage_name=stage.stage_name,
            stage_version=stage.stage_version,
            policy_version=resolved_policy,
            items_input=len(item_ids),
        )
        run_context = RunContext(
            run_id=run_id,
            stage_run_id=stage_run_id,
            code_commit_sha=code_commit_sha(),
            policy_version=resolved_policy,
            dry_run=dry_run,
        )

        summary: dict[str, Any] = {
            "run_id": run_id,
            "stage_run_id": stage_run_id,
            "policy_version": resolved_policy,
            "mode": mode,
            "items": len(item_ids),
            "by_status": {},
            "by_outcome": {},
            "tier_counts": {},
            "rows_written": 0,
            "rows_deduped": 0,
            "results": [],
        }

        for content_item_id in item_ids:
            started_at = datetime.now().astimezone()
            result = stage.process(content_item_id, run_context)
            summary["by_status"][result.status] = summary["by_status"].get(result.status, 0) + 1
            outcome = result.data.get("outcome", "unknown")
            summary["by_outcome"][outcome] = summary["by_outcome"].get(outcome, 0) + 1
            summary["rows_written"] += int(result.data.get("rows_written") or 0)
            summary["rows_deduped"] += int(result.data.get("rows_deduped") or 0)
            for tier, count in (result.data.get("tier_counts") or {}).items():
                summary["tier_counts"][tier] = summary["tier_counts"].get(tier, 0) + count
            summary["results"].append(
                {"content_item_id": content_item_id, "status": result.status, **result.data}
            )
            record_item_stage_run(
                conn,
                run_id=run_id,
                stage_run_id=stage_run_id,
                content_item_id=content_item_id,
                status=_ITEM_STATUS.get(result.status, "failed"),
                started_at=started_at,
                metadata={
                    **{k: v for k, v in result.data.items() if k != "results"},
                    "stage_status": result.status,
                    "mode": mode,
                },
                error_type=result.metadata.get("error_type"),
                error_message=result.metadata.get("error_message"),
            )
            conn.commit()

        failed = summary["by_status"].get("failed", 0)
        if not failed:
            run_status = "succeeded"
        elif failed < len(item_ids):
            run_status = "partial"
        else:
            run_status = "failed"
        finish_stage_run(
            conn,
            stage_run_id,
            status=run_status,
            items_success=summary["by_status"].get("success", 0),
            items_failed=summary["by_status"].get("failed", 0),
        )
        finish_pipeline_run(
            conn,
            run_id,
            status=run_status,
            items_input=len(item_ids),
            items_succeeded=summary["by_status"].get("success", 0),
            items_failed=summary["by_status"].get("failed", 0),
            items_skipped=summary["by_status"].get("unresolved", 0),
        )
        return summary
    finally:
        if owns_conn:
            conn.close()
