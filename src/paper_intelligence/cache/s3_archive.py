"""S3 archive for relevance-rejected papers (jsonl.gz).

Best-effort: failures log and continue. Uses the same RDS manifest table as
Research Radar (`research_radar.s3_archives`) so both pipelines share one
index of archived rejects.
"""

from __future__ import annotations

import gzip
import json
import logging
import os
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable, Iterator
from uuid import UUID

log = logging.getLogger("paper_intelligence.s3")

S3_ARCHIVE_ENABLED = os.getenv("S3_ARCHIVE_ENABLED", "false").lower() == "true"
S3_BUCKET = os.getenv(
    "PAPER_INTELLIGENCE_S3_BUCKET",
    os.getenv("RESEARCH_RADAR_S3_BUCKET", ""),
)
S3_PREFIX = os.getenv("PAPER_INTELLIGENCE_S3_PREFIX", "paper-intelligence")


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _s3_key(kind: str, stage: str, run_id: str, when: datetime | None = None) -> str:
    when = when or _utc_now()
    y, m, d = when.year, f"{when.month:02d}", f"{when.day:02d}"
    return f"{S3_PREFIX}/{kind}/{stage}/{y}/{m}/{d}/{run_id}.jsonl.gz"


def _iter_records(records: Iterable[dict[str, Any]]) -> Iterator[dict[str, Any]]:
    for rec in records:
        if rec is not None:
            yield rec


def _write_jsonl_gzip(path: Path, records: Iterable[dict[str, Any]]) -> tuple[int, int]:
    count = 0
    with gzip.open(path, "wt", encoding="utf-8") as gz:
        for rec in _iter_records(records):
            gz.write(json.dumps(rec, default=str) + "\n")
            count += 1
    return count, path.stat().st_size


def _upload_file(local_path: Path, bucket: str, key: str) -> None:
    import boto3

    client = boto3.client("s3")
    with open(local_path, "rb") as fh:
        client.put_object(
            Bucket=bucket, Key=key, Body=fh, ContentType="application/gzip"
        )


def _write_manifest(
    conn: Any,
    *,
    run_id: str,
    kind: str,
    stage: str,
    bucket: str,
    key: str,
    record_count: int,
    bytes_written: int,
) -> None:
    conn.execute(
        """
        INSERT INTO research_radar.s3_archives (
            run_id, kind, stage, s3_bucket, s3_key, record_count, bytes_written
        ) VALUES (%s, %s, %s, %s, %s, %s, %s)
        ON CONFLICT (s3_bucket, s3_key) DO UPDATE SET
            record_count = EXCLUDED.record_count,
            bytes_written = EXCLUDED.bytes_written,
            created_at = NOW()
        """,
        (str(run_id), kind, stage, bucket, key, record_count, bytes_written),
    )


def build_rejected_record(
    *,
    content_id: int,
    canonical_url: str,
    title: str,
    abstract: str,
    categories: Any,
    relevance_score: float,
    primary_topic: str | None,
    rejection_reason: str,
    relevance_version: str,
    arxiv_id: str | None = None,
    rejected_at: datetime | None = None,
) -> dict[str, Any]:
    if isinstance(categories, str):
        try:
            categories = json.loads(categories)
        except json.JSONDecodeError:
            categories = [categories]
    return {
        "content_id": content_id,
        "arxiv_id": arxiv_id,
        "canonical_url": canonical_url,
        "title": title,
        "abstract": abstract or "",
        "categories": categories or [],
        "relevance_score": relevance_score,
        "primary_topic": primary_topic,
        "rejection_reason": rejection_reason,
        "relevance_version": relevance_version,
        "rejected_at": (rejected_at or _utc_now()).isoformat(),
        "pipeline": "paper_intelligence",
    }


def archive_rejected(
    conn: Any,
    run_id: str | UUID,
    stage: str,
    records: Iterable[dict[str, Any]],
) -> dict[str, Any] | None:
    """Upload rejected-paper payloads to S3 before status is set to REJECTED."""
    key = _s3_key("rejected", stage, str(run_id))
    materialised = list(_iter_records(records))
    if not materialised:
        return None

    if not S3_ARCHIVE_ENABLED:
        log.info(
            "S3 archive disabled: would write %d rejected records to s3://%s/%s",
            len(materialised),
            S3_BUCKET or "(unset)",
            key,
        )
        return {
            "skipped": True,
            "reason": "S3_ARCHIVE_ENABLED=false",
            "record_count": len(materialised),
            "key": key,
        }

    if not S3_BUCKET:
        log.warning(
            "S3_ARCHIVE_ENABLED but PAPER_INTELLIGENCE_S3_BUCKET / "
            "RESEARCH_RADAR_S3_BUCKET unset; skipping archive"
        )
        return None

    with tempfile.NamedTemporaryFile(suffix=".jsonl.gz", delete=False) as tmp:
        tmp_path = Path(tmp.name)
    try:
        record_count, nbytes = _write_jsonl_gzip(tmp_path, materialised)
        try:
            _upload_file(tmp_path, S3_BUCKET, key)
        except Exception as exc:  # noqa: BLE001 — best-effort archive
            log.warning("S3 upload failed key=%s: %s", key, exc)
            return None
        if conn is not None:
            try:
                _write_manifest(
                    conn,
                    run_id=str(run_id),
                    kind="rejected",
                    stage=stage,
                    bucket=S3_BUCKET,
                    key=key,
                    record_count=record_count,
                    bytes_written=nbytes,
                )
                conn.commit()
            except Exception as exc:  # noqa: BLE001
                log.warning("S3 manifest write failed after upload: %s", exc)
        log.info(
            "S3 archived rejected=%d bytes=%d s3://%s/%s",
            record_count,
            nbytes,
            S3_BUCKET,
            key,
        )
        return {
            "bucket": S3_BUCKET,
            "key": key,
            "record_count": record_count,
            "bytes_written": nbytes,
        }
    finally:
        tmp_path.unlink(missing_ok=True)
