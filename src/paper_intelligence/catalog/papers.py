"""Read helpers for paper_intelligence.papers (shadow-capable)."""

from __future__ import annotations

from typing import Any, Sequence

from psycopg import Connection

from paper_intelligence.catalog.normalize import normalize_arxiv_id, normalize_doi

PAPER_FIELDS_SQL = """
SELECT
    p.paper_id AS content_item_id,
    p.paper_id,
    p.legacy_content_item_id,
    p.title,
    COALESCE(p.abstract, p.summary, '') AS abstract,
    COALESCE(p.categories, '[]'::jsonb) AS categories,
    p.published_at,
    p.arxiv_id,
    p.doi,
    p.canonical_url,
    p.source,
    p.source_external_id
FROM paper_intelligence.papers p
WHERE p.paper_id = ANY(%s)
ORDER BY p.paper_id
"""


def fetch_papers_by_ids(
    conn: Connection, paper_ids: Sequence[int]
) -> list[dict[str, Any]]:
    """Fetch catalog rows shaped like legacy fetch_papers (content_item_id alias)."""
    if not paper_ids:
        return []
    with conn.cursor() as cur:
        cur.execute(PAPER_FIELDS_SQL, (list(paper_ids),))
        return list(cur.fetchall())


def resolve_paper_id(
    conn: Connection,
    *,
    paper_id: int | None = None,
    legacy_content_item_id: int | None = None,
    arxiv_id: str | None = None,
    doi: str | None = None,
) -> int | None:
    """Resolve a PI paper_id from identity hints."""
    if paper_id is not None:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT paper_id FROM paper_intelligence.papers WHERE paper_id = %s",
                (int(paper_id),),
            )
            row = cur.fetchone()
            return int(row["paper_id"]) if row else None

    if legacy_content_item_id is not None:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT paper_id FROM paper_intelligence.papers
                WHERE legacy_content_item_id = %s OR paper_id = %s
                LIMIT 1
                """,
                (int(legacy_content_item_id), int(legacy_content_item_id)),
            )
            row = cur.fetchone()
            return int(row["paper_id"]) if row else None

    norm_arxiv = normalize_arxiv_id(arxiv_id)
    if norm_arxiv:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT paper_id FROM paper_intelligence.papers WHERE arxiv_id = %s",
                (norm_arxiv,),
            )
            row = cur.fetchone()
            if row:
                return int(row["paper_id"])
            cur.execute(
                """
                SELECT paper_id FROM paper_intelligence.paper_identity_map
                WHERE system = 'arxiv' AND external_id = %s
                """,
                (norm_arxiv,),
            )
            row = cur.fetchone()
            return int(row["paper_id"]) if row else None

    norm_doi = normalize_doi(doi)
    if norm_doi:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT paper_id FROM paper_intelligence.papers WHERE doi = %s",
                (norm_doi,),
            )
            row = cur.fetchone()
            return int(row["paper_id"]) if row else None

    return None
