#!/usr/bin/env python3
"""Backfill missing in-scope Radar arXiv papers into paper_intelligence.papers.

Identity/metadata only. No paid stages.

- Papers with Radar keep/reject lifecycle statuses get migrated_legacy_state
  relevance (same mapping as the original enrichment-ref backfill).
- INGESTED / other pre-decision statuses get NO relevance row (discoverable
  later by PI-native relevance candidate selection).

Example:
  PYTHONPATH=src python3 scripts/backfill_pi_papers_scope.py --dry-run
  PYTHONPATH=src python3 scripts/backfill_pi_papers_scope.py --apply
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

DEFAULT_FROM = "2026-06-01"
DEFAULT_UNTIL = "2026-09-21"

MISSING_SQL = """
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
  cs.ai_relevance,
  cs.scoring_reason
FROM research_radar.content_items ci
LEFT JOIN research_radar.paper_metadata pm ON pm.content_id = ci.id
LEFT JOIN research_radar.content_scores cs ON cs.content_id = ci.id
WHERE ci.source = 'arxiv_oai'
  AND ci.published_at >= %s::timestamptz
  AND ci.published_at < (%s::timestamptz + interval '1 day')
  AND NOT EXISTS (
    SELECT 1 FROM paper_intelligence.papers p
    WHERE p.paper_id = ci.id OR p.legacy_content_item_id = ci.id
  )
