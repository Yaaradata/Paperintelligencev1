# Combined STOP — STEP A fixes + Phase 7a seat merge

**Date:** 2026-09-22 · **Branch:** `dev/subha`  
**Status:** STOP before Phase 7a items 2–7 (awaiting approval of merged seats)

---

## 1. affiliation_fast HTML pass (pre-router)

### Fix
`affiliation_fast` now allows **arXiv HTML** when OAI/local evidence is empty; still **no ROR/OpenAlex**. Stage version **v003**. Reuses the deep stage HTML parser + alias/domain/watchlist matching. Rate limit/cache unchanged (`ARXIV_HTML_REQUEST_SLEEP`).

### Sep 16–21 re-run (live, $0)

| Metric | Value |
|---|---:|
| Screen survivors processed | 2535 |
| resolved | 1713 |
| review_required | 526 |
| no_evidence_supplied | 296 |
| rows_written | 46515 |

### Notable-org vs prior 380 selected

| Metric | Count |
|---|---:|
| Notable-org survivors (judge-effective) | **273** |
| Day top-slice | 380 |
| Router union (top ∪ notable ∪ person) | **582** |
| Notable-org **not** already in top-slice (= new quality candidates) | **202** |
| Previously Terra-scored | 380 |

**Do not run quality for the 202 yet** (per brief).

Dry-run Terra cost for those **202**:
- table estimate: **~$1.89** (~41 calls)
- empirical at last-run $/paper (~$0.00325): **~$0.66**

Artifacts: `reports/review_fixes/sep16_21_affiliation_fast_html.log`, `affiliation_fast_html_sep16_21.json`

---

## 2. Screen ID robustness

### (a) Batch-local indices
Screen / audience / quality user prompts now emit `batch_index: 1..N` only; parsers map back in code. Model-echoed `content_item_id` is ignored.

| Stage | Prompt version |
|---|---|
| screen | **v002** (new file; v001 kept) |
| audience_domain | **v003** (new file; v001/v002 kept) |
| quality | **v001 kept** (batch_index in prompt text; **not** bumped so existing Terra rows stay current) |

### (b) `screen_attempts`
Migration **018** + `screen/attempts.py` — succeeded/failed attempts recorded like quality. Missing screens appear via failed attempts.

### (c) Rescore `199751` (paid, approved)
- Cost: **$0.0002**
- Result: `ai_relevance=4.0` → **gate failed** (pass=false)
- `screen_attempts`: succeeded, prompt_version=v002
- Not a quality candidate

---

## 3. Boost impact (Sep 16–21, read-only)

Full tables: [`boost_impact_sep16_21.md`](boost_impact_sep16_21.md)

- Scored n=380; quality **p50=7.70**, **p90=8.10**, gap **0.40**
- Only **org_boost** affects final today (person_boost=0; HF stored but not in final)
- Top-20 membership: **1** swap (`200082` out / `197271` in)
- **15** shared ids change rank within top-20
- Org boosts are typically **0.11–0.38** ≈ **0.3–0.9×** the p50–p90 gap — enough to reorder near-ties, rarely to vault a mid-pack paper into top-20

---

## 4. Phase 7a item 1 — merged seats (canonical)

**Source:** `policies/editorial_seats/v001.yaml`  
**Loaders:** `scripts/select_newsletter.py` → `newsletter_select_v002`; `scripts/select_linkedin.py` → `linkedin_select_v002` (keeps LinkedIn lens + topic lists).  
**v001 prompts remain on disk.**

### Merged seat text

```
<seat name="TECH">
Reader:
Senior engineering managers, directors, GMs, heads of engineering, AI/ML,
platform, architecture, or technical strategy.

Strong candidates affect decisions involving:
- architecture or technical design
- evaluation
- reliability or failure modes
- security or safety
- cost, latency, or performance
- model/tool/vendor choice
- engineering practices
- whether a technical claim is credible

Prefer:
- measurable evidence
- reproducible or adaptable methods
- useful comparisons
- explicit limitations or failure modes
- lessons transferable to an enterprise engineering environment

A frontier-scale experiment may still qualify if its result changes a decision
that a normal enterprise engineering organisation can make.

Anchor test:
Pick the paper that best lets such a reader say one of:
- "I can have my team try this on our stack this quarter and report back."
- "This changes an architecture / eval / cost / safety bet I am about to make."
- "I can use this to judge whether a vendor or internal claim is real."

Reject for this seat: pure theory with no implementable path, or a finding
whose only action is "interesting".

Do not select a paper whose only value is theoretical novelty or a benchmark
improvement with no meaningful engineering consequence.
</seat>

<seat name="PRODUCT">
Reader:
Senior product managers, product directors, heads of product, and adjacent
business/process/risk leaders.

Strong candidates affect decisions involving:
- what to build or not build
- feature scope
- workflow or process design
- user behaviour, adoption, or trust
- human-AI interaction
- commercial model or pricing
- governance, compliance, or risk
- deployment or operating model

Prefer:
- user or deployment evidence
- measurable behavioural or business outcomes
- workflow implications
- human factors
- risks that alter product design
- findings transferable beyond the exact experiment

Anchor test:
Pick the paper that best lets such a reader say one of:
- "This changes what we should build or how we should scope an AI feature."
- "This tells me something real about user behaviour, trust, adoption, or risk."
- "This affects go-to-market, pricing, compliance, or process design for AI."

Reject for this seat: papers whose contribution is only a kernel, a training
trick, or a benchmark number with no product or process consequence.

Do not select a paper merely because a product leader can understand it.
It must change a plausible product, process, commercial, or governance decision.
</seat>
```

---

## Tests

`197` unit tests passed (full `tests/unit`).

---

## STOP

Awaiting approval of the **merged seat text** before Phase 7a items **2–7** (classification v002, audience prompt v003, wiring, migration for seat scores, pool loaders, router invariance).

Also open: whether to score the **202** new notable-org quality candidates (dry-run ~$0.66–$1.89 Terra) — not started.
