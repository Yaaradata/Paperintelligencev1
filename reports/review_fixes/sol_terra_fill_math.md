# Sol vs Terra backfill projection — math corrected

**Date:** 2026-09-22

## What was wrong in the earlier summary

The line **"Fill Terra $15.09" for 453 Sep 1–15 papers** mixed two different denominators.

| Figure | Meaning | N | Cost |
|---|---|---:|---:|
| `need_sol` | Router candidates **without a Sol** quality row | **453** | Fill Sol ≈ **$10.56** |
| `need_terra` | Router candidates **without a Terra** quality row | **1610** | Fill Terra ≈ **$15.09** |
| Unit $/candidate | `proj_full_terra / 1661` | 1661 | ≈ **$0.0094** |

Check: `1610 × $0.0094 ≈ $15.13` ✓ — the $15.09 is for **rescored-as-Terra all candidates missing Terra**, not the 453 Sol-pending papers.

If you only Terra-scored the 453 Sol-pending papers: `453 × $0.0094 ≈ **$4.26**` (not $15).

**Decision (confirmed):** do **not** fill those 453 Sep 1–15 Sol-pending candidates. Leave Sol scores as-is for that edition.

Raw numbers remain in `sol_terra_backfill_projection.json` (unchanged); this note clarifies the labels.
