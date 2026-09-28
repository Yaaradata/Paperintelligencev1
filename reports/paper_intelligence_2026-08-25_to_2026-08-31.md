# PaperIntelligence v1 — Run Report

**Window:** 2026-08-25 → 2026-08-31 (published_at)  
**Generated:** 2026-09-28 08:53 UTC  
**Pipeline:** relevance (free) → normalize_authors (free) → screen → classify → quality → affiliation → adjudication

## 1. Funnel

| Step | Papers |
|---|---|
| arXiv ingested in window | 4121 |
| Rejected by relevance (free, pre-LLM) | 1521 |
| Entered paid stages | 2600 |
| Passed screen gate | 2505 |
| Failed screen gate (scores kept) | 95 |
| Quality scored | 2505 |
| Quality pending | 0 |
| Quality failed | 0 |
| Stale content (hash mismatch) | 0 |

Relevance runs first precisely so the paid stages never see the rejected papers.

**Quality models in scored pool:** `typesafe/jev-1.13` ×2505

## 2. Stage coverage

| Task type | Papers | Result rows |
|---|---|---|
| screen | 2600 | 2795 |
| application_domain | 2505 | 2572 |
| audience | 2505 | 2572 |
| domain | 2505 | 2572 |
| quality | 2505 | 2563 |
| subdomain | 2505 | 2572 |


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
| ingest | v001 | succeeded | 0 | 4973 | 0 | 89.4 |
| ingest | v001 | succeeded | 0 | 0 | 0 | 61.1 |
| quality | v001 | partial | 1 | 0 | 1 | 6.1 |
| quality | v001 | running | 1 | 0 | 0 |  |
| quality | v001 | running | 1 | 0 | 0 |  |
| quality | v001 | running | 1 | 0 | 0 |  |
| quality | v001 | succeeded | 60 | 60 | 0 | 34.4 |
| relevance | v001 | succeeded | 0 | 2637 | 0 | 16.5 |
| screen | v001 | partial | 2638 | 2637 | 1 | 718.3 |
| affiliation_fast | v002 | succeeded | 2535 | 0 | 0 | 7.9 |
| quality | v001 | succeeded | 380 | 380 | 0 | 176.2 |
| affiliation_deep | v002 | succeeded | 380 | 272 | 0 | 895.4 |
| hf_signals | v001 | succeeded | 0 | 58 | 0 | 18.2 |
| adjudication | v001 | succeeded | 0 | 2637 | 0 | 1.9 |
| affiliation_fast | v003 | succeeded | 2535 | 1713 | 0 | 2858.5 |
| screen | v001 | succeeded | 1 | 1 | 0 | 5.2 |
| quality | v001 | succeeded | 202 | 202 | 0 | 105.2 |
| affiliation_deep | v002 | succeeded | 582 | 474 | 0 | 741.9 |
| adjudication | v001 | succeeded | 0 | 2638 | 0 | 2.2 |
| quality | v001 | partial | 1347 | 1005 | 342 | 547.5 |
| affiliation_deep | v002 | running | 1587 | 0 | 0 |  |
| quality | v001 | running | 342 | 0 | 0 |  |
| affiliation_deep | v002 | succeeded | 168 | 15 | 0 | 227.8 |
| quality | v001 | succeeded | 24 | 24 | 0 | 12.4 |
| ingest | v001 | succeeded | 0 | 2177 | 0 | 87.5 |
| screen | v001 | succeeded | 478 | 478 | 0 | 351.0 |
| quality | v001 | failed | 200 | 0 | 0 | 1937.7 |
| affiliation_fast | v003 | succeeded | 456 | 297 | 0 | 414.6 |
| domain | v001 | partial | 456 | 231 | 225 | 970.0 |
| quality | v001 | running | 456 | 0 | 0 |  |
| affiliation_deep | v002 | succeeded | 290 | 212 | 0 | 435.0 |
| quality | v001 | succeeded | 456 | 456 | 0 | 3480.1 |
| quality | v001 | succeeded | 200 | 200 | 0 | 1940.0 |
| hf_signals | v001 | succeeded | 0 | 48 | 0 | 11.3 |
| adjudication | v001 | succeeded | 0 | 478 | 0 | 0.5 |
| relevance | v001 | succeeded | 0 | 1083 | 0 | 7.6 |
| screen | v001 | succeeded | 1083 | 1083 | 0 | 418.3 |
| affiliation_fast | v003 | succeeded | 1489 | 979 | 0 | 1723.5 |
| adjudication | v001 | succeeded | 0 | 1561 | 0 | 1.5 |
| domain | v001 | partial | 1258 | 493 | 765 | 2924.6 |
| quality | v001 | running | 1033 | 0 | 0 |  |
| quality | v001 | running | 1033 | 0 | 0 |  |
| quality | v001 | succeeded | 1033 | 1033 | 0 | 8354.5 |
| ingest | v001 | running | 0 | 0 | 0 |  |
| ingest | v001 | running | 0 | 0 | 0 |  |
| ingest | v001 | succeeded | 0 | 0 | 0 | 1.4 |
| relevance | v001 | succeeded | 0 | 388 | 0 | 5.7 |
| screen | v001 | partial | 3793 | 3778 | 15 | 2465.6 |
| affiliation_fast | v003 | succeeded | 3655 | 2536 | 0 | 3506.9 |
| adjudication | v001 | succeeded | 0 | 1561 | 0 | 1.9 |
| domain | v001 | partial | 3655 | 1900 | 1755 | 6404.9 |
| quality | v001 | succeeded | 3655 | 3655 | 0 | 22757.0 |
| quality_prose | quality_prose_v001 | cancelled | 1620 | 0 | 0 |  |
| quality_prose | quality_prose_v001 | failed | 20 | 0 | 0 | 71.1 |
| quality_prose | quality_prose_v001 | failed | 20 | 0 | 0 | 0.7 |
| quality_prose | quality_prose_v001 | succeeded | 20 | 20 | 0 | 15.1 |
| ingest | v001 | succeeded | 0 | 121 | 0 | 336.5 |
| quality_prose | quality_prose_v001 | succeeded | 20 | 20 | 0 | 17.4 |
| domain | v001 | cancelled | 20 | 0 | 20 | 41.9 |
| domain | v001 | succeeded | 20 | 20 | 0 | 14.0 |
| ingest | v001 | succeeded | 0 | 0 | 0 | 0.0 |
| relevance | v001 | succeeded | 0 | 75 | 0 | 1.1 |
| screen | v001 | succeeded | 280 | 280 | 0 | 38.5 |
| affiliation_fast | v003 | succeeded | 2505 | 1644 | 0 | 1276.6 |
| domain | v001 | succeeded | 1289 | 1289 | 0 | 207.6 |
| quality | v001 | succeeded | 273 | 273 | 0 | 219.1 |
| affiliation_deep | v002 | succeeded | 2505 | 1824 | 0 | 2675.5 |
| hf_signals | v001 | succeeded | 0 | 153 | 0 | 1.1 |
| adjudication | v001 | succeeded | 0 | 2600 | 0 | 3.8 |


