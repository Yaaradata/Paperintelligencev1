# G3b — Terra scores for screen_failed + flagged (gate-drop eval)

**Generated:** 2026-09-24T08:14:48.924559+00:00  
**run_id:** `866234e7-fb27-4ecd-a881-318cca1bf72e` (pipeline `golden_g3b_gate_drop_eval` — NOT current quality)  
**Model:** `openai/gpt-5.6-terra` · **cost:** $0.0683 (cap $1.0)  
**Scored:** 24/24  
**Rank pool:** 191 golden papers with Terra composites  

## What the screen gate drops (human labels)

Of the **24** screen_failed+flagged papers, **6** were labelled `shortlist` or `winner_material`:

| paper_id | stratum | verdict | h_final | terra_composite | rank / pool |
|---:|---|---|---:|---:|---:|
| 137619 | flagged | winner_material | 9.5 | 7.62 | 64 / 191 |
| 194089 | flagged | winner_material | 9.0 | 7.1 | 110 / 191 |
| 197726 | flagged | winner_material | 9.0 | 6.72 | 134 / 191 |
| 196256 | screen_failed | shortlist | 8.5 | 7.62 | 65 / 191 |
| 196694 | screen_failed | winner_material | 9.0 | 7.82 | 42 / 191 |
| 196699 | screen_failed | shortlist | 8.0 | 6.62 | 136 / 191 |

## All 24 gate-drop papers

| paper_id | stratum | h_verdict | h_final | terra_composite | rank / pool |
|---:|---|---|---:|---:|---:|
| 137619 | flagged | winner_material | 9.5 | 7.62 | 64 / 191 |
| 194089 | flagged | winner_material | 9.0 | 7.1 | 110 / 191 |
| 195234 | flagged | maybe | 7.0 | 7.86 | 39 / 191 |
| 197726 | flagged | winner_material | 9.0 | 6.72 | 134 / 191 |
| 196256 | screen_failed | shortlist | 8.5 | 7.62 | 65 / 191 |
| 196310 | screen_failed | reject | 5.0 | 6.96 | 116 / 191 |
| 196315 | screen_failed | maybe | 6.0 | 7.32 | 83 / 191 |
| 196387 | screen_failed | reject | 5.5 | 6.18 | 160 / 191 |
| 196391 | screen_failed | reject | 4.0 | 6.44 | 139 / 191 |
| 196393 | screen_failed | reject | 5.5 | 6.16 | 163 / 191 |
| 196398 | screen_failed | reject | 4.5 | 4.98 | 188 / 191 |
| 196413 | screen_failed | reject | 5.5 | 5.72 | 181 / 191 |
| 196483 | screen_failed | maybe | 7.0 | 6.24 | 158 / 191 |
| 196542 | screen_failed | maybe | 6.0 | 7.9 | 38 / 191 |
| 196552 | screen_failed | reject | 5.5 | 7.84 | 40 / 191 |
| 196607 | screen_failed | reject | 4.0 | 6.54 | 138 / 191 |
| 196608 | screen_failed | reject | 5.5 | 5.36 | 185 / 191 |
| 196652 | screen_failed | reject | 4.5 | 7.42 | 79 / 191 |
| 196659 | screen_failed | maybe | 6.5 | 7.82 | 41 / 191 |
| 196692 | screen_failed | maybe | 6.0 | 6.44 | 140 / 191 |
| 196694 | screen_failed | winner_material | 9.0 | 7.82 | 42 / 191 |
| 196699 | screen_failed | shortlist | 8.0 | 6.62 | 136 / 191 |
| 196708 | screen_failed | reject | 3.5 | 8.58 | 3 / 191 |
| 196776 | screen_failed | reject | 5.5 | 7.08 | 112 / 191 |

## Notes

- Scores written under dedicated pipeline run; excluded from current-quality comparison via reports/golden/g3b_run.json.
- Rank is among all golden papers that have a Terra quality composite (gate drops + previously scored non-gate; pool_n=191).
