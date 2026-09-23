# PaperIntelligence v1 — Run Report

**Window:** 2026-08-23 → 2026-08-23 (published_at)  
**Generated:** 2026-09-17 12:34 UTC  
**Pipeline:** relevance (free) → normalize_authors (free) → screen → classify → quality → affiliation → adjudication

## 1. Funnel

| Step | Papers |
|---|---|
| arXiv ingested in window | 401 |
| Rejected by relevance (free, pre-LLM) | 149 |
| Entered paid stages | 252 |
| Passed screen gate | 248 |
| Failed screen gate (scores kept) | 3 |

Relevance runs first precisely so the paid stages never see the rejected papers.

## 2. Stage coverage

| Task type | Papers | Result rows |
|---|---|---|
| screen | 251 | 251 |
| application_domain | 248 | 248 |
| audience | 248 | 248 |
| domain | 248 | 248 |
| subdomain | 248 | 248 |
| quality | 47 | 47 |


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


## 3. Cost

| Model | Stage | Calls | Input tokens | Output tokens | Cost (USD) |
|---|---|---|---|---|---|
| openai/gpt-5.6-sol | quality | 375 | 793042 | 374266 | $4.7340 |
| z-ai/glm-5.3-flash | screen | 523 | 2631438 | 713035 | $0.7512 |
| z-ai/glm-5.3-flash | classify | 291 | 1680437 | 955053 | $0.7296 |
| z-ai/glm-5.3-flash | audience_domain | 17 | 99207 | 81702 | $0.0557 |

**Total LLM spend:** $6.2705

| External provider | Requests | Cache hits | Failures |
|---|---|---|---|
| arxiv | 15388 | 1753 | 845 |
| ror | 5826 | 2231 | 0 |
| openalex | 4900 | 269 | 1168 |
| openrouter | 1658 | 0 | 452 |
| huggingface | 1018 | 384 | 7 |


## 4. Top 20 papers by final score

Final score = blinded quality composite × evidence factor + organisation boost (capped at 0.5). The quality model never saw authors or affiliations.

| # | Title | Final | Quality | Screen | Org score | Boost | Organisation | Domain |
|---|---|---|---|---|---|---|---|---|
| 1 | KeyPooling: Measuring Where LLM API Relay Paths Collapse Prompt Cache  | 8.5 | 8.8 | 7.3 | 3.0 | 0.096 | Johns Hopkins University | efficient_inference |
| 2 | JetStream: Generating Query Accelerators for Existing Database Systems | 8.4 | 8.7 | 7.3 | 3.0 | 0.096 | MIT Computer Science and Artificial Intelligence Laboratory | systems_infrastructure |
| 3 | Decomposition Attacks Across Unlinkable Identities: Limits of Stateful | 8.3 | 8.7 | 7.7 | 0.0 | 0.000 | — | alignment_safety |
| 4 | Measuring in-context algorithmic reasoning in language models against  | 8.3 | 8.6 | 8.0 | 3.0 | 0.096 | University of Oxford | evaluation_benchmarking |
| 5 | The Imitator Game: Benchmarking Robot Imitative Ability Beyond Action  | 8.2 | 8.5 | 7.3 | 0.0 | 0.000 | — | robotics_embodied |
| 6 | A JoLT for the KV cache: Near-lossless KV cache compression via joint  | 8.1 | 8.5 | 7.7 | 0.0 | 0.000 | — | efficient_inference |
| 7 | Which Algorithms Can Graph Neural Networks Learn? | 8.1 | 8.5 | 8.3 | 3.0 | 0.135 | RWTH Aachen University | graph_learning |
| 8 | Training Proactive and Personalized LLM Agents | 8.1 | 8.4 | 7.5 | 6.0 | 0.191 | Carnegie Mellon University | reinforcement_learning |
| 9 | A survey detection channel overrides the pixels in an astronomical fou | 8.0 | 8.4 | 8.0 | 0.0 | 0.000 | — | interpretability |
| 10 | Omni-SafetyBench: A Benchmark for Safety Evaluation of Audio-Visual La | 8.0 | 8.2 | 7.2 | 6.0 | 0.191 | Tsinghua University | alignment_safety |
| 11 | GraniKV: Asymmetric Granularity KV-Cache Paging for Multi-Agent System | 7.9 | 8.3 | 7.2 | 3.0 | 0.096 | Seoul National University | efficient_inference |
| 12 | CONTRAMEM: Learning Self-Evolving Procedural Memory from Contrasting M | 7.9 | 8.3 | 7.2 | 0.0 | 0.000 | — | natural_language_processing |
| 13 | DiD It in 87 Minutes: A Label-Free Softmax-to-Linear Adaptation of Vis | 7.8 | 8.3 | 7.3 | 0.0 | 0.000 | — | computer_vision |
| 14 | Improving Few-Step Language Flows with Untied Self-Conditioning | 7.8 | 8.2 | 7.8 | 3.0 | 0.096 | Korea University of Science and Technology | natural_language_processing |
| 15 | Two Regimes of Chain-of-Thought Unfaithfulness: Metric-Based Detection | 7.8 | 8.0 | 7.7 | 3.0 | 0.135 | University of Southern Mississippi | alignment_safety |
| 16 | CAI-DLLM: Convergence Aware Inference for Diffusion Language Models | 7.8 | 8.0 | 7.2 | 3.0 | 0.096 | Virginia Tech | efficient_inference |
| 17 | Training Large Language Models to Reason in a Continuous Latent Space | 7.7 | 8.3 | 7.7 | 0.0 | 0.000 | — | natural_language_processing |
| 18 | Detecting and Suppressing Reward Hacking with Gradient Fingerprints | 7.7 | 8.2 | 7.5 | 3.0 | 0.096 | New York University | alignment_safety |
| 19 | RASET: Router-Agnostic Safety-Critical Expert Tuning Exposes Localized | 7.7 | 8.2 | 7.3 | 0.0 | 0.000 | — | alignment_safety |
| 20 | Where Cognition Lives: Dissecting Emergent from Computed Function in a | 7.7 | 8.1 | 7.2 | 3.0 | 0.096 | University of Almería | theory_foundations |


