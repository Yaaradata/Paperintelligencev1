# Architecture — PaperIntelligenceV1

## Position in the stack

Ingestion (OAI-PMH → `content_items` / `paper_metadata`) already exists. PaperIntelligence is a **post-ingest enrichment** pipeline in schema `paper_intelligence`.

## Target flow

See root `Context.md`. Stages: normalize → screen → (gate) → classify → {quality ∥ affiliation} → adjudication → `paper_intelligence_current`.

## Architecture delta (P-001 / S-001)

### What exists (reuse)

| Asset | Location | Action |
|---|---|---|
| OAI ingestion + `content_items` / `paper_metadata` | Research Radar / RDS | **Reuse as-is** — do not modify |
| Ad-hoc audience/domain LLM enrichment | Predecessor pipeline | **Refactor** into versioned `classify` stage |
| Org/people concepts in `research_radar` | Existing watchlists | **Do not duplicate semantics** into PI blindly; PI has its own canonical tables with evidence rows |
| Measured model choice | GLM 5.3 Flash (screen/classify) | Adopt |
| Golden set assets (200+200) | To be loaded into PI golden tables | Preserve `gold_label_source` |

### What is missing (build)

| Gap | Owner |
|---|---|
| `paper_intelligence` schema applied in RDS | Human applies Subha migrations |
| Stage implementations normalize→…→current | Subha |
| Cache + external/OpenRouter implementations | Urmila |
| Golden loaders + `evaluate_golden.py` | Urmila (+ Subha metrics) |
| `check_schema.py` live DB probe | Shared Phase 4 |

### Migration sequence

1. `sql/migrations/001_schema.sql` — full Phase 2 tables (this commit)
2. Human applies on RDS after review
3. Later migrations only additive; views use `DROP VIEW IF EXISTS` then `CREATE VIEW`

### Implementation sequence (after this contract lands on `main`)

1. Both worktrees rebase
2. Urmila: ROR cache path first, then OpenAlex/OpenRouter
3. Subha: `normalize_authors` → `screen` → `classify` → `quality` ∥ `affiliation` → adjudication/current
4. Evaluation tooling + M1 demo

### Interfaces Urmila depends on (frozen here)

- Tables: `external_requests`, `llm_requests` (see `data_model.md`)
- Python: `ror.resolve_affiliation`, `openalex.get_work`, `arxiv.get_paper`, `openrouter.complete`
- Stage contract: `Stage` / `StageResult` / `Evidence` / `RunContext`

## Module map

| Package | Responsibility |
|---|---|
| `normalize` / `screen` / `classify` / `quality` | Enrichment stages |
| `author_affiliation` / `organisation_resolution` | Evidence-based affiliation |
| `adjudication` | Resolve conflicts; feed current state |
| `openrouter` / `external` | Client boundaries (no business decisions) |
| `cache` / `observability` | Urmila |
| `evaluation` / `db` / `common` | Golden eval, DB, contracts |

## Evidence layers

1. Raw source (OAI, cached API JSON.gz)
2. Individual model / extractor outputs (append-only)
3. Adjudicated outputs (append-only)
4. Canonical current (`paper_intelligence_current`)

## Versioning

Independent `stage_version`, `prompt_version`, `policy_version`, plus `code_commit_sha` on runs.
