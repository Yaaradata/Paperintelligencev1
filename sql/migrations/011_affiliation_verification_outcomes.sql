-- Migration 011: Extend affiliation verification outcomes for phased runs.
-- Additive. Allows needs_openalex_lookup / needs_pdf_review.

BEGIN;

ALTER TABLE paper_intelligence.affiliation_verifications
    DROP CONSTRAINT IF EXISTS affiliation_verifications_outcome_check;

ALTER TABLE paper_intelligence.affiliation_verifications
    ADD CONSTRAINT affiliation_verifications_outcome_check
    CHECK (
        outcome IS NULL OR outcome = ANY (ARRAY[
            'verified_agreement'::text,
            'partial_agreement'::text,
            'verified_html_primary'::text,
            'verified_openalex_primary'::text,
            'conflict'::text,
            'unresolved'::text,
            'needs_openalex_lookup'::text,
            'needs_pdf_review'::text
        ])
    );

COMMIT;
