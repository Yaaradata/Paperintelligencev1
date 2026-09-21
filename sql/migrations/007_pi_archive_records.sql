-- Migration 007: PI-owned reject/archive index (additive).
-- Does NOT drop research_radar.s3_archives.
-- Does NOT disable Radar compatibility archive writes.
--
-- Apply manually:
--   psql "$DATABASE_URL" -f sql/migrations/007_pi_archive_records.sql

BEGIN;

CREATE TABLE IF NOT EXISTS paper_intelligence.archive_records (
    archive_id       BIGSERIAL PRIMARY KEY,
    run_id           UUID
        REFERENCES paper_intelligence.pipeline_runs(run_id) ON DELETE SET NULL,
    archive_kind     TEXT NOT NULL DEFAULT 'rejected',
    stage_name       TEXT NOT NULL,
    s3_bucket        TEXT,
    s3_key           TEXT,
    s3_uri           TEXT,
    record_count     INTEGER,
    bytes_written    BIGINT,
    sha256           TEXT,
    metadata         JSONB NOT NULL DEFAULT '{}'::jsonb,
    created_at       TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    CONSTRAINT archive_records_bucket_key_uniq UNIQUE (s3_bucket, s3_key)
);

CREATE INDEX IF NOT EXISTS ix_archive_records_run
    ON paper_intelligence.archive_records (run_id);

CREATE INDEX IF NOT EXISTS ix_archive_records_kind_created
    ON paper_intelligence.archive_records (archive_kind, created_at DESC);

-- Backfill PI-relevant archive manifest rows from Radar (object refs only).
INSERT INTO paper_intelligence.archive_records (
    run_id, archive_kind, stage_name, s3_bucket, s3_key, s3_uri,
    record_count, bytes_written, metadata
)
SELECT
    a.run_id,
    a.kind,
    a.stage,
    a.s3_bucket,
    a.s3_key,
    CASE
      WHEN a.s3_bucket IS NOT NULL AND a.s3_key IS NOT NULL
      THEN 's3://' || a.s3_bucket || '/' || a.s3_key
      ELSE NULL
    END,
    a.record_count,
    a.bytes_written,
    jsonb_build_object(
        'backfilled_from', 'research_radar.s3_archives',
        'radar_archive_id', a.archive_id,
        'window_from', a.window_from,
        'window_until', a.window_until
    )
FROM research_radar.s3_archives a
WHERE a.stage ILIKE '%relevance%'
   OR a.s3_key LIKE 'paper-intelligence/%'
ON CONFLICT (s3_bucket, s3_key) DO NOTHING;

COMMIT;
