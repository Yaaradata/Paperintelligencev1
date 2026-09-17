# PaperIntelligence v1 — Run Report

**Window:** 2026-09-11 → 2026-09-16 (published_at)  
**Generated:** 2026-09-16 06:53 UTC  
**Pipeline:** relevance (free) → normalize_authors (free) → screen → classify → quality → affiliation → adjudication

## 1. Funnel

| Step | Papers |
|---|---|
| arXiv ingested in window | 3757 |
| Rejected by relevance (free, pre-LLM) | 1371 |
| Entered paid stages | 2386 |
| Passed screen gate | 2282 |
| Failed screen gate (scores kept) | 72 |

Relevance runs first precisely so the paid stages never see the rejected papers.

## 2. Stage coverage

| Task type | Papers | Result rows |
|---|---|---|
| screen | 2354 | 2354 |
| application_domain | 2204 | 2204 |
| audience | 2204 | 2204 |
| domain | 2204 | 2204 |
| subdomain | 2204 | 2204 |
| quality | 570 | 570 |


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
| affiliation | v001 | running | 7541 | 0 | 0 |  |
| affiliation | v001 | succeeded | 200 | 135 | 0 | 102.5 |
| quality | v001 | succeeded | 547 | 547 | 0 | 220.5 |
| affiliation | v001 | succeeded | 200 | 165 | 0 | 491.9 |
| affiliation | v001 | succeeded | 570 | 401 | 0 | 1279.6 |
| affiliation | v001 | succeeded | 200 | 144 | 0 | 436.5 |
| affiliation | v001 | running | 200 | 0 | 0 |  |
| adjudication | v001 | succeeded | 0 | 2354 | 0 | 2.3 |


## 3. Cost

| Model | Stage | Calls | Input tokens | Output tokens | Cost (USD) |
|---|---|---|---|---|---|
| openai/gpt-5.6-sol | quality | 365 | 773427 | 364640 | $4.6132 |
| z-ai/glm-5.3-flash | classify | 291 | 1680437 | 955053 | $0.7296 |
| z-ai/glm-5.3-flash | screen | 506 | 2546397 | 671105 | $0.7175 |

**Total LLM spend:** $6.0603

| External provider | Requests | Cache hits | Failures |
|---|---|---|---|
| arxiv | 1987 | 233 | 89 |
| openrouter | 1614 | 0 | 452 |
| ror | 1264 | 405 | 0 |
| openalex | 620 | 97 | 131 |


## 4. Top 20 papers by final score

Final score = blinded quality composite × evidence factor + organisation boost (capped at 0.5). The quality model never saw authors or affiliations.

