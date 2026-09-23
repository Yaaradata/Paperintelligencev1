# PaperIntelligence v1 — Run Report

**Window:** 2026-09-14 → 2026-09-14 (published_at)  
**Generated:** 2026-09-21 07:03 UTC  
**Pipeline:** relevance (free) → normalize_authors (free) → screen → classify → quality → affiliation → adjudication

## 1. Funnel

| Step | Papers |
|---|---|
| arXiv ingested in window | 1065 |
| Rejected by relevance (free, pre-LLM) | 384 |
| Entered paid stages | 681 |
| Passed screen gate | 662 |
| Failed screen gate (scores kept) | 19 |

Relevance runs first precisely so the paid stages never see the rejected papers.

## 2. Stage coverage

| Task type | Papers | Result rows |
|---|---|---|
| screen | 681 | 681 |
| application_domain | 637 | 644 |
| audience | 637 | 644 |
| domain | 637 | 644 |
| subdomain | 637 | 644 |
| quality | 189 | 189 |


| Stage run | Version | Status | In | OK | Failed | Seconds |
|---|---|---|---|---|---|---|
| screen | v001 | running | 15 | 0 | 0 |  |
| screen | v001 | partial | 5210 | 5194 | 16 | 537.8 |
| affiliation | v001 | running | 5 | 0 | 0 |  |
| affiliation | v001 | succeeded | 5 | 0 | 0 | 2.2 |
| affiliation | v001 | succeeded | 5 | 1 | 0 | 0.8 |
| affiliation | v001 | succeeded | 5 | 3 | 0 | 4.9 |
| affiliation | v001 | succeeded | 10 | 4 | 0 | 0.5 |
| affiliation | v001 | succeeded | 10 | 4 | 0 | 1.1 |
| affiliation | v001 | succeeded | 10 | 4 | 0 | 0.6 |
| affiliation | v001 | succeeded | 10 | 4 | 0 | 0.5 |
| affiliation | v001 | succeeded | 10 | 4 | 0 | 1.2 |
| affiliation | v001 | succeeded | 10 | 4 | 0 | 1.0 |
| affiliation | v001 | succeeded | 10 | 4 | 0 | 0.7 |
| affiliation | v001 | succeeded | 10 | 4 | 0 | 1.1 |
| screen | v001 | succeeded | 16 | 16 | 0 | 13.2 |
| affiliation | v001 | succeeded | 8 | 4 | 0 | 6.4 |
| affiliation | v001 | succeeded | 8 | 4 | 0 | 0.2 |
| classify | v001 | partial | 5092 | 1064 | 4028 | 217.5 |
| quality | v001 | partial | 764 | 200 | 564 | 84.7 |
| quality | v001 | partial | 564 | 215 | 349 | 90.8 |
| affiliation | v001 | succeeded | 8 | 0 | 0 | 2.4 |
| affiliation | v001 | succeeded | 8 | 0 | 0 | 0.1 |
| affiliation | v001 | succeeded | 8 | 0 | 0 | 0.1 |
| affiliation | v001 | succeeded | 20 | 8 | 0 | 14.6 |
| affiliation | v001 | succeeded | 20 | 8 | 0 | 0.6 |
| affiliation | v001 | succeeded | 20 | 8 | 0 | 0.6 |
| affiliation | v001 | succeeded | 20 | 8 | 0 | 1.8 |
| affiliation | v001 | succeeded | 20 | 8 | 0 | 1.0 |
| affiliation | v001 | succeeded | 20 | 8 | 0 | 1.2 |
| affiliation | v001 | succeeded | 20 | 8 | 0 | 2.1 |
| affiliation | v001 | succeeded | 415 | 24 | 0 | 23.1 |
| quality | v001 | succeeded | 858 | 858 | 0 | 328.1 |
| affiliation | v001 | succeeded | 1232 | 62 | 0 | 70.8 |
| adjudication | v001 | succeeded | 0 | 5225 | 0 | 3.0 |
| classify | v001 | partial | 1009 | 994 | 15 | 279.0 |
| adjudication | v001 | succeeded | 0 | 5225 | 0 | 2.7 |
| classify | v001 | succeeded | 15 | 15 | 0 | 17.8 |
| adjudication | v001 | succeeded | 0 | 5225 | 0 | 2.5 |
| affiliation | v001 | running | 1 | 0 | 0 |  |
| affiliation | v001 | succeeded | 37 | 17 | 0 | 55.2 |
| adjudication | v001 | succeeded | 0 | 5225 | 0 | 2.4 |
| affiliation | v001 | running | 1 | 0 | 0 |  |
| adjudication | v001 | succeeded | 0 | 5225 | 0 | 2.5 |
| affiliation | v001 | running | 1 | 0 | 0 |  |
| adjudication | v001 | succeeded | 0 | 5225 | 0 | 2.4 |
| screen | v001 | partial | 2312 | 2280 | 32 | 302.0 |
| classify | v001 | partial | 2251 | 2173 | 78 | 869.7 |
| affiliation | v001 | succeeded | 7541 | 5213 | 0 | 13125.6 |
| affiliation | v001 | succeeded | 200 | 135 | 0 | 102.5 |
| quality | v001 | succeeded | 547 | 547 | 0 | 220.5 |
| affiliation | v001 | succeeded | 200 | 165 | 0 | 491.9 |
| affiliation | v001 | succeeded | 570 | 401 | 0 | 1279.6 |
| affiliation | v001 | succeeded | 200 | 144 | 0 | 436.5 |
| affiliation | v001 | succeeded | 200 | 158 | 0 | 521.8 |
| adjudication | v001 | succeeded | 0 | 2354 | 0 | 2.3 |
| affiliation | v001 | succeeded | 200 | 142 | 0 | 407.5 |
| adjudication | v001 | succeeded | 0 | 7505 | 0 | 4.9 |
| affiliation | v001 | succeeded | 200 | 143 | 0 | 388.6 |
| affiliation | v001 | succeeded | 200 | 147 | 0 | 349.8 |
| affiliation | v001 | succeeded | 200 | 117 | 0 | 379.9 |
| affiliation | v001 | succeeded | 200 | 145 | 0 | 319.4 |
| affiliation | v001 | succeeded | 200 | 138 | 0 | 366.1 |
| affiliation | v001 | succeeded | 200 | 135 | 0 | 380.9 |
| affiliation | v001 | succeeded | 200 | 129 | 0 | 374.6 |
| affiliation | v001 | succeeded | 200 | 137 | 0 | 334.5 |
| affiliation | v001 | succeeded | 200 | 136 | 0 | 334.6 |
| affiliation | v001 | succeeded | 200 | 135 | 0 | 339.9 |
| affiliation | v001 | succeeded | 1 | 1 | 0 | 1.4 |
| affiliation | v001 | succeeded | 1 | 1 | 0 | 2.0 |
| affiliation | v001 | succeeded | 200 | 138 | 0 | 186.4 |
| affiliation | v001 | succeeded | 200 | 136 | 0 | 65.4 |
| affiliation | v001 | succeeded | 200 | 120 | 0 | 245.9 |
| affiliation | v001 | succeeded | 200 | 145 | 0 | 338.7 |
| affiliation | v001 | succeeded | 200 | 149 | 0 | 315.0 |
| affiliation | v001 | succeeded | 200 | 129 | 0 | 310.3 |
| affiliation | v001 | succeeded | 200 | 139 | 0 | 394.7 |
| affiliation | v001 | succeeded | 200 | 136 | 0 | 344.1 |
| affiliation | v001 | succeeded | 200 | 143 | 0 | 384.3 |
| affiliation | v001 | succeeded | 200 | 148 | 0 | 416.3 |
| affiliation | v001 | succeeded | 200 | 140 | 0 | 369.0 |
| affiliation | v001 | succeeded | 200 | 128 | 0 | 390.7 |
| affiliation | v001 | succeeded | 200 | 131 | 0 | 400.0 |
| affiliation | v001 | succeeded | 200 | 138 | 0 | 397.5 |
| affiliation | v001 | succeeded | 200 | 154 | 0 | 409.7 |
| affiliation | v001 | succeeded | 200 | 137 | 0 | 348.1 |
| affiliation | v001 | succeeded | 200 | 136 | 0 | 336.3 |
| affiliation | v001 | succeeded | 200 | 139 | 0 | 289.9 |
| affiliation | v001 | succeeded | 200 | 142 | 0 | 331.1 |
| affiliation | v001 | succeeded | 200 | 125 | 0 | 318.2 |
| affiliation | v001 | succeeded | 200 | 130 | 0 | 339.8 |
| affiliation | v001 | succeeded | 200 | 141 | 0 | 290.0 |
| affiliation | v001 | succeeded | 141 | 83 | 0 | 265.4 |
| adjudication | v001 | succeeded | 0 | 7505 | 0 | 5.0 |
| hf_signals | v001 | running | 0 | 0 | 0 |  |
| hf_signals | v001 | succeeded | 0 | 1 | 0 | 5.9 |
| hf_signals | v001 | succeeded | 0 | 15 | 0 | 10.2 |
| hf_signals | v001 | succeeded | 0 | 292 | 0 | 89.0 |
| hf_validation | v001 | succeeded | 0 | 22585 | 0 | 95.8 |
| ingest | v001 | succeeded | 0 | 1 | 0 | 20.6 |
| ingest | v001 | succeeded | 0 | 0 | 0 | 7.3 |
| relevance | v001 | succeeded | 0 | 251 | 0 | 2.2 |
| screen | v001 | succeeded | 251 | 251 | 0 | 80.4 |
| affiliation_fast | v001 | succeeded | 248 | 113 | 0 | 10.0 |
| domain | v001 | succeeded | 248 | 248 | 0 | 185.2 |
| quality | v001 | succeeded | 47 | 47 | 0 | 44.2 |
| affiliation_deep | v001 | succeeded | 47 | 31 | 0 | 39.8 |
| hf_signals | v001 | succeeded | 0 | 5 | 0 | 0.2 |
| adjudication | v001 | succeeded | 0 | 251 | 0 | 0.2 |
| affiliation_fast | v002 | succeeded | 248 | 116 | 0 | 9.2 |
| affiliation_deep | v002 | succeeded | 47 | 31 | 0 | 29.0 |
| adjudication | v001 | succeeded | 0 | 251 | 0 | 0.2 |
| org_coverage_validation | v001 | succeeded | 0 | 20 | 0 | 11.4 |
| org_coverage_validation | v001 | running | 0 | 0 | 0 |  |
| org_coverage_validation | v001 | running | 0 | 0 | 0 |  |
| org_coverage_validation | v001 | running | 0 | 0 | 0 |  |
| org_coverage_validation | v001 | succeeded | 0 | 22310 | 4 | 4062.0 |
| ingest | v001 | failed | 0 | 0 | 0 | 10.3 |
| relevance | v001 | succeeded | 0 | 0 | 0 | 0.0 |
| ingest | v001 | succeeded | 0 | 48 | 0 | 12.8 |
| relevance | v001 | succeeded | 0 | 0 | 0 | 0.0 |
| ingest | v001 | succeeded | 0 | 69 | 0 | 53.0 |
| relevance | v001 | succeeded | 0 | 0 | 0 | 0.0 |
| screen | v001 | succeeded | 7 | 7 | 0 | 15.3 |
| affiliation_fast | v002 | succeeded | 10 | 3 | 0 | 0.3 |
| domain | v001 | succeeded | 10 | 10 | 0 | 30.6 |
| quality | v001 | succeeded | 10 | 10 | 0 | 21.0 |
| affiliation_deep | v002 | succeeded | 10 | 9 | 0 | 20.7 |
| hf_signals | v001 | succeeded | 0 | 10 | 0 | 1.6 |
| adjudication | v001 | succeeded | 0 | 508 | 0 | 0.6 |
| ingest | v001 | succeeded | 0 | 37 | 0 | 17.8 |
| relevance | v001 | succeeded | 0 | 0 | 0 | 0.0 |
| screen | v001 | succeeded | 9 | 9 | 0 | 63.4 |
| affiliation_fast | v002 | succeeded | 10 | 4 | 0 | 0.3 |
| domain | v001 | succeeded | 10 | 10 | 0 | 94.9 |
| quality | v001 | succeeded | 10 | 10 | 0 | 19.7 |
| affiliation_deep | v002 | succeeded | 10 | 9 | 0 | 11.0 |
| hf_signals | v001 | succeeded | 0 | 10 | 0 | 0.4 |
| adjudication | v001 | succeeded | 0 | 681 | 0 | 0.8 |


