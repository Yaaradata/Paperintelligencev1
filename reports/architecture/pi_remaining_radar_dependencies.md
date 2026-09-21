# Remaining Radar dependencies (pre-final cutover)

**Date:** 2026-09-19  
**Repo:** `worktrees/subha`  
**Flags:** `PI_USE_PAPERS_CATALOG` default **OFF**; `PI_WRITE_RADAR_COMPAT` default **ON**

Classification:
- **legacy rollback path** — Radar branch when catalog flag is off
- **compatibility write** — best-effort / dual-write to Radar after PI success
- **production blocker for PI independence** — live path requires Radar with no (or incomplete) PI branch
- **test/dev-only** — shadow, canary, dry-run, tests, one-shot backfill
- **obsolete** — unused symbols / docs only

---

## Production blockers for PI independence

| File:function | What |
|---|---|
| `relevance/stage.py:run_window` | Candidate SELECT from `content_items` filtered by Radar status (`INGESTED`…) |
| `normalize/repository.py:fetch_authors_raw` | Authors always from Radar `content_items`/`paper_metadata` |
| `author_affiliation/runner.py:select_window` | Window ids via Radar + `paper_metadata` |
| `quality/nomination.py:resolve_content_ids` / `describe_targets` | Radar `paper_metadata` / `content_items.status` |
| `scripts/select_newsletter.py:CANDIDATE_SQL` / `load_candidates_from_db` | Editorial pool from Radar (status counts + joins) |
| `scripts/select_linkedin.py` | Imports newsletter loader (same Radar pool) |
| `scripts/generate_report.py:build_report` | Funnel + stage joins on `content_items` |
| `scripts/generate_audience_tops.py:fetch_pool` / `coverage` | Joins Radar for title/`published_at` |
| `scripts/run_pipeline.py:_quality_ids` | Quality ids via Radar `published_at` |
| `scripts/validate_hf_signals.py` | HF corpus from Radar |
| `evaluation/org_coverage.py:load_papers` / `compute_window_metrics` | Papers + Radar `status` |
| `evaluation/golden.py:upsert_golden_set` | Existence check against Radar `content_items` |
| `sql/migrations/001_schema.sql` + `003_hf_signals.sql` | FKs → `research_radar.content_items(id)` |

---

## Legacy rollback path (`PI_USE_PAPERS_CATALOG=0`)

| File:function | What |
|---|---|
| `db/results.py:PI_ELIGIBLE_STATUSES` | Radar status allow-list for screen/audience/normalize |
| `db/results.py:fetch_papers` / `select_window_candidates` / `count_window` / `latest_screen_scores` | Radar SQL when flag off |
| `adjudication/stage.py:run_window` | Radar date-window joins when flag off |
| `author_affiliation/repository.py:fetch_paper` | `FETCH_PAPER_SQL_RADAR` when flag off |
| `hf_signals/stage.py:_lookup_content_items` / `run_window` | Radar arXiv lookup when flag off |
| `scripts/run_stage.py:_run_normalize` | Radar + `PI_ELIGIBLE_STATUSES` when flag off |

---

## Compatibility writes

| File:function | What |
|---|---|
| `ingest/repository.py:upsert_item` / `upsert_paper_metadata` | Radar `content_items` / `paper_metadata` |
| `ingest/arxiv_oai.py:checkpoint_*` | Radar `backfill_checkpoints` |
| `relevance/stage.py:_set_status` / `_set_relevance_version` | Gated by `PI_WRITE_RADAR_COMPAT` |
| `relevance/stage.py:_store_relevance` | Radar `content_scores` / `content_topics` (ungated historically) |
| `cache/s3_archive.py` | Radar `s3_archives` index |

---

## Test / dev-only

| File | Role |
|---|---|
| `scripts/shadow_catalog_*.py`, `canary_pi_catalog_oneday.py` | Shadow / canary |
| `scripts/backfill_pi_papers.py`, `validate_pi_catalog_backfill.py` | One-shot backfill |
| `scripts/dry_run_quality_status_coupling.py` | Diagnostic |
| `tests/unit/test_catalog_cutover.py`, affiliation/quality router tests | Unit |
| `tests/integration/test_normalize_authors.py` | Live Radar fixture |

---

## Obsolete

| Item | Why |
|---|---|
| `db/results.py:REQUIRED_UPSTREAM_STATUS` | Defined; zero call sites |
| `db/results.py:EXCLUDED_UPSTREAM_STATUSES` | Documented; unused in SQL |
| Architecture markdown / prompts | Narrative only |

---

## FK inventory (unchanged)

`item_stage_runs`, `external_requests`, `paper_authors`, `papers_people`, `paper_author_affiliations`, `paper_classification_results`, `paper_intelligence_current`, `golden_set_items`, `golden_labels`, `evaluation_results`, `paper_hf_signals` → `research_radar.content_items(id)`.

Migration `006` does **not** migrate/drop these FKs.

---

## Status after pre-final write-path phase (2026-09-19)

Addressed behind `PI_USE_PAPERS_CATALOG=1` (default still OFF):

1. **Ingest** — PI `papers` first; PI `ingest_checkpoints` control resume; Radar dual-write best-effort.
2. **Relevance candidates** — PI papers without current relevance (no `INGESTED` gate).
3. **Report/editorial** — newsletter/LinkedIn, generate_report, audience tops, HF validate, org_coverage dual-path.
4. **Normalize / affiliation runner / nomination / golden** — dual-path.

Still deferred to **final** cutover:

5. Schema FKs → Radar `content_items`.
6. Code default `PI_USE_PAPERS_CATALOG=1`.
7. `PI_WRITE_RADAR_COMPAT=0` + remove rollback branches.
8. Reject archive off Radar `s3_archives`.
