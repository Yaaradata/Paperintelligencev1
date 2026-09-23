# Jev J1b — STOP

**Generated:** 2026-09-23T09:47:33.448986+00:00  
**Model:** `typesafe/jev-1.13`  
**Spend:** $0.2343 / $2.00  
**Cascade:** not started  
**DB connection:** `neural_admin` (live RDS). **neural_rw role:** USAGE on `paper_intelligence` = true; SELECT on all 29 base tables = true (0 missing).

## Decision numbers (lead)

**Recommend Jev-for-all-survivors?** **NO — keep LLM for quality** (bar: Spearman≥0.75 every dim **and** top-50≥35/50 in **both** Sol and Terra windows).

### (a) Per-dimension Spearman — Jev vs LLM quality

| Dimension | vs Sol (Sep 1–15) | vs Terra (Sep 16–21) |
|---|---:|---:|
| technical_significance | 0.539 | 0.563 |
| apparent_novelty | 0.594 | 0.610 |
| practical_applicability | 0.713 | 0.706 |
| professional_value | 0.498 | 0.457 |
| learning_value | 0.378 | 0.435 |
| evidence_strength | 0.684 | 0.685 |

### (b) Top-50 overlap by composite quality score

| Window | Top-50 overlap | Top-20 overlap |
|---|---:|---:|
| Sol (Sep 1–15) | **11/50** | 2/20 |
| Terra (Sep 16–21) | **15/50** | 5/20 |

### (c) Cost & wall-clock per 1,000 papers (quality scoring)

| Engine | $/1,000 | wall-clock / 1,000 |
|---|---:|---:|
| Jev 6-dim (this run) | **$0.0574** | **63.2 s** (~1.1 min) |
| Terra full quality (Sep16–21 actual $1.2344/380) | **$3.2484** | not logged in that run |

## 0. Grant confirmation

Confirmed for role `neural_rw` (checked via `has_schema_privilege` / `has_table_privilege`):

- `USAGE` on schema `paper_intelligence`: **true**
- `SELECT` on all **29** base tables in that schema: **true** (0 missing)

No GRANT statements needed. This evaluation read title/abstract + classification rows from live RDS (not caches). Session user for the run was `neural_admin`; `neural_rw` privileges were verified separately against the same DB.

## 1. Screen — top-slice is the decision

Sample **704** papers stratified across screen rank_mean, percentile boundaries (15/50/75), plus **103** Sep 16–21 gate failures.

### Spearman (LLM vs Jev)

| Dimension | Spearman | N |
|---|---:|---:|
| ai_relevance | 0.733 | 704 |
| technical_significance | 0.660 | 704 |
| apparent_novelty | 0.603 | 704 |
| evidence_strength | 0.519 | 704 |
| rank_mean | 0.575 | 704 |

### Top-slice agreement at GATE_PERCENTILE 15 / 50 / 75

| Pct | LLM sel | Jev sel | Flip in | Flip out | In % of LLM sel | Out % | Jaccard | Flip-in with quality | Mean Q of flip-in |
|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| 15 | 89 | 89 | 62 | 62 | 69.7% | 69.7% | 0.179 | 34 | 7.97 |
| 50 | 302 | 302 | 91 | 91 | 30.1% | 30.1% | 0.537 | 18 | 7.32 |
| 75 | 449 | 449 | 69 | 69 | 15.4% | 15.4% | 0.734 | 7 | 7.17 |

### Flip-in papers that already have quality (sample)

