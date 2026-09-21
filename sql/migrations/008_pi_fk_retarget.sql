-- Migration 008: Add PI papers FKs alongside existing Radar content_items FKs.
-- Additive only. Does NOT drop Radar FKs (that is migration 009 after soak).
--
-- Apply:
--   psql "$DATABASE_URL" -v ON_ERROR_STOP=1 -f sql/migrations/008_pi_fk_retarget.sql
--
-- Policy: ON DELETE NO ACTION (no cross-system cascading deletes).

BEGIN;

-- ---------------------------------------------------------------------------
-- Orphan guards (must all be 0 or this transaction aborts)
-- ---------------------------------------------------------------------------
DO $$
DECLARE
  orphan_count bigint;
  tbl text;
BEGIN
  FOREACH tbl IN ARRAY ARRAY[
    'item_stage_runs',
    'external_requests',
    'paper_authors',
    'papers_people',
    'paper_author_affiliations',
    'paper_classification_results',
    'paper_intelligence_current',
    'golden_set_items',
    'golden_labels',
    'evaluation_results',
    'paper_hf_signals'
  ]
  LOOP
    EXECUTE format(
      'SELECT count(*) FROM paper_intelligence.%I x
       WHERE x.content_item_id IS NOT NULL
         AND NOT EXISTS (
           SELECT 1 FROM paper_intelligence.papers p
           WHERE p.paper_id = x.content_item_id
         )',
      tbl
    ) INTO orphan_count;
    IF orphan_count <> 0 THEN
      RAISE EXCEPTION 'orphan content_item_id in paper_intelligence.%: %', tbl, orphan_count;
    END IF;
  END LOOP;
END $$;

-- ---------------------------------------------------------------------------
-- Add PI FKs (NOT VALID → VALIDATE) without dropping Radar FKs
-- ---------------------------------------------------------------------------

ALTER TABLE paper_intelligence.item_stage_runs
  DROP CONSTRAINT IF EXISTS item_stage_runs_content_item_id_papers_fkey;
ALTER TABLE paper_intelligence.item_stage_runs
  ADD CONSTRAINT item_stage_runs_content_item_id_papers_fkey
  FOREIGN KEY (content_item_id)
  REFERENCES paper_intelligence.papers(paper_id)
  ON DELETE NO ACTION
  NOT VALID;
ALTER TABLE paper_intelligence.item_stage_runs
  VALIDATE CONSTRAINT item_stage_runs_content_item_id_papers_fkey;

ALTER TABLE paper_intelligence.external_requests
  DROP CONSTRAINT IF EXISTS external_requests_content_item_id_papers_fkey;
ALTER TABLE paper_intelligence.external_requests
  ADD CONSTRAINT external_requests_content_item_id_papers_fkey
  FOREIGN KEY (content_item_id)
  REFERENCES paper_intelligence.papers(paper_id)
  ON DELETE NO ACTION
  NOT VALID;
ALTER TABLE paper_intelligence.external_requests
  VALIDATE CONSTRAINT external_requests_content_item_id_papers_fkey;

ALTER TABLE paper_intelligence.paper_authors
  DROP CONSTRAINT IF EXISTS paper_authors_content_item_id_papers_fkey;
ALTER TABLE paper_intelligence.paper_authors
  ADD CONSTRAINT paper_authors_content_item_id_papers_fkey
  FOREIGN KEY (content_item_id)
  REFERENCES paper_intelligence.papers(paper_id)
  ON DELETE NO ACTION
  NOT VALID;
ALTER TABLE paper_intelligence.paper_authors
  VALIDATE CONSTRAINT paper_authors_content_item_id_papers_fkey;

ALTER TABLE paper_intelligence.papers_people
  DROP CONSTRAINT IF EXISTS papers_people_content_item_id_papers_fkey;
ALTER TABLE paper_intelligence.papers_people
  ADD CONSTRAINT papers_people_content_item_id_papers_fkey
  FOREIGN KEY (content_item_id)
  REFERENCES paper_intelligence.papers(paper_id)
  ON DELETE NO ACTION
  NOT VALID;
ALTER TABLE paper_intelligence.papers_people
  VALIDATE CONSTRAINT papers_people_content_item_id_papers_fkey;

ALTER TABLE paper_intelligence.paper_author_affiliations
  DROP CONSTRAINT IF EXISTS paper_author_affiliations_content_item_id_papers_fkey;
