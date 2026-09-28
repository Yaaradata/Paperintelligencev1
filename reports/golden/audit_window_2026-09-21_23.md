# Window completeness audit 2026-09-21 .. 2026-09-23

Window papers: 2454 · passed screen: 1489 · papers with a quality row: 1492 · quality rows (all engines/runs): 1805

| defect | count | % of window | example ids (up to 10) |
|---|---:|---:|---|
| Passed screen, no quality row | 0 | 0.0% | — |
| Quality row with NULL technical_significance | 0 | 0.0% | — |
| Quality row with NULL apparent_novelty | 0 | 0.0% | — |
| Quality row with NULL practical_applicability | 0 | 0.0% | — |
| Quality row with NULL professional_value | 0 | 0.0% | — |
| Quality row with NULL learning_value | 0 | 0.0% | — |
| Quality row with NULL evidence_strength | 0 | 0.0% | — |
| Quality row with NULL/empty composite | 0 | 0.0% | — |
| Quality row with NULL/empty so_what | 765 | 31.2% | 199195<br>199196<br>199205<br>199245<br>199263<br>199267<br>199270<br>199275<br>199402<br>199407 |
| Quality row with NULL/empty reason_not_higher | 765 | 31.2% | 199195<br>199196<br>199205<br>199245<br>199263<br>199267<br>199270<br>199275<br>199402<br>199407 |
| Dimension or composite outside 0-10 | 0 | 0.0% | — |
| Quality row but no paper_intelligence_current row | 0 | 0.0% | — |
| quality_status in failed/pending/stale_content/inconsistent_attempt_without_result | 0 | 0.0% | — |
| Latest quality attempt failed and no quality row exists | 2 | 0.1% | 200094 (attempt failed: OpenRouterError: HTTP 402: {"error":{"message":"This request would exceed your available credits given your current in-flight requests. Retry after in-flight re)<br>200268 (attempt failed: OpenRouterError: HTTP 402: {"error":{"message":"This request would exceed your available credits given your current in-flight requests. Retry after in-flight re) |
| Quality row without scoring_engine stamp | 3 | 0.1% | 200454<br>200785<br>200788 |
| Quality row without prose_model stamp | 768 | 31.3% | 199195<br>199196<br>199205<br>199245<br>199263<br>199267<br>199270<br>199275<br>199402<br>199407 |
| Paper scored more than once under different engines | 287 | 11.7% | 199177 (jev_glm + openai/gpt-5.6-terra)<br>199195 (jev_glm + openai/gpt-5.6-terra)<br>199197 (jev_glm + openai/gpt-5.6-terra)<br>199198 (jev_glm + openai/gpt-5.6-terra)<br>199226 (jev_glm + openai/gpt-5.6-terra)<br>199245 (jev_glm + openai/gpt-5.6-terra)<br>199263 (jev_glm + openai/gpt-5.6-terra)<br>199267 (jev_glm + openai/gpt-5.6-terra)<br>199270 (jev_glm + openai/gpt-5.6-terra)<br>199272 (jev_glm + openai/gpt-5.6-terra) |
| arXiv v1 (raw_metadata.created) before window start | 0 | 0.0% | — |

Prose missing: 765 of 1492 scored papers (51.3%); threshold 10%.

**Complete enough to publish: NO.**
- prose missing on 765/1492 scored papers (51.3%) > 10%
