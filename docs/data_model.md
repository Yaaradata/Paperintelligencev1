# Data model — PaperIntelligenceV1

Schema: `paper_intelligence`. Foreign keys to `research_radar.content_items`. Do not duplicate `content_items` or `paper_metadata`.

## Identity and affiliation

- `paper_authors` — occurrence per paper; identity fields nullable until resolved
- `people` — canonical person
- `organisations` — canonical org
- `organisation_aliases` — name/domain/abbreviation/historical_name
- `paper_author_affiliations` — **append-only** evidence; `organisation_id` nullable by design (unlisted)
- `papers_people` — paper ↔ person link

## Classification and scoring (append-only)

`paper_classification_results.task_type` ∈ `screen`, `audience`, `domain`, `subdomain`, `application_domain`, `quality`.

One classify call writes multiple rows sharing `run_id` / `prompt_version` / `stage_version`.

## Canonical current

`paper_intelligence_current` — derived only. Includes domain, subdomains, audiences, application_domains, screen_score, quality_score, resolution statuses.

## Run tracking

`pipeline_runs` → `stage_runs` → `item_stage_runs`.

## Golden and evaluation

`golden_sets`, `golden_set_items`, `golden_labels` (`gold_label_source` required), `evaluation_runs`, `evaluation_results`. Score `manual` and `llm_adjudicated` separately.

## Interfaces Urmila implements (shape only — Phase 2 will freeze columns)

### `external_requests`

Intent: one row per external HTTP/API attempt (arxiv, openalex, ror, openrouter) with `request_hash`, timing, `cache_hit`, `response_path`, `response_sha256`, errors, optional links to run/stage/content.

### `llm_requests`

Intent: OpenRouter economics linked to an `external_requests` row — `model`, `prompt_version`, token counts, `estimated_cost`.

> Column-precise DDL lands in Phase 2 migration + this doc update (S-005).
