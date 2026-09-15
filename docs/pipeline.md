# Pipeline — PaperIntelligenceV1

## Stages

1. **normalize_authors** (free) — 100% of papers
2. **screen** (paid, cheap, reasoning off) — 100%; gate `ai_relevance >= SCREEN_MIN_AI_RELEVANCE`
3. **classify** (paid, cheap, reasoning off) — survivors; one call → four task rows
4. **quality** (paid, reasoning on) — top `GATE_PERCENTILE` of survivors by mean(tech, novelty, evidence)
5. **affiliation** (paid where external) — screen survivors; OAI first
6. **adjudication** — resolve competing evidence
7. **paper_intelligence_current** — derive consumer state

## Operational rules

- Paid stages require `--from` / `--until` on `published_at`
- Print resolved scope and candidate count before work
- `--dry-run` makes zero API calls and projects cost
- `--allow-paid` required for live spend
- End of paid stage: papers, calls, tokens, cost, average per paper

## Batching

| Stage | Batch | Composition |
|---|---|---|
| screen | 15 | Random — never grouped by date/category/prior score |
| classify | 15 | Same |
| quality | 5 | Top percentile slice |

## Prompts / policies

| Stage | Prompt | Policy |
|---|---|---|
| screen | `prompts/screen/v001.md` | `policies/gating/v001.yaml` |
| classify | `prompts/classify/v001.md` | `policies/classification/v001.yaml` |
| quality | `prompts/quality/v001.md` | gating percentile |
| affiliation | — | `policies/affiliation_resolution/v001.yaml` |
| adjudication | `prompts/adjudication/v001.md` | affiliation + classification policies |
