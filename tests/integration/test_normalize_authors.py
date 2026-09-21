"""DB-backed tests for normalize_authors (skipped without DATABASE_URL)."""

from __future__ import annotations

import os
import uuid

import pytest

from paper_intelligence.common import RunContext
from paper_intelligence.db import connect
from paper_intelligence.normalize import NormalizeAuthorsStage
from paper_intelligence.normalize.repository import list_paper_authors

pytestmark = pytest.mark.skipif(
    not (os.environ.get("DATABASE_URL") or os.environ.get("PG_DSN")),
    reason="DATABASE_URL/PG_DSN not set",
)


def _ctx() -> RunContext:
    return RunContext(run_id=str(uuid.uuid4()), stage_run_id=str(uuid.uuid4()))


@pytest.fixture()
def sample_content_id():
    with connect() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT p.paper_id AS id
                FROM paper_intelligence.papers p
                WHERE jsonb_typeof(p.authors_raw) = 'array'
                  AND jsonb_array_length(p.authors_raw) >= 2
                ORDER BY p.paper_id
                LIMIT 1
                """
            )
            row = cur.fetchone()
    if not row:
        pytest.skip("no PI papers with authors_raw")
    return int(row["id"])


def test_normalize_idempotent_and_preserves_unicode(sample_content_id: int) -> None:
    stage = NormalizeAuthorsStage()
    first = stage.process(sample_content_id, _ctx())
    assert first.status == "success"
    second = stage.process(sample_content_id, _ctx())
    assert second.status == "success"
    assert first.data["authors"] == second.data["authors"]

    with connect() as conn:
        stored = list_paper_authors(conn, sample_content_id)
    assert stored
    for row in stored:
        assert row["person_id"] is None
        assert row["orcid"] is None
        assert row["openalex_author_id"] is None
        # unicode / content preserved as stored text
        assert isinstance(row["raw_name"], str) and row["raw_name"]


def test_empty_authors_succeeds_cleanly() -> None:
    """Insert a throwaway PI catalog paper with empty authors, normalize, then delete."""
    with connect() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO paper_intelligence.papers (
                    source, source_type, canonical_url, title, authors_raw, abstract
                ) VALUES (
                    'arxiv_oai', 'arxiv',
                    %s, 'PI normalize empty-authors fixture',
                    '[]'::jsonb, ''
                )
                RETURNING paper_id
                """,
                (f"https://example.invalid/pi-normalize-{uuid.uuid4()}",),
            )
            content_id = int(cur.fetchone()["paper_id"])
        conn.commit()

    try:
        result = NormalizeAuthorsStage().process(content_id, _ctx())
        assert result.status == "success", getattr(result, "metadata", None)
        assert result.data["author_count"] == 0
        with connect() as conn:
            assert list_paper_authors(conn, content_id) == []
    finally:
        with connect() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    "DELETE FROM paper_intelligence.paper_authors WHERE content_item_id = %s",
                    (content_id,),
                )
                cur.execute(
                    "DELETE FROM paper_intelligence.papers WHERE paper_id = %s",
                    (content_id,),
                )
            conn.commit()
            conn.commit()
