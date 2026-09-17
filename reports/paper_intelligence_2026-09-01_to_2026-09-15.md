# PaperIntelligence v1 — Run Report

**Window:** 2026-09-01 → 2026-09-15 (published_at)  
**Generated:** 2026-09-15 16:13 UTC  
**Pipeline:** relevance (free) → normalize_authors (free) → screen → classify → quality → affiliation → adjudication

## 1. Funnel

| Step | Papers |
|---|---|
| arXiv ingested in window | 8200 |
| Rejected by relevance (free, pre-LLM) | 2975 |
| Entered paid stages | 5225 |
| Passed screen gate | 5092 |
| Failed screen gate (scores kept) | 133 |

Relevance runs first precisely so the paid stages never see the rejected papers.

## 2. Stage coverage

| Task type | Papers | Result rows |
|---|---|---|
| screen | 5225 | 5225 |
| application_domain | 2073 | 2073 |
| audience | 2073 | 2073 |
| domain | 2073 | 2073 |
| subdomain | 2073 | 2073 |
| quality | 1273 | 1273 |


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


## 3. Cost

| Model | Stage | Calls | Input tokens | Output tokens | Cost (USD) |
|---|---|---|---|---|---|
| openai/gpt-5.6-sol | quality | 255 | 541194 | 255432 | $3.2308 |
| z-ai/glm-5.3-flash | screen | 351 | 1769743 | 449487 | $0.4902 |
| z-ai/glm-5.3-flash | classify | 140 | 810602 | 336932 | $0.2901 |

**Total LLM spend:** $4.0111

| External provider | Requests | Cache hits | Failures |
|---|---|---|---|
| openrouter | 1198 | 0 | 452 |
| ror | 232 | 81 | 0 |
| openalex | 88 | 24 | 29 |
| arxiv | 39 | 3 | 4 |


## 4. Top 20 papers by final score

Final score = blinded quality composite × evidence factor + organisation boost (capped at 0.5). The quality model never saw authors or affiliations.

| # | Title | Final | Quality | Screen | Org score | Boost | Organisation | Domain |
|---|---|---|---|---|---|---|---|---|
| 1 | Learning transferable human physiology from two million hours of sleep | 9.1 | 9.1 | 7.7 | 3.0 | 0.096 | Stanford University | multimodal_learning |
| 2 | Evidence Integration in Large Language Models | 9.0 | 9.1 | 8.3 | 3.0 | 0.135 | Massachusetts Institute of Technology | interpretability |
| 3 | Water-network decisions share one hydraulic gradient, and it can now b | 8.9 | 9.2 | 7.3 | 0.0 | 0.000 | — | theory_foundations |
| 4 | Extending concurrent separation logic to the hardware level to verify  | 8.8 | 9.1 | 7.0 | 3.0 | 0.096 | MIT Computer Science and Artificial Intelligence Laboratory | theory_foundations |
| 5 | MOLE: Detecting Insider Threats in AI Agents | 8.8 | 8.9 | 7.8 | 3.0 | 0.096 | Carnegie Mellon University | evaluation_benchmarking |
| 6 | Atlas: Efficient Verifiable Semantic Search | 8.7 | 9.0 | 8.2 | 3.0 | 0.096 | Belfort Labs (Belgium) | systems_infrastructure |
| 7 | The Oversight Gap: What LLM Safety Monitors Miss, and Why It Is Not Ca | 8.7 | 8.9 | 7.5 | 3.0 | 0.113 | Carnegie Mellon University | alignment_safety |
| 8 | MINERVA: How Small Can a Manipulation Policy Be and Still Solve LIBERO | 8.7 | 8.9 | 8.2 | 3.0 | 0.096 | École Supérieure d'Ingénieurs en Génie Électrique | robotics_embodied |
| 9 | Hyperparameter Scaling Laws Across MoE Sparsity | 8.7 | 8.8 | 8.0 | 0.0 | 0.000 | — | theory_foundations |
| 10 | Gauge dependence and structured-output corruption in sign-branched rep | 8.6 | 9.0 | 7.7 | 0.0 | 0.000 | — | efficient_inference |
| 11 | Alignment Whack-a-Mole : Finetuning Activates Verbatim Recall of Copyr | 8.6 | 8.9 | 8.3 | 3.0 | 0.096 | Carnegie Mellon University | alignment_safety |
| 12 | The Geometry of Refusal: Why Post-Hoc Safety Is Fragile and Pretrainin | 8.6 | 8.9 | 8.3 | 0.0 | 0.000 | — | alignment_safety |
| 13 | VLA-Precision: Asymmetric Co-Bootstrapping for Efficient Real-World On | 8.6 | 8.8 | 7.3 | 0.0 | 0.000 | — | robotics_embodied |
| 14 | TGR: Advancing Industrial Recommendation from Generative-Paradigm Rank | 8.6 | 8.8 | 7.3 | 0.0 | 0.000 | — | generative_models |
| 15 | Signing the Transaction but Not the Decision: Whisper Attacks and a Bi | 8.6 | 8.8 | 7.0 | 0.0 | 0.000 | — | alignment_safety |
| 16 | Advancing Subseasonal Forecasting with Machine Learning | 8.6 | 8.7 | 7.7 | 3.0 | 0.096 | Massachusetts Institute of Technology | generative_models |
| 17 | Audit Without Verification: When LLM Accountability Layers Relay Rathe | 8.6 | 8.7 | 7.8 | 0.0 | 0.000 | — | evaluation_benchmarking |
| 18 | ALIGN-HOLD: Experience Alignment for Real-Time Hold Control in Large-S | 8.6 | 8.7 | 7.3 | 3.0 | 0.096 | Shanghai Jiao Tong University | reinforcement_learning |
| 19 | Clean Engineering, Unstable Measurement: A Preregistered Reliability F | 8.6 | 8.7 | 8.2 | 0.0 | 0.000 | — | evaluation_benchmarking |
| 20 | Autonomous discovery of new structure-plausibility laws for explainabl | 8.5 | 8.9 | 7.8 | 0.0 | 0.000 | — | natural_language_processing |


