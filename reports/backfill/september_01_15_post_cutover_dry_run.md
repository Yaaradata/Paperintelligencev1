# September 1–15 post-cutover dry-run

**Generated:** 2026-09-21T07:29:48.917585+00:00  
**Window:** 2026-09-01 → 2026-09-15 (inclusive)  
**Flags:** `PI_USE_PAPERS_CATALOG=1`, `PI_WRITE_RADAR_COMPAT=0`  
**Paid bulk:** **NOT EXECUTED** (dry-run only)

Machine-readable twin: `september_01_15_post_cutover_dry_run.json`

---

## 1. Post-cutover health check

| Check | Result |
|---|---|
| PI catalog default ON | **True** |
| Radar compatibility OFF | **True** (`PI_WRITE_RADAR_COMPAT=False`) |
| PI → Radar FKs | **0** remaining |
| Migrations 006–009 | {"006_papers": true, "007_archive_records": true, "008_pi_fks": true, "009_radar_fks_dropped": true} |
| Duplicate arXiv IDs | **0** |
| Duplicate DOI identities | **0** |
| Orphan PI result rows | **0** |
| Selectors depend on Radar status | **False** |
| Health OK | **True** |

**Versions / models in force**

- Screen: `{'stage': 'v001', 'prompt': 'v001', 'policy': 'v001', 'model': 'z-ai/glm-5.3-flash'}`
- Audience: `{'stage': 'v001', 'prompt': 'v002', 'policy': 'v001', 'model': 'z-ai/glm-4.6'}`
- Quality: `{'stage': 'v001', 'prompt': 'v001', 'policy': 'v001', 'model': 'openai/gpt-5.6-sol'}`
- Gate percentile: **15.0**

Cutover-critical unit tests re-run: catalog/quality router suites **passed**. No cutover regression found that blocks this dry-run.

---

## 2. Exact Sep 1–15 backlog (PI-only recompute)

| Code | Metric | Count |
|---|---|---:|
| A | Total PI papers | **12149** |
| B | Papers with no relevance result | **295** |
| C | Relevance keep | **7548** |
| D | Relevance reject | **4306** |
| E | Keep missing **current-version** screen | **27** |
| F | Screen-passed papers | **7315** |
| G | Screen-passed missing current FAST affiliation | **7308** |
| H | Screen-passed missing **current** audience | **7315** |
| I | Quality-router selected | **1661** |
| J | Selected with reusable current quality | **1208** |
| K | Selected needing **NEW** paid quality | **453** |
| L | Selected missing DEEP affiliation | **1649** |
| M | Papers missing HF row | **11834** (have row: 315) |
| N | Screened missing adjudication/current | **0** |
| O | Failed item_stage_runs | **0** |

**E breakdown:** never screened 27, old-version only 0  
**H breakdown:** never 3064, old version/model 4251  
**K breakdown:** never 453, old version/model 0

**Historical 38 / 468 quality estimates are superseded.** Recomputed **K = 453**.

### Audience model warning (affects H and cost)

Env `CLASSIFY_MODEL=z-ai/glm-4.6` matches **zero** existing domain rows (all historical audience used `z-ai/glm-5.3-flash`).

| Scenario | Missing audience | Notes |
|---|---:|---|
| Strict current env (glm-4.6) | **7315** | Full rescore of all screen-passed |
| Aligned to historical/screen model (glm-5.3-flash) | **5122** | Reuses 2193 current prompt-v002 rows |

**Recommendation:** set `CLASSIFY_MODEL=z-ai/glm-5.3-flash` unless intentionally migrating audience to glm-4.6.

---

## 3. Why each backlog exists