## 3. Cost

| Model | Stage | Calls | Input tokens | Output tokens | Cost (USD) |
|---|---|---|---|---|---|
| openai/gpt-5.6-sol | quality | 379 | 800434 | 378606 | $4.7866 |
| z-ai/glm-5.3-flash | screen | 525 | 2637363 | 716448 | $0.7538 |
| z-ai/glm-5.3-flash | classify | 291 | 1680437 | 955053 | $0.7296 |
| z-ai/glm-5.3-flash | audience_domain | 19 | 108371 | 87175 | $0.0598 |

**Total LLM spend:** $6.3298

| External provider | Requests | Cache hits | Failures |
|---|---|---|---|
| arxiv | 15419 | 1782 | 846 |
| ror | 5912 | 2275 | 0 |
| openalex | 5205 | 303 | 1184 |
| openrouter | 1666 | 0 | 452 |
| huggingface | 1053 | 413 | 7 |


## 4. Top 20 papers by final score

Final score = blinded quality composite × evidence factor + organisation boost (capped at 0.5). The quality model never saw authors or affiliations.

| # | Title | Final | Quality | Screen | Org score | Boost | Organisation | Domain |
|---|---|---|---|---|---|---|---|---|
| 1 | Scaling Verification of Cryptographic Software with Aeneas, Rust, and  | 9.1 | 9.3 | 8.0 | 3.0 | 0.096 | École Normale Supérieure - PSL | systems_infrastructure |
| 2 | VC-Attention: Value Smoothing and Softmax Casting for Low-bit Attentio | 8.7 | 8.8 | 7.3 | 6.0 | 0.191 | University of California, Berkeley | model_compression |
| 3 | Misleading the Planner through Deceptive Resumes: Registration-Time In | 8.7 | 8.8 | 7.2 | 3.0 | 0.135 | National University of Singapore | alignment_safety |
| 4 | Illusion of Depth: Revealing Hidden Stereo Vision Vulnerabilities in D | 8.7 | 8.8 | 8.0 | 3.0 | 0.096 | University of Florida | computer_vision |
| 5 | Ave: Guiding Agentic GPU Optimization Using Data-Flow Invariants | 8.6 | 9.3 | 7.7 | 0.0 | 0.000 | — | efficient_inference |
| 6 | Autonomous Mathematical Discovery in an Open-World Multi-Agent Environ | 8.6 | 9.1 | 8.5 | 3.0 | 0.128 | University of Cambridge | natural_language_processing |
| 7 | X-Stage: Modeling Post-Issue Backpressure in GPU Communication--Comput | 8.6 | 8.7 | 6.8 | 6.0 | 0.191 | Tsinghua University | systems_infrastructure |
| 8 | P-POSEMEM: Projective Semantic Memory for Consistent Language Groundin | 8.5 | 8.6 | 7.5 | 3.0 | 0.135 | Fudan University | robotics_embodied |
| 9 | Tele360: Real-Time Feed-Forward Human Reconstruction from Sparse Unpos | 8.4 | 8.7 | 6.8 | 6.0 | 0.191 | Tsinghua University | computer_vision |
| 10 | $\mathbb{SL}(n)$ Representation Learning: An Intrinsic Mixed-Curvature | 8.4 | 8.6 | 7.2 | 6.0 | 0.270 | Stanford University | theory_foundations |
| 11 | Data Attribution of Emergent Misalignment with Persona Features | 8.3 | 8.6 | 7.7 | 3.0 | 0.096 | University of Bonn | interpretability |
| 12 | GM-Loco: Terrain-Adaptive Humanoid Locomotion on Granular Media | 8.3 | 8.6 | 8.0 | 3.0 | 0.096 | Georgia Institute of Technology | robotics_embodied |
| 13 | Vulnerability Localization Benchmark: Measuring Agentic Security Analy | 8.3 | 8.3 | 7.3 | 6.0 | 0.191 | Carnegie Mellon University | evaluation_benchmarking |
| 14 | A light-touch AI literacy intervention helps protect against AI politi | 8.3 | 8.3 | 6.8 | 6.0 | 0.270 | Carnegie Mellon University | alignment_safety |
| 15 | The Misery of Mechanistic Interpretability: A Formal Perspective | 8.2 | 8.6 | 7.3 | 3.0 | 0.135 | Technical University of Munich | interpretability |
| 16 | Divide, Consult, Conquer: Capability Laundering Through Aligned LLMs | 8.2 | 8.6 | 7.7 | 0.0 | 0.000 | — | alignment_safety |
| 17 | When Agents Slow Down: Understanding LLM Agents' Test-Time Strategies  | 8.2 | 8.5 | 7.7 | 0.0 | 0.000 | — | evaluation_benchmarking |
| 18 | Decoy Direction Optimization: A Post-Hoc Defense Against LLM Abliterat | 8.2 | 8.4 | 7.5 | 6.0 | 0.191 | Carnegie Mellon University | alignment_safety |
| 19 | DualView: Preventing Indirect Prompt Injection in Personal AI Agents | 8.1 | 8.7 | 7.0 | 3.0 | 0.096 | Seoul National University | alignment_safety |
| 20 | A Language-Guided Multimodal Foundation Model for Zero-Shot and Multi- | 8.1 | 8.6 | 7.7 | 3.0 | 0.115 | Chinese Institute for Brain Research | multimodal_learning |


