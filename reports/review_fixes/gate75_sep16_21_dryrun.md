# GATE_PERCENTILE=75 dry-run — Sep 16–21

**Date:** 2026-09-22 · **Scope:** day · **Notable-org:** FAST-tier evidence types (excl. society emails)

## Router recount (items 2–3)

| Metric | Count |
|---|---:|
| Screen survivors | 2535 |
| Notable FAST-tier OOI (post society fix) | **264** |
| Top 15% slice | 380 |
| Notable ∩ top 15% | **70** (was 0 — stage_version dedupe bug) |
| `selected_top_slice_and_notable_org` @15% | **70** |
| Top 75% slice | 1901 |
| Union @75% (top ∪ notable) | **1928** |
| Society email OOI papers excluded | 9 |

**Root cause of ∩=0:** FAST re-emit deduped against deep rows and left `stage_version=v002`. Router now keys on FAST evidence types (`explicit_paper_affiliation`, `email_domain`, `oai_author_affiliation`), not stage_version alone.

**Watchlist (ask before removing):**
- **IEEE Standards Association** — on `config/organisations.yaml` (`ieee.org`, `standards.ieee.org`), OOI=true. **Not removed.**
- **ACM** — not on yaml.

Email-domain matches for ieee.org/acm.org/iso.org/… are excluded from FAST/deep resolution and notable-org.

## Candidates @75%

| Day | Candidates | Already Terra-scored | New |
|---|---:|---:|---:|
| 2026-09-16 | 392 | 120 | 272 |
| 2026-09-17 | 393 | 116 | 277 |
| 2026-09-18 | 365 | 110 | 255 |
| 2026-09-19 | 191 | 61 | 130 |
| 2026-09-20 | 231 | 68 | 163 |
| 2026-09-21 | 356 | 106 | 250 |
| **Total** | **1928** | **581** (window scored=582) | **1347** |

## Cost projection

| Basis | $/paper | ×1347 new |
|---|---:|---:|
| Table (pipeline dry-run) | ~$0.00937 | **$12.63** |
| Provider-actual (prior Terra blend $1.8382/582) | ~$0.00316 | **~$4.25** |

Table ≤ $15 → **proceed** with `--allow-paid --max-cost-usd 10` (+ `--force-over-projection` so table>$10 does not refuse; spend still capped at provider $10).

Log: `gate75_sep16_21_dryrun.log`
