# PaperIntelligence v1 — Run Report

**Window:** 2026-09-01 → 2026-09-16 (published_at)  
**Generated:** 2026-09-16 06:59 UTC  
**Pipeline:** relevance (free) → normalize_authors (free) → screen → classify → quality → affiliation → adjudication

## 1. Funnel

| Step | Papers |
|---|---|
| arXiv ingested in window | 12149 |
| Rejected by relevance (free, pre-LLM) | 4306 |
| Entered paid stages | 7843 |
| Passed screen gate | 7300 |
| Failed screen gate (scores kept) | 205 |

Relevance runs first precisely so the paid stages never see the rejected papers.

## 2. Stage coverage

| Task type | Papers | Result rows |
|---|---|---|
| screen | 7505 | 7505 |
| application_domain | 4246 | 4246 |
| audience | 4246 | 4246 |
| domain | 4246 | 4246 |
| subdomain | 4246 | 4246 |
| quality | 1820 | 1820 |


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
| affiliation | v001 | succeeded | 200 | 158 | 0 | 521.8 |
| adjudication | v001 | succeeded | 0 | 2354 | 0 | 2.3 |
| affiliation | v001 | running | 200 | 0 | 0 |  |
| adjudication | v001 | succeeded | 0 | 7505 | 0 | 4.9 |


## 3. Cost

| Model | Stage | Calls | Input tokens | Output tokens | Cost (USD) |
|---|---|---|---|---|---|
| openai/gpt-5.6-sol | quality | 365 | 773427 | 364640 | $4.6132 |
| z-ai/glm-5.3-flash | classify | 291 | 1680437 | 955053 | $0.7296 |
| z-ai/glm-5.3-flash | screen | 506 | 2546397 | 671105 | $0.7175 |

**Total LLM spend:** $6.0603

| External provider | Requests | Cache hits | Failures |
|---|---|---|---|
| arxiv | 2385 | 275 | 113 |
| openrouter | 1614 | 0 | 452 |
| ror | 1412 | 453 | 0 |
| openalex | 736 | 107 | 133 |


## 4. Top 20 papers by final score

Final score = blinded quality composite × evidence factor + organisation boost (capped at 0.5). The quality model never saw authors or affiliations.

| # | Title | Final | Quality | Screen | Org score | Boost | Organisation | Domain |
|---|---|---|---|---|---|---|---|---|
| 1 | Learning transferable human physiology from two million hours of sleep | 9.2 | 9.1 | 7.7 | 6.0 | 0.191 | Stanford University | multimodal_learning |
| 2 | Scaling Verification of Cryptographic Software with Aeneas, Rust, and  | 9.1 | 9.3 | 8.0 | 3.0 | 0.096 | École Normale Supérieure - PSL | systems_infrastructure |
| 3 | Evidence Integration in Large Language Models | 9.1 | 9.1 | 8.3 | 6.0 | 0.270 | Massachusetts Institute of Technology | interpretability |
| 4 | Flattening Every Memory Peak in Long-Context Mixture-of-Experts Traini | 8.9 | 9.3 | 7.5 | 0.0 | 0.000 | — | systems_infrastructure |
| 5 | Water-network decisions share one hydraulic gradient, and it can now b | 8.9 | 9.2 | 7.3 | 0.0 | 0.000 | — | theory_foundations |
| 6 | The Intruder Threshold: A Spectral Law for LoRA Fine-Tuning | 8.9 | 9.0 | 8.3 | 3.0 | 0.113 | Technical University of Munich | theory_foundations |
| 7 | The Oversight Gap: What LLM Safety Monitors Miss, and Why It Is Not Ca | 8.9 | 8.9 | 7.5 | 6.0 | 0.225 | Carnegie Mellon University | alignment_safety |
| 8 | MOLE: Detecting Insider Threats in AI Agents | 8.9 | 8.9 | 7.8 | 6.0 | 0.191 | Carnegie Mellon University | evaluation_benchmarking |
| 9 | TyPatch: Transforming Patches into Typestate Rules for Kernel Bug Dete | 8.9 | 8.9 | 7.5 | 6.0 | 0.270 | Tsinghua University | natural_language_processing |
| 10 | Extending concurrent separation logic to the hardware level to verify  | 8.8 | 9.1 | 7.0 | 3.0 | 0.096 | MIT Computer Science and Artificial Intelligence Laboratory | theory_foundations |
| 11 | 4D Parallelism Unlocks Exascale Bayesian Neural Networks for High-Fide | 8.7 | 9.1 | 7.5 | 3.0 | 0.096 | Forschungszentrum Jülich | systems_infrastructure |
| 12 | An ab initio foundation model of wavefunctions that accurately describ | 8.7 | 9.0 | 8.7 | 6.0 | 0.270 | Microsoft | theory_foundations |
| 13 | Atlas: Efficient Verifiable Semantic Search | 8.7 | 9.0 | 8.2 | 3.0 | 0.096 | Belfort Labs (Belgium) | systems_infrastructure |
| 14 | Nameless Tokenization: A Lossless Tokenizer-Level Defense Against Cont | 8.7 | 8.9 | 7.7 | 3.0 | 0.096 | Korea University | natural_language_processing |
| 15 | Alignment Whack-a-Mole : Finetuning Activates Verbatim Recall of Copyr | 8.7 | 8.9 | 8.3 | 3.0 | 0.135 | Columbia University | alignment_safety |
| 16 | MINERVA: How Small Can a Manipulation Policy Be and Still Solve LIBERO | 8.7 | 8.9 | 8.2 | 3.0 | 0.096 | École Supérieure d'Ingénieurs en Génie Électrique | robotics_embodied |
| 17 | RelateAnything: Real-Time Open-Vocabulary Relation Prediction From Any | 8.7 | 8.9 | 7.8 | 0.0 | 0.000 | — | computer_vision |
| 18 | Misleading the Planner through Deceptive Resumes: Registration-Time In | 8.7 | 8.8 | 7.2 | 3.0 | 0.135 | National University of Singapore | alignment_safety |
| 19 | Hyperparameter Scaling Laws Across MoE Sparsity | 8.7 | 8.8 | 8.0 | 0.0 | 0.000 | — | theory_foundations |
| 20 | Illusion of Depth: Revealing Hidden Stereo Vision Vulnerabilities in D | 8.7 | 8.8 | 8.0 | 3.0 | 0.096 | University of Florida | computer_vision |


