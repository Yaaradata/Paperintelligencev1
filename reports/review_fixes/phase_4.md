# Phase 4 stop report — Deterministic router + judge-effective orgs

**Branch:** `dev/subha`  
**Date:** 2026-09-22  

Independent of Sol/Terra decision. **Default scope unchanged (`window`).**

---

## What changed

1. **`ROUTER_PERCENTILE_SCOPE`** (`window` \| `day`, default `window`) in config / `.env.example`.
2. **Day mode:** top-N% computed per UTC `published_at` date; window mode = prior behaviour.
3. **Shared ranking** via `_rank_screen_survivors` / `_top_slice_ids`; `explain_quality_routing` and `select_quality_candidates` use the same path.
4. **`QualityRoutingDecision.percentile_scope`** recorded (flows into adjudication JSON).
5. **Notable-org** uses judge-effective exclusions by default (`apply_judge_effective=True`); stored affiliations untouched. Raw OOI available via `apply_judge_effective=False` for comparison.
6. **`latest_screen_scores`** (PI + Radar paths) now return `published_at`.
7. **`scripts/compare_router_modes.py`** → `reports/review_fixes/router_mode_comparison.{md,json}`.

---

## Comparison (Sep 1–15)

| Mode | Selected | + / − vs `window+judge` | + need quality (dry-run $) |
|---|---:|---:|---|
| `window+judge` (baseline / default) | 1661 | 0 / 0 | — |
| `window+raw_ooi` | 1661 | 0 / 0 | — |
| `day+judge` | 1667 | +90 / −84 | 0 (all 90 already have reusable Sol quality) |
| `day+raw_ooi` | 1667 | +90 / −84 | same |

Judge-effective did not change the notable-org set on this window (`raw == judge`). Day scope reshuffles ~90 ids in / 84 out vs window.

## Files

| Path | Role |
|---|---|
| `src/paper_intelligence/common/config.py` | `ROUTER_PERCENTILE_SCOPE` |
| `src/paper_intelligence/quality/stage.py` | Day/window + judge-effective router |
| `src/paper_intelligence/db/results.py` / `catalog/shadow.py` | `published_at` on screen rows |
| `scripts/compare_router_modes.py` | Read-only comparison |
| `tests/unit/test_quality_router.py` | Day invariance, judge reject, select≡explain |
| `reports/review_fixes/router_mode_comparison.*` | Sep 1–15 numbers |
| `reports/review_fixes/calibration_cutover_checks.md` | Calibration + cutover (separate) |

---

## Tests

- Day scope: 1-day vs 2-day window → same per-day picks  
- Judge-rejected OOI no longer selects  
- `select` ids == `explain` selected  
- Existing router cases still pass  

**Full unit suite:** `186 passed`.

---

## Behaviour

- Production default still **window** scope.  
- Notable-org now respects resolved judge rejects (aligned with adjudication).  
- Flip to day only after you choose (set `ROUTER_PERCENTILE_SCOPE=day`).

---

## STOP

Phase 4 complete. Awaiting approval before Phase 5.  
**Also awaiting your Sol/Terra cutover decision** (see `calibration_cutover_checks.md` — recommend Sol everywhere; do not change `v001.yaml` yet).
