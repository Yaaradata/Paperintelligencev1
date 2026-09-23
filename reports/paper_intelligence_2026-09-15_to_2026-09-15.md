# PaperIntelligence v1 — Run Report

**Window:** 2026-09-15 → 2026-09-15 (published_at)  
**Generated:** 2026-09-21 06:56 UTC  
**Pipeline:** relevance (free) → normalize_authors (free) → screen → classify → quality → affiliation → adjudication

## 1. Funnel

| Step | Papers |
|---|---|
| arXiv ingested in window | 823 |
| Rejected by relevance (free, pre-LLM) | 315 |
| Entered paid stages | 508 |
| Passed screen gate | 496 |
| Failed screen gate (scores kept) | 12 |

Relevance runs first precisely so the paid stages never see the rejected papers.

## 2. Stage coverage

| Task type | Papers | Result rows |
|---|---|---|
| screen | 508 | 508 |
| application_domain | 470 | 478 |
| audience | 470 | 478 |
| domain | 470 | 478 |
| subdomain | 470 | 478 |
| quality | 146 | 146 |


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


## 3. Cost

| Model | Stage | Calls | Input tokens | Output tokens | Cost (USD) |
|---|---|---|---|---|---|
| openai/gpt-5.6-sol | quality | 377 | 796678 | 376483 | $4.7607 |
| z-ai/glm-5.3-flash | screen | 524 | 2634094 | 713734 | $0.7520 |
| z-ai/glm-5.3-flash | classify | 291 | 1680437 | 955053 | $0.7296 |
| z-ai/glm-5.3-flash | audience_domain | 18 | 103742 | 83268 | $0.0572 |

**Total LLM spend:** $6.2995

| External provider | Requests | Cache hits | Failures |
|---|---|---|---|
| arxiv | 15413 | 1776 | 846 |
| ror | 5893 | 2263 | 0 |
| openalex | 5205 | 303 | 1184 |
| openrouter | 1662 | 0 | 452 |
| huggingface | 1035 | 396 | 7 |


## 4. Top 20 papers by final score

Final score = blinded quality composite × evidence factor + organisation boost (capped at 0.5). The quality model never saw authors or affiliations.

| # | Title | Final | Quality | Screen | Org score | Boost | Organisation | Domain |
|---|---|---|---|---|---|---|---|---|
| 1 | Nameless Tokenization: A Lossless Tokenizer-Level Defense Against Cont | 8.7 | 8.9 | 7.7 | 3.0 | 0.096 | Korea University | natural_language_processing |
| 2 | Alignment Whack-a-Mole : Finetuning Activates Verbatim Recall of Copyr | 8.7 | 8.9 | 8.3 | 3.0 | 0.135 | Columbia University | alignment_safety |
| 3 | PipeSwift: Revisiting Pipeline Parallelism for Large-Scale Completion- | 8.6 | 8.8 | 7.5 | 6.0 | 0.191 | Tsinghua University | efficient_inference |
| 4 | Repeat-After-Me: Black-Box Adaptive Visual Prompt Injection | 8.6 | 8.8 | 6.8 | 6.0 | 0.191 | University of California, Berkeley | alignment_safety |
| 5 | Learning Sparse Latent Predictive Foundation Model for Multimodal Neur | 8.6 | 8.7 | 7.3 | 6.0 | 0.191 | Stanford University | computer_vision |
| 6 | A Vision-Language Foundation Model for Precise and Comprehensive Brain | 8.4 | 8.8 | 7.5 | 0.0 | 0.000 | — | multimodal_learning |
| 7 | Stellar Colosseum: A Many-Agent Harness for Long-Horizon Research in M | 8.3 | 8.7 | 7.3 | 6.0 | 0.191 | Carnegie Mellon University | natural_language_processing |
| 8 | Decomposition Buys Integrity, Not Yield | 8.3 | 8.5 | 7.7 | 0.0 | 0.000 | — | natural_language_processing |
| 9 | Same Problem, Different Field: Cross-Domain Solution Import via Domain | 8.3 | 8.4 | 7.2 | 3.0 | 0.135 | KU Leuven | natural_language_processing |
| 10 | Discrete Beckmann Transport Models for One-Step Language Modeling and  | 8.2 | 8.8 | 7.0 | 0.0 | 0.000 | — | generative_models |
| 11 | ADeptS-Bench: Measuring the Trustworthiness of Computer Use Agents Acr | 8.2 | 8.7 | 6.7 | 0.0 | 0.000 | — | evaluation_benchmarking |
| 12 | Verbalizing Subliminal Learning Effects Using Text Optimization | 8.2 | 8.5 | 7.0 | 6.0 | 0.191 | Stanford University | alignment_safety |
| 13 | K-Bench: a clinically calibrated benchmark for evaluating large langua | 8.2 | 8.3 | 7.3 | 3.0 | 0.135 | University of Roehampton | evaluation_benchmarking |
| 14 | FlexiSLM: A Spoken Language Model with Dynamic and Controllable Frame  | 8.1 | 8.5 | 7.0 | 3.0 | 0.096 | Chinese University of Hong Kong | speech_audio |
| 15 | TAME: Token Attribution and Masking for Emergent misalignment | 8.1 | 8.5 | 7.5 | 0.0 | 0.000 | — | interpretability |
| 16 | Composable multi-satellite precipitation estimation for evolving obser | 8.1 | 8.4 | 7.2 | 3.0 | 0.096 | University of Chinese Academy of Sciences | generative_models |
| 17 | Dual Randomized Smoothing: Beyond Global Noise Variance | 8.1 | 8.4 | 7.5 | 3.0 | 0.096 | ETH Zurich | theory_foundations |
| 18 | API Benchmark Scores Do Not Reliably Transfer to Chatbot Interfaces | 8.1 | 8.3 | 7.5 | 6.0 | 0.270 | Stanford University | evaluation_benchmarking |
| 19 | Spheriverse: 3D Scene Understanding from Spherical Observations in the | 8.1 | 8.3 | 7.5 | 3.0 | 0.135 | Hunan University | computer_vision |
| 20 | The Verifier is the Curriculum: Precision Sets the Return on Search in | 8.1 | 8.2 | 7.5 | 3.0 | 0.135 | Institute of Science Tokyo | natural_language_processing |


