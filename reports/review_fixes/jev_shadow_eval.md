# Jev shadow evaluation (Phase J1) — STOP

**Generated:** 2026-09-23T07:41:14.881952+00:00  
**Model:** `typesafe/jev-1.13` (pinned; jev-latest forbidden)  
**Spend:** $0.0372 / cap $2.00  
**Defaults changed:** none (screen/audience engines still LLM)  
**DB:** `neural_rw` lacked `paper_intelligence` USAGE at run time; sample rebuilt from OpenRouter raw caches + arXiv API + report id maps.

## Scope

- Screen shadow: **300** Sep-2026 papers with existing LLM screen scores
- Audience shadow: **300** papers (title+abstract → seat scores + domain/app)
- Golden-60 (Sol/Terra calibration ids) in screen sample: **30**
- Quality stage: **not replaced** (no `so_what` / `reason_not_higher`)

## Screen gate agreement (Jev vs current LLM gate)

| Metric | Value |
|---|---:|
| N (comparable) | 300 |
| Accuracy | 98.0% |
| Precision (Jev pass \| LLM pass) | 98.0% |
| Recall | 100.0% |
| TP / FP / FN / TN | 293 / 6 / 0 / 1 |

### Top-slice flips (day scope, interpreted keep % from `GATE_PERCENTILE`)

- Config `GATE_PERCENTILE=75.0` → keep top **75.0%** per day among gate-passers in the sample.
- LLM selected: **219** · Jev selected: **219**
- Flip **in** (Jev only): **30** · Flip **out** (LLM only): **30**

## Rank correlation (Spearman, LLM vs Jev 0–10 mapped scores)

| Dimension | Spearman | N |
|---|---:|---:|
| ai_relevance | 0.647 | 300 |
| technical_significance | 0.710 | 300 |
| apparent_novelty | 0.660 | 300 |
| evidence_strength | 0.633 | 300 |
| rank_mean | 0.675 | 300 |

## Golden-60 agreement

Only **30/60** calibration ids were in the Sep-2026 screen+arxiv offline pool (DB unavailable for the rest).

- In sample with Jev ok: **30**
- Gate agreement: **30/30** (100.0%)
- Mean |Δ| by dimension:
  - `ai_relevance`: 0.93
  - `technical_significance`: 0.77
  - `apparent_novelty`: 0.68
  - `evidence_strength`: 1.13

## Jev confidence bands (screen mean confidence vs gate agreement)

| Band | N | Gate accuracy |
|---|---:|---:|
| [0.0, 0.6) | 4 | 75.0% |
| [0.6, 0.7) | 14 | 92.9% |
| [0.7, 0.8) | 121 | 96.7% |
| [0.8, 0.9) | 161 | 100.0% |
| [0.9, 1.0) | 0 | n/a |

## Cost and wall-clock

| Stage | N ok | Provider/billable $ | Wall (s) | $/paper | wall s/paper |
|---|---:|---:|---:|---:|---:|
| Jev screen | 300 | $0.0142 | 18.5 | $0.000047 | 0.062 |
| Jev audience | 300 | $0.0230 | 18.6 | $0.000077 | 0.062 |
| LLM screen (Sep16–21 actual) | 2638 | $0.2504 | — | $0.000095 | ~0.05 est |
| LLM audience (7a dry-run) | 2535 | $0.3546 | — | $0.000140 | — |

### Cost per 1,000 papers

| Stage | Before (LLM) | After (100% Jev) |
|---|---:|---:|
| Screen | $0.0949 | $0.0473 |
| Audience | $0.1399 | $0.0765 |

## Cascade proposal (screen)

| Threshold | Jev fraction | Gate accuracy on decidable | $/1k | wall s/1k (est) |
|---:|---:|---:|---:|---:|
| 0.6 | 98.7% | 98.3% | $0.0480 | 62 |
| 0.7 | 94.0% | 98.6% | $0.0502 | 61 |
| 0.8 | 53.7% | 100.0% | $0.0694 | 56 |
| 0.9 | 0.0% | n/a | $0.0949 | 50 |

**Proposed threshold for J2 cascade:** `0.8` (Jev fraction 53.7%, decidable gate accuracy 100.0%, $0.0694/1k screen).

## Audience shadow notes

- Domain agreement vs cached classify labels: **234/295** (79.3%)
- Application-domain agreement: **257/295** (87.1%)
- `tech_relevance` / `product_relevance` baselines are largely absent until audience v002 runs; Jev seat scores were collected for cost/latency but not accuracy-benchmarked against LLM seats.

## Quality stage

Jev returns typed noul/choice/score only; editorial selection depends on so_what and reason_not_higher prose from Sol/Terra. At most, Jev could shadow the six rubric scores while an LLM keeps the prose — not evaluated as a replacement in J1.

## J2 (not started)

Awaiting threshold approval. Then: `SCREEN_ENGINE` / `AUDIENCE_ENGINE` ∈ `{llm, jev, cascade}` defaulting to **`llm`**, with engine+version stamped on result rows.

## STOP

No pipeline defaults changed. Artifacts:
- `reports/review_fixes/jev_shadow_eval.md`
- `reports/review_fixes/jev_shadow_eval.json`
