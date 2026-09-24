# quality_scoring_golden_v1

| | |
|---|---|
| **Name** | `quality_scoring_golden_v1` |
| **Files** | `golden/quality_scoring_golden_v1.xlsx`, `golden/quality_scoring_golden_v1.csv` |
| **Table** | `paper_intelligence.golden_human_scores` (keep this name) |
| **dataset_version** | `quality_scoring_golden_v1` (migration **022**, not yet applied) |
| **Stage it governs** | **quality scoring** — rubric dimensions + composite / newsletter verdict |
| **Labeller** | `subha` · `label_round=v1` · **n=200** · labelled **2026-09-24** · **blind** to model scores |
| **Baseline** | `reports/golden/baseline_v1.md` |

## Sampling (five strata)

| Stratum | Count |
|---|---:|
| `editorial_pick` | 12 |
| `flagged` | 4 |
| `max_disagreement` | 60 |
| `score_strata` | 104 |
| `screen_failed` | 20 |
| **Total** | **200** |

(Window + editorial history; see also `docs/golden_dataset.md`.)

## What it is for

The **baseline the verifier checks scoring changes against**. Any quality engine, prompt, policy, or weight change is measured against these **human** labels (Spearman / verdict recall gates in `baseline_v1.md`).

**Rule:** scoring changes are measured against human labels, **never** against another model's scores.

## What it is NOT for

- It does **not** cover audience seats (no engine seat scores exist on this set).
- It is **not** a training set for prompts.

## Versioning

| Change | Action |
|---|---|
| Corrections to the same papers / same labeller intent | new `label_round` (e.g. `v2`), **same** `dataset_version` |
| New sample and/or new labeller set | new `dataset_version` (`quality_scoring_golden_v2`), **never** edit v1 files in place |

## Related artifacts

| Path | Role |
|---|---|
| `golden/golden_labelling_200.xlsx` | Blank / prior labelling template (not the locked v1 dataset name) |
| `golden/model_scores_hidden.csv` | Model scores for the same ids — **gitignored**; comparison only |
| `golden/double_label_30.xlsx` | Human–human reliability sample (Ranjith); separate from this dataset |
| `reports/golden/engine_comparison.md` | Terra / Jev vs human |
| `reports/golden/g3_decision.md` | G3 stop: keep Terra primary; weights not shipped |
| `sql/migrations/020_golden_human_scores.sql` | Table create (applied) |
| `sql/migrations/021_golden_ai_relevance.sql` | `h_ai_relevance` (applied) |
| `sql/migrations/022_golden_dataset_version.sql` | `dataset_version` (**written, not applied**) |

## Current baseline (pointer)

See **`reports/golden/baseline_v1.md`** — intersection n=151; per-dimension Spearman and verdict recall@50 for Terra / Jev v001 / Jev v002. Do not restore `ai_relevance` to the gate without independent human labels.
