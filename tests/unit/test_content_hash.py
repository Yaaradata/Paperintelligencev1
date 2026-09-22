"""Phase 3: content fingerprint + reuse rules."""

from __future__ import annotations

from typing import Any
from unittest.mock import MagicMock

import pytest

from paper_intelligence.adjudication.quality_status import quality_result_is_current
from paper_intelligence.common.content_hash import compute_content_hash, normalize_content_text
from paper_intelligence.db import results as results_mod


def test_content_hash_stable_under_whitespace_and_nfc():
    a = compute_content_hash("Hello   World", "abs\n tract")
    b = compute_content_hash("Hello World", "abs tract")
    assert a == b
    assert len(a) == 64


def test_content_hash_changes_when_abstract_changes():
    h1 = compute_content_hash("T", "abstract one")
    h2 = compute_content_hash("T", "abstract two")
    assert h1 != h2


def test_normalize_collapses_whitespace():
    assert normalize_content_text("  a \t b\n c  ") == "a b c"


class _FakeCur:
    def __init__(self, db: "_FakeConn"):
        self.db = db
        self._rows: list[dict] = []

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return None

    def execute(self, sql, params=None):
        text = " ".join(str(sql).split())
        self.db.last_sql = text
        self.db.last_params = params
        if "INSERT INTO paper_intelligence.paper_classification_results" in text:
            self.db.inserts.append({"sql": text, "params": params})
            return
        if "SELECT DISTINCT r.content_item_id" in text or (
            "SELECT DISTINCT content_item_id" in text and "paper_classification_results" in text
        ):
            # Simulate reusable ids: only those in db.reusable matching filters.
            self._rows = [{"content_item_id": i} for i in self.db.reusable]
            return
        self._rows = []

    def fetchall(self):
        return list(self._rows)


class _FakeConn:
    def __init__(self, reusable: set[int] | None = None):
        self.reusable = reusable or set()
        self.inserts: list[dict] = []
        self.last_sql = ""
        self.last_params = None

    def cursor(self):
        return _FakeCur(self)


def test_ids_with_result_sql_includes_content_hash_clause():
    conn = _FakeConn(reusable={1, 2})
    done = results_mod.ids_with_result(
        conn,
        [1, 2, 3],
        "screen",
        stage_version="v001",
        prompt_version="v001",
        policy_version="v001",
        model="m",
    )
    assert done == {1, 2}
    assert "input_content_hash IS NULL" in conn.last_sql
    assert "content_hash" in conn.last_sql


def test_insert_writes_input_content_hash():
    conn = _FakeConn()
    results_mod.insert_classification_results(
        conn,
        [
            {
                "content_item_id": 9,
                "task_type": "screen",
                "result_json": {},
                "model": "m",
                "prompt_version": "v001",
                "policy_version": "v001",
                "stage_version": "v001",
                "run_id": "r",
                "input_content_hash": "abc123",
            }
        ],
    )
    assert conn.inserts
    assert conn.inserts[0]["params"][-1] == "abc123"
    assert "input_content_hash" in conn.inserts[0]["sql"]


def test_quality_current_null_hash_legacy_reusable():
    assert quality_result_is_current(
        {
            "stage_version": "v001",
            "prompt_version": "v001",
            "policy_version": "v001",
            "model": "openai/gpt-5.6-sol",
            "input_content_hash": None,
        },
        stage_version="v001",
        prompt_version="v001",
        policy_version="v001",
        model="openai/gpt-5.6-sol",
        paper_content_hash="newhash",
    )


def test_quality_current_mismatch_hash_not_current():
    assert not quality_result_is_current(
        {
            "stage_version": "v001",
            "prompt_version": "v001",
            "policy_version": "v001",
            "model": "openai/gpt-5.6-sol",
            "input_content_hash": "old",
        },
        stage_version="v001",
        prompt_version="v001",
        policy_version="v001",
        model="openai/gpt-5.6-sol",
        paper_content_hash="new",
    )


def test_quality_current_matching_hash():
    assert quality_result_is_current(
        {
            "stage_version": "v001",
            "prompt_version": "v001",
            "policy_version": "v001",
            "model": "openai/gpt-5.6-sol",
            "input_content_hash": "same",
        },
        stage_version="v001",
        prompt_version="v001",
        policy_version="v001",
        model="openai/gpt-5.6-sol",
        paper_content_hash="same",
    )


def test_ingest_revision_updates_hash_and_logs(monkeypatch):
    """Revised abstract changes content_hash and appends a change-log row."""
    from paper_intelligence.catalog import ingest as ingest_mod

    old_hash = compute_content_hash("Title", "old abstract")
    new_hash = compute_content_hash("Title", "new abstract text")
    assert old_hash != new_hash

    state: dict[str, Any] = {
        "content_hash": old_hash,
        "title": "Title",
        "abstract": "old abstract",
        "arxiv_version": 1,
        "changes": [],
    }

    class Cur:
        def __enter__(self):
            return self

        def __exit__(self, *a):
            return None

        def execute(self, sql, params=None):
            text = " ".join(str(sql).split())
            self._params = params
            if text.startswith("SELECT content_hash, arxiv_version"):
                self._row = {
                    "content_hash": state["content_hash"],
                    "arxiv_version": state["arxiv_version"],
                }
            elif (
                "UPDATE paper_intelligence.papers SET" in text
                and "title = %s" in text
            ):
                # Full catalog update — abstract positional args include new text.
                state["title"] = "Title"
                state["abstract"] = "new abstract text"
                state["arxiv_version"] = 2
                state["content_hash"] = params[-2]  # content_hash before paper_id
                self._row = {
                    "paper_id": 42,
                    "content_hash": state["content_hash"],
                    "arxiv_version": 2,
                }
            elif text.startswith("SELECT title, abstract, content_hash"):
                self._row = {
                    "title": state["title"],
                    "abstract": state["abstract"],
                    "content_hash": state["content_hash"],
                    "arxiv_version": state["arxiv_version"],
                }
            elif "SET content_hash = %s" in text and "WHERE paper_id" in text:
                state["content_hash"] = params[0]
            elif "INSERT INTO paper_intelligence.paper_content_hash_changes" in text:
                state["changes"].append(params)
            else:
                self._row = {"paper_id": 42}

        def fetchone(self):
            return getattr(self, "_row", None)

    class Conn:
        def cursor(self):
            return Cur()

    monkeypatch.setattr(ingest_mod, "find_existing_paper_id", lambda *a, **k: 42)

    pid, is_new = ingest_mod.upsert_paper_from_oai(
        Conn(),
        {
            "arxiv_id": "2609.00001v2",
            "title": "Title",
            "abstract": "new abstract text",
            "authors": [],
            "categories": [],
            "created": "2026-09-01T00:00:00Z",
        },
    )
    assert pid == 42 and is_new is False
    assert state["changes"], "expected content hash change log row"
    assert state["changes"][0][1] == old_hash
    assert state["changes"][0][2] == new_hash
    assert state["content_hash"] == new_hash
