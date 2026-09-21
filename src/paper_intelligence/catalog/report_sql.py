"""Shared SQL fragments for report/editorial date-window paper joins.

When ``PI_USE_PAPERS_CATALOG`` is on, join ``paper_intelligence.papers``.
When off, join Radar ``content_items`` (legacy rollback).
"""

from __future__ import annotations

from paper_intelligence.common.config import PI_USE_PAPERS_CATALOG


def paper_window_from_alias(alias: str = "p") -> str:
    """FROM clause for papers in a published_at window (params: from, until)."""
    if PI_USE_PAPERS_CATALOG:
        return f"""
        paper_intelligence.papers {alias}
        WHERE {alias}.published_at >= %s::timestamptz
          AND {alias}.published_at < (%s::timestamptz + interval '1 day')
        """
    return f"""
        research_radar.content_items {alias}
        WHERE {alias}.published_at >= %s::timestamptz
          AND {alias}.published_at < (%s::timestamptz + interval '1 day')
        """


def paper_id_expr(alias: str = "p") -> str:
    return f"{alias}.paper_id" if PI_USE_PAPERS_CATALOG else f"{alias}.id"


def join_results_to_window(
    results_alias: str = "r",
    paper_alias: str = "p",
) -> str:
    """JOIN paper table onto classification/current rows by id + date window."""
    pid = paper_id_expr(paper_alias)
    table = (
        "paper_intelligence.papers"
        if PI_USE_PAPERS_CATALOG
        else "research_radar.content_items"
    )
    return f"""
        JOIN {table} {paper_alias}
          ON {pid} = {results_alias}.content_item_id
         AND {paper_alias}.published_at >= %s::timestamptz
         AND {paper_alias}.published_at < (%s::timestamptz + interval '1 day')
    """


def funnel_sql() -> str:
    if PI_USE_PAPERS_CATALOG:
        return """
        SELECT
            COUNT(*) AS ingested,
            COUNT(*) FILTER (WHERE lr.decision = 'reject') AS relevance_rejected,
            COUNT(*) FILTER (
              WHERE lr.decision = 'keep' OR lr.decision IS NULL
            ) AS relevance_kept
        FROM paper_intelligence.papers p
        LEFT JOIN LATERAL (
          SELECT decision FROM paper_intelligence.paper_relevance_results r
          WHERE r.paper_id = p.paper_id
          ORDER BY r.created_at DESC, r.relevance_id DESC
          LIMIT 1
        ) lr ON TRUE
        WHERE p.published_at >= %s::timestamptz
          AND p.published_at < (%s::timestamptz + interval '1 day')
        """
    return """
        SELECT
            COUNT(*) AS ingested,
            COUNT(*) FILTER (WHERE status = 'REJECTED') AS relevance_rejected,
            COUNT(*) FILTER (WHERE status <> 'REJECTED') AS relevance_kept
        FROM research_radar.content_items
        WHERE published_at >= %s::timestamptz
          AND published_at < (%s::timestamptz + interval '1 day')
        """