| # | Title | Final | Quality | Screen | Org score | Boost | Organisation | Domain |
|---|---|---|---|---|---|---|---|---|
| 1 | Scaling Verification of Cryptographic Software with Aeneas, Rust, and  | 9.1 | 9.3 | 8.0 | 3.0 | 0.096 | École Normale Supérieure - PSL | systems_infrastructure |
| 2 | Flattening Every Memory Peak in Long-Context Mixture-of-Experts Traini | 8.9 | 9.3 | 7.5 | 0.0 | 0.000 | — | systems_infrastructure |
| 3 | The Intruder Threshold: A Spectral Law for LoRA Fine-Tuning | 8.9 | 9.0 | 8.3 | 3.0 | 0.113 | Technical University of Munich | theory_foundations |
| 4 | TyPatch: Transforming Patches into Typestate Rules for Kernel Bug Dete | 8.9 | 8.9 | 7.5 | 6.0 | 0.270 | Tsinghua University | natural_language_processing |
| 5 | 4D Parallelism Unlocks Exascale Bayesian Neural Networks for High-Fide | 8.7 | 9.1 | 7.5 | 3.0 | 0.096 | Forschungszentrum Jülich | systems_infrastructure |
| 6 | An ab initio foundation model of wavefunctions that accurately describ | 8.7 | 9.0 | 8.7 | 6.0 | 0.270 | Microsoft | theory_foundations |
| 7 | Alignment Whack-a-Mole : Finetuning Activates Verbatim Recall of Copyr | 8.7 | 8.9 | 8.3 | 3.0 | 0.135 | Columbia University | alignment_safety |
| 8 | Nameless Tokenization: A Lossless Tokenizer-Level Defense Against Cont | 8.7 | 8.9 | 7.7 | 3.0 | 0.096 | Korea University | natural_language_processing |
| 9 | RelateAnything: Real-Time Open-Vocabulary Relation Prediction From Any | 8.7 | 8.9 | 7.8 | 0.0 | 0.000 | — | computer_vision |
| 10 | Illusion of Depth: Revealing Hidden Stereo Vision Vulnerabilities in D | 8.7 | 8.8 | 8.0 | 3.0 | 0.096 | University of Florida | computer_vision |
| 11 | The BatchNorm Illusion: Diagnosing Normalization Artifacts in Machine  | 8.7 | 8.8 | 7.7 | 3.0 | 0.096 | National University of Singapore | evaluation_benchmarking |
| 12 | Misleading the Planner through Deceptive Resumes: Registration-Time In | 8.7 | 8.8 | 7.2 | 3.0 | 0.135 | National University of Singapore | alignment_safety |
| 13 | VC-Attention: Value Smoothing and Softmax Casting for Low-bit Attentio | 8.7 | 8.8 | 7.3 | 6.0 | 0.191 | University of California, Berkeley | model_compression |
| 14 | End-to-End Battery Dispatch with Exact Rainflow Degradation via Mixed- | 8.7 | 8.7 | 7.2 | 10.0 | 0.450 | IEEE Standards Association | theory_foundations |
| 15 | Ave: Guiding Agentic GPU Optimization Using Data-Flow Invariants | 8.6 | 9.3 | 7.7 | 0.0 | 0.000 | — | efficient_inference |
| 16 | Autonomous Mathematical Discovery in an Open-World Multi-Agent Environ | 8.6 | 9.1 | 8.5 | 3.0 | 0.096 | University of Cambridge | natural_language_processing |
| 17 | Dual-guided Hierarchical Edge Localization for Large-scale Optimal Tra | 8.6 | 9.0 | 7.2 | 0.0 | 0.000 | — | theory_foundations |
| 18 | MARCUS: An agentic, multimodal vision-language model for cardiac diagn | 8.6 | 8.9 | 7.7 | 6.0 | 0.191 | Stanford University | multimodal_learning |
| 19 | PipeSwift: Revisiting Pipeline Parallelism for Large-Scale Completion- | 8.6 | 8.8 | 7.5 | 6.0 | 0.191 | Tsinghua University | efficient_inference |
| 20 | Repeat-After-Me: Black-Box Adaptive Visual Prompt Injection | 8.6 | 8.8 | 6.8 | 6.0 | 0.191 | University of California, Berkeley | alignment_safety |


### Why these papers

**1. Scaling Verification of Cryptographic Software with Aeneas, Rust, and Lean** (id 194032, final 9.1)  
So what: This work presents a credible route to kernel-checked verification of production-grade, high-performance cryptographic implementations without abandoning Rust, portability, or deployment requirements.  
Not higher because: The methodology still depends on expert-reviewed formalizations, Rust ports, specialized tooling, and a very large Lean development, so its cost and transferability beyond the demonstrated cryptographic codebase remain important constraints.  
Organisation evidence: École Normale Supérieure - PSL via explicit_paper_affiliation (org score 3.0, boost 0.0955)

**2. Flattening Every Memory Peak in Long-Context Mixture-of-Experts Training** (id 193268, final 8.9)  
So what: Bounding every major memory peak can turn otherwise infeasible long-context, hundred-billion-parameter MoE training runs into executable and efficient workloads without approximate gradients.  
Not higher because: The exceptional scale and throughput claims require substantial specialized infrastructure, and the abstract does not fully expose communication costs, hardware sensitivity, implementation complexity, or independent reproducibility.  
Organisation evidence: — via none (org score 0.0, boost 0.0)

**3. The Intruder Threshold: A Spectral Law for LoRA Fine-Tuning** (id 106054, final 8.9)  
So what: A parameter-free spectral threshold could predict which LoRA updates create harmful new directions and enable safer adapter tuning without validation sweeps.  
Not higher because: Threshold localization is only within a factor of two for 82% of layers, and the reported mitigation and task-preservation result appears concentrated on the most fragile model; broader downstream tasks and training regimes would be needed for a near-universal law.  
Organisation evidence: Technical University of Munich via email_domain (org score 3.0, boost 0.1125)

**4. TyPatch: Transforming Patches into Typestate Rules for Kernel Bug Detection** (id 192435, final 8.9)  
So what: Separating LLM-extracted defect rules from reusable program-analysis machinery turns historical patches into scalable kernel bug detectors with strong precision and major generation-cost savings.  
Not higher because: The results are centered on one large and unusually well-curated codebase, and the abstract does not quantify recall, false-negative behavior, backend soundness, or portability to substantially different systems and languages.  
Organisation evidence: Tsinghua University via email_domain (org score 6.0, boost 0.27)

