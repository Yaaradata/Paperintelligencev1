"""PI-authoritative paper ingest helpers (catalog mode).

Writes ``paper_intelligence.papers`` first. Radar dual-write is optional and
must never roll back a successful PI upsert.
"""

from __future__ import annotations

import json
import logging
from datetime import date, datetime, timezone
from typing import Any

from paper_intelligence.catalog.normalize import (
    extract_arxiv_version,
    normalize_arxiv_id,
    normalize_doi,
)
from paper_intelligence.common.content_hash import compute_content_hash

log = logging.getLogger("paper_intelligence.catalog.ingest")

SOURCE_ARXIV_OAI = "arxiv_oai"


def _parse_dt(value: Any) -> datetime | None:
    if value is None:
        return None
    if isinstance(value, datetime):
        return value if value.tzinfo else value.replace(tzinfo=timezone.utc)
    if isinstance(value, str):
        text = value.strip()
        if not text:
            return None
        try:
            if text.endswith("Z"):
                text = text[:-1] + "+00:00"
            dt = datetime.fromisoformat(text)
            return dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)
        except ValueError:
            return None
    return None


def _affiliation_lines(authors_structured: list[dict[str, Any]] | None) -> list[str]:
    lines: list[str] = []
    seen: set[str] = set()
    for author in authors_structured or []:
        for aff in author.get("affiliations") or []:
            text = " ".join(str(aff).split())
            if not text:
                continue
            key = text.casefold()
            if key in seen:
                continue
            seen.add(key)
            lines.append(f"Affiliation: {text}")
    return lines


def find_existing_paper_id(
    conn: Any,
    *,
    arxiv_id: str | None,
    doi: str | None,
    source: str,
    source_external_id: str | None,
) -> int | None:
    """Resolve canonical PI paper_id without creating duplicates."""
    with conn.cursor() as cur:
        if arxiv_id:
            cur.execute(
                """
                SELECT paper_id FROM paper_intelligence.papers
                WHERE arxiv_id = %s
                LIMIT 1
                """,
                (arxiv_id,),
            )
            row = cur.fetchone()
            if row:
                return int(row["paper_id"])
            cur.execute(
                """
                SELECT paper_id FROM paper_intelligence.paper_identity_map
                WHERE system = 'arxiv' AND external_id = %s
                LIMIT 1
                """,
                (arxiv_id,),
            )
            row = cur.fetchone()
            if row:
                return int(row["paper_id"])
        if doi:
            cur.execute(
                """
                SELECT paper_id FROM paper_intelligence.papers
                WHERE doi = %s
                LIMIT 1
                """,
                (doi,),
            )
            row = cur.fetchone()
            if row:
                return int(row["paper_id"])
        if source_external_id:
            cur.execute(
                """
                SELECT paper_id FROM paper_intelligence.papers
                WHERE source = %s AND source_external_id = %s
                LIMIT 1
                """,
                (source, source_external_id),
            )
            row = cur.fetchone()
            if row:
                return int(row["paper_id"])
    return None


