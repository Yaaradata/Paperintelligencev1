# HTML + OpenAlex affiliation judge — implementation + dry-run

**Status:** Implemented. **Dry-run only** — no paid LLM calls.  
**Flags:** `PI_USE_PAPERS_CATALOG=1`, `PI_WRITE_RADAR_COMPAT=0`  
**Judge model (configured):** `z-ai/glm-4.6` (`MODEL_JUDGE_GLM` / `CLASSIFY_MODEL`)  
**Prompt:** `prompts/affiliation_judge/v001.md`

---

## 1. Files changed and tests

| Path | Role |
|---|---|
| `sql/migrations/012_affiliation_judgments.sql` | Judgment outcomes table |
| `src/.../verify/judge_compare.py` | Fetch/compare HTML vs OA claims |
| `src/.../verify/judge_llm.py` | Prompt, validate, resolve, cost estimate |
| `src/.../verify/judge_persist.py` | Upsert judgment; append `llm_affiliation_judge` evidence |
| `src/.../verify/judge_workflow.py` | Orchestration (auto paths + judge) |
| `prompts/affiliation_judge/v001.md` | Judge instructions |
| `scripts/affiliation_judge_pilot.py` | Stratified 20-paper dry-run/execute |
| `tests/test_affiliation_judge.py` | Compare + validation unit tests |
| `adjudication/org_score.py` | Weight for `llm_affiliation_judge` (0.95) |
| `author_affiliation/policy.py` | Precedence: judge above HTML/OA |
| `common/config.py` | Price entry for `z-ai/glm-4.6` |

**Tests:** `pytest tests/test_affiliation_judge.py` → **7 passed**

---

## 2. Pilot compare counts (20 papers)

| Path | n | Judge? |
|---|---:|---|
| Exact match | **4** | No |
| Disagreement | **6** | **Yes (proposed)** |
| HTML-only (OA missing/empty) | **4** | No |
| OpenAlex-only | **3** | No |
| Neither | **3** | No |

---

## 3. Pilot papers and proposed judge-call count

- **20** papers selected from prior Sep verification strata  
- **Proposed judge calls:** **6** (one per disagreement)  
- Artifact: `reports/backfill/affiliation_judge_pilot_dry_run.json`

---

## 4. Estimated LLM judge cost

| Item | Value |
|---|---|
| Model | `z-ai/glm-4.6` |
| Assumed price | $0.15 / $0.50 per 1M in/out (same band as glm flash defaults) |
| Est. tokens (6 calls) | ~5.1k input + ~2.1k output |
| **Est. total** | **~$0.0018** |

No paid calls executed.

---

## 5. Example structured judge input / output

### Input (disagreement — `2601.10511`)

```json
{
  "paper_id": 12243,
  "arxiv_id": "2601.10511",
  "title": "Scalable Algorithms for Approximate DNF Model Counting",
  "authors": ["Paul Burkhardt", "David G. Harris", "Kevin T Schmitt"],
  "html_affiliation_text": ["nsa", "Note: National Security Agency", "Note: University of Maryland", "..."],
  "html_organisation_claims": {
    "org_names": ["national security authority"],
    "org_ids": [174]
  },
  "openalex": {
    "identity_ok": true,
    "organisation_claims": {
      "org_names": ["national security agency", "university of maryland, college park"],
      "org_ids": [801, 1362]
    }
  }
}
```

### Expected output shape (not executed — illustrative)

```json
{
  "decision": "OPENALEX",
  "accepted_organisations": [
    {
      "organisation_name": "National Security Agency",
      "existing_organisation_id": 801,
      "author_names": [],
      "supporting_evidence": "HTML note text says National Security Agency; stored HTML org 'Authority' looks like a mis-parse of NSA"
    },
    {
      "organisation_name": "University of Maryland, College Park",
      "existing_organisation_id": 1362,
      "author_names": [],
      "supporting_evidence": "HTML notes include University of Maryland"
    }
  ],
  "reason": "HTML note text aligns with OpenAlex; 'National Security Authority' is unsupported",
  "unsupported_claims": ["national security authority"]
}
```

---

## 6. How accepted affiliation enters PI adjudication

1. Judgment row stored in `paper_intelligence.affiliation_judgments` (`judge_version`, decision, cost, org ids, `result_json`).
2. On paid execute (not yet): accepted orgs with resolved IDs are **appended** as `evidence_type=llm_affiliation_judge` via existing `insert_affiliation` — **original HTML/OA rows unchanged**.
3. `organisation_score` / adjudication already scans `paper_author_affiliations`; new type weight **0.95**, precedence **first** in affiliation policy — so judge-backed orgs are preferred when present and `confidence ≥ 0.6`.
4. Exact match / HTML-only: **no new rows**; existing evidence continues to drive adjudication.
5. `UNCERTAIN` / invalid judge output: **no accepted orgs inserted**; pipeline continues without inventing affiliations.

---

## 7. Cases where evidence remains insufficient

- **Neither** (3 in pilot): no usable HTML or OA orgs → auto-skip / unresolved.  
- **OA-only** (3): no HTML text to corroborate → no judge; retain OA under existing policy.  
- **Disagreements** (6): need judge; until approved, still unresolved at the judge layer.  
- Example `2601.10511`: HTML extraction/canonicalisation noise (`nsa` → “National Security Authority”) vs OA “National Security Agency” + UMD — classic insufficient/noisy HTML without a judge.

---

## Verification checklist (dry-run)

| Check | Result |
|---|---|
| Exact match does not invoke judge | Pass |
| Missing OA does not invoke judge | Pass |
| Disagreement proposes exactly one call/paper | Pass |
| No duplicate paid calls this run | Pass (0 paid) |
| Original evidence preserved | Pass (append-only design) |

---

## Next step (awaits your approval)

```bash
cd /home/ubuntu/Paperintelligencev1/worktrees/subha
export PI_USE_PAPERS_CATALOG=1 PI_WRITE_RADAR_COMPAT=0 PYTHONPATH=src
python3 scripts/affiliation_judge_pilot.py --execute --limit 20 \
  --output reports/backfill/affiliation_judge_pilot_execute.json
```

Estimated spend for this pilot: **≈ $0.002**.
