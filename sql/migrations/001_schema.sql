BEGIN;

-- PaperIntelligenceV1 canonical schema.
-- Reads existing research_radar.content_items / paper_metadata; does not duplicate them.
-- Principle: raw evidence, model outputs, adjudication, and current state stay separate.

CREATE SCHEMA IF NOT EXISTS paper_intelligence;

-- ---------------------------------------------------------------------------
-- Run provenance (foundational — every enrichment stage links here)
-- ---------------------------------------------------------------------------

CREATE TABLE IF NOT EXISTS paper_intelligence.pipeline_runs (
    run_id           UUID PRIMARY KEY,
    pipeline_name    TEXT NOT NULL,
    trigger_type     TEXT NOT NULL,
    code_commit_sha  TEXT,
    started_at       TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    ended_at         TIMESTAMPTZ,
    status           TEXT NOT NULL DEFAULT 'running'
        CHECK (status IN ('running', 'succeeded', 'failed', 'partial', 'cancelled')),
    items_input      INTEGER NOT NULL DEFAULT 0,
    items_succeeded  INTEGER NOT NULL DEFAULT 0,
    items_failed     INTEGER NOT NULL DEFAULT 0,
    items_skipped    INTEGER NOT NULL DEFAULT 0,
    created_by       TEXT,
    metadata         JSONB NOT NULL DEFAULT '{}'::jsonb
);

CREATE TABLE IF NOT EXISTS paper_intelligence.stage_runs (
    stage_run_id     UUID PRIMARY KEY,
    run_id           UUID NOT NULL
        REFERENCES paper_intelligence.pipeline_runs(run_id) ON DELETE CASCADE,
    stage_name       TEXT NOT NULL,
    stage_version    TEXT NOT NULL,
    prompt_version   TEXT,
    policy_version   TEXT,
    started_at       TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    ended_at         TIMESTAMPTZ,
    duration_ms      INTEGER,
    items_input      INTEGER NOT NULL DEFAULT 0,
    items_success    INTEGER NOT NULL DEFAULT 0,
    items_failed     INTEGER NOT NULL DEFAULT 0,
    items_cached     INTEGER NOT NULL DEFAULT 0,
    status           TEXT NOT NULL DEFAULT 'running'
        CHECK (status IN ('running', 'succeeded', 'failed', 'partial', 'cancelled')),
    error_summary    TEXT
);

CREATE INDEX IF NOT EXISTS ix_stage_runs_run
    ON paper_intelligence.stage_runs (run_id, stage_name);

CREATE TABLE IF NOT EXISTS paper_intelligence.item_stage_runs (
    id               BIGSERIAL PRIMARY KEY,
    run_id           UUID NOT NULL
        REFERENCES paper_intelligence.pipeline_runs(run_id) ON DELETE CASCADE,
    stage_run_id     UUID NOT NULL
        REFERENCES paper_intelligence.stage_runs(stage_run_id) ON DELETE CASCADE,
    content_item_id  BIGINT NOT NULL
        REFERENCES research_radar.content_items(id) ON DELETE CASCADE,
    attempt_number   INTEGER NOT NULL DEFAULT 1,
    started_at       TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    ended_at         TIMESTAMPTZ,
    duration_ms      INTEGER,
    status           TEXT NOT NULL
        CHECK (status IN ('running', 'succeeded', 'failed', 'skipped', 'cached')),
    input_hash       TEXT,
    output_hash      TEXT,
    error_type       TEXT,
    error_message    TEXT,
    metadata         JSONB NOT NULL DEFAULT '{}'::jsonb,
    UNIQUE (stage_run_id, content_item_id, attempt_number)
);

CREATE INDEX IF NOT EXISTS ix_item_stage_runs_content
    ON paper_intelligence.item_stage_runs (content_item_id, stage_run_id);

-- ---------------------------------------------------------------------------
-- External request observability + raw cache pointers
-- ---------------------------------------------------------------------------