| Stage | Count | Classification | Bug? |
|---|---:|---|---|
| Relevance (B) | 295 | **never_processed** — no `paper_relevance_results`; many were Radar `INGESTED` and invisible to old status-gated relevance; PI path can score them now | No |
| Screen (E) | 27 | mostly **never_processed** (27); old-version 0 | No |
| FAST aff (G) | 7308 | **never_processed / incomplete** historical fast coverage on survivors (ISR success@v002 rare) | No |
| Audience (H) | 7315 | **model mismatch** under strict env (glm-4.6 vs stored glm-5.3-flash) + never/prompt gaps | Config decision, not cutover bug |
| Quality (K) | 453 | **ordinary historical backlog** (never 453, other-model/version 0) | No |
| DEEP (L) | 1649 | **never_processed** on quality-selected set | No |
| HF (M) | 11834 | **skipped_legitimately / never matched** — most papers are not on HF Daily | No (policy: stage attempt ≠ row per paper) |
| Adjudication (N) | 0 | already complete for screened set | No |
| Failures (O) | 0 | none requiring retry | No |

Forensic Radar statuses among no-relevance papers (informational only): `{'INGESTED': 295}`

---

## 4. Dry-run execution plan (order)

| # | Stage | Candidates / new work | Reusable | Paid? | Proj. $ | Wall h |
|---|---|---:|---:|---|---:|---:|
| 1 | relevance | 295 | 11854 | free | 0 | 0.01 |
| 2 | screen | 27 | (keeps with current screen) | **paid** | 0.0022 | 0.07 |
| 3 | affiliation_fast | 7308 | 7 | free | 0 | 4.87 |
| 4 | audience_domain | 7315 strict / 5122 aligned | — | **paid** | see §5 | 24.38 / 17.07 |
| 5 | quality routing | 7315 | all | free | 0 | ~0.01 |
| 6 | quality | 453 | 1208 | **paid** | 3.4336 | 5.66 |
| 7 | affiliation_deep | 1649 | — | free* | 0 | 8.24 |
| 8 | hf_signals | window match | 315 rows | free | 0 | 0.5 |
| 9 | adjudication | refresh | N=0 | free | 0 | 0.73 |

\*ROR/OpenAlex may consume external API quota (not LLM).

**Sequential wall estimate:** strict ~44.46 h; aligned audience ~37.15 h.

---

## 5. Paid cost breakdown

Empirical $/paper (cutover canaries): screen ~$0.00016, audience ~$0.00021, quality ~$0.00263.

| Stage | New paid units | LOW | EXPECTED | HIGH |
|---|---:|---:|---:|---:|
| Relevance | 0 | 0 | 0 | 0 |
| Screen | 27 | 0.0015 | 0.0022 | 0.0033 |
| Audience (strict glm-4.6) | 7315 | 1.0523 | 1.5032 | 2.2548 |
| Audience (aligned glm-5.3-flash) | 5122 | 0.7368 | 1.0526 | 1.5789 |
| Quality | 453 | 2.4035 | 3.4336 | 5.1504 |

**Totals (LLM)**

| Scenario | LOW | EXPECTED | HIGH | Hard cap (recommended) |
|---|---:|---:|---:|---:|
| Strict CLASSIFY=glm-4.6 | 3.4573 | 4.939 | 7.4085 | **$9.94** |
| Aligned CLASSIFY=glm-5.3-flash | 3.1419 | 4.4884 | 6.7326 | **$9.49** |

Note: `z-ai/glm-4.6` has **$0.00** entries in the local price table, so stage dry-run USD undercounts; empirical rates used for money estimates.

---

## 6. Paper 137619 (separate from normal backlog)

| Field | Value |
|---|---|
| Found | True |
| paper_id | 137619 |
| arxiv_id | 2609.03181 |
| published_at | 2026-09-02 00:00:00+00:00 |
| relevance | {'paper_id': 137619, 'decision': 'keep', 'score': 5.2, 'method': 'migrated_legacy_state', 'stage_version': 'v001'} |
| screen_gate_passed | True |
| screen_rank_mean | None |
| normal router | {'content_item_id': 137619, 'decision': 'not_selected', 'reason': 'not_selected_below_gate_percentile', 'rank_mean': 6.6667, 'rank_position': 199, 'survivors_in_window': 556, 'top_slice_keep': 83, 'gate_percentile': 15.0} |
| quality current version | False |
| quality any version | False |
| editorial would require paid | True |
| editorial est. cost | $0.0026 |
| prepared route | `editorial_nomination` |
| executed | **false** |

