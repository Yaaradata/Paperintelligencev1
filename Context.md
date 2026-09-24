# Context — PaperIntelligenceV1 (`dev/subha`)

**Updated:** 2026-09-24  
**Worktree:** `worktrees/subha`

Decisions and golden identity for the next thread. Pipeline shape summary still also lives in `PROJECT.md` (that file is **behind** on quality engines and golden naming — see note there).

---

## Golden dataset (find this without being told)

| | |
|---|---|
| **Name / version** | `quality_scoring_golden_v1` |
| **Paths** | `golden/quality_scoring_golden_v1.xlsx`, `golden/quality_scoring_golden_v1.csv` |
| **Table** | `paper_intelligence.golden_human_scores` |
| **Gates** | quality scoring changes (rubric dims + composite / verdict) |
| **Baseline** | `reports/golden/baseline_v1.md` |
| **README** | `golden/README.md` |

**One-line rule:** scoring changes are measured against **human** labels, **never** against another model's scores.

---

## Decisions made (2026-09-24)

| Decision | Evidence | Date |
|---|---|---|
| Keep **Terra** as primary quality engine (G2 accepted; no engine switch) | `reports/golden/g3_decision.md`; intersection baseline `reports/golden/baseline_v1.md` | 2026-09-24 |
| Do **not** ship composite weight / policy / prompt changes in G3 | `reports/golden/g3_decision.md`, `reports/golden/g3c_weight_fit.md` (proposals only; settings unchanged) | 2026-09-24 |
| Verifier gate uses **3-engine intersection** (n=151); drop circular `ai_relevance` from comparison | `reports/golden/engine_comparison.md`, `baseline_v1.md` | 2026-09-24 |
| Ship **`QUALITY_ENGINE=terra\|jev_glm`** (Jev v001 scores + GLM prose); default remains **terra** | `src/paper_intelligence/common/config.py`, `quality/jev_glm_engine.py`, `tests/unit/test_quality_engine_jev_glm.py` | 2026-09-24 |
| Name/lock golden sample as **`quality_scoring_golden_v1`** (xlsx+csv); table stays `golden_human_scores` | `golden/README.md`; migration `022_golden_dataset_version.sql` (written, not applied) | 2026-09-24 |
| Human labels imported: labeller `subha`, round `v1`, n=200, blind | DB `golden_human_scores` count=200; labelled 2026-09-24 | 2026-09-24 |

---

## Decisions still open

| Topic | Options | Cost / risk |
|---|---|---|
| **Ship refit composite weights** (G3c a/b/c) | (i) adopt ridge/logistic/mixed weights · (ii) keep current weights | Shipping without human–human ceiling may overfit; waiting delays rank quality. Held-out ρ~0.61–0.65 looks strong but ceiling unknown. |
| **Screen-gate policy** after G3b | (i) soften/bypass for high-Terra survivors · (ii) keep gate · (iii) post-gate rescue path | Softening increases paid quality volume/cost; keeping gate continues dropping human shortlist/winners (6/24 in G3b). |
| **Default `QUALITY_ENGINE`** | keep `terra` · flip default to `jev_glm` | Flip changes production scores and adjudication model-guard behaviour; keep = opt-in only via env. |
| **org_boost magnitude vs Terra spread** (carried) | rescale boost · leave formula | Affects `final_score` ranking vs quality-only tops. |

---

## Conflicts (question + alternatives — no recommendation)

**Q1.** After Ranjith finishes `golden/double_label_30.xlsx`, which path should lock first?

- **A.** Adopt a G3c refit composite (which of a / b / c?) against the human–human ceiling.
- **B.** Change screen-gate / rescue policy using G3b evidence.
- **C.** Leave weights and gate unchanged; accept current composite Spearman and gate drop rate.

**Q2.** Should production quality runs for new days use `QUALITY_ENGINE=jev_glm` while Terra remains the locked "primary" for gate comparison?

- **A.** Terra only in production until a formal engine decision revisits G2.
- **B.** `jev_glm` for production scoring/prose; Terra retained only as golden baseline comparator.
- **C.** Dual-run / shadow indefinitely (cost ≈ 2× quality).

---

## Pointers

- Wrap-up procedure: `docs/WRAP_UP_MY_DAY.md`
- Flow diagram: `docs/pipeline_flow.md`
- G3 stop: `reports/golden/g3_decision.md`
