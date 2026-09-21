# Phased affiliation verification — Sep 1–15 final report

**Workers:** 4 · **OpenAlex concurrency:** 4 · **PDF concurrency:** 3  
**Versions:** `html-oa-targeted-local-v002` → `html-oa-targeted-oa-v001` → `html-oa-targeted-pdf-v001`  
**Original affiliation evidence was not overwritten.** Conflicting org sets were never unioned.

---

## 1. Root cause of the 33 OA-primary benchmark cases

**Systematic verification bug (fixed):** `load_html_orgs` ignored `evidence_value` when `organisation_id` was NULL, while the OpenAlex path used `evidence_value`. Combined with ROR non-links (~43% of window HTML/explicit rows lack `organisation_id`), HTML org sets appeared empty and papers were falsely labelled OA-primary.

**Classification of the original 33 (after inspection):**

| Class | n |
|---|---:|
| ROR lookup / canonicalisation miss (real org text, unlinked) | **29** |
| HTML evidence not actually an organisation (e.g. author name / independent) | **3** |
| HTML affiliation parsing failed (truncated e.g. `Laboratoire`, `University`) | **1** |

**Fix:** provisional org names from cleaned HTML `evidence_value` (noise filtered). Re-ran 45-paper set (`html-oa-v003-postfix`): OA-primary dropped **33 → 3**; most became **conflict** (string-level HTML vs OA naming mismatch — correct for no-merge policy).

Do **not** treat OpenAlex as correct merely because ROR failed to link.

---

## 2. Phase 1 — local/cache sweep

| Metric | Value |
|---|---:|
| Total processed | **6504** |
| Exact agreement | **4** |
| Partial agreement | **6** |
| HTML-primary | **5430** |
| OA-primary | **38** |
| Conflict | **34** |
| Unresolved | **0** |
| Needs OA network | **992** |
| Needs PDF | **0** |
| Wall time | **192.6 s (~3.2 min)** |
| Papers/min | **2026** |
| Errors | **0** |
| New OA API calls | **0** |

---

## 3–4. Phase 2 — OpenAlex network (actual queue = 992, not estimated 514)

| Metric | Value |
|---|---:|
| Queue (from Phase 1 `needs_openalex_lookup`) | **992** |
| Cache hits | **924** |
| New API calls | **68** |
| 429 / retries | **0 / 0** |
| Fetch errors | **66** |
| OA with institutions | **19** |
| OA without institutions | **973** |
| Wall time | **191.2 s (~3.2 min)** |
| Papers/min | **311** |
| Post-OA outcomes | unresolved **973**, OA-primary **19** |

Priority mix in queue: quality 259 · newsletter/LinkedIn 669 · low-confidence 38 · other 26.

**OpenAlex mismatch note:** Most cached/API works for this unresolved subset return **no institutions**. Cache hit ≠ usable affiliation evidence.

---

## 5–6. Phase 3 — PDF queue (tightened; no mass download)

| Metric | Value |
|---|---:|
| PDF queue size (after OA) | **295** (not 1388) |
| PDFs downloaded / extracted | **0 / 0** |
| Persisted as `needs_pdf_review` | **295** |

Queue reasons: unresolved quality-selected 254 · disjoint HTML/OA 19 · newsletter uncertainty 25 · OA-primary notable no HTML 16 · partial extras 6 · notable-org uncertainty 2.

PDF text extraction is **not implemented in v001**; queue is ready for primary-source follow-up. HTML preferred when it already had org evidence.

---

## 7. Final outcome counts (merged phases)

| Outcome | n |
|---|---:|
| Exact (`verified_agreement`) | **4** |
| Partial | **0** (6 moved into PDF review queue) |
| Conflict | **15** (19 important conflicts → PDF queue) |
| Unresolved | **719** |
| HTML-primary | **5430** |
| OA-primary | **41** |
| Needs PDF review | **295** |

---

## 8. Author-affiliation conflicts

On remaining paper-level **conflict** set (15 papers): **55** author pairs with both HTML+OA org ids; **49** author-level disjoint; **0** author-level partial on that subset.

---

## 9. HTML extraction / canonicalisation bugs found

1. **Verification asymmetry** (fixed): HTML path dropped unlinked `evidence_value`.
2. **ROR gap:** large share of explicit HTML affiliations never get `organisation_id` (window ~49k/114k rows unlinked).
3. **Parse truncations:** values like `Laboratoire`, `University`, `École`.
4. **Non-org HTML strings:** author names / “Independent Researcher…” stored as affiliation text.

---

## 10. OpenAlex mismatches found

- Naming mismatch vs provisional HTML (e.g. `Baidu, Inc., Beijing, China` vs `Baidu (China)`).
- Homonym / wrong org (e.g. NSA vs National Security Authority).
- Cached works frequently have **empty institution lists** for the unresolved cohort.
- **66** network/fetch errors on the 68 cache-miss API attempts (no 429s).

---

## 11. Recommended final accepted affiliations

| Outcome | Accept |
|---|---|
| `verified_agreement` | Either set (identical) |
| `verified_html_primary` | **HTML/ROR as primary** |
| `verified_openalex_primary` | OA only when HTML has **no usable org text**; never overwrite HTML rows |
| `partial_agreement` / `conflict` | **Keep both tiers separate — do not union** |
| `needs_pdf_review` | Hold for primary-source review |
| `unresolved` | No org yet |

---

## 12. Remaining manual-review queue

| Bucket | n |
|---|---:|
| `needs_pdf_review` | **295** |
| `unresolved` | **719** |
| `conflict` (not in PDF queue) | **15** |
| **Total manual-ish** | **1029** |

Artifacts: `affiliation_verify_phase1_local.json`, `affiliation_verify_phase2_oa.json`, `affiliation_verify_phase3_pdf.json`, `phase0_oa_primary_33_investigation.json`, `phase2_oa_queue.json`, `phase3_pdf_queue.json`, `affiliation_verify_phased_final_summary.json`.