### Why these papers

**1. Learning transferable human physiology from two million hours of sleep with SleepFM-2** (id 184835, final 9.2)  
So what: A broadly transferable representation learned from sleep physiology could support scalable disease screening, sleep assessment, and cross-sensor health modeling from clinical and wearable data.  
Not higher because: Despite exceptional scale and breadth, the abstract does not establish prospective clinical utility, causal validity, calibration across populations, or whether gains justify the operational cost of deploying such a model.  
Organisation evidence: Stanford University via explicit_paper_affiliation (org score 6.0, boost 0.1911)

**2. Scaling Verification of Cryptographic Software with Aeneas, Rust, and Lean** (id 194032, final 9.1)  
So what: This work presents a credible route to kernel-checked verification of production-grade, high-performance cryptographic implementations without abandoning Rust, portability, or deployment requirements.  
Not higher because: The methodology still depends on expert-reviewed formalizations, Rust ports, specialized tooling, and a very large Lean development, so its cost and transferability beyond the demonstrated cryptographic codebase remain important constraints.  
Organisation evidence: École Normale Supérieure - PSL via explicit_paper_affiliation (org score 3.0, boost 0.0955)

**3. Evidence Integration in Large Language Models** (id 142581, final 9.1)  
So what: It provides a predictive and mechanistic account of why LLMs accept external answers—even ones they can verify are wrong—with major implications for retrieval, tool use, multi-agent systems, and scientific reasoning.  
Not higher because: The proposed distributional law and mechanistic dissociation are broad but may not fully capture interactive, long-context, or source-aware evidence use in deployed systems, and practical countermeasures are not yet established.  
Organisation evidence: Massachusetts Institute of Technology via email_domain (org score 6.0, boost 0.27)

**4. Flattening Every Memory Peak in Long-Context Mixture-of-Experts Training** (id 193268, final 8.9)  
So what: Bounding every major memory peak can turn otherwise infeasible long-context, hundred-billion-parameter MoE training runs into executable and efficient workloads without approximate gradients.  
Not higher because: The exceptional scale and throughput claims require substantial specialized infrastructure, and the abstract does not fully expose communication costs, hardware sensitivity, implementation complexity, or independent reproducibility.  
Organisation evidence: — via none (org score 0.0, boost 0.0)

