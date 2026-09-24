# Golden human-labelling dataset

Source of truth for scoring changes. Model-vs-model agreement is never evidence of
quality; only human labels in `paper_intelligence.golden_human_scores` are.

**Canonical sample name:** `quality_scoring_golden_v1` — see **`golden/README.md`**.

## Layout

| Path | Role |
|---|---|
| `sql/migrations/020_golden_human_scores.sql` | Append-only table (applied) |
| `sql/migrations/021_golden_ai_relevance.sql` | Adds `h_ai_relevance` (applied) |
| `sql/migrations/022_golden_dataset_version.sql` | Adds `dataset_version` default `quality_scoring_golden_v1` (**not applied**) |
| `scripts/export_golden_template.py` | Build blind labelling workbook (no paid calls) |
| `golden/quality_scoring_golden_v1.xlsx` | **Locked v1 labelled set** (labeller subha, round v1, n=200) |
| `golden/quality_scoring_golden_v1.csv` | Same rows as CSV |
| `golden/golden_labelling_200.xlsx` | Labelling template / prior blank sheet |
| `golden/model_scores_hidden.csv` | Terra/Jev scores for the same 200 ids — comparison only (gitignored) |
| `scripts/import_golden_labels.py` | Validate + insert filled rows |
| `scripts/evaluate_against_golden.py` | Engines vs human (read-only) |
| `reports/golden/engine_comparison.md` | Latest comparison report |
| `reports/golden/baseline_v1.md` | Verifier regression baseline |

## Labelling rules

- Label **blind**: the xlsx must never contain Terra/Jev scores, ranks, or composites.
- Leave a row blank rather than guess.
- `h_final_score` is the labeller's own judgement (not a computed cell).
- Do ~25 papers per sitting.
- Re-import with the same `(paper_id, labeller, label_round)` is an **error**, not an overwrite.

## Sample strata (200 papers, Sep 1–21 2026 window + editorial history)

| Stratum | Count |
|---|---:|
| `editorial_pick` | 12 |
| `flagged` | 4 |
| `max_disagreement` | 60 |
| `score_strata` | 104 |
| `screen_failed` | 20 |

## Versioning

- Corrections → new `label_round`, same `dataset_version`.
- New sample or labeller set → new `dataset_version` (`quality_scoring_golden_v2`); never edit v1 in place.

## Phase G2 / G3 gate (verifier)

Any scoring change is evaluated against human labels, not another model.

- Per-dimension Spearman must not fall more than **0.05** below `reports/golden/baseline_v1.md`
- Verdict recall (`winner_material` in engine top-50) must not fall
- Fewer than **150** labelled rows on the intersection → Cannot be determined

Do not change models, prompts, policies, or thresholds from an evaluation run —
bring numbers to the human decision-maker.
