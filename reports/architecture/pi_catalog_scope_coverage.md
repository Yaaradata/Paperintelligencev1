# PI catalog scope coverage

## Sep 02 Radar-only (9 papers)

All 9 were arxiv_oai INGESTED papers with valid cs.*/stat.* categories. They were absent because the initial PI catalog backfill only included papers referenced by PI enrichment tables (REFS_SQL). These 9 never received PI enrichment, so they were out of that backfill set — not intentionally out of PI ingest scope.

- After backfill: radar=936 pi=936 radar_only=**0**

## Horizon coverage (arxiv_oai 2026-06-01 → 2026-09-21)

- Radar arxiv_oai: 59937
- PI papers in window: 64069
- Radar-only remaining: **0**
- Backfilled this phase: **30213** identity rows (29609 intended; 604 recovered on second pass)

## Validation

- Duplicate canonical arXiv: 0
- Duplicate DOI: 0
- Orphan classification: 0
- Orphan current: 0

## No-relevance backlog (informational; no paid calls)

| Window | papers_no_relevance | radar_INGESTED | radar_keepish | radar_REJECTED |
|---|---:|---:|---:|---:|
| sep_1_15 | 295 | 295 | 0 | 0 |
| aug_1_31 | 6110 | 6110 | 0 | 0 |
| jan_1_present | 35613 | 35613 | 0 | 0 |
| horizon_jun_sep21 | 35613 | 35613 | 0 | 0 |

### Sep 1–15 by day

| day | no_relevance |
|---|---:|
| 2026-09-01 | 4 |
| 2026-09-02 | 9 |
| 2026-09-03 | 6 |
| 2026-09-04 | 7 |
| 2026-09-05 | 3 |
| 2026-09-06 | 9 |
| 2026-09-07 | 13 |
| 2026-09-08 | 14 |
| 2026-09-09 | 23 |
| 2026-09-10 | 207 |