### Why these papers

**1. KeyPooling: Measuring Where LLM API Relay Paths Collapse Prompt Cache Isolation** (id 172395, final 8.5)  
So what: It demonstrates that shared relay credentials can collapse prompt-cache isolation across customers and provides a concrete identity-preserving defense contract with modest modeled cost.  
Not higher because: The measurements cover five open-source gateways, two providers, and a bounded production sample; prevalence across proprietary relay implementations and the full practical impact of token recovery remain less certain.  
Organisation evidence: Johns Hopkins University via explicit_paper_affiliation (org score 3.0, boost 0.0955)

**2. JetStream: Generating Query Accelerators for Existing Database Systems** (id 172652, final 8.4)  
So what: JetStream could bring workload-specific, generated acceleration to established DBMSs without sacrificing native storage, transaction handling, or support for changing data.  
Not higher because: The exceptional speedups are demonstrated primarily on TPC-H, and the abstract does not establish robustness across broader transactional workloads, complex update patterns, accelerator-generation costs, or direct production deployment.  
Organisation evidence: MIT Computer Science and Artificial Intelligence Laboratory via explicit_paper_affiliation (org score 3.0, boost 0.0955)

**3. Decomposition Attacks Across Unlinkable Identities: Limits of Stateful Defenses for LLM Services** (id 120560, final 8.3)  
So what: It shows that stateful request monitoring alone cannot reliably stop decomposed harmful tasks when attackers can rotate identities and learn from blocking feedback, clarifying which additional controls are necessary.  
Not higher because: The formal result assumes specified attack and grouping models, while the empirical scope covers a finite task set and policy family; real services may possess side signals, economic controls, or usage constraints outside that model.  
Organisation evidence: — via none (org score 0.0, boost 0.0)

**4. Measuring in-context algorithmic reasoning in language models against an exact Bayes-optimal reference** (id 120504, final 8.3)  
So what: Provides an unusually rigorous, exact Bayesian reference for testing whether language-model predictions resemble principled in-context inference rather than merely achieving high task accuracy.  
Not higher because: The reference is necessarily tied to a bounded program space, machine, and declared prior, while distance from that reference cannot by itself establish what algorithm or inference process a model uses; practical use is also more diagnostic than deployment-oriented.  
Organisation evidence: University of Oxford via explicit_paper_affiliation (org score 3.0, boost 0.0955)

