# HTML vs OpenAlex affiliations — Sep 1–15 2026

**Generated:** 2026-09-21T07:46:59.417429+00:00  
**Window:** 2026-09-01 → 2026-09-15 inclusive  
**Scope:** PI `paper_author_affiliations` only

Twin: `september_01_15_html_vs_openalex_affiliations.json`

---

## Coverage

| Set | Papers |
|---|---:|
| Window PI papers | 12149 |
| With HTML affiliation evidence | 5448 |
| With OpenAlex affiliation evidence | 128 |
| **Both HTML and OpenAlex** | **45** |
| HTML only | 5403 |
| OpenAlex only | 83 |

OpenAlex is rarely present alongside HTML because DEEP mode calls OpenAlex only when the paper is still unresolved after HTML/ROR.

---

## Agreement (papers with both + resolved orgs)

| Metric | Value |
|---|---:|
| Comparable papers | 12 |
| Exact same org set | 6 (50.0%) |
| Partial overlap | 4 |
| Disjoint (no shared org) | 2 |
| Any overlap | 83.3% |

### Author-level (same paper_author with both evidence types)

| Metric | Value |
|---|---:|
| Author pairs | 74 |
| Exact org-id set match | 22 (29.7%) |
| Any org overlap | 37 (50.0%) |
| No overlap | 37 |

---

## Paper-level disagreements (non-exact)

- `2510.20721` (partial): HTML=['Carnegie Mellon University'] · OA=['Carnegie Mellon University', 'Fujitsu (China)', 'Fujitsu (Japan)', 'Fujitsu (United States)'] — User Perceptions vs. Proxy LLM Judges: Privacy and Helpfulness in LLM 
- `2604.24622` (partial): HTML=['Southern University of Science and Technology', 'Tsinghua University', 'University of Chinese Academy of Sciences'] · OA=['Nova Management (United States)', 'Southern University of Science and Technology', 'University of Science and Technology of China', "Xi'an Jiaotong University"] — CF-VLA: Efficient Coarse-to-Fine Action Generation for Vision-Language
- `2509.06285` (partial): HTML=['Hong Kong University of Science and Technology', 'University of Science and Technology Beijing'] · OA=['Aerospace Institute (Germany)', 'Hong Kong University of Science and Technology', 'National University of Defense Technology', 'University of Science and Technology Beijing', 'University of Toronto'] — DCReg: Decoupled Characterization for Efficient Degenerate LiDAR Regis
- `2609.11486` (partial): HTML=['Lomonosov Moscow State University'] · OA=['Lomonosov Moscow State University', 'Moscow State University'] — FreeFlow: A Bias-free Hierarchical Transformer for Optical Flow Estima
- `2601.10511` (disjoint): HTML=['National Security Authority'] · OA=['National Security Agency', 'University of Maryland, College Park'] — Scalable Algorithms for Approximate DNF Model Counting
- `2603.02790` (disjoint): HTML=['University of Amsterdam'] · OA=['Clinical Research Consortium'] — Designing UNICORN: a Unified Benchmark for Imaging in Computational Pa

---

## Author-level disagreement samples

