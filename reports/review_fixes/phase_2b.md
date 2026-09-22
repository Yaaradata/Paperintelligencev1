# Phase 2b stop report — Cost accuracy

**Branch:** `dev/subha`  
**Date:** 2026-09-22  
**No paid calls.**

---

## Price updates (verified OpenRouter 2026-09-22)

| Model | Old (code) | New (list) | Source |
|---|---:|---:|---|
| `z-ai/glm-5.3-flash` | 0.15 / 0.50 | **0.15 / 0.50** (unchanged) | https://openrouter.ai/z-ai/glm-5.3-flash |
| `z-ai/glm-4.6` | 0.15 / 0.50 | **0.43 / 1.75** | https://openrouter.ai/z-ai/glm-4.6 |
| `openai/gpt-5.6-sol` | 1.25 / 10.00 | **5.00 / 30.00** | https://openrouter.ai/openai/gpt-5.6-sol |

Note on flash: 50% promo until 2026-09-09 16:00 UTC — earlier runs may have billed ~half of table.

---

## Provider cost capture

- OpenRouter client reads `usage.cost` → `actual_cost` on `LLMResponse`.
- Table estimate remains `estimated_cost`.
- Logged on `llm_requests`: `estimated_cost` + new `actual_cost` (migration **015**).
- Request body sets `usage.include` (documented no-op on current API; usage is always returned).
- **Budget cap** uses `actual_cost` when present, else table estimate. Dry-run projections still use the table.
- Run summary warns if provider vs table diverge by **>20%** over the run; prints both totals.

---

## Sep 1–15 dry-run under NEW prices

Models: `SCREEN=z-ai/glm-5.3-flash`, `CLASSIFY=z-ai/glm-5.3-flash`, `QUALITY=openai/gpt-5.6-sol`.

### Residual (skip already-done — what a normal resume would cost)

| Stage | Candidates | Projected |
|---|---:|---:|
| screen | 27 | **$0.002** |
| audience_domain | 5,122 | **$0.61** |
| quality | 453 | **$10.56** |
| **Total residual** | | **~$11.17** |

**Quality alone ($10.56) exceeds a $10 cap.** Reset the cap if you want residual quality to finish in one run (suggest ≥ $11 for quality-only, or ≥ $12 for residual screen+audience+quality).

### Full reprocess (all window candidates)

| Stage | Candidates | Projected |
|---|---:|---:|
| screen | 7,548 | **$0.63** |
| audience_domain | 7,315 | **$0.87** |
| quality | 1,661 | **$38.93** |
| **Total reprocess** | | **~$40.43** |

---

## Historical audit (read-only)

Script: `scripts/audit_llm_cost_repricing.py`  
Outputs: `reports/review_fixes/llm_cost_repricing_audit.{json,md}`

| | |
|---|---|
| Calls | 1,282 |
| Old table total | **$6.37** |
| New table total | **$17.04** (~2.7×) |
| Quality (`gpt-5.6-sol`) alone | old $4.79 → new **$15.36** (×3.21) |
| glm-4.6 judge | old $0.04 → new **$0.14** (×3.35) |

Run IDs + timestamps are listed in the audit MD for matching OpenRouter activity.

---

## Files

- `src/paper_intelligence/common/config.py` — prices + source comments  
- `src/paper_intelligence/openrouter/client.py` — provider cost  
- `src/paper_intelligence/common/llm_stage.py` / `batch_runner.py` / `budget.py`  
- `src/paper_intelligence/observability/runs.py` — persist `actual_cost`  
- `sql/migrations/015_llm_actual_cost.sql`  
- `scripts/audit_llm_cost_repricing.py`  
- `tests/unit/test_cost_accuracy.py`  
- stage `add_call` wiring in screen / audience_domain / quality  

**Tests:** 162 passed (full unit suite).

**Ops:** apply migration **015** before paid runs that should store `actual_cost`.

---

## STOP

Phase 2b complete. Awaiting approval for Phase 3 (and your new `--max-cost-usd` if resetting).