**5. The Imitator Game: Benchmarking Robot Imitative Ability Beyond Action Prediction** (id 120807, final 8.2)  
So what: The benchmark exposes whether robots understand demonstrated intent rather than merely replay trajectories, identifying functional substitution as a concrete barrier to general-purpose imitation.  
Not higher because: This is primarily a benchmark and dataset contribution rather than a demonstrated solution to intent-level imitation, and even the evaluated models remain below 13% zero-shot success on unseen tasks.  
Organisation evidence: — via none (org score 0.0, boost 0.0)

**6. A JoLT for the KV cache: Near-lossless KV cache compression via joint Lagrangian allocation of Tucker ranks and a rotated residual for llms** (id 3611, final 8.1)  
So what: Near-lossless 2–3x KV-cache compression could materially increase long-context inference capacity and throughput without sacrificing model quality.  
Not higher because: The reported validation covers only two model families and selected tasks, and real-world impact still depends on end-to-end kernel efficiency, runtime memory overhead, hardware behavior, and performance at substantially longer contexts.  
Organisation evidence: — via none (org score 0.0, boost 0.0)

**7. Which Algorithms Can Graph Neural Networks Learn?** (id 3568, final 8.1)  
So what: A general account of which algorithms MPNNs can learn and extrapolate could turn neural algorithmic reasoning from an empirical practice into a discipline with actionable guarantees and architectural design principles.  
Not higher because: The practical reach of the guarantees may depend on restrictive assumptions about algorithms, training distributions, optimization, and approximation, while deployment relevance beyond canonical algorithmic tasks remains uncertain.  
Organisation evidence: RWTH Aachen University via email_domain (org score 3.0, boost 0.135)

**8. Training Proactive and Personalized LLM Agents** (id 120294, final 8.1)  
So what: Training agents to ask useful questions and adapt to individual preferences could make them substantially more effective, controllable, and usable as real collaborators.  
Not higher because: The approach depends on LLM-based user simulation and multi-objective reward design, creating open questions about simulator bias, reward trade-offs, deployment cost, and generalization to sustained interactions with diverse real users.  
Organisation evidence: Carnegie Mellon University via explicit_paper_affiliation (org score 6.0, boost 0.1911)

**9. A survey detection channel overrides the pixels in an astronomical foundation model, and biases tomographic mean redshifts** (id 3223, final 8.0)  
So what: It identifies a concrete, removable input-channel failure that can turn astronomical foundation-model predictions into survey-scale redshift biases exceeding operational requirements.  
Not higher because: The strongest causal and downstream results center on one foundation model and survey pipeline, so broader generality across architectures, training regimes, and surveys remains uncertain.  
Organisation evidence: — via none (org score 0.0, boost 0.0)

**10. Omni-SafetyBench: A Benchmark for Safety Evaluation of Audio-Visual Large Language Models** (id 120264, final 8.0)  
So what: Omni-SafetyBench makes cross-modal and audio-visual safety failures measurable, exposing vulnerabilities that text- or single-modality evaluations can miss.  
Not higher because: As a benchmark, it diagnoses rather than resolves the underlying safety problems, and its coverage is ultimately bounded by 972 seed samples and the representativeness of the selected modality transformations, harms, and metrics.  
Organisation evidence: Tsinghua University via explicit_paper_affiliation (org score 6.0, boost 0.1911)

**11. GraniKV: Asymmetric Granularity KV-Cache Paging for Multi-Agent Systems with Long Shared Prefix** (id 1470, final 7.9)  
So what: Asymmetric KV-cache allocation could substantially increase throughput for long-prefix, multi-agent LLM serving while handling heterogeneous prompts better than globally shared-prefix optimizations.  
Not higher because: The contribution targets a specialized serving regime, and the abstract does not establish performance across broader workloads, hardware platforms, latency objectives, or memory-pressure conditions.  
Organisation evidence: Seoul National University via explicit_paper_affiliation (org score 3.0, boost 0.0955)