### Why these papers

**1. Nameless Tokenization: A Lossless Tokenizer-Level Defense Against Control-Token Forgery in Open-Weight LLMs** (id 195035, final 8.7)  
So what: Removing surface strings from reserved control tokens offers an unusually clean, lossless way to prevent prompt content from forging privileged turn, tool, or reasoning boundaries.  
Not higher because: The evaluation covers tokenizer behavior and targeted probes, but the abstract does not fully demonstrate deployment compatibility, end-to-end security under adaptive attacks, or effects across broader agent stacks and model families.  
Organisation evidence: Korea University via explicit_paper_affiliation (org score 3.0, boost 0.0955)

**2. Alignment Whack-a-Mole : Finetuning Activates Verbatim Recall of Copyrighted Books in Large Language Models** (id 42672, final 8.7)  
So what: If ordinary-looking finetuning can reactivate extensive verbatim recall, alignment safeguards may not reliably prevent copyrighted training material from being extracted after model customization.  
Not higher because: The strong conclusion that weights store copies has substantial technical and legal nuance, while the abstract does not fully expose extraction controls, contamination checks, reproducibility constraints, or the representativeness of the tested books and APIs.  
Organisation evidence: Columbia University via email_domain (org score 3.0, boost 0.135)

**3. PipeSwift: Revisiting Pipeline Parallelism for Large-Scale Completion-Oriented Agentic Serving** (id 194786, final 8.6)  
So what: PipeSwift reframes agent-serving optimization around end-to-end job completion and shows that pipeline parallelism can materially improve the economics and responsiveness of long-running LLM agents.  
Not higher because: The results rely on deterministic trajectory replays, very large MoE models, and 64 H800 GPUs; benefits under live agents, diverse hardware scales, variable tool latency, failures, and rapidly changing serving baselines remain uncertain.  
Organisation evidence: Tsinghua University via explicit_paper_affiliation (org score 6.0, boost 0.1911)

**4. Repeat-After-Me: Black-Box Adaptive Visual Prompt Injection** (id 142692, final 8.6)  
So what: The attack demonstrates that untrusted images can induce consequential tool calls and persistent agent compromise even when textual injection fails, exposing an urgent multimodal security boundary.  
Not higher because: Attack success remains substantially below universal on commercial victims, transferability is partial, and the abstract offers discussion rather than demonstrated effectiveness for the proposed defenses.  
Organisation evidence: University of California, Berkeley via explicit_paper_affiliation (org score 6.0, boost 0.1911)

