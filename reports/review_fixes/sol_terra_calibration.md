# Sol vs Terra quality calibration

Window: 2026-09-01 → 2026-09-15
Sample: 60 papers
Dry-run Terra cost: ~$0.5653

Run id: `a4071bf8-db07-4e98-b5c0-08fa45afe681`
Actual cost: $0.1994
Spearman(final_score): 0.8064704610267392
Top-15 overlap: 6/15
Mean |Δ final|: 0.791

## Mean |Δ| by rubric dimension

- `technical_significance`: 0.7
- `apparent_novelty`: 0.6833
- `practical_applicability`: 0.6
- `professional_value`: 0.7167
- `learning_value`: 0.5083
- `evidence_strength`: 0.7917

## Biggest disagreements

- id 98681 |Δ|=1.7112000000000007: Sol 5.7152 vs Terra 4.004 — LEXIC: Lightweight On-Device Decoding of Reading Comprehension from Eye Movement
  - Sol so_what: LEXIC shows that reading-comprehension signals can be extracted from eye movements with a tiny, fast model suitable for private on-device adaptive-reading systems.
  - Terra so_what: LEXIC shows that reading-comprehension prediction from eye movements can be implemented with extremely small, fast models suitable for local devices.
- id 138187 |Δ|=1.6575999999999995: Sol 8.6136 vs Terra 6.956 — MINERVA: How Small Can a Manipulation Policy Be and Still Solve LIBERO?
  - Sol so_what: It shows that standard LIBERO tasks can be solved by sub-million-parameter, CPU-deployable policies while exposing memorization and robustness limitations hidden by headline benchmark scores.
  - Terra so_what: It shows that strong LIBERO results can be achieved with extremely small, fast policies, while also exposing that the benchmark may reward task memorization rather than robust language-conditioned manipulation.
- id 40589 |Δ|=1.4566: Sol 8.366 vs Terra 6.9094 — MARCUS: An agentic, multimodal vision-language model for cardiac diagnosis and m
  - Sol so_what: A unified, interactive system that interprets ECG, echocardiography, and CMR together could improve cardiac diagnostic workflows where clinicians must integrate heterogeneous tests at scale.
  - Terra so_what: A genuinely multimodal, interactive cardiac AI system could reduce fragmentation across ECG, echo, and CMR interpretation while supporting more coherent diagnostic reasoning.
- id 184994 |Δ|=1.4179999999999993: Sol 8.633 vs Terra 7.215 — The Oversight Gap: What LLM Safety Monitors Miss, and Why It Is Not Capability
  - Sol so_what: It reframes important monitoring failures as information-and-procedure limits, providing formal detectability bounds and concrete guidance for building valid safety oversight and benchmarks.
  - Terra so_what: It reframes the limits of LLM safety monitoring for relational behaviors as measurable information and procedure gaps, rather than simply deficiencies in model capability.
- id 191527 |Δ|=1.1747999999999994: Sol 8.5748 vs Terra 7.4 — The BatchNorm Illusion: Diagnosing Normalization Artifacts in Machine Unlearning
  - Sol so_what: It exposes a large, easily triggered BatchNorm artifact that can invalidate machine-unlearning conclusions and supplies a principled way to separate measurement effects from information retained in model weights.
  - Terra so_what: It identifies and isolates a serious BatchNorm-state confound that can make machine-unlearning results appear substantially better or worse than the underlying weight-level forgetting.
- id 191803 |Δ|=1.1721000000000004: Sol 8.6523 vs Terra 7.4802 — 4D Parallelism Unlocks Exascale Bayesian Neural Networks for High-Fidelity Atmos
  - Sol so_what: BEAST combines scalable Bayesian deep learning with global high-resolution forecasting, making large-ensemble uncertainty quantification and extreme-event prediction feasible at unprecedented computational scale.
  - Terra so_what: It demonstrates a path to train and run high-resolution Bayesian atmospheric models with scalable uncertainty quantification at exascale, including faster ensemble forecasts for extreme-event prediction.
- id 185148 |Δ|=1.1150000000000002: Sol 8.404 vs Terra 7.289 — KTO: Model Alignment as Prospect Theoretic Optimization
  - Sol so_what: KTO offers a simpler alignment route using binary desirable/undesirable feedback rather than paired preferences, potentially reducing the cost and complexity of preference optimization.
  - Terra so_what: Provides a preference-data-light alignment objective grounded in a formal model of human loss aversion, potentially making alignment training cheaper and more adaptable.
- id 194708 |Δ|=1.1106000000000007: Sol 8.5554 vs Terra 7.4448 — Illusion of Depth: Revealing Hidden Stereo Vision Vulnerabilities in Depth Estim
  - Sol so_what: Simple physical patterns can dangerously manipulate stereo depth across classical, learned, fused, and commercial systems, exposing a concrete safety risk for autonomous vehicles and robots while motivating a targeted defense.
  - Terra so_what: The work identifies a physically realizable attack surface in stereo depth sensing that can directly affect braking and obstacle-response behavior in autonomous systems.
- id 142692 |Δ|=1.1067: Sol 8.4231 vs Terra 7.3164 — Repeat-After-Me: Black-Box Adaptive Visual Prompt Injection
  - Sol so_what: The attack demonstrates that untrusted images can induce consequential tool calls and persistent agent compromise even when textual injection fails, exposing an urgent multimodal security boundary.
  - Terra so_what: Demonstrates that visually embedded, black-box prompt injections can induce serious unauthorized agent actions, making multimodal input handling an urgent AI-agent security problem.
- id 106054 |Δ|=1.079600000000001: Sol 8.7688 vs Terra 7.6892 — The Intruder Threshold: A Spectral Law for LoRA Fine-Tuning
  - Sol so_what: A parameter-free spectral threshold could predict which LoRA updates create harmful new directions and enable safer adapter tuning without validation sweeps.
  - Terra so_what: Provides a measurable, layer-level rule for anticipating and mitigating a specific source of LoRA-induced catastrophic forgetting without costly validation sweeps.
