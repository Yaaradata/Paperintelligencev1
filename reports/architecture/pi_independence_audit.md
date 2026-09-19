# PaperIntelligence Independence Audit

**Date:** 2026-09-19  
**Repo:** `PaperIntelligencev1/worktrees/subha`  
**Scope:** Phase 1 dependency map + Phase 2 status-coupling root cause  
**Status:** Audit complete. Immediate quality-router fix implemented in code (no catalog cutover).

---

## 1. Root cause

PaperIntelligence stores classifications, affiliations, HF signals and adjudication in
`paper_intelligence.*`, but several stage selectors still require:

```text
research_radar.content_items.status = 'RELEVANT'
```

via `REQUIRED_UPSTREAM_STATUS` in `src/paper_intelligence/db/results.py`.

**Concrete failure (content_item_id = 137619):**

| Fact | Value |
|---|---|
| PI screen | gate passed (`ai_relevance` 9.0) |
| Radar status | `ENTITY_RESOLVED` (set by Research Radar after entity resolution) |
| Quality router input | `latest_screen_scores()` filtered to `status = RELEVANT` |
| Outcome | paper invisible to quality routing → never considered |

A screen pass does **not** imply automatic quality scoring. It should imply entry into
the quality **candidate router**, with an explicit selected / not_selected / blocked
decision. Status coupling caused silent disappearance instead.

---

## 2. Shared vs PI-owned surfaces today

| Surface | Owner today | Notes |
|---|---|---|
| `research_radar.content_items` | Shared / Radar | Identity, title, `published_at`, **status** |
| `research_radar.paper_metadata` | Shared / Radar | arXiv, DOI, abstract, affiliation_text |
| `paper_intelligence.paper_classification_results` | PI | screen / audience / quality append-only |
| `paper_intelligence.paper_author_affiliations` (+ orgs) | PI | FAST/DEEP affiliations |
| `paper_intelligence.paper_hf_signals` | PI | HF Daily Papers enrichment |
| `paper_intelligence.paper_intelligence_current` | PI | Adjudicated projection + `quality_status` |
| `paper_intelligence.pipeline_runs` / stage runs / LLM logs | PI | Observability |

Architecture docs already state: ingest/relevance write Radar; enrichment writes PI.
Eligibility incorrectly still reads Radar **status**.

---

## 3. Dependency inventory

### 3.1 Critical — eligibility / status (Phase 2 target)

| Location | Stage | Uses | R/W Radar | Replace with | Risk |
|---|---|---|---|---|---|
| `db/results.py` `REQUIRED_UPSTREAM_STATUS` | db helper | status=`RELEVANT` | READ | PI screen / PI relevance outcomes | **High** |
| `db/results.py` `latest_screen_scores` | quality / FAST survivors | status + published_at | READ | published_at window only; eligibility = PI screen gate | **High** |
| `db/results.py` `select_window_candidates` | screen / audience | status=`RELEVANT` | READ | non-REJECTED PI-eligible set until PI catalog | **High** |
| `db/results.py` `count_window` | paid dry-run counts | status=`RELEVANT` | READ | same as above | Med |
| `scripts/run_stage.py` normalize SQL | normalize | status=`RELEVANT` | READ | PI-eligible statuses | Med |
| `quality/nomination.py` | editorial quality | `PI_ELIGIBLE_STATUSES` (was missing) | READ | screen-gate primary; stop blocking on Radar status for routing | Med |

### 3.2 Identity / metadata reads (Phase 3–4 catalog)

| Location | Stage | Uses | R/W | Replace with | Risk |
|---|---|---|---|---|---|
| `db/results.py` `PAPER_FIELDS_SQL` / `fetch_papers` | screen/audience/quality | title/abstract/categories | READ | `paper_intelligence.papers` | High |
| `ingest/repository.py` | ingest | upsert items + metadata | **WRITE** | PI papers + source metadata | High |
| `ingest/arxiv_oai.py` | ingest | `backfill_checkpoints` | R/W | `paper_intelligence.ingest_checkpoints` | Med |
| `relevance/stage.py` | relevance | status lifecycle RELEVANT/REJECTED | **WRITE** | PI relevance results; stop mutating Radar status | High |
| `normalize/repository.py` | normalize | authors_raw | READ | PI papers | Med |
| `author_affiliation/repository.py` | FAST/DEEP | doi/arxiv/affiliation_text | READ | PI papers enrichment cols | High |
| `author_affiliation/runner.py` | FAST/DEEP | window select (no status) | READ | PI papers | Med |
| `hf_signals/stage.py` | HF | arxiv_id ↔ content_id | READ | PI papers.arxiv_id unique | Med |
| `adjudication/stage.py` | adjudication | published_at window only | READ | PI papers.published_at | Med |
| reports / editorial / org_coverage / golden | reports/eval | title/published_at/status counts | READ | PI papers + PI funnel metrics | Med |