### Why these papers

**1. Scaling Verification of Cryptographic Software with Aeneas, Rust, and Lean** (id 194032, final 9.1)  
So what: This work presents a credible route to kernel-checked verification of production-grade, high-performance cryptographic implementations without abandoning Rust, portability, or deployment requirements.  
Not higher because: The methodology still depends on expert-reviewed formalizations, Rust ports, specialized tooling, and a very large Lean development, so its cost and transferability beyond the demonstrated cryptographic codebase remain important constraints.  
Organisation evidence: École Normale Supérieure - PSL via explicit_paper_affiliation (org score 3.0, boost 0.0955)

**2. VC-Attention: Value Smoothing and Softmax Casting for Low-bit Attention** (id 194101, final 8.7)  
So what: It addresses both accuracy and the softmax bottleneck in low-bit video-model attention with hardware-realized techniques that deliver meaningful kernel and end-to-end speedups.  
Not higher because: The approach is specialized to particular low-bit formats and recent GPU architectures, while the reported end-to-end gains are smaller than the kernel gains and broader model or workload generality remains unshown.  
Organisation evidence: University of California, Berkeley via explicit_paper_affiliation (org score 6.0, boost 0.1911)

**3. Misleading the Planner through Deceptive Resumes: Registration-Time Injection in Centralized Multi-Agent Systems** (id 193970, final 8.7)  
So what: Registration-time injection exposes a consequential supply-chain-like weakness in multi-agent systems, while DescGuard offers a deployable way to constrain untrusted agent descriptions before they can corrupt planning.  
Not higher because: The attack and defense are evaluated within centralized planner-worker architectures and GAIA-style tasks; broader validation is needed for decentralized systems, richer tool ecosystems, adaptive attackers, and cases where aggressive description filtering removes legitimate interface semantics.  
Organisation evidence: National University of Singapore via email_domain (org score 3.0, boost 0.135)

