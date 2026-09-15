# Data model — PaperIntelligenceV1

Schema: `paper_intelligence`. FKs to `research_radar.content_items`. Do not duplicate `content_items` or `paper_metadata`.

DDL: `sql/migrations/001_schema.sql` (**agents do not apply**).

## Identity and affiliation

| Table | Notes |
|---|---|
| `paper_authors` | `(content_item_id, author_position)` unique; identity fields nullable |
| `people` | `priority`, `is_person_of_interest`, `active`, `metadata` |
| `organisations` | ROR/OpenAlex ids unique when present |
| `organisation_aliases` | `alias_type ∈ {name,domain,abbreviation,historical_name}` |
| `paper_author_affiliations` | Append-only; **`organisation_id` NULL = unlisted, keep raw** |
| `papers_people` | `author_position`, `confidence`, `evidence_type` |

## Classification and scoring (append-only)

`paper_classification_results.task_type ∈`:

`screen` · `audience` · `domain` · `subdomain` · `application_domain` · `quality`

Payload in `result_json`. One classify call → multiple rows sharing `run_id` / `prompt_version` / `stage_version`.

## Canonical current

`paper_intelligence_current`: domain, subdomains, audiences, application_domains, confidences, `screen_score`, `quality_score`, resolution statuses. **Derived only.**

## Run tracking

`pipeline_runs` → `stage_runs` → `item_stage_runs`.

## Golden and evaluation

| Table | Critical fields |
|---|---|
| `golden_sets` | `name`, `version`, `task_type` |
| `golden_set_items` | set ↔ content_item |
| `golden_labels` | `task_type`, `label_json`, **`gold_label_source`**, `labeller` |
| `evaluation_runs` | versions + `code_commit_sha` |
| `evaluation_results` | `predicted_json`, `gold_json`, `is_match`, `error_class` |

Score `manual` and `llm_adjudicated` separately in reports.

## Interfaces Urmila implements behind

### `external_requests`

| Column | Purpose |
|---|---|
| `request_id` UUID PK | |
| `run_id` / `stage_run_id` / `content_item_id` | nullable links |
| `provider` | `arxiv` \| `openalex` \| `ror` \| `openrouter` |
| `endpoint` | |
| `request_hash` | deterministic cache key |
| `started_at` / `ended_at` / `duration_ms` | |
| `http_status` / `success` / `cache_hit` | |
| `response_path` / `response_sha256` | raw JSON.gz pointer |
| `error_type` / `error_message` | |
| `created_at` | |

### `llm_requests`

| Column | Purpose |
|---|---|
| `llm_request_id` UUID PK | |
| `request_id` | FK → `external_requests` |
| `model` / `prompt_version` | |
| `input_tokens` / `output_tokens` / `estimated_cost` | |
| `created_at` | |

### Python stubs

```python
ror.resolve_affiliation(raw: str) -> RorResponse
openalex.get_work(identifier: str) -> OpenAlexWork
arxiv.get_paper(arxiv_id: str) -> ArxivResponse
openrouter.complete(request: LLMRequest) -> LLMResponse
```

Clients return structured data only. Stages decide meaning.
