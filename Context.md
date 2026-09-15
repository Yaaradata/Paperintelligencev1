# PaperIntelligenceV1 — Context

## What this pipeline is

PaperIntelligence enriches already-ingested arXiv papers with screen scores, domain/audience classification, quality scoring, and author/affiliation resolution. It begins **after** OAI-PMH ingestion. Ingestion producing `research_radar.content_items` and `paper_metadata` is out of scope — do not rebuild, duplicate, or modify it.

## Stage diagram

```
content_items / paper_metadata                    EXISTING
        │
        ▼
[1] normalize_authors                 free        100% of papers
        │
        ▼
[2] screen  (Pass 1)                  PAID cheap  100% of papers
    ai_relevance · technical_significance
    apparent_novelty · evidence_strength
    numbers only, no prose
        │
        │  ── GATE: ai_relevance >= SCREEN_MIN_AI_RELEVANCE ──
        ▼
[3] classify                          PAID cheap  survivors
    ONE call → audience + domain + subdomain + application_domain
        │
        ├────────────────────────┐
        ▼                        ▼
[4] quality (Pass 2)         [5] affiliation
    top GATE_PERCENTILE%         OAI → aliases → ROR → OpenAlex
        └────────────┬───────────┘
                     ▼
              [6] adjudication
                     ▼
        [7] paper_intelligence_current
                     ▼
        downstream publishing / search / training
```

## Why stages sit in this order

- **Screen first** — cheapest filter; off-topic papers leave before expensive work.
- **Classify on survivors, not only the top slice** — corpus must stay queryable by domain/audience.
- **Audience + domain = one call** — same input, closed vocabularies, non-reasoning; persist as **separate rows** (`audience`, `domain`, `subdomain`, `application_domain`).
- **Quality last, top slice only** — reasoning justified; most expensive; fewest papers.
- **Affiliation gated on screen** — avoid ROR/OpenAlex spend on irrelevant papers.

Expected funnel: 100% screened → ~60% classified → ~15% of survivors quality-scored.

## Reasoning policy

| Stage | Reasoning | Why |
|---|---|---|
| screen | off | Numeric scoring against anchors |
| classify | off | Closed-enum mapping |
| quality | on | Multi-step claim vs evidence separation |

## Invariants

- Evidence is never overwritten (append-only results; current state is derived).
- Four layers stay distinct: raw source · model outputs · adjudicated · canonical current.
- Unknown beats wrong organisation attribution.
- Store `paper → author → organisation → evidence`, never bare `paper → organisation`.
- Author’s current employer ≠ paper affiliation without paper-specific evidence.
- External clients return structured data only; stages decide meaning.
- No global version — stage / prompt / policy version independently.
- Every stage idempotent and independently rerunnable.
- Every paid stage requires `--from` / `--until` and prints scope before work.
- Affiliation precedence: explicit OAI → deterministic alias/domain → ROR → OpenAlex paper-specific → author-profile secondary only.

## Constraints

| Constraint | Rule |
|---|---|
| LLM provider | OpenRouter only |
| Database | AWS RDS/PostgreSQL, schema `paper_intelligence` |
| Existing tables | Do not duplicate `content_items` / `paper_metadata` |
| Agents in runtime | Forbidden |
| New infra | Avoid; S3 not a first-implementation dependency |
| Architecture folders | One tree — never `app2/`, `new_pipeline/`, `final_version/` |
| Prompts / policies | Versioned files only; never edit an existing version in place |

## Assets carried in

**Golden sets.** `GOLDEN_AUDIENCE_DOMAIN_V1` and `GOLDEN_AUTHOR_AFFILIATION_V1`, 200 papers each — 170 triple-LLM adjudicated, 30 manually labelled. Preserve `gold_label_source` (`manual` / `llm_adjudicated`); **never merge** — unequal evidentiary weight.

**Model selection.** GLM 5.3 Flash measured at 90% on application domain and 82% Jaccard on audience against 30 human labels, with zero over-inclusion errors (every error is a miss). Adopted for screen and classify, non-reasoning. Chosen by measurement, not benchmark rank.

## Team ownership

| Owner | Stream |
|---|---|
| Subha (`dev/subha`) | Architecture, schema, normalize/screen/classify/quality/affiliation/adjudication policy and stages |
| Urmila (`dev/urmila`) | Cache, external clients, observability, golden loaders, evaluation tooling behind Subha’s interfaces |

## M1 definition

**M1 — 200+200 Golden Replayable.** Not “pipeline working.” For every golden paper the system must answer: what was ingested · which external APIs were called · which raw responses came back · which calls were cached · which stage and version produced this answer · which prompt and model · what affiliation evidence was used · the final answer · how it compares to the golden label · what changed versus the previous version.

## Glossary

| Term | Meaning |
|---|---|
| Stage | Versioned processing unit (`stage_name` + `stage_version`) with idempotent `process` |
| Evidence | Append-only fact linking paper/author/org with type, source, value, confidence |
| Adjudication | Choosing among competing evidence without deleting losers |
| Canonical current state | `paper_intelligence_current` — derived view for consumers, not source of truth |
| Golden set | Frozen labelled papers used as deployment tests |
| `general_method` | Correct application_domain for most papers; mutually exclusive with sector labels; not a fallback |
| Unlisted organisation | Resolved but not on watchlist — stored with `organisation_id NULL`, never discarded |
