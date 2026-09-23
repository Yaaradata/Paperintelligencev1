-- Migration 019: seat scores on paper_intelligence_current (Phase 7a).
-- Additive only. Keeps audiences column; never map old labels to seat scores.
-- tech_relevance / product_relevance filled by adjudication from latest
-- classification rows with policy_version=v002 (prompt v003) only.

BEGIN;

ALTER TABLE paper_intelligence.paper_intelligence_current
    ADD COLUMN IF NOT EXISTS tech_relevance NUMERIC(4, 1);

ALTER TABLE paper_intelligence.paper_intelligence_current
    ADD COLUMN IF NOT EXISTS product_relevance NUMERIC(4, 1);

ALTER TABLE paper_intelligence.paper_intelligence_current
    ADD COLUMN IF NOT EXISTS audience_policy_version TEXT;

COMMENT ON COLUMN paper_intelligence.paper_intelligence_current.tech_relevance IS
    'Seat score 0–10 (0.5 steps) from classification policy v002; null if not scored under v002.';
COMMENT ON COLUMN paper_intelligence.paper_intelligence_current.product_relevance IS
    'Seat score 0–10 (0.5 steps) from classification policy v002; null if not scored under v002.';
COMMENT ON COLUMN paper_intelligence.paper_intelligence_current.audience_policy_version IS
    'classification policy version that produced seat scores (e.g. v002); null when only legacy audience labels exist.';

COMMIT;