**5. 4D Parallelism Unlocks Exascale Bayesian Neural Networks for High-Fidelity Atmospheric Modeling** (id 191803, final 8.7)  
So what: BEAST combines scalable Bayesian deep learning with global high-resolution forecasting, making large-ensemble uncertainty quantification and extreme-event prediction feasible at unprecedented computational scale.  
Not higher because: The approach requires extraordinary supercomputing resources, the largest performance run and the fully trained model use different scales, and claims of exceptional extreme-event skill and first-ever status need broader task-specific comparisons and independent confirmation.  
Organisation evidence: Forschungszentrum Jülich via explicit_paper_affiliation (org score 3.0, boost 0.0955)

**6. An ab initio foundation model of wavefunctions that accurately describes chemical bond breaking** (id 191305, final 8.7)  
So what: A transferable neural wavefunction that reliably handles bond breaking could amortize expensive quantum calculations across molecules and make high-accuracy multireference predictions substantially more accessible.  
Not higher because: The practical reach still depends on fine-tuning cost, scaling to larger and more chemically diverse systems, and independent validation of the claimed consistency and cost advantage over established multireference methods.  
Organisation evidence: Microsoft via email_domain (org score 6.0, boost 0.27)

**7. Alignment Whack-a-Mole : Finetuning Activates Verbatim Recall of Copyrighted Books in Large Language Models** (id 42672, final 8.7)  
So what: If ordinary-looking finetuning can reactivate extensive verbatim recall, alignment safeguards may not reliably prevent copyrighted training material from being extracted after model customization.  
Not higher because: The strong conclusion that weights store copies has substantial technical and legal nuance, while the abstract does not fully expose extraction controls, contamination checks, reproducibility constraints, or the representativeness of the tested books and APIs.  
Organisation evidence: Columbia University via email_domain (org score 3.0, boost 0.135)

**8. Nameless Tokenization: A Lossless Tokenizer-Level Defense Against Control-Token Forgery in Open-Weight LLMs** (id 195035, final 8.7)  
So what: Removing surface strings from reserved control tokens offers an unusually clean, lossless way to prevent prompt content from forging privileged turn, tool, or reasoning boundaries.  
Not higher because: The evaluation covers tokenizer behavior and targeted probes, but the abstract does not fully demonstrate deployment compatibility, end-to-end security under adaptive attacks, or effects across broader agent stacks and model families.  
Organisation evidence: Korea University via explicit_paper_affiliation (org score 3.0, boost 0.0955)

**9. RelateAnything: Real-Time Open-Vocabulary Relation Prediction From Any Inputs** (id 191681, final 8.7)  
So what: This work moves relation prediction toward genuinely open-vocabulary, detector-independent deployment while supplying the large corpus and transfer-oriented benchmark needed to evaluate that capability.  
Not higher because: The strongest claims depend on a newly introduced corpus and benchmark, and broader independent validation is needed to establish coverage of rare, ambiguous, compositional, and culturally dependent relations in unconstrained settings.  
Organisation evidence: — via none (org score 0.0, boost 0.0)

**10. Illusion of Depth: Revealing Hidden Stereo Vision Vulnerabilities in Depth Estimation** (id 194708, final 8.7)  
So what: Simple physical patterns can dangerously manipulate stereo depth across classical, learned, fused, and commercial systems, exposing a concrete safety risk for autonomous vehicles and robots while motivating a targeted defense.  
Not higher because: The abstract does not fully characterize attacker deployment constraints, robustness across lighting, distance, viewing angle, weather, or unseen camera pipelines, and the proposed defense still needs broad validation against adaptive attacks and under safety-critical operating conditions.  
Organisation evidence: University of Florida via explicit_paper_affiliation (org score 3.0, boost 0.0955)

**11. The BatchNorm Illusion: Diagnosing Normalization Artifacts in Machine Unlearning Evaluation** (id 191527, final 8.7)  
So what: It exposes a large, easily triggered BatchNorm artifact that can invalidate machine-unlearning conclusions and supplies a principled way to separate measurement effects from information retained in model weights.  
Not higher because: The issue is specific to stateful normalization and selected evaluation metrics, while membership-inference results appear largely unaffected; broader validation across architectures, datasets, and unlearning threat models would strengthen universality.  
Organisation evidence: National University of Singapore via explicit_paper_affiliation (org score 3.0, boost 0.0955)

