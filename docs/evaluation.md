# Evaluation — PaperIntelligenceV1

## Golden sets (in repo)

| File | Task | Size | Composition |
|---|---|---|---|
| `data/golden/audience_domain_200_v1.json` | audience_domain | ~229 | 200 llm_adjudicated tagging sample + 30 manual human labels |
| `data/golden/audience_domain_human_30_v1.json` | audience_domain | 30 | manual only (`version=v1-human`) |
| `data/golden/author_affiliation_200_v1.json` | author_affiliation | 200 | llm_adjudicated (sol preferred) |

Never merge label sources when scoring — metrics are split by `gold_label_source`.

## Load + evaluate

```bash
python3 scripts/load_golden.py --file data/golden/audience_domain_200_v1.json
python3 scripts/load_golden.py --file data/golden/audience_domain_human_30_v1.json
python3 scripts/load_golden.py --file data/golden/author_affiliation_200_v1.json

python3 scripts/evaluate_golden.py --task audience_domain --golden-version v1
python3 scripts/evaluate_golden.py --task author_affiliation --golden-version v1
```

## Required report fields

- Accuracy split by `gold_label_source` (`manual` vs `llm_adjudicated`)
- Missing-prediction count
- For affiliation: any-org overlap rate and exact org-set rate

## HF validation

See `docs/hf_validation.md` (observational; does not change `final_score`).
