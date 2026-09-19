# PI Catalog Controlled Cutover — Stop Report

**Date:** 2026-09-19  
**Status:** Stopped before final cutover. Default flag remains OFF.

---

## 1. Additive/shadow commit SHA

`addb201929f1169529e9ffb76656afb2e47b882e`  
`feat(catalog): add PI-owned paper catalog in shadow mode`

## 2. Migrated relevance provenance audit

See `reports/architecture/pi_relevance_provenance_audit.{md,json}`.

| Q | Answer |
|---|---|
| A. Radar → keep | RELEVANT, ENRICHED, ENTITY_RESOLVED, SCORED, CANDIDATE |
| B. Radar → reject | REJECTED |
| C. ENTITY_RESOLVED → keep? | **Yes** (13,959 rows) |
| D. Justification | Post-relevance Radar lifecycle; not a reject; preserves Phase-2 papers |
| E. keep + screen fail | 208 — **not** a relevance contradiction (later paid screen gate) |
| F. reject + screen pass | **0** |

Relabeled all 28,383 rows: `method = migrated_legacy_state`.  
`stop_for_contradictions = false`.

## 3–4. Shadow 7d / 15d

| Window | Unexplained |
|---|---:|
| 2026-09-09 → 2026-09-15 (7d) | **0** |
| 2026-09-01 → 2026-09-15 (15d) | **0** |

Expected `migrated_state_difference` on paper_window / relevance / screen&audience candidate pools / HF window (PI subset vs full Radar).  
Screen survivors, quality selected, affiliation deep, adjudication population: **match**.

Reports: `pi_catalog_shadow_7d.{md,json}`, `pi_catalog_shadow_15d.{md,json}`

## 5. Unexplained difference count

**0** (both windows)

## 6. Reader-cutover files changed (uncommitted — review)

- `src/paper_intelligence/common/config.py` — `PI_USE_PAPERS_CATALOG`, `PI_WRITE_RADAR_COMPAT`
- `src/paper_intelligence/db/results.py` — flag-branched fetch/select/screen
- `src/paper_intelligence/catalog/relevance.py` — `insert_relevance_result`
- `src/paper_intelligence/relevance/stage.py` — native PI relevance write; Radar best-effort
- `src/paper_intelligence/author_affiliation/repository.py` — PI metadata fetch
- `src/paper_intelligence/hf_signals/stage.py` — PI arxiv lookup
- `src/paper_intelligence/adjudication/stage.py` — PI published_at joins
- `scripts/run_stage.py` — normalize uses PI keep when flag on
- `scripts/shadow_catalog_expanded.py`, `scripts/canary_pi_catalog_oneday.py`
- `tests/unit/test_catalog_cutover.py`
- provenance + shadow + canary reports under `reports/architecture/`

## 7. Feature-flag behaviour

| Flag | Default | Effect |
|---|---|---|
| `PI_USE_PAPERS_CATALOG` | **0 / OFF** | ON → PI papers + PI relevance eligibility; no Radar status gate |
| `PI_WRITE_RADAR_COMPAT` | **1 / ON** | Radar status writes best-effort; failure does not invalidate PI relevance |

## 8. One-day canary (2026-09-02)

`PI_USE_PAPERS_CATALOG=1`, `PI_WRITE_RADAR_COMPAT=1`, **no paid quality**.

| Check | Result |
|---|---|
| Papers resolve from PI | Yes |
| 137619 relevance keep | Yes (`migrated_legacy_state`) |
| Screen present / enters router | Yes |
| Outcome | `not_selected_below_gate_percentile` |
| Affiliation from PI | Yes |
| arXiv unique / vN same | Yes |
| Orphan screen rows | 0 |
| Paid calls | 0 |

Report: `pi_catalog_canary_2026-09-02.json`

## 9. Radar mutation independence

Mutated 137619 Radar status through RELEVANT / ENTITY_RESOLVED / SCORED (then restored).  
With catalog flag ON: screen pool membership and quality reason **unchanged**.

## 10. Tests passed

**21 passed** (`test_catalog_normalize`, `test_catalog_cutover`, `test_quality_router`, `test_nomination`)

## 11. Remaining Radar reads

- Legacy path when flag OFF (full)
- Ingest still reads/writes Radar tables
- Relevance still *selects* candidates from Radar INGESTED rows (writes PI relevance + optional Radar status)
- Some report/editorial scripts may still join Radar directly (not all flipped)

## 12. Remaining Radar writes

- Ingest → `content_items` / `paper_metadata` / checkpoints  
- Relevance → Radar status/scores when `PI_WRITE_RADAR_COMPAT=1`  
- S3 reject archive → Radar `s3_archives`

## 13. Remaining Radar FKs

Unchanged: PI `content_item_id` → `research_radar.content_items` CASCADE.

## 14. Exact next cutover actions (need approval)

1. Review & commit controlled cutover patch (flags default OFF).  
2. Optionally enable `PI_USE_PAPERS_CATALOG=1` in staging/canary env.  
3. Dual-write ingest to `papers` (PI authoritative).  
4. Default flag ON after soak.  
5. Disable `PI_WRITE_RADAR_COMPAT`.  
6. Migrate FKs off Radar.  
7. PI-only ingest independence test.

**Not done / not allowed yet:** default ON, disable Radar writes, FK migration, bulk paid scoring, delete legacy path.