**12. CONTRAMEM: Learning Self-Evolving Procedural Memory from Contrasting Multi-Model Trajectories** (id 120883, final 7.9)  
So what: Contrasting successful and failed trajectories from diverse models can create transferable procedural memory that more than doubles computer-use agent success without model training.  
Not higher because: The approach depends on collecting and curating multiple trajectories, and the evidence described is still confined to a small set of computer-use benchmarks and agent families rather than sustained real-world operation.  
Organisation evidence: — via none (org score 0.0, boost 0.0)

**13. DiD It in 87 Minutes: A Label-Free Softmax-to-Linear Adaptation of Vision Transformers for Object Detection** (id 3854, final 7.8)  
So what: Detector-interface distillation offers a fast, label-free way to convert existing softmax-attention detectors into substantially cheaper linear-attention models without sacrificing reported accuracy.  
Not higher because: The evidence described is concentrated on DOTA-v1.5, so generality across detector families, natural-image datasets, resolutions, hardware, and linear-attention variants is not yet established in the abstract.  
Organisation evidence: — via none (org score 0.0, boost 0.0)

**14. Improving Few-Step Language Flows with Untied Self-Conditioning** (id 3560, final 7.8)  
So what: A training-free sampler correction substantially improves low-step flow-based language generation, potentially making parallel token refinement much more competitive at low latency.  
Not higher because: The reported gains are compelling but are demonstrated on a limited set of flow-language-model settings, and broader validation is needed across model scales, architectures, generation tasks, and end-to-end latency conditions.  
Organisation evidence: Korea University of Science and Technology via explicit_paper_affiliation (org score 3.0, boost 0.0955)

**15. Two Regimes of Chain-of-Thought Unfaithfulness: Metric-Based Detection Fails Where Models Are Wrong** (id 120492, final 7.8)  
So what: It shows that behavioral chain-of-thought faithfulness detectors fail precisely in the incorrect-answer regime where most annotated unfaithfulness occurs, challenging their usefulness for model oversight.  
Not higher because: The work diagnoses existing signals more strongly than it supplies a deployable replacement, and the generality of the two-regime finding beyond the studied benchmark, models, and elicitation procedures remains uncertain.  
Organisation evidence: University of Southern Mississippi via email_domain (org score 3.0, boost 0.135)

**16. CAI-DLLM: Convergence Aware Inference for Diffusion Language Models** (id 120912, final 7.8)  
So what: A training-free confidence-based schedule could make diffusion language models dramatically faster and more energy-efficient without routinely sacrificing output quality.  
Not higher because: Confidence-guided early commitment and adaptive computation are conceptually incremental, the largest figures are best-case results, and validation is limited to two model families with some harder tasks still losing accuracy.  
Organisation evidence: Virginia Tech via explicit_paper_affiliation (org score 3.0, boost 0.0955)

**17. Training Large Language Models to Reason in a Continuous Latent Space** (id 120218, final 7.7)  
So what: Latent-space reasoning could let language models explore complex solution paths more efficiently without forcing every intermediate state into natural-language tokens.  
Not higher because: The demonstrated scope appears concentrated on search-heavy logical reasoning, while the scalability, interpretability, and robustness of the claimed breadth-first behavior across broader tasks remain unclear.  
Organisation evidence: — via none (org score 0.0, boost 0.0)

**18. Detecting and Suppressing Reward Hacking with Gradient Fingerprints** (id 3496, final 7.7)  
So what: Gradient-level fingerprints offer a way to detect reward hacking that remains hidden behind plausible reasoning traces and can be used during fine-tuning to improve the true objective.  
Not higher because: Gradient extraction may be computationally expensive and requires white-box model access; the abstract also leaves open robustness to adaptive reward hacking, architecture changes, and realistic large-scale RLVR pipelines.  
Organisation evidence: New York University via explicit_paper_affiliation (org score 3.0, boost 0.0955)

**19. RASET: Router-Agnostic Safety-Critical Expert Tuning Exposes Localized Safety Enforcement Failures in Mixture-of-Experts LLMs** (id 120421, final 7.7)  
So what: RASET shows that MoE safety enforcement may be concentrated in a few experts even when routing remains topic-driven, revealing a concrete attack surface and a target for expert-aware defenses.  
Not higher because: The method is primarily an offensive diagnostic with dual-use risk, and the abstract does not establish whether the identified localization persists across closed models, alternative alignment methods, post-training regimes, or realistic attacker access constraints.  
Organisation evidence: — via none (org score 0.0, boost 0.0)

