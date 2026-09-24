-- Migration 022: dataset_version on golden_human_scores.
-- DO NOT auto-apply. Apply manually after review.
--
-- Note: migration 021 already exists (h_ai_relevance). dataset_version is 022.
-- Default identifies the quality-scoring golden sample quality_scoring_golden_v1.

BEGIN;

ALTER TABLE paper_intelligence.golden_human_scores
    ADD COLUMN IF NOT EXISTS dataset_version TEXT NOT NULL DEFAULT 'quality_scoring_golden_v1';

COMMENT ON COLUMN paper_intelligence.golden_human_scores.dataset_version IS
    'Golden sample identity. Corrections reuse dataset_version with a new label_round; '
    'a new sample or labeller set is a new dataset_version (e.g. quality_scoring_golden_v2).';

CREATE INDEX IF NOT EXISTS ix_golden_human_scores_dataset
    ON paper_intelligence.golden_human_scores (dataset_version, label_round);

COMMIT;

-- =============================================================================
-- VERIFY (run after apply)
-- =============================================================================
-- SELECT column_name, column_default
-- FROM information_schema.columns
-- WHERE table_schema = 'paper_intelligence'
--   AND table_name = 'golden_human_scores'
--   AND column_name = 'dataset_version';
-- =============================================================================
