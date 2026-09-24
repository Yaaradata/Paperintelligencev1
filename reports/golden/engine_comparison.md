# Golden engine comparison (Phase G3a)

**Generated:** 2026-09-24T08:12:10.079634+00:00  
**Labels:** labeller=`subha` round=`v1` n_labelled=**200** · n_intersection=**151**  
**Verdict mix (intersection):** {'maybe': 65, 'winner_material': 22, 'reject': 40, 'shortlist': 24}  
**Engine coverage (full / intersection):** {'terra': 167, 'jev_v001': 169, 'jev_v002': 153} / {'terra': 151, 'jev_v001': 151, 'jev_v002': 151}  
**Gate (intersection ≥150):** OK

## Notes

- ai_relevance REMOVED from all comparison tables. It was backfilled from pipeline screen scores for this labelling round; a Spearman of 1.000 vs Terra was circular (not independent human agreement) and would be misread.
- Headline metrics use the INTERSECTION of papers scored by all three engines (Terra + Jev v001 + Jev v002) with full six quality dimensions (n=151).
- Any stratum or cell with n < 25 is suppressed (noise, not a finding).
- Secondary table reports per-engine full coverage on the labelled set, with n per cell.
- Seat scores (tech_relevance / product_relevance) remain unscored by engines — omitted.
- Composite comparison uses human h_final_score vs engine quality composite.
- G3b evaluation run_ids listed in reports/golden/g3b_run.json are excluded from Terra loads here (gate-drop eval must not pollute current quality).

## Headline — intersection (n=151, all three engines)

Per dimension: Spearman / MAE / n

| Dimension | Terra | Jev v001 | Jev v002 | Closer to human |
|---|---:|---:|---:|---|
| technical_significance | 0.432 / 0.70 / 151 | 0.248 / 0.66 / 151 | 0.289 / 1.26 / 151 | **terra** |
| apparent_novelty | 0.426 / 0.68 / 151 | 0.321 / 0.61 / 151 | 0.280 / 1.59 / 151 | **terra** |
| practical_applicability | 0.588 / 1.20 / 151 | 0.539 / 1.12 / 151 | 0.413 / 2.25 / 151 | **terra** |
| professional_value | 0.302 / 1.21 / 151 | 0.615 / 0.95 / 151 | 0.696 / 2.07 / 151 | **jev_v002** |
| learning_value | 0.232 / 0.77 / 151 | 0.187 / 0.75 / 151 | 0.309 / 2.44 / 151 | **jev_v002** |
| evidence_strength | 0.517 / 0.99 / 151 | 0.394 / 1.89 / 151 | 0.370 / 1.70 / 151 | **terra** |
| **composite (h_final vs engine)** | 0.219 / 1.23 / 151 | 0.367 / 1.31 / 151 | 0.427 / 2.12 / 151 | **jev_v002** |

### Verdict recall on intersection (`winner_material` in engine top-K)

| Engine | winners | top-20 hits | recall@20 | top-50 hits | recall@50 |
|---|---:|---:|---:|---:|---:|
| terra | 22 | 4 | 0.182 | 11 | 0.500 |
| jev_v001 | 22 | 4 | 0.182 | 13 | 0.591 |
| jev_v002 | 22 | 8 | 0.364 | 17 | 0.773 |

## Secondary — per-engine full coverage (n varies by cell)

Same labelled set; each engine uses whatever papers it scored. Cells with n < 25 suppressed.

| Dimension | Terra | Jev v001 | Jev v002 |
|---|---:|---:|---:|
| technical_significance | 0.494 / 0.71 / 167 | 0.329 / 0.65 / 169 | 0.296 / 1.27 / 153 |
| apparent_novelty | 0.478 / 0.69 / 167 | 0.371 / 0.64 / 169 | 0.284 / 1.61 / 153 |
| practical_applicability | 0.579 / 1.22 / 167 | 0.572 / 1.10 / 169 | 0.420 / 2.25 / 153 |
| professional_value | 0.335 / 1.22 / 167 | 0.632 / 0.94 / 169 | 0.688 / 2.08 / 153 |
| learning_value | 0.265 / 0.78 / 167 | 0.212 / 0.73 / 169 | 0.293 / 2.45 / 153 |
| evidence_strength | 0.546 / 0.99 / 167 | 0.416 / 1.90 / 169 | 0.377 / 1.69 / 153 |
| **composite** | 0.278 / 1.23 / 167 | 0.403 / 1.33 / 169 | 0.413 / 2.14 / 153 |

| Engine | winners (labelled) | recall@20 | recall@50 | engine_scored_n |
|---|---:|---:|---:|---:|
| terra | 33 | 0.152 | 0.394 | 167 |
| jev_v001 | 33 | 0.152 | 0.455 | 169 |
| jev_v002 | 33 | 0.242 | 0.515 | 153 |

## Per stratum (intersection only; n ≥ 25)

### `max_disagreement` (n=56)

| Dimension | Terra sp | Jev v001 sp | Jev v002 sp | Closer |
|---|---:|---:|---:|---|
| technical_significance | 0.153 | 0.018 | 0.116 | **terra** |
| apparent_novelty | 0.412 | 0.223 | 0.343 | **terra** |
| practical_applicability | 0.542 | 0.517 | 0.514 | **terra** |
| professional_value | -0.004 | 0.548 | 0.694 | **jev_v002** |
| learning_value | -0.167 | -0.085 | 0.196 | **jev_v002** |
| evidence_strength | 0.383 | 0.317 | 0.396 | **jev_v002** |
| composite | -0.126 | 0.209 | 0.380 | **jev_v002** |

### `score_strata` (n=95)

| Dimension | Terra sp | Jev v001 sp | Jev v002 sp | Closer |
|---|---:|---:|---:|---|
| technical_significance | 0.453 | 0.281 | 0.241 | **terra** |
| apparent_novelty | 0.386 | 0.291 | 0.183 | **terra** |
| practical_applicability | 0.630 | 0.554 | 0.357 | **terra** |
| professional_value | 0.417 | 0.664 | 0.702 | **jev_v002** |
| learning_value | 0.362 | 0.281 | 0.344 | **terra** |
| evidence_strength | 0.557 | 0.464 | 0.343 | **terra** |
| composite | 0.346 | 0.439 | 0.420 | **jev_v001** |

### Suppressed strata

| Stratum | n (intersection) | Reason |
|---|---:|---|
| `editorial_pick` | 0 | intersection n < 25 |
| `flagged` | 0 | intersection n < 25 |
| `screen_failed` | 0 | intersection n < 25 |

## STOP

- No model / prompt / policy / threshold / weight changes from this run.
- Baseline recorded at `reports/golden/baseline_v1.md` from **intersection** numbers.
- Artifacts: `reports/golden/engine_comparison.md`, `reports/golden/engine_comparison.json`, `golden/golden_scores.xlsx`
