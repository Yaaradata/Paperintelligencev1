# G3c — composite weight refit (proposal only)

**Generated:** 2026-09-24T08:16:59.558421+00:00  
**n (Terra rows):** 167 · **n (mixed Terra+Jev):** 167  
**config/policies/settings.yaml: UNCHANGED** — numbers below are proposals only.

## Baseline (current weights)

- G2 cited (full Terra coverage): Spearman **0.278** / recall@20 **0.152** / recall@50 **0.394**
- Recomputed same-n quality=Σw·dim (n=167, winners=26): Spearman **0.279** / recall@20 **0.192** / recall@50 **0.500**
- Noise floor (Spearman SE ≈ 1/√(n−1)): **0.078**

## Held-out metrics (5-fold OOF)

| Option | OOF Spearman | recall@20 | recall@50 | Δρ vs G2 cited | Noise flag |
|---|---:|---:|---:|---:|---|
| (a) Ridge Terra-6 → h_final | 0.648 | 0.385 | 0.808 | 0.370 | **above noise** |
| (b) logistic Terra-6 → winner_material | 0.634 | 0.346 | 0.692 | 0.356 | **above noise** |
| (c) mixed Terra tech/novelty/evidence + Jev prof/practical | 0.606 | 0.385 | 0.692 | 0.328 | **above noise** |

## Fitted weights (full-data proposal)

### (a) Ridge Terra-6 → h_final

Intercept: `2.7158`

| Feature | Signed coef | L1 share |
|---|---:|---:|
| `technical_significance` | -0.9491 | 0.2779 |
| `apparent_novelty` | 0.0406 | 0.0119 |
| `practical_applicability` | 0.7221 | 0.2115 |
| `professional_value` | 1.2236 | 0.3583 |
| `learning_value` | -0.2747 | 0.0804 |
| `evidence_strength` | -0.2047 | 0.0600 |

### (b) logistic Terra-6 → winner_material

Intercept: `-11.8682`

| Feature | Signed coef | L1 share |
|---|---:|---:|
| `technical_significance` | -1.1034 | 0.2228 |
| `apparent_novelty` | -0.1445 | 0.0292 |
| `practical_applicability` | 1.5765 | 0.3184 |
| `professional_value` | 1.6386 | 0.3309 |
| `learning_value` | -0.2965 | 0.0599 |
| `evidence_strength` | -0.1924 | 0.0389 |

### (c) mixed Terra tech/novelty/evidence + Jev prof/practical

Intercept: `0.4884`

| Feature | Signed coef | L1 share |
|---|---:|---:|
| `terra_technical_significance` | 0.1628 | 0.1442 |
| `terra_apparent_novelty` | 0.0119 | 0.0105 |
| `terra_evidence_strength` | 0.0522 | 0.0463 |
| `jev_professional_value` | 0.8050 | 0.7131 |
| `jev_practical_applicability` | -0.0970 | 0.0859 |

## Interpretation

- Do **not** ship weights from this run. Propose only.
- Option (b) ranks by P(winner_material); Spearman vs h_final is secondary.
- Option (c) requires both Terra and Jev at inference — operational cost.
- L1 share is |coef| / Σ|coef| for readability; scoring uses signed coefs + intercept.
- Compare human–human ceiling (double_label_30) before treating Spearman ~0.6 as a win.
