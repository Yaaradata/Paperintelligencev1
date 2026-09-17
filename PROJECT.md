# PaperIntelligenceV1 — Project

**Updated:** 2026-09-17  
**Worktree:** `worktrees/subha` (`dev/subha`)

Single project source of truth (Context/State/Backlog point here).

---

## Pipeline

```
ingest → relevance → normalize → screen
  → affiliation_fast → audience_domain → quality
  → affiliation_deep → hf_signals → adjudication → reports
```

Quality stays author/org-blind. FAST affiliation feeds the quality router. HF does **not** affect `final_score`.

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

---

## Notes

- arXiv OAI rarely emits `<affiliation>`; capture is still required when present. FAST also uses existing `paper_metadata.affiliation_text` + local aliases.
- Golden assets sourced from Research Radar reports; see `data/golden/README.md`.
- Measured HF validation still recommends **no** HF weight in `final_score` yet.
