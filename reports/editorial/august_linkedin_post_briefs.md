# August 2026 LinkedIn post briefs

Do not publish/schedule from this file. Claims stay within paper evidence.

---

## Post 1 — Friday — TECH

**Paper:** A JoLT for the KV cache: Near-lossless KV cache compression via joint Lagrangian allocation of Tucker ranks and a rotated residual for llms  
**arXiv:** 2607.12550 · https://arxiv.org/abs/2607.12550

**Hook:**  
Your long-context LLM bill is climbing, but is the model itself the bottleneck? For many serving stacks, memory and throughput collapse because the KV cache grows with context—not because the weights got bigger.

**Core insight:**  
This paper argues the KV cache becomes the dominant memory cost of transformer inference at long context and proposes JoLT: near-lossless compression via joint Lagrangian allocation of Tucker ranks plus a rotated residual. Reported results claim roughly 2–3× KV-cache compression with limited quality loss on the evaluated settings.

**Why it matters:**  
Engineering leaders planning long-context products should treat cache/memory strategy as a first-class capacity decision alongside model choice and quantization.

**Practical action:**  
Pick one real long-context workload; measure peak KV memory and tokens/sec today; evaluate a KV-cache compression approach (or vendor equivalent) under the same latency SLO before the next capacity buy.

**Caveat:**  
Validation is described on two model families and selected tasks; end-to-end wins still depend on kernels, runtime overhead, hardware, and longer contexts.

**Suggested closing question:**  
If your KV cache—not your weights—set the ceiling, what would you change in next quarter’s inference roadmap?

---

## Post 2 — Next Tuesday — PRODUCT

**Paper:** Training Proactive and Personalized LLM Agents  
**arXiv:** 2511.02208 · https://arxiv.org/abs/2511.02208

**Hook:**  
Most “AI agents” in demos are optimized to finish a task alone. Real users need collaborators that ask the right questions and adapt to how people actually work.

**Core insight:**  
The authors argue for training agents across productivity, proactivity, and personalization—not isolated task completion—and propose methods to make agents ask useful questions and adapt to individual preferences. The product claim is a paradigm shift in what “good” means for agent systems.

**Why it matters:**  
Product leaders shipping agent features should stop accepting solo task-success as the only north-star metric if the intended experience is collaboration.

**Practical action:**  
For one agent workflow, add rubric dimensions for question usefulness and preference adaptation; score 10–20 real traces; decide whether the roadmap needs explicit training/eval investment beyond task completion.

**Caveat:**  
The approach relies on LLM user simulation and multi-objective rewards; simulator bias and generalization to diverse real users remain open.

**Suggested closing question:**  
If your agent never asks a clarifying question, is it a collaborator—or just a faster autocomplete?
