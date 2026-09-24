# Backlog — PaperIntelligenceV1 (`dev/subha`)

**Updated:** 2026-09-24

Active work. Closed items with verifier evidence → `BacklogClosed.md`.

---

## P0 / unblock

| ID | Item | Notes |
|---|---|---|
| B-JEV-REPORT | Fix `scripts/write_jev_glm_report.py` (`c.paper_id` / funnel join) and regenerate Sep 21–23 report | Discovered 2026-09-24; quality rerun chain failed at report writer |
| B-MIG-022 | Apply `sql/migrations/022_golden_dataset_version.sql` (ops) | Written; **do not apply from agents** |
| B-DL30 | Import Ranjith labels from `golden/double_label_30.xlsx` | Needed before shipping G3c weights |

## P1 — open decisions as work

| ID | Item | Notes |
|---|---|---|
| B-G3C-WEIGHTS | Decide/ship or reject composite refit | Blocked on B-DL30 + human decision |
| B-SCREEN-GATE | Screen-gate policy after G3b (6/24 human winners dropped) | Blocked on ceiling + weight decision |
| B-Q-DEFAULT | Whether default `QUALITY_ENGINE` stays `terra` | Product decision; code already supports `jev_glm` |
| B-ORG-BOOST | org_boost magnitude vs Terra spread | Carried from Phase 7a |
| B-PEOPLE | Notable people + `person_boost` | Carried — `PROJECT.md` |
| B-OBS | Parent pipeline run + item_stage_runs; OAI raw cache | Carried |

## P2 — hygiene

| ID | Item | Notes |
|---|---|---|
| B-STAGE-REPORTS | `run_stage.py` does not know `stage=reports` | Detached quality chain expected it |
| B-PROJECT-DRIFT | Refresh `PROJECT.md` stage/engine/golden sections | Explicitly behind as of 2026-09-24 |
| B-GOLDEN-PATHS | Update scripts/docs still naming `golden_labelling_200_papers_human.xlsx` | Prefer `quality_scoring_golden_v1.xlsx` |