Normal router leaves it **not_selected** (below gate percentile). Do **not** force into top slice. If scoring is desired, use **editorial_nomination** only after approval.

---

## 7. Definition: “September 1–15 fully enriched”

- Every PI paper has relevance keep/reject OR listed relevance failure
- Every relevance-keep has current-version screen (model/stage/prompt/policy) OR listed failure
- Every screen-passed has affiliation_fast attempt at stage_version v002 recorded
- Every screen-passed has current-version audience/domain OR listed failure
- Quality routing decision available for every latest screen row
- Every quality-selected paper has current-version quality OR listed failure
- Every quality-selected paper has affiliation_deep attempt at v002
- HF stage completed for window (matches recorded; non-match OK)
- paper_intelligence_current present for all screened papers
- No unexplained skips; failures explicit; counts reproducible from PI
- 0 duplicate arxiv/doi; 0 orphan PI rows

---

## 8. Post-backfill validation plan

- Recompute A–O from PI tables; diff vs this JSON  
- Integrity: 0 dup arxiv/doi, 0 orphans, PI FKs intact  
- Quality routing reason histogram stable / selected count = I (after screen catch-up may change slightly)  
- Org coverage 7d/15d unique orgs from `paper_author_affiliations`  
- OpenAlex comparison only if cached/free  
- Newsletter/LinkedIn loaders populate from PI with catalog ON  
- **Do not** re-run paid stages for validation  

---

## 9. Proposed commands (do not run paid until approved)

```bash
export PI_USE_PAPERS_CATALOG=1 PI_WRITE_RADAR_COMPAT=0
PYTHONPATH=src python3 scripts/run_stage.py --stage relevance --from 2026-09-01 --until 2026-09-15
# PAID — approval required:
PYTHONPATH=src python3 scripts/run_stage.py --stage screen --from 2026-09-01 --until 2026-09-15 --allow-paid
PYTHONPATH=src python3 scripts/run_pipeline.py --from 2026-09-01 --until 2026-09-15 --stages affiliation_fast
PYTHONPATH=src python3 scripts/run_stage.py --stage audience_domain --from 2026-09-01 --until 2026-09-15 --allow-paid
PYTHONPATH=src python3 scripts/run_stage.py --stage quality --from 2026-09-01 --until 2026-09-15 --allow-paid --gate-percentile 15.0
PYTHONPATH=src python3 scripts/run_pipeline.py --from 2026-09-01 --until 2026-09-15 --stages affiliation_deep,hf_signals,adjudication,reports
# Optional separate (not normal router): editorial_nomination for 137619 — DO NOT RUN until approved
```

---

## 10. Approvals required before any paid bulk

- DECIDE audience model: keep CLASSIFY=z-ai/glm-4.6 (forces 7315 rescores) OR align CLASSIFY to z-ai/glm-5.3-flash (5122 new; 2193 reusable)
- Paid screen: 27 calls/papers (~$0.0022)
- Paid audience: 7315 papers (~$0.0)
- Paid quality: 453 papers (~$3.4336)
- Hard budget cap $8.44
- Optional editorial_nomination for 137619 (separate)
- Confirm HF policy: stage match attempt vs require row per paper

---

## 11. Output checklist

1. Sep 1–15 paper count **A = 12149**  
2. Backlog by stage: table in §2  
3. NEW paid calls: screen **27**, audience **7315** (strict) or **5122** (aligned), quality **453**  
4. Projected cost: §5  
5. Hard budget cap: **$9.94** (strict) / **$9.49** (aligned)  
6. Wall time: ~44.46 h strict / ~37.15 h aligned  
7. Root causes: §3  
8. Paper 137619: §6  
9. Commands: §9  
10. Completion definition: §7  
11. Validation plan: §8  
12. Approvals: §10  

**STOP — no paid bulk executed.**
