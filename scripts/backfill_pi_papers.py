#!/usr/bin/env python3
"""Backfill paper_intelligence.papers + identity_map + relevance from Radar.

Additive only. No paid LLM. No Radar DDL. No production cutover.

Example:
  PYTHONPATH=src python3 scripts/backfill_pi_papers.py --apply
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from paper_intelligence.catalog.normalize import (
    extract_arxiv_version,
    normalize_arxiv_id,
    normalize_doi,
)
from paper_intelligence.catalog.relevance import (
    RELEVANCE_KEEP_STATUSES,
    RELEVANCE_REJECT_STATUSES,
)
from paper_intelligence.db import connect

REFS_SQL = """
SELECT DISTINCT id FROM (
  SELECT content_item_id AS id FROM paper_intelligence.paper_classification_results
  UNION SELECT content_item_id FROM paper_intelligence.paper_intelligence_current
  UNION SELECT content_item_id FROM paper_intelligence.paper_authors
  UNION SELECT content_item_id FROM paper_intelligence.paper_author_affiliations
  UNION SELECT content_item_id FROM paper_intelligence.papers_people
  UNION SELECT content_item_id FROM paper_intelligence.paper_hf_signals
  UNION SELECT content_item_id FROM paper_intelligence.item_stage_runs
  UNION SELECT content_item_id FROM paper_intelligence.golden_set_items
  UNION SELECT content_item_id FROM paper_intelligence.evaluation_results
) u
WHERE id IS NOT NULL
"""

SOURCE_SQL = """
SELECT
  ci.id AS legacy_content_item_id,
  ci.source,
  ci.source_type,
  ci.source_external_id,
  ci.canonical_url,
  ci.title,
  ci.summary,
  ci.authors_raw AS ci_authors_raw,
  ci.categories_raw,
  ci.published_at,
  ci.updated_at AS source_updated_at,
  ci.ingested_at,
  ci.raw_metadata AS ci_raw_metadata,
  ci.status,
  ci.created_at,
  ci.modified_at,
  pm.arxiv_id AS raw_arxiv_id,
  pm.arxiv_version,
  pm.doi AS raw_doi,
  pm.abstract,
  pm.categories AS pm_categories,
  pm.authors_raw AS pm_authors_raw,
  pm.affiliation_text,
  pm.extracted_emails,
  pm.enrichment_metadata,
  pm.submission_date,
  pm.latest_revision_date,
  cs.ai_relevance,
  cs.scoring_reason
