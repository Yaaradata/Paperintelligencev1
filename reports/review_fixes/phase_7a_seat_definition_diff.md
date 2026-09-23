# Phase 7a — STOP: seat definition copies differ
Per brief item 1: if TECH/PRODUCT seat definition copies differ, STOP and show the diff.
## Sources compared
| Source | Location |
|---|---|
| A | `prompts/newsletter_select/v001.md` — `### Seat 1 — TECH` / `### Seat 2 — PRODUCT` |
| B | `scripts/select_newsletter.py` — `USER_RUBRIC` `<seat name="TECH|PRODUCT">` |
| C | `scripts/select_linkedin.py` — `USER_RUBRIC` (topic lists + shared philosophy; **no XML seat blocks**) |

## Verdict
**DIFFERS.** Do not extract a shared source yet.

### A vs B (newsletter prompt file vs newsletter script)
Both define TECH and PRODUCT seats, but wording, structure, and rejection criteria differ substantially.

#### TECH seat diff

```diff
--- newsletter_select/v001.md TECH
+++ select_newsletter.py TECH
@@ -1,14 +1,26 @@
-Who: senior engineering managers, directors, GMs, heads of AI/ML/platform.
-They own teams, budgets, and technical bets.
+Reader:
+Senior engineering managers, directors, GMs, heads of engineering, AI/ML,
+platform, architecture, or technical strategy.
 
-Pick the paper that best lets such a reader say one of:
-- "I can have my team try this on our stack this quarter and report back."
-- "This changes an architecture / eval / cost / safety bet I am about to make."
-- "I can use this to judge whether a vendor or internal claim is real."
+Strong candidates affect decisions involving:
+- architecture or technical design
+- evaluation
+- reliability or failure modes
+- security or safety
+- cost, latency, or performance
+- model/tool/vendor choice
+- engineering practices
+- whether a technical claim is credible
 
-Good signals: reproducible method or measurement, clear before/after, cost or
-latency or reliability implications, failure modes named, works at a scale a
-normal enterprise team can attempt.
+Prefer:
+- measurable evidence
+- reproducible or adaptable methods
+- useful comparisons
+- explicit limitations or failure modes
+- lessons transferable to an enterprise engineering environment
 
-Reject for this seat: pure theory with no implementable path, results that need
-frontier-lab-only compute, or a finding whose only action is "interesting".+A frontier-scale experiment may still qualify if its result changes a decision
+that a normal enterprise engineering organisation can make.
+
+Do not select a paper whose only value is theoretical novelty or a benchmark
+improvement with no meaningful engineering consequence.
```

#### PRODUCT seat diff

```diff
--- newsletter_select/v001.md PRODUCT
+++ select_newsletter.py PRODUCT
@@ -1,14 +1,24 @@
-Who: product leaders in a **business-and-process** role — product managers,
-product directors, heads of product, plus adjacent ops/risk owners.
+Reader:
+Senior product managers, product directors, heads of product, and adjacent
+business/process/risk leaders.
 
-Pick the paper that best lets such a reader say one of:
-- "This changes what we should build or how we should scope an AI feature."
-- "This tells me something real about user behaviour, trust, adoption, or risk."
-- "This affects go-to-market, pricing, compliance, or process design for AI."
+Strong candidates affect decisions involving:
+- what to build or not build
+- feature scope
+- workflow or process design
+- user behaviour, adoption, or trust
+- human-AI interaction
+- commercial model or pricing
+- governance, compliance, or risk
+- deployment or operating model
 
-Good signals: deployment or production evidence, user/human-factors findings,
-governance or compliance consequence, workflow redesign, measurable business
-outcome, market or sector applicability.
+Prefer:
+- user or deployment evidence
+- measurable behavioural or business outcomes
+- workflow implications
+- human factors
+- risks that alter product design
+- findings transferable beyond the exact experiment
 
-Reject for this seat: papers whose contribution is only a kernel, a training
-trick, or a benchmark number with no product or process consequence.+Do not select a paper merely because a product leader can understand it.
+It must change a plausible product, process, commercial, or governance decision.
```

### B vs C (newsletter script vs LinkedIn script)
LinkedIn does **not** embed the same XML `<seat>` blocks. It restates a shorter decision-value philosophy plus LinkedIn-specific topic prioritisation lists for TECH/PRODUCT. Not verbatim-equivalent to A or B.

#### LinkedIn USER_RUBRIC (full)

