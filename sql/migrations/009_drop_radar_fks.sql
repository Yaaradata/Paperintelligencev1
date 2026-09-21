-- Migration 009: Drop PI → Radar content_items foreign keys.
-- Prerequisite: migration 008 PI papers FKs validated + PI-only operation proven.
-- Does NOT drop Radar tables or data.
--
-- Apply:
--   psql "$DATABASE_URL" -v ON_ERROR_STOP=1 -f sql/migrations/009_drop_radar_fks.sql

BEGIN;

-- Confirm PI papers FKs exist before dropping Radar FKs
DO $$
DECLARE
  missing text;
BEGIN
  SELECT string_agg(c, ', ') INTO missing
  FROM unnest(ARRAY[
    'item_stage_runs_content_item_id_papers_fkey',
    'external_requests_content_item_id_papers_fkey',
    'paper_authors_content_item_id_papers_fkey',
    'papers_people_content_item_id_papers_fkey',
    'paper_author_affiliations_content_item_id_papers_fkey',
    'paper_classification_results_content_item_id_papers_fkey',
    'paper_intelligence_current_content_item_id_papers_fkey',
    'golden_set_items_content_item_id_papers_fkey',
    'golden_labels_content_item_id_papers_fkey',
    'evaluation_results_content_item_id_papers_fkey',
    'paper_hf_signals_content_item_id_papers_fkey'
  ]) AS c
  WHERE NOT EXISTS (
    SELECT 1 FROM pg_constraint
    WHERE conname = c
      AND connamespace = 'paper_intelligence'::regnamespace
  );
  IF missing IS NOT NULL THEN
    RAISE EXCEPTION 'missing PI papers FKs before Radar FK drop: %', missing;
  END IF;
END $$;

ALTER TABLE paper_intelligence.item_stage_runs
  DROP CONSTRAINT IF EXISTS item_stage_runs_content_item_id_fkey;
ALTER TABLE paper_intelligence.external_requests
  DROP CONSTRAINT IF EXISTS external_requests_content_item_id_fkey;
ALTER TABLE paper_intelligence.paper_authors
  DROP CONSTRAINT IF EXISTS paper_authors_content_item_id_fkey;
ALTER TABLE paper_intelligence.papers_people
  DROP CONSTRAINT IF EXISTS papers_people_content_item_id_fkey;
ALTER TABLE paper_intelligence.paper_author_affiliations
  DROP CONSTRAINT IF EXISTS paper_author_affiliations_content_item_id_fkey;
ALTER TABLE paper_intelligence.paper_classification_results
  DROP CONSTRAINT IF EXISTS paper_classification_results_content_item_id_fkey;
ALTER TABLE paper_intelligence.paper_intelligence_current
  DROP CONSTRAINT IF EXISTS paper_intelligence_current_content_item_id_fkey;
ALTER TABLE paper_intelligence.golden_set_items
  DROP CONSTRAINT IF EXISTS golden_set_items_content_item_id_fkey;
ALTER TABLE paper_intelligence.golden_labels
  DROP CONSTRAINT IF EXISTS golden_labels_content_item_id_fkey;
ALTER TABLE paper_intelligence.evaluation_results
  DROP CONSTRAINT IF EXISTS evaluation_results_content_item_id_fkey;
ALTER TABLE paper_intelligence.paper_hf_signals
  DROP CONSTRAINT IF EXISTS paper_hf_signals_content_item_id_fkey;

COMMIT;
