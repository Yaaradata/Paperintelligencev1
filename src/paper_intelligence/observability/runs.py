"""Run / stage / item provenance and external request logging."""

from __future__ import annotations

import json
import subprocess
import uuid
from datetime import datetime, timezone
from typing import Any

from psycopg import Connection


def code_commit_sha() -> str | None:
    try:
        out = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            capture_output=True,
            text=True,
            timeout=5,
        )
        return out.stdout.strip() or None
    except Exception:
        return None


def _now() -> datetime:
    return datetime.now(timezone.utc)


def start_pipeline_run(
    conn: Connection,
    *,
    pipeline_name: str,
    trigger_type: str = "manual",
    created_by: str | None = None,
    metadata: dict[str, Any] | None = None,
) -> str:
    run_id = str(uuid.uuid4())
    with conn.cursor() as cur:
        cur.execute(
            """
            INSERT INTO paper_intelligence.pipeline_runs
                (run_id, pipeline_name, trigger_type, code_commit_sha, created_by, metadata)
            VALUES (%s, %s, %s, %s, %s, %s::jsonb)
            """,
            (
                run_id,
                pipeline_name,
                trigger_type,
                code_commit_sha(),
                created_by,
                json.dumps(metadata or {}, default=str),
            ),
        )
    conn.commit()
    return run_id


def finish_pipeline_run(
    conn: Connection,
    run_id: str,
    *,
    status: str,
    items_input: int = 0,
    items_succeeded: int = 0,
    items_failed: int = 0,
    items_skipped: int = 0,
    metadata: dict[str, Any] | None = None,
) -> None:
    with conn.cursor() as cur:
        cur.execute(
            """
            UPDATE paper_intelligence.pipeline_runs
            SET ended_at = clock_timestamp(), status = %s, items_input = %s, items_succeeded = %s,
                items_failed = %s, items_skipped = %s,
                metadata = metadata || %s::jsonb
            WHERE run_id = %s
            """,
            (
                status,
                items_input,
                items_succeeded,
                items_failed,
                items_skipped,
                json.dumps(metadata or {}, default=str),
                run_id,
            ),
        )
    conn.commit()


def start_stage_run(
    conn: Connection,
    run_id: str,
    *,
    stage_name: str,
    stage_version: str,
    prompt_version: str | None = None,
    policy_version: str | None = None,
    items_input: int = 0,
) -> str:
    stage_run_id = str(uuid.uuid4())
    with conn.cursor() as cur:
        cur.execute(
            """
            INSERT INTO paper_intelligence.stage_runs
                (stage_run_id, run_id, stage_name, stage_version, prompt_version,
                 policy_version, items_input)
            VALUES (%s, %s, %s, %s, %s, %s, %s)
            """,
            (
                stage_run_id,
                run_id,
                stage_name,
                stage_version,
                prompt_version,
                policy_version,
                items_input,
            ),
        )
    conn.commit()
    return stage_run_id


def finish_stage_run(
    conn: Connection,
    stage_run_id: str,
    *,
    status: str,
    items_success: int = 0,
    items_failed: int = 0,
    items_cached: int = 0,
    error_summary: str | None = None,
) -> None:
    with conn.cursor() as cur:
        cur.execute(
            """
            UPDATE paper_intelligence.stage_runs
            SET ended_at = clock_timestamp(),
                duration_ms = EXTRACT(EPOCH FROM (clock_timestamp() - started_at)) * 1000,
                status = %s, items_success = %s, items_failed = %s,
                items_cached = %s, error_summary = %s
            WHERE stage_run_id = %s
            """,
            (status, items_success, items_failed, items_cached, error_summary, stage_run_id),
        )
    conn.commit()


def record_item_stage_run(
    conn: Connection,
    *,
    run_id: str,
    stage_run_id: str,
    content_item_id: int,
    status: str,
    started_at: datetime,
    input_hash: str | None = None,
    output_hash: str | None = None,
    error_type: str | None = None,
    error_message: str | None = None,
    metadata: dict[str, Any] | None = None,
) -> None:
    ended = _now()
    duration_ms = int((ended - started_at).total_seconds() * 1000)
    with conn.cursor() as cur:
        cur.execute(
            """
            INSERT INTO paper_intelligence.item_stage_runs
                (run_id, stage_run_id, content_item_id, attempt_number, started_at,
                 ended_at, duration_ms, status, input_hash, output_hash,
                 error_type, error_message, metadata)
            VALUES (%s, %s, %s,
                    COALESCE((SELECT MAX(attempt_number) + 1
                              FROM paper_intelligence.item_stage_runs
                              WHERE stage_run_id = %s AND content_item_id = %s), 1),
                    %s, %s, %s, %s, %s, %s, %s, %s, %s::jsonb)
            ON CONFLICT (stage_run_id, content_item_id, attempt_number) DO NOTHING
            """,
            (
                run_id,
                stage_run_id,
                content_item_id,
                stage_run_id,
                content_item_id,
                started_at,
                ended,
                duration_ms,
                status,
                input_hash,
                output_hash,
                error_type,
                error_message,
                json.dumps(metadata or {}, default=str),
            ),
        )


def record_external_request(
    conn: Connection,
    *,
    run_id: str | None,
    stage_run_id: str | None,
    content_item_id: int | None,
    provider: str,
    endpoint: str,
    request_hash: str,
    started_at: datetime,
    http_status: int | None,
    success: bool,
    cache_hit: bool = False,
    response_path: str | None = None,
    response_sha256: str | None = None,
    error_type: str | None = None,
    error_message: str | None = None,
    llm: dict[str, Any] | None = None,
) -> str:
    """Insert one external_requests row (plus llm_requests when llm metadata given)."""
    request_id = str(uuid.uuid4())
    ended = _now()
    duration_ms = int((ended - started_at).total_seconds() * 1000)
    with conn.cursor() as cur:
        cur.execute(
            """
            INSERT INTO paper_intelligence.external_requests
                (request_id, run_id, stage_run_id, content_item_id, provider, endpoint,
                 request_hash, started_at, ended_at, duration_ms, http_status, success,
                 cache_hit, response_path, response_sha256, error_type, error_message)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            """,
            (
                request_id,
                run_id,
                stage_run_id,
                content_item_id,
                provider,
                endpoint,
                request_hash,
                started_at,
                ended,
                duration_ms,
                http_status,
                success,
                cache_hit,
                response_path,
                response_sha256,
                error_type,
                error_message,
            ),
        )
        if llm:
            cur.execute(
                """
                INSERT INTO paper_intelligence.llm_requests
                    (llm_request_id, request_id, model, prompt_version,
                     input_tokens, output_tokens, estimated_cost)
                VALUES (%s, %s, %s, %s, %s, %s, %s)
                """,
                (
                    str(uuid.uuid4()),
                    request_id,
                    llm.get("model"),
                    llm.get("prompt_version"),
                    llm.get("input_tokens"),
                    llm.get("output_tokens"),
                    llm.get("estimated_cost"),
                ),
            )
    return request_id
