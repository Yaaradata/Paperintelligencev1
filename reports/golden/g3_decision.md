# G3 decision report

**Generated:** 2026-09-24T08:16:00Z  
**Stance:** G2 accepted — **do not switch engines**. No model, prompt, policy, or weight changes shipped.

---

## Verdict

1. **Comparison is fixed.** Headline metrics now use the 3-engine intersection (n=151); `ai_relevance` is gone; n&lt;25 strata/cells are suppressed. Baseline regenerated from intersection.
2. **Screen gate drops real winners.** 6/24 gate-drop papers were human `shortlist`/`winner_material`. Terra would have ranked the best of them mid-pack (~42–65/191), not top-20 — so the gate is not only dropping junk, but Terra alone would not have rescued them into the head of the list either.
3. **Composite weights are the bottleneck, and refit helps above noise.** Held-out Spearman jumps from **0.278 → ~0.61–0.65** under all three proposals. **Do not ship yet** — wait for `double_label_30` (Ranjith) to establish the human–human ceiling before treating 0.6 as “good.”
4. **Next action:** get Ranjith labels on `golden/double_label_30.xlsx`; then decide whether to (i) adopt a refit composite, (ii) soften/bypass screen for high-Terra survivors, or (iii) keep current stack and accept gate+weight loss.

---

## G3a — comparison fix (read-only)

Artifacts:
- `reports/golden/engine_comparison.md` / `.json`
- `reports/golden/baseline_v1.md` (regenerated from intersection)
- `golden/golden_scores.xlsx`

### What changed
- **`ai_relevance` removed** from comparison and baseline. It was backfilled from screen scores; Spearman 1.000 vs Terra was circular, not human agreement.
- **Headline = intersection** of papers with full six quality dims on Terra + Jev v001 + Jev v002: **n=151**.
- **Secondary table** = per-engine full coverage with n per cell.
- **Suppressed:** any stratum/cell with n&lt;25 (`editorial_pick`, `flagged`, `screen_failed`, and any thin cells).

### Headline (intersection n=151)

| Dimension | Terra | Jev v001 | Jev v002 | Closer |
|---|---:|---:|---:|---|
| technical_significance | 0.432 | 0.248 | 0.289 | terra |
| apparent_novelty | 0.426 | 0.321 | 0.280 | terra |
| practical_applicability | 0.588 | 0.539 | 0.413 | terra |
| professional_value | 0.302 | 0.615 | 0.696 | jev_v002 |
| learning_value | 0.232 | 0.187 | 0.309 | jev_v002 |
| evidence_strength | 0.517 | 0.394 | 0.370 | terra |
| **composite** | **0.219** | **0.367** | **0.427** | **jev_v002** |

Verdict recall@50 (intersection, 22 winners): Terra 0.500 · Jev v001 0.591 · Jev v002 0.773.

**Unchanged conclusion vs G2:** Terra wins most dimensions; Jev wins composite/recall. Still no engine switch.

Strata kept: `max_disagreement` (n=56), `score_strata` (n=95).

---

## G3b — gate-drop scoring (paid)

Artifacts:
- `reports/golden/g3b_run.json` (run_id excluded from current-quality loads)
- `reports/golden/g3b_gate_drop.md` / `.json`

| | |
|---|---|
| run_id | `866234e7-fb27-4ecd-a881-318cca1bf72e` |
| pipeline | `golden_g3b_gate_drop_eval` (**not** current quality) |
| model | `openai/gpt-5.6-terra` |
| scored | 24/24 |
| cost | **$0.068** (cap $1) |
| rank pool | 191 golden papers with Terra composites |

### Human labels on the 24

**6 / 24** labelled `shortlist` or `winner_material`:

| paper_id | stratum | verdict | h_final | Terra quality | rank / 191 |
|---:|---|---|---:|---:|---:|
| 196694 | screen_failed | winner_material | 9.0 | 7.82 | **42** |
| 137619 | flagged | winner_material | 9.5 | 7.62 | 64 |
| 196256 | screen_failed | shortlist | 8.5 | 7.62 | 65 |
| 194089 | flagged | winner_material | 9.0 | 7.10 | 110 |
| 197726 | flagged | winner_material | 9.0 | 6.72 | 134 |
| 196699 | screen_failed | shortlist | 8.0 | 6.62 | 136 |

