"""Shadow PI-catalog selectors (compare-only; production still uses Radar paths)."""

from __future__ import annotations

from typing import Any

from psycopg import Connection

from paper_intelligence.catalog.papers import fetch_papers_by_ids
from paper_intelligence.catalog.relevance import papers_with_latest_decision


def select_window_candidates_pi(
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
    """PI relevance keep + version-aware skip. No Radar status."""
    ids = papers_with_latest_decision(
        conn, date_from=date_from, date_until=date_until, decision="keep"
    )
    if not ids:
        return []

    if skip_done:
        done_clauses = ["r.content_item_id = ANY(%s)", "r.task_type = %s"]
        params: list[Any] = [ids, stage_task_type]
        if stage_version is not None:
            done_clauses.append("r.stage_version = %s")
            params.append(stage_version)
        if prompt_version is not None:
            done_clauses.append("r.prompt_version = %s")
            params.append(prompt_version)
        if policy_version is not None:
            done_clauses.append("r.policy_version = %s")
            params.append(policy_version)
        if model is not None:
            done_clauses.append("r.model = %s")
            params.append(model)
        done_clauses.append(
            "(r.input_content_hash IS NULL OR r.input_content_hash = p.content_hash)"
        )
        with conn.cursor() as cur:
            cur.execute(
                f"""
                SELECT DISTINCT r.content_item_id
                FROM paper_intelligence.paper_classification_results r
                LEFT JOIN paper_intelligence.papers p ON p.paper_id = r.content_item_id
                WHERE {" AND ".join(done_clauses)}
                """,
                params,
            )
            done = {int(r["content_item_id"]) for r in cur.fetchall()}
        ids = [i for i in ids if i not in done]

    if limit is not None:
        ids = ids[: int(limit)]
    return ids


def count_window_pi(conn: Connection, *, date_from: str, date_until: str) -> int:
    return len(
        papers_with_latest_decision(
            conn, date_from=date_from, date_until=date_until, decision="keep"
        )
    )


def latest_screen_scores_pi(
    conn: Connection, *, date_from: str, date_until: str
) -> list[dict[str, Any]]:
    """Latest PI screen rows for papers in the PI catalog published_at window.

    Joins paper_intelligence.papers for the date window — no Radar status filter.
    """
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
                p.published_at
            FROM paper_intelligence.paper_classification_results r
            JOIN paper_intelligence.papers p ON p.paper_id = r.content_item_id
            WHERE r.task_type = 'screen'
              AND p.published_at >= %s::timestamptz
              AND p.published_at < (%s::timestamptz + interval '1 day')
              AND (r.input_content_hash IS NULL OR r.input_content_hash = p.content_hash)
            ORDER BY r.content_item_id, r.created_at DESC
            """,
            (date_from, date_until),
        )
        return list(cur.fetchall())


def fetch_papers_shadow(conn: Connection, content_item_ids: list[int]) -> list[dict[str, Any]]:
    return fetch_papers_by_ids(conn, content_item_ids)


def compare_id_sets(old_ids: list[int], new_ids: list[int]) -> dict[str, Any]:
    old_set, new_set = set(old_ids), set(new_ids)
    return {
        "old_count": len(old_ids),
        "new_count": len(new_ids),
        "intersection": len(old_set & new_set),
        "old_only_count": len(old_set - new_set),
        "new_only_count": len(new_set - old_set),
        "old_only_sample": sorted(old_set - new_set)[:25],
        "new_only_sample": sorted(new_set - old_set)[:25],
    }
