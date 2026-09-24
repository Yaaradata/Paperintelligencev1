# PaperIntelligence v1 — Run Report

**Window:** 2026-09-21 → 2026-09-23 (published_at)  
**Generated:** 2026-09-24 09:55 UTC  
**Pipeline:** relevance (free) → normalize_authors (free) → screen → classify → quality → affiliation → adjudication

## 1. Funnel

| Step | Papers |
|---|---|
| arXiv ingested in window | 2454 |
| Rejected by relevance (free, pre-LLM) | 893 |
| Entered paid stages | 1561 |
| Passed screen gate | 456 |
| Failed screen gate (scores kept) | 22 |
| Quality scored | 0 |
| Quality pending | 456 |
| Quality failed | 0 |
| Stale content (hash mismatch) | 0 |

Relevance runs first precisely so the paid stages never see the rejected papers.

**Quality models in scored pool:** (none)

## 2. Stage coverage

| Task type | Papers | Result rows |
|---|---|---|
| screen | 478 | 956 |
| quality | 290 | 316 |
| application_domain | 231 | 231 |
| audience | 231 | 231 |
| domain | 231 | 231 |
| subdomain | 231 | 231 |


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
| quality | v001 | running | 456 | 0 | 0 |  |
| quality | v001 | succeeded | 200 | 200 | 0 | 1940.0 |
| hf_signals | v001 | succeeded | 0 | 48 | 0 | 11.3 |
| adjudication | v001 | succeeded | 0 | 478 | 0 | 0.5 |
| relevance | v001 | succeeded | 0 | 1083 | 0 | 7.6 |


## 3. Cost

| Model | Stage | Calls | Input tokens | Output tokens | Cost (USD) |
|---|---|---|---|---|---|
| openai/gpt-5.6-terra | quality | 336 | 689492 | 293252 | $4.8980 |
| openai/gpt-5.6-sol | quality | 379 | 800434 | 378606 | $4.7866 |
| z-ai/glm-5.3-flash | screen | 734 | 3687359 | 1041134 | $1.0737 |
| z-ai/glm-5.3-flash | classify | 291 | 1680437 | 955053 | $0.7296 |
| z-ai/glm-5.3-flash | audience_domain | 50 | 287476 | 256569 | $0.1714 |
| z-ai/glm-5.3-flash | quality_prose | 130 | 276714 | 160502 | $0.1218 |
| z-ai/glm-4.6 | affiliation_judge | 68 | 64739 | 62596 | $0.0410 |

**Total LLM spend:** $11.8221

| External provider | Requests | Cache hits | Failures |
|---|---|---|---|
| openalex | 29600 | 24243 | 1500 |
| arxiv | 20043 | 3655 | 1062 |
| ror | 7561 | 3190 | 0 |
| openrouter | 2510 | 0 | 522 |
| huggingface | 1174 | 438 | 7 |


## 4. Top 20 papers by final score

Final score = blinded quality composite × evidence factor + organisation boost (capped at 0.5). The quality model never saw authors or affiliations.

_no rows_


### Why these papers


## 5. Organisation leaderboard

Organisation score is derived from verified affiliation evidence (paper affiliation, email domain, ROR, OpenAlex) and applied only after scoring.

| Organisation | On watchlist | Priority | Papers | Avg org score | Best final |
|---|---|---|---|---|---|
| Tsinghua University | yes | 6 | 12 | 6.00 |  |
| Carnegie Mellon University | yes | 6 | 9 | 6.00 |  |
| Shanghai Jiao Tong University | no | 0 | 7 | 3.00 |  |
| University of Illinois Urbana-Champaign | no | 0 | 6 | 3.00 |  |
| Columbia University | no | 0 | 5 | 3.00 |  |
| New York University | no | 0 | 5 | 3.00 |  |
| Northeastern University | no | 0 | 5 | 3.00 |  |
| Korea University | no | 0 | 5 | 3.00 |  |
| Stanford University | yes | 8 | 5 | 6.00 |  |
| University of California, Berkeley | yes | 8 | 4 | 6.00 |  |
| The University of Tokyo | no | 0 | 4 | 3.00 |  |
| The Hong Kong University of Science and Technology (Guangzhou) | no | 0 | 4 | 3.00 |  |
| Hong Kong University of Science and Technology | no | 0 | 4 | 3.00 |  |
| Chinese University of Hong Kong | no | 0 | 4 | 3.00 |  |
| East China Normal University | no | 0 | 4 | 3.00 |  |
| Zhejiang University | no | 0 | 4 | 3.00 |  |
| Cornell University | no | 0 | 4 | 3.00 |  |
| Johns Hopkins University | no | 0 | 3 | 3.00 |  |
| Karlsruhe Institute of Technology | no | 0 | 3 | 3.00 |  |
| University of Chicago | no | 0 | 3 | 3.00 |  |
| NVIDIA | yes | 10 | 3 | 6.00 |  |
| Peking University | no | 0 | 3 | 3.00 |  |
| Fudan University | no | 0 | 3 | 3.00 |  |
| Mila - Quebec Artificial Intelligence Institute | yes | 6 | 3 | 6.00 |  |
| Massachusetts Institute of Technology | yes | 8 | 3 | 6.00 |  |


## 6. Domain distribution

| Domain | Papers | Avg quality |
|---|---|---|
| natural_language_processing | 33 |  |
| computer_vision | 31 |  |
| robotics_embodied | 27 |  |
| evaluation_benchmarking | 23 |  |
| theory_foundations | 22 |  |
| multimodal_learning | 16 |  |
| speech_audio | 15 |  |
| reinforcement_learning | 13 |  |
| alignment_safety | 12 |  |
| generative_models | 12 |  |
| interpretability | 8 |  |
| efficient_inference | 7 |  |
| model_compression | 4 |  |
| graph_learning | 4 |  |
| systems_infrastructure | 4 |  |


## 7. Data quality

| Check | Count |
|---|---|
| Papers in current state | 478 |
| Affiliation resolved | 318 |
| Affiliation evidence present but ambiguous | 88 |
| No affiliation evidence supplied | 72 |
| Screen/quality disagreement ≥ 3.0 | 0 |
| quality_status=stale_content | 0 |


Unresolved affiliations are reported, not hidden: unknown beats wrong, and every raw affiliation string is preserved for re-resolution.
