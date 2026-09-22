# STEP A — Sep 16–21 preview (dry-run STOP)

**Date:** 2026-09-22 · **Branch:** `dev/subha`  
**Audience stage:** SKIPPED  
**Quality model map:** CONFIRMED cutover `2026-09-16` → Terra  
**Router default:** `ROUTER_PERCENTILE_SCOPE=day` (commit `6d12737`)

---

## Decisions recorded

1. **Cutover confirmed** in `policies/quality_models/v001.yaml` (Sol pre / Terra post, 2026-09-16). Sep 1–15 Sol pending **not** filled.
2. **Terra fill math:** `$15.09` was for **1610** candidates missing Terra (`1610 × ~$0.0094`), not the **453** Sol-pending. Clarified in `sol_terra_fill_math.md`.
3. **Phase 4 headline (Sep 1–15):**

| Mode | Selected | Δ vs window+judge |
|---|---:|---|
| window+judge (old default) | 1661 | — |
| day+judge | 1667 | +90 / −84 |

No problem signal (near-parity; +90 already had Sol quality). **Day is now the default.**

---

## Harvest coverage

| Signal | Value |
|---|---|
| Latest OAI datestamp in `papers.raw_metadata` | **2026-09-22** |
| Latest completed ingest checkpoint window | **2026-09-22** (COMPLETE) |
| Max `ingested_at` | 2026-09-22 06:21 UTC |

### Papers by `published_at` (Sep 16–21)

| Day | Papers | Likely complete? |
|---|---:|---|
| 2026-09-16 | 867 | Yes (harvest through +6d) |
| 2026-09-17 | 869 | Yes |
| 2026-09-18 | 793 | Likely |
| 2026-09-19 | 427 | **Partial** — count dip; lag window |
| 2026-09-20 | 466 | **Partial** — lag |
| 2026-09-21 | 724 | **Partial** — announced ≤1d ago |
| **Total** | **4146** | |

**Flag:** With today = 2026-09-22 UTC and 1–3 day OAI announcement lag, **Sep 19–21 are likely still incomplete**. Treat the window as a **partial preview**, not a final edition.

---

## Free prereqs run (live, $0)

Needed so screen/quality projections are real:

| Stage | Result |
|---|---|
| relevance | **2638 keep** / reject remainder of 4146 |
| normalize_authors | **2638 succeeded** |

---

## Paid dry-run projections (no `--allow-paid`)

| Stage | Candidates / notes | Projected $ |
|---|---|---|
| **screen** (`z-ai/glm-5.3-flash`) | **2638** | **~$0.22** |
| affiliation_fast | after screen survivors (free) | $0 |
| **quality** (Terra via map, day scope) | **~$585** after screen\* | **~$5.50** table / ~$1.93 if calib actual/paper |
| affiliation_deep | quality-scored only (mixed free/paid APIs) | not LLM-capped here |
| hf_signals | free | $0 |
| adjudication | free | $0 |
| audience_domain | **SKIPPED** | — |

\*Quality dry-run reports **0** today because no screen rows exist yet; N≈585 = `2638 × Sep1–15 gate pass rate (97.3%) × day-scope select rate (22.8%)`. Terra unit ≈ `$0.0094` (table) from Sep full projection.

**Estimated paid total (screen + quality):** ~**$5.7** (table) — under proposed `--max-cost-usd 10`.

---

## Proposed paid command (awaiting approval)

```bash
unset QUALITY_MODEL
export PI_USE_PAPERS_CATALOG=1 ROUTER_PERCENTILE_SCOPE=day
export SCREEN_MODEL=z-ai/glm-5.3-flash CLASSIFY_MODEL=z-ai/glm-5.3-flash
PYTHONPATH=src python3 scripts/run_pipeline.py \
  --from 2026-09-16 --until 2026-09-21 \
  --stages screen,affiliation_fast,quality,affiliation_deep,hf_signals,adjudication \
  --allow-paid --max-cost-usd 10
```

(relevance + normalize already done)

---

## STOP

Awaiting approval to run the paid Sep 16–21 preview (no audience).  
Then STEP B = Phase 7a (build, no LLM).
