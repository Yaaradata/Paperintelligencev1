"""Shared-RDS writes for OAI ingest into research_radar tables.

PaperIntelligence owns the harvest stage; the tables stay in research_radar
(same RDS). Research Radar's own ingest is left untouched.
"""

from __future__ import annotations

import json
import re
from datetime import datetime, timezone
from typing import Any
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

ARXIV_RE = re.compile(
    r"(?:arxiv\.org/(?:abs|html|pdf)/|arxiv:)?"
    r"(?P<id>(?:\d{4}\.\d{4,5}|[a-z\-]+(?:\.[A-Z]{2})?/\d{7}))"
    r"(?P<version>v\d+)?",
    re.I,
)
TRACKING_PARAMS = {
    "utm_source",
    "utm_medium",
    "utm_campaign",
    "utm_term",
    "utm_content",
    "gclid",
    "fbclid",
    "mc_cid",
    "mc_eid",
}


def extract_arxiv_id(value: str | None) -> tuple[str | None, int | None]:
    if not value:
        return None, None
    match = ARXIV_RE.search(value)
    if not match:
        return None, None
    version = match.group("version")
    return match.group("id"), int(version[1:]) if version else None


def normalize_url(url: str) -> str:
    arxiv_id, _ = extract_arxiv_id(url)
    if arxiv_id and "arxiv.org" in url.lower():
        return f"https://arxiv.org/abs/{arxiv_id}"
    parts = urlsplit(url.strip())
    scheme = (parts.scheme or "https").lower()
    netloc = parts.netloc.lower()
    if netloc.startswith("www."):
        netloc = netloc[4:]
    query = [
        (key, value)
        for key, value in parse_qsl(parts.query, keep_blank_values=True)
        if key.lower() not in TRACKING_PARAMS
    ]
    return urlunsplit(
        (scheme, netloc, parts.path.rstrip("/") or "/", urlencode(query), "")
    )


def parse_iso_datetime(value: Any) -> datetime | None:
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


def upsert_item(conn: Any, item: dict[str, Any]) -> tuple[int, bool]:
    with conn.cursor() as cur:
        cur.execute(
            "SELECT id FROM research_radar.content_items WHERE canonical_url=%s LIMIT 1",
            (item["canonical_url"],),
        )
        is_new = cur.fetchone() is None
        cur.execute(
            """
            INSERT INTO research_radar.content_items(
                source_type, source, source_external_id, source_feed, canonical_url,
                title, summary, authors_raw, categories_raw, inoreader_tags,
                published_at, source_seen_at, updated_at, raw_metadata,
                status, ingested_at, modified_at
            )
            VALUES (
                %s, %s, %s, %s, %s,
                %s, %s, %s::jsonb, %s::jsonb, %s::jsonb,
                %s, %s, %s, %s::jsonb,
                'INGESTED', NOW(), NOW()
            )
            ON CONFLICT (canonical_url) DO UPDATE SET
              source_external_id = COALESCE(
                  EXCLUDED.source_external_id,
                  research_radar.content_items.source_external_id
              ),
              source_feed = COALESCE(
                  EXCLUDED.source_feed, research_radar.content_items.source_feed
              ),
              title = EXCLUDED.title,
              summary = COALESCE(
                  NULLIF(EXCLUDED.summary, ''), research_radar.content_items.summary
              ),
              authors_raw = CASE
                  WHEN EXCLUDED.authors_raw <> '[]'::jsonb THEN EXCLUDED.authors_raw
                  ELSE research_radar.content_items.authors_raw
              END,
              categories_raw = CASE
                  WHEN EXCLUDED.categories_raw <> '[]'::jsonb THEN EXCLUDED.categories_raw
                  ELSE research_radar.content_items.categories_raw
              END,
              inoreader_tags = EXCLUDED.inoreader_tags,
              published_at = COALESCE(
                  EXCLUDED.published_at, research_radar.content_items.published_at
              ),
              source_seen_at = COALESCE(
                  research_radar.content_items.source_seen_at, EXCLUDED.source_seen_at
              ),
              updated_at = COALESCE(
                  EXCLUDED.updated_at, research_radar.content_items.updated_at
              ),
              raw_metadata = EXCLUDED.raw_metadata,
              modified_at = NOW()
            RETURNING id
            """,
            (
                item["source_type"],
                item["source"],
                item.get("source_external_id"),
                item.get("source_feed"),
                item["canonical_url"],
                item["title"],
                item.get("summary"),
                json.dumps(item.get("authors_raw", [])),
                json.dumps(item.get("categories_raw", [])),
                json.dumps(item.get("inoreader_tags", [])),
                item.get("published_at"),
                item.get("source_seen_at"),
                item.get("updated_at"),
                json.dumps(item.get("raw_metadata", {}), default=str),
            ),
        )
        return int(cur.fetchone()["id"]), is_new