**5. Learning Sparse Latent Predictive Foundation Model for Multimodal Neuroimaging** (id 102642, final 8.6)  
So what: Provides a scalable multimodal MRI representation-learning framework with unusually broad clinical and cross-domain evaluation, potentially improving reusable models for neuroimaging applications.  
Not higher because: The abstract does not quantify effect sizes, computational requirements, subgroup robustness, or prospective clinical utility, and the core ingredients build on established latent-prediction and mixture-of-experts methods.  
Organisation evidence: Stanford University via explicit_paper_affiliation (org score 6.0, boost 0.1911)

**6. A Vision-Language Foundation Model for Precise and Comprehensive Brain Tumor Diagnosis from Preoperative Multimodal Data** (id 194836, final 8.4)  
So what: A comprehensive multimodal system spanning tumor classification, uncertainty estimation, report generation, and molecular subgroup prediction could materially improve presurgical decision-making and clinician consistency.  
Not higher because: The abstract does not report diagnostic accuracy, calibration, subgroup performance, reader-study effect sizes, failure modes, or prospective clinical outcomes, so the magnitude and safety of the claimed benefit cannot be fully assessed.  
Organisation evidence: — via none (org score 0.0, boost 0.0)

**7. Stellar Colosseum: A Many-Agent Harness for Long-Horizon Research in Mathematics and Theoretical Computer Science** (id 195234, final 8.3)  
So what: A structured many-agent workflow could make language models materially more capable and reliable on research tasks requiring long chains of strategic, interdependent decisions.  
Not higher because: The unusually strong benchmark and open-problem claims need fuller validation, expert review, ablations, and accounting of inference cost; it is also unclear how much improvement comes from the harness rather than the underlying frontier models and execution feedback.  
Organisation evidence: Carnegie Mellon University via explicit_paper_affiliation (org score 6.0, boost 0.1911)

**8. Decomposition Buys Integrity, Not Yield** (id 195340, final 8.3)  
So what: The paper offers a measurable decision framework for when multi-agent decomposition is worthwhile, showing that depth can protect context integrity and reduce cost while systematically losing discovered information.  
Not higher because: The retention model is deliberately simple, and the strongest empirical conclusions appear tied to one production environment; observational traces may not establish causality or transfer to other agent designs, models, task types, and communication protocols.  
Organisation evidence: — via none (org score 0.0, boost 0.0)

**9. Same Problem, Different Field: Cross-Domain Solution Import via Domain-Stripped Computational Fingerprints** (id 185634, final 8.3)  
So what: A domain-stripped description of computational mechanisms could help researchers discover mature solutions hidden behind another field's terminology, reducing duplicated work and enabling concrete method transfer.  
Not higher because: The benchmark is relatively small and family-curated, while performance on the wild corpus still requires subjective adjudication; broader disciplinary coverage and prospective evidence of routinely successful imports would strengthen the claim.  
Organisation evidence: KU Leuven via email_domain (org score 3.0, boost 0.135)

**10. Discrete Beckmann Transport Models for One-Step Language Modeling and Reasoning** (id 195232, final 8.2)  
So what: A teacher-free transport objective capable of high-quality one- or few-step generation could materially reduce the latency and training complexity of non-autoregressive language models.  
Not higher because: The abstract gives few quantitative results or details about model scale, compute, sequence length, and comparison conditions, making the claimed practical advantage and scalability difficult to assess fully.  
Organisation evidence: — via none (org score 0.0, boost 0.0)

**11. ADeptS-Bench: Measuring the Trustworthiness of Computer Use Agents Across Devices** (id 122800, final 8.2)  
So what: Provides a directly actionable benchmark for whether computer-use agents resist interface attacks and request clarification before taking consequential actions.  
Not higher because: Coverage is limited to seven models and the benchmark's constructed tasks may not capture the full diversity of real interfaces, long-horizon attacks, user intent, and deployment-specific safeguards.  
Organisation evidence: — via none (org score 0.0, boost 0.0)