**4. Illusion of Depth: Revealing Hidden Stereo Vision Vulnerabilities in Depth Estimation** (id 194708, final 8.7)  
So what: Simple physical patterns can dangerously manipulate stereo depth across classical, learned, fused, and commercial systems, exposing a concrete safety risk for autonomous vehicles and robots while motivating a targeted defense.  
Not higher because: The abstract does not fully characterize attacker deployment constraints, robustness across lighting, distance, viewing angle, weather, or unseen camera pipelines, and the proposed defense still needs broad validation against adaptive attacks and under safety-critical operating conditions.  
Organisation evidence: University of Florida via explicit_paper_affiliation (org score 3.0, boost 0.0955)

**5. Ave: Guiding Agentic GPU Optimization Using Data-Flow Invariants** (id 53419, final 8.6)  
So what: Structured data-flow invariants and compiler-generated counterexamples could enable coding agents to produce GPU kernels approaching expert assembly performance instead of relying on sparse trial-and-error feedback.  
Not higher because: The evaluation is centered on one GPU architecture, the very large speedups need careful baseline and end-to-end validation, and the title names Ave while the abstract names Argus, creating uncertainty about the precise system being evaluated.  
Organisation evidence: — via none (org score 0.0, boost 0.0)

**6. Autonomous Mathematical Discovery in an Open-World Multi-Agent Environment** (id 3120, final 8.6)  
So what: A decentralized AI system that produces verifiable constructions, theorems, and mathematical records could materially expand how researchers explore difficult open problems.  
Not higher because: The exceptional claims span heterogeneous problems, but the abstract does not establish independent expert validation, proof correctness, reproducibility rates, or how reliably the approach improves over strong centralized discovery systems.  
Organisation evidence: University of Cambridge via explicit_paper_affiliation (org score 3.0, boost 0.1275)