### Why these papers

**1. Learning transferable human physiology from two million hours of sleep with SleepFM-2** (id 184835, final 9.1)  
So what: A broadly transferable representation learned from sleep physiology could support scalable disease screening, sleep assessment, and cross-sensor health modeling from clinical and wearable data.  
Not higher because: Despite exceptional scale and breadth, the abstract does not establish prospective clinical utility, causal validity, calibration across populations, or whether gains justify the operational cost of deploying such a model.  
Organisation evidence: Stanford University via explicit_paper_affiliation (org score 3.0, boost 0.0955)

**2. Evidence Integration in Large Language Models** (id 142581, final 9.0)  
So what: It provides a predictive and mechanistic account of why LLMs accept external answers—even ones they can verify are wrong—with major implications for retrieval, tool use, multi-agent systems, and scientific reasoning.  
Not higher because: The proposed distributional law and mechanistic dissociation are broad but may not fully capture interactive, long-context, or source-aware evidence use in deployed systems, and practical countermeasures are not yet established.  
Organisation evidence: Massachusetts Institute of Technology via email_domain (org score 3.0, boost 0.135)

**3. Water-network decisions share one hydraulic gradient, and it can now be computed exactly** (id 184607, final 8.9)  
So what: Exact, scalable gradients for established water-network simulators could replace costly derivative-free workflows and materially improve calibration, leak localisation, and sensor planning.  
Not higher because: The claims are exceptionally strong, but broader deployment evidence is still needed for difficult operational regimes, topology or control changes, and nondifferentiable status boundaries; reproducibility and integration details are not stated in the abstract.  
Organisation evidence: — via none (org score 0.0, boost 0.0)

**4. Extending concurrent separation logic to the hardware level to verify the xv6 OS kernel on RISC-V with AI agents** (id 138345, final 8.8)  
So what: Connecting concurrent separation logic to detailed RISC-V execution and using it to verify a concurrent OS kernel could substantially narrow the assurance gap between software proofs and real hardware behavior.  
Not higher because: The case study is limited to the relatively small xv6 kernel, while the abstract does not quantify proof coverage, trusted-computing-base assumptions, automation rates, or how much the AI agents contributed beyond human-guided verification.  
Organisation evidence: MIT Computer Science and Artificial Intelligence Laboratory via explicit_paper_affiliation (org score 3.0, boost 0.0955)

