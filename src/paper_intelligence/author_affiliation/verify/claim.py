"""Atomic work claims for affiliation verification (FOR UPDATE SKIP LOCKED)."""

from __future__ import annotations

import json
import os
from datetime import datetime, timedelta, timezone
from typing import Any, Sequence

VERIFICATION_VERSION_DEFAULT = os.getenv(
    "AFFILIATION_VERIFY_VERSION", "html-oa-v001"
)

# Running claims older than this are treated as abandoned and retryable.
STALE_RUNNING_MINUTES = int(os.getenv("AFFILIATION_VERIFY_STALE_MINUTES", "20"))


def _now() -> datetime:
    return datetime.now(timezone.utc)


def enqueue_papers(
    conn: Any,
    paper_ids: Sequence[int],
    *,
    verification_version: str = VERIFICATION_VERSION_DEFAULT,
) -> int:
    """Insert pending rows for papers not yet enrolled. Returns newly inserted count."""
    if not paper_ids:
        return 0
    inserted = 0
    with conn.cursor() as cur:
        for pid in paper_ids:
            cur.execute(
                """
                INSERT INTO paper_intelligence.affiliation_verifications
                    (paper_id, verification_version, status)
                VALUES (%s, %s, 'pending')
                ON CONFLICT (verification_version, paper_id) DO NOTHING
                RETURNING verification_id
                """,
                (int(pid), verification_version),
            )
            if cur.fetchone():
                inserted += 1
    conn.commit()
    return inserted


def reclaim_stale(
    conn: Any,
    *,
    verification_version: str = VERIFICATION_VERSION_DEFAULT,
    stale_minutes: int = STALE_RUNNING_MINUTES,
) -> int:
    """Reset abandoned running claims to pending so they can be reclaimed."""
    cutoff = _now() - timedelta(minutes=stale_minutes)
    with conn.cursor() as cur:
        cur.execute(
            """
            UPDATE paper_intelligence.affiliation_verifications
            SET status = 'pending',
                worker_id = NULL,
                claimed_at = NULL,
                started_at = NULL,
                error = COALESCE(error, '') || CASE
                    WHEN error IS NULL OR error = '' THEN 'stale_reclaim'
                    ELSE '; stale_reclaim'
                END,
                modified_at = NOW()
            WHERE verification_version = %s
              AND status = 'running'
              AND COALESCE(started_at, claimed_at) < %s
            """,
            (verification_version, cutoff),
        )
        n = cur.rowcount
    conn.commit()
    return int(n or 0)


def claim_batch(
    conn: Any,
    *,
    worker_id: str,
    limit: int = 1,
    verification_version: str = VERIFICATION_VERSION_DEFAULT,
) -> list[dict[str, Any]]:
    """Atomically claim up to ``limit`` pending rows for this worker.

    Uses FOR UPDATE SKIP LOCKED so concurrent workers never take the same paper.
    Each (verification_version, paper_id) is processed at most once per successful complete.
    """
    if limit < 1:
        return []
    with conn.cursor() as cur:
        cur.execute(
            """
            WITH picked AS (
                SELECT verification_id
                FROM paper_intelligence.affiliation_verifications
                WHERE verification_version = %s
                  AND status IN ('pending', 'failed')
                ORDER BY
                    CASE status WHEN 'pending' THEN 0 ELSE 1 END,
                    verification_id
                FOR UPDATE SKIP LOCKED
                LIMIT %s
            )
            UPDATE paper_intelligence.affiliation_verifications v
            SET status = 'running',
                worker_id = %s,
                claimed_at = NOW(),
                started_at = NOW(),
                attempt_count = attempt_count + 1,
                error = NULL,
                modified_at = NOW()
            FROM picked
            WHERE v.verification_id = picked.verification_id
            RETURNING v.verification_id, v.paper_id, v.verification_version,
                      v.attempt_count, v.status
            """,
            (verification_version, int(limit), worker_id),
        )
        rows = [dict(r) for r in cur.fetchall()]
    conn.commit()
    return rows


def mark_complete(
    conn: Any,
    verification_id: int,
    *,
    outcome: str,
    result_json: dict[str, Any],
) -> None:
    with conn.cursor() as cur:
        cur.execute(
            """
            UPDATE paper_intelligence.affiliation_verifications
            SET status = 'complete',
                outcome = %s,
                result_json = %s::jsonb,
                completed_at = NOW(),
                error = NULL,
                modified_at = NOW()
            WHERE verification_id = %s
              AND status = 'running'
            """,
            (
                outcome,
                json.dumps(result_json, default=str),
                int(verification_id),
            ),
        )
    conn.commit()


def mark_failed(
    conn: Any,
    verification_id: int,
    *,
    error: str,
    result_json: dict[str, Any] | None = None,
) -> None:
    with conn.cursor() as cur:
        cur.execute(
            """
            UPDATE paper_intelligence.affiliation_verifications
            SET status = 'failed',
                error = %s,
                result_json = COALESCE(%s::jsonb, result_json),
                completed_at = NOW(),
                modified_at = NOW()
            WHERE verification_id = %s
              AND status = 'running'
            """,
            (
                (error or "failed")[:2000],
                json.dumps(result_json or {}, default=str),
                int(verification_id),
            ),
        )
    conn.commit()


def counts_by_status(
    conn: Any, *, verification_version: str = VERIFICATION_VERSION_DEFAULT
) -> dict[str, int]:
    rows = conn.execute(
        """
        SELECT status, count(*) n
        FROM paper_intelligence.affiliation_verifications
        WHERE verification_version = %s
        GROUP BY status
        """,
        (verification_version,),
    ).fetchall()
    return {str(r["status"]): int(r["n"]) for r in rows}