**5. Water-network decisions share one hydraulic gradient, and it can now be computed exactly** (id 184607, final 8.9)  
So what: Exact, scalable gradients for established water-network simulators could replace costly derivative-free workflows and materially improve calibration, leak localisation, and sensor planning.  
Not higher because: The claims are exceptionally strong, but broader deployment evidence is still needed for difficult operational regimes, topology or control changes, and nondifferentiable status boundaries; reproducibility and integration details are not stated in the abstract.  
Organisation evidence: — via none (org score 0.0, boost 0.0)

**6. The Intruder Threshold: A Spectral Law for LoRA Fine-Tuning** (id 106054, final 8.9)  
So what: A parameter-free spectral threshold could predict which LoRA updates create harmful new directions and enable safer adapter tuning without validation sweeps.  
Not higher because: Threshold localization is only within a factor of two for 82% of layers, and the reported mitigation and task-preservation result appears concentrated on the most fragile model; broader downstream tasks and training regimes would be needed for a near-universal law.  
Organisation evidence: Technical University of Munich via email_domain (org score 3.0, boost 0.1125)

**7. The Oversight Gap: What LLM Safety Monitors Miss, and Why It Is Not Capability** (id 184994, final 8.9)  
So what: It reframes important monitoring failures as information-and-procedure limits, providing formal detectability bounds and concrete guidance for building valid safety oversight and benchmarks.  
Not higher because: The strongest conclusions appear grounded in controlled leak families and designed factorial experiments; applicability of the quantitative frontiers to messy, adaptive production threats remains to be demonstrated.  
Organisation evidence: Carnegie Mellon University via email_domain (org score 6.0, boost 0.225)

**8. MOLE: Detecting Insider Threats in AI Agents** (id 184890, final 8.9)  
So what: MOLE provides a large, realistic testbed for determining whether limited-budget monitoring can detect harmful AI-agent activity hidden within routine account operations.  
Not higher because: The benchmark covers a bounded set of simulated services, threats, models, and audit conditions, so its results may not fully transfer to evolving agents or real frontier-lab infrastructure.  
Organisation evidence: Carnegie Mellon University via explicit_paper_affiliation (org score 6.0, boost 0.1911)

**9. TyPatch: Transforming Patches into Typestate Rules for Kernel Bug Detection** (id 192435, final 8.9)  
So what: Separating LLM-extracted defect rules from reusable program-analysis machinery turns historical patches into scalable kernel bug detectors with strong precision and major generation-cost savings.  
Not higher because: The results are centered on one large and unusually well-curated codebase, and the abstract does not quantify recall, false-negative behavior, backend soundness, or portability to substantially different systems and languages.  
Organisation evidence: Tsinghua University via email_domain (org score 6.0, boost 0.27)

**10. Extending concurrent separation logic to the hardware level to verify the xv6 OS kernel on RISC-V with AI agents** (id 138345, final 8.8)  
So what: Connecting concurrent separation logic to detailed RISC-V execution and using it to verify a concurrent OS kernel could substantially narrow the assurance gap between software proofs and real hardware behavior.  
Not higher because: The case study is limited to the relatively small xv6 kernel, while the abstract does not quantify proof coverage, trusted-computing-base assumptions, automation rates, or how much the AI agents contributed beyond human-guided verification.  
Organisation evidence: MIT Computer Science and Artificial Intelligence Laboratory via explicit_paper_affiliation (org score 3.0, boost 0.0955)

**11. 4D Parallelism Unlocks Exascale Bayesian Neural Networks for High-Fidelity Atmospheric Modeling** (id 191803, final 8.7)  
So what: BEAST combines scalable Bayesian deep learning with global high-resolution forecasting, making large-ensemble uncertainty quantification and extreme-event prediction feasible at unprecedented computational scale.  
Not higher because: The approach requires extraordinary supercomputing resources, the largest performance run and the fully trained model use different scales, and claims of exceptional extreme-event skill and first-ever status need broader task-specific comparisons and independent confirmation.  
Organisation evidence: Forschungszentrum Jülich via explicit_paper_affiliation (org score 3.0, boost 0.0955)

**12. An ab initio foundation model of wavefunctions that accurately describes chemical bond breaking** (id 191305, final 8.7)  
So what: A transferable neural wavefunction that reliably handles bond breaking could amortize expensive quantum calculations across molecules and make high-accuracy multireference predictions substantially more accessible.  
Not higher because: The practical reach still depends on fine-tuning cost, scaling to larger and more chemically diverse systems, and independent validation of the claimed consistency and cost advantage over established multireference methods.  
Organisation evidence: Microsoft via email_domain (org score 6.0, boost 0.27)