**5. MOLE: Detecting Insider Threats in AI Agents** (id 184890, final 8.8)  
So what: MOLE provides a large, realistic testbed for determining whether limited-budget monitoring can detect harmful AI-agent activity hidden within routine account operations.  
Not higher because: The benchmark covers a bounded set of simulated services, threats, models, and audit conditions, so its results may not fully transfer to evolving agents or real frontier-lab infrastructure.  
Organisation evidence: Carnegie Mellon University via explicit_paper_affiliation (org score 3.0, boost 0.0955)

**6. Atlas: Efficient Verifiable Semantic Search** (id 188266, final 8.7)  
So what: Atlas makes high-recall HNSW semantic search cryptographically verifiable at realistic scale, reducing the need to trust retrieval providers without exposing their indexes.  
Not higher because: The abstract does not expose proof sizes, verifier and preprocessing costs, update handling, hardware assumptions, or operational trade-offs for dynamic production indexes, all of which affect real-world deployment.  
Organisation evidence: Belfort Labs (Belgium) via explicit_paper_affiliation (org score 3.0, boost 0.0955)

**7. The Oversight Gap: What LLM Safety Monitors Miss, and Why It Is Not Capability** (id 184994, final 8.7)  
So what: It reframes important monitoring failures as information-and-procedure limits, providing formal detectability bounds and concrete guidance for building valid safety oversight and benchmarks.  
Not higher because: The strongest conclusions appear grounded in controlled leak families and designed factorial experiments; applicability of the quantitative frontiers to messy, adaptive production threats remains to be demonstrated.  
Organisation evidence: Carnegie Mellon University via email_domain (org score 3.0, boost 0.1125)

**8. MINERVA: How Small Can a Manipulation Policy Be and Still Solve LIBERO?** (id 138187, final 8.7)  
So what: It shows that standard LIBERO tasks can be solved by sub-million-parameter, CPU-deployable policies while exposing memorization and robustness limitations hidden by headline benchmark scores.  
Not higher because: The capacity-floor conclusion is benchmark-specific, and the severe LIBERO-Plus degradation leaves open whether the compact policy design transfers to diverse real-world manipulation.  
Organisation evidence: École Supérieure d'Ingénieurs en Génie Électrique via explicit_paper_affiliation (org score 3.0, boost 0.0955)

**9. Hyperparameter Scaling Laws Across MoE Sparsity** (id 186119, final 8.7)  
So what: Unified scaling laws for learning rate and batch size across MoE sparsity could substantially reduce costly hyperparameter searches when training increasingly sparse models.  
Not higher because: The laws remain empirical and may depend on the studied architecture, optimizer, routing design, data regime, and scale range; validation beyond 12B parameters and across substantially different training stacks is not reported here.  
Organisation evidence: — via none (org score 0.0, boost 0.0)

**10. Gauge dependence and structured-output corruption in sign-branched repetition penalties: measurements across models, inference stacks, and alternative repetition controls** (id 100541, final 8.6)  
So what: A widely deployed repetition penalty depends on an arbitrary logit offset and can severely damage structured output, while a readily implementable normalized alternative removes the identified pathology.  
Not higher because: The empirical study covers a limited number of models, primarily up to 7B, and further evaluation is needed across larger production models, decoding strategies, languages, and open-ended repetition-quality tradeoffs before changing defaults universally.  
Organisation evidence: — via none (org score 0.0, boost 0.0)

**11. Alignment Whack-a-Mole : Finetuning Activates Verbatim Recall of Copyrighted Books in Large Language Models** (id 42672, final 8.6)  
So what: If ordinary-looking finetuning can reactivate extensive verbatim recall, alignment safeguards may not reliably prevent copyrighted training material from being extracted after model customization.  
Not higher because: The strong conclusion that weights store copies has substantial technical and legal nuance, while the abstract does not fully expose extraction controls, contamination checks, reproducibility constraints, or the representativeness of the tested books and APIs.  
Organisation evidence: Carnegie Mellon University via explicit_paper_affiliation (org score 3.0, boost 0.0955)

**12. The Geometry of Refusal: Why Post-Hoc Safety Is Fragile and Pretraining-Time Safety Persists** (id 184872, final 8.6)  
So what: The work offers a mechanistic explanation for fragile refusal tuning and evidence that distributing safety learning throughout pretraining can produce markedly more persistent safeguards.  
Not higher because: The geometric account may not capture all alignment mechanisms, while robustness is demonstrated against a bounded set of fine-tuning attacks and refusal measures; safety co-training from scratch is also less accessible than post-hoc alignment.  
Organisation evidence: — via none (org score 0.0, boost 0.0)

