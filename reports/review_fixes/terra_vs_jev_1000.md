# Terra vs Jev — 1000-paper human judgement set

**N:** 1000  
**Jev model:** `typesafe/jev-1.13`  
**Jev policy:** `quality_v001` (chosen because it beat quality_v002 on Terra/Sol Spearman; v002 raised confidence≥0.9 but lowered rank agreement)  
**Jev source:** `reports/review_fixes/jev_j1b_quality_scores.json`  
**CSV:** `reports/review_fixes/terra_vs_jev_1000.csv`

## Editorial picks — ranks in this set

| paper_id | role | title | terra_rank | jev_rank | terra_pct | jev_pct |
|---:|---|---|---:|---:|---:|---:|
| 42672 | runner_up | Alignment Whack-a-Mole : Finetuning Activates Verbatim Recal | 13 | 129 | 98.8% | 87.2% |
| 184890 | winner | MOLE: Detecting Insider Threats in AI Agents | 56 | 32 | 94.5% | 96.9% |
| 143079 | runner_up | Don't Drop Dropout: Optimizing Layer Sparsity for Efficient  | 339 | 172 | 66.2% | 82.9% |

- Mean Terra rank: **136.0** (mean pctile 86.5%)
- Mean Jev rank: **111.0** (mean pctile 89.0%)

## 20 largest |rank_gap| disagreements

| |rank_gap| | terra_rank | jev_rank | terra_Q | jev_Q | title |
|---:|---:|---:|---:|---:|---|
| 913 | 66 | 979 | 8.20 | 4.86 | GVPO++: Group Variance Policy Optimization for LLM Post-Training and O |
| 882 | 40 | 922 | 8.34 | 5.33 | Predicting magnetism with first-principles AI |
| 776 | 134 | 910 | 8.08 | 5.38 | Learning in Structured Stackelberg Games |
| 746 | 188 | 934 | 8.00 | 5.24 | gwBenchmarks: Stress-Testing LLM Agents on High-Precision Gravitationa |
| 741 | 802 | 61 | 7.12 | 7.29 | AquaOrbit: Sim-to-Real Reinforcement Learning for Underwater Target Or |
| 734 | 12 | 746 | 8.60 | 5.88 | Machine-Interpretable Information: Compiling Documents into Searchable |
| 722 | 957 | 235 | 6.60 | 6.81 | Graph Memory for LLM Agents: At What Cost? A Comparative Evaluation of |
| 720 | 183 | 903 | 8.00 | 5.39 | Beyond PINNs: A Unified Gauss--Newton and Petrov--Galerkin Framework f |
| 709 | 127 | 836 | 8.08 | 5.64 | LMEnt: A Suite for Analyzing Knowledge in Language Models from Pretrai |
| 709 | 207 | 916 | 7.98 | 5.35 | Origin Is All You Need: Provenance-Aware Transformers for Structural T |
| 699 | 152 | 851 | 8.04 | 5.61 | How Model Growth, Recursion, and Boundary Operators Influence Scaling  |
| 683 | 766 | 83 | 7.18 | 7.20 | From Rollout to Reset: A Graph-Based Harness for Autonomous Long-Horiz |
| 679 | 838 | 159 | 7.02 | 6.97 | Conservation Buys Stability and Factoring Buys Counterfactuals in Phys |
| 670 | 189 | 859 | 8.00 | 5.59 | LIGE-GR: A Smooth Leap from Ranking to Generative Recommendation in th |
| 663 | 292 | 955 | 7.82 | 5.11 | Reinforcement Learning under State and Outcome Uncertainty: A Foundati |
| 661 | 784 | 123 | 7.16 | 7.05 | MM-ContextFold: Context Folding for Multimodal Agentic Retrieval |
| 645 | 27 | 672 | 8.46 | 6.01 | Extending concurrent separation logic to the hardware level to verify  |
| 642 | 117 | 759 | 8.10 | 5.85 | Fast and Robust Temporal Logic Planning via ADMM-based Trajectory Opti |
| 641 | 111 | 752 | 8.10 | 5.86 | A Unified Framework for Wasserstein Convergence of ULMC Methods beyond |
| 630 | 113 | 743 | 8.10 | 5.88 | CORDS: Continuous Representations of Discrete Structures |