**12. Misleading the Planner through Deceptive Resumes: Registration-Time Injection in Centralized Multi-Agent Systems** (id 193970, final 8.7)  
So what: Registration-time injection exposes a consequential supply-chain-like weakness in multi-agent systems, while DescGuard offers a deployable way to constrain untrusted agent descriptions before they can corrupt planning.  
Not higher because: The attack and defense are evaluated within centralized planner-worker architectures and GAIA-style tasks; broader validation is needed for decentralized systems, richer tool ecosystems, adaptive attackers, and cases where aggressive description filtering removes legitimate interface semantics.  
Organisation evidence: National University of Singapore via email_domain (org score 3.0, boost 0.135)

**13. VC-Attention: Value Smoothing and Softmax Casting for Low-bit Attention** (id 194101, final 8.7)  
So what: It addresses both accuracy and the softmax bottleneck in low-bit video-model attention with hardware-realized techniques that deliver meaningful kernel and end-to-end speedups.  
Not higher because: The approach is specialized to particular low-bit formats and recent GPU architectures, while the reported end-to-end gains are smaller than the kernel gains and broader model or workload generality remains unshown.  
Organisation evidence: University of California, Berkeley via explicit_paper_affiliation (org score 6.0, boost 0.1911)

**14. End-to-End Battery Dispatch with Exact Rainflow Degradation via Mixed-Integer Differentiable Predictive Control** (id 191869, final 8.7)  
So what: Fast neural dispatch that retains exact rainflow degradation accounting and guaranteed operational feasibility could make economically realistic battery optimization deployable across large fleets.  
Not higher because: The evaluation appears scenario-based rather than a live deployment, and the use of dense proxy gradients leaves questions about training bias, robustness under distribution shift, and generality beyond the tested tariffs and fleet.  
Organisation evidence: IEEE Standards Association via email_domain (org score 10.0, boost 0.45)

**15. Ave: Guiding Agentic GPU Optimization Using Data-Flow Invariants** (id 53419, final 8.6)  
So what: Structured data-flow invariants and compiler-generated counterexamples could enable coding agents to produce GPU kernels approaching expert assembly performance instead of relying on sparse trial-and-error feedback.  
Not higher because: The evaluation is centered on one GPU architecture, the very large speedups need careful baseline and end-to-end validation, and the title names Ave while the abstract names Argus, creating uncertainty about the precise system being evaluated.  
Organisation evidence: — via none (org score 0.0, boost 0.0)

**16. Autonomous Mathematical Discovery in an Open-World Multi-Agent Environment** (id 3120, final 8.6)  
So what: A decentralized AI system that produces verifiable constructions, theorems, and mathematical records could materially expand how researchers explore difficult open problems.  
Not higher because: The exceptional claims span heterogeneous problems, but the abstract does not establish independent expert validation, proof correctness, reproducibility rates, or how reliably the approach improves over strong centralized discovery systems.  
Organisation evidence: University of Cambridge via explicit_paper_affiliation (org score 3.0, boost 0.0955)

**17. Dual-guided Hierarchical Edge Localization for Large-scale Optimal Transport Across Dimensions** (id 191887, final 8.6)  
So what: HELLO could make high-accuracy unregularized optimal transport practical at million-point scale by localizing a sparse set of transport edges while retaining optimality-oriented KKT checks.  
Not higher because: The finite-optimality guarantee relies on exact arithmetic and symbolic tie-breaking, while real GPU execution is finite precision; performance across pathological costs and the full set of claimed downstream OT variants is not detailed.  
Organisation evidence: — via none (org score 0.0, boost 0.0)

**18. MARCUS: An agentic, multimodal vision-language model for cardiac diagnosis and management** (id 40589, final 8.6)  
So what: A unified, interactive system that interprets ECG, echocardiography, and CMR together could improve cardiac diagnostic workflows where clinicians must integrate heterogeneous tests at scale.  
Not higher because: Despite large datasets and external-cohort results, the abstract does not establish prospective clinical utility, workflow safety, calibration, subgroup fairness, or performance under broader multi-institutional distribution shifts.  
Organisation evidence: Stanford University via explicit_paper_affiliation (org score 6.0, boost 0.1911)