**13. VLA-Precision: Asymmetric Co-Bootstrapping for Efficient Real-World Online RL of Vision-Language-Action Models** (id 142601, final 8.6)  
So what: It offers a high-throughput route for large vision-language-action models to improve autonomously on precision manipulation tasks without unstable value learning or prohibitive real-world training time.  
Not higher because: Despite strong claimed results, the contribution is demonstrated within high-precision chemistry manipulation; broader task transfer, long-horizon robustness, safety, and dependence on intervention quality remain unresolved.  
Organisation evidence: — via none (org score 0.0, boost 0.0)

**14. TGR: Advancing Industrial Recommendation from Generative-Paradigm Ranking toward Unified Generation and Reasoning** (id 135993, final 8.6)  
So what: The work demonstrates that generative ranking, slate generation, and offline-assisted reasoning can produce material business and engagement gains at recommender-system scale.  
Not higher because: TGR bundles several distinct architectures and deployment initiatives, making the unified scientific contribution and attribution of gains less clear; external reproducibility and transferability beyond the reported production environment are also uncertain.  
Organisation evidence: — via none (org score 0.0, boost 0.0)

**15. Signing the Transaction but Not the Decision: Whisper Attacks and a Binding Defense for AP2** (id 188233, final 8.6)  
So what: It shows that cryptographically valid agent payments can still violate user intent and supplies protocol-level bindings, formal invariants, and a substantial benchmark for mitigating that gap.  
Not higher because: A-VIP cannot automatically prevent attacks that leave no structural trace and instead requires user confirmation, while the real-world impact depends on how widely AP2-like protocols and vulnerable agent designs are deployed.  
Organisation evidence: — via none (org score 0.0, boost 0.0)

**16. Advancing Subseasonal Forecasting with Machine Learning** (id 99006, final 8.6)  
So what: Substantially improving probabilistic forecasts at the difficult 2–6 week horizon could directly benefit agriculture, energy, water management, and extreme-weather preparedness.  
Not higher because: Bias correction is an established general strategy, so the primary novelty appears to lie in the probabilistic framework, scale, and operational performance rather than a wholly new forecasting paradigm; longer-term deployment results are not yet reported.  
Organisation evidence: Massachusetts Institute of Technology via explicit_paper_affiliation (org score 3.0, boost 0.0955)

**17. Audit Without Verification: When LLM Accountability Layers Relay Rather Than Check** (id 185674, final 8.6)  
So what: LLM accountability layers may merely repeat upstream accusations rather than independently diagnose faults, making conclusion-independent evidence essential for reliable audits.  
Not higher because: The findings concern a controlled six-agent reporting architecture and selected models and domains, so their generality to real organizational workflows, heterogeneous agents, and richer audit evidence remains uncertain.  
Organisation evidence: — via none (org score 0.0, boost 0.0)

**18. ALIGN-HOLD: Experience Alignment for Real-Time Hold Control in Large-Scale Ride-Hailing Matching at DiDi** (id 186907, final 8.6)  
So what: It shows that implicit marketplace preferences can replace brittle handcrafted rewards for a consequential matching decision and deliver measurable benefits at production scale.  
Not higher because: The approach depends on platform-specific trajectory data, simulators, and marketplace instrumentation, while the abstract does not quantify effect sizes or establish portability beyond the deployed Brazil marketplace.  
Organisation evidence: Shanghai Jiao Tong University via explicit_paper_affiliation (org score 3.0, boost 0.0955)

**19. Clean Engineering, Unstable Measurement: A Preregistered Reliability Failure of Black-Box LLM Observers on Shared Endpoints** (id 138412, final 8.6)  
So what: It shows that shared-endpoint LLM judges may be too unstable to serve as reproducible measurement instruments and supplies concrete checks for detecting that failure before costly studies proceed.  
Not higher because: The findings concern particular shared serving environments and tested observer designs, so they do not establish that all hosted judges or evaluation tasks are unreliable; some mechanisms may also change as serving stacks evolve.  
Organisation evidence: — via none (org score 0.0, boost 0.0)