**12. Verbalizing Subliminal Learning Effects Using Text Optimization** (id 195015, final 8.2)  
So what: SALVE makes otherwise hidden trait transmission in model-generated data legible, offering both a conceptual account of subliminal learning and a potential data-poisoning diagnostic.  
Not higher because: The abstract does not establish detection reliability across a wide range of model families, adversarially concealed traits, or operational false-positive and false-negative conditions.  
Organisation evidence: Stanford University via explicit_paper_affiliation (org score 6.0, boost 0.1911)

**13. K-Bench: a clinically calibrated benchmark for evaluating large language models in high-risk mental health conversations** (id 194529, final 8.2)  
So what: Offers a clinically calibrated and contamination-resistant way to compare LLM safety across evolving high-risk mental-health conversations, with direct relevance to deployment decisions.  
Not higher because: The evaluation still relies on a fixed cohort dominated by synthetic vignettes and an automated judge calibrated on a subset of transcripts; protected test materials also limit independent inspection and reproducibility.  
Organisation evidence: University of Roehampton via email_domain (org score 3.0, boost 0.135)

**14. FlexiSLM: A Spoken Language Model with Dynamic and Controllable Frame Rates** (id 170846, final 8.1)  
So what: Dynamic, controllable speech frame rates give spoken-language systems a useful runtime quality-versus-latency trade-off while substantially reducing token and inference costs.  
Not higher because: The contribution depends on a pretrained dynamic-rate codec, and the abstract leaves open how well gains generalize across languages, voices, acoustic conditions, longer interactions, and deployment hardware.  
Organisation evidence: Chinese University of Hong Kong via explicit_paper_affiliation (org score 3.0, boost 0.0955)

**15. TAME: Token Attribution and Masking for Emergent misalignment** (id 194919, final 8.1)  
So what: TAME identifies and causally suppresses the token-level training signals that trigger broad misalignment, offering both a diagnostic tool and a targeted mitigation.  
Not higher because: Validation appears focused on released emergent-misalignment setups, two model families, and one medical-advice split; broader fine-tuning regimes and possible utility or capability trade-offs remain unestablished.  
Organisation evidence: — via none (org score 0.0, boost 0.0)

**16. Composable multi-satellite precipitation estimation for evolving observing systems** (id 65647, final 8.1)  
So what: A modular precipitation model that can add satellite sensors without retraining its generative backbone could keep operational monitoring accurate as observing systems evolve.  
Not higher because: The demonstrated sensor and geographic scope is still limited, the 37-second inference figure lacks deployment context, and plug-and-play performance for genuinely new sensor types is not directly reported.  
Organisation evidence: University of Chinese Academy of Sciences via explicit_paper_affiliation (org score 3.0, boost 0.0955)

**17. Dual Randomized Smoothing: Beyond Global Noise Variance** (id 33848, final 8.1)  
So what: Dual randomized smoothing addresses the inherent compromise of a single global noise variance, substantially improving certified accuracy across multiple perturbation radii while retaining formal guarantees.  
Not higher because: The method adds inference cost and system complexity, and the reported validation is limited to standard image benchmarks; its advantages under larger-scale deployment, varied threat models, and adaptive implementation choices remain unclear.  
Organisation evidence: ETH Zurich via explicit_paper_affiliation (org score 3.0, boost 0.0955)

**18. API Benchmark Scores Do Not Reliably Transfer to Chatbot Interfaces** (id 186176, final 8.1)  
So what: If API evaluations do not predict chatbot behavior, widely used model comparisons may mislead purchasers, researchers, auditors, and policymakers about deployed-system performance.  
Not higher because: The measured average gaps are meaningful but moderate, and the abstract does not fully clarify temporal stability, interface configuration coverage, causal mechanisms, or generalization beyond the audited providers and benchmarks.  
Organisation evidence: Stanford University via email_domain (org score 6.0, boost 0.27)

**19. Spheriverse: 3D Scene Understanding from Spherical Observations in the Wild** (id 186238, final 8.1)  
So what: Provides a substantial spherical image–LiDAR resource, rigorous multi-task benchmarks, and geometry-aware modeling that can advance panoramic 3D perception for robotics and autonomous systems.  
Not higher because: The reported occupancy gains are meaningful but moderate, and the abstract does not establish how well the proposed method transfers beyond this new dataset or compares in computational efficiency.  
Organisation evidence: Hunan University via email_domain (org score 3.0, boost 0.135)

