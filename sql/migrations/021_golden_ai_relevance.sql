-- Migration 021: add h_ai_relevance to golden_human_scores.
-- Additive only. Apply once after 020.

BEGIN;

ALTER TABLE paper_intelligence.golden_human_scores
    ADD COLUMN IF NOT EXISTS h_ai_relevance NUMERIC(3, 1);

COMMENT ON COLUMN paper_intelligence.golden_human_scores.h_ai_relevance IS
    'Human (or backfilled screen) AI/ML relevance 0–10 in 0.5 steps; screen-aligned.';

COMMIT;

-- VERIFY
-- SELECT column_name FROM information_schema.columns
-- WHERE table_schema='paper_intelligence' AND table_name='golden_human_scores'
--   AND column_name='h_ai_relevance';
