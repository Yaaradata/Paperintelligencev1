"""Reads for the affiliation stage and append-only writes to paper_author_affiliations."""

from __future__ import annotations

from typing import Any

from psycopg import Connection

FETCH_PAPER_SQL = """
SELECT
    ci.id            AS content_item_id,
    ci.title         AS title,
    ci.raw_metadata  AS raw_metadata,
    pm.doi           AS doi,
    pm.arxiv_id      AS arxiv_id,
    pm.affiliation_text  AS affiliation_text,
    pm.extracted_emails  AS extracted_emails,
    pm.enrichment_metadata AS enrichment_metadata
FROM research_radar.content_items ci
LEFT JOIN research_radar.paper_metadata pm ON pm.content_id = ci.id
WHERE ci.id = %s
"""

LIST_AUTHORS_SQL = """
SELECT id, author_position, raw_name, normalized_name, openalex_author_id, orcid
FROM paper_intelligence.paper_authors
WHERE content_item_id = %s
ORDER BY author_position
"""

EXISTING_EVIDENCE_SQL = """
SELECT 1
FROM paper_intelligence.paper_author_affiliations
WHERE content_item_id = %s
  AND paper_author_id = %s
  AND organisation_id IS NOT DISTINCT FROM %s
  AND evidence_type = %s
  AND evidence_value IS NOT DISTINCT FROM %s
LIMIT 1
"""

INSERT_SQL = """
INSERT INTO paper_intelligence.paper_author_affiliations
    (content_item_id, paper_author_id, organisation_id, raw_affiliation,
     relationship_scope, evidence_type, evidence_source, evidence_value,
     confidence, run_id, stage_version, policy_version)
VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
RETURNING id
"""

COUNT_SQL = """
SELECT count(*) AS n
FROM paper_intelligence.paper_author_affiliations
WHERE content_item_id = %s
"""


def fetch_paper(conn: Connection, content_item_id: int) -> dict[str, Any]:
    with conn.cursor() as cur:
        cur.execute(FETCH_PAPER_SQL, (content_item_id,))
        row = cur.fetchone()
    if row is None:
        raise LookupError(f"content_item_id={content_item_id} not found")
    return row


def list_paper_authors(conn: Connection, content_item_id: int) -> list[dict[str, Any]]:
    with conn.cursor() as cur:
        cur.execute(LIST_AUTHORS_SQL, (content_item_id,))
        return list(cur.fetchall())


def count_affiliations(conn: Connection, content_item_id: int) -> int:
    with conn.cursor() as cur:
        cur.execute(COUNT_SQL, (content_item_id,))
        return int(cur.fetchone()["n"])


def insert_affiliation(
    conn: Connection,
    *,
    content_item_id: int,
    paper_author_id: int,
    organisation_id: int | None,
    raw_affiliation: str | None,
    relationship_scope: str | None,
    evidence_type: str,
    evidence_source: str,
    evidence_value: str | None,
    confidence: float | None,
    run_id: str | None,
    stage_version: str,
    policy_version: str | None,
) -> int | None:
    """Append one evidence row unless an identical one already exists.

    Dedupe key: content_item_id + paper_author_id + organisation_id +
    evidence_type + evidence_value. Returns the new row id, or None when the
    evidence was already recorded.

    When the same evidence is re-emitted with a higher confidence (e.g. after a
    stage_version bump that fixed org-on-paper semantics), upgrade the stored
    confidence in place so adjudication sees the corrected value.
    """
    with conn.cursor() as cur:
        cur.execute(
            EXISTING_EVIDENCE_SQL,
            (content_item_id, paper_author_id, organisation_id, evidence_type, evidence_value),
        )
        if cur.fetchone() is not None:
            if confidence is not None:
                cur.execute(
                    """
                    UPDATE paper_intelligence.paper_author_affiliations
                    SET confidence = %s,
                        run_id = COALESCE(%s, run_id),
                        stage_version = %s,
                        policy_version = COALESCE(%s, policy_version)
                    WHERE content_item_id = %s
                      AND paper_author_id = %s
                      AND organisation_id IS NOT DISTINCT FROM %s
                      AND evidence_type = %s
                      AND evidence_value IS NOT DISTINCT FROM %s
                      AND (confidence IS NULL OR confidence < %s)
                    """,
                    (
                        confidence,
                        run_id,
                        stage_version,
                        policy_version,
                        content_item_id,
                        paper_author_id,
                        organisation_id,
                        evidence_type,
                        evidence_value,
                        confidence,
                    ),
                )
            return None
        cur.execute(
            INSERT_SQL,
            (
                content_item_id,
                paper_author_id,
                organisation_id,
                raw_affiliation,
                relationship_scope,
                evidence_type,
                evidence_source,
                evidence_value,
                confidence,
                run_id,
                stage_version,
                policy_version,
            ),
        )
        row = cur.fetchone()
    return row["id"] if row else None
