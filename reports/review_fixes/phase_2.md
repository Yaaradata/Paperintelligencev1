# Phase 2 stop report — Enforced budget cap (+ Phase 1 follow-ups)

**Branch:** `dev/subha`  
**Date:** 2026-09-22  
**Issue:** #2 — $10 ceiling was a human rule; unknown models priced at $0; glm-4.6 looked copy-pasted.  
**Also:** model pins / banners, adjudication QUALITY_MODEL stale guard, inconsistency reason, Phase 7 amendments recorded.

---

## What changed

### Pricing
- `model_prices()` raises `UnknownModelPriceError` for unknown models unless both `PI_PRICE_<SLUG>_IN` and `_OUT` are set. No silent $0 default.
- Paid stage / pipeline startup calls `require_model_priced` for screen, classify, and quality models.
- **`z-ai/glm-4.6`:** left in defaults with **TODO + comment** — values match glm-5.3-flash and **must be verified** against OpenRouter before trusting budget math. **Please confirm.**

### Budget cap
- `--max-cost-usd` on `run_stage.py` and `run_pipeline.py`; env `PI_MAX_COST_USD`.
- Pre-check: dry-run projection over cap → refuse (exit 2) unless `--force-over-projection`.
- Live: `BudgetCap` + incremental `run_batches` submission; stops **new** batches once actual ≥ cap; in-flight may finish.
- Pipeline: cap is **cumulative** across paid stages via a temp budget-state JSON; remaining passed as `--max-cost-usd` per stage.
- Status `stopped_budget_cap` written into pipeline/stage run metadata; exit non-zero.
- Run summary line: `budget: projected=… actual=… cap=… status=ok|stopped_budget_cap`.

### Model pins / banners (corrections)
- `.env.example`: `QUALITY_MODEL=openai/gpt-5.6-sol`, `CLASSIFY_MODEL=z-ai/glm-5.3-flash`, `SCREEN_MODEL=z-ai/glm-5.3-flash`.
- Every paid run and pipeline start prints  
  `models: screen=… classify=… quality=…`.
- Adjudication refuses if configured `QUALITY_MODEL` would stale existing current-version quality rows in the window (count printed), unless `--allow-quality-model-change`.

### Inconsistency (from Phase 1 follow-up)
- Succeeded attempt + no current quality row → `quality_status=pending`,  
  `selection_reason=inconsistent_attempt_without_result`; counted in adjudication summary.

### Phase 7
- Amendments only: `reports/review_fixes/phase_7_amendments.md` (product slice flag, 7b extras, weekly success criterion). **Not implemented.**

---

## Files touched

| Path | Role |
|---|---|
| `src/paper_intelligence/common/config.py` | Fail-fast prices; glm-4.6 TODO |
| `src/paper_intelligence/common/budget.py` | Cap helpers + ledger |
| `src/paper_intelligence/common/batch_runner.py` | Incremental submit + skip counts |
| `src/paper_intelligence/{screen,audience_domain,quality}/stage.py` | `max_cost_usd` |
| `src/paper_intelligence/adjudication/quality_status.py` | Inconsistency reason |
| `src/paper_intelligence/adjudication/model_guard.py` | Stale-by-model count |
| `src/paper_intelligence/adjudication/stage.py` | Inconsistency counter |
| `scripts/run_stage.py` / `run_pipeline.py` | Flags, banners, enforcement |
| `.env.example` | Model pins |
| `tests/unit/test_budget.py` | New tests |
| `tests/unit/test_quality_failures.py` | Inconsistency test |
| `reports/review_fixes/phase_7_amendments.md` | Phase 7 delta |
| `reports/review_fixes/phase_2.md` | This report |

---

## Tests

- Unknown model raises; env override works  
- Projection-over-cap condition  
- Cap stops further batches (mocked handlers)  
- Concurrent cost accumulation  
- Inconsistency reason  

**Full unit suite:** `155 passed`.

---

## Behaviour change

- Unpriced models cannot start paid work.
- Paid runs with a cap refuse or stop early instead of overspending unbounded.
- Adjudication blocks accidental QUALITY_MODEL switches that would blank scored windows.
- No change to scoring weights, prompts, or which papers the router selects.

---

## Open for you

1. **Confirm or correct** `z-ai/glm-4.6` OpenRouter in/out prices (currently unverified 0.15 / 0.50).
2. Phase 7 amendments file ready when you start Phase 7 after Phase 6.

---

## STOP

Phase 2 complete. Awaiting approval before Phase 3.
