# PaperIntelligenceV1 — Project

**Updated:** 2026-09-24 (partial — see drift note)  
**Worktree:** `worktrees/subha` (`dev/subha`)

> **Drift note (2026-09-24):** This file is **behind the repo**. Day-to-day decisions, live state, and backlog now live in **`Context.md`**, **`State.md`**, **`Backlog.md`**, **`BacklogClosed.md`**. Quality engine flag (`QUALITY_ENGINE=terra|jev_glm`), affiliation LLM judge after deep, and golden dataset `quality_scoring_golden_v1` are documented there and in `docs/pipeline_flow.md` / `golden/README.md` — not fully reflected in the sections below. Do not treat this file alone as current.

---

## Pipeline

```
ingest → relevance → normalize → screen
  → affiliation_fast → audience_domain → quality
  → affiliation_deep → affiliation_judge → hf_signals → adjudication → reports
```

Quality stays author/org-blind. FAST affiliation feeds the quality router. HF does **not** affect `final_score`.  
See **`docs/pipeline_flow.md`** for models/engines and affiliation evidence hierarchy.
---

## This cycle (funnel correction) — Done

| ID | Item | Status |
|---|---|---|
| S-OAI-AFF | OAI `authors_structured` + affiliation capture | **Done** |
| S-AFF-SPLIT | `affiliation_fast` before quality / `affiliation_deep` after | **Done** |
| S-Q-ROUTER | Quality = top screen ∪ notable-org ∪ notable-person | **Done** |
| S-VER-SKIP | Version-aware already-processed checks | **Done** |
| S-GOLDEN | Load 200+200 (+ human 30) + real `evaluate_golden.py` | **Done** |
| S-Q-STATUS | `quality_status` on current (`not_selected`/`scored`/`skipped`/`failed`) | **Done** (migration 005) |
| S-ORG-SEED | Export Org-of-Interest into `config/organisations.yaml` | **Done** (30 orgs) |

### Still open

| ID | Item | Status |
|---|---|---|
| S-PEOPLE | Notable people + `person_boost` | P1 next |
| S-OBS | Parent pipeline run + item_stage_runs everywhere; OAI raw cache | P1 |
| S-1DAY | One previous day E2E with new funnel | Next after people or in parallel |
| S-HF-SCORE | Consider HF in final_score | Blocked on stronger evidence |
| S-ORG-BOOST | org_boost magnitude vs Terra score spread | Open decision (Phase 7a) |

---

## Open decisions

- **org_boost magnitude vs Terra score spread** — top-N reports now rank by
  `quality_score` (org_boost / final_score as columns). Whether org_boost
  should be rescaled relative to Terra's score distribution is undecided;
  final_score formula unchanged for now.

## Notes

- arXiv OAI rarely emits `<affiliation>`; capture is still required when present. FAST also uses existing `paper_metadata.affiliation_text` + local aliases.
- **Quality-scoring golden:** `quality_scoring_golden_v1` — `golden/quality_scoring_golden_v1.xlsx` / `.csv`; table `golden_human_scores`; baseline `reports/golden/baseline_v1.md`. Older Radar golden assets: `data/golden/README.md`.
- Measured HF validation still recommends **no** HF weight in `final_score` yet.
- **Open (2026-09-24):** composite weight refit, screen-gate policy, default `QUALITY_ENGINE` — see `Context.md`.