## 3. Cost

| Model | Stage | Calls | Input tokens | Output tokens | Cost (USD) |
|---|---|---|---|---|---|
| openai/gpt-5.6-terra | quality | 336 | 689492 | 293252 | $4.8980 |
| openai/gpt-5.6-sol | quality | 379 | 800434 | 378606 | $4.7866 |
| z-ai/glm-5.3-flash | screen | 1079 | 5420407 | 1773190 | $1.6997 |
| z-ai/glm-5.3-flash | audience_domain | 468 | 2736766 | 2523070 | $1.6721 |
| z-ai/glm-5.3-flash | quality_prose | 1521 | 2790600 | 1402947 | $1.1201 |
| z-ai/glm-5.3-flash | classify | 291 | 1680437 | 955053 | $0.7296 |
| openai/gpt-6-luna | prose_audit | 708 | 889750 | 331273 | $0.2546 |
| z-ai/glm-4.6 | affiliation_judge | 68 | 64739 | 62596 | $0.0410 |

**Total LLM spend:** $15.2017

| External provider | Requests | Cache hits | Failures |
|---|---|---|---|
| openalex | 30150 | 24732 | 1523 |
| arxiv | 27690 | 7436 | 1525 |
| ror | 10831 | 4174 | 0 |
| openrouter | 5987 | 0 | 1137 |
| huggingface | 1348 | 612 | 7 |