```
Use the SAME decision-value philosophy as the newsletter selection.

Governing question:
"What does this paper change for me, my team, my product, or my organisation?"

Select for DECISION VALUE, not prestige, novelty alone, or leaderboard gains.
Organisation prestige must NOT decide the winner.

Additionally apply a LinkedIn publishing lens.

A LinkedIn paper should have:
- one clear practical insight that can be explained without oversimplifying
- a decision or assumption professionals can debate
- enough evidence to support the claim
- a useful takeaway within the first few lines of a post
- relevance beyond a very narrow research niche
- a credible connection to day-to-day technical or product leadership

Avoid:
- papers requiring excessive academic background before the insight becomes useful
- papers whose main value is only benchmark improvement
- hype-driven results
- papers where the LinkedIn headline would require overstating the evidence

For TECH LinkedIn, prioritise topics such as:
- engineering practice
- architecture
- agents
- LLM evaluation
- reliability
- inference/cost/performance
- security
- deployment
- AI infrastructure

For PRODUCT LinkedIn, prioritise topics such as:
- human-AI interaction
- AI adoption
- workflow design
- trust
- governance
- user behaviour
- product operating model
- risk
- commercial/product decisions

Application gate:
There must be a credible 3–6 month decision, experiment, review, or operating
change for the intended reader. A test/review is enough; production rollout is not required.

Prefer also avoiding newsletter runner-ups when equally strong alternatives exist,
but that is not a hard rule.

For each LinkedIn seat also identify ONE runner-up.
Winner IDs must differ from BOTH newsletter winners.
```

## Side-by-side excerpts (TECH)
### A — newsletter_select/v001.md

```
Who: senior engineering managers, directors, GMs, heads of AI/ML/platform.
They own teams, budgets, and technical bets.

Pick the paper that best lets such a reader say one of:
- "I can have my team try this on our stack this quarter and report back."
- "This changes an architecture / eval / cost / safety bet I am about to make."
- "I can use this to judge whether a vendor or internal claim is real."

Good signals: reproducible method or measurement, clear before/after, cost or
latency or reliability implications, failure modes named, works at a scale a
normal enterprise team can attempt.

Reject for this seat: pure theory with no implementable path, results that need
frontier-lab-only compute, or a finding whose only action is "interesting".
```
### B — select_newsletter.py USER_RUBRIC

```
Reader:
Senior engineering managers, directors, GMs, heads of engineering, AI/ML,
platform, architecture, or technical strategy.

Strong candidates affect decisions involving:
- architecture or technical design
- evaluation
- reliability or failure modes
- security or safety
- cost, latency, or performance
- model/tool/vendor choice
- engineering practices
- whether a technical claim is credible

Prefer:
- measurable evidence
- reproducible or adaptable methods
- useful comparisons
- explicit limitations or failure modes
- lessons transferable to an enterprise engineering environment

A frontier-scale experiment may still qualify if its result changes a decision
that a normal enterprise engineering organisation can make.

Do not select a paper whose only value is theoretical novelty or a benchmark
improvement with no meaningful engineering consequence.
```

## Side-by-side excerpts (PRODUCT)
### A — newsletter_select/v001.md

```
Who: product leaders in a **business-and-process** role — product managers,
product directors, heads of product, plus adjacent ops/risk owners.

Pick the paper that best lets such a reader say one of:
- "This changes what we should build or how we should scope an AI feature."
- "This tells me something real about user behaviour, trust, adoption, or risk."
- "This affects go-to-market, pricing, compliance, or process design for AI."

Good signals: deployment or production evidence, user/human-factors findings,
governance or compliance consequence, workflow redesign, measurable business
outcome, market or sector applicability.

Reject for this seat: papers whose contribution is only a kernel, a training
trick, or a benchmark number with no product or process consequence.
```
### B — select_newsletter.py USER_RUBRIC

```
Reader:
Senior product managers, product directors, heads of product, and adjacent
business/process/risk leaders.

Strong candidates affect decisions involving:
- what to build or not build
- feature scope
- workflow or process design
- user behaviour, adoption, or trust
- human-AI interaction
- commercial model or pricing
- governance, compliance, or risk
- deployment or operating model

Prefer:
- user or deployment evidence
- measurable behavioural or business outcomes
- workflow implications
- human factors
- risks that alter product design
- findings transferable beyond the exact experiment

Do not select a paper merely because a product leader can understand it.
It must change a plausible product, process, commercial, or governance decision.
```

## STOP
Awaiting which copy is canonical before extracting `policies/editorial_seats/v001` (or equivalent) and continuing 7a items 2–7.
