# Parallel affiliation verification — Sep 1–15 results

**Generated:** 2026-09-21  
**Version:** `html-oa-v002` (45-paper run)  
**Artifacts:** `affiliation_verify_45_html_oa.json`, `affiliation_verify_benchmark.json`, `affiliation_verify_targeted_dry_run.json`

Full 12,149-paper OpenAlex refresh was **not** run. Targeted Sep execute is **not** launched.

---

## 1–6. 45-paper run (both HTML + OpenAlex)

| Metric | Value |
|---|---:|
| Papers processed | **45** |
| Exact (`verified_agreement`) | **6** |
| Partial (`partial_agreement`) | **4** |
| Disjoint / conflict | **2** |
| Unresolved | **0** |
| OA-primary (HTML orgs empty after canonicalize) | **33** |
| Wall seconds (workers=8) | **1.20** |
| Papers/minute | **2244** |
| Cache hits (PI evidence reuse) | **45 / 45 (100%)** |
| New OpenAlex API calls | **0** |
| 429 / retries | **0 / 0** |
| PDF fallbacks | **0** |
| Errors | **0** |

All 45 reused existing PI `openalex_paper_specific` evidence — no network refresh required.

### Investigation: 6 exact

| arXiv | HTML = OA org set |
|---|---|
| `2504.00285` | University of California San Diego |
| `2601.03163` | Masaryk Memorial Cancer Institute, Masaryk University |
| `2602.14048` | Peking University |
| `2603.22437` | Cornell Tech, Cornell University |
| `2605.16879` | Sichuan University |
| `2609.09002` | Polytechnique Montréal |

### Investigation: 4 partial

| arXiv | Pattern |
|---|---|
| `2510.20721` | HTML ⊂ OA — CMU shared; OA adds Fujitsu (CN/JP/US) |
| `2604.24622` | One shared (SUSTech); HTML has Tsinghua/UCAS; OA has USTC/XJTU/Nova |
| `2509.06285` | Both HKUST + USTB shared; OA adds Toronto / NUDT / Aerospace Institute |
| `2609.11486` | Near-duplicate naming — Lomonosov MSU vs also “Moscow State University” |

**Do not union** these sets; treat as complementary evidence.

### Investigation: 2 disjoint (conflict)

| arXiv | HTML | OA | Notes |
|---|---|---|---|
| `2601.10511` | National Security **Authority** | National Security **Agency** + UMD | Likely HTML mis-parse / near-homonym |
| `2603.02790` | University of Amsterdam | Clinical Research Consortium | Different evidence tiers; no automatic merge |

---

## 7. Worker benchmark (same 45, no network)

| Workers | Wall s | Papers/min | DB ms avg | HTML ms avg | OA wait | 429/retry |
|---:|---:|---:|---:|---:|---:|---:|
| 1 | 2.29 | **1178** | 3.3 | 6.4 | 0 | 0 |
| 4 | **1.18** | **2297** | 6.1 | 12.1 | 0 | 0 |
| 8 | 1.33 | 2033 | 13.4 | 31.0 | 0 | 0 |

Bench RSS ≈ **57 MB**. CPU ≈ 75% over the combined bench.

**Recommended workers: 4** — throughput peaked at 4; 8 was ~11% slower (DB claim/query contention). More workers are not better for this PI-evidence path.

---

## 8. Targeted Sep dry-run (not executed)

Deduplicated candidates meeting quality / OOI / newsletter / LinkedIn / low-confidence / ambiguous ROR / prior conflict / random audit:

| Metric | Value |
|---|---:|
| Total candidates | **6504** |
| Already verified (any complete) | **45** |
| Remaining to verify | **6459** |
| HTML available | **5116** |
| OA PI evidence | **82** |
| OA cached among remaining (sampled est.) | **~5908** |
| OA lookup required (est.) | **~514** |
| PDF likely required | **1388** |

Bucket sizes: quality_selected 1661 · notable_ooi 748 · newsletter/linkedin 4272 · low_confidence 5026 · ambiguous_ror 150 · conflict_prior 2 · random_audit 50.

### Projected runtime (PI/cache-first throughput from bench)

| Workers | ppm (source) | Est. minutes for 6459 |
|---:|---:|---:|
| 1 | 1178 measured | **5.5** |
| 4 | 2297 measured | **2.8** |
| 8 | 2033 measured | **3.2** |
| 16 | 2297 capped at best | **2.8** |

**Caveat:** these minutes assume the same fast path as the 45-run (PI/cached OA, no PDF). Enabling network for ~514 OA lookups (bounded by `OPENALEX_MAX_CONCURRENCY=4`) and any future PDF path will dominate wall time beyond these figures. Est. new OA API calls if cache misses hold: **~514**.

---

## 9. Bottleneck

For cache/PI verification: **Postgres claim + HTML affiliation reads**, not OpenAlex. Scaling past 4 workers increases per-paper DB/HTML latency and lowers aggregate ppm.

When network is enabled for the targeted set: **OpenAlex semaphore (≤4)** becomes the limiter for the ~514 lookup subset; do not raise worker count to push OA harder.

---

## 10. Exact recommended parallel command

```bash
cd /home/ubuntu/Paperintelligencev1/worktrees/subha
set -a; source /home/ubuntu/Paperintelligencev1/.env; set +a
set -a; source /home/ubuntu/Research_Radar1/.env; set +a
unset PG_DSN PG_DSN_RO
export PI_USE_PAPERS_CATALOG=1 PI_WRITE_RADAR_COMPAT=0
export AFFILIATION_VERIFY_WORKERS=4
export OPENALEX_MAX_CONCURRENCY=4
export PDF_MAX_CONCURRENCY=3
export PYTHONPATH=src

# After review — enqueue + verify targeted set (example; do not run until approved):
# PYTHONPATH=src python3 scripts/verify_affiliations.py \
#   --workers 4 \
#   --verification-version html-oa-targeted-v001 \
#   --from 2026-09-01 --until 2026-09-15 \
#   --resume \
#   --output reports/backfill/affiliation_verify_targeted_run.json

# Resume-safe 45-paper style (already complete for html-oa-v002):
PYTHONPATH=src python3 scripts/verify_affiliations.py \
  --set both-sep \
  --workers 4 \
  --verification-version html-oa-v002 \
  --resume \
  --from 2026-09-01 --until 2026-09-15
```

Targeted execute is **withheld pending review** of these numbers.