def upsert_paper_from_oai(
    conn: Any,
    rec: dict[str, Any],
    *,
    set_spec: str | None = None,
) -> tuple[int, bool]:
    """Insert or update a PI catalog paper from an OAI record.

    Identity: normalized arXiv id (no vN) is canonical. Version is stored
    separately. DOI normalized. ``published_at`` preserved on rediscovery.
    Returns ``(paper_id, is_new)``.
    """
    raw_arxiv = rec.get("arxiv_id") or ""
    arxiv_id = normalize_arxiv_id(raw_arxiv)
    arxiv_version = extract_arxiv_version(raw_arxiv)
    if arxiv_version is None:
        # OAI id field is usually bare; version may appear only in URL paths.
        arxiv_version = extract_arxiv_version(rec.get("identifier"))
    doi = normalize_doi(rec.get("doi"))
    source_external_id = rec.get("identifier")
    published_at = _parse_dt(rec.get("created"))
    source_updated_at = _parse_dt(rec.get("updated")) if rec.get("updated") else None
    authors_structured = rec.get("authors_structured") or []
    affiliation_lines = _affiliation_lines(authors_structured)
    categories = rec.get("categories") or []
    authors = rec.get("authors") or []
    title = (rec.get("title") or "(untitled)").strip() or "(untitled)"
    abstract = rec.get("abstract") or ""
    content_hash = compute_content_hash(title, abstract)
    canonical_url = (
        f"https://arxiv.org/abs/{arxiv_id}" if arxiv_id else None
    )
    raw_metadata = {
        "oai_identifier": source_external_id,
        "datestamp": rec.get("datestamp"),
        "created": rec.get("created"),
        "updated": rec.get("updated"),
        "categories": categories,
        "authors": authors,
        "authors_structured": authors_structured,
        "doi": rec.get("doi"),
        "journal_ref": rec.get("journal_ref"),
        "title": rec.get("title"),
        "abstract": abstract,
        "set_spec": set_spec,
        "ingested_by": "paper_intelligence.catalog.ingest",
    }

    existing_id = find_existing_paper_id(
        conn,
        arxiv_id=arxiv_id,
        doi=doi,
        source=SOURCE_ARXIV_OAI,
        source_external_id=source_external_id,
    )

    with conn.cursor() as cur:
        if existing_id is not None:
            cur.execute(
                """
                SELECT content_hash, arxiv_version
                FROM paper_intelligence.papers
                WHERE paper_id = %s
                """,
                (existing_id,),
            )
            prev = cur.fetchone() or {}
            previous_hash = prev.get("content_hash")

            cur.execute(
                """
                UPDATE paper_intelligence.papers SET
                    arxiv_id = COALESCE(%s, arxiv_id),
                    arxiv_version = CASE
                        WHEN %s::integer IS NULL THEN arxiv_version
                        WHEN arxiv_version IS NULL THEN %s::integer
                        WHEN %s::integer > arxiv_version THEN %s::integer
                        ELSE arxiv_version
                    END,
                    doi = COALESCE(%s, doi),
                    source_external_id = COALESCE(%s, source_external_id),
                    canonical_url = COALESCE(%s, canonical_url),
                    title = %s,
                    abstract = CASE
                        WHEN COALESCE(%s, '') <> '' THEN %s
                        ELSE abstract
                    END,
                    summary = CASE
                        WHEN COALESCE(%s, '') <> '' THEN %s
                        ELSE summary
                    END,
                    categories = CASE
                        WHEN %s::jsonb <> '[]'::jsonb THEN %s::jsonb
                        ELSE categories
                    END,
                    authors_raw = CASE
                        WHEN %s::jsonb <> '[]'::jsonb THEN %s::jsonb
                        ELSE authors_raw
                    END,
                    authors_structured = CASE
                        WHEN %s::jsonb <> '[]'::jsonb THEN %s::jsonb
                        ELSE authors_structured
                    END,
                    affiliation_text = CASE
                        WHEN affiliation_text = '[]'::jsonb
                             AND %s::jsonb <> '[]'::jsonb
                        THEN %s::jsonb
                        ELSE affiliation_text
                    END,
                    published_at = COALESCE(published_at, %s),
                    source_updated_at = COALESCE(%s, source_updated_at),
                    raw_metadata = raw_metadata || %s::jsonb,
                    content_hash = %s,
                    modified_at = NOW()
                WHERE paper_id = %s
                RETURNING paper_id, content_hash, arxiv_version
                """,
                (
                    arxiv_id,
                    arxiv_version,
                    arxiv_version,
                    arxiv_version,
                    arxiv_version,
                    doi,
                    source_external_id,
                    canonical_url,
                    title,
                    abstract,
                    abstract,
                    abstract,
                    abstract,
                    json.dumps(categories),
                    json.dumps(categories),
                    json.dumps(authors),
                    json.dumps(authors),
                    json.dumps(authors_structured),
                    json.dumps(authors_structured),
                    json.dumps(affiliation_lines),
                    json.dumps(affiliation_lines),
                    published_at,
                    source_updated_at,
                    json.dumps(raw_metadata, default=str),
                    content_hash,
                    existing_id,
                ),
            )
            updated = cur.fetchone()
            paper_id = int(updated["paper_id"])
            is_new = False
            # Recompute hash from stored title/abstract when abstract was empty
            # in the feed (UPDATE keeps prior abstract).
            cur.execute(
                """
                SELECT title, abstract, content_hash, arxiv_version
                FROM paper_intelligence.papers WHERE paper_id = %s
                """,
                (paper_id,),
            )
            stored = cur.fetchone()
            final_hash = compute_content_hash(stored.get("title"), stored.get("abstract"))
            if stored.get("content_hash") != final_hash:
                cur.execute(
                    """
                    UPDATE paper_intelligence.papers
                    SET content_hash = %s, modified_at = NOW()
                    WHERE paper_id = %s
                    """,
                    (final_hash, paper_id),
                )
            if previous_hash != final_hash:
                cur.execute(
                    """
                    INSERT INTO paper_intelligence.paper_content_hash_changes
                        (paper_id, previous_hash, new_hash, arxiv_version, source, metadata)
                    VALUES (%s, %s, %s, %s, %s, %s::jsonb)
                    """,
                    (
                        paper_id,
                        previous_hash,
                        final_hash,
                        stored.get("arxiv_version"),
                        SOURCE_ARXIV_OAI,
                        json.dumps(
                            {
                                "oai_identifier": source_external_id,
                                "datestamp": rec.get("datestamp"),
                            },
                            default=str,
                        ),
                    ),
                )
        else:
            cur.execute(
                """
                INSERT INTO paper_intelligence.papers (
                    arxiv_id, arxiv_version, doi, source, source_external_id,
                    source_type, canonical_url, title, abstract, summary,
                    categories, authors_raw, authors_structured, affiliation_text,
                    published_at, source_updated_at, raw_metadata, content_hash
                ) VALUES (
                    %s, %s::integer, %s, %s, %s,
                    %s, %s, %s, %s, %s,
                    %s::jsonb, %s::jsonb, %s::jsonb, %s::jsonb,
                    %s, %s, %s::jsonb, %s
                )
                RETURNING paper_id
                """,
                (
                    arxiv_id,
                    arxiv_version,
                    doi,
                    SOURCE_ARXIV_OAI,
                    source_external_id,
                    "arxiv",
                    canonical_url,
                    title,
                    abstract,
                    abstract,
                    json.dumps(categories),
                    json.dumps(authors),
                    json.dumps(authors_structured),
                    json.dumps(affiliation_lines),
                    published_at,
                    source_updated_at,
                    json.dumps(raw_metadata, default=str),
                    content_hash,
                ),
            )
            paper_id = int(cur.fetchone()["paper_id"])
            is_new = True

        if arxiv_id:
            cur.execute(
                """
                INSERT INTO paper_intelligence.paper_identity_map
                    (paper_id, system, external_id)
                VALUES (%s, 'arxiv', %s)
                ON CONFLICT (system, external_id) DO UPDATE SET
                    paper_id = EXCLUDED.paper_id
                """,
                (paper_id, arxiv_id),
            )
        if doi:
            cur.execute(
                """
                INSERT INTO paper_intelligence.paper_identity_map
                    (paper_id, system, external_id)
                VALUES (%s, 'doi', %s)
                ON CONFLICT (system, external_id) DO UPDATE SET
                    paper_id = EXCLUDED.paper_id
                """,
                (paper_id, doi),
            )

    return paper_id, is_new