**7. X-Stage: Modeling Post-Issue Backpressure in GPU Communication--Computation Fusion** (id 105913, final 8.6)  
So what: Exposing and modeling post-issue GPU communication progress gives kernel designers a concrete way to shape traffic bursts, avoid sender backpressure, and hide distributed-inference communication.  
Not higher because: The contribution is highly valuable but specialized, and its model parameters and scheduling conclusions may depend on particular GPU architectures, interconnect behavior, kernels, and remote-store mechanisms.  
Organisation evidence: Tsinghua University via explicit_paper_affiliation (org score 6.0, boost 0.1911)

**8. P-POSEMEM: Projective Semantic Memory for Consistent Language Grounding under Pose-Graph Rewrites** (id 193844, final 8.5)  
So what: It addresses a subtle but consequential robotics failure mode: language-grounded object identities changing merely because the underlying SLAM graph is rewritten.  
Not higher because: The approach depends on retaining and reconstructing marginalized pose information, which may impose storage or inference costs, and its demonstrated scope is limited to the reported semantic-memory and SLAM settings rather than end-to-end deployment across diverse robot platforms.  
Organisation evidence: Fudan University via email_domain (org score 3.0, boost 0.135)

**9. Tele360: Real-Time Feed-Forward Human Reconstruction from Sparse Unposed Cameras** (id 193641, final 8.4)  
So what: Tele360 could make high-resolution live free-viewpoint telepresence practical by removing camera calibration and per-scene optimization while retaining consumer-GPU real-time performance.  
Not higher because: The abstract omits quantitative reconstruction and rendering-quality results, and validation appears concentrated on studio benchmarks and the authors' multi-camera setup rather than uncontrolled deployment conditions.  
Organisation evidence: Tsinghua University via explicit_paper_affiliation (org score 6.0, boost 0.1911)