## 4. Top 20 papers by final score

Final score = blinded quality composite × evidence factor + organisation boost (capped at 0.5). The quality model never saw authors or affiliations.

| # | Title | Final | Quality | Screen | Org score | Boost | Organisation | Domain |
|---|---|---|---|---|---|---|---|---|
| 1 | SilentProbe: Measuring Silent Failure in Production APIs Used as Agent | 8.0 | 8.2 | 7.2 | 3.0 | 0.135 | Texas A&M University | systems_infrastructure |
| 2 | Beyond the Editing Canvas: Evidence Divergence in OOXML-to-LLM Ingesti | 7.9 | 8.2 | 7.2 | 3.0 | 0.128 | Wuhan University | systems_infrastructure |
| 3 | Delegation Without Trust: An Empirical Gap Analysis of Identity, Autho | 7.8 | 8.4 | 7.0 | 0.0 | 0.000 | — | alignment_safety |
| 4 | Reading Is Not Using: Retrieval, Judgment, and the Design of AI Financ | 7.8 | 8.2 | 7.5 | 3.0 | 0.135 | Columbia University | natural_language_processing |
| 5 | Efficient GPU Retrieval for Semantic Search | 7.8 | 8.2 | 6.8 | 0.0 | 0.000 | — | natural_language_processing |
| 6 | APIFlow-Bench: Measuring Whether Agents Survive Long, Dependent API Wo | 7.8 | 8.2 | 7.8 | 0.0 | 0.000 | — | evaluation_benchmarking |
| 7 | Recognition Without Enforcement: Configuration-Dependent Failures in L | 7.7 | 8.1 | 7.3 | 0.0 | 0.000 | — | alignment_safety |
| 8 | Vowel Signs Are Not Letters: A Pre-tokenization Ceiling on Multilingua | 7.7 | 8.1 | 7.7 | 0.0 | 0.000 | — | natural_language_processing |
| 9 | How Fast Do Agents Rot? An Empirical Study of Long-Horizon Degradation | 7.7 | 8.1 | 7.0 | 0.0 | 0.000 | — | evaluation_benchmarking |
| 10 | LongGuard: Mechanistic Analysis and Training-Free Mitigation of Long-C | 7.7 | 8.1 | 6.8 | 3.0 | 0.128 | Institute of Information Engineering | alignment_safety |
| 11 | SetMIR: Multi-Interest Retrieval as Set Prediction | 7.7 | 8.1 | 7.0 | 0.0 | 0.000 | — | natural_language_processing |
| 12 | TransRetrieval: Scaling Up Transformer-Based Retrieval for Industrial  | 7.7 | 8.0 | 7.2 | 3.0 | 0.135 | Renmin University of China | natural_language_processing |
| 13 | From Generation to Discovery: Diffusion Mutation Kernels for Circuit a | 7.6 | 8.1 | 7.7 | 0.0 | 0.000 | — | generative_models |
| 14 | InfraOcc: An Infrastructure Occupancy Benchmark with Static-to-Dynamic | 7.6 | 8.0 | 7.3 | 3.0 | 0.135 | Nanyang Technological University | computer_vision |
| 15 | Scaling Graph Neural Networks for Friend Recommendation: Multi-Hash Us | 7.6 | 8.0 | 7.0 | 0.0 | 0.000 | — | graph_learning |
| 16 | The Framing Gap: Indirect Prompt-Injection Exfiltration Defeats Surfac | 7.6 | 8.0 | 7.5 | 3.0 | 0.128 | Gyeongsang National University | alignment_safety |
| 17 | EVOMAL: Self-Poisoning in Self-Evolving Coding Agents | 7.6 | 7.9 | 7.7 | 3.0 | 0.135 | Queen's University | alignment_safety |
| 18 | CogEvol: Towards Efficient and Reliable Learning Environment Generatio | 7.6 | 7.9 | 6.2 | 6.0 | 0.255 | Tsinghua University | generative_models |
| 19 | Sequential knowledge editing breaks a model's ability to tell good evi | 7.6 | 7.9 | 7.7 | 0.0 | 0.000 | — | natural_language_processing |
| 20 | ACE: A Self-Correcting Agentic Canvas Editor for Multi-Slide Presentat | 7.6 | 7.9 | 6.2 | 3.0 | 0.128 | Seoul National University | natural_language_processing |


