# Golden datasets

| File | Task | Size | Sources |
|---|---|---|---|
| `audience_domain_200_v1.json` | audience_domain | ~229 | Research Radar tagging sample (200) + human 30 |
| `audience_domain_human_30_v1.json` | audience_domain | 30 | Human labels only (`version=v1-human`) |
| `author_affiliation_200_v1.json` | author_affiliation | 200 | Research Radar `affiliation_200_results_v2.xlsx` |

`gold_label_source` is either `manual` or `llm_adjudicated`.

```bash
python3 scripts/load_golden.py --file data/golden/audience_domain_200_v1.json
python3 scripts/load_golden.py --file data/golden/audience_domain_human_30_v1.json
python3 scripts/load_golden.py --file data/golden/author_affiliation_200_v1.json

python3 scripts/evaluate_golden.py --task audience_domain --golden-version v1
python3 scripts/evaluate_golden.py --task author_affiliation --golden-version v1
```