**10. $\mathbb{SL}(n)$ Representation Learning: An Intrinsic Mixed-Curvature Space with Higher Curvature Capacities and Deeper Order-Aware Composition** (id 193670, final 8.4)  
So what: It offers a unified representation space that combines multiple curvature regimes with intrinsically deep, order-sensitive composition, potentially avoiding the manual factor design of product manifolds.  
Not higher because: The practical evidence is concentrated on graph and ordered-composition benchmarks, so it remains unclear whether the theoretical curvature advantages translate broadly across modalities, tasks, and computational scales.  
Organisation evidence: Stanford University via email_domain (org score 6.0, boost 0.27)

**11. Data Attribution of Emergent Misalignment with Persona Features** (id 114717, final 8.3)  
So what: It connects emergent misalignment to causally controllable persona features and shows that training format, not merely harmful semantic content, is important in inducing the behavior.  
Not higher because: The findings span four open-weight models but may depend on SAE quality, feature interpretation, corpus coverage, and the specific misalignment protocols; direct deployment-ready detection or prevention methods are not demonstrated.  
Organisation evidence: University of Bonn via explicit_paper_affiliation (org score 3.0, boost 0.0955)

**12. GM-Loco: Terrain-Adaptive Humanoid Locomotion on Granular Media** (id 187177, final 8.3)  
So what: Physics-grounded simulation of granular contact could enable humanoids to traverse sand and similar deformable surfaces that defeat controllers trained with rigid-contact assumptions.  
Not higher because: The abstract does not quantify hardware success rates, traversal speed, robustness, energy cost, or the computational expense of training, and the claimed breadth beyond the tested materials remains uncertain.  
Organisation evidence: Georgia Institute of Technology via explicit_paper_affiliation (org score 3.0, boost 0.0955)

