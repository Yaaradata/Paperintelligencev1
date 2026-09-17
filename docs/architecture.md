# Architecture — PaperIntelligenceV1

Canonical summary: root **[PROJECT.md](../PROJECT.md)**.

## Flow

```
ingest → relevance (+ S3 rejects) → normalize → screen
  → affiliation_fast → audience_domain → quality
  → affiliation_deep → hf_signals → adjudication → current → reports
```

Quality scoring stays **blind** to authors/organisations. FAST affiliation is a discovery signal for the quality router (`top screen slice ∪ notable org ∪ notable person`). DEEP affiliation enriches after scoring.

## Modules (brief-aligned)

| Package | Role |
|---|---|
| `ingest/` | OAI-PMH harvest; `authors_structured` + OAI affiliation capture |
| `relevance/` | Free deterministic filter; S3 archive of rejects |
| `normalize/` | Author rows |
| `audience_domain/` | Closed-vocab audience/domain (brief name; was `classify`) |
| `screen/` / `quality/` | Paid scoring funnel + quality candidate router |
| `author_affiliation/` / `organisation_resolution/` | FAST/DEEP affiliation evidence |
| `hf_signals/` | HF Daily Papers enrichment by arxiv_id |
| `adjudication/` | Current state + org_boost + `quality_status` |
| `evaluation/` | HF validation + golden load/eval |
| `cache/s3_archive.py` | Rejected-paper uploads |
| `external/` (arxiv HTML, ROR, OpenAlex, **huggingface**) | Infra clients |
| `openrouter/` / `observability/` / `db/` | LLM + runs |

## Shared RDS

- Ingest + relevance write `research_radar.*` (status, scores, S3 manifest)
- Enrichment writes `paper_intelligence.*` only
