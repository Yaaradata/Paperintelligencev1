# Jev quality v002 vs v001 — STOP

**Generated:** 2026-09-24T05:57:23.163973+00:00  
**Model:** `typesafe/jev-1.13` · **Policy:** `quality_v002`  
**Spend:** $0.2141 / $2.00  
**N:** 3366 (sol=1779, terra=1587) · ok=3366  
**Winner for CSV:** **v001** (higher Terra/Sol Spearman and composite agreement).
v002 **did** lift confidence (now reaches ≥0.9 for 42/3366 papers) but **lowered**
rank agreement on almost every dimension — so the adverb-ladder hypothesis alone
does not explain the weak J1b numbers; observable levels helped calibration of
confidence, not Terra alignment.

## Design changes (v002)

- 5–6 observable criteria levels (no adverb ladders)
- No cross-question instructions
- `professional_value` = mean(`decision_relevance_eng`, `decision_relevance_product`)
- Dropped “ignore author prestige”
- Composite weights unchanged; evidence still only via evidence_factor

## (a) Per-dimension Spearman — side by side

### vs Sol (Sep 1–15)

| Dimension | v001 | v002 | Δ |
|---|---:|---:|---:|
| technical_significance | 0.539 | 0.322 | -0.217 |
| apparent_novelty | 0.594 | 0.375 | -0.219 |
| practical_applicability | 0.713 | 0.583 | -0.131 |
| professional_value | 0.498 | 0.429 | -0.069 |
| learning_value | 0.378 | 0.475 | 0.097 |
| evidence_strength | 0.684 | 0.570 | -0.114 |

Composite Spearman: v001 **0.445** · v002 **0.388**
Top-20 / Top-50: v001 **2/20** / **11/50** · v002 **2/20** / **9/50**

### vs Terra (Sep 16–21)

| Dimension | v001 | v002 | Δ |
|---|---:|---:|---:|
| technical_significance | 0.563 | 0.333 | -0.229 |
| apparent_novelty | 0.610 | 0.466 | -0.144 |
| practical_applicability | 0.706 | 0.544 | -0.162 |
| professional_value | 0.457 | 0.382 | -0.076 |
| learning_value | 0.435 | 0.483 | 0.048 |
| evidence_strength | 0.685 | 0.529 | -0.155 |

Composite Spearman: v001 **0.533** · v002 **0.448**
Top-20 / Top-50: v001 **5/20** / **15/50** · v002 **6/20** / **16/50**

## Confidence bands (v002)

Max mean confidence: **0.943** · Any ≥0.9: **True**

### Sol

| Band | N | composite MAE |
|---|---:|---:|
| [0.0,0.6) | 12 | 3.56 |
| [0.6,0.7) | 165 | 3.38 |
| [0.7,0.8) | 750 | 3.07 |
| [0.8,0.9) | 831 | 2.87 |
| [0.9,1.0) | 21 | 2.66 |

### Terra

| Band | N | composite MAE |
|---|---:|---:|
| [0.0,0.6) | 11 | 3.72 |
| [0.6,0.7) | 116 | 2.76 |
| [0.7,0.8) | 640 | 2.59 |
| [0.8,0.9) | 799 | 2.45 |
| [0.9,1.0) | 21 | 2.37 |

## Cost / wall (v002 quality)

$0.0636 / 1k · 80.7 s / 1k · total $0.2141 in 272s

## STOP

- Per-paper cache: `reports/review_fixes/jev_j1b_quality_scores.json`
- Next: `export_terra_vs_jev_1000.py` using **v001**