**20. Where Cognition Lives: Dissecting Emergent from Computed Function in a Minimal Complete Cognitive Architecture** (id 120829, final 7.7)  
So what: It provides a mechanism-focused framework for distinguishing genuinely emergent cognitive functions from artifacts of training, instrumentation, and readout design, with implications for compute allocation in reasoning systems.  
Not higher because: The strongest conclusions appear partly grounded in deliberately constructed settings, and it remains unclear how broadly the competence-versus-control decomposition generalizes to diverse architectures and real-world agent tasks.  
Organisation evidence: University of Almería via explicit_paper_affiliation (org score 3.0, boost 0.0955)


## 5. Organisation leaderboard

Organisation score is derived from verified affiliation evidence (paper affiliation, email domain, ROR, OpenAlex) and applied only after scoring.

| Organisation | On watchlist | Priority | Papers | Avg org score | Best final |
|---|---|---|---|---|---|
| Virginia Tech | no | 0 | 3 | 3.00 | 7.8 |
| Peking University | no | 0 | 3 | 3.00 | 7.4 |
| Technical University of Munich | no | 0 | 3 | 3.00 | 7.4 |
| Jilin University | no | 0 | 3 | 3.00 |  |
| Carnegie Mellon University | yes | 6 | 2 | 6.00 | 8.1 |
| Tsinghua University | yes | 6 | 2 | 6.00 | 8.0 |
| Seoul National University | no | 0 | 2 | 3.00 | 7.9 |
| Birla Institute of Technology and Science, Pilani | no | 0 | 2 | 3.00 | 7.6 |
| University of Chinese Academy of Sciences | no | 0 | 2 | 3.00 | 7.4 |
| Texas A&M University | no | 0 | 2 | 3.00 |  |
| Cornell University | no | 0 | 2 | 3.00 |  |
| Wuhan University | no | 0 | 2 | 3.00 |  |
| Northwestern Polytechnical University | no | 0 | 2 | 3.00 |  |
| University of Luxembourg | no | 0 | 2 | 3.00 |  |
| Korea Advanced Institute of Science and Technology | no | 0 | 2 | 3.00 |  |
| Samsung Electronics (South Korea) | no | 0 | 2 | 3.00 |  |
| University of Southern Denmark | no | 0 | 2 | 3.00 |  |
| Harbin Institute of Technology | no | 0 | 2 | 3.00 |  |
| Johns Hopkins University | no | 0 | 1 | 3.00 | 8.5 |
| MIT Computer Science and Artificial Intelligence Laboratory | no | 0 | 1 | 3.00 | 8.4 |
| University of Oxford | no | 0 | 1 | 3.00 | 8.3 |
| RWTH Aachen University | no | 0 | 1 | 3.00 | 8.1 |
| University of Southern Mississippi | no | 0 | 1 | 3.00 | 7.8 |
| Korea University of Science and Technology | no | 0 | 1 | 3.00 | 7.8 |
| University of Almería | no | 0 | 1 | 3.00 | 7.7 |


## 6. Domain distribution

| Domain | Papers | Avg quality |
|---|---|---|
| natural_language_processing | 49 | 7.88 |
| computer_vision | 31 | 7.93 |
| evaluation_benchmarking | 30 | 7.68 |
| robotics_embodied | 21 | 8.50 |
| multimodal_learning | 19 | 7.50 |
| alignment_safety | 17 | 8.14 |
| theory_foundations | 13 | 7.80 |
| efficient_inference | 12 | 8.40 |
| interpretability | 11 | 7.50 |
| generative_models | 11 | 8.20 |
| reinforcement_learning | 9 | 7.95 |
| graph_learning | 8 | 8.50 |
| systems_infrastructure | 7 | 8.40 |
| model_compression | 5 | 7.70 |
| speech_audio | 5 |  |


## 7. Data quality

| Check | Count |
|---|---|
| Papers in current state | 251 |
| Affiliation resolved | 105 |
| Affiliation evidence present but ambiguous | 68 |
| No affiliation evidence supplied | 78 |
| Screen/quality disagreement ≥ 3.0 | 0 |


Unresolved affiliations are reported, not hidden: unknown beats wrong, and every raw affiliation string is preserved for re-resolution.