**At 15%:**
- `3822` Q=7.76 final=7.18 (openai/gpt-5.6-terra): CatchBench: When Can an Agent Failure Be Caught?
- `136374` Q=8.58 final=8.19 (openai/gpt-5.6-sol): Hearing the Whispers: Black-Box Membership Inference Attacks on Finetuned TTS Mo
- `136943` Q=8.22 final=7.85 (openai/gpt-5.6-sol): How Output Format Confounds Data Quality and Capability in Instruction Tuning
- `138212` Q=8.36 final=7.86 (openai/gpt-5.6-sol): RealCADBench: Benchmarking Parametric CAD Modeling from Industrial Design Intent
- `138345` Q=8.46 final=7.83 (openai/gpt-5.6-terra): Extending concurrent separation logic to the hardware level to verify the xv6 OS
- `142563` Q=8.18 final=7.69 (openai/gpt-5.6-sol): Compute-in-Memory Attention: A Time-Domain Analog Softmax Circuit with RC-Tunabl
- `184777` Q=8.24 final=7.87 (openai/gpt-5.6-sol): PARSER: Read in Parallel, Reason in Depth for Long-Context LLM Agents
- `184829` Q=7.82 final=7.23 (openai/gpt-5.6-sol): NormViz: A Benchmark and Framework for Grounding Multimodal Reasoning in Global 
- `184983` Q=8.22 final=7.85 (openai/gpt-5.6-sol): EquiGQNet: Fast Grasp Quality Evaluation via Shared Equivariant Point Cloud Enco
- `185020` Q=8.10 final=7.74 (openai/gpt-5.6-sol): Distance-Aware Attention and Wall-Distance Expert Routing for Transformer-Based 
- `185082` Q=8.50 final=7.99 (openai/gpt-5.6-sol): BlueprintAgent: Constraint-Triggered Targeted Revisits for Simulation-Ready Gene
- `185983` Q=7.80 final=7.33 (openai/gpt-5.6-sol): Rank Without an Oracle: Deviation-Aware Interaction-Rank Selection from Offline 
- `185987` Q=7.94 final=7.58 (openai/gpt-5.6-sol): Reachability-Certified Subteam Decomposition for Locally Interacting Multi-Agent
- `186788` Q=8.14 final=7.77 (openai/gpt-5.6-sol): Vision-language models know more about agriculture than they show and rubric-gro
- `187663` Q=8.36 final=7.86 (openai/gpt-5.6-sol): Grounding Agent Memory: Environment-Probing Curation for Enterprise Agents

**At 75%:**
- `195840` Q=6.48 final=5.80 (openai/gpt-5.6-terra): Unleash LLMs Potential for Sequential Recommendation by Coordinating Dual Dynami
- `197997` Q=7.54 final=6.86 (openai/gpt-5.6-terra): Aligning with Lived Experience: Heterogeneous Benefits of Fine Tuning in Mental 
- `198588` Q=7.90 final=7.07 (openai/gpt-5.6-terra): EnterpriseVal: Quantifying the Efficacy, Reliability and Value of Generative AI 
- `198990` Q=6.66 final=6.06 (openai/gpt-5.6-terra): Forecasting Intrathecal Tracer Enhancement from Pre-Contrast Brain MRI: Direct R
- `199509` Q=7.14 final=6.28 (openai/gpt-5.6-terra): ARCGym: Benchmarking Deep Reinforcement Learning in Autonomous Robotic Colonosco
- `199511` Q=6.94 final=6.21 (openai/gpt-5.6-terra): C$^{2}$-INR: Customized Convolutional Implicit Neural Representation
- `200755` Q=7.52 final=6.96 (openai/gpt-5.6-terra): Who Does What in AI Auditing? Designing Human-AI Collaboration for Auditing Gene

## 2. Quality rubric via Jev

Eligible: **Sol Sep1–15 = 1779**, **Terra Sep16–21 = 1587**, run N = **3366** (spec cited ~1887; this is the current DB window set).
Cost/1k: **$0.0574** · wall/1k ≈ **63.2 s** ($0.000057/paper).

### vs Sol (Sep 1–15) — n_ok=1779/1779

| Dimension | Spearman | mean \|Δ\| | N |
|---|---:|---:|---:|
| technical_significance | 0.539 | 0.57 | 1779 |
| apparent_novelty | 0.594 | 0.94 | 1779 |
| practical_applicability | 0.713 | 1.60 | 1779 |
| professional_value | 0.498 | 1.02 | 1779 |
| learning_value | 0.378 | 0.36 | 1779 |
| evidence_strength | 0.684 | 1.54 | 1779 |

- Composite Spearman: **0.445** · MAE: **1.68**
- Top-20 overlap: **2/20** · Top-50: **11/50**

