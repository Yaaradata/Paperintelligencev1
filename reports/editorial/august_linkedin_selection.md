# August 2026 LinkedIn selection

Hard exclusion: newsletter winners `[172395, 2184]`.

## LinkedIn TECH
### Winner
- **A JoLT for the KV cache: Near-lossless KV cache compression via joint Lagrangian allocation of Tucker ranks and a rotated residual for llms**
- ID `3611` · arXiv `2607.12550` · [link](https://arxiv.org/abs/2607.12550)
- Scores: quality `8.5`, final `8.1` (tie-break only)
- Orgs (context): n/a
- **Why:** Makes the KV cache—not model weights—the throughput ceiling for long-context inference, and offers a near-lossless compression path leaders can evaluate against capacity plans.
- **Decision:** Whether long-context serving investments should prioritize KV-cache compression/memory strategy alongside model choice.
- **Action:** Benchmark one production long-context workload’s memory/throughput with and without a KV-cache compression candidate (or vendor equivalent); decide if cache strategy is now a capacity lever.
- **Talking point:** At long context, the KV cache—not the weights—often sets the inference throughput ceiling.
- **Caveat:** Validated on two model families/selected tasks; real impact still depends on kernels, runtime overhead, hardware, and longer contexts.

### Runner-up
- **Decomposition Attacks Across Unlinkable Identities: Limits of Stateful Defenses for LLM Services**
- ID `120560` · arXiv `2608.17445` · [link](https://arxiv.org/abs/2608.17445)
- Scores: quality `8.7`, final `8.3` (tie-break only)
- Orgs (context): n/a
- **Why:** Shows stateful request monitoring alone cannot stop decomposed harmful tasks when attackers rotate identities—useful security debate for LLM service owners.
- **Decision:** Whether identity-rotating decomposition is in scope for the LLM abuse-defense roadmap.
- **Action:** Threat-model one production LLM API for decomposition + identity rotation; list controls beyond per-request stateful grouping that would be required.
- **Talking point:** Stateful monitors that only group by identity can fail when attackers unlink and learn from blocks.
- **Caveat:** Formal/empirical scope is bounded; real services may have economic or side-channel controls outside the studied model.


## LinkedIn PRODUCT
### Winner
- **Training Proactive and Personalized LLM Agents**
- ID `120294` · arXiv `2511.02208` · [link](https://arxiv.org/abs/2511.02208)
- Scores: quality `8.4`, final `8.2` (tie-break only)
- Orgs (context): Carnegie Mellon University
- **Why:** Reframes agent products from isolated task completers to collaborators that ask useful questions and adapt to people—changing product requirements for “agent” features.
- **Decision:** Whether the agent roadmap optimizes only for solo task success, or also for proactive questioning and personalization as first-class product outcomes.
- **Action:** Define acceptance criteria for one agent workflow that include question quality and preference adaptation—not only task completion—then score the current agent against that rubric with 10–20 real user traces.
- **Talking point:** Most agents are trained to finish tasks alone; real collaborators need to ask and adapt.
- **Caveat:** Depends on LLM user simulation and multi-objective rewards; simulator bias and real-user generalization remain open.

### Runner-up
- **Grounded Normative Rule Generation with Structured Search**
- ID `3556` · arXiv `2608.22229` · [link](https://arxiv.org/abs/2608.22229)
- Scores: quality `7.8`, final `7.4` (tie-break only)
- Orgs (context): Peking University, University of Chinese Academy of Sciences
- **Why:** Argues institutional/workplace policies must be operationally verifiable against records, not merely fluent—useful for AI policy/compliance product design.
- **Decision:** Whether AI-drafted policies are accepted based on readability or checked for enforceability against available environment data.
- **Action:** Take one AI-drafted internal policy; attempt to map each clause to an auditable record/check; reject clauses that cannot be verified.
- **Talking point:** A policy that reads well but cannot be checked against real records is not operational.
- **Caveat:** Controlled formalism may miss complex legal contexts; benchmarks do not prove live compliance readiness.


## Cross-check
- LinkedIn winners ≠ newsletter winners: yes ([3611, 120294] vs [172395, 2184])