**19. PipeSwift: Revisiting Pipeline Parallelism for Large-Scale Completion-Oriented Agentic Serving** (id 194786, final 8.6)  
So what: PipeSwift reframes agent-serving optimization around end-to-end job completion and shows that pipeline parallelism can materially improve the economics and responsiveness of long-running LLM agents.  
Not higher because: The results rely on deterministic trajectory replays, very large MoE models, and 64 H800 GPUs; benefits under live agents, diverse hardware scales, variable tool latency, failures, and rapidly changing serving baselines remain uncertain.  
Organisation evidence: Tsinghua University via explicit_paper_affiliation (org score 6.0, boost 0.1911)

**20. Repeat-After-Me: Black-Box Adaptive Visual Prompt Injection** (id 142692, final 8.6)  
So what: The attack demonstrates that untrusted images can induce consequential tool calls and persistent agent compromise even when textual injection fails, exposing an urgent multimodal security boundary.  
Not higher because: Attack success remains substantially below universal on commercial victims, transferability is partial, and the abstract offers discussion rather than demonstrated effectiveness for the proposed defenses.  
Organisation evidence: University of California, Berkeley via explicit_paper_affiliation (org score 6.0, boost 0.1911)


## 5. Organisation leaderboard

Organisation score is derived from verified affiliation evidence (paper affiliation, email domain, ROR, OpenAlex) and applied only after scoring.

| Organisation | On watchlist | Priority | Papers | Avg org score | Best final |
|---|---|---|---|---|---|
| Tsinghua University | yes | 6 | 27 | 6.00 | 8.9 |
| Carnegie Mellon University | yes | 6 | 15 | 6.00 | 8.4 |
| Zhejiang University | no | 0 | 15 | 3.00 | 8.4 |
| Stanford University | yes | 8 | 14 | 6.00 | 8.6 |
| University of Cambridge | no | 0 | 11 | 3.00 | 8.6 |
| Peking University | no | 0 | 10 | 3.00 | 8.4 |
| Fudan University | no | 0 | 9 | 3.00 | 8.5 |
| Shanghai Jiao Tong University | no | 0 | 8 | 3.00 | 8.1 |
| National University of Singapore | no | 0 | 7 | 3.00 | 8.7 |
| Georgia Institute of Technology | no | 0 | 7 | 3.00 | 8.3 |
| Massachusetts Institute of Technology | yes | 8 | 7 | 6.00 | 7.8 |
| Technical University of Munich | no | 0 | 6 | 3.00 | 8.9 |
| University of Oxford | no | 0 | 6 | 3.00 | 8.6 |
| University of Illinois Urbana-Champaign | no | 0 | 6 | 3.00 | 7.7 |
| Beijing University of Posts and Telecommunications | no | 0 | 6 | 3.00 | 7.6 |
| Beihang University | no | 0 | 6 | 3.00 | 7.6 |
| Korea University of Science and Technology | no | 0 | 5 | 3.00 | 8.2 |
| Seoul National University | no | 0 | 5 | 3.00 | 8.1 |
| ETH Zurich | no | 0 | 5 | 3.00 | 8.1 |
| Nanyang Technological University | no | 0 | 5 | 3.00 | 7.4 |
| University of California, Berkeley | yes | 8 | 4 | 6.00 | 8.7 |
| Columbia University | no | 0 | 4 | 3.00 | 8.7 |
| Cornell University | no | 0 | 4 | 3.00 | 8.3 |
| Macquarie University | no | 0 | 4 | 3.00 | 7.9 |
| Nanjing University | no | 0 | 4 | 3.00 | 7.8 |


## 6. Domain distribution

| Domain | Papers | Avg quality |
|---|---|---|
| natural_language_processing | 402 | 8.04 |
| computer_vision | 265 | 8.16 |
| evaluation_benchmarking | 252 | 7.94 |
| theory_foundations | 206 | 8.05 |
| robotics_embodied | 178 | 8.09 |
| multimodal_learning | 140 | 8.07 |
| alignment_safety | 135 | 8.16 |
| reinforcement_learning | 105 | 7.91 |
| interpretability | 98 | 7.88 |
| efficient_inference | 95 | 8.30 |
| speech_audio | 82 | 8.05 |
| generative_models | 78 | 8.03 |
| systems_infrastructure | 74 | 8.51 |
| graph_learning | 48 | 7.95 |
| model_compression | 46 | 8.11 |


## 7. Data quality

| Check | Count |
|---|---|
| Papers in current state | 2354 |
| Affiliation resolved | 450 |
| Affiliation evidence present but ambiguous | 127 |
| No affiliation evidence supplied | 1777 |
| Screen/quality disagreement ≥ 3.0 | 0 |


Unresolved affiliations are reported, not hidden: unknown beats wrong, and every raw affiliation string is preserved for re-resolution.
