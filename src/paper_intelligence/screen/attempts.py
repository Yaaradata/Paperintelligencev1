"""Persist and query per-paper screen LLM attempts (success/failure).

Failures live here — not in paper_classification_results — so skip-done /
funnel logic can distinguish failed calls from never-attempted papers.
"""

from __future__ import annotations

import json
from typing import Any, Iterable, Sequence

from psycopg import Connection

from paper_intelligence.common.config import SCREEN_MODEL

_DEFAULT_STAGE_VERSION = "v001"
_DEFAULT_PROMPT_VERSION = "v002"
_DEFAULT_POLICY_VERSION = "v001"


def insert_screen_attempts(
    conn: Connection,
    rows: Iterable[dict[str, Any]],
) -> int:
    """Append-only insert of screen attempt rows. Returns count inserted."""
    payload = list(rows)
    if not payload:
        return 0
    with conn.cursor() as cur:
        for row in payload:
            cur.execute(
                """
                INSERT INTO paper_intelligence.screen_attempts
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
                    row.get("model") or SCREEN_MODEL,
                    row["status"],
                    (row.get("error_summary") or None),
                    json.dumps(row.get("metadata") or {}, default=str),
                ),
            )
    return len(payload)


def record_screen_successes(
    conn: Connection,
    content_item_ids: Sequence[int],
    *,
    run_id: str | None,
    stage_run_id: str | None,
    model: str,
    stage_version: str = _DEFAULT_STAGE_VERSION,
    prompt_version: str = _DEFAULT_PROMPT_VERSION,
    policy_version: str = _DEFAULT_POLICY_VERSION,
    metadata: dict[str, Any] | None = None,
) -> int:
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
            "metadata": metadata or {},
        }
        for cid in content_item_ids
    ]
    return insert_screen_attempts(conn, rows)


def record_screen_failures(
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
            "error_summary": (error_summary or "screen_failed")[:2000],
            "metadata": metadata or {},
        }
        for cid in content_item_ids
    ]
    return insert_screen_attempts(conn, rows)


def latest_screen_attempts(
    conn: Connection,
    content_item_ids: Sequence[int],
    *,
    stage_version: str | None = None,
    prompt_version: str | None = None,
    policy_version: str | None = None,
    model: str | None = None,
) -> dict[int, dict[str, Any]]:
    """Latest attempt per paper, optionally filtered to a version/model tuple."""
    if not content_item_ids:
        return {}
    clauses = ["content_item_id = ANY(%s)"]
    params: list[Any] = [list(content_item_ids)]
    if stage_version is not None:
        clauses.append("stage_version = %s")
        params.append(stage_version)
    if prompt_version is not None:
        clauses.append("prompt_version = %s")
        params.append(prompt_version)
    if policy_version is not None:
        clauses.append("policy_version = %s")
        params.append(policy_version)
    if model is not None:
        clauses.append("model = %s")
        params.append(model)
    where = " AND ".join(clauses)
    with conn.cursor() as cur:
        cur.execute(
            f"""
            SELECT DISTINCT ON (content_item_id)
                content_item_id, status, error_summary, attempted_at,
                stage_version, prompt_version, policy_version, model, metadata
            FROM paper_intelligence.screen_attempts
            WHERE {where}
            ORDER BY content_item_id, attempted_at DESC
            """,
            params,
        )
        return {int(r["content_item_id"]): dict(r) for r in cur.fetchall()}
