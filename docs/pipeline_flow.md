# Pipeline flow (Mermaid)

Canonical stage order, models/engines, and affiliation evidence. Update this file when any of those change (`docs/WRAP_UP_MY_DAY.md` §5).

```mermaid
flowchart TB
  subgraph free["Free / deterministic"]
    ingest["ingest<br/>arXiv OAI-PMH"]
    relevance["relevance<br/>deterministic AI filter<br/>rejects → S3 when enabled"]
    normalize["normalize_authors"]
    aff_fast["affiliation_fast<br/>OAI / alias / domain<br/>+ arXiv HTML if OAI empty<br/>no ROR / OpenAlex"]
    aff_deep["affiliation_deep<br/>evidence: arXiv HTML → ROR → OpenAlex"]
    judge["affiliation_judge LLM<br/>after deep<br/>prompt affiliation_judge/v001"]
    hf["hf_signals<br/>HF Daily Papers by arxiv_id"]
    adj["adjudication<br/>→ paper_intelligence_current"]
    reports["reports<br/>top-N slices"]
  end

  subgraph paid["Paid (OpenRouter)"]
    screen["screen<br/>model: SCREEN_MODEL<br/>default z-ai/glm-5.3-flash<br/>gate: ai_relevance"]
    audience["audience_domain<br/>model: CLASSIFY_MODEL<br/>default z-ai/glm-5.3-flash<br/>policy AUDIENCE_POLICY"]
    quality["quality<br/>QUALITY_ENGINE flag"]
  end

  ingest --> relevance --> normalize --> screen
  screen --> aff_fast --> audience --> quality
  quality --> aff_deep --> judge --> hf --> adj --> reports

  subgraph qeng["QUALITY_ENGINE"]
    terra["terra default<br/>openai/gpt-5.6-terra<br/>scores + prose"]
    jev_glm["jev_glm opt-in<br/>typesafe/jev-1.13 scores<br/>+ GLM flash prose<br/>prompt quality_prose/v001<br/>method=llm; prose fail keeps scores"]
  end

  quality -.-> terra
  quality -.-> jev_glm
```

## Evidence hierarchy (affiliation)

| Phase | Sources | Notes |
|---|---|---|
| **fast** (pre-quality) | OAI / existing `affiliation_text` + local alias/domain; **arXiv HTML** when OAI empty | No ROR / OpenAlex |
| **deep** (post-quality) | **arXiv HTML → ROR → OpenAlex** | Enrichment after quality (quality stays author/org-blind) |
| **judge** (after deep) | LLM `affiliation_judge` | Resolves / verifies; evidence type `llm_affiliation_judge` |

## Engine flag

| Flag | Default | Effect |
|---|---|---|
| `QUALITY_ENGINE` | `terra` | `terra` = Terra scores+prose; `jev_glm` = Jev v001 scores + GLM prose |

Paid stages require `--from` / `--until` and `--allow-paid`.
