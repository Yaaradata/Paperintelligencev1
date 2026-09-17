-- Migration 005: explicit quality_status on current-state projection.
-- final_score NULL previously conflated "never selected for quality" with "low quality".

BEGIN;

ALTER TABLE paper_intelligence.paper_intelligence_current
    ADD COLUMN IF NOT EXISTS quality_status TEXT;

DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1
        FROM pg_constraint
        WHERE conname = 'paper_intelligence_current_quality_status_check'
    ) THEN
        ALTER TABLE paper_intelligence.paper_intelligence_current
            ADD CONSTRAINT paper_intelligence_current_quality_status_check
            CHECK (
                quality_status IS NULL
                OR quality_status IN ('not_selected', 'scored', 'failed', 'skipped')
            );
    END IF;
END $$;

-- Backfill from existing scores: scored when quality_score present, else not_selected
-- for rows that have screen_score (entered the funnel) without quality.
UPDATE paper_intelligence.paper_intelligence_current
SET quality_status = CASE
    WHEN quality_score IS NOT NULL THEN 'scored'
    WHEN screen_score IS NOT NULL THEN 'not_selected'
    ELSE 'skipped'
END
WHERE quality_status IS NULL;

COMMIT;
