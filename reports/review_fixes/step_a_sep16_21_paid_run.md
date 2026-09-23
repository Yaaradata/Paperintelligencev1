# STEP A — Sep 16–21 paid preview (complete)

**Date:** 2026-09-22 · **Branch:** `dev/subha`  
**Command:** `--stages screen,affiliation_fast,quality,affiliation_deep,hf_signals,adjudication --allow-paid --max-cost-usd 10` (no `audience_domain`)  
**Router:** `ROUTER_PERCENTILE_SCOPE=day` · **Quality map:** Terra post-cutover  
**Log:** `reports/review_fixes/sep16_21_paid_run.log`

---

## affiliation_deep cost (answered before / confirmed by this run)

| Signal | Detail |
|---|---|
| What it calls | **arXiv HTML** footnotes → **ROR** (`api.ror.org`) → **OpenAlex** (`api.openalex.org`) |
| PDF? | **No** — PDF probe lives in the separate verify/judge path, not `affiliation_deep` |
| OpenRouter / LLM? | **No** |
| In `PAID_STAGES`? | **No** (`screen`, `audience_domain`, `quality` only) |
| Counts toward `--max-cost-usd`? | **No** |
| Monetary cost | **$0** (public HTTP APIs; rate-limited / cacheable) |
| This run | 380 items · external: ROR 439, arXiv HTML 393, OpenAlex 111 · outcomes resolved 272 / review_required 60 / no_evidence 48 |

No uncapped dollar spend on this stage. Cap not needed.

---

## Per-day funnel

| Day | Papers | Rel keep | Screen ok | Screen pass | Router selected | Top-slice | Notable-org only | Both (top∩org) | Q scored | Q failed | Q pending | Q stale |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| 2026-09-16 | 867 | 539 | 539 | 514 | 77 | 77 | 0 | 16 | 77 | 0 | 0 | 0 |
| 2026-09-17 | 869 | 549 | 549 | 520 | 78 | 78 | 0 | 13 | 78 | 0 | 0 | 0 |
| 2026-09-18 | 793 | 493 | 493 | 479 | 72 | 72 | 0 | 12 | 72 | 0 | 0 | 0 |
| 2026-09-19 | 427 | 268 | 268 | 251 | 38 | 38 | 0 | 8 | 38 | 0 | 0 | 0 |
| 2026-09-20 | 466 | 311 | 310 | 303 | 45 | 45 | 0 | 7 | 45 | 0 | 0 | 0 |
| 2026-09-21 | 724 | 478 | 478 | 468 | 70 | 70 | 0 | 15 | 70 | 0 | 0 | 0 |
| **Total** | **4146** | **2638** | **2637** | **2535** | **380** | **380** | **0** | **71** | **380** | **0** | **0** | **0** |

Notes:
- **Top-slice** = `selected_top_slice` + `selected_top_slice_and_notable_org` (all 380).
- **Notable-org only** = 0 this window (day-scope top slice absorbed every notable-org survivor).
- Screen gate fails (pass=false): 102 total → adjudication `quality_status=skipped` / reason `blocked_screen_gate_failed`.
- Not selected below percentile: 2155.

---

## Cost: provider vs table estimate

| Stage | Candidates / calls | Table / pipeline est | Provider `actual_cost` | Cap impact |
|---|---|---:|---:|---|
| screen (`z-ai/glm-5.3-flash`) | 2638 / 176 | $0.2573 (proj $0.2187) | **$0.2504** | under $10 |
| quality (Terra) | 380 / 76 | $1.1525 (proj $3.5741) | **$1.2344** | under $10 |
| affiliation_deep / hf / adjudication | — | $0 | $0 | n/a |
| **Paid total** | | dry-run table ~$5.7 (assumed ~585 Q) | **$1.4848** | status=ok |

Dry-run overestimated quality N (~585 vs actual **380** day-scope) and Terra unit cost (table ~$0.0094 vs actual ~$0.0032/paper).

---

## Terra quality score distribution (n=380)

| Stat | Value |
|---|---:|
| mean | **7.71** |
| p50 | **7.70** |
| p90 | **8.10** |
| min / max | 6.7 / 8.8 |

Scale for this edition: scores cluster tightly around **~7.7**; p90 only **+0.4** above the median.

---

## Failures / stale_content

| Issue | Detail |
|---|---|
| Quality failed | **0** |
| `stale_content` | **0** (adjudication metadata) |
| Screen partial | **1** keep without screen row: `paper_id=199751` (2026-09-20) — *Scenario MPC with STL…* (`2609.23263`). Log: `WARN unexpected content_item_id 197751; missing ids: [199751]`. Stage exited 1; pipeline continued. |
| Other failed/stale papers | none in current for this window |

---

## Partial harvest days (still flagged)

Same as dry-run (today = 2026-09-22 UTC; 1–3d OAI lag):

- **2026-09-19** — partial (count dip)
- **2026-09-20** — partial
- **2026-09-21** — partial (announced ≤1d ago)

Sep 16–18 treated as complete for preview purposes.

---

## Pipeline outcome

```
=== pipeline complete ===
partial failures: screen=1
budget: projected=$0.2200 actual=$1.4848 cap=$10.0000 status=ok
```

affiliation_fast wrote **0** rows (`no_evidence_supplied` × 2535) — expected when OAI has no affiliation lines; deep stage recovered orgs for 272/380.