### Why these papers

**1. SilentProbe: Measuring Silent Failure in Production APIs Used as Agent Tools** (id 135007, final 8.0)  
So what: —  
Not higher because: —  
Organisation evidence: Texas A&M University via email_domain (org score 3.0, boost 0.135)

**2. Beyond the Editing Canvas: Evidence Divergence in OOXML-to-LLM Ingestion** (id 175040, final 7.9)  
So what: Any pipeline feeding Office documents to LLMs should assume the extracted text can differ from what users see in Office, and should pin extractor versions, document which view is authoritative, and test against known evidence forks. This is a concrete, fixable compliance and reliability gap affecting financial and legal workflows today.  
Not higher because: The 21 documented forks and measured trap rates are a snapshot of current extractors and model APIs, so specific percentages will shift as vendors patch, though the structural problem will persist.  
Organisation evidence: Wuhan University via explicit_paper_affiliation (org score 3.0, boost 0.1275)

**3. Delegation Without Trust: An Empirical Gap Analysis of Identity, Authorization, and Runtime Governance in Multi-Agent LLM Systems** (id 135595, final 7.8)  
So what: —  
Not higher because: —  
Organisation evidence: — via none (org score 0.0, boost 0.0)

**4. Reading Is Not Using: Retrieval, Judgment, and the Design of AI Financial Research Workflows** (id 121976, final 7.8)  
So what: —  
Not higher because: —  
Organisation evidence: Columbia University via email_domain (org score 3.0, boost 0.135)

**5. Efficient GPU Retrieval for Semantic Search** (id 133270, final 7.8)  
So what: —  
Not higher because: —  
Organisation evidence: — via none (org score 0.0, boost 0.0)

**6. APIFlow-Bench: Measuring Whether Agents Survive Long, Dependent API Workflows** (id 133366, final 7.8)  
So what: —  
Not higher because: —  
Organisation evidence: — via none (org score 0.0, boost 0.0)

**7. Recognition Without Enforcement: Configuration-Dependent Failures in LLM Agent Instruction Arbitration and External Control** (id 176906, final 7.7)  
So what: Treat LLM agent instruction arbitration as a capability, not a security boundary: even models that verbally detect forged authority can still execute the conflicting tool call, and prompt-layer defenses do not generalize across models or adaptive attacks. The actionable takeaway is to deploy an external reference monitor with authenticated source routing and capability-gated tool execution, which the authors show deterministically blocks all tested forgeries.  
Not higher because: The reference monitor is validated against the authors' own attack suite and one red-team pass, so its robustness against broader adaptive adversaries and integration cost in production fleets remain open.  
Organisation evidence: — via none (org score 0.0, boost 0.0)

**8. Vowel Signs Are Not Letters: A Pre-tokenization Ceiling on Multilingual Tokenizer Fertility** (id 122862, final 7.7)  
So what: —  
Not higher because: —  
Organisation evidence: — via none (org score 0.0, boost 0.0)

**9. How Fast Do Agents Rot? An Empirical Study of Long-Horizon Degradation in LLM Agents for Production Decision-Making** (id 136350, final 7.7)  
So what: —  
Not higher because: —  
Organisation evidence: — via none (org score 0.0, boost 0.0)

**10. LongGuard: Mechanistic Analysis and Training-Free Mitigation of Long-Context Failure in Safety Guardrails** (id 134341, final 7.7)  
So what: —  
Not higher because: —  
Organisation evidence: Institute of Information Engineering via explicit_paper_affiliation (org score 3.0, boost 0.1275)

**11. SetMIR: Multi-Interest Retrieval as Set Prediction** (id 134497, final 7.7)  
So what: —  
Not higher because: —  
Organisation evidence: — via none (org score 0.0, boost 0.0)

