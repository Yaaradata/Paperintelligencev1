# Phase 1 stop report — Explicit quality failures

**Branch:** `dev/subha`  
**Date:** 2026-09-22  
**Issue:** #1 — router-selected papers with no quality row were labelled `not_selected` / `pending_quality_score:…`; LLM/parse failures were indistinguishable from never-attempted papers; migration 005’s `failed` value was never written.

---

## Storage choice

**New table `paper_intelligence.quality_attempts` (migration 014)** — not `item_stage_runs`.

| Option | Why rejected / accepted |
|---|---|
| `paper_classification_results` | Would make `ids_with_result` treat failures as done → not retryable. |
| `item_stage_runs` | Batch/stage grain, not per-paper; no version/model/error shape for adjudication. |
| **`quality_attempts`** | Append-only per paper + stage/prompt/policy/model; status `succeeded`/`failed`; failures stay out of classification results so skip logic still retries. |

Migration 014 also extends `paper_intelligence_current.quality_status` CHECK to allow **`pending`**.

---

## What changed

1. **`quality/stage.py` `run_window`:** on batch exception, record a `failed` attempt for every paper in the batch; on partial parse, `succeeded` for parsed ids + `failed` for missing/invalid ids; successful rows still go to `paper_classification_results`.
2. **`adjudication`:** `quality_status` via `derive_quality_status`:
   - **scored** — quality row matches **current** stage/prompt/policy + model
   - **failed** — router `selected`, latest attempt for those versions failed, no current row
   - **pending** — router `selected`, no attempt yet (or succeeded attempt without a current row)
   - **not_selected** / **skipped** — unchanged
3. Stale-version quality rows no longer count as scored (scores/`with_quality` only from current versions).
4. Failures do **not** populate classification results → quality skip remains retryable.

---

## Files touched

| Path | Role |
|---|---|
| `sql/migrations/014_quality_attempts.sql` | Table + CHECK `pending` |
| `src/paper_intelligence/quality/attempts.py` | Insert/query helpers |
| `src/paper_intelligence/adjudication/quality_status.py` | Status derivation |
| `src/paper_intelligence/quality/stage.py` | Persist attempts in `run_window` |
| `src/paper_intelligence/adjudication/stage.py` | Wire derivation + attempt lookup |
| `tests/unit/test_quality_failures.py` | New unit tests |
| `reports/review_fixes/phase_1.md` | This report |

---

## Tests added

- batch exception → all ids `failed` attempts, no classification rows  
- partial parse → only missing ids `failed`; parsed `succeeded`  
- failed then current quality row → `scored`  
- selected, no attempt → `pending`  
- stale stage/model → not current / not scored  
- `not_selected` / `blocked` → unchanged  

**Full unit suite:** `146 passed`.

---

## Behaviour change

- Selected-but-unscored papers move from `quality_status=not_selected` + `pending_quality_score:…` to **`pending`**.
- After a failed quality call, status becomes **`failed`** with `quality_attempt_failed:…` in `selection_reason`.
- Historical quality rows with old versions/models no longer set `scored` or fill `quality_score`/`final_score` until re-run under current versions.

**Ops note:** apply migration **014** before running adjudication against a DB that needs attempt lookups / `pending` status (agents do not apply DDL).

---

## STOP

Phase 1 complete. Awaiting approval before Phase 2.