ORDER BY ci.id
"""


def _categories(row: dict):
    cats = row.get("pm_categories")
    if cats in (None, [], {}, "[]"):
        cats = row.get("categories_raw")
    return cats if cats is not None else []


def _authors(row: dict):
    return (
        row.get("pm_authors_raw")
        if row.get("pm_authors_raw") is not None
        else row.get("ci_authors_raw")
    )


def _decision_for_status(status: str | None) -> str | None:
    if status in RELEVANCE_KEEP_STATUSES:
        return "keep"
    if status in RELEVANCE_REJECT_STATUSES:
        return "reject"
    return None


def backfill(conn, *, date_from: str, date_until: str, apply: bool) -> dict:
    with conn.cursor() as cur:
        cur.execute(MISSING_SQL, (date_from, date_until))
        rows = [dict(r) for r in cur.fetchall()]

    by_status: dict[str, int] = {}
    for row in rows:
        by_status[row.get("status") or "NULL"] = (
            by_status.get(row.get("status") or "NULL", 0) + 1
        )

    summary = {
        "mode": "apply" if apply else "dry-run",
        "date_from": date_from,
        "date_until": date_until,
        "missing_total": len(rows),
        "missing_by_status": by_status,
        "would_insert_papers": len(rows),
        "would_insert_relevance_migrated": sum(
            1 for r in rows if _decision_for_status(r.get("status"))
        ),
        "would_leave_no_relevance": sum(
            1 for r in rows if not _decision_for_status(r.get("status"))
        ),
    }
    if not apply:
        return summary

    inserted = 0
    identity_rows = 0
    relevance_rows = 0
    skipped_no_title = 0
    errors: list[str] = []

    with conn.cursor() as cur:
        for row in rows:
            legacy_id = int(row["legacy_content_item_id"])
            title = (row.get("title") or "").strip()
            if not title:
                skipped_no_title += 1
                continue
            arxiv_id = normalize_arxiv_id(row.get("raw_arxiv_id"))
            arxiv_version = row.get("arxiv_version")
            if arxiv_version is None:
                arxiv_version = extract_arxiv_version(row.get("raw_arxiv_id"))
            doi = normalize_doi(row.get("raw_doi"))
            try:
                cur.execute("SAVEPOINT sp_row")
                if doi:
                    cur.execute(
                        "SELECT paper_id FROM paper_intelligence.papers WHERE doi = %s",
                        (doi,),
                    )
                    if cur.fetchone() is not None:
                        doi = None
                cur.execute(
                    """
                    INSERT INTO paper_intelligence.papers (
                        paper_id, legacy_content_item_id, arxiv_id, arxiv_version, doi,
                        source, source_external_id, source_type, canonical_url,
                        title, abstract, summary, categories, authors_raw,
                        affiliation_text, extracted_emails,
                        published_at, source_updated_at, ingested_at, raw_metadata,
                        created_at, modified_at
                    ) OVERRIDING SYSTEM VALUE VALUES (
                        %s, %s, %s, %s, %s,
                        %s, %s, %s, %s,
                        %s, %s, %s, %s::jsonb, %s::jsonb,
                        %s::jsonb, %s::jsonb,
                        %s, %s, %s, %s::jsonb,
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
                        row.get("source") or "arxiv_oai",
                        row.get("source_external_id"),
                        row.get("source_type") or "arxiv",
                        row.get("canonical_url"),
                        title,
                        row.get("abstract") or row.get("summary"),
                        row.get("summary"),
                        json.dumps(_categories(row)),
                        json.dumps(_authors(row) or []),
                        json.dumps(row.get("affiliation_text") or []),
                        json.dumps(row.get("extracted_emails") or []),
                        row.get("published_at"),
                        row.get("source_updated_at"),
                        row.get("ingested_at"),
                        json.dumps(
                            {
                                "backfill": "scope_coverage",
                                "radar_status": row.get("status"),
                                "ci_raw_metadata": row.get("ci_raw_metadata"),
                                "enrichment_metadata": row.get("enrichment_metadata"),
                            },
                            default=str,
                        ),
                        row.get("created_at"),
                        row.get("modified_at"),
                    ),
                )
                if cur.rowcount:
                    inserted += 1
                if arxiv_id:
                    cur.execute(
                        """
                        INSERT INTO paper_intelligence.paper_identity_map
                            (paper_id, system, external_id)
                        VALUES (%s, 'arxiv', %s)
                        ON CONFLICT (system, external_id) DO UPDATE
                          SET paper_id = EXCLUDED.paper_id
                        """,
                        (legacy_id, arxiv_id),
                    )
                    identity_rows += 1
                cur.execute(
                    """
                    INSERT INTO paper_intelligence.paper_identity_map
                        (paper_id, system, external_id)
                    VALUES (%s, 'research_radar', %s)
                    ON CONFLICT (system, external_id) DO UPDATE
                      SET paper_id = EXCLUDED.paper_id
                    """,
                    (legacy_id, str(legacy_id)),
                )
                identity_rows += 1
                if doi:
                    cur.execute(
                        """
                        INSERT INTO paper_intelligence.paper_identity_map
                            (paper_id, system, external_id)
                        VALUES (%s, 'doi', %s)
                        ON CONFLICT (system, external_id) DO NOTHING
                        """,
                        (legacy_id, doi),
                    )
                    identity_rows += 1

                decision = _decision_for_status(row.get("status"))
                if decision:
                    cur.execute(
                        """
                        SELECT 1 FROM paper_intelligence.paper_relevance_results
                        WHERE paper_id = %s LIMIT 1
                        """,
                        (legacy_id,),
                    )
                    if cur.fetchone() is None:
                        reason = None
                        score = row.get("ai_relevance")
                        scoring = row.get("scoring_reason")
                        if isinstance(scoring, dict):
                            reason = scoring.get("relevance_reason")
                        cur.execute(
                            """
                            INSERT INTO paper_intelligence.paper_relevance_results
                              (paper_id, decision, score, reason, method,
                               stage_version, policy_version)
                            VALUES (%s, %s, %s, %s, 'migrated_legacy_state',
                                    'migrated', 'migrated')
                            """,
                            (
                                legacy_id,
                                decision,
                                float(score) if score is not None else None,
                                reason
                                or f"migrated_from_radar_status={row.get('status')}",
                            ),
                        )
                        relevance_rows += 1
                cur.execute("RELEASE SAVEPOINT sp_row")
            except Exception as exc:  # noqa: BLE001
                cur.execute("ROLLBACK TO SAVEPOINT sp_row")
                errors.append(f"id={legacy_id}: {exc}")
                continue
            if inserted and inserted % 1000 == 0:
                conn.commit()

    conn.commit()
    summary.update(
        {
            "inserted_papers": inserted,
            "identity_rows": identity_rows,
            "relevance_migrated": relevance_rows,
            "skipped_no_title": skipped_no_title,
            "errors": errors[:50],
            "error_count": len(errors),
        }
    )
    return summary


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--from", dest="date_from", default=DEFAULT_FROM)
    parser.add_argument("--until", dest="date_until", default=DEFAULT_UNTIL)
    parser.add_argument("--apply", action="store_true")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()
    apply = bool(args.apply) and not args.dry_run
    with connect() as conn:
        result = backfill(
            conn, date_from=args.date_from, date_until=args.date_until, apply=apply
        )
    print(json.dumps(result, indent=2, default=str))
    return 0 if result.get("error_count", 0) == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