### 3.3 Structural FK risk

`sql/migrations/001_schema.sql` and `003_hf_signals.sql`: almost every
`content_item_id` FK references `research_radar.content_items(id)` with
`ON DELETE CASCADE`. Radar row deletion would wipe PI history.

**Migration risk: High** — must move FK to PI papers (or drop CASCADE) before cutover.

### 3.4 Stages that do NOT filter Radar status today

- adjudication (window only)
- HF enrichment (arxiv lookup)
- affiliation DEEP candidate list (quality result join + published_at)
- author_affiliation window select (no status)

These still **join** Radar for identity/dates.

---

## 4. Quality router contract (verified)

From `quality/stage.py` + `policies/gating/v001.yaml`:

1. Load latest PI `screen` rows in published_at window.
2. Keep rows with `result_json.gate.passed == true`.
3. Rank survivors by mean(`technical_significance`, `apparent_novelty`, `evidence_strength`).
4. Keep top `GATE_PERCENTILE` (default 15%).
5. Union notable-org survivors and notable-person survivors.
6. Score only the union (paid).

**Screen pass ≠ quality score.** Screen pass ⇒ enter router ⇒ explicit decision.

---

## 5. Phase 2 fix (implemented; non-destructive)

1. `latest_screen_scores` no longer filters on Radar `status`.
2. `select_window_candidates` / `count_window` use `PI_ELIGIBLE_STATUSES`
   (`RELEVANT`, `ENTITY_RESOLVED`, `SCORED`, `CANDIDATE`, `ENRICHED`) instead of exact `RELEVANT`.
   Still excludes `REJECTED` / `INGESTED` from paid selection until PI owns relevance outcomes.
3. `explain_quality_routing()` records explicit decisions for every latest screen row.
4. Adjudication stores `quality_selection_reason` in `adjudication_json`.
5. Nomination eligibility for scoring no longer blocks on Radar status when screen passed.
6. Regression tests cover the six required cases.
7. Dry-run script counts historical coupling impact + projected paid quality volume
   (no LLM calls).

**Not done in Phase 2 (needs approval):** PI-owned catalog, FK migration, stopping
ingest/relevance writes to Radar, bulk quality re-score of newly visible candidates.

---

## 6. Phase 3–4 design pointers

See companion: `reports/architecture/pi_catalog_migration_design.md`.

Preferred table: `paper_intelligence.papers` with stable `paper_id`, arXiv uniqueness,
crosswalk to legacy `content_item_id`, and stage state via results + `current` —
**not** a single mutable `paper.status` as funnel source of truth.

---

## 7. Remaining Radar dependencies after Phase 2

| Dependency | Still required? | Notes |
|---|---|---|
| Radar status for quality router | **No** | Fixed |
| Radar `content_items` / `paper_metadata` for identity | Yes | Until catalog migration |
| PI ingest/relevance writing Radar | Yes | Until catalog + PI relevance store |
| FK CASCADE to Radar | Yes | Until migration 006+ |
| Reports counting Radar `RELEVANT` | Yes | Cosmetic / funnel metrics |

---

## 9. One-day validation (2026-09-02) — PASSED

See `reports/architecture/phase2_oneday_validation_2026-09-02.json` and
`phase2_oneday_adjudication_2026-09-02.json`.

| Metric | Value |
|---|---|
| Latest screen rows | 567 |
| Screen-passed (enter router) | 556 |
| Blocked (gate failed) | 11 |
| Selected | 131 |
| Already scored (current versions) | 93 |
| Newly selected (paid not launched) | 38 |
| Est. paid calls / cost | 8 / ~$0.29 |
| 137619 reason | `not_selected_below_gate_percentile` |
| 137619 screen_score | 6.7 unchanged |
| Editorial nomination can score 137619 | Yes (standard quality rubric; dry-run only) |
| Adjudication one-day write | reason stamped; 0 historical score mismatches |

Quality router confirmed **not** using `PI_ELIGIBLE_STATUSES` (556 of 567 screen rows are non-`RELEVANT`).

---

## 10. Actions requiring approval / next

1. ~~Commit Phase 2 status-coupling fix~~ (this commit).
2. Optional: paid quality for newly selected papers on validated days (dry-run first).
3. Optional: adjudication on additional days to stamp `quality_selection_reason`.
4. Review catalog migration design before any DDL/cutover (still design-only).
5. Deploy when ready.
