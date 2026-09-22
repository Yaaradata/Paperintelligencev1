# Phase 7 amendments (recorded; not started)

Recorded during Phase 2 approval. Do **not** implement until Phase 6 is done
and Phase 7 is explicitly started. Supersedes conflicting text in the original
Phase 7 brief.

## Background

In `reports/business_top_20_2026-09-01_to_2026-09-15.md` the business pool was
339/1273, but only 32 had `enterprise_adoption`; 307 were sector-only. The
quality router ranks on technical_significance, novelty and evidence, so
product-type papers (user studies, deployment case studies, governance,
workflow) are likely filtered out before pools are built.

## Changes vs original Phase 7

### (a) Router — replace “must remain audience-blind”

Router **default** behaviour is unchanged in 7a.

Add an **optional** route `selected_product_slice`, behind flag
`ROUTER_PRODUCT_SLICE_PCT` (**default 0 = off**):

- Screen-passed papers in the top N% by `product_relevance` (using the same
  percentile scope as Phase 4) are added to the quality candidate set.
- Record it as its own routing reason.
- Tests: flag off → routing identical to today; flag on → only the union grows,
  never shrinks.

### (b) Additions to 7b validation

Using the ~100-paper sample plus router state, also report:

- How many papers with high `product_relevance` were screen-passed but
  `not_selected` by the current router (extrapolate to Sep 1–15).
- For `ROUTER_PRODUCT_SLICE_PCT = 5 / 10 / 15`: extra quality candidates per
  week and the dry-run quality cost.
- Projected PRODUCT pool size per week under the proposed `PRODUCT_POOL_MIN`,
  with and without the product slice.
- Include in the sample the **32** `enterprise_adoption` papers from Sep 1–10
  and **20** sector-only business-pool papers.

### (c) 7c decision + success criterion

In 7c, the product-slice setting is decided together with the pool thresholds.

**Success criterion:** at least **5 PRODUCT-pool candidates per weekly edition**
with `product_relevance` above threshold. Report **per-week counts**, not just
the total.