def link_legacy_content_item(conn: Any, paper_id: int, content_item_id: int) -> None:
    """Best-effort crosswalk after a successful Radar compatibility write."""
    with conn.cursor() as cur:
        cur.execute(
            """
            UPDATE paper_intelligence.papers
            SET legacy_content_item_id = COALESCE(legacy_content_item_id, %s),
                modified_at = NOW()
            WHERE paper_id = %s
              AND (legacy_content_item_id IS NULL OR legacy_content_item_id = %s)
            """,
            (content_item_id, paper_id, content_item_id),
        )
        cur.execute(
            """
            INSERT INTO paper_intelligence.paper_identity_map
                (paper_id, system, external_id)
            VALUES (%s, 'research_radar', %s)
            ON CONFLICT (system, external_id) DO UPDATE SET
                paper_id = EXCLUDED.paper_id
            """,
            (paper_id, str(content_item_id)),
        )


def checkpoint_status_pi(
    conn: Any, source: str, set_spec: str, window_from: date, window_until: date
) -> str | None:
    row = conn.execute(
        """
        SELECT status FROM paper_intelligence.ingest_checkpoints
        WHERE source=%s AND set_spec=%s AND window_from=%s AND window_until=%s
        ORDER BY started_at DESC, checkpoint_id DESC
        LIMIT 1
        """,
        (source, set_spec, window_from, window_until),
    ).fetchone()
    return row["status"] if row else None


def start_checkpoint_pi(
    conn: Any, source: str, set_spec: str, window_from: date, window_until: date
) -> int:
    existing = conn.execute(
        """
        SELECT checkpoint_id FROM paper_intelligence.ingest_checkpoints
        WHERE source=%s AND set_spec=%s AND window_from=%s AND window_until=%s
        ORDER BY started_at DESC, checkpoint_id DESC
        LIMIT 1
        """,
        (source, set_spec, window_from, window_until),
    ).fetchone()
    if existing:
        conn.execute(
            """
            UPDATE paper_intelligence.ingest_checkpoints
            SET status='RUNNING', started_at=NOW(), ended_at=NULL, error=NULL,
                records_seen=0, records_kept=0, records_new=0, records_dupe=0
            WHERE checkpoint_id=%s
            """,
            (int(existing["checkpoint_id"]),),
        )
        return int(existing["checkpoint_id"])
    row = conn.execute(
        """
        INSERT INTO paper_intelligence.ingest_checkpoints
            (source, set_spec, window_from, window_until, status, started_at)
        VALUES (%s, %s, %s, %s, 'RUNNING', NOW())
        RETURNING checkpoint_id
        """,
        (source, set_spec, window_from, window_until),
    ).fetchone()
    return int(row["checkpoint_id"])


def finish_checkpoint_pi(
    conn: Any,
    checkpoint_id: int,
    *,
    status: str,
    records_seen: int = 0,
    records_kept: int = 0,
    records_new: int = 0,
    records_dupe: int = 0,
    error: str | None = None,
    metadata: dict[str, Any] | None = None,
) -> None:
    conn.execute(
        """
        UPDATE paper_intelligence.ingest_checkpoints
        SET status=%s, records_seen=%s, records_kept=%s, records_new=%s,
            records_dupe=%s, error=%s, ended_at=NOW(),
            metadata = COALESCE(metadata, '{}'::jsonb) || %s::jsonb
        WHERE checkpoint_id=%s
        """,
        (
            status,
            records_seen,
            records_kept,
            records_new,
            records_dupe,
            error,
            json.dumps(metadata or {}),
            checkpoint_id,
        ),
    )