Confidence bands (composite MAE):

| Band | N | composite MAE |
|---|---:|---:|
| [0.0,0.6) | 80 | 2.63 |
| [0.6,0.7) | 368 | 2.12 |
| [0.7,0.8) | 1162 | 1.55 |
| [0.8,0.9) | 169 | 1.17 |
| [0.9,1.0) | 0 | n/a |

### vs Terra (Sep 16–21) — n_ok=1587/1587

| Dimension | Spearman | mean \|Δ\| | N |
|---|---:|---:|---:|
| technical_significance | 0.563 | 0.40 | 1587 |
| apparent_novelty | 0.610 | 0.47 | 1587 |
| practical_applicability | 0.706 | 1.11 | 1587 |
| professional_value | 0.457 | 0.74 | 1587 |
| learning_value | 0.435 | 0.42 | 1587 |
| evidence_strength | 0.685 | 1.12 | 1587 |

- Composite Spearman: **0.533** · MAE: **1.24**
- Top-20 overlap: **5/20** · Top-50: **15/50**

Confidence bands (composite MAE):

| Band | N | composite MAE |
|---|---:|---:|
| [0.0,0.6) | 42 | 2.02 |
| [0.6,0.7) | 314 | 1.67 |
| [0.7,0.8) | 1051 | 1.16 |
| [0.8,0.9) | 180 | 0.81 |
| [0.9,1.0) | 0 | n/a |

## 3. Audience seats vs editorial ground truth

Past TECH picks (n=4): mean tech_relevance=**8.62** min=8.50
Past PRODUCT picks (n=4): mean product_relevance=**8.00** min=7.00

Pick-level scores:

- TECH `3611` (linkedin_winner): tech=8.5 product=5.5
- TECH `143079` (runner_up): tech=8.5 product=4.0
- TECH `172395` (winner): tech=9.0 product=8.5
- TECH `184890` (winner): tech=8.5 product=7.5
- PRODUCT `2184` (winner): tech=7.5 product=8.5
- PRODUCT `42672` (runner_up): tech=8.5 product=8.5
- PRODUCT `120294` (linkedin_winner): tech=7.5 product=7.0
- PRODUCT `194758` (winner): tech=6.0 product=8.0

### Both / one / neither by threshold (full validation set)

| Threshold | both | one | neither | N |
|---:|---:|---:|---:|---:|
| 5.0 | 71 | 34 | 5 | 110 |
| 6.0 | 55 | 47 | 8 | 110 |
| 7.0 | 31 | 53 | 26 | 110 |
| 8.0 | 9 | 31 | 70 | 110 |

**Proposed pool mins:** `TECH_POOL_MIN≈8.5` · `PRODUCT_POOL_MIN≈7.0` (p25 of past picks on their seat score).

## Architecture proposal (not implemented)

Bar (Spearman≥0.75 every dim **and** top-50≥35/50 in **both** windows): **DOES NOT HOLD — keep LLM for quality**.
- Sol: dims_ok=False top-50=11/50
- Terra: dims_ok=False top-50=15/50

Bar not met in both windows — keep LLM for quality scoring. Do not adopt Jev-for-all-survivors.

### Cost & runtime per Sep16–21-scale window (~2535 survivors)

| Design | Quality / prose $ | Est. quality wall | Notes |
|---|---:|---:|---|
| Today: GATE=75% full Terra quality (~1901 papers) | **$6.18** | Terra wall not logged | screen LLM ~$0.24 unchanged |
| Proposed: Jev 6-dim on all 2535 survivors + LLM prose top 150 | **$0.63** (Jev $0.15 + prose $0.49) | ~160 s Jev (~2.7 min at this run's concurrency) + LLM prose for 150 | Δ vs today quality path: $5.78 |

Economics above are illustrative only — **do not adopt** until both-window bar holds.

## STOP

- No `SCREEN_ENGINE` / `AUDIENCE_ENGINE` cascade.
- No pipeline default changes.
- Artifacts: `reports/review_fixes/jev_j1b.md`, `reports/review_fixes/jev_j1b.json`