**20. Autonomous discovery of new structure-plausibility laws for explainable and rapid crystal diagnosis and screening** (id 136102, final 8.5)  
So what: PRIS could substantially reduce expensive crystal-validation workloads while providing chemically interpretable reasons for rejecting candidates, turning high-throughput screening into a more explainable process.  
Not higher because: Although the reported scale, screening gains, and mechanistic interpretability are exceptional, prospective experimental validation and demonstrated transfer across broader chemistries and generator distributions would be needed to establish the strongest possible claim of general physicochemical laws.  
Organisation evidence: — via none (org score 0.0, boost 0.0)


## 5. Organisation leaderboard

Organisation score is derived from verified affiliation evidence (paper affiliation, email domain, ROR, OpenAlex) and applied only after scoring.

| Organisation | On watchlist | Priority | Papers | Avg org score | Best final |
|---|---|---|---|---|---|
| Massachusetts Institute of Technology | no | 0 | 5 | 3.00 | 9.0 |
| Carnegie Mellon University | no | 0 | 5 | 3.00 | 8.8 |
| New York University | no | 0 | 5 | 3.00 | 8.2 |
| Nanyang Technological University | no | 0 | 5 | 3.00 | 7.6 |
| Zhejiang University | no | 0 | 4 | 3.00 | 7.6 |
| Peking University | no | 0 | 3 | 3.00 | 8.4 |
| Fudan University | no | 0 | 3 | 3.00 | 7.9 |
| Tsinghua University | no | 0 | 3 | 3.00 | 7.9 |
| National University of Singapore | no | 0 | 3 | 3.00 | 7.8 |
| Stanford University | no | 0 | 2 | 3.00 | 9.1 |
| University of Illinois Urbana-Champaign | no | 0 | 2 | 3.00 | 8.4 |
| Sun Yat-sen University | no | 0 | 2 | 3.00 | 8.1 |
| Singapore Management University | no | 0 | 2 | 3.00 | 8.0 |
| Institute of Science Tokyo | no | 0 | 2 | 3.00 | 7.9 |
| Shandong University | no | 0 | 2 | 3.00 | 7.9 |
| California Institute of Technology | no | 0 | 2 | 3.00 | 7.8 |
| University of Oxford | no | 0 | 2 | 3.00 | 7.8 |
| University of Virginia | no | 0 | 2 | 3.00 | 7.8 |
| Sichuan University | no | 0 | 2 | 3.00 | 7.4 |
| University of California San Diego | no | 0 | 2 | 3.00 | 7.4 |
| MIT Computer Science and Artificial Intelligence Laboratory | no | 0 | 1 | 3.00 | 8.8 |
| École Supérieure d'Ingénieurs en Génie Électrique | no | 0 | 1 | 3.00 | 8.7 |
| Belfort Labs (Belgium) | no | 0 | 1 | 3.00 | 8.7 |
| Shanghai Jiao Tong University | no | 0 | 1 | 3.00 | 8.6 |
| Duke University | no | 0 | 1 | 3.00 | 8.5 |


## 6. Domain distribution

| Domain | Papers | Avg quality |
|---|---|---|
| natural_language_processing | 353 | 8.01 |
| evaluation_benchmarking | 285 | 8.01 |
| computer_vision | 241 | 7.99 |
| theory_foundations | 194 | 8.01 |
| alignment_safety | 164 | 8.14 |
| robotics_embodied | 153 | 8.14 |
| multimodal_learning | 97 | 7.95 |
| interpretability | 95 | 7.79 |
| reinforcement_learning | 89 | 8.02 |
| efficient_inference | 88 | 8.25 |
| generative_models | 86 | 8.12 |
| systems_infrastructure | 77 | 8.33 |
| model_compression | 62 | 8.12 |
| graph_learning | 47 | 7.98 |
| speech_audio | 42 | 8.07 |


## 7. Data quality

| Check | Count |
|---|---|
| Papers in current state | 5225 |
| Affiliation resolved | 108 |
| Affiliation evidence present but ambiguous | 43 |
| No affiliation evidence supplied | 5074 |
| Screen/quality disagreement ≥ 3.0 | 0 |


Unresolved affiliations are reported, not hidden: unknown beats wrong, and every raw affiliation string is preserved for re-resolution.