- `2408.10608` / Jing Pan: HTML `None` ← `Ling Chen` · OA `Monash University` ← `Monash University`
- `2408.10608` / Jing Pan: HTML `None` ← `Ling Chen` · OA `Australian Regenerative Medicine Institute` ← `Australian Regenerative Medicine Institute`
- `2408.10608` / Ling Chen: HTML `None` ← `Ling Chen` · OA `University of Technology Sydney` ← `University of Technology Sydney`
- `2408.10608` / Xiaoyu Tan: HTML `None` ← `Ling Chen` · OA `National University of Singapore` ← `National University of Singapore`
- `2408.10608` / Xihe Qiu: HTML `None` ← `Ling Chen` · OA `National University of Singapore` ← `National University of Singapore`
- `2408.10608` / Yongxin Deng: HTML `None` ← `Ling Chen` · OA `University of Technology Sydney` ← `University of Technology Sydney`
- `2408.10608` / Zhen Fang: HTML `None` ← `Ling Chen` · OA `University of Technology Sydney` ← `University of Technology Sydney`
- `2410.10136` / Cosimo Spera: HTML `None` ← `Minerva CQ, Sunnyvale, California, USA` · OA `Sunnyvale Public Library` ← `Sunnyvale Public Library`
- `2410.10136` / Garima Agrawal: HTML `None` ← `Minerva CQ, Sunnyvale, California, USA` · OA `Sunnyvale Public Library` ← `Sunnyvale Public Library`
- `2410.10136` / Sashank Gummuluri: HTML `None` ← `Minerva CQ, Sunnyvale, California, USA` · OA `Sunnyvale Public Library` ← `Sunnyvale Public Library`
- `2504.00285` / Benjamin K. Bergen: HTML `None` ← `Department of Cognitive Science` · OA `University of California San Diego` ← `University of California, San Diego`
- `2504.00285` / Samuel M. Taylor: HTML `None` ← `Department of Cognitive Science` · OA `University of California San Diego` ← `University of California, San Diego`
- `2509.06285` / Jin Wu: HTML `Hong Kong University of Science and Technology` ← `Hong Kong University of Science and Technology` · OA `University of Science and Technology Beijing` ← `University of Science and Technology Beijing`
- `2509.06285` / Jin Wu: HTML `Hong Kong University of Science and Technology` ← `Hong Kong University of Science and Technology` · OA `University of Science and Technology Beijing` ← `University of Science and Technology Beijing`
- `2509.06285` / Mingkai Jia: HTML `University of Science and Technology Beijing` ← `University of Science and Technology Beijing` · OA `Hong Kong University of Science and Technology` ← `Hong Kong University of Science and Technology`
- `2509.06285` / Ping Tan: HTML `University of Science and Technology Beijing` ← `University of Science and Technology Beijing` · OA `Hong Kong University of Science and Technology` ← `Hong Kong University of Science and Technology`
- `2509.06285` / Steven L. Waslander: HTML `Hong Kong University of Science and Technology` ← `Hong Kong University of Science and Technology` · OA `Aerospace Institute (Germany)` ← `Aerospace Institute (Germany)`
- `2509.06285` / Steven L. Waslander: HTML `University of Science and Technology Beijing` ← `University of Science and Technology Beijing` · OA `University of Toronto` ← `University of Toronto`
- `2509.06285` / Steven L. Waslander: HTML `Hong Kong University of Science and Technology` ← `Hong Kong University of Science and Technology` · OA `University of Toronto` ← `University of Toronto`
- `2509.06285` / Steven L. Waslander: HTML `University of Science and Technology Beijing` ← `University of Science and Technology Beijing` · OA `Aerospace Institute (Germany)` ← `Aerospace Institute (Germany)`
- `2509.06285` / Steven L. Waslander: HTML `Hong Kong University of Science and Technology` ← `Hong Kong University of Science and Technology` · OA `University of Toronto` ← `University of Toronto`
- `2509.06285` / Steven L. Waslander: HTML `Hong Kong University of Science and Technology` ← `Hong Kong University of Science and Technology` · OA `Aerospace Institute (Germany)` ← `Aerospace Institute (Germany)`
- `2509.06285` / Xiangcheng Hu: HTML `University of Science and Technology Beijing` ← `University of Science and Technology Beijing` · OA `Hong Kong University of Science and Technology` ← `Hong Kong University of Science and Technology`
- `2509.06285` / Xiangcheng Hu: HTML `University of Science and Technology Beijing` ← `University of Science and Technology Beijing` · OA `Hong Kong University of Science and Technology` ← `Hong Kong University of Science and Technology`
- `2509.06285` / Xieyuanli Chen: HTML `Hong Kong University of Science and Technology` ← `Hong Kong University of Science and Technology` · OA `National University of Defense Technology` ← `National University of Defense Technology`
- … +15 more in JSON

---

## Exact-match examples

- `2504.00285`: ['University of California San Diego'] — When Do Large Language Models Exhibit Unsolicited Deception?
- `2601.03163`: ['Masaryk Memorial Cancer Institute', 'Masaryk University'] — LSP-DETR: Efficient and Scalable Nuclei Segmentation in Whol
- `2602.14048`: ['Peking University'] — ProAct: Harnessing Streaming Motion Generation and Agentic R
- `2603.22437`: ['Cornell Tech', 'Cornell University'] — mmFHE: mmWave Sensing with End-to-End Fully Homomorphic Encr
- `2605.16879`: ['Sichuan University'] — Towards Generalized Image Manipulation Localization via Scor
- `2609.09002`: ['Polytechnique Montréal'] — Factorized and Vectorized Execution: Optimizing Analytical a

---

## Takeaway

For Sep 1–15, HTML and OpenAlex affiliations are **usually not co-present**. Where both resolve organisations, they **often overlap (~83.3%)** but are **exact matches only about half the time (~50.0%)**. Treat them as complementary evidence tiers, not identical sources.
