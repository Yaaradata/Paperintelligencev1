"""PI-owned relevance results and current-decision projection."""

from __future__ import annotations

from typing import Any, Sequence

from psycopg import Connection

# Radar statuses mapped into keep/reject when backfilling relevance.
RELEVANCE_KEEP_STATUSES = (
    "RELEVANT",
    "ENRICHED",
    "ENTITY_RESOLVED",
    "SCORED",
    "CANDIDATE",
)
RELEVANCE_REJECT_STATUSES = ("REJECTED",)

LATEST_RELEVANCE_SQL = """
SELECT DISTINCT ON (r.paper_id)
    r.paper_id,
    r.decision,
    r.score,
    r.reason,
    r.method,
    r.stage_version,
    r.policy_version,
    r.created_at,
    r.relevance_id
FROM paper_intelligence.paper_relevance_results r
WHERE r.paper_id = ANY(%s)
ORDER BY r.paper_id, r.created_at DESC, r.relevance_id DESC
"""


def latest_relevance_decision(
    conn: Connection, paper_ids: Sequence[int]
) -> dict[int, dict[str, Any]]:
    """Map paper_id → latest relevance row."""
    if not paper_ids:
        return {}
    with conn.cursor() as cur:
        cur.execute(LATEST_RELEVANCE_SQL, (list(paper_ids),))
        return {int(row["paper_id"]): dict(row) for row in cur.fetchall()}


def current_relevance(
    conn: Connection, paper_id: int
) -> dict[str, Any] | None:
    return latest_relevance_decision(conn, [paper_id]).get(int(paper_id))


def insert_relevance_result(
    conn: Connection,
    *,
    paper_id: int,
    decision: str,
    score: float | None,
    reason: str | None,
    method: str = "deterministic",
    stage_version: str | None = None,
    prompt_version: str | None = None,
    policy_version: str | None = None,
    model: str | None = None,
    run_id: str | None = None,
) -> None:
    """Append-only native PI relevance decision."""
    with conn.cursor() as cur:
        cur.execute(
            """
            INSERT INTO paper_intelligence.paper_relevance_results
              (paper_id, decision, score, reason, method,
               stage_version, prompt_version, policy_version, model, run_id)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            """,
            (
                int(paper_id),
                decision,
                score,
                reason,
                method,
                stage_version,
                prompt_version,
                policy_version,
                model,
                run_id,
            ),
        )


def papers_with_latest_decision(
    conn: Connection,
    *,
    date_from: str,
    date_until: str,
    decision: str = "keep",
) -> list[int]:
    """Paper ids in published_at window whose latest relevance decision matches."""
    with conn.cursor() as cur:
        cur.execute(
            """
            WITH windowed AS (
              SELECT paper_id
              FROM paper_intelligence.papers
              WHERE published_at >= %s::timestamptz
                AND published_at < (%s::timestamptz + interval '1 day')
            ),
            latest AS (
              SELECT DISTINCT ON (r.paper_id)
                     r.paper_id, r.decision
              FROM paper_intelligence.paper_relevance_results r
              JOIN windowed w ON w.paper_id = r.paper_id
              ORDER BY r.paper_id, r.created_at DESC, r.relevance_id DESC
            )
            SELECT paper_id
            FROM latest
            WHERE decision = %s
            ORDER BY paper_id
            """,
            (date_from, date_until, decision),
        )
        return [int(r["paper_id"]) for r in cur.fetchall()]
