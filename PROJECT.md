# PaperIntelligenceV1 — Project

**Updated:** 2026-09-17  
**Worktree:** `worktrees/subha` (`dev/subha`)

Single project source of truth (Context/State/Backlog point here).

---

## Pipeline

```
ingest → relevance → normalize → screen → audience_domain → quality
  → affiliation → hf_signals → adjudication → reports
```

HF is enrichment only (no duplicate papers). **`final_score` is not influenced by HF.**

---

## HF validation (complete)

- Field rename: `hf_trending_rank` → `hf_daily_upvote_rank` (migration 004)
- 30-day window: **2026-08-18 → 2026-09-16**
- Reports: `docs/hf_validation.md`, `reports/hf_validation_30d.json`, cohort CSVs
- Script: `scripts/validate_hf_signals.py`
- Measured recommendation: **no incremental signal** on this window
  (BOTH avg final_score 7.72 vs OURS_ONLY 7.57; BOTH is only 132 of 1820 high-quality)

Do **not** add HF into `final_score` until a later window replicates a stronger lift.

---

## Backlog

| ID | Item | Status |
|---|---|---|
| S-HF-VAL | 30d overlap + ranking comparison | **Done** |
| S-AFF-GAP | Affiliation footnote re-pass | Next |
| S-1DAY | One previous day E2E test | Next |
| S-OVERNIGHT | 1–2 week historical overnight | After 1-day OK |
| S-HF-SCORE | Consider HF in final_score | Blocked on stronger evidence |
| S-GOLDEN / S-PEOPLE / photo-OCR | Deferred / not doing | — |

### Closed

| Item | Note |
|---|---|
| HF enrichment stage | Done earlier |
| `hf_daily_upvote_rank` rename | Done |
| HF validation reports | Done — see `docs/hf_validation.md` |
