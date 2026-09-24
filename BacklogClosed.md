# Backlog closed — PaperIntelligenceV1 (`dev/subha`)

**Updated:** 2026-09-24

Items below were closed with **verifier / report evidence**. Do not re-open without a new decision.

| ID | Item | Closed | Verifier evidence |
|---|---|---|---|
| G2-ENGINE | Keep Terra primary; no engine switch from golden comparison | 2026-09-24 | `reports/golden/g3_decision.md` (G2 accepted); `reports/golden/baseline_v1.md`; `reports/golden/engine_comparison.md` |
| G3A-BASELINE | Intersection baseline; remove circular ai_relevance from gate tables | 2026-09-24 | `reports/golden/engine_comparison.md`; regenerated `baseline_v1.md` |
| G3-STOP | No weight/policy/prompt/model ship in G3 | 2026-09-24 | `reports/golden/g3_decision.md` STOP section; settings unchanged |
| G1-IMPORT | Import 200 blind human labels (`subha` / `v1`) | 2026-09-24 | `golden_human_scores` n=200; strata counts in `golden/README.md`; files `quality_scoring_golden_v1.xlsx` |
| JEV-GLM-WIRE | Implement `QUALITY_ENGINE=jev_glm` (Jev scores + GLM prose) with tests; default terra | 2026-09-24 | `tests/unit/test_quality_engine_jev_glm.py`; code under `quality/jev_glm_engine.py` + stage routing (unit-verified; production default unchanged) |

Older closed / deferred funnel items remain summarised in historical `PROJECT.md` § “This cycle (funnel correction) — Done”.
