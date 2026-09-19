# PI Catalog Shadow Comparison (15d)

Window: `2026-09-01` → `2026-09-15`

Unexplained differences: **0**

| Reader | old | new | ∩ | old_only | new_only | class | reason |
|---|---:|---:|---:|---:|---:|---|---|
| paper_window | 12149 | 11853 | 11853 | 296 | 0 | migrated_state_difference | PI catalog/relevance is PI-referenced subset or keep-seeded; legacy path uses full Radar window / PI_ELIGIBLE_STATUSES |
| relevance_keep | 7548 | 7541 | 7541 | 7 | 0 | migrated_state_difference | PI catalog/relevance is PI-referenced subset or keep-seeded; legacy path uses full Radar window / PI_ELIGIBLE_STATUSES |
| relevance_reject | 4306 | 4306 | 4306 | 0 | 0 | match | identical |
| screen_candidates | 43 | 36 | 36 | 7 | 0 | migrated_state_difference | PI catalog/relevance is PI-referenced subset or keep-seeded; legacy path uses full Radar window / PI_ELIGIBLE_STATUSES |
| screen_survivors | 7300 | 7300 | 7300 | 0 | 0 | match | identical |
| audience_candidates | 5375 | 5368 | 5368 | 7 | 0 | migrated_state_difference | PI catalog/relevance is PI-referenced subset or keep-seeded; legacy path uses full Radar window / PI_ELIGIBLE_STATUSES |
| normalize_candidates | 7548 | 7541 | 7541 | 7 | 0 | migrated_state_difference | PI catalog/relevance is PI-referenced subset or keep-seeded; legacy path uses full Radar window / PI_ELIGIBLE_STATUSES |
| quality_router_population | 7300 | 7300 | 7300 | 0 | 0 | match | identical |
| quality_selected | 1654 | 1654 | 1654 | 0 | 0 | match | identical |
| affiliation_fast_candidates | 7300 | 7300 | 7300 | 0 | 0 | match | identical |
| affiliation_deep_candidates | 1820 | 1820 | 1820 | 0 | 0 | match | identical |
| hf_window_papers | 12149 | 11853 | 11853 | 296 | 0 | migrated_state_difference | PI catalog/relevance is PI-referenced subset or keep-seeded; legacy path uses full Radar window / PI_ELIGIBLE_STATUSES |
| adjudication_editorial_population | 7505 | 7505 | 7505 | 0 | 0 | match | identical |