**13. Vulnerability Localization Benchmark: Measuring Agentic Security Analysis at Repository Scale** (id 194157, final 8.3)  
So what: The benchmark isolates a critical missing capability for security agents: finding vulnerability-relevant code across an unfamiliar repository and knowing when not to report a remediated issue.  
Not higher because: It is principally an evaluation and dataset contribution rather than a new localization method, and benchmark labels derived from security fixes may not capture every vulnerability-relevant file or all real-world ambiguity.  
Organisation evidence: Carnegie Mellon University via explicit_paper_affiliation (org score 6.0, boost 0.1911)

**14. A light-touch AI literacy intervention helps protect against AI political persuasion** (id 194758, final 8.3)  
So what: A brief, easily deployed warning appears to cut AI-driven political belief change roughly in half without broadly undermining trust in generative AI.  
Not higher because: The intervention was tested among Americans on a limited set of political topics, so durability, cross-cultural generalization, effectiveness against optimized persuaders, and real-world behavioral effects remain uncertain.  
Organisation evidence: Carnegie Mellon University via email_domain (org score 6.0, boost 0.27)

**15. The Misery of Mechanistic Interpretability: A Formal Perspective** (id 193983, final 8.2)  
So what: Formal certificates could turn fragile mechanistic interpretations into auditable claims, addressing a central obstacle to using interpretability in model-safety decisions.  
Not higher because: The practical scalability, tightness, and semantic usefulness of the certificates for frontier-scale models are not established in the abstract, and guarantees about replacement-network faithfulness may not fully guarantee correctness of the resulting human interpretation.  
Organisation evidence: Technical University of Munich via email_domain (org score 3.0, boost 0.135)

**16. Divide, Consult, Conquer: Capability Laundering Through Aligned LLMs** (id 193808, final 8.2)  
So what: The work shows that interaction-level refusal can fail systemically because harmful capability can be decomposed, obtained through benign-looking consultations, and recomposed by a weaker model.  
Not higher because: The demonstrated recovery rates vary substantially by orchestrator and benchmark, and the abstract does not establish how broadly the attack transfers across decomposition strategies, access controls, or real-world monitored deployments.  
Organisation evidence: — via none (org score 0.0, boost 0.0)

**17. When Agents Slow Down: Understanding LLM Agents' Test-Time Strategies via Elo-per-token Analysis** (id 193772, final 8.2)  
So what: It provides a principled way to measure how effectively agents convert test-time tokens into progress and directly informs when compute should be split across parallel sessions.  
Not higher because: The framework depends on continuously scored open-ended tasks and a particular independent-sampling reference, so its conclusions may not transfer cleanly to tasks with sparse, binary, or highly path-dependent outcomes.  
Organisation evidence: — via none (org score 0.0, boost 0.0)

**18. Decoy Direction Optimization: A Post-Hoc Defense Against LLM Abliteration** (id 194635, final 8.2)  
So what: DDO offers a substantially cheaper way to harden open-weight LLM safety mechanisms against refusal-direction ablation without retraining each checkpoint.  
Not higher because: The defense remains substantially vulnerable under adaptive attacks, with a reported 65% worst-case attack success rate, and its protection is tailored to attacks that depend on estimating or manipulating refusal features.  
Organisation evidence: Carnegie Mellon University via explicit_paper_affiliation (org score 6.0, boost 0.1911)

**19. DualView: Preventing Indirect Prompt Injection in Personal AI Agents** (id 96805, final 8.1)  
So what: Extending untrusted-data provenance into the persistent environment closes a serious security gap for agents that write and later reread files or communicate through external channels.  
Not higher because: The evaluation summary does not quantify utility costs or address deployment complexities such as provenance loss, unsupported tools, view desynchronization, side channels, and adversarial transformations of stored content.  
Organisation evidence: Seoul National University via explicit_paper_affiliation (org score 3.0, boost 0.0955)

