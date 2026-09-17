# Pipeline — PaperIntelligenceV1

Canonical summary: root **[PROJECT.md](../PROJECT.md)**.

## Stages

```
ingest → relevance → normalize_authors → screen
  → affiliation_fast          # OAI + local alias/domain only (pre-quality)
  → audience_domain
  → quality                   # top screen slice ∪ notable org ∪ notable person
  → affiliation_deep          # HTML + ROR + OpenAlex (post-quality)
  → hf_signals → adjudication → reports
```

0. **ingest** (free) — arXiv OAI-PMH → shared `research_radar` tables; stores `authors_structured` when OAI provides affiliations  
1. **relevance** (free) — deterministic AI relevance; rejects archived to S3  
2. **normalize_authors** (free) — `status = RELEVANT` only  
3. **screen** (paid) — gate `ai_relevance`  
4. **affiliation_fast** (free) — OAI / existing `affiliation_text` + alias/domain; **no HTML/ROR/OpenAlex**  
5. **audience_domain** (paid) — audience / domain / subdomains / application_domain  
6. **quality** (paid) — router: top `GATE_PERCENTILE` ∪ Org-of-Interest ∪ Person-of-Interest; scoring stays author/org-blind  
7. **affiliation_deep** (free) — HTML footnotes → ROR → OpenAlex  
8. **hf_signals** (free) — HF Daily Papers enrichment by `arxiv_id` (no new papers)  
9. **adjudication** — `paper_intelligence_current` including explicit `quality_status`  
10. **reports** — tech / business / audience tops  

## Version-aware skips

Paid stages skip a paper only when a `paper_classification_results` row already exists for the **current** `(task_type, stage_version, prompt_version, policy_version, model)` tuple.

## S3 rejects

`S3_ARCHIVE_ENABLED=true` + bucket env →  
`s3://{bucket}/paper-intelligence/rejected/relevance/.../{run_id}.jsonl.gz`  
Manifest: `research_radar.s3_archives`.

## CLI notes

- `--stage classify` aliases to `audience_domain`
- Pipeline alias `affiliation` → `affiliation_deep`
- Paid stages need `--allow-paid`
- Downstream paid selection requires `status = RELEVANT`