def ensure_paper_metadata_row(conn: Any, content_id: int) -> None:
    with conn.cursor() as cur:
        cur.execute(
            """
            INSERT INTO research_radar.paper_metadata(content_id)
            VALUES (%s)
            ON CONFLICT (content_id) DO NOTHING
            """,
            (content_id,),
        )


def affiliation_lines_from_structured(authors_structured: list[dict[str, Any]] | None) -> list[str]:
    """Flatten structured OAI affiliations into paper_metadata.affiliation_text lines."""
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


def upsert_paper_metadata(conn: Any, content_id: int, rec: dict[str, Any]) -> None:
    """Gap-fill paper_metadata from an OAI record. Never overwrites non-empty fields."""
    arxiv_id = rec["arxiv_id"]
    ensure_paper_metadata_row(conn, content_id)
    authors_structured = rec.get("authors_structured") or []
    affiliation_lines = affiliation_lines_from_structured(authors_structured)
    conn.execute(
        """
        UPDATE research_radar.paper_metadata SET
            arxiv_id = COALESCE(arxiv_id, %s),
            doi = COALESCE(doi, %s),
            abstract = CASE WHEN COALESCE(abstract, '') = '' THEN %s ELSE abstract END,
            categories = CASE WHEN categories = '[]'::jsonb THEN %s::jsonb ELSE categories END,
            authors_raw = CASE WHEN authors_raw = '[]'::jsonb THEN %s::jsonb ELSE authors_raw END,
            affiliation_text = CASE
                WHEN affiliation_text = '[]'::jsonb AND %s::jsonb <> '[]'::jsonb
                THEN %s::jsonb
                ELSE affiliation_text
            END,
            submission_date = COALESCE(submission_date, %s),
            latest_revision_date = COALESCE(latest_revision_date, %s),
            journal_reference = COALESCE(journal_reference, %s),
            paper_url = COALESCE(paper_url, %s),
            html_url = COALESCE(html_url, %s),
            pdf_url = COALESCE(pdf_url, %s),
            enrichment_metadata = enrichment_metadata || %s::jsonb,
            modified_at = NOW()
        WHERE content_id = %s
        """,
        (
            arxiv_id,
            rec.get("doi"),
            rec.get("abstract") or "",
            json.dumps(rec.get("categories") or []),
            json.dumps(rec.get("authors") or []),
            json.dumps(affiliation_lines),
            json.dumps(affiliation_lines),
            parse_iso_datetime(rec["created"]),
            parse_iso_datetime(rec["updated"]) if rec.get("updated") else None,
            rec.get("journal_ref"),
            f"https://arxiv.org/abs/{arxiv_id}",
            f"https://arxiv.org/html/{arxiv_id}",
            f"https://arxiv.org/pdf/{arxiv_id}",
            json.dumps(
                {
                    "oai_ingest": {
                        "datestamp": rec.get("datestamp"),
                        "set_spec": rec.get("_set_spec"),
                        "via": "paper_intelligence.ingest",
                        "authors_structured": authors_structured,
                    }
                }
            ),
            content_id,
        ),
    )