FROM research_radar.content_items ci
LEFT JOIN research_radar.paper_metadata pm ON pm.content_id = ci.id
LEFT JOIN research_radar.content_scores cs ON cs.content_id = ci.id
WHERE ci.id = ANY(%s)
ORDER BY ci.id
"""


def _categories(row: dict) -> list | dict:
    cats = row.get("pm_categories")
    if cats in (None, [], {}, "[]"):
        cats = row.get("categories_raw")
    return cats if cats is not None else []


def _authors(row: dict):
    return row.get("pm_authors_raw") if row.get("pm_authors_raw") is not None else row.get("ci_authors_raw")


def backfill(conn, *, apply: bool) -> dict:
    with conn.cursor() as cur:
        cur.execute(REFS_SQL)
        ids = [int(r["id"]) for r in cur.fetchall()]
        cur.execute(SOURCE_SQL, (ids,))
        rows = [dict(r) for r in cur.fetchall()]

    inserted = 0
    identity_rows = 0
    relevance_rows = 0
    skipped_no_title = 0
    errors: list[str] = []

    if not apply:
        return {
            "mode": "dry-run",
            "candidate_ids": len(ids),
            "source_rows": len(rows),
            "would_insert_papers": len(rows),
        }

    with conn.cursor() as cur:
        for row in rows:
            legacy_id = int(row["legacy_content_item_id"])
            title = (row.get("title") or "").strip()
            if not title:
                skipped_no_title += 1
                title = f"[untitled legacy_content_item_id={legacy_id}]"

            raw_arxiv = row.get("raw_arxiv_id")
            arxiv_id = normalize_arxiv_id(raw_arxiv)
            arxiv_version = row.get("arxiv_version")
            if arxiv_version is None:
                arxiv_version = extract_arxiv_version(raw_arxiv)
            doi = normalize_doi(row.get("raw_doi"))

            source = row.get("source") or "unknown"
            source_external_id = row.get("source_external_id")
            # Avoid unique (source, source_external_id) collisions when external id null:
            # Postgres UNIQUE allows multiple NULLs; fine.

            raw_metadata = {
                "backfill": True,
                "legacy_status": row.get("status"),
                "content_items_raw_metadata": row.get("ci_raw_metadata") or {},
                "enrichment_metadata": row.get("enrichment_metadata") or {},
                "raw_arxiv_id": raw_arxiv,
                "raw_doi": row.get("raw_doi"),
                "submission_date": str(row["submission_date"]) if row.get("submission_date") else None,
                "latest_revision_date": str(row["latest_revision_date"])
                if row.get("latest_revision_date")
                else None,
            }

            try:
                cur.execute("SAVEPOINT paper_row")
                cur.execute(
                    """
                    INSERT INTO paper_intelligence.papers (
                      paper_id, legacy_content_item_id, arxiv_id, arxiv_version, doi,
                      source, source_external_id, source_type, canonical_url,
                      title, abstract, summary, categories, authors_raw,
                      affiliation_text, extracted_emails,
                      published_at, source_updated_at, ingested_at, raw_metadata,
                      created_at, modified_at
                    ) OVERRIDING SYSTEM VALUE
                    VALUES (
                      %s, %s, %s, %s, %s,
                      %s, %s, %s, %s,
                      %s, %s, %s, %s::jsonb, %s::jsonb,
                      %s::jsonb, %s::jsonb,
                      %s, %s, COALESCE(%s, NOW()), %s::jsonb,
                      COALESCE(%s, NOW()), COALESCE(%s, NOW())
                    )
                    ON CONFLICT (paper_id) DO NOTHING
                    """,
                    (
                        legacy_id,
                        legacy_id,
                        arxiv_id,
                        arxiv_version,
                        doi,
                        source,
                        source_external_id,
                        row.get("source_type"),
                        row.get("canonical_url"),
                        title,
                        row.get("abstract"),
                        row.get("summary"),
                        json.dumps(_categories(row), default=str),
                        json.dumps(_authors(row), default=str) if _authors(row) is not None else None,
                        json.dumps(row.get("affiliation_text"), default=str)
                        if row.get("affiliation_text") is not None
                        else None,
                        json.dumps(row.get("extracted_emails"), default=str)
                        if row.get("extracted_emails") is not None
                        else None,
                        row.get("published_at"),
                        row.get("source_updated_at"),
                        row.get("ingested_at"),
                        json.dumps(raw_metadata, default=str),
                        row.get("created_at"),
                        row.get("modified_at"),
                    ),
                )
                if cur.rowcount:
                    inserted += 1

                identity_pairs = [("research_radar", str(legacy_id))]
                if arxiv_id:
                    identity_pairs.append(("arxiv", arxiv_id))
                if doi:
                    identity_pairs.append(("doi", doi))
                for system, external in identity_pairs:
                    cur.execute(
                        """
                        INSERT INTO paper_intelligence.paper_identity_map
                          (paper_id, system, external_id)
                        VALUES (%s, %s, %s)
                        ON CONFLICT (system, external_id) DO NOTHING
                        """,
                        (legacy_id, system, external),
                    )
                    if cur.rowcount:
                        identity_rows += 1

                status = row.get("status")
                decision = None
                if status in RELEVANCE_KEEP_STATUSES:
                    decision = "keep"
                elif status in RELEVANCE_REJECT_STATUSES:
                    decision = "reject"
                if decision:
                    score = (
                        float(row["ai_relevance"])
                        if row.get("ai_relevance") is not None
                        else None
                    )
                    reason = f"migrated_from_radar_status={status}"
                    cur.execute(
                        """
                        INSERT INTO paper_intelligence.paper_relevance_results
                          (paper_id, decision, score, reason, method,
                           stage_version, policy_version)
                        VALUES (%s, %s, %s, %s, 'migrated_legacy_state', 'v001', 'v001')
                        """,
                        (legacy_id, decision, score, reason),
                    )
                    relevance_rows += 1
                cur.execute("RELEASE SAVEPOINT paper_row")
            except Exception as exc:  # noqa: BLE001
                cur.execute("ROLLBACK TO SAVEPOINT paper_row")
                errors.append(f"id={legacy_id}: {type(exc).__name__}: {exc}")
                continue
        # Sequence above global max content_item_id to avoid dual-write collisions
        cur.execute("SELECT COALESCE(MAX(paper_id), 0) AS m FROM paper_intelligence.papers")
        max_paper = int(cur.fetchone()["m"])
        cur.execute("SELECT COALESCE(MAX(id), 0) AS m FROM research_radar.content_items")
        max_ci = int(cur.fetchone()["m"])
        next_id = max(max_paper, max_ci) + 1
        cur.execute(
            """
            SELECT setval(
              pg_get_serial_sequence('paper_intelligence.papers', 'paper_id'),
              %s,
              false
            )
            """,
            (next_id,),
        )
        conn.commit()

    return {
        "mode": "apply",
        "candidate_ids": len(ids),
        "source_rows": len(rows),
        "papers_inserted": inserted,
        "identity_map_rows_inserted": identity_rows,
        "relevance_rows_inserted": relevance_rows,
        "skipped_no_title": skipped_no_title,
        "sequence_next_paper_id": next_id,
        "errors": errors[:50],
        "error_count": len(errors),
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--apply", action="store_true", help="Write rows (default dry-run)")
    args = parser.parse_args(argv)
    with connect() as conn:
        report = backfill(conn, apply=args.apply)
    print(json.dumps(report, indent=2, default=str))
    return 1 if report.get("error_count") else 0


if __name__ == "__main__":
    raise SystemExit(main())
