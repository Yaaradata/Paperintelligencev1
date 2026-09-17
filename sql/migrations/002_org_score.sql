-- 002_org_score.sql
-- Adds the institutional-standing columns that adjudication writes.
--
-- The organisation score is a REPORTING value derived from verified affiliation
-- evidence. It is applied as a capped additive boost AFTER blinded quality
-- scoring, never as an input to it, so a well-known lab cannot inflate the
-- rubric itself.
--
-- Idempotent. Apply manually:
--   psql "$DATABASE_URL" -f sql/migrations/002_org_score.sql

BEGIN;

ALTER TABLE paper_intelligence.paper_intelligence_current
    ADD COLUMN IF NOT EXISTS organisation_score   NUMERIC(4, 1),
    ADD COLUMN IF NOT EXISTS org_boost            NUMERIC(4, 3),
    ADD COLUMN IF NOT EXISTS person_boost         NUMERIC(4, 3),
    ADD COLUMN IF NOT EXISTS final_score          NUMERIC(4, 1),
    ADD COLUMN IF NOT EXISTS top_organisation_id  BIGINT
        REFERENCES paper_intelligence.organisations(id) ON DELETE SET NULL,
    ADD COLUMN IF NOT EXISTS adjudication_json    JSONB NOT NULL DEFAULT '{}'::jsonb,
    ADD COLUMN IF NOT EXISTS run_id               UUID
        REFERENCES paper_intelligence.pipeline_runs(run_id) ON DELETE SET NULL;

CREATE INDEX IF NOT EXISTS ix_pic_final_score
    ON paper_intelligence.paper_intelligence_current (final_score DESC NULLS LAST);

CREATE INDEX IF NOT EXISTS ix_pic_top_org
    ON paper_intelligence.paper_intelligence_current (top_organisation_id)
    WHERE top_organisation_id IS NOT NULL;

COMMIT;
