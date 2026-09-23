# Organisation coverage validation

- date_until: `2026-09-15`
- min_confidence: `0.6`
- commit: `32ee6af1d6cea160cda4573b757a72becf951cd0`
- generated_at: `2026-09-18T06:07:35.770883+00:00`

## Comparison table

| Window | Papers | Ours org coverage | Unique ours orgs | OA match rate | OA org coverage | Unique OA orgs | At least one overlap |
|---|---:|---:|---:|---:|---:|---:|---:|
| 7d | 0 | n/a | 0 | n/a | n/a | 0 | 0 |
| 15d | 2 | 0.0% | 0 | 100.0% | 0.0% | 0 | 0 |
| 31d | 20 | 0.0% | 0 | 100.0% | 25.0% | 11 | 0 |

## Denominators (explicit)

- **Ours org coverage** = papers_with_accepted_org / total_arxiv_papers (accepted = organisation_id present and confidence ≥ 0.6)
- **OA match rate** = openalex_matched_papers / total_arxiv_papers
- **OA org coverage** = matched_openalex_papers_with_institution / openalex_matched_papers
- **Agreement rate** = matched papers with ≥1 common canonical org / matched papers where either side has ≥1 org

## Disagreement counts (matched papers only)

| Window | Exact set | ≥1 overlap | Ours only | OA only | Both disagree | Agreement rate |
|---|---:|---:|---:|---:|---:|---:|
| 7d | 0 | 0 | 0 | 0 | 0 | n/a |
| 15d | 0 | 0 | 0 | 0 | 0 | n/a |
| 31d | 0 | 0 | 0 | 5 | 0 | 0.0% |

## OpenAlex fetch statistics (31d population)

- papers attempted: 20
- works matched: 20
- unmatched / no id / errors: 0 (no_identifier=0, errors=0)
- OpenAlex requests logged: 20
- cache hits: 0
- cache misses: 20
- runtime_seconds: 11.406

## Notes

- OpenAlex is a public baseline, not ground truth; rates are labeled **OpenAlex agreement** / **OpenAlex coverage comparison**, not precision/recall.
- Canonical comparison prefers ROR ID, then OpenAlex institution ID, then casefolded name.
- Duplicate author→institution rows are deduplicated by organisation/institution id before counting.

## Observed disagreement causes (from counts + samples)

- OpenAlex-only orgs dominate residual gaps in counts (summed across windows: 5 matched papers).
- sample: OA institutions present while we stored no accepted organisation_id
