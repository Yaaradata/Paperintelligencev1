-- 004_rename_hf_daily_upvote_rank.sql
-- Rename misleading hf_trending_rank → hf_daily_upvote_rank.
-- Values preserved (same-day upvote rank, not HF global trending).

BEGIN;

DO $$
BEGIN
    IF EXISTS (
        SELECT 1 FROM information_schema.columns
        WHERE table_schema = 'paper_intelligence'
          AND table_name = 'paper_hf_signals'
          AND column_name = 'hf_trending_rank'
    ) AND NOT EXISTS (
        SELECT 1 FROM information_schema.columns
        WHERE table_schema = 'paper_intelligence'
          AND table_name = 'paper_hf_signals'
          AND column_name = 'hf_daily_upvote_rank'
    ) THEN
        ALTER TABLE paper_intelligence.paper_hf_signals
            RENAME COLUMN hf_trending_rank TO hf_daily_upvote_rank;
    END IF;
END $$;

COMMIT;
