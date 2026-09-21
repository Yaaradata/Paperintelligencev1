# Backfill count reconciliation (604 rows)

**Date:** 2026-09-21

## Headline numbers

| Claim | Value |
|---|---:|
| Radar-only in horizon before backfill | 29,609 |
| Unique `scope_coverage` papers now in PI | **29,609** |
| Incorrect “30,213 backfilled” total in readiness report | arithmetic double-count |

## What the 604 were

They were **not** an additional import beyond the 29,609.

| Field | Value |
|---|---|
| Count | 604 |
| Source | `arxiv_oai` only |
| Radar status | all `INGESTED` |
| Date range | 2026-06-01 … 2026-07-13 (602 in July, 2 in June) |
| Reason included | Same in-scope Radar-only set as the first pass |

### Why they appeared twice in the narrative

1. **First apply:** `missing_total=29,609`, reported `inserted_papers=29,607` + 2 DOI-collision retries.
2. After that pass, **604** of the original set were still absent (uncommitted / savepoint leftovers in the long first transaction — paper_ids around `99646+`).
3. **Second apply:** inserted those remaining **604**.
4. Readiness text incorrectly summed `29,609 + 604 = 30,213` as if the 604 were new. They were a **subset** of the original 29,609.

### Correct identity

```
unique_backfilled = 29,609
                 = first_pass_committed + doi_retries + second_pass_604
                 = original Radar-only count
```

## Safety checks (post-backfill)

| Check | Result |
|---|---|
| Duplicate canonical arXiv | **0** |
| Duplicate DOI | **0** |
| `paper_id ≠ legacy_content_item_id` | **0** |
| Non-`arxiv_oai` in scope backfill | **0** |
| Horizon Radar-only remaining | **0** |

**Verdict:** explained cleanly — proceed with cutover.
