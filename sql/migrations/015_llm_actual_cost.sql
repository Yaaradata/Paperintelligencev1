-- Migration 015: store provider-reported LLM cost alongside table estimate.
-- Additive. Does not rewrite existing rows (actual_cost stays NULL for history).

BEGIN;

ALTER TABLE paper_intelligence.llm_requests
    ADD COLUMN IF NOT EXISTS actual_cost NUMERIC(12, 6);

COMMENT ON COLUMN paper_intelligence.llm_requests.estimated_cost IS
    'Table-estimated USD from PI model_prices × tokens';
COMMENT ON COLUMN paper_intelligence.llm_requests.actual_cost IS
    'Provider-reported USD from OpenRouter usage.cost when present';

COMMIT;
