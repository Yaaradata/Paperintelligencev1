# PI catalog pre-final cutover — stop report

**Date:** 2026-09-19  
**Phase:** Pre-final cutover (ingest + relevance candidates + editorial readers)  
**Status:** STOPPED before final cutover — awaiting review

---

## 1. Controlled-cutover commit SHA

`24b3867ab1ee26759a60d56859b2e9e5a53e9632`

`feat(catalog): add feature-flagged PI catalog cutover path`

Defaults in that commit (unchanged):

- `PI_USE_PAPERS_CATALOG=0`
- `PI_WRITE_RADAR_COMPAT=1`

Write-path work in this phase is **uncommitted** (separate from that SHA).

---

## 2. Remaining Radar dependency audit

See: `reports/architecture/pi_remaining_radar_dependencies.md`

After this phase, **production blockers reduced**:

| Area | Before | After (flag=1) |
|---|---|---|
| Ingest | Radar-first | PI `papers` first + best-effort Radar |
| Ingest checkpoints | Radar only | PI `ingest_checkpoints` controls resume |
| Relevance candidates | Radar `INGESTED` status | PI papers w/o current relevance |
| Newsletter / LinkedIn | Radar joins | Dual SQL; PI path when flag on |
| generate_report / audience tops | Radar joins | Dual join helper when flag on |
| normalize authors | Radar only | Dual |
| affiliation runner window | Radar only | Dual |
| quality nomination | Radar only | Dual |
| org_coverage / HF validate / golden | Radar | Dual / PI-or-Radar existence |

Still deferred (final cutover):

- Schema FKs → `research_radar.content_items`
- Default flag ON
- Disable `PI_WRITE_RADAR_COMPAT`
- Delete rollback branches
- S3 archive still writes Radar `s3_archives`

---

## 3. Ingest files changed

- `src/paper_intelligence/catalog/ingest.py` **(new)** — PI upsert, identity, checkpoints
- `src/paper_intelligence/ingest/arxiv_oai.py` — PI-first window + Radar best-effort dual-write
- `src/paper_intelligence/catalog/__init__.py` — exports

---

## 4. Relevance-selection files changed

- `src/paper_intelligence/relevance/stage.py`
  - `_select_candidates_pi` / `_select_candidates_radar`
  - No `INGESTED` / Radar status gate when catalog on
  - `_store_relevance` now best-effort under `PI_WRITE_RADAR_COMPAT`

---

## 5. Reports / editorial readers changed

- `scripts/select_newsletter.py` (+ LinkedIn via shared loader)
- `scripts/generate_report.py`
- `scripts/generate_audience_tops.py`
- `scripts/run_pipeline.py` (`_quality_ids`)
- `scripts/validate_hf_signals.py`
- `src/paper_intelligence/normalize/repository.py`
- `src/paper_intelligence/author_affiliation/runner.py`
- `src/paper_intelligence/quality/nomination.py`
- `src/paper_intelligence/evaluation/org_coverage.py`
- `src/paper_intelligence/evaluation/golden.py`
- `src/paper_intelligence/catalog/report_sql.py` **(new)**

---

## 6. PI-only paper independence result

**PASSED** (`reports/architecture/pi_only_paper_independence.json`)

- Created PI paper with **no Radar row**
- Selected for PI relevance
- Received PI relevance `keep`
- Not re-selected after result
- Eligible for screen via PI keep pool
- Reader found metadata
- Fixture **rolled back** (no permanent data)
- Stopped before paid stages

---

## 7. Write-path canary result

**PASSED** (`reports/architecture/pi_catalog_writepath_canary.json`)

Day: `2026-09-02`

- arXiv version rediscovery → same `paper_id`, **no duplicate**
- PI checkpoint table queryable
- Relevance candidates from PI papers (0 pending that day — already scored)
- Screen visibility: 567 keep-eligible
- **Paid calls executed: 0**
- Paid projection if quality were run: 393 would-call (not executed)

---

## 8. Soak comparison

**PASSED** (`reports/architecture/pi_catalog_flag_soak.md`)

Day: `2026-09-02` · read-only · flag soak only (not global default)

| metric | old | new | class |
|---|---:|---:|---|
| paper_window | 936 | 927 | expected_fix (9 Radar-only not backfilled) |
| screen_candidates | 567 | 567 | match |
| audience_candidates | 567 | 567 | match |
| screen_results_present | 567 | 567 | match |
| editorial_quality_papers | 163 | 163 | match |

---

## 9. Unexplained differences

**0**

---

## 10. Tests passed

- `tests/unit/test_catalog_cutover.py` + `test_catalog_writepath.py` + quality router: **23**
- Full `tests/unit/`: **131 passed**

---

## 11. Remaining Radar reads (flag=1 path)

- Legacy rollback branches still present (flag=0)
- S3 reject archive index (`research_radar.s3_archives`)
- Some evaluation tooling may still touch Radar when flag off
- Affiliation / HF / adjudication use PI when flag on (already dual)

---

## 12. Remaining Radar writes

- Best-effort ingest dual-write when `PI_WRITE_RADAR_COMPAT=1`
- Best-effort relevance status / scores / topics
- S3 archive index
- Optional Radar checkpoint mirror (does not control PI resume)

---

## 13. Remaining Radar FKs

Unchanged from migration `001` / `003` (10+ tables). Not migrated in this phase.

---

## 14. Exact actions needed for FINAL cutover

1. **Commit** this write-path / reader patch (flags still default OFF).
2. **Soak longer** with `PI_USE_PAPERS_CATALOG=1` in staging/ops env (not code default).
3. Flip **code default** `PI_USE_PAPERS_CATALOG=1` after soak sign-off.
4. Set `PI_WRITE_RADAR_COMPAT=0` after dual-write soak.
5. Migration: retarget FKs from Radar `content_items` → PI `papers`.
6. Remove Radar rollback branches / `PI_ELIGIBLE_STATUSES` live use.
7. Move reject archive index off Radar `s3_archives`.
8. Only then: historical paid catch-up / bulk scoring (still explicitly gated).

**Do not yet:** default catalog ON in code, disable Radar compat, migrate FKs, delete Radar tables, run bulk paid scoring.

---

## Flag behaviour (unchanged defaults)

| Flag | Default | Meaning |
|---|---|---|
| `PI_USE_PAPERS_CATALOG` | **0 / OFF** | Radar rollback path live |
| `PI_WRITE_RADAR_COMPAT` | **1 / ON** | Best-effort Radar dual-write after PI success |
