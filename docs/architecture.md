# Architecture — PaperIntelligenceV1

Canonical summary: root **[PROJECT.md](../PROJECT.md)**.

## Flow

```
ingest → relevance (+ S3 rejects) → normalize → screen → audience_domain
  → {quality ∥ affiliation} → hf_signals → adjudication → current → reports
```

## Modules (brief-aligned)

| Package | Role |
|---|---|
| `ingest/` | OAI-PMH harvest |
| `relevance/` | Free deterministic filter; S3 archive of rejects |
| `normalize/` | Author rows |
| `audience_domain/` | Closed-vocab audience/domain (brief name; was `classify`) |
| `screen/` / `quality/` | Paid scoring funnel |
| `author_affiliation/` / `organisation_resolution/` | Affiliation evidence |
| `hf_signals/` | HF Daily Papers enrichment by arxiv_id |
| `adjudication/` | Current state + org_boost |
| `cache/s3_archive.py` | Rejected-paper uploads |
| `external/` (arxiv HTML, ROR, OpenAlex, **huggingface**) | Infra clients |
| `openrouter/` / `observability/` / `db/` | LLM + runs |

## Shared RDS

- Ingest + relevance write `research_radar.*` (status, scores, S3 manifest)
- Enrichment writes `paper_intelligence.*`
- RR copies of ingest/relevance remain; do not delete them
