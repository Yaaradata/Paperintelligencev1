# Phase 3b stop report — Quality model by date + stale content

**Branch:** `dev/subha`  
**Date:** 2026-09-22  

---

## 0. Phase 2b confirmation

**Merged.** Commit `d8a70e0` (`fix(cost): use verified OpenRouter prices and provider-reported spend`) is an ancestor of HEAD. Report: [`reports/review_fixes/phase_2b.md`](phase_2b.md).

---

## What changed

### 1. Quality model by date range (Sol / Terra)

- **Policy:** `policies/quality_models/v001.yaml`  
  - `cutover_date: 2026-09-16` (proposed — confirm)  
  - pre → `openai/gpt-5.6-sol`  
  - post → `openai/gpt-5.6-terra`
- **Resolver:** `quality/model_policy.py` — `mapped_quality_model`, `resolve_quality_model`, `group_ids_by_quality_model`, override warn.
- **Wired into:** quality skip/reuse (per-paper model groups in `run_stage`), adjudication `quality_result_is_current`, Phase 2 model guard (mapping mismatch, not single env), nomination done-checks.
- **`QUALITY_MODEL` env:** override for one-off runs only; loud WARNING when it disagrees with the mapping. `.env.example` leaves it unset by default.
- **Reports:** `generate_report` + `generate_audience_tops` print which quality model(s) scored the pool and flag **MIXED** pools; funnel includes `stale_content`.

### 2. Explicit stale content

- Migration **017:** `quality_status` CHECK adds `stale_content`.
- Adjudication derives `stale_content` when latest screen/quality row has non-NULL hash ≠ `papers.content_hash` (and versions+mapped model otherwise match).
- Run summary prints `stale_content=N` and `quality_models=…`.
- **`scripts/rescore_stale_content.py`:** dry-run by default; `--max-cost-usd` / `--allow-paid`; optional `--only-editorial`; rescored from drift set only.

### 3. `backfill_content_hash.py`

- Does **not** touch `modified_at`.
- Keyset batching: `paper_id > last_id LIMIT N` (default batch 1000).

### 4. Pre-016 revision report (read-only)

- **`scripts/report_pre016_revision_drift.py`:** legacy `input_content_hash IS NULL` where `papers.source_updated_at > result.created_at`, counts by stage and month + dry-run rescore cost. **No rescore.**

### 5. Sol vs Terra calibration (PAID — not run)

- **`scripts/calibrate_sol_terra_quality.py`:** samples ~60 Sep 1–15 Sol-scored papers (stratified + top 20), dry-run Terra cost by default.
- With `--allow-paid` (needs your go-ahead): writes Terra under a **calibration `run_id`** (not current — adjudication still expects Sol pre-cutover). Reports Spearman, top-15 overlap, mean |Δ| per rubric dim, biggest disagreements.
- **Stopped before any paid call.** Re-run with `--allow-paid` only after you approve the dry-run cost.

---

## Files

| Path | Role |
|---|---|
| `policies/quality_models/v001.yaml` | Date → model map |
| `sql/migrations/017_stale_content_status.sql` | `stale_content` status |
| `src/paper_intelligence/quality/model_policy.py` | Resolver + pool summary |
| `src/paper_intelligence/adjudication/{quality_status,model_guard,stage}.py` | Mapped model + stale |
| `scripts/run_stage.py` / `run_pipeline.py` | Grouped quality; banners |
| `scripts/backfill_content_hash.py` | Keyset; no `modified_at` |
| `scripts/rescore_stale_content.py` | Optional rescore |
| `scripts/report_pre016_revision_drift.py` | Legacy revision report |
| `scripts/calibrate_sol_terra_quality.py` | Calibration (dry-run default) |
| `scripts/generate_report.py` / `generate_audience_tops.py` | Model + stale in reports |
| `tests/unit/test_quality_model_policy.py` | New unit tests |
| `.env.example` | QUALITY_MODEL override docs |

---

## Tests

- Mapped model pre/post cutover; spanning window groups Sol vs Terra  
- Sep 1–15 Sol stays current under Terra env default  
- Guard uses date map (no false alarm from env alone)  
- `stale_content` derivation; calibration sample + Spearman helpers  

**Full unit suite:** `183 passed`.

---

## Ops notes

```bash
# apply migration 017
PYTHONPATH=src python3 scripts/backfill_content_hash.py   # safe to re-run
PYTHONPATH=src python3 scripts/report_pre016_revision_drift.py
PYTHONPATH=src python3 scripts/calibrate_sol_terra_quality.py \
  --from 2026-09-01 --until 2026-09-15   # dry-run cost only
```

Confirm cutover date `2026-09-16` in `policies/quality_models/v001.yaml` before relying on Terra for new windows.

---

## STOP

Phase 3b complete. **No paid calibration run.** Awaiting approval (and optional go-ahead for item 5) before Phase 4.
