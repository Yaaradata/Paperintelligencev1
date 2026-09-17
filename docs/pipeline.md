# Pipeline — PaperIntelligenceV1

Canonical summary: root **[PROJECT.md](../PROJECT.md)**.

## Stages

0. **ingest** (free) — arXiv OAI-PMH → shared `research_radar` tables  
1. **relevance** (free) — deterministic AI relevance; rejects archived to S3  
2. **normalize_authors** (free) — `status = RELEVANT` only  
3. **screen** (paid) — gate `ai_relevance`  
4. **audience_domain** (paid) — audience / domain / subdomains / application_domain  
5. **quality** (paid) — top `GATE_PERCENTILE`  
6. **affiliation** — OAI / HTML footnotes → alias → ROR → OpenAlex  
7. **hf_signals** (free) — HF Daily Papers enrichment by `arxiv_id` (no new papers)  
8. **adjudication** — `paper_intelligence_current`  
9. **reports** — tech / business / audience tops  

## S3 rejects

`S3_ARCHIVE_ENABLED=true` + bucket env →  
`s3://{bucket}/paper-intelligence/rejected/relevance/.../{run_id}.jsonl.gz`  
Manifest: `research_radar.s3_archives`.

## CLI notes

- `--stage classify` aliases to `audience_domain`
- Paid stages need `--allow-paid`
- Downstream paid selection requires `status = RELEVANT`
