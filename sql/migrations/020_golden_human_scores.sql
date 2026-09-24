-- Migration 020: golden human scores (append-only human labels).
-- DO NOT auto-apply from app startup. Apply manually after review.
--
-- Purpose: store blind human labels for the golden set. UNIQUE
-- (paper_id, labeller, label_round) — re-import of the same key must fail,
-- never overwrite.

BEGIN;

CREATE TABLE IF NOT EXISTS paper_intelligence.golden_human_scores (
    id                              BIGSERIAL PRIMARY KEY,
    paper_id                        BIGINT NOT NULL
        REFERENCES paper_intelligence.papers (paper_id),
    arxiv_id                        TEXT,
    labeller                        TEXT NOT NULL,
    label_round                     TEXT NOT NULL DEFAULT 'v1',
    blind                           BOOLEAN NOT NULL DEFAULT TRUE,
    sample_stratum                  TEXT,
    h_ai_relevance                  NUMERIC(3, 1),
    h_technical_significance        NUMERIC(3, 1),
    h_apparent_novelty              NUMERIC(3, 1),
    h_practical_applicability       NUMERIC(3, 1),
    h_professional_value            NUMERIC(3, 1),
    h_learning_value                NUMERIC(3, 1),
    h_evidence_strength             NUMERIC(3, 1),
    h_tech_relevance                NUMERIC(3, 1),
    h_product_relevance             NUMERIC(3, 1),
    h_final_score                   NUMERIC(3, 1),
    h_domain                        TEXT,
    h_application_domain            TEXT,
    h_newsletter_verdict            TEXT,
    h_reject_reason                 TEXT,
    h_notes                         TEXT,
    labelled_at                     TIMESTAMPTZ NOT NULL DEFAULT now(),
    CONSTRAINT golden_human_scores_unique_label
        UNIQUE (paper_id, labeller, label_round),
    CONSTRAINT golden_human_scores_verdict_chk
        CHECK (
            h_newsletter_verdict IS NULL
            OR h_newsletter_verdict IN (
                'winner_material', 'shortlist', 'maybe', 'reject'
            )
        )
);

CREATE INDEX IF NOT EXISTS ix_golden_human_scores_round
    ON paper_intelligence.golden_human_scores (label_round, labelled_at DESC);

CREATE INDEX IF NOT EXISTS ix_golden_human_scores_paper
    ON paper_intelligence.golden_human_scores (paper_id);

COMMENT ON TABLE paper_intelligence.golden_human_scores IS
    'Append-only human golden labels. UNIQUE (paper_id, labeller, label_round); never upsert.';

COMMIT;

-- =============================================================================
-- VERIFY (run after apply; expect one row, all checks true)
-- =============================================================================
-- SELECT
--   to_regclass('paper_intelligence.golden_human_scores') IS NOT NULL AS table_exists,
--   EXISTS (
--     SELECT 1 FROM pg_constraint
--     WHERE conname = 'golden_human_scores_unique_label'
--   ) AS unique_key_exists,
--   (
--     SELECT count(*) FROM information_schema.columns
--     WHERE table_schema = 'paper_intelligence'
--       AND table_name = 'golden_human_scores'
--       AND column_name IN (
--         'paper_id','arxiv_id','labeller','label_round','blind','sample_stratum',
--         'h_ai_relevance',
--         'h_technical_significance','h_apparent_novelty','h_practical_applicability',
--         'h_professional_value','h_learning_value','h_evidence_strength',
--         'h_tech_relevance','h_product_relevance','h_final_score',
--         'h_domain','h_application_domain','h_newsletter_verdict',
--         'h_reject_reason','h_notes','labelled_at'
--       )
--   ) = 22 AS all_columns_present;
-- =============================================================================
