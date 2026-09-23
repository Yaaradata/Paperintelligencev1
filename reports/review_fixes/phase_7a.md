# Phase 7a — STOP report

**Date:** 2026-09-22 · **Branch:** `dev/subha`  
**Status:** Build complete. No audience LLM run. Awaiting approval before 7b.

---

## What shipped

### 1. Shared seats (item 1 — already approved)
- `policies/editorial_seats/v001.yaml` — canonical TECH/PRODUCT
- Newsletter `newsletter_select_v002` / LinkedIn `linkedin_select_v002` load seats from it
- Seat file **unchanged** in this pass

### 2–7. Classification → pools

| Piece | Detail |
|---|---|
| Policy | `policies/classification/v002.yaml` — seat scores; no `audience_relevance` |
| Prompt | `prompts/audience_domain/v003.md` — injects `{{EDITORIAL_SEATS}}`; **per-paper** anchor language (“A high score (8+) means…”) only in the prompt |
| Stage | Dual path via `AUDIENCE_POLICY`; v002 → policy v002 + prompt v003 + stage v002 |
| Migration | **019** applied — `tech_relevance`, `product_relevance`, `audience_policy_version` on `paper_intelligence_current` |
| Adjudication | Fills seat columns from v002 rows only; never maps old labels |
| Pools | v002: `tech_relevance >= TECH_POOL_MIN`, `product_relevance >= PRODUCT_POOL_MIN`; both allowed; rank by **quality_score** |
| Product slice | `ROUTER_PRODUCT_SLICE_PCT` default **0** (off); opt-in union growth |
| Tests | **210** unit tests passing |

### Flags / defaults

| Flag | Default | Notes |
|---|---|---|
| `AUDIENCE_POLICY` | **v001** | Switch to `v002` in 7c after thresholds approved |
| `TECH_POOL_MIN` | **6.0** | Provisional until 7b |
| `PRODUCT_POOL_MIN` | **6.0** | Provisional until 7b |
| `ROUTER_PRODUCT_SLICE_PCT` | **0** | Off until 7c |

### Report ranking (item 3)
Tech/product top-N sort by **quality_score** (then final_score). Columns: quality, org_boost, final; org name as label. `final_score` formula unchanged.  
`PROJECT.md` open decision: **org_boost magnitude vs Terra score spread**.

---

## Notable-org route fix + Sep 16–21 catch-up

### Router filter (fixed)
Notable-org selection now requires:
- `affiliation_fast` rows only (`stage_version = v003`)
- `organisation_id IS NOT NULL` (resolved — excludes `review_required`)
- `is_org_of_interest`

Deep (v002 / ROR/OpenAlex) no longer feeds the pre-quality router.

### Recount

| Metric | Before (any stage) | After (FAST resolved only) |
|---|---:|---:|
| Notable-org survivors | 273 | **202** |
| Notable ∩ top-slice | 71 | **0** (those 71 were deep-only OOI on top-slice papers) |
| New quality candidates | 202 | **202** |
| Router union | 582 | **582** (380 top + 202 notable) |

### Precision sample (20)
See [`notable_org_fast_sample20.md`](notable_org_fast_sample20.md) — Tsinghua/CMU/MIT/Meta/Amazon/NVIDIA/Microsoft/Apple/Stanford/Berkeley/Mila look right; **IEEE via `@ieee.org`** appears twice (worth a watchlist precision check).

### Paid catch-up (approved, ≤$2)

| Stage | Result |
|---|---|
| quality Terra | **202 ok / 0 fail**, provider **$0.6038** (table est $0.56; under $2) |
| affiliation_deep | 582 items (re-run window) — resolved 474 / review 60 / no_ev 48 |
| adjudication | **582 scored** Terra; reasons: 380 `selected_top_slice` + 202 `selected_notable_org` |

Log: `sep16_21_notable_org_quality.log`

---

## Dry-run cost projections (`CLASSIFY_MODEL=z-ai/glm-5.3-flash`)

| Scope | N (screen-passed) | Est. $ |
|---|---:|---:|
| **(i) 7b validation sample** (~130 = ~100 stratified + past picks) | 130 | **~$0.02** |
| **(ii) Sep 16–21 full audience v003** | 2535 | **~$0.35** |
| Sep 1–15 full reclass (context; not this step) | 7315 | **~$1.02** |

Details: `phase_7a_cost_projections.json`

---

## Key files

```
policies/editorial_seats/v001.yaml
policies/classification/v002.yaml
prompts/audience_domain/v003.md
sql/migrations/019_seat_relevance.sql
src/paper_intelligence/audience_domain/{stage,vocabulary,pools}.py
src/paper_intelligence/quality/stage.py          # FAST-only notable-org + product slice
src/paper_intelligence/adjudication/stage.py
scripts/generate_audience_tops.py
src/paper_intelligence/common/config.py
tests/unit/test_phase7a_seats.py
```

---

## STOP

Awaiting approval to start **Phase 7b** (paid validation ≤$1 on the sample set).  
Do **not** set `AUDIENCE_POLICY=v002` default or run Sep 16–21 audience v003 until after 7b/7c.
