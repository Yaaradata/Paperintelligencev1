# Quality all-survivors dry-run — Sep 1–21 (no paid calls)

**Generated:** 2026-09-23  
**Router:** `ROUTER_SCORE_ALL_SURVIVORS=true` (default) → reason `selected_all_survivors`  
**Model map:** Terra-only (`pre=post=openai/gpt-5.6-terra`, cutover `2000-01-01`)  
**Cap default:** `--max-cost-usd 25`

## Counts

| Metric | N |
|---|---:|
| Screen survivors (quality candidates) | 9850 |
| Already have current Terra quality (skipped) | 1648 |
| **Remaining to score** | **8202** |

## Cost projection (quality only)

| Estimate | Amount |
|---|---:|
| Table / pipeline projection | **~$76.88** (~1641 batches × Terra table rates) |
| Calibrated from Sep16–21 actual ($1.2344 / 380 ≈ $0.00325/paper) | **~$26.66** |

`--max-cost-usd 25` is below the table projection; a paid fill needs a higher cap (e.g. **80** table / **30** calibrated) and/or `--force-over-projection`.

No paid re-score started.