**12. TransRetrieval: Scaling Up Transformer-Based Retrieval for Industrial Recommendation** (id 174869, final 7.7)  
So what: Token-norm divergence from heterogeneous features is the concrete blocker to scaling Transformers in recommendation retrieval, and weighted average aggregation plus target token compression restores log-linear scaling while cutting per-candidate FLOPs by 85% — a validated recipe for teams planning retrieval compute investments. The 2.53% revenue lift under identical latency constraints is the strongest kind of evidence: an online A/B test at industrial scale.  
Not higher because: The core fix is a single aggregation technique whose generality beyond this feature-heterogeneity regime, and the durability of gains as scale grows further, are only partially established outside the authors' own stack.  
Organisation evidence: Renmin University of China via email_domain (org score 3.0, boost 0.135)

**13. From Generation to Discovery: Diffusion Mutation Kernels for Circuit and Physical Design** (id 176515, final 7.6)  
So what: This reframes diffusion models as learned mutation operators for design discovery rather than samplers, with formally verified results — prefix adders beating Kogge-Stone on delay and area under placed-and-timed flows, and novel amplifier topologies confirmed by re-simulation. Teams doing EDA or analog design exploration should treat learned transition kernels plus external verification as a credible alternative to pure generative sampling.  
Not higher because: The results are strong but confined to three electronic design spaces with rigorous external evaluators; generalization to domains lacking cheap, reliable simulation or formal checking remains untested.  
Organisation evidence: — via none (org score 0.0, boost 0.0)

**14. InfraOcc: An Infrastructure Occupancy Benchmark with Static-to-Dynamic Reasoning** (id 134715, final 7.6)  
So what: —  
Not higher because: —  
Organisation evidence: Nanyang Technological University via email_domain (org score 3.0, boost 0.135)

**15. Scaling Graph Neural Networks for Friend Recommendation: Multi-Hash User Embeddings and Temporal Neighbor Sampling** (id 123365, final 7.6)  
So what: —  
Not higher because: —  
Organisation evidence: — via none (org score 0.0, boost 0.0)

**16. The Framing Gap: Indirect Prompt-Injection Exfiltration Defeats Surface-Level Defenses in Tool-Using Agents** (id 175945, final 7.6)  
So what: For agent architectures handling secrets, the actionable takeaway is to enforce destination allow-lists and split planning from content reading rather than relying on the model to refuse injections — policy clauses and prompt-level defenses demonstrably fail under cheap reframing. Security teams should also assume attackers will reuse known templates with swapped payloads, so defenses must be payload-blind.  
Not higher because: The evidence comes from a synthetic lab with canary secrets and mock tools, so transfer to production agent environments with real destinations and adversarial pressure remains unvalidated.  
Organisation evidence: Gyeongsang National University via explicit_paper_affiliation (org score 3.0, boost 0.1275)

**17. EVOMAL: Self-Poisoning in Self-Evolving Coding Agents** (id 122591, final 7.6)  
So what: —  
Not higher because: —  
Organisation evidence: Queen's University via email_domain (org score 3.0, boost 0.135)

**18. CogEvol: Towards Efficient and Reliable Learning Environment Generation** (id 136790, final 7.6)  
So what: If you ship AI-generated courseware, CogEvol shows single-pass specialized models can replace multi-turn agent scaffolding at production latency and cost, with reliability engineered through failure-derived training data and a hardened reward. The 4B Apache-2.0 release plus ~76% scaffold-editing savings make this a practical build-vs-buy baseline for education pipelines.  
Not higher because: Evidence is strongest for slide and interactive-HTML generation within one vendor's production domain, so generality to other artifact types and independently verified quality beyond the 500-case benchmark remains unproven.  
Organisation evidence: Tsinghua University via explicit_paper_affiliation (org score 6.0, boost 0.255)

**19. Sequential knowledge editing breaks a model's ability to tell good evidence from bad, without costing it accuracy** (id 203295, final 7.6)  
So what: Knowledge editing can silently degrade a model's ability to arbitrate between its own memory and retrieved evidence while leaving standard benchmarks and locality checks untouched, so teams deploying sequential edits should add arbitration and selective-prediction probes to their eval suite. The secondary collapse finding — edit success at 1.00 with MMLU at chance under published hyperparameters — argues for capability monitoring in any production editing pipeline.  
Not higher because: The evidence is strong but confined to 7B-scale instruction models, LoRA/MEMIT-style editors, and simulated injected passages with a frozen retriever, leaving open how the effect transfers to larger models, other editing families, and live retrieval stacks.  
Organisation evidence: — via none (org score 0.0, boost 0.0)