**13. Atlas: Efficient Verifiable Semantic Search** (id 188266, final 8.7)  
So what: Atlas makes high-recall HNSW semantic search cryptographically verifiable at realistic scale, reducing the need to trust retrieval providers without exposing their indexes.  
Not higher because: The abstract does not expose proof sizes, verifier and preprocessing costs, update handling, hardware assumptions, or operational trade-offs for dynamic production indexes, all of which affect real-world deployment.  
Organisation evidence: Belfort Labs (Belgium) via explicit_paper_affiliation (org score 3.0, boost 0.0955)

**14. Nameless Tokenization: A Lossless Tokenizer-Level Defense Against Control-Token Forgery in Open-Weight LLMs** (id 195035, final 8.7)  
So what: Removing surface strings from reserved control tokens offers an unusually clean, lossless way to prevent prompt content from forging privileged turn, tool, or reasoning boundaries.  
Not higher because: The evaluation covers tokenizer behavior and targeted probes, but the abstract does not fully demonstrate deployment compatibility, end-to-end security under adaptive attacks, or effects across broader agent stacks and model families.  
Organisation evidence: Korea University via explicit_paper_affiliation (org score 3.0, boost 0.0955)

**15. Alignment Whack-a-Mole : Finetuning Activates Verbatim Recall of Copyrighted Books in Large Language Models** (id 42672, final 8.7)  
So what: If ordinary-looking finetuning can reactivate extensive verbatim recall, alignment safeguards may not reliably prevent copyrighted training material from being extracted after model customization.  
Not higher because: The strong conclusion that weights store copies has substantial technical and legal nuance, while the abstract does not fully expose extraction controls, contamination checks, reproducibility constraints, or the representativeness of the tested books and APIs.  
Organisation evidence: Columbia University via email_domain (org score 3.0, boost 0.135)

**16. MINERVA: How Small Can a Manipulation Policy Be and Still Solve LIBERO?** (id 138187, final 8.7)  
So what: It shows that standard LIBERO tasks can be solved by sub-million-parameter, CPU-deployable policies while exposing memorization and robustness limitations hidden by headline benchmark scores.  
Not higher because: The capacity-floor conclusion is benchmark-specific, and the severe LIBERO-Plus degradation leaves open whether the compact policy design transfers to diverse real-world manipulation.  
Organisation evidence: École Supérieure d'Ingénieurs en Génie Électrique via explicit_paper_affiliation (org score 3.0, boost 0.0955)

**17. RelateAnything: Real-Time Open-Vocabulary Relation Prediction From Any Inputs** (id 191681, final 8.7)  
So what: This work moves relation prediction toward genuinely open-vocabulary, detector-independent deployment while supplying the large corpus and transfer-oriented benchmark needed to evaluate that capability.  
Not higher because: The strongest claims depend on a newly introduced corpus and benchmark, and broader independent validation is needed to establish coverage of rare, ambiguous, compositional, and culturally dependent relations in unconstrained settings.  
Organisation evidence: — via none (org score 0.0, boost 0.0)

**18. Misleading the Planner through Deceptive Resumes: Registration-Time Injection in Centralized Multi-Agent Systems** (id 193970, final 8.7)  
So what: Registration-time injection exposes a consequential supply-chain-like weakness in multi-agent systems, while DescGuard offers a deployable way to constrain untrusted agent descriptions before they can corrupt planning.  
Not higher because: The attack and defense are evaluated within centralized planner-worker architectures and GAIA-style tasks; broader validation is needed for decentralized systems, richer tool ecosystems, adaptive attackers, and cases where aggressive description filtering removes legitimate interface semantics.  
Organisation evidence: National University of Singapore via email_domain (org score 3.0, boost 0.135)

**19. Hyperparameter Scaling Laws Across MoE Sparsity** (id 186119, final 8.7)  
So what: Unified scaling laws for learning rate and batch size across MoE sparsity could substantially reduce costly hyperparameter searches when training increasingly sparse models.  
Not higher because: The laws remain empirical and may depend on the studied architecture, optimizer, routing design, data regime, and scale range; validation beyond 12B parameters and across substantially different training stacks is not reported here.  
Organisation evidence: — via none (org score 0.0, boost 0.0)

