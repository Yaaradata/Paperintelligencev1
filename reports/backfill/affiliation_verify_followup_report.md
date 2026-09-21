# Affiliation verification follow-up — OA errors, HTML audit, ROR, pilot

**Scope:** post–Sep 1–15 targeted run (6504 papers). No full-corpus PDF/OA refresh. No paid LLM. No bulk rewrite of accepted affiliations. No automatic HTML∪OA merge.

---

## 1. Root causes of the 66 OpenAlex fetch errors

| Cause | Count |
|---|---:|
| HTTP 404 (`arxiv_datacite_doi` path) | **66** |
| timeout | 0 |
| connection/DNS/TLS | 0 |
| auth/config | 0 |
| response parsing | 0 |
| other HTTP | 0 |

All 66 used strategy `arxiv_datacite_doi` (`10.48550/arxiv.{id}`). Representative error: `http_404` (e.g. `2609.14005`, `2609.14180`).

### A / B / C distinction (Phase 2 empty cohort)

| Class | Meaning | Count |
|---|---|---:|
| **A** | Valid Work, zero institutions | **907** |
| **B** | No matching Work (DOI 404 / search identity fail) | **66** (+ retries below) |
| **C** | Request failed → institution availability UNKNOWN | **0** among the 66 (clean 404, not transport failure) |

**Never classified failed fetches as “OA has no institutions”.**

---

## 2–3. OpenAlex retry + incorrect cache

| Metric | Value |
|---|---:|
| Incorrectly cached failed lookups | **0** (404 responses are not written to raw_store) |
| Retry queue | 66 |
| Direct retry wall | **169.3 s** |
| After title-search + identity validation | with institutions **23** · zero institutions **21** · no work **18** · fetch failed **4** |
| Verify overlay outcomes | OA-primary **23** · unresolved **43** |
| 429 / retries | **0 / 0** |

**Fixes shipped:**
- Reject error-shaped cache payloads in `get_work`
- Do not cache non-200 bodies
- Title-search fallback after DataCite 404
- Strict `validate_work_identity` (DOI / arXiv URL / high title Jaccard) — **do not trust `arxiv_datacite_doi` alone**

---

## 4. HTML-primary audit (5430 papers)

**HTML-primary ≠ canonical org verified correct.**

### Paper-level (mutually preferential bucket)

| Bucket | Papers |
|---|---:|
| Canonical `organisation_id` linked | **4638** |
| Valid organisation text, not linked | **605** |
| Provisional normalised name only | **187** |
| Ambiguous / truncated / non-org / mapping uncertain as primary | **0** in this preference order (those tags appear on rows; papers usually also have linked or valid text) |

### Evidence-row counts (HTML/explicit rows on HTML-primary papers)

| Bucket | Rows |
|---|---:|
| Canonical linked | **62914** |
| Valid organisation text (unlinked) | **32394** |
| Provisional-name-eligible | **43741** |
| Ambiguous institution name | **8363** |
| Truncated affiliation text | **1378** |
| Non-organisation text | **3486** |
| Department-only | **2721** |
| Total rows examined | **~113k** |

---

## 5. HTML / ROR fixes and tests

**Implemented:** `html_resolve.py` — country-suffix stripping, punctuation normalisation, department-prefix peel, local name/alias lookup (no network).

**ROR pass (grounded, stage policy):** top 30 unlinked strings → **7** grounded alias/org updates (**1** org created, **18** aliases), **23** skipped (ungrounded ROR ranking / ambiguity / truncation). Removed unsafe aliases for truncated `University of Science and Technology of` → false Korea UST match.

| Test set | Already linked | Newly resolvable after fixes |
|---|---:|---:|
| Original 33 OA-primary | 0 | **0** (mostly short/weird/non-org text) |
| Current 15 conflicts | 0 | **0** (provisional vs OA naming mismatch) |
| HTML-primary sample 80 | 61 | **+1** |
| Unresolved sample 40 | 0 | 0 |

**Root causes of unlinked HTML:** institution aliases / “The …” prefixes; multi-campus ambiguity (`University of California`); truncated extraction; ROR affiliation API false positives without grounding; department-only / non-org text; companies poorly covered.

**Additional correctly linkable (estimate):** ~1/80 HTML-primary sample after alias pass ≈ **~1%** of unlinked-valid (~6 of 605) without writing affiliation rows. Full DEEP re-affiliation not run (would bulk-change evidence — out of scope).

---

## 6. Updated classification of unresolved (698 after OA retry overlay)

| Next actionable reason | n |
|---|---:|
| OpenAlex valid Work but no institutions | **678** |
| OpenAlex no matching Work | **16** |
| OpenAlex lookup failed | **4** |

Not auto-sent to manual review. High-value subset → PDF/HTML queue only.

---

## 7. PDF pilot (≤20)

**Method:** existing `external.arxiv_html` re-fetch (no PDF binary library installed; **$0**; no LLM).

| Metric | Value |
|---|---:|
| Pilot size | **20** |
| Wall | **11.1 s** (~0.55 s/paper) |
| Confirms prior HTML | 1 |
| Differs from stored HTML | 5 |
| New affiliation text recovered | **13** |
| Still empty (true PDF needed) | 1 |
| Est. full 295 queue runtime | **~2.7 min** HTML-path |
| Est. API/LLM cost | **$0** |

Binary PDF extraction not available without adding a dependency; recommend HTML-first for remaining queue, PDF only when HTML empty.

---

## 8. Author-level conflicts (re-checked)

On local-version conflict papers (34):

| Metric | n |
|---|---:|
| Author pairs examined | 133 |
| Pairs with both HTML+OA **org ids** | **25** |
| Disjoint | **25** |
| Genuine affiliation conflicts | **25** |
| Comparison/canonicalisation artifacts | **0** |

Earlier **49/55** included weaker joins; with org-id requirement the genuine disjoint set is **25**.

---

## 9. Updated exact / partial / conflict / unresolved

| Outcome | Count |
|---|---:|
| Exact agreement | **4** |
| Partial | **0** (still in PDF review overlay) |
| Conflict | **15** |
| Unresolved | **698** |
| HTML-primary | **5430** |
| OA-primary | **62** (was 41; +23 from OA retry) |
| Needs PDF review | **295** |

---

## 10. Additional correctly linked canonical organisations

- **1** org created + **~18** aliases (minus 2 unsafe truncated aliases removed)
- **+1** paper in HTML sample newly locally resolvable
- **+23** papers gained OA institutions via retry (verify outcome OA-primary) — evidence in verification JSON only; **affiliation tables not bulk-updated**

---

## 11. Remaining high-priority manual review

**310** = conflicts (15) + PDF queue (295) + quality-selected unresolved (overlap removed in set).

---

## 12. Remaining PDF queue estimate

| Path | Runtime | Cost |
|---|---|---|
| HTML re-fetch for 295 (measured pilot) | **~2.7 min** | **$0** |
| True PDF binary (not implemented) | unknown; need `pypdf`/`pdfminer` | **$0** if local extract |
| LLM adjudication | not proposed | would require separate approval |

**Stopped** after fixes, reclassification, and 20-paper HTML pilot. Did not process all 295 PDFs. Did not launch full-window OpenAlex refresh. Did not bulk-change accepted affiliations.

### Artifacts
- `oa_fetch_error_audit.json`, `oa_fetch_retry_66.json`
- `followup_html_audit.json`, `followup_resolve_tests.json`, `followup_ror_alias_pass.json`
- `followup_unresolved_reasons.json`, `followup_author_conflicts.json`
- `followup_pdf_html_pilot.json`, `followup_recompute.json`
