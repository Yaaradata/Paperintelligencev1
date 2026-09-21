# PI catalog — final cutover readiness report

**Date:** 2026-09-21  
**Status:** STOPPED before final cutover — awaiting review  
**Code defaults unchanged:** `PI_USE_PAPERS_CATALOG=0`, `PI_WRITE_RADAR_COMPAT=1`

---

## 1. New commit SHA (write-path patch)

`43b7d8f98fbc0b2d543b622c11d4b96a93e62e72`

`feat(catalog): add PI-native ingest and relevance path`

This readiness phase also produced **uncommitted** follow-ups (scope backfill script, soak, archive migration 007, FK/rollback docs, ingest canary). Commit those separately after review if desired.

---

## 2. Explanation of the 9 Sep-02 Radar-only papers

**Classification: valid arXiv papers awaiting PI processing** (catalog gap, not intentional scope exclusion).

| Field | Value |
|---|---|
| IDs | 192167–192175 |
| Source | `arxiv_oai` |
| Status | all `INGESTED` |
| Categories | cs.*/stat.* (in PI ingest allow-list) |
| PI enrichment | none |

**Root cause:** the initial catalog backfill only copied papers referenced by PI enrichment tables (`REFS_SQL`). These 9 never entered PI stages, so they were never backfilled — while still being valid in-scope arXiv harvest rows.

They are **not**: rejected/invalid, duplicates, or intentional out-of-scope.

---

## 3. Total Radar-only in-scope papers found

Horizon definition: `arxiv_oai` with `published_at ∈ [2026-06-01, 2026-09-21]`.

| Metric | Count |
|---|---:|
| Radar arxiv_oai in horizon | 59,937 |
| Missing from PI before this phase | **29,609** |
| Of which INGESTED (no relevance decision yet) | 29,536 |
| Of which keep/reject lifecycle (RELEVANT/ENTITY_RESOLVED/REJECTED) | 73 |

---

## 4. Number backfilled into PI catalog

| Pass | Inserted |
|---|---:|
| First apply | 29,607 (+ 2 DOI-collision retries with `doi=NULL`) |
| Second apply (txn leftovers) | 604 |
| **Total identity backfilled** | **30,213** |
| Migrated relevance (`migrated_legacy_state`) | 73 |
| Left with **no** relevance row (correct for INGESTED) | 29,536 + 604 |

**After backfill:** Sep-02 and horizon `radar_only = 0`.  
Validation: **0** duplicate arXiv, **0** duplicate DOI, **0** orphan enrichment.

---

## 5. Remaining papers with no PI relevance result

Informational backlog (no paid calls executed):

| Window | papers_no_relevance |
|---|---:|
| Sep 1–15 | 295 |
| Aug 1–31 | 6,110 |
| Jan 1–present / Jun–Sep 21 horizon | 35,613 |

All counted rows are Radar `INGESTED` (no keep/reject decision). These become naturally visible to PI-native relevance candidate selection when catalog mode is on.

Details: `reports/architecture/pi_catalog_scope_coverage.md`

---

## 6–7. Soak results (env flag ON; code defaults OFF)

`PI_USE_PAPERS_CATALOG=1` `PI_WRITE_RADAR_COMPAT=1` · read-only · **0 paid calls**

### 3 representative days

| Day | catalog_window | unexplained |
|---|---|---:|
| 2026-09-10 (recent) | 996 = 996 **match** | 0 |
| 2026-09-02 (prior gap day) | 936 = 936 **match** | 0 |
| 2026-08-15 (older) | 402 = 402 **match** | 0 |

### 7d / 15d

| Window | catalog_window | unexplained |
|---|---|---:|
| 7d 2026-09-09→15 | 5645 = 5645 **match** | 0 |
| 15d 2026-09-01→15 | 12149 = 12149 **match** | 0 |

Screen/audience/normalize/quality/HF/affiliation/adjudication comparisons: **0 unexplained** (see `pi_catalog_final_soak.md`).

---

## 8. Unexplained differences

**0**

---

## 9. Real PI-first ingest result

**PASSED** — `reports/architecture/pi_first_ingest_canary.json`

- PI write first + retained after injected Radar failure
- Version rediscovery → same paper, no duplicate
- Visible to PI relevance selector
- PI checkpoint controls resume; Radar COMPLETE alone does not skip PI

---

## 10. Archive dependency status

- Additive table: `paper_intelligence.archive_records` (migration **007** applied)
- `s3_archive.py` writes PI index first; Radar `s3_archives` remains best-effort compat
- Object bodies unchanged (index only)
- Radar archive **not** disabled

---

## 11. FK migration plan

`reports/architecture/pi_fk_migration_plan.md`

- Orphan precheck: **0** across all FK child tables
- Add PI FKs with `NO ACTION` / `NOT VALID` → `VALIDATE`
- **Do not drop** Radar FKs in this phase

---

## 12. Post-compat rollback plan

`reports/architecture/pi_post_compat_rollback.md`

- After compat-off, PI remains authoritative
- Flag-off is not a full rollback
- Recovery = fix-forward in PI; optional PI→Radar projection only

---

## 13. Tests passed

- Catalog unit tests: **15 passed**
- PI-first ingest canary: **passed**
- Final soak: **passed**

---

## 14. Remaining Radar reads (flag=1)

- Legacy rollback branches (flag=0 path)
- Best-effort Radar dual-read only where not yet dual-pathed (should be minimal)
- Optional Radar checkpoint mirror reads unused for PI resume

## 15. Remaining Radar writes

- Ingest / relevance / archive dual-write while `PI_WRITE_RADAR_COMPAT=1`
- Not disabled

## 16. Exact final cutover sequence

1. Commit remaining readiness artifacts (007 wiring, soak reports, scope backfill script, docs) if not already committed.
2. Ops soak with **env** `PI_USE_PAPERS_CATALOG=1` (code default still 0) for ≥1 production-like day.
3. Flip **code default** `PI_USE_PAPERS_CATALOG=1`.
4. Apply FK add migration (`008`) — validate constraints; keep Radar FKs.
5. Set `PI_WRITE_RADAR_COMPAT=0`.
6. Drop Radar FKs after soak with PI-only inserts.
7. Remove rollback eligibility (`PI_ELIGIBLE_STATUSES`) from live paths.
8. Stop Radar archive dual-write when PI archive_records proven.
9. Only then: historical paid relevance/screen/quality catch-up (explicit approval).

### Still forbidden without new approval

- Disable Radar compat now
- Drop Radar FKs / delete Radar tables
- Bulk paid scoring / historical paid backfill
- Remove rollback code

---

## Artefacts

| Path | Role |
|---|---|
| `reports/architecture/pi_catalog_scope_coverage.md` | Coverage + 9-paper explanation |
| `reports/architecture/pi_catalog_final_soak.md` | 3-day + 7d/15d soak |
| `reports/architecture/pi_first_ingest_canary.json` | PI-first ingest |
| `reports/architecture/pi_fk_migration_plan.md` | FK plan |
| `reports/architecture/pi_post_compat_rollback.md` | Post-compat rollback |
| `sql/migrations/007_pi_archive_records.sql` | Archive index (applied) |
| `scripts/backfill_pi_papers_scope.py` | Scope identity backfill |
