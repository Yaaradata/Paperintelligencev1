-- Migration 013: Store judge-rejected organisation IDs for adjudication exclusion.
-- Additive. Original HTML/OpenAlex evidence rows remain unchanged.

BEGIN;

ALTER TABLE paper_intelligence.affiliation_judgments
    ADD COLUMN IF NOT EXISTS rejected_organisation_ids BIGINT[] NOT NULL DEFAULT '{}';

COMMIT;
