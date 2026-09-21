# PI FK migration plan (prepare only — do not execute drops)

**Date:** 2026-09-21  
**Status:** Plan + orphan precheck only. Radar FKs **not** dropped in this phase.

## Goal

Retarget all PI child FKs from:

`research_radar.content_items(id)`

to:

`paper_intelligence.papers(paper_id)`

Because migrated/backfilled rows use `paper_id = legacy_content_item_id`, **no data rewrite** is required.

## Precheck (2026-09-21)

| Table | Orphan `content_item_id` not in `papers` |
|---|---:|
| item_stage_runs | 0 |
| external_requests | 0 |
| paper_authors | 0 |
| papers_people | 0 |
| paper_author_affiliations | 0 |
| paper_classification_results | 0 |
| paper_intelligence_current | 0 |
| golden_set_items | 0 |
| golden_labels | 0 |
| evaluation_results | 0 |
| paper_hf_signals | 0 |

## Proposed migration shape (future `008_pi_fk_retarget.sql`)

For each table `T` with `content_item_id`:

```sql
BEGIN;

-- 1. Re-verify orphans (must be 0)
-- SELECT count(*) FROM paper_intelligence.T x
-- WHERE x.content_item_id IS NOT NULL
--   AND NOT EXISTS (SELECT 1 FROM paper_intelligence.papers p WHERE p.paper_id = x.content_item_id);

-- 2. Add PI FK (NOT VALID first for online safety, then VALIDATE)
ALTER TABLE paper_intelligence.T
  ADD CONSTRAINT T_content_item_id_papers_fkey
  FOREIGN KEY (content_item_id)
  REFERENCES paper_intelligence.papers(paper_id)
  ON DELETE NO ACTION
  NOT VALID;

ALTER TABLE paper_intelligence.T
  VALIDATE CONSTRAINT T_content_item_id_papers_fkey;

-- 3. Only AFTER validation + soak: drop Radar FK
-- ALTER TABLE paper_intelligence.T DROP CONSTRAINT <radar_fk_name>;

COMMIT;
```

### ON DELETE policy

Prefer **`NO ACTION` / `RESTRICT`** over `CASCADE` so deleting a catalog paper cannot silently wipe enrichment history across systems.

### Tables / expected Radar FK names (from `001` / `003`)

Confirm exact constraint names with `\d paper_intelligence.<table>` before drop:

- `item_stage_runs.content_item_id`
- `external_requests.content_item_id` (nullable — SET NULL historically; keep nullable)
- `paper_authors.content_item_id`
- `papers_people.content_item_id`
- `paper_author_affiliations.content_item_id`
- `paper_classification_results.content_item_id`
- `paper_intelligence_current.content_item_id`
- `golden_set_items.content_item_id`
- `golden_labels.content_item_id`
- `evaluation_results.content_item_id`
- `paper_hf_signals.content_item_id`

## Rollback steps (if PI FK add fails)

1. `ALTER TABLE ... DROP CONSTRAINT T_content_item_id_papers_fkey;`
2. Leave Radar FK intact (never drop Radar FK in the same transaction as the first PI FK add until validated).
3. Investigate orphans / identity gaps before retry.

## Rollback steps (if Radar FK already dropped)

1. Re-add Radar FK only if every `content_item_id` still exists in `research_radar.content_items`.
2. If PI-only papers exist, Radar FK **cannot** be restored without excluding those IDs — another reason PI must stay authoritative after compat-off.

## Explicit non-goals this phase

- Do **not** drop Radar FKs yet
- Do **not** rename `content_item_id` → `paper_id` columns yet (optional later cleanup)
- Do **not** delete Radar tables
