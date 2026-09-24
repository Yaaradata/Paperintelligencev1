# State — PaperIntelligenceV1 (`dev/subha`)

**Updated:** 2026-09-24

---

## Golden (always visible)

- **Dataset:** `quality_scoring_golden_v1` → `golden/quality_scoring_golden_v1.xlsx` / `.csv`
- **Gates:** quality scoring (rubric + composite)
- **Rule:** measure scoring changes against **human** labels, never against another model
- **Baseline:** `reports/golden/baseline_v1.md`
- **Migration 022** (`dataset_version`) — **written, not applied**

---

## Running today

| Job | Status | Notes |
|---|---|---|
| Balance pipeline Sep 21–23 (`run_jev_glm_balance_sep21_23_detached.sh`) | Was running through affiliation_fast → later stages | Log: `reports/golden/jev_glm_balance_sep21_23_pipeline.log` · cap $5 · `QUALITY_ENGINE=jev_glm` |
| Quality reprocess Sep 21–23 | **Finished** (exit 0) | 456 `jev_glm` quality rows adjudicated; `write_jev_glm_report.py` failed on SQL (`c.paper_id`); `run_stage.py` has no `reports` stage | Log: `reports/golden/jev_glm_quality_rerun.log` |

Re-check with `pgrep -af 'run_pipeline.py|run_stage.py'` before assuming idle.

---

## Wired but off

| Feature | Flag | Default |
|---|---|---|
| Jev scores + GLM prose quality path | `QUALITY_ENGINE` | **`terra`** (`jev_glm` opt-in) |
| Product slice into quality router | `ROUTER_PRODUCT_SLICE_PCT` | **0** (off) |
| S3 relevance rejects | `S3_ARCHIVE_ENABLED` (+ bucket/prefix env) | off unless enabled |

---

## Built but unwired / incomplete

| Item | Notes |
|---|---|
| G3c weight proposals | Reports only; `settings` / policies **unchanged** |
| `write_jev_glm_report.py` | Script present; funnel SQL bug (`c.paper_id`) — report not produced |
| `run_stage.py --stage reports` | Unknown stage (reports via pipeline path / other entry) |
| `double_label_30` | Workbook ready; Ranjith labels not imported |
| Migration 022 `dataset_version` | File only — **DDL not applied** |

---

## Next unblocked item

1. Fix `write_jev_glm_report.py` SQL + regenerate Sep 21–23 jev_glm report **or**
2. Apply migration 022 when ops ready **or**
3. Import Ranjith `double_label_30` when labelled  

(Do not ship weights or flip `QUALITY_ENGINE` default without resolving Context.md open decisions.)

---

## Funnel snapshot (Sep 21–23, last known)

- Relevance: 1561 keep / 893 reject
- Screen: completed for balance pending set; quality `jev_glm` partial then reprocess 456
- Full balance pipeline: check live process / log for audience → quality completion