CREATE TABLE IF NOT EXISTS paper_intelligence.external_requests (
    request_id       UUID PRIMARY KEY,
    run_id           UUID
        REFERENCES paper_intelligence.pipeline_runs(run_id) ON DELETE SET NULL,
    stage_run_id     UUID
        REFERENCES paper_intelligence.stage_runs(stage_run_id) ON DELETE SET NULL,
    content_item_id  BIGINT
        REFERENCES research_radar.content_items(id) ON DELETE SET NULL,
    provider         TEXT NOT NULL
        CHECK (provider IN ('arxiv', 'openalex', 'ror', 'openrouter')),
    endpoint         TEXT NOT NULL,
    request_hash     TEXT NOT NULL,
    started_at       TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    ended_at         TIMESTAMPTZ,
    duration_ms      INTEGER,
    http_status      INTEGER,
    success          BOOLEAN,
    cache_hit        BOOLEAN NOT NULL DEFAULT FALSE,
    response_path    TEXT,
    response_sha256  TEXT,
    error_type       TEXT,
    error_message    TEXT,
    created_at       TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS ix_external_requests_hash
    ON paper_intelligence.external_requests (provider, request_hash);

CREATE INDEX IF NOT EXISTS ix_external_requests_run
    ON paper_intelligence.external_requests (run_id, provider);

CREATE TABLE IF NOT EXISTS paper_intelligence.llm_requests (
    llm_request_id   UUID PRIMARY KEY,
    request_id       UUID NOT NULL
        REFERENCES paper_intelligence.external_requests(request_id) ON DELETE CASCADE,
    model            TEXT NOT NULL,
    prompt_version   TEXT,
    input_tokens     INTEGER,
    output_tokens    INTEGER,
    estimated_cost   NUMERIC(12, 6),
    created_at       TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS ix_llm_requests_model
    ON paper_intelligence.llm_requests (model, created_at DESC);

-- ---------------------------------------------------------------------------
-- Canonical identity: people + organisations
-- ---------------------------------------------------------------------------

CREATE TABLE IF NOT EXISTS paper_intelligence.people (
    id                   BIGSERIAL PRIMARY KEY,
    canonical_name       TEXT NOT NULL,
    orcid                TEXT,
    openalex_author_id   TEXT,
    aliases              TEXT[] NOT NULL DEFAULT ARRAY[]::TEXT[],
    metadata             JSONB NOT NULL DEFAULT '{}'::jsonb,
    created_at           TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at           TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE UNIQUE INDEX IF NOT EXISTS ux_people_orcid
    ON paper_intelligence.people (orcid) WHERE orcid IS NOT NULL;
CREATE UNIQUE INDEX IF NOT EXISTS ux_people_openalex
    ON paper_intelligence.people (openalex_author_id) WHERE openalex_author_id IS NOT NULL;

CREATE TABLE IF NOT EXISTS paper_intelligence.organisations (
    id                       BIGSERIAL PRIMARY KEY,
    canonical_name           TEXT NOT NULL,
    organisation_type        TEXT,
    parent_organisation_id   BIGINT
        REFERENCES paper_intelligence.organisations(id) ON DELETE SET NULL,
    country_code             TEXT,
    ror_id                   TEXT,
    openalex_id              TEXT,
    priority                 INTEGER NOT NULL DEFAULT 0,
    is_org_of_interest       BOOLEAN NOT NULL DEFAULT FALSE,
    active                   BOOLEAN NOT NULL DEFAULT TRUE,
    metadata                 JSONB NOT NULL DEFAULT '{}'::jsonb,
    created_at               TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at               TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE UNIQUE INDEX IF NOT EXISTS ux_organisations_ror
    ON paper_intelligence.organisations (ror_id) WHERE ror_id IS NOT NULL;
CREATE UNIQUE INDEX IF NOT EXISTS ux_organisations_openalex
    ON paper_intelligence.organisations (openalex_id) WHERE openalex_id IS NOT NULL;
CREATE INDEX IF NOT EXISTS ix_organisations_name
    ON paper_intelligence.organisations (canonical_name);

CREATE TABLE IF NOT EXISTS paper_intelligence.organisation_aliases (
    id               BIGSERIAL PRIMARY KEY,
    organisation_id  BIGINT NOT NULL
        REFERENCES paper_intelligence.organisations(id) ON DELETE CASCADE,
    alias            TEXT NOT NULL,
    alias_type       TEXT NOT NULL
        CHECK (alias_type IN ('name', 'domain', 'abbreviation', 'historical_name')),
    confidence       NUMERIC(4, 3),
    created_at       TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE (organisation_id, alias, alias_type)
);

CREATE INDEX IF NOT EXISTS ix_organisation_aliases_alias
    ON paper_intelligence.organisation_aliases (lower(alias));

-- ---------------------------------------------------------------------------
-- Paper-author occurrence + affiliations (evidence preserved)
-- ---------------------------------------------------------------------------

CREATE TABLE IF NOT EXISTS paper_intelligence.paper_authors (
    id                   BIGSERIAL PRIMARY KEY,
    content_item_id      BIGINT NOT NULL
        REFERENCES research_radar.content_items(id) ON DELETE CASCADE,
    author_position      INTEGER NOT NULL,
    raw_name             TEXT NOT NULL,
    normalized_name      TEXT,
    person_id            BIGINT
        REFERENCES paper_intelligence.people(id) ON DELETE SET NULL,
    orcid                TEXT,
    openalex_author_id   TEXT,
    created_at           TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at           TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE (content_item_id, author_position)
);

CREATE INDEX IF NOT EXISTS ix_paper_authors_person
    ON paper_intelligence.paper_authors (person_id)
    WHERE person_id IS NOT NULL;
CREATE INDEX IF NOT EXISTS ix_paper_authors_normalized
    ON paper_intelligence.paper_authors (lower(normalized_name));

CREATE TABLE IF NOT EXISTS paper_intelligence.papers_people (
    id               BIGSERIAL PRIMARY KEY,
    content_item_id  BIGINT NOT NULL
        REFERENCES research_radar.content_items(id) ON DELETE CASCADE,
    person_id        BIGINT NOT NULL
        REFERENCES paper_intelligence.people(id) ON DELETE CASCADE,
    paper_author_id  BIGINT
        REFERENCES paper_intelligence.paper_authors(id) ON DELETE SET NULL,
    confidence       NUMERIC(4, 3),
    run_id           UUID
        REFERENCES paper_intelligence.pipeline_runs(run_id) ON DELETE SET NULL,
    created_at       TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE (content_item_id, person_id)
);

CREATE TABLE IF NOT EXISTS paper_intelligence.paper_author_affiliations (
    id                   BIGSERIAL PRIMARY KEY,
    content_item_id      BIGINT NOT NULL
        REFERENCES research_radar.content_items(id) ON DELETE CASCADE,
    paper_author_id      BIGINT NOT NULL
        REFERENCES paper_intelligence.paper_authors(id) ON DELETE CASCADE,
    organisation_id      BIGINT
        REFERENCES paper_intelligence.organisations(id) ON DELETE SET NULL,
    raw_affiliation      TEXT,
    relationship_scope   TEXT,
    evidence_type        TEXT NOT NULL,
    evidence_source      TEXT NOT NULL,
    evidence_value       TEXT,
    confidence           NUMERIC(4, 3),
    run_id               UUID
        REFERENCES paper_intelligence.pipeline_runs(run_id) ON DELETE SET NULL,
    stage_version        TEXT,
    policy_version       TEXT,
    created_at           TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS ix_paper_author_affiliations_content
    ON paper_intelligence.paper_author_affiliations (content_item_id);
CREATE INDEX IF NOT EXISTS ix_paper_author_affiliations_org
    ON paper_intelligence.paper_author_affiliations (organisation_id)
    WHERE organisation_id IS NOT NULL;
CREATE INDEX IF NOT EXISTS ix_paper_author_affiliations_author
    ON paper_intelligence.paper_author_affiliations (paper_author_id);

-- ---------------------------------------------------------------------------
-- Audience / domain enrichment (append-only) + current state
-- ---------------------------------------------------------------------------

CREATE TABLE IF NOT EXISTS paper_intelligence.paper_classification_results (
    id               BIGSERIAL PRIMARY KEY,
    content_item_id  BIGINT NOT NULL
        REFERENCES research_radar.content_items(id) ON DELETE CASCADE,
    task_type        TEXT NOT NULL,
    audience         TEXT,
    domain           TEXT,
    subdomain        TEXT,
    result_json      JSONB NOT NULL DEFAULT '{}'::jsonb,
    method           TEXT NOT NULL
        CHECK (method IN ('deterministic', 'llm', 'adjudicated', 'manual')),
    provider         TEXT,
    model            TEXT,
    prompt_version   TEXT,
    policy_version   TEXT,
    stage_version    TEXT,
    confidence       NUMERIC(4, 3),
    run_id           UUID
        REFERENCES paper_intelligence.pipeline_runs(run_id) ON DELETE SET NULL,
    created_at       TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS ix_paper_classification_results_content
    ON paper_intelligence.paper_classification_results (content_item_id, created_at DESC);
CREATE INDEX IF NOT EXISTS ix_paper_classification_results_task
    ON paper_intelligence.paper_classification_results (task_type, method);

CREATE TABLE IF NOT EXISTS paper_intelligence.paper_intelligence_current (
    content_item_id               BIGINT PRIMARY KEY
        REFERENCES research_radar.content_items(id) ON DELETE CASCADE,
    domain                        TEXT,
    subdomains                    JSONB NOT NULL DEFAULT '[]'::jsonb,
    audiences                     JSONB NOT NULL DEFAULT '[]'::jsonb,
    domain_confidence             NUMERIC(4, 3),
    audience_confidence           NUMERIC(4, 3),
    author_resolution_status      TEXT,
    affiliation_resolution_status TEXT,
    updated_at                    TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- ---------------------------------------------------------------------------
-- Golden datasets + evaluation
-- ---------------------------------------------------------------------------

CREATE TABLE IF NOT EXISTS paper_intelligence.golden_sets (
    golden_set_id    BIGSERIAL PRIMARY KEY,
    name             TEXT NOT NULL UNIQUE,
    task_type        TEXT NOT NULL,
    version          TEXT NOT NULL,
    description      TEXT,
    item_count       INTEGER NOT NULL DEFAULT 0,
    created_at       TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE (task_type, version)
);

CREATE TABLE IF NOT EXISTS paper_intelligence.golden_set_items (
    id               BIGSERIAL PRIMARY KEY,
    golden_set_id    BIGINT NOT NULL
        REFERENCES paper_intelligence.golden_sets(golden_set_id) ON DELETE CASCADE,
    content_item_id  BIGINT NOT NULL
        REFERENCES research_radar.content_items(id) ON DELETE CASCADE,
    metadata         JSONB NOT NULL DEFAULT '{}'::jsonb,
    UNIQUE (golden_set_id, content_item_id)
);

CREATE TABLE IF NOT EXISTS paper_intelligence.golden_labels (
    id               BIGSERIAL PRIMARY KEY,
    golden_set_id    BIGINT NOT NULL
        REFERENCES paper_intelligence.golden_sets(golden_set_id) ON DELETE CASCADE,
    content_item_id  BIGINT NOT NULL
        REFERENCES research_radar.content_items(id) ON DELETE CASCADE,
    label_json       JSONB NOT NULL DEFAULT '{}'::jsonb,
    gold_label_source TEXT NOT NULL
        CHECK (gold_label_source IN ('manual', 'llm_adjudicated')),
    labelled_by      TEXT,
    notes            TEXT,
    created_at       TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE (golden_set_id, content_item_id)
);

CREATE TABLE IF NOT EXISTS paper_intelligence.evaluation_runs (
    evaluation_run_id UUID PRIMARY KEY,
    golden_set_id     BIGINT NOT NULL
        REFERENCES paper_intelligence.golden_sets(golden_set_id) ON DELETE CASCADE,
    pipeline_run_id   UUID
        REFERENCES paper_intelligence.pipeline_runs(run_id) ON DELETE SET NULL,
    task_type         TEXT NOT NULL,
    code_commit_sha   TEXT,
    stage_version     TEXT,
    prompt_version    TEXT,
    policy_version    TEXT,
    started_at        TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    ended_at          TIMESTAMPTZ,
    status            TEXT NOT NULL DEFAULT 'running'
        CHECK (status IN ('running', 'succeeded', 'failed')),
    summary_json      JSONB NOT NULL DEFAULT '{}'::jsonb,
    created_by        TEXT
);

CREATE TABLE IF NOT EXISTS paper_intelligence.evaluation_results (
    id                  BIGSERIAL PRIMARY KEY,
    evaluation_run_id   UUID NOT NULL
        REFERENCES paper_intelligence.evaluation_runs(evaluation_run_id) ON DELETE CASCADE,
    content_item_id     BIGINT NOT NULL
        REFERENCES research_radar.content_items(id) ON DELETE CASCADE,
    gold_label_source   TEXT NOT NULL
        CHECK (gold_label_source IN ('manual', 'llm_adjudicated')),
    gold_json           JSONB NOT NULL DEFAULT '{}'::jsonb,
    predicted_json      JSONB NOT NULL DEFAULT '{}'::jsonb,
    match               BOOLEAN,
    regression          BOOLEAN NOT NULL DEFAULT FALSE,
    metrics_json        JSONB NOT NULL DEFAULT '{}'::jsonb,
    notes               TEXT,
    UNIQUE (evaluation_run_id, content_item_id)
);

CREATE INDEX IF NOT EXISTS ix_evaluation_results_run
    ON paper_intelligence.evaluation_results (evaluation_run_id, match);

COMMIT;