ALTER TABLE paper_intelligence.paper_author_affiliations
  ADD CONSTRAINT paper_author_affiliations_content_item_id_papers_fkey
  FOREIGN KEY (content_item_id)
  REFERENCES paper_intelligence.papers(paper_id)
  ON DELETE NO ACTION
  NOT VALID;
ALTER TABLE paper_intelligence.paper_author_affiliations
  VALIDATE CONSTRAINT paper_author_affiliations_content_item_id_papers_fkey;

ALTER TABLE paper_intelligence.paper_classification_results
  DROP CONSTRAINT IF EXISTS paper_classification_results_content_item_id_papers_fkey;
ALTER TABLE paper_intelligence.paper_classification_results
  ADD CONSTRAINT paper_classification_results_content_item_id_papers_fkey
  FOREIGN KEY (content_item_id)
  REFERENCES paper_intelligence.papers(paper_id)
  ON DELETE NO ACTION
  NOT VALID;
ALTER TABLE paper_intelligence.paper_classification_results
  VALIDATE CONSTRAINT paper_classification_results_content_item_id_papers_fkey;

ALTER TABLE paper_intelligence.paper_intelligence_current
  DROP CONSTRAINT IF EXISTS paper_intelligence_current_content_item_id_papers_fkey;
ALTER TABLE paper_intelligence.paper_intelligence_current
  ADD CONSTRAINT paper_intelligence_current_content_item_id_papers_fkey
  FOREIGN KEY (content_item_id)
  REFERENCES paper_intelligence.papers(paper_id)
  ON DELETE NO ACTION
  NOT VALID;
ALTER TABLE paper_intelligence.paper_intelligence_current
  VALIDATE CONSTRAINT paper_intelligence_current_content_item_id_papers_fkey;

ALTER TABLE paper_intelligence.golden_set_items
  DROP CONSTRAINT IF EXISTS golden_set_items_content_item_id_papers_fkey;
ALTER TABLE paper_intelligence.golden_set_items
  ADD CONSTRAINT golden_set_items_content_item_id_papers_fkey
  FOREIGN KEY (content_item_id)
  REFERENCES paper_intelligence.papers(paper_id)
  ON DELETE NO ACTION
  NOT VALID;
ALTER TABLE paper_intelligence.golden_set_items
  VALIDATE CONSTRAINT golden_set_items_content_item_id_papers_fkey;

ALTER TABLE paper_intelligence.golden_labels
  DROP CONSTRAINT IF EXISTS golden_labels_content_item_id_papers_fkey;
ALTER TABLE paper_intelligence.golden_labels
  ADD CONSTRAINT golden_labels_content_item_id_papers_fkey
  FOREIGN KEY (content_item_id)
  REFERENCES paper_intelligence.papers(paper_id)
  ON DELETE NO ACTION
  NOT VALID;
ALTER TABLE paper_intelligence.golden_labels
  VALIDATE CONSTRAINT golden_labels_content_item_id_papers_fkey;

ALTER TABLE paper_intelligence.evaluation_results
  DROP CONSTRAINT IF EXISTS evaluation_results_content_item_id_papers_fkey;
ALTER TABLE paper_intelligence.evaluation_results
  ADD CONSTRAINT evaluation_results_content_item_id_papers_fkey
  FOREIGN KEY (content_item_id)
  REFERENCES paper_intelligence.papers(paper_id)
  ON DELETE NO ACTION
  NOT VALID;
ALTER TABLE paper_intelligence.evaluation_results
  VALIDATE CONSTRAINT evaluation_results_content_item_id_papers_fkey;

ALTER TABLE paper_intelligence.paper_hf_signals
  DROP CONSTRAINT IF EXISTS paper_hf_signals_content_item_id_papers_fkey;
ALTER TABLE paper_intelligence.paper_hf_signals
  ADD CONSTRAINT paper_hf_signals_content_item_id_papers_fkey
  FOREIGN KEY (content_item_id)
  REFERENCES paper_intelligence.papers(paper_id)
  ON DELETE NO ACTION
  NOT VALID;
ALTER TABLE paper_intelligence.paper_hf_signals
  VALIDATE CONSTRAINT paper_hf_signals_content_item_id_papers_fkey;

COMMIT;