**20. A Language-Guided Multimodal Foundation Model for Zero-Shot and Multi-Task Brain Signal Analysis** (id 194077, final 8.1)  
So what: A genuinely zero-shot, language-aligned model for heterogeneous brain signals could substantially reduce task-specific labeling and retraining across neuroscience and clinical workflows.  
Not higher because: The abstract provides limited detail on corpus harmonization, leakage controls, modality and task coverage, subgroup robustness, and prospective clinical validation despite unusually broad performance claims.  
Organisation evidence: Chinese Institute for Brain Research via openalex_paper_specific (org score 3.0, boost 0.1147)


## 5. Organisation leaderboard

Organisation score is derived from verified affiliation evidence (paper affiliation, email domain, ROR, OpenAlex) and applied only after scoring.

| Organisation | On watchlist | Priority | Papers | Avg org score | Best final |
|---|---|---|---|---|---|
| Tsinghua University | yes | 6 | 13 | 6.00 | 8.6 |
| Carnegie Mellon University | yes | 6 | 13 | 6.00 | 8.3 |
| Stanford University | yes | 8 | 12 | 6.00 | 8.4 |
| Massachusetts Institute of Technology | yes | 8 | 9 | 6.00 | 7.9 |
| The Hong Kong University of Science and Technology (Guangzhou) | no | 0 | 8 | 3.00 | 7.8 |
| University of Cambridge | no | 0 | 7 | 3.00 | 8.6 |
| Georgia Institute of Technology | no | 0 | 6 | 3.00 | 8.3 |
| Zhejiang University | no | 0 | 6 | 3.00 | 8.0 |
| National University of Singapore | no | 0 | 5 | 3.00 | 8.7 |
| Korea University of Science and Technology | no | 0 | 5 | 3.00 |  |
| University of California, Berkeley | yes | 8 | 4 | 6.00 | 8.7 |
| Fudan University | no | 0 | 4 | 3.00 | 8.5 |
| ETH Zurich | no | 0 | 4 | 3.00 | 8.0 |
| Columbia University | no | 0 | 4 | 3.00 | 7.9 |
| University of Illinois Urbana-Champaign | no | 0 | 4 | 3.00 | 7.7 |
| Shanghai Jiao Tong University | no | 0 | 4 | 3.00 | 7.6 |
| Delft University of Technology | no | 0 | 4 | 3.00 | 7.5 |
| Nanyang Technological University | no | 0 | 4 | 3.00 | 7.0 |
| Beijing University of Posts and Telecommunications | no | 0 | 4 | 3.00 | 6.5 |
| IEEE Standards Association | yes | 3 | 4 | 10.00 | 3.9 |
| Wuhan University | no | 0 | 4 | 3.00 |  |
| Seoul National University | no | 0 | 3 | 3.00 | 8.1 |
| University of Southern California | no | 0 | 3 | 3.00 | 8.0 |
| Alibaba Group (China) | no | 0 | 3 | 3.00 | 7.9 |
| Peking University | no | 0 | 3 | 3.00 | 7.7 |


## 6. Domain distribution

| Domain | Papers | Avg quality |
|---|---|---|
| natural_language_processing | 117 | 7.87 |
| evaluation_benchmarking | 72 | 7.85 |
| theory_foundations | 62 | 8.02 |
| computer_vision | 58 | 8.18 |
| robotics_embodied | 50 | 8.10 |
| alignment_safety | 48 | 8.23 |
| multimodal_learning | 48 | 8.05 |
| reinforcement_learning | 32 | 7.72 |
| efficient_inference | 30 | 8.44 |
| interpretability | 28 | 8.02 |
| speech_audio | 23 | 8.05 |
| systems_infrastructure | 22 | 7.96 |
| generative_models | 21 | 8.04 |
| model_compression | 14 | 8.03 |
| graph_learning | 12 | 7.30 |


## 7. Data quality

| Check | Count |
|---|---|
| Papers in current state | 681 |
| Affiliation resolved | 389 |
| Affiliation evidence present but ambiguous | 146 |
| No affiliation evidence supplied | 146 |
| Screen/quality disagreement ≥ 3.0 | 0 |


Unresolved affiliations are reported, not hidden: unknown beats wrong, and every raw affiliation string is preserved for re-resolution.
