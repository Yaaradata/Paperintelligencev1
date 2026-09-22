# Calibration + cutover checks (pre–Phase 4)

**Date:** 2026-09-22  
**Policy file NOT changed** (`policies/quality_models/v001.yaml` still proposes 2026-09-16).

---

## 1. Post–Sep 15 quality rows (current versions)

Latest quality rows with `published_at >= 2026-09-16`, stage/prompt/policy `v001`:

| Model | Papers |
|---|---|
| *(none)* | **0** |

No Sol (or any) quality scores after Sep 15. Cutover to Terra would **not** stale existing rows today.  
(Sep 16–21 have ~4.1k ingested papers but **0** screen rows yet.)

---

## 2. Edition window / proposed cutover day

Evidence:

- `reports/newsletter_picks_2026-09-01_to_2026-09-15.json` → **Sep 1–15**
- August editorial was a full calendar month (`2026-08-01` → `2026-08-31`)
- `select_newsletter.py` takes arbitrary `--from/--until` (no hardcoded weekday)

**Operational edition for September:** half-month **1–15**, then **16–end**.

**Proposed cutover (if Terra is adopted):** **2026-09-16** — first day of the next half-month edition after Sep 1–15. That avoids a MIXED Sol/Terra pool inside one edition window.

*(Cutover still NOT confirmed — see calibration below.)*

---

## 3. Sol vs Terra calibration (PAID, approved ≤ $1)

| Metric | Value |
|---|---|
| Sample | 60 Sep 1–15 Sol-scored papers (stratified + top 20) |
| Dry-run estimate | ~$0.57 |
| **Actual provider cost** | **$0.1994** |
| Run id | `a4071bf8-db07-4e98-b5c0-08fa45afe681` |
| Spearman(final) | **0.806** |
| Top-15 overlap | **6 / 15** |
| Mean \|Δ final\| | 0.791 |

Mean \|Δ\| by rubric: tech 0.70, novelty 0.68, practical 0.60, professional 0.72, learning 0.51, evidence 0.79.

Biggest disagreements (Sol higher → Terra lower on these; see `sol_terra_calibration.md` for so_what pairs): LEXIC, MINERVA, MARCUS, Oversight Gap, BatchNorm Illusion, …

### Adoption criteria

- Spearman ≥ 0.75 → **pass** (0.806)
- Top-15 overlap ≥ 10/15 → **fail** (6/15)

**Recommendation: keep Sol for all dates** (map would say Sol everywhere). Do **not** confirm Terra cutover.

### Aug→Jan backfill cost (if staying on Sol vs switching to Terra)

Router candidates present in DB today:

| Window | Candidates | Already Sol | Fill Sol $ | Fill Terra $ | Full Sol $ | Full Terra $ |
|---|---:|---:|---:|---:|---:|---:|
| Aug 2026 | 47 | 47 | 0 | 0.44 | 1.10 | 0.44 |
| Sep 1–15 | 1661 | 1208 | **10.56** | 15.09 | 38.93 | 15.57 |
| Sep 16–Jan | 0* | — | — | — | — | — |

\*Sep 16–21 papers exist (~4.1k) but unpaid screen/quality not run yet.  
Unit cost / candidate (Sep 1–15 full): Sol **~$0.023** · Terra **~$0.009**.

Remaining Sep 1–15 Sol fill ≈ **$10.56**. Terra is cheaper per paper but fails the top-15 overlap bar for rank compatibility.

Full detail: `reports/review_fixes/sol_terra_calibration.{json,md}`, `sol_terra_backfill_projection.json`.

---

## Ops applied on DB (this session)

Migrations **014**, **015**, **016**, **017** + `backfill_content_hash.py` (69 197 rows). Needed for calibration / Phase 3b schema.
