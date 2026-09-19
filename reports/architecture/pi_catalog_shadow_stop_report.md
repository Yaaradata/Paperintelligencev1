# PI Catalog Migration — Shadow Stop Report

**Date:** 2026-09-19  
**Mode:** Additive / shadow only — **no production cutover**  
**Commit:** not created (awaiting review)

---

## 1. Migrations created

| File | Applied? |
|---|---|
| `sql/migrations/006_pi_papers_catalog.sql` | **Yes** (additive DDL only) |

Creates: `papers`, `paper_identity_map`, `paper_relevance_results`, `ingest_checkpoints`.  
**Not** created: `s3_archives` (PI still uses Radar compatibility archive).  
**Not** modified: any Research Radar table.  
**Not** changed: legacy FKs.

## 2. Schema created

- `paper_intelligence.papers` — canonical identity (`paper_id`, dates separated)
- `paper_intelligence.paper_identity_map` — Radar / arXiv / DOI crosswalk
- `paper_intelligence.paper_relevance_results` — append-only keep/reject
- `paper_intelligence.ingest_checkpoints` — PI ingest checkpoint store

## 3. Papers backfilled

**34,460** PI papers (exact match to all PI-referenced `content_item_id`s)

Also: 70,952 identity map rows; 28,383 relevance seed rows  
(20,300 keep / 8,083 reject; INGESTED papers intentionally have no relevance row yet)

## 4. Identity reuse decision

**`paper_id = legacy_content_item_id` — SAFE**

- 0 orphan PI refs vs Radar
- 0 duplicate normalized arXiv / DOI among refs
- Sequence reset: next `paper_id` = **195658** (`last_value=195658`, `is_called=false`)

## 5. Sequence / collision validation

| Check | Result |
|---|---|
| Max referenced legacy id | 195610 |
| Max Radar `content_items.id` | 195657 |
| Sequence next | 195658 |
| Collision risk for future PI-only inserts | Mitigated |

## 6. Duplicate arXiv / DOI

| | Groups |
|---|---|
| Duplicate arXiv | **0** |
| Duplicate DOI | **0** |

## 7. Orphan counts

| Enrichment table | Orphans vs `papers` |
|---|---|
| classification_results | 0 |
| current | 0 |
| authors | 0 |
| affiliations | 0 |
| hf_signals | 0 |

Title/arxiv/date mismatches vs Radar: **0 samples**

Reports:  
`reports/architecture/pi_catalog_backfill_validation.{md,json}`  
`reports/architecture/pi_catalog_precheck.json`

## 8. Reader shadow comparison (2026-09-02)

| Reader | old | new | ∩ | old_only | new_only |
|---|---:|---:|---:|---:|---:|
| Screen candidates needing work | 0 | 0 | 0 | 0 | 0 |
| Screen survivors (gate passed) | 556 | 556 | 556 | **0** | **0** |
| Quality selected | 131 | 131 | 131 | **0** | **0** |

Unexplained differences: **none** for this day.

Production still uses Radar-backed `select_window_candidates` / `latest_screen_scores`.  
Shadow implementations live in `paper_intelligence.catalog.shadow` (not wired to CLI).

## 9. One-day shadow E2E (2026-09-02)

| Step | Result |
|---|---|
| PI papers in day | 927 |
| Relevance keep / reject | 567 / 360 |
| Screen rows / passed / blocked | 567 / 556 / 11 |
| Quality selected | 131 |
| Already scored | 93 |
| Would need paid (not run) | 38 (~$0.29 / 8 calls) |
| Paid LLM executed | **No** |

### Paper 137619

| Check | Result |
|---|---|
| Exists as one PI paper | Yes (`paper_id=137619`, arxiv `2609.03181`) |
| Dates | `published_at=2026-09-02`, `source_updated_at=2026-09-04`, `ingested_at=2026-09-05` (distinct) |
| PI relevance | `keep` (migrated from ENTITY_RESOLVED) |
| Enters quality router | Yes |
| Outcome | `not_selected_below_gate_percentile` |
| Radar status affects routing | **No** |

## 10. Remaining Radar reads/writes

| Still active | Purpose |
|---|---|
| Ingest writes `content_items` / `paper_metadata` | Compatibility (not flipped) |
| Relevance writes Radar `status` | Compatibility |
| `select_window_candidates` uses `PI_ELIGIBLE_STATUSES` | **Production path still** |
| Affiliation / HF / adjudication / reports join Radar | Identity/dates until reader cutover |
| FK CASCADE to Radar | Untouched |
| Reject archive → Radar `s3_archives` | Compatibility |

PI relevance is populated and shadow selectors exist, but **`PI_ELIGIBLE_STATUSES` has not been removed from production** (awaiting cutover approval).

## 11. Proposed cutover order (next approval)

1. Feature-flag PI catalog readers (`fetch_papers`, windows)
2. Screen/audience/normalize eligibility → PI relevance `keep` (remove `PI_ELIGIBLE_STATUSES`)
3. Affiliation / HF / adjudication / report readers → `papers`
4. Dual-write: PI authoritative; Radar best-effort (`PI_WRITE_RADAR_COMPAT`)
5. Turn off Radar writes
6. Migrate FKs off Radar CASCADE
7. Independence test: ingest new arXiv **only** into PI

## 12. Rollback procedure

1. Stop using shadow modules (already unused by production CLI).
2. Leave tables in place (additive); do not drop until reconciled.
3. Sequence/papers data can remain; production ignores them until flag on.
4. Never delete Radar rows to “clean up”.

## 13. Tests passed

- `tests/unit/test_catalog_normalize.py` (3)
- `tests/unit/test_quality_router.py` (regression)  
**11 passed** in combined run with quality router suite earlier; normalize alone + quality = green.

---

## Explicitly NOT done

- Production reader cutover  
- Removal of `PI_ELIGIBLE_STATUSES` from live selectors  
- Disable Radar compatibility writes  
- FK migration / drop  
- Bulk paid scoring  
- Commit/deploy cutover  

**Awaiting review before any cutover step.**
