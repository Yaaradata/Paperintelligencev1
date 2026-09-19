# PI Catalog Backfill Validation

**Mode:** additive / shadow (no production cutover)

## Summary

| Check | Value |
|---|---|
| Radar/PI refs considered | 34460 |
| PI papers inserted | 34460 |
| Orphan PI enrichment IDs | 0 |
| Duplicate arXiv groups | 0 |
| Duplicate DOI groups | 0 |
| Identity map rows | 70952 |
| Papers without legacy Radar | 0 |

## Targets

| Target | Pass |
|---|---|
| 0 orphan enrichment rows | True |
| 0 duplicate canonical arXiv | True |
| 0 duplicate DOI | True |
| papers count == refs | True |

## ID reuse

- Decision: `paper_id = legacy_content_item_id` (**safe**, precheck passed)
- Sequence next expected: `195658`
- Sequence last_value / is_called: `195658` / `False`

## Missing metadata

```json
{
  "missing_published_at": 0,
  "missing_arxiv": 0,
  "missing_abstract": 0,
  "missing_title": 0
}
```

## Enrichment join orphans

```json
{
  "paper_classification_results": {
    "orphans": 0,
    "total": 27599
  },
  "paper_intelligence_current": {
    "orphans": 0,
    "total": 7756
  },
  "paper_authors": {
    "orphans": 0,
    "total": 165645
  },
  "paper_author_affiliations": {
    "orphans": 0,
    "total": 124783
  },
  "paper_hf_signals": {
    "orphans": 0,
    "total": 580
  }
}
```

## Latest relevance decisions (migrated)

```json
[
  {
    "decision": "keep",
    "n": 20300
  },
  {
    "decision": "reject",
    "n": 8083
  }
]
```

## Focus paper 137619

```json
{
  "paper_id": 137619,
  "legacy_content_item_id": 137619,
  "arxiv_id": "2609.03181",
  "title": "Jina-OCR-v1: Efficient Document Parsing with Speculative Decoding and Dense Verifiable Rewards",
  "published_at": "2026-09-02 00:00:00+00:00",
  "ingested_at": "2026-09-05 09:57:30.585308+00:00",
  "source_updated_at": "2026-09-04 00:00:00+00:00"
}
```

## Mismatch samples (title/arxiv/date)

Count shown: 0 (limit 20)

See JSON for details.