**20. Illusion of Depth: Revealing Hidden Stereo Vision Vulnerabilities in Depth Estimation** (id 194708, final 8.7)  
So what: Simple physical patterns can dangerously manipulate stereo depth across classical, learned, fused, and commercial systems, exposing a concrete safety risk for autonomous vehicles and robots while motivating a targeted defense.  
Not higher because: The abstract does not fully characterize attacker deployment constraints, robustness across lighting, distance, viewing angle, weather, or unseen camera pipelines, and the proposed defense still needs broad validation against adaptive attacks and under safety-critical operating conditions.  
Organisation evidence: University of Florida via explicit_paper_affiliation (org score 3.0, boost 0.0955)


## 5. Organisation leaderboard

Organisation score is derived from verified affiliation evidence (paper affiliation, email domain, ROR, OpenAlex) and applied only after scoring.

| Organisation | On watchlist | Priority | Papers | Avg org score | Best final |
|---|---|---|---|---|---|
| Tsinghua University | yes | 6 | 44 | 6.00 | 8.9 |
| Carnegie Mellon University | yes | 6 | 38 | 6.00 | 8.9 |
| Zhejiang University | no | 0 | 27 | 3.00 | 8.4 |
| Stanford University | yes | 8 | 22 | 6.00 | 9.2 |
| National University of Singapore | no | 0 | 19 | 3.00 | 8.7 |
| Peking University | no | 0 | 18 | 3.00 | 8.4 |
| Shanghai Jiao Tong University | no | 0 | 17 | 3.00 | 8.6 |
| Fudan University | no | 0 | 17 | 3.00 | 8.5 |
| Nanyang Technological University | no | 0 | 15 | 3.00 | 7.6 |
| Massachusetts Institute of Technology | yes | 8 | 14 | 6.00 | 9.1 |
| University of Cambridge | no | 0 | 14 | 3.00 | 8.6 |
| University of Oxford | no | 0 | 13 | 3.00 | 8.6 |
| Seoul National University | no | 0 | 13 | 3.00 | 8.1 |
| Technical University of Munich | no | 0 | 12 | 3.00 | 8.9 |
| University of Illinois Urbana-Champaign | no | 0 | 11 | 3.00 | 8.4 |
| Korea University of Science and Technology | no | 0 | 11 | 3.00 | 8.2 |
| New York University | no | 0 | 11 | 3.00 | 8.2 |
| ETH Zurich | no | 0 | 9 | 3.00 | 8.1 |
| Nanjing University | no | 0 | 9 | 3.00 | 7.8 |
| University of California, Berkeley | yes | 8 | 8 | 6.00 | 8.7 |
| University of Chinese Academy of Sciences | no | 0 | 8 | 3.00 | 8.1 |
| Johns Hopkins University | no | 0 | 8 | 3.00 | 7.9 |
| Beihang University | no | 0 | 8 | 3.00 | 7.7 |
| Georgia Institute of Technology | no | 0 | 7 | 3.00 | 8.3 |
| Institute of Science Tokyo | no | 0 | 7 | 3.00 | 8.1 |


## 6. Domain distribution

| Domain | Papers | Avg quality |
|---|---|---|
| natural_language_processing | 751 | 8.02 |
| evaluation_benchmarking | 530 | 7.99 |
| computer_vision | 503 | 8.03 |
| theory_foundations | 399 | 8.03 |
| robotics_embodied | 329 | 8.12 |
| alignment_safety | 294 | 8.14 |
| multimodal_learning | 234 | 7.98 |
| interpretability | 193 | 7.82 |
| reinforcement_learning | 193 | 7.98 |
| efficient_inference | 180 | 8.27 |
| generative_models | 164 | 8.09 |
| systems_infrastructure | 151 | 8.39 |
| speech_audio | 122 | 8.06 |
| model_compression | 108 | 8.12 |
| graph_learning | 95 | 7.97 |


## 7. Data quality

| Check | Count |
|---|---|
| Papers in current state | 7505 |
| Affiliation resolved | 1005 |
| Affiliation evidence present but ambiguous | 281 |
| No affiliation evidence supplied | 6219 |
| Screen/quality disagreement ≥ 3.0 | 0 |


Unresolved affiliations are reported, not hidden: unknown beats wrong, and every raw affiliation string is preserved for re-resolution.
