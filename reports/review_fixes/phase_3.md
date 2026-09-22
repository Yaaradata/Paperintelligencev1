# Phase 3 stop report — Content-aware reuse

**Branch:** `dev/subha`  
**Date:** 2026-09-22  

**Model decision (from chat):** keep existing **Sol** quality scores for Sep 1–15; use **Terra** only for new windows. `openai/gpt-5.6-terra` added to `_DEFAULT_PRICES` ($2/$12). Default `QUALITY_MODEL` remains Sol; `.env.example` documents Terra for new days.

---

## What changed

1. **Fingerprint:** `compute_content_hash(title, abstract)` = sha256 of NFC + whitespace-collapsed title + abstract (`common/content_hash.py`).
2. **Migration 016:** nullable `papers.content_hash`, `paper_classification_results.input_content_hash`, append-only `paper_content_hash_changes`.
3. **Backfill script:** `scripts/backfill_content_hash.py` (no LLM).
4. **Ingest:** every OAI upsert recomputes `content_hash`; on change, logs previous/new hash, `arxiv_version`, timestamp.
5. **LLM stages** (screen, audience_domain, quality) write `input_content_hash` on new result rows.
6. **Reuse:** result reusable iff versions+model match **and** (`input_content_hash IS NULL` **or** equals `papers.content_hash`). NULL = legacy → **no mass rescore**.
7. **`latest_screen_scores` / adjudication latest results / `quality_result_is_current`:** ignore hash mismatches.
8. **Report (no rescore):** `scripts/report_content_hash_drift.py` — per-stage drift counts + dry-run rescore cost.

---

## Files

| Path | Role |
|---|---|
| `sql/migrations/016_content_hash.sql` | Schema |
| `src/paper_intelligence/common/content_hash.py` | Shared helper |
| `src/paper_intelligence/catalog/ingest.py` | Hash on upsert + change log |
| `src/paper_intelligence/db/results.py` | Insert + `ids_with_result` + radar screen latest |
| `src/paper_intelligence/catalog/shadow.py` | PI skip + screen latest |
| `src/paper_intelligence/{screen,audience_domain,quality}/stage.py` | Write hash |
| `src/paper_intelligence/adjudication/*` | Current quality + hash-aware latest |
| `scripts/backfill_content_hash.py` | Backfill |
| `scripts/report_content_hash_drift.py` | Drift report |
| `tests/unit/test_content_hash.py` | Unit tests |
| `src/paper_intelligence/common/config.py` / `.env.example` | Terra price + notes |

---

## Tests

- Hash stability / change detection  
- Skip SQL includes NULL-or-match clause  
- Insert carries `input_content_hash`  
- Legacy NULL → current; mismatch → not current  
- Ingest revision updates hash + change log  

**Full unit suite:** `171 passed`.

---

## Behaviour change

- After migrate + backfill: revised arXiv title/abstract invalidates reuse for that paper’s LLM stages (legacy NULL rows still reuse).
- **Does not** rescore anything by itself.
- Adjudication / quality routing ignore content-mismatched screen/quality rows.

---

## Ops before using this on DB

```bash
# apply migration 016 (ops), then:
PYTHONPATH=src python3 scripts/backfill_content_hash.py
PYTHONPATH=src python3 scripts/report_content_hash_drift.py \
  --from 2026-09-01 --until 2026-09-15 \
  --out reports/review_fixes/content_hash_drift.json
```

---

## STOP

Phase 3 complete. Awaiting approval before Phase 4.
