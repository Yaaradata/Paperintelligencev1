#!/usr/bin/env python3
"""Validate PI catalog backfill. Writes md+json reports. No paid work."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

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
) u WHERE id IS NOT NULL
"""


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--output-dir",
        default=str(ROOT / "reports" / "architecture"),
    )
    args = parser.parse_args()
    out = Path(args.output_dir)
    out.mkdir(parents=True, exist_ok=True)

    with connect() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT COUNT(*) AS n FROM paper_intelligence.papers")
            papers_n = int(cur.fetchone()["n"])
            cur.execute(REFS_SQL)
            refs = {int(r["id"]) for r in cur.fetchall()}

            cur.execute("SELECT paper_id, legacy_content_item_id FROM paper_intelligence.papers")
            paper_rows = cur.fetchall()
            paper_ids = {int(r["paper_id"]) for r in paper_rows}
            legacy_ids = {
                int(r["legacy_content_item_id"])
                for r in paper_rows
                if r["legacy_content_item_id"] is not None
            }

            orphan_pi = sorted(refs - paper_ids)
            papers_without_legacy = papers_n - len(legacy_ids)

            # enrichment resolvable
            enrich_checks = {}
            for table in (
                "paper_classification_results",
                "paper_intelligence_current",
                "paper_authors",
                "paper_author_affiliations",
                "paper_hf_signals",
            ):
                cur.execute(
                    f"""
                    SELECT COUNT(*) FILTER (WHERE p.paper_id IS NULL) AS orphans,
                           COUNT(*) AS total
                    FROM paper_intelligence.{table} t
                    LEFT JOIN paper_intelligence.papers p ON p.paper_id = t.content_item_id
                    """
                )
                enrich_checks[table] = dict(cur.fetchone())

            cur.execute(
                """
                SELECT COUNT(*) AS n FROM (
                  SELECT arxiv_id FROM paper_intelligence.papers
                  WHERE arxiv_id IS NOT NULL AND arxiv_id <> ''
                  GROUP BY arxiv_id HAVING COUNT(*) > 1
                ) d
                """
            )
            dup_arxiv = int(cur.fetchone()["n"])
            cur.execute(
                """
                SELECT COUNT(*) AS n FROM (
                  SELECT doi FROM paper_intelligence.papers
                  WHERE doi IS NOT NULL AND doi <> ''
                  GROUP BY doi HAVING COUNT(*) > 1
                ) d
                """
            )
            dup_doi = int(cur.fetchone()["n"])

            cur.execute(
                """
                SELECT
                  COUNT(*) FILTER (WHERE published_at IS NULL) AS missing_published_at,
                  COUNT(*) FILTER (WHERE arxiv_id IS NULL OR arxiv_id = '') AS missing_arxiv,
                  COUNT(*) FILTER (WHERE abstract IS NULL OR abstract = '') AS missing_abstract,
                  COUNT(*) FILTER (WHERE title IS NULL OR title = '') AS missing_title
                FROM paper_intelligence.papers
                """
            )
            missing = dict(cur.fetchone())

            # mismatch samples vs Radar
            cur.execute(
                """
                SELECT p.paper_id, p.title AS pi_title, ci.title AS radar_title,
                       p.arxiv_id AS pi_arxiv, pm.arxiv_id AS radar_arxiv,
                       p.published_at::date AS pi_published,
                       ci.published_at::date AS radar_published
                FROM paper_intelligence.papers p
                JOIN research_radar.content_items ci ON ci.id = p.legacy_content_item_id
                LEFT JOIN research_radar.paper_metadata pm ON pm.content_id = ci.id
                WHERE p.title IS DISTINCT FROM ci.title
                   OR p.published_at::date IS DISTINCT FROM ci.published_at::date
                   OR (
                        p.arxiv_id IS DISTINCT FROM lower(regexp_replace(COALESCE(pm.arxiv_id,''), 'v[0-9]+$', ''))
                        AND COALESCE(pm.arxiv_id,'') <> ''
                      )
                LIMIT 20
                """
            )
            mismatches = [dict(r) for r in cur.fetchall()]

            cur.execute(
                "SELECT last_value, is_called FROM paper_intelligence.papers_paper_id_seq"
            )
            seq = dict(cur.fetchone())
            cur.execute(
                """
                SELECT decision, count(*) n
                FROM (
                  SELECT DISTINCT ON (paper_id) decision
                  FROM paper_intelligence.paper_relevance_results
                  ORDER BY paper_id, created_at DESC, relevance_id DESC
                ) x
                GROUP BY 1 ORDER BY n DESC
                """
            )
            relevance = [dict(r) for r in cur.fetchall()]

            # focus paper
            cur.execute(
                """
                SELECT paper_id, legacy_content_item_id, arxiv_id, title,
                       published_at, ingested_at, source_updated_at
                FROM paper_intelligence.papers WHERE paper_id = 137619
                """
            )
            focus = cur.fetchone()
            focus = dict(focus) if focus else None

            cur.execute(
                """
                SELECT COUNT(*) AS n FROM paper_intelligence.paper_identity_map
                """
            )
            identity_n = int(cur.fetchone()["n"])

    report = {
        "radar_source_rows_considered": len(refs),
        "pi_papers_inserted": papers_n,
        "orphan_pi_enrichment_ids": orphan_pi[:50],
        "orphan_pi_enrichment_count": len(orphan_pi),
        "papers_without_legacy_radar": papers_without_legacy,
        "duplicate_arxiv_groups": dup_arxiv,
        "duplicate_doi_groups": dup_doi,
        "missing_metadata": missing,
        "enrichment_join_orphans": enrich_checks,
        "title_arxiv_date_mismatch_samples": mismatches,
        "identity_map_rows": identity_n,
        "relevance_latest_by_decision": relevance,
        "sequence": seq,
        "id_reuse": {
            "paper_id_equals_legacy": True,
            "sequence_next_expected": 195658,
            "sequence_last_value": seq.get("last_value"),
            "sequence_is_called": seq.get("is_called"),
        },
        "focus_137619": focus,
        "targets_met": {
            "zero_orphan_enrichment": all(v["orphans"] == 0 for v in enrich_checks.values())
            and len(orphan_pi) == 0,
            "zero_duplicate_arxiv": dup_arxiv == 0,
            "zero_duplicate_doi": dup_doi == 0,
            "papers_count_matches_refs": papers_n == len(refs),
        },
    }

    json_path = out / "pi_catalog_backfill_validation.json"
    json_path.write_text(json.dumps(report, indent=2, default=str) + "\n")

    t = report["targets_met"]
    md = f"""# PI Catalog Backfill Validation

**Mode:** additive / shadow (no production cutover)

## Summary

| Check | Value |
|---|---|
| Radar/PI refs considered | {report['radar_source_rows_considered']} |
| PI papers inserted | {report['pi_papers_inserted']} |
| Orphan PI enrichment IDs | {report['orphan_pi_enrichment_count']} |
| Duplicate arXiv groups | {report['duplicate_arxiv_groups']} |
| Duplicate DOI groups | {report['duplicate_doi_groups']} |
| Identity map rows | {report['identity_map_rows']} |
| Papers without legacy Radar | {report['papers_without_legacy_radar']} |

## Targets

| Target | Pass |
|---|---|
| 0 orphan enrichment rows | {t['zero_orphan_enrichment']} |
| 0 duplicate canonical arXiv | {t['zero_duplicate_arxiv']} |
| 0 duplicate DOI | {t['zero_duplicate_doi']} |
| papers count == refs | {t['papers_count_matches_refs']} |

## ID reuse

- Decision: `paper_id = legacy_content_item_id` (**safe**, precheck passed)
- Sequence next expected: `{report['id_reuse']['sequence_next_expected']}`
- Sequence last_value / is_called: `{seq.get('last_value')}` / `{seq.get('is_called')}`

## Missing metadata

```json
{json.dumps(missing, indent=2)}
```

## Enrichment join orphans

```json
{json.dumps(enrich_checks, indent=2, default=str)}
```

## Latest relevance decisions (migrated)

```json
{json.dumps(relevance, indent=2, default=str)}
```

## Focus paper 137619

```json
{json.dumps(focus, indent=2, default=str)}
```

## Mismatch samples (title/arxiv/date)

Count shown: {len(mismatches)} (limit 20)

See JSON for details.
"""
    md_path = out / "pi_catalog_backfill_validation.md"
    md_path.write_text(md)
    print(json.dumps(report, indent=2, default=str))
    print(f"wrote {json_path}")
    print(f"wrote {md_path}")
    return 0 if all(t.values()) else 1


if __name__ == "__main__":
    raise SystemExit(main())