### Gate-drop reading
- Screen is **not** precision-only: it drops papers humans would shortlist/win.
- Even after Terra scores them, none of the six land in top-20 of the golden Terra ranking; best is rank 42.
- Oddity worth noting: `196708` (human **reject**, h_final 3.5) scored Terra **8.58 → rank 3/191**. Composite/weight mismatch again, not a reason to open the gate blindly.

---

## G3c — composite refit (proposal only)

Artifacts: `reports/golden/g3c_weight_fit.md` / `.json`  
**`config/policies/settings.yaml` unchanged.**

Baseline (G2 cited): Spearman **0.278** / recall@20 **0.152** / recall@50 **0.394**.  
Same-n recomputed quality=Σw·dim (n=167, 26 winners): 0.279 / 0.192 / 0.500.  
Noise floor: Spearman SE ≈ **0.078** (1/√(n−1)).

### Held-out (5-fold OOF)

| Option | OOF Spearman | recall@20 | recall@50 | Δρ vs G2 | Noise |
|---|---:|---:|---:|---:|---|
| (a) Ridge Terra-6 → h_final | **0.648** | 0.385 | 0.808 | +0.370 | **above noise** |
| (b) logistic Terra-6 → winner | 0.634 | 0.346 | 0.692 | +0.356 | **above noise** |
| (c) Terra tech/novelty/evidence + Jev prof/practical | 0.606 | 0.385 | 0.692 | +0.328 | **above noise** |

**None of the options’ held-out Spearman gains are within noise** for n≈200 (all Δρ ≫ 0.078).

### Proposed weights (full-data; scoring = signed coefs + intercept)

**(a) Ridge → h_final** — intercept `2.716` (best Spearman / recall@50)

| Feature | Signed coef | L1 share |
|---|---:|---:|
| technical_significance | −0.949 | 0.278 |
| apparent_novelty | +0.041 | 0.012 |
| practical_applicability | +0.722 | 0.211 |
| professional_value | +1.224 | 0.358 |
| learning_value | −0.275 | 0.080 |
| evidence_strength | −0.205 | 0.060 |

**(b) logistic → winner_material** — intercept `−11.87`; ranks by P(winner)

| Feature | Signed coef | L1 share |
|---|---:|---:|
| technical_significance | −1.103 | 0.223 |
| apparent_novelty | −0.145 | 0.029 |
| practical_applicability | +1.577 | 0.318 |
| professional_value | +1.639 | 0.331 |
| learning_value | −0.297 | 0.060 |
| evidence_strength | −0.192 | 0.039 |

**(c) mixed Terra+Jev** — intercept `0.488`; needs both engines at inference

| Feature | Signed coef | L1 share |
|---|---:|---:|
| terra_technical_significance | +0.163 | 0.144 |
| terra_apparent_novelty | +0.012 | 0.011 |
| terra_evidence_strength | +0.052 | 0.046 |
| jev_professional_value | +0.805 | 0.713 |
| jev_practical_applicability | −0.097 | 0.086 |

Pattern: current weights over-weight tech/novelty/evidence and under-weight **professional_value** + **practical_applicability** relative to human finals. Option (a)/(b) even assign **negative** coefs to tech/learning/evidence — consistent with Terra dims correlating well individually but the current composite pointing the wrong way.

### Caveat before shipping weights
Spearman ~0.6 looks like a large win vs 0.278, but **without human–human reliability we cannot say whether 0.6 is near ceiling or still poor.** That is what double-labelling is for.

---

## Double-label set (human–human ceiling)

- Workbook: `golden/double_label_30.xlsx` (blind, same format as G1)
- Sample meta: `golden/double_label_30_sample.json` (Subha labels hidden from workbook)
- Target import: `--labeller ranjith --label-round v1`
- Mix: strata `{editorial_pick:4, flagged:2, max_disagreement:6, score_strata:14, screen_failed:4}`; Subha verdicts `{winner_material:8, shortlist:8, maybe:7, reject:7}`

---

## Decisions locked / open

| Item | Status |
|---|---|
| Engine choice (Terra primary) | **Locked** — no switch |
| Weight / policy / prompt / model changes | **Locked off** this phase |
| Intersection baseline for verifier | **Updated** (`baseline_v1.md`) |
| Ship refit composite | **Open** — wait for Ranjith double-labels |
| Screen-gate policy | **Open** — G3b shows drop of 6 shortlist/winners; revisit after ceiling + weight decision |

---

## STOP

No model, prompt, policy, or weight changes.  
Primary stop artifact: `reports/golden/g3_decision.md` (this file).
