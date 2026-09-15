"""Stage: normalize_authors — free, 100% of papers."""

from __future__ import annotations

from typing import Any

from paper_intelligence.common import RunContext, StageResult
from paper_intelligence.db import connect
from paper_intelligence.normalize.names import authors_to_rows
from paper_intelligence.normalize.repository import (
    fetch_authors_raw,
    list_paper_authors,
    replace_paper_authors,
)

STAGE_NAME = "normalize_authors"
STAGE_VERSION = "v001"


class NormalizeAuthorsStage:
    stage_name = STAGE_NAME
    stage_version = STAGE_VERSION

    def __init__(self, conn: Any | None = None) -> None:
        self._conn = conn

    def process(self, content_item_id: int, run_context: RunContext) -> StageResult:
        owns_conn = self._conn is None
        conn = self._conn or connect()
        try:
            try:
                authors_raw = fetch_authors_raw(conn, content_item_id)
            except LookupError as exc:
                return StageResult(
                    status="failed",
                    data={"content_item_id": content_item_id},
                    metadata={"error_type": "not_found", "error_message": str(exc)},
                )

            rows = authors_to_rows(authors_raw)

            if run_context.dry_run:
                return StageResult(
                    status="success",
                    data={
                        "content_item_id": content_item_id,
                        "author_count": len(rows),
                        "authors": rows,
                    },
                    metadata={
                        "stage_name": self.stage_name,
                        "stage_version": self.stage_version,
                        "dry_run": True,
                    },
                )

            stats = replace_paper_authors(conn, content_item_id, rows)
            conn.commit()
            stored = list_paper_authors(conn, content_item_id)

            return StageResult(
                status="success",
                data={
                    "content_item_id": content_item_id,
                    "author_count": len(stored),
                    "authors": stored,
                    "stats": stats,
                },
                metadata={
                    "stage_name": self.stage_name,
                    "stage_version": self.stage_version,
                    "run_id": run_context.run_id,
                    "stage_run_id": run_context.stage_run_id,
                    "code_commit_sha": run_context.code_commit_sha,
                },
            )
        except Exception as exc:  # noqa: BLE001 — stage boundary returns failed
            if not owns_conn:
                conn.rollback()
            else:
                conn.rollback()
            return StageResult(
                status="failed",
                data={"content_item_id": content_item_id},
                metadata={
                    "error_type": type(exc).__name__,
                    "error_message": str(exc),
                    "stage_name": self.stage_name,
                    "stage_version": self.stage_version,
                },
            )
        finally:
            if owns_conn:
                conn.close()