**20. ACE: A Self-Correcting Agentic Canvas Editor for Multi-Slide Presentation Automation** (id 121741, final 7.6)  
So what: —  
Not higher because: —  
Organisation evidence: Seoul National University via explicit_paper_affiliation (org score 3.0, boost 0.1275)


## 5. Organisation leaderboard

Organisation score is derived from verified affiliation evidence (paper affiliation, email domain, ROR, OpenAlex) and applied only after scoring.

| Organisation | On watchlist | Priority | Papers | Avg org score | Best final |
|---|---|---|---|---|---|
| Tsinghua University | yes | 6 | 64 | 6.00 | 7.6 |
| Zhejiang University | no | 0 | 31 | 3.00 | 7.3 |
| Shanghai Jiao Tong University | no | 0 | 31 | 3.00 | 7.1 |
| Seoul National University | no | 0 | 22 | 3.00 | 7.6 |
| Peking University | no | 0 | 21 | 3.00 | 7.4 |
| Beihang University | no | 0 | 21 | 3.00 | 7.3 |
| Nanyang Technological University | no | 0 | 20 | 3.00 | 7.6 |
| Stanford University | yes | 8 | 20 | 6.00 | 7.4 |
| Carnegie Mellon University | yes | 6 | 20 | 6.00 | 7.2 |
| Alibaba Group (China) | no | 0 | 18 | 3.00 | 6.9 |
| Massachusetts Institute of Technology | yes | 8 | 17 | 6.00 | 7.2 |
| Korea Advanced Institute of Science and Technology | no | 0 | 17 | 3.00 | 7.0 |
| Amazon | yes | 10 | 16 | 6.00 | 7.6 |
| Fudan University | no | 0 | 16 | 3.00 | 6.8 |
| Technical University of Munich | no | 0 | 15 | 3.00 | 6.8 |
| The Hong Kong University of Science and Technology (Guangzhou) | no | 0 | 14 | 3.00 | 7.3 |
| Northeastern University | no | 0 | 12 | 3.00 | 7.1 |
| Huazhong University of Science and Technology | no | 0 | 12 | 3.00 | 7.0 |
| Hong Kong University of Science and Technology | no | 0 | 12 | 3.00 | 6.9 |
| Korea University of Science and Technology | no | 0 | 12 | 3.00 | 6.9 |
| University of California, Berkeley | yes | 8 | 11 | 6.00 | 7.4 |
| University of Southern California | no | 0 | 11 | 3.00 | 7.2 |
| University of Oxford | no | 0 | 11 | 3.00 | 7.2 |
| University of Hong Kong | no | 0 | 11 | 3.00 | 7.0 |
| New York University | no | 0 | 11 | 3.00 | 7.0 |


## 6. Domain distribution

| Domain | Papers | Avg quality |
|---|---|---|
| natural_language_processing | 530 | 6.87 |
| evaluation_benchmarking | 334 | 6.99 |
| computer_vision | 322 | 6.86 |
| multimodal_learning | 191 | 6.94 |
| alignment_safety | 181 | 7.15 |
| theory_foundations | 154 | 6.48 |
| robotics_embodied | 150 | 7.01 |
| generative_models | 97 | 7.00 |
| systems_infrastructure | 94 | 6.94 |
| reinforcement_learning | 92 | 6.77 |
| efficient_inference | 88 | 7.13 |
| interpretability | 77 | 6.68 |
| speech_audio | 66 | 6.88 |
| graph_learning | 64 | 6.83 |
| model_compression | 64 | 6.98 |


## 7. Data quality

| Check | Count |
|---|---|
| Papers in current state | 2600 |
| Affiliation resolved | 1825 |
| Affiliation evidence present but ambiguous | 354 |
| No affiliation evidence supplied | 421 |
| Screen/quality disagreement ≥ 3.0 | 9 |
| quality_status=stale_content | 0 |


Unresolved affiliations are reported, not hidden: unknown beats wrong, and every raw affiliation string is preserved for re-resolution.
