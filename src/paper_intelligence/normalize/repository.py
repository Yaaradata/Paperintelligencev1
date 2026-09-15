"""Persist normalized authors into paper_intelligence.paper_authors."""

from __future__ import annotations

from typing import Any, Sequence

from psycopg import Connection


FETCH_AUTHORS_SQL = """
SELECT
    ci.id AS content_item_id,
    CASE
        WHEN pm.authors_raw IS NOT NULL
             AND jsonb_typeof(pm.authors_raw) = 'array'
             AND jsonb_array_length(pm.authors_raw) > 0
            THEN pm.authors_raw
        ELSE ci.authors_raw
    END AS authors_raw
FROM research_radar.content_items ci
LEFT JOIN research_radar.paper_metadata pm ON pm.content_id = ci.id
WHERE ci.id = %s
"""

UPSERT_SQL = """
INSERT INTO paper_intelligence.paper_authors (
    content_item_id, author_position, raw_name, normalized_name,
    person_id, orcid, openalex_author_id
) VALUES (
    %(content_item_id)s, %(author_position)s, %(raw_name)s, %(normalized_name)s,
    NULL, NULL, NULL
)
ON CONFLICT (content_item_id, author_position) DO UPDATE SET
    raw_name = EXCLUDED.raw_name,
    normalized_name = EXCLUDED.normalized_name,
    updated_at = NOW()
RETURNING id, (xmax = 0) AS inserted
"""

DELETE_EXTRA_SQL = """
DELETE FROM paper_intelligence.paper_authors
WHERE content_item_id = %s
  AND author_position > %s
"""

LIST_AUTHORS_SQL = """
SELECT author_position, raw_name, normalized_name, person_id, orcid, openalex_author_id
FROM paper_intelligence.paper_authors
WHERE content_item_id = %s
ORDER BY author_position
"""


def fetch_authors_raw(conn: Connection, content_item_id: int) -> Any | None:
    with conn.cursor() as cur:
        cur.execute(FETCH_AUTHORS_SQL, (content_item_id,))
        row = cur.fetchone()
    if row is None:
        raise LookupError(f"content_item_id={content_item_id} not found")
    return row["authors_raw"]


def replace_paper_authors(
    conn: Connection,
    content_item_id: int,
    rows: Sequence[dict[str, Any]],
) -> dict[str, int]:
    """Upsert author rows and drop trailing positions. Identity fields stay NULL on insert."""
    inserted = 0
    updated = 0
    with conn.cursor() as cur:
        for row in rows:
            payload = {
                "content_item_id": content_item_id,
                "author_position": row["author_position"],
                "raw_name": row["raw_name"],
                "normalized_name": row["normalized_name"],
            }
            cur.execute(UPSERT_SQL, payload)
            result = cur.fetchone()
            if result and result.get("inserted"):
                inserted += 1
            else:
                updated += 1
        cur.execute(DELETE_EXTRA_SQL, (content_item_id, len(rows)))
        deleted = cur.rowcount
    return {
        "upserted": len(rows),
        "inserted": inserted,
        "updated": updated,
        "deleted_extra": deleted,
    }


def list_paper_authors(conn: Connection, content_item_id: int) -> list[dict[str, Any]]:
    with conn.cursor() as cur:
        cur.execute(LIST_AUTHORS_SQL, (content_item_id,))
        return list(cur.fetchall())
