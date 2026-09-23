# Organisation coverage validation

- date_until: `2026-09-15`
- min_confidence: `0.6`
- commit: `32ee6af1d6cea160cda4573b757a72becf951cd0`
- generated_at: `2026-09-18T07:21:42.851059+00:00`

## Comparison table

| Window | Papers | Ours org coverage | Unique ours orgs | OA match rate | OA org coverage | Unique OA orgs | At least one overlap |
|---|---:|---:|---:|---:|---:|---:|---:|
| 7d | 5645 | 36.4% | 753 | 92.6% | 6.1% | 523 | 136 |
| 15d | 12149 | 37.4% | 1075 | 93.6% | 6.0% | 933 | 296 |
| 31d | 23836 | 19.6% | 1077 | 93.6% | 6.2% | 1604 | 299 |

## Denominators (explicit)

- **Ours org coverage** = papers_with_accepted_org / total_arxiv_papers (accepted = organisation_id present and confidence ≥ 0.6)
- **OA match rate** = openalex_matched_papers / total_arxiv_papers
- **OA org coverage** = matched_openalex_papers_with_institution / openalex_matched_papers
- **Agreement rate** = matched papers with ≥1 common canonical org / matched papers where either side has ≥1 org

## Disagreement counts (matched papers only)

| Window | Exact set | ≥1 overlap | Ours only | OA only | Both disagree | Agreement rate |
|---|---:|---:|---:|---:|---:|---:|
| 7d | 82 | 136 | 1759 | 168 | 13 | 6.6% |
| 15d | 188 | 296 | 3940 | 360 | 30 | 6.4% |
| 31d | 189 | 299 | 4053 | 1063 | 30 | 5.5% |

## OpenAlex fetch statistics (31d population)

- papers attempted: 23836
- works matched: 22310
- unmatched / no id / errors: 1526 (no_identifier=0, errors=4)
- OpenAlex requests logged: 23836
- cache hits: 2340
- cache misses: 21496
- runtime_seconds: 4059.252

## Notes

- OpenAlex is a public baseline, not ground truth; rates are labeled **OpenAlex agreement** / **OpenAlex coverage comparison**, not precision/recall.
- Canonical comparison prefers ROR ID, then OpenAlex institution ID, then casefolded name.
- Duplicate author→institution rows are deduplicated by organisation/institution id before counting.

## Observed disagreement causes (from counts + samples)

- OpenAlex-only orgs dominate residual gaps in counts (summed across windows: 1591 matched papers).
- Ours-only orgs appear on 9752 matched papers across windows (often email_domain / local alias where OpenAlex authorships lack institutions).
- 73 matched papers have both sides non-empty but disagree on canonical sets (canonicalisation / ROR linkage mismatches are visible in disagreement CSVs).
- sample: OA institutions present while we stored no accepted organisation_id
- sample: we resolved organisations while OpenAlex Work has empty institutions
- sample: both sides non-empty but canonical key sets disjoint (ROR/OpenAlex/name)
