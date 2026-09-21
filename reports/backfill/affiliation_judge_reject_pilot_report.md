# Affiliation judge pilot — reject exclusion + execute

## Critical fix

**Before:** judge accepted orgs were appended as `llm_affiliation_judge`, but rejected HTML/OA orgs (e.g. National Security Authority / org 174) remained in the effective set via original evidence above `MIN_CONFIDENCE`. Weight/`precedence` alone did **not** remove them.

**After:**
1. Store `accepted_organisation_ids` **and** `rejected_organisation_ids` on `affiliation_judgments` (migration `013`).
2. Rejected = evaluated HTML∪OA claim IDs − accepted IDs (only orgs the judge saw).
3. Empty accepted on a resolved decision → **no exclusions** (fail open).
4. `organisation_score` / effective org set filter rejected IDs when `decision ∈ {HTML,OPENALEX,BOTH}` and `judge_called`.
5. Original HTML/OA rows are **not** deleted (audit preserved).
6. Accepted orgs must be grounded in supplied paper evidence.

## Tests

`tests/test_affiliation_judge.py` — **12 passed** (includes NSA regression + empty-accept fail-open + unevaluated org retained).

Idempotency (pilot re-pass): all 6 disagreements `skipped_duplicate` + no new `llm_affiliation_judge` rows.

## Pilot (20 papers)

| Metric | Value |
|---|---|
| Paid calls this run | 2 (repair empty-accept only) |
| This-run cost | **$0.001136** (cap $0.05) |
| Six judgments stored cost sum | **~$0.00365** |
| Max paid calls | 6 |

### Six judge decisions

| arxiv | decision | accepted IDs | rejected IDs | effective AFTER |
|---|---|---|---|---|
| 2601.10511 | OPENALEX | 801, 1362 (UMD, NSA Agency) | **174** (Authority) | Agency + UMD (**Authority removed**) |
| 2601.14810 | UNCERTAIN | — | — | unchanged (INRIA / Paris-Saclay / LISN) |
| 2512.13742 | UNCERTAIN | — | — | unchanged |
| 2602.18613 | BOTH | 220 (Özyeğin) | — | Özyeğin |
| 2603.02790 | HTML | 245 (Amsterdam) | 223 (CRC) | Amsterdam only |
| 2605.31291 | UNCERTAIN | — | — | unchanged (SSR / EPFL) |

### NSA audit check (2601.10511)

- HTML evidence rows for org **174** still present: **6 rows** (preserved).
- Effective set after adjudication: **174 excluded**; 801 + 1362 kept.
- Verification flag `nsa_authority_excluded`: **true**.

### Unintended changes

Effective org set changed only for judged papers with non-empty reject sets:
- `12243` removed Authority
- `31691` removed Clinical Research Consortium

Non-disagreement pilots and UNCERTAIN papers: no effective-set change.

Artifact: `reports/backfill/affiliation_judge_pilot_execute.json`

## Stop

No September bulk judging. Ready for review.
