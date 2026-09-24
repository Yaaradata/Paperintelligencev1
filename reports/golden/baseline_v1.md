# Golden baseline v1

**Recorded:** 2026-09-24T08:12:10.079634+00:00  
**Labels:** `subha` / `v1` · n_labelled=200 · **n_intersection=151**  

**ai_relevance removed:** backfilled from screen scores; Spearman 1.000 vs Terra was circular, not human agreement. Do not restore without independent human labels.

Verifier gate (scoring changes) — measured on the **3-engine intersection**:
- Per-dimension Spearman vs human must not fall more than **0.05** below these values.
- Verdict recall@50 must not fall below the value below.
- Intersection n < 150 → Cannot be determined.
- Cells / strata with n < 25 are not gate inputs.

## Per-dimension Spearman (intersection n=151)

| Dimension | Terra | Jev v001 | Jev v002 |
|---|---:|---:|---:|
| technical_significance | 0.432 | 0.248 | 0.289 |
| apparent_novelty | 0.426 | 0.321 | 0.280 |
| practical_applicability | 0.588 | 0.539 | 0.413 |
| professional_value | 0.302 | 0.615 | 0.696 |
| learning_value | 0.232 | 0.187 | 0.309 |
| evidence_strength | 0.517 | 0.394 | 0.370 |

Composite Spearman — Terra `0.219` · Jev v001 `0.367` · Jev v002 `0.427`

## Verdict recall@50 (intersection baseline)

- **terra:** 0.500 (11/22 winner_material in top 50)
- **jev_v001:** 0.591 (13/22 winner_material in top 50)
- **jev_v002:** 0.773 (17/22 winner_material in top 50)

Source: `reports/golden/engine_comparison.md`
