# Architecture — PaperIntelligenceV1

## Position in the stack

Ingestion (OAI-PMH → `content_items` / `paper_metadata`) already exists. PaperIntelligence is a **post-ingest enrichment** pipeline in schema `paper_intelligence`.

## Target flow

See root `Context.md` for the full diagram. Stages: normalize → screen → (gate) → classify → {quality ∥ affiliation} → adjudication → `paper_intelligence_current`.

## Module map

| Package | Responsibility |
|---|---|
| `normalize` | authors_raw → `paper_authors` |
| `screen` | Pass 1 numeric scores |
| `classify` | One LLM call → multiple classification rows |
| `quality` | Pass 2 rubric on top percentile |
| `author_affiliation` / `organisation_resolution` | Evidence-based affiliation |
| `adjudication` | Resolve conflicts; feed current state |
| `openrouter` / `external` | Client boundaries (no business decisions) |
| `cache` / `observability` | Urmila — replayable raw + run metrics |
| `evaluation` / `db` / `common` | Golden eval, DB access, shared contracts |

## Evidence layers

1. Raw source (OAI, cached API JSON.gz)
2. Individual model / extractor outputs (append-only)
3. Adjudicated outputs (append-only)
4. Canonical current (`paper_intelligence_current`)

## Versioning

Independent `stage_version`, `prompt_version`, `policy_version`, plus `code_commit_sha` on runs. No single global pipeline version.

## Architecture delta status

Phase 1 scaffold only. Full exists/reuse/missing/sequence delta is **S-001 / P-001** immediately after this commit.
