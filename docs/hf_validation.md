# Hugging Face Daily Papers — validation

## Purpose

Determine whether HF Daily Papers adds **incremental editorial/relevance signal**
beyond PaperIntelligence ranking. A finding that HF adds little value is valid.

This analysis does **not** change `final_score`, adjudication, classification,
or affiliation.

## Methodology

- **Window (inclusive):** `2026-08-18` → `2026-09-16`
  (30 days).
- **Our corpus:** `research_radar.content_items` with `paper_metadata.arxiv_id`
  and `published_at` in the window.
- **HF set:** unique arXiv ids from HF Daily Papers API for each day in the
  window (day-local list; not `sort=trending`).
- **Overlap** joins those id sets.
- **Score field:** `final_score` on `paper_intelligence_current`.
- **High-quality selection:** `final_score_is_not_null`.
  High-quality = papers with paper_intelligence_current.final_score IS NOT NULL (already selected by screen gate + quality GATE_PERCENTILE slice + adjudication). No new score threshold invented.

### Cohorts (mutually exclusive on comparison universe)

- **BOTH** — HF Daily Papers ∩ high-quality (`final_score` present)
- **OURS_ONLY** — high-quality \ HF
- **HF_ONLY** — HF ∩ our corpus, but no `final_score`

Comparison universe = high-quality ∪ (HF ∩ our corpus).

## Overlap calculations

| Metric | Value |
|---|---:|
| HF unique (Daily Papers in window) | 657 |
| Our unique (arxiv papers in window) | 22585 |
| Intersection | 575 |
| HF → ours % | 87.5 |
| Ours → HF % | 2.5 |
| HF-only (not in our window corpus) | 82 |
| Ours-only (not on HF Daily in window) | 22010 |

## Ranking comparison

Score field `final_score`; selection `final_score_is_not_null`. High-quality = papers with paper_intelligence_current.final_score IS NOT NULL (already selected by screen gate + quality GATE_PERCENTILE slice + adjudication). No new score threshold invented.

| Cohort | N | Avg final_score | Median | % notable org | % tech/product aud | Mean HF upvotes |
|---|---:|---:|---:|---:|---:|---:|
| BOTH | 132 | 7.72 | 7.8 | 22.7 | 98.5 | 53.106 |
| OURS_ONLY | 1688 | 7.574 | 7.6 | 13.8 | 98.3 | 14.5 |
| HF_ONLY | 443 | None | None | 3.6 | 14.0 | 38.099 |

### Domain distribution (BOTH)

```
{
  "natural_language_processing": 28,
  "evaluation_benchmarking": 18,
  "multimodal_learning": 16,
  "alignment_safety": 13,
  "reinforcement_learning": 10,
  "robotics_embodied": 9,
  "computer_vision": 8,
  "model_compression": 8,
  "generative_models": 5,
  "efficient_inference": 5,
  "systems_infrastructure": 4,
  "speech_audio": 2,
  "theory_foundations": 2,
  "interpretability": 2
}
```

## Caveats

- Quality/`final_score` coverage may be concentrated in part of the window
  (pipeline paid stages not necessarily run for every day).
- HF-only cohort average score is expected to be null when those papers never
  entered the quality slice.
- `hf_daily_upvote_rank` is same-day upvote rank, not HF global trending.
- HF→ours < 100% can mean paper not in our category filter / not yet ingested
  for that publish date, not that HF has non-arXiv papers.

## Findings

- HF → our corpus overlap is 87.5% (575/657).
- Our corpus → HF overlap is 2.5% (575/22585) — HF is a thin curated slice.
- Cohorts: BOTH=132, OURS_ONLY=1688, HF_ONLY=443.
- Avg final_score BOTH (7.72) vs OURS_ONLY (7.574); delta=0.146.
- BOTH is not materially higher-scoring than OURS_ONLY and is a small share of our high-quality set — HF adds little ranking lift on this window.
- HF_ONLY=443 papers are featured on HF but lack final_score (mean upvotes=38.099) — candidates we may be missing if gate/quality coverage is incomplete, not proof HF should boost score.

## Recommendation

**Recommendation: no incremental signal** — on this window HF does not improve on our high-quality set enough to warrant a ranking change.

## Run provenance

```json
{
  "run_id": "5dc5fd0a-b6a7-4237-b379-c96523bc3f58",
  "stage_name": "hf_validation",
  "stage_version": "v001",
  "code_commit_sha": "be8af1b9335a0027c6b9c20380b4bcdb344516bb",
  "papers_evaluated": 22585,
  "hf_unique": 657,
  "high_quality_count": 1820
}
```
