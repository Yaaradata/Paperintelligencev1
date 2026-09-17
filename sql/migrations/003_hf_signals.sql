-- Hugging Face Daily Papers enrichment signals (not a second paper source).
-- Join to canonical papers by arxiv_id / content_item_id.

BEGIN;

CREATE TABLE IF NOT EXISTS paper_intelligence.paper_hf_signals (
    content_item_id        BIGINT PRIMARY KEY
        REFERENCES research_radar.content_items(id) ON DELETE CASCADE,
    arxiv_id               TEXT NOT NULL,
    hf_featured            BOOLEAN NOT NULL DEFAULT FALSE,
    hf_featured_date       DATE,
    hf_upvotes             INT,
    hf_daily_upvote_rank       INT,
    hf_num_comments        INT,
    hf_submitter           TEXT,
    linked_models_count    INT,
    linked_datasets_count  INT,
    linked_spaces_count    INT,
    github_url             TEXT,
    github_stars           INT,
    project_url            TEXT,
    hf_title               TEXT,
    pulled_at              TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    raw_response_path      TEXT,
    stage_version          TEXT,
    run_id                 UUID,
    metadata               JSONB NOT NULL DEFAULT '{}'::jsonb
);

CREATE INDEX IF NOT EXISTS ix_paper_hf_signals_arxiv
    ON paper_intelligence.paper_hf_signals (arxiv_id);
CREATE INDEX IF NOT EXISTS ix_paper_hf_signals_featured
    ON paper_intelligence.paper_hf_signals (hf_featured, hf_upvotes DESC NULLS LAST);
CREATE INDEX IF NOT EXISTS ix_paper_hf_signals_featured_date
    ON paper_intelligence.paper_hf_signals (hf_featured_date);

-- Convenience columns on current state for ranking / reports.
ALTER TABLE paper_intelligence.paper_intelligence_current
    ADD COLUMN IF NOT EXISTS hf_featured BOOLEAN,
    ADD COLUMN IF NOT EXISTS hf_upvotes INT,
    ADD COLUMN IF NOT EXISTS hf_featured_date DATE;

-- Allow Hugging Face as an external provider in request logs.
ALTER TABLE paper_intelligence.external_requests
    DROP CONSTRAINT IF EXISTS external_requests_provider_check;
ALTER TABLE paper_intelligence.external_requests
    ADD CONSTRAINT external_requests_provider_check
    CHECK (provider IN ('arxiv', 'openalex', 'ror', 'openrouter', 'huggingface'));

COMMIT;