**20. The Verifier is the Curriculum: Precision Sets the Return on Search in Code Self-Distillation** (id 99376, final 8.1)  
So what: The work shows that a precise, deterministic verifier can act as the effective curriculum for self-distillation, producing large functional gains where permissive or proxy-based judging fails.  
Not higher because: The evidence is unusually well controlled but comes from one engine-based code-generation setting with a small reported family-level evaluation, so it remains unclear how strongly the conclusion extends to less deterministic software tasks or verifiers with incomplete coverage.  
Organisation evidence: Institute of Science Tokyo via email_domain (org score 3.0, boost 0.135)


## 5. Organisation leaderboard

Organisation score is derived from verified affiliation evidence (paper affiliation, email domain, ROR, OpenAlex) and applied only after scoring.

| Organisation | On watchlist | Priority | Papers | Avg org score | Best final |
|---|---|---|---|---|---|
| Tsinghua University | yes | 6 | 11 | 6.00 | 8.6 |
| Zhejiang University | no | 0 | 9 | 3.00 | 8.0 |
| Stanford University | yes | 8 | 7 | 6.00 | 8.6 |
| ETH Zurich | no | 0 | 7 | 3.00 | 8.1 |
| Carnegie Mellon University | yes | 6 | 6 | 6.00 | 8.3 |
| Beijing University of Posts and Telecommunications | no | 0 | 6 | 3.00 | 7.6 |
| Korea University of Science and Technology | no | 0 | 5 | 3.00 | 7.6 |
| Peking University | no | 0 | 4 | 3.00 | 8.0 |
| Wuhan University | no | 0 | 4 | 3.00 | 7.7 |
| Nanyang Technological University | no | 0 | 4 | 3.00 | 7.4 |
| Shanghai Jiao Tong University | no | 0 | 4 | 3.00 | 7.3 |
| Monash University | no | 0 | 4 | 3.00 | 7.2 |
| Korea University | no | 0 | 3 | 3.00 | 8.7 |
| Technical University of Munich | no | 0 | 3 | 3.00 | 7.8 |
| University of Bonn | no | 0 | 3 | 3.00 | 7.8 |
| University of Edinburgh | no | 0 | 3 | 3.00 | 7.7 |
| Fudan University | no | 0 | 3 | 3.00 | 7.7 |
| Beihang University | no | 0 | 3 | 3.00 | 7.6 |
| Duke University | no | 0 | 3 | 3.00 | 7.4 |
| Ocean University of China | no | 0 | 3 | 3.00 |  |
| Harbin Institute of Technology | no | 0 | 3 | 3.00 |  |
| Ludwig-Maximilians-Universität München | no | 0 | 3 | 3.00 |  |
| KU Leuven | no | 0 | 2 | 3.00 | 8.3 |
| Institute of Science Tokyo | no | 0 | 2 | 3.00 | 8.1 |
| University of Chinese Academy of Sciences | no | 0 | 2 | 3.00 | 8.1 |


## 6. Domain distribution

| Domain | Papers | Avg quality |
|---|---|---|
| natural_language_processing | 81 | 8.08 |
| computer_vision | 66 | 8.04 |
| evaluation_benchmarking | 52 | 7.84 |
| theory_foundations | 43 | 8.08 |
| robotics_embodied | 40 | 8.01 |
| multimodal_learning | 34 | 7.98 |
| alignment_safety | 28 | 8.05 |
| efficient_inference | 25 | 8.19 |
| reinforcement_learning | 24 | 8.00 |
| speech_audio | 20 | 8.24 |
| interpretability | 17 | 7.91 |
| generative_models | 15 | 8.11 |
| systems_infrastructure | 9 | 8.45 |
| model_compression | 8 | 7.90 |
| graph_learning | 8 |  |


## 7. Data quality

| Check | Count |
|---|---|
| Papers in current state | 508 |
| Affiliation resolved | 304 |
| Affiliation evidence present but ambiguous | 96 |
| No affiliation evidence supplied | 108 |
| Screen/quality disagreement ≥ 3.0 | 0 |


Unresolved affiliations are reported, not hidden: unknown beats wrong, and every raw affiliation string is preserved for re-resolution.
