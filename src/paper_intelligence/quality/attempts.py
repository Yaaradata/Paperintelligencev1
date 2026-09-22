"""Persist and query per-paper quality LLM attempts (success/failure).

Failures live here — not in paper_classification_results — so ids_with_result /
skip-done logic still treats failed papers as retryable.
"""

from __future__ import annotations

import json
from typing import Any, Iterable, Sequence

from psycopg import Connection

from paper_intelligence.common.config import QUALITY_MODEL

# Keep version defaults in sync with quality.stage (avoid circular imports).
_DEFAULT_STAGE_VERSION = "v001"
_DEFAULT_PROMPT_VERSION = "v001"
_DEFAULT_POLICY_VERSION = "v001"


def insert_quality_attempts(
    conn: Connection,
    rows: Iterable[dict[str, Any]],
) -> int:
    """Append-only insert of quality attempt rows. Returns count inserted."""
    payload = list(rows)
    if not payload:
        return 0
    with conn.cursor() as cur:
        for row in payload:
            cur.execute(
                """
                INSERT INTO paper_intelligence.quality_attempts
                    (content_item_id, run_id, stage_run_id, stage_version,
                     prompt_version, policy_version, model, status,
                     error_summary, metadata)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s::jsonb)
                """,
                (
                    int(row["content_item_id"]),
                    row.get("run_id"),
                    row.get("stage_run_id"),
                    row.get("stage_version") or _DEFAULT_STAGE_VERSION,
                    row.get("prompt_version") or _DEFAULT_PROMPT_VERSION,
                    row.get("policy_version") or _DEFAULT_POLICY_VERSION,
                    row.get("model") or QUALITY_MODEL,
                    row["status"],
                    (row.get("error_summary") or None),
                    json.dumps(row.get("metadata") or {}, default=str),
                ),
            )
    return len(payload)


def record_quality_failures(
    conn: Connection,
    content_item_ids: Sequence[int],
    *,
    run_id: str | None,
    stage_run_id: str | None,
    model: str,
    error_summary: str,
    stage_version: str = _DEFAULT_STAGE_VERSION,
    prompt_version: str = _DEFAULT_PROMPT_VERSION,
    policy_version: str = _DEFAULT_POLICY_VERSION,
    metadata: dict[str, Any] | None = None,
) -> int:
    """Record a failed attempt for each paper id (batch exception / missing parse)."""
    rows = [
        {
            "content_item_id": cid,
            "run_id": run_id,
            "stage_run_id": stage_run_id,
            "stage_version": stage_version,
            "prompt_version": prompt_version,
            "policy_version": policy_version,
            "model": model,
            "status": "failed",
            "error_summary": (error_summary or "quality_failed")[:2000],
            "metadata": metadata or {},
        }
        for cid in content_item_ids
    ]
    return insert_quality_attempts(conn, rows)


def record_quality_successes(
    conn: Connection,
    content_item_ids: Sequence[int],
    *,
    run_id: str | None,
    stage_run_id: str | None,
    model: str,
    stage_version: str = _DEFAULT_STAGE_VERSION,
    prompt_version: str = _DEFAULT_PROMPT_VERSION,
    policy_version: str = _DEFAULT_POLICY_VERSION,
) -> int:
    """Record succeeded attempts alongside classification_results inserts."""
    rows = [
        {
            "content_item_id": cid,
            "run_id": run_id,
            "stage_run_id": stage_run_id,
            "stage_version": stage_version,
            "prompt_version": prompt_version,
            "policy_version": policy_version,
            "model": model,
            "status": "succeeded",
            "error_summary": None,
            "metadata": {},
        }
        for cid in content_item_ids
    ]
    return insert_quality_attempts(conn, rows)


def latest_quality_attempts(
    conn: Connection,
    content_item_ids: Sequence[int],
    *,
    stage_version: str = _DEFAULT_STAGE_VERSION,
    prompt_version: str = _DEFAULT_PROMPT_VERSION,
    policy_version: str = _DEFAULT_POLICY_VERSION,
    model: str | None = None,
) -> dict[int, dict[str, Any]]:
    """Latest attempt per paper for the given quality versions.

    When ``model`` is None, the latest attempt across models (for those versions)
    is returned so callers can match against a per-paper mapped model.
    """
    if not content_item_ids:
        return {}
    clauses = [
        "content_item_id = ANY(%s)",
        "stage_version = %s",
        "prompt_version = %s",
        "policy_version = %s",
    ]
    params: list[Any] = [
        list(content_item_ids),
        stage_version,
        prompt_version,
        policy_version,
    ]
    if model is not None:
        clauses.append("model = %s")
        params.append(model)
    with conn.cursor() as cur:
        cur.execute(
            f"""
            SELECT DISTINCT ON (content_item_id)
                content_item_id, status, error_summary, attempted_at,
                stage_version, prompt_version, policy_version, model, run_id
            FROM paper_intelligence.quality_attempts
            WHERE {" AND ".join(clauses)}
            ORDER BY content_item_id, attempted_at DESC
            """,
            params,
        )
        return {int(r["content_item_id"]): dict(r) for r in cur.fetchall()}
