# Evaluation — PaperIntelligenceV1

## Golden sets

| Name | Size | Composition |
|---|---|---|
| `GOLDEN_AUDIENCE_DOMAIN_V1` | 200 | 170 llm_adjudicated + 30 manual |
| `GOLDEN_AUTHOR_AFFILIATION_V1` | 200 | 170 llm_adjudicated + 30 manual |

Never merge label sources when scoring.

## Runner (Phase 4)

```bash
python scripts/evaluate_golden.py \
  --task audience_domain \
  --golden-version v1
```

```bash
python scripts/evaluate_golden.py \
  --task author_affiliation \
  --golden-version v1
```

## Required report fields

- Previous vs candidate accuracy (split by `gold_label_source`)
- Resolved count delta
- Regressions listed by paper
- Unresolved rate
- False-positive organisation attribution (affiliation task; heavier weight than unresolved)

## M1 bar

For every golden paper, provenance + comparison questions in `Context.md` must be answerable.
