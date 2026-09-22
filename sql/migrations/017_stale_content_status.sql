-- Migration 017: allow quality_status='stale_content'.
-- Additive CHECK replace (same pattern as 014).

BEGIN;

ALTER TABLE paper_intelligence.paper_intelligence_current
    DROP CONSTRAINT IF EXISTS paper_intelligence_current_quality_status_check;

ALTER TABLE paper_intelligence.paper_intelligence_current
    ADD CONSTRAINT paper_intelligence_current_quality_status_check
    CHECK (
        quality_status IS NULL
        OR quality_status = ANY (ARRAY[
            'not_selected'::text,
            'scored'::text,
            'failed'::text,
            'skipped'::text,
            'pending'::text,
            'stale_content'::text
        ])
    );

COMMIT;
