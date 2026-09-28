# Verifier — golden gate, window completeness, prose audit

Three separate checks, reported separately. No default changes, no weights applied, no policy edits, no DDL.

## Part 0 — Window completeness audit (SQL only, $0)

Window 2026-09-21 .. 2026-09-23 (`papers.published_at`). Script: `scripts/audit_window_completeness.py --from 2026-09-21 --until 2026-09-23`.

Window papers **2454** · passed screen **1489** · papers with a quality row **1492** · quality rows across all engines/runs **1805**.

| defect | count | % of window | example ids (up to 10) |
|---|---:|---:|---|
| Passed screen, no quality row | 0 | 0.0% | — |
| Quality row with NULL technical_significance | 0 | 0.0% | — |
| Quality row with NULL apparent_novelty | 0 | 0.0% | — |
| Quality row with NULL practical_applicability | 0 | 0.0% | — |
| Quality row with NULL professional_value | 0 | 0.0% | — |
| Quality row with NULL learning_value | 0 | 0.0% | — |
| Quality row with NULL evidence_strength | 0 | 0.0% | — |
| Quality row with NULL/empty composite | 0 | 0.0% | — |
| Quality row with NULL/empty so_what | 765 | 31.2% | 199195<br>199196<br>199205<br>199245<br>199263<br>199267<br>199270<br>199275<br>199402<br>199407 |
| Quality row with NULL/empty reason_not_higher | 765 | 31.2% | 199195<br>199196<br>199205<br>199245<br>199263<br>199267<br>199270<br>199275<br>199402<br>199407 |
| Dimension or composite outside 0-10 | 0 | 0.0% | — |
| Quality row but no paper_intelligence_current row | 0 | 0.0% | — |
| quality_status in failed/pending/stale_content/inconsistent_attempt_without_result | 0 | 0.0% | — |
| Latest quality attempt failed and no quality row exists | 2 | 0.1% | 200094 (attempt failed: OpenRouterError: HTTP 402: {"error":{"message":"This request would exceed your available credits given your current in-flight requests. Retry after in-flight re)<br>200268 (attempt failed: OpenRouterError: HTTP 402: {"error":{"message":"This request would exceed your available credits given your current in-flight requests. Retry after in-flight re) |
| Quality row without scoring_engine stamp | 3 | 0.1% | 200454<br>200785<br>200788 |
| Quality row without prose_model stamp | 768 | 31.3% | 199195<br>199196<br>199205<br>199245<br>199263<br>199267<br>199270<br>199275<br>199402<br>199407 |
| Paper scored more than once under different engines | 287 | 11.7% | 199177 (jev_glm + openai/gpt-5.6-terra)<br>199195 (jev_glm + openai/gpt-5.6-terra)<br>199197 (jev_glm + openai/gpt-5.6-terra)<br>199198 (jev_glm + openai/gpt-5.6-terra)<br>199226 (jev_glm + openai/gpt-5.6-terra)<br>199245 (jev_glm + openai/gpt-5.6-terra)<br>199263 (jev_glm + openai/gpt-5.6-terra)<br>199267 (jev_glm + openai/gpt-5.6-terra)<br>199270 (jev_glm + openai/gpt-5.6-terra)<br>199272 (jev_glm + openai/gpt-5.6-terra) |
| arXiv v1 (raw_metadata.created) before window start | 0 | 0.0% | — |

Prose missing on **765 of 1492** scored papers (**51.3%**); publish threshold is 10%.

**Complete enough to publish from: NO.**
- prose missing on 765/1492 scored papers (51.3%) > 10%

---

## Part A — Golden gate (arithmetic only, no model, $0)

Candidate: jev_glm golden re-score, run `750f86d6-fc86-445a-b6bb-7a57e9bcae35` (200 rows, stamps [['typesafe/jev-1.13', 'prose_v001', 'systemone_v001', 'jev']]). Labels: `golden_human_scores` labeller `subha`, round `v1`, n=200. No LLM judges anything in this part.

Script: `scripts/verify_golden_gate.py --run-id 750f86d6-fc86-445a-b6bb-7a57e9bcae35`.

### Verdict: **Does not hold**

| Baseline column | Verdict | Failing checks |
|---|---|---|
| terra | Does not hold | technical_significance, apparent_novelty, evidence_strength |
| jev_v001 | Holds | — |
| jev_v002 | Does not hold | technical_significance, professional_value, learning_value, recall@50 |

`baseline_v1.md` lists three columns and does not say which one a scoring change is gated against. The candidate holds only against Jev v001, the same System One policy family, and only with zero margin on recall@50 (13/22 vs 13/22). It does not hold against Terra, the production default (`QUALITY_ENGINE=terra`): three dimensions drop more than 0.05. It does not hold against Jev v002 either. Because it fails the production column, the headline is **Does not hold**. Which column governs is an open decision; nothing was adjusted.

### Intersection (n=151, rebuilt with the baseline rule; candidate missing on 0 papers)

Spearman vs human (MAE in brackets). Floor = baseline − 0.05.

| Dimension | jev_glm | Terra | Jev v001 | Jev v002 | vs Terra floor | vs v001 floor | vs v002 floor |
|---|---:|---:|---:|---:|---|---|---|
| technical_significance | 0.214 (0.68) | 0.432 (0.70) | 0.248 (0.66) | 0.289 (1.26) | **FAIL** (0.382) | pass (0.198) | **FAIL** (0.239) |
| apparent_novelty | 0.301 (0.61) | 0.426 (0.68) | 0.321 (0.61) | 0.280 (1.59) | **FAIL** (0.376) | pass (0.271) | pass (0.230) |
| practical_applicability | 0.543 (1.13) | 0.588 (1.20) | 0.539 (1.12) | 0.413 (2.25) | pass (0.538) | pass (0.489) | pass (0.363) |
| professional_value | 0.614 (0.95) | 0.302 (1.21) | 0.615 (0.95) | 0.696 (2.07) | pass (0.252) | pass (0.565) | **FAIL** (0.646) |
| learning_value | 0.231 (0.74) | 0.232 (0.77) | 0.187 (0.75) | 0.309 (2.44) | pass (0.182) | pass (0.137) | **FAIL** (0.259) |
| evidence_strength | 0.379 (1.90) | 0.517 (0.99) | 0.394 (1.89) | 0.370 (1.70) | **FAIL** (0.467) | pass (0.344) | pass (0.320) |
| composite vs h_final_score | 0.421 (1.12) | 0.219 (1.23) | 0.368 (1.31) | 0.427 (2.12) | not a gate input | | |

Verdict recall (`winner_material`, ranked by composite; 22 winners in the intersection):

| | jev_glm | Terra | Jev v001 | Jev v002 |
|---|---:|---:|---:|---:|
| recall@20 | 0.273 (6/22) | 0.182 (4/22) | 0.182 (4/22) | 0.364 (8/22) |
| recall@50 | 0.591 (13/22) | 0.500 (11/22) | 0.591 (13/22) | 0.773 (17/22) |

Composite here is `composite.quality` (Σ weight·dim, weights unchanged). h_final_score is present on all intersection rows, so composite-vs-human-composite equals composite-vs-h_final_score.

Full 200 (informational only, not comparable to the baseline): composite vs h_final_score Spearman 0.482, MAE 1.14; recall@20 0.273 (9/33), recall@50 0.485 (16/33).

### Provenance of every figure

| Figure | Status |
|---|---|
| jev_glm per-dimension Spearman / MAE, composite, recall@20/@50 | **Re-derived** from run `750f86d6-fc86-445a-b6bb-7a57e9bcae35` rows and `golden_human_scores` |
| Intersection membership (n=151) | **Re-derived** from `golden/model_scores_hidden.csv` + human rows, using the baseline rule |
| Baseline Spearman ×18, composite ×3, recall@50 ×3 (Terra / v001 / v002) | **Re-derived** from `model_scores_hidden.csv`; all 24 match `baseline_v1.md` to 3 dp |
| Baseline MAE, recall@20, composite vs h_final_score MAE | **Re-derived** (not in `baseline_v1.md`) |
| Gate thresholds (0.05, recall@50 not lower, n ≥ 150, cells n ≥ 25) | Carried from `baseline_v1.md` (rules, not figures) |

Gate comparisons use the unrounded re-derived baseline values (e.g. v001 recall@50 = 13/22, not the rounded 0.591).

### G3c refitted weights — reported, not stored

Option (a) ridge from `reports/golden/g3c_weight_fit.json`: intercept 2.716; technical_significance -0.949 · apparent_novelty +0.041 · practical_applicability +0.722 · professional_value +1.224 · learning_value -0.275 · evidence_strength -0.205.

Applied to this run's jev_glm dimensions on the same intersection (n=151): composite vs h_final_score Spearman **0.574**, recall@20 **0.455** (10/22), recall@50 **0.773** (17/22).

Reported, not stored. The weights were fitted on **Terra** dimensions against these same human labels, so this line is in-sample for the labels and out-of-distribution for jev_glm dimensions. It is not a gate input and no weights were applied anywhere.

---

## Part B — Prose audit (paid, `openai/gpt-6-luna`, cap $0.50)

Model pinned `openai/gpt-6-luna` (OpenRouter served: openai/gpt-6-luna); price $0.10/M in, $0.50/M out, verified 2026-09-25 from openrouter.ai/openai/gpt-6-luna. Prompt `prompts/prose_audit/v001.md` (`prose_audit_v001`). Four typed judgements only; no rewriting, scoring or ranking. Script: `scripts/audit_prose_luna.py`.

Population: every window paper whose current quality row has non-null `so_what`: **727**; judged **727**.

| Flag | count | rate |
|---|---:|---:|
| so_what not specific (could describe any paper) | 0 | 0.0% |
| claims something the abstract does not support | 492 | 67.7% |
| contradicts the scores it was given | 2 | 0.3% |
| reason_not_higher is a hedge | 0 | 0.0% |
| **any flag (overall flag rate)** | **492** | **67.7%** |

Of these, 724 rows are jev_glm prose for currently scored papers. 3 (200454, 200785, 200788) are older Terra prose on papers now `skipped` (screen failed), included because they still hold non-null prose.

**Scope note.** The prompt asks whether `so_what` *or* `reason_not_higher` makes a claim the abstract does not support. The specification asked about `so_what` only. The unsupported-claim count may therefore include limitations stated in `reason_not_higher` that the abstract does not mention. In the 4 flagged examples read by hand, the unsupported part was in `so_what` (downstream product or audience claims), but the split was not measured.

### Spend

- `usage.cost` summed over 690 calls: **$0.2571** (table estimate $0.2485; calls without `usage.cost`: 0).
- Two failed smoke runs before this (8 papers each, no judgements kept): $0.0033 + $0.0026.
- **Actual Part B spend: $0.2630** of the $0.50 cap.
- 75 call errors, mostly empty output on 8-paper batches. Every affected paper was retried as a single-paper call, so all papers were judged; the retries account for the high call count.

### 10 flagged examples (full prose)

**200881 — Unbiased Gradients, Moving Stability Boundaries: Exact Mini-Batch Geometry in Linear Self-Attention**  
Flags: claims something the abstract does not support; contradicts the scores it was given  
Scores: technical=8.0, apparent=7.5, practical=4.0, professional=4.0, learning=7.5, evidence=7.0

> **so_what:** This gives training-infrastructure teams an exact, checkable criterion for when mini-batch sampling shifts stability boundaries in linear self-attention — meaning batch-size choices can destabilize runs even when gradients are unbiased. The one-step crossing test and effective-context-length law for softmax attention are directly usable as diagnostics.
>
> **reason_not_higher:** The theory is exact only for one-layer linear self-attention on linear regression, with empirical confirmation limited to four trained Transformers, so applicability to deeper production models is inferred rather than established.

**202472 — Preregistered Belief Revision Contracts**  
Flags: claims something the abstract does not support; contradicts the scores it was given  
Scores: technical=8.0, apparent=8.0, practical=4.0, professional=6.0, learning=8.0, evidence=7.0

> **so_what:** If you are orchestrating multi-agent LLM systems, PBRC offers a concrete router-enforceable contract that provably blocks conformity-driven confidence cascades while keeping an audit trail for every belief change — a deployable governance primitive, not just an analysis. The trade-off is that you must preregister evidence triggers and accept conservative fallback behavior when they are not met.
>
> **reason_not_higher:** The guarantees hold under idealized assumptions (token-invariant contracts, sound enforcement, externally validated evidence tokens) and are demonstrated mainly through simulations, so robustness in production multi-agent deployments remains untested.

**200285 — PICID: Proof-Driven Clause Learning in Neural Network Verification**  
Flags: claims something the abstract does not support  
Scores: technical=7.5, apparent=6.5, practical=6.5, professional=6.5, learning=7.5, evidence=4.0

> **so_what:** PICID gives verification teams a way to obtain independently checkable proofs of neural network properties in a standard SMT format (Alethe), reducing lock-in to verifier-specific proof formats and making audit trails for certified models more practical. Its CDCL(T) integration with a proof-producing SAT solver also points to a reusable architecture for building reliable verifiers.
>
> **reason_not_higher:** The evaluation is thin — proofs are valid only 'in the vast majority of cases' and comparative evidence against existing proof-producing tools is limited — so reliability claims need stronger empirical support before adoption.

**200327 — SurgMotion: A Video-Native Foundation Model for Universal Understanding of Surgical Videos**  
Flags: claims something the abstract does not support  
Scores: technical=8.0, apparent=7.5, practical=6.5, professional=7.5, learning=8.0, evidence=7.0

> **so_what:** A motion-oriented surgical video foundation model with a 3,658-hour pretraining corpus could serve as a shared backbone for workflow recognition, triplet detection, and skill assessment, reducing the need to train task-specific video models per surgical product. Teams building surgical analytics should benchmark it as a drop-in encoder before investing in bespoke pretraining.
>
> **reason_not_higher:** Practical adoption hinges on deployment factors the abstract does not address, such as inference cost on clinical video streams, licensing of the 50 data sources, and validation beyond the curated benchmark suite.

**200843 — Neighbor-Aware Token Reduction via Hilbert Curve for Vision Transformers**  
Flags: claims something the abstract does not support  
Scores: technical=6.5, apparent=6.5, practical=6.5, professional=6.5, learning=7.0, evidence=3.0

> **so_what:** If you deploy ViTs under latency or memory constraints, Hilbert-curve reordering offers a drop-in way to prune or merge tokens while keeping local spatial context, potentially improving the accuracy-efficiency trade-off over standard ToMe-style merging. The practical question is whether the gains hold on your specific backbone and workload.
>
> **reason_not_higher:** The experimental evidence is thin — limited benchmarks and ablations make it hard to judge how the claimed trade-offs generalize beyond the tested settings.

**201202 — Deploying Foundation Models for Embodied Navigation**  
Flags: claims something the abstract does not support  
Scores: technical=6.5, apparent=6.5, practical=6.0, professional=6.5, learning=7.0, evidence=5.0

> **so_what:** Offers two deployable techniques for FM-based navigation: mining scene data to personalize behavior in unseen environments, and a memory-head mechanism that cuts context usage roughly in half while improving long-horizon task success by ~20%. Relevant to any team shipping LLM-driven agents under real context-length and latency budgets.
>
> **reason_not_higher:** Real-world validation is limited to one robot in one lab environment, and the reported gains come from small-sample comparisons whose generality across environments and platforms is untested.

**201397 — LOIP:Collaborative Lossless LLM Inference Serving with Offloading-based Pipeline Parallelism on Edge Devices**  
Flags: claims something the abstract does not support  
Scores: technical=8.0, apparent=6.5, practical=7.0, professional=7.5, learning=8.0, evidence=6.5

> **so_what:** LOIP makes collaborative lossless inference of large models feasible on clusters of memory-constrained edge devices by overlapping offloading, compute, and communication, which matters for teams deploying private LLM serving where cloud egress or data residency rules out remote APIs. The reported 8.8–20.3x speedups over baselines suggest edge-cluster serving is now an operationally viable tier rather than a research curiosity.
>
> **reason_not_higher:** Evidence comes from a single model (LLaMA3.3-70B) on five Jetson devices under controlled bandwidth and request patterns, so generalization to other models, larger clusters, and production traffic remains untested.

**201759 — Enriching Speech Emotion Representations with Conversational Context**  
Flags: claims something the abstract does not support  
Scores: technical=7.0, apparent=5.5, practical=6.5, professional=7.0, learning=7.0, evidence=6.0

> **so_what:** For voice-interface teams, ACERT suggests that a sliding window of conversational context is a simple, modular way to improve utterance-level emotion detection without changing the underlying encoder. Ablations indicate the gains come from emotional continuity rather than speaker or acoustic cues, so the module should transfer across front-end models.
>
> **reason_not_higher:** The approach is a straightforward contextual-window extension with moderate novelty, and evaluation rests on standard benchmarks (IEMOCAP, MELD, SAFE) whose class imbalance and recording conditions limit confidence in real-world gains.

**202337 — MORSE: Multi-Context Ordering via Reverse Scoring for Evidence-Preserving Compression**  
Flags: claims something the abstract does not support  
Scores: technical=7.0, apparent=6.5, practical=7.0, professional=7.5, learning=7.5, evidence=7.0

> **so_what:** For RAG and long-context systems that compress retrieved evidence, context ordering is not a neutral detail: naive ordering can silently drop your strongest evidence. MORSE provides a drop-in, compression-aware ordering method that improves evidence survival and downstream QA across budgets and compressors.
>
> **reason_not_higher:** Gains are demonstrated on multi-hop QA benchmarks with specific scoring models, and the added ordering pass introduces compute overhead whose cost-benefit in broader production settings remains unquantified.

**202938 — HaRP: High Dynamic Range Photosequencing through Dual Reversed Shutter Scanning**  
Flags: claims something the abstract does not support  
Scores: technical=7.5, apparent=7.0, practical=4.5, professional=6.0, learning=7.5, evidence=4.0

> **so_what:** For camera and ISP teams evaluating rolling-shutter-with-global-reset sensors, dual reversed scanning is a concrete path to recover dynamic range and capture speed, and the row-adaptive alignment plus hallucination network shows how the two views can be fused. Adoption, however, presumes the ability to build or source a dual-scanner imaging pipeline.
>
> **reason_not_higher:** The approach depends on custom coaxial dual-scanner hardware that is not available in commodity mobile devices, and the reported evidence base is thin, so near-term deployability is limited.
