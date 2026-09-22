"""Unit tests for explicit quality failure / pending / scored status (Phase 1)."""

from __future__ import annotations

import json
from contextlib import contextmanager
from typing import Any
from unittest.mock import MagicMock

import pytest

from paper_intelligence.adjudication.quality_status import (
    derive_quality_status,
    quality_result_is_current,
)
from paper_intelligence.quality import attempts as attempts_mod
from paper_intelligence.quality import stage as quality


# ---------------------------------------------------------------------------
# derive_quality_status / quality_result_is_current
# ---------------------------------------------------------------------------


class TestQualityResultIsCurrent:
    def test_current_versions_match(self):
        assert quality_result_is_current(
            {
                "stage_version": "v001",
                "prompt_version": "v001",
                "policy_version": "v001",
                "model": "z-ai/glm-5.3-flash",
            },
            stage_version="v001",
            prompt_version="v001",
            policy_version="v001",
            model="z-ai/glm-5.3-flash",
        )

    def test_stale_stage_version_not_current(self):
        assert not quality_result_is_current(
            {
                "stage_version": "v000",
                "prompt_version": "v001",
                "policy_version": "v001",
                "model": "z-ai/glm-5.3-flash",
            },
            stage_version="v001",
            prompt_version="v001",
            policy_version="v001",
            model="z-ai/glm-5.3-flash",
        )

    def test_stale_model_not_current(self):
        assert not quality_result_is_current(
            {
                "stage_version": "v001",
                "prompt_version": "v001",
                "policy_version": "v001",
                "model": "old-model",
            },
            stage_version="v001",
            prompt_version="v001",
            policy_version="v001",
            model="z-ai/glm-5.3-flash",
        )

    def test_none_meta_not_current(self):
        assert not quality_result_is_current(
            None,
            stage_version="v001",
            prompt_version="v001",
            policy_version="v001",
            model="m",
        )


class TestDeriveQualityStatus:
    def test_scored_when_current_row(self):
        status, reason = derive_quality_status(
            has_current_quality_row=True,
            route_decision="selected",
            route_reason="selected_top_gate_percentile",
            latest_attempt_status=None,
        )
        assert status == "scored"
        assert reason == "scored_quality_result_current_versions"

    def test_selected_no_attempt_is_pending(self):
        status, reason = derive_quality_status(
            has_current_quality_row=False,
            route_decision="selected",
            route_reason="selected_top_gate_percentile",
            latest_attempt_status=None,
        )
        assert status == "pending"
        assert reason.startswith("pending_quality_score:")

    def test_selected_failed_attempt_is_failed(self):
        status, reason = derive_quality_status(
            has_current_quality_row=False,
            route_decision="selected",
            route_reason="selected_top_gate_percentile",
            latest_attempt_status="failed",
            latest_attempt_error="TimeoutError: boom",
        )
        assert status == "failed"
        assert "TimeoutError" in reason

    def test_succeeded_attempt_without_row_is_inconsistency(self):
        status, reason = derive_quality_status(
            has_current_quality_row=False,
            route_decision="selected",
            route_reason="selected_top_gate_percentile",
            latest_attempt_status="succeeded",
        )
        assert status == "pending"
        assert reason == "inconsistent_attempt_without_result"

    def test_stale_quality_row_selected_no_attempt_pending(self):
        status, reason = derive_quality_status(
            has_current_quality_row=False,  # stale version does not count
            route_decision="selected",
            route_reason="selected_notable_org",
            latest_attempt_status=None,
        )
        assert status == "pending"
        assert "pending_quality_score" in reason

    def test_not_selected_unchanged(self):
        status, reason = derive_quality_status(
            has_current_quality_row=False,
            route_decision="not_selected",
            route_reason="not_selected_below_gate_percentile",
            latest_attempt_status=None,
        )
        assert status == "not_selected"
        assert reason == "not_selected_below_gate_percentile"

    def test_blocked_is_skipped(self):
        status, reason = derive_quality_status(
            has_current_quality_row=False,
            route_decision="blocked",
            route_reason="blocked_screen_gate_failed",
            latest_attempt_status=None,
        )
        assert status == "skipped"
        assert reason == "blocked_screen_gate_failed"


# ---------------------------------------------------------------------------
# run_window attempt persistence (mocked LLM / DB)
# ---------------------------------------------------------------------------


class _CaptureConn:
    """Minimal connection that records quality_attempts inserts."""

    def __init__(self):
        self.attempt_rows: list[dict[str, Any]] = []
        self.commits = 0

    def cursor(self):
        return _CaptureCur(self)

    def commit(self):
        self.commits += 1


class _CaptureCur:
    def __init__(self, conn: _CaptureConn):
        self.conn = conn

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return None

    def execute(self, sql, params=None):
        text = " ".join(str(sql).split())
        if "INSERT INTO paper_intelligence.quality_attempts" in text and params:
            self.conn.attempt_rows.append(
                {
                    "content_item_id": params[0],
                    "run_id": params[1],
                    "stage_run_id": params[2],
                    "stage_version": params[3],
                    "prompt_version": params[4],
                    "policy_version": params[5],
                    "model": params[6],
                    "status": params[7],
                    "error_summary": params[8],
                }
            )


def _paper(cid: int) -> dict[str, Any]:
    return {
        "content_item_id": cid,
        "title": f"T{cid}",
        "abstract": "A",
        "categories": ["cs.LG"],
    }


def _valid_quality_entry(cid: int) -> dict[str, Any]:
    entry = {dim: 6.0 for dim in quality.RUBRIC_DIMENSIONS}
    entry["content_item_id"] = cid
    entry["so_what"] = "useful"
    entry["reason_not_higher"] = "limited evidence"
    entry["confidence"] = 7.0
    return entry


@pytest.fixture
def quality_run_mocks(monkeypatch):
    capture = _CaptureConn()
    inserted: list[list[dict]] = []

    @contextmanager
    def fake_connect():
        yield capture

    monkeypatch.setattr(quality, "connect", fake_connect)
    monkeypatch.setattr(quality, "fetch_papers", lambda conn, ids: [_paper(i) for i in ids])
    monkeypatch.setattr(quality, "read_prompt", lambda *a, **k: "system")
    monkeypatch.setattr(
        quality,
        "insert_classification_results",
        lambda conn, rows: inserted.append(list(rows)),
    )
    monkeypatch.setattr(quality, "random_batches", lambda papers, size: [list(papers)])
    # Sequential batches — avoid thread-pool flake in unit tests.
    monkeypatch.setattr(
        "paper_intelligence.common.batch_runner.STAGE_CONCURRENCY",
        1,
    )
    return capture, inserted


def test_batch_exception_records_failed_attempts(quality_run_mocks, monkeypatch):
    capture, inserted = quality_run_mocks

    def boom(*args, **kwargs):
        raise RuntimeError("llm_down")

    monkeypatch.setattr(quality, "call_llm_logged", boom)

    stats = quality.run_window(
        MagicMock(),
        [10, 11],
        run_id="run1",
        stage_run_id="sr1",
        model="z-ai/glm-5.3-flash",
        batch_size=10,
        dry_run=False,
    )
    assert stats.papers_failed == 2
    assert inserted == []
    assert len(capture.attempt_rows) == 2
    assert {r["content_item_id"] for r in capture.attempt_rows} == {10, 11}
    assert all(r["status"] == "failed" for r in capture.attempt_rows)
    assert all("RuntimeError" in (r["error_summary"] or "") for r in capture.attempt_rows)


def test_partial_parse_only_missing_ids_failed(quality_run_mocks, monkeypatch):
    capture, inserted = quality_run_mocks

    def ok_call(*args, **kwargs):
        # Only paper 1 present and valid; paper 2 missing from response.
        payload = {"papers": [_valid_quality_entry(1)]}
        return {
            "content": json.dumps(payload),
            "input_tokens": 10,
            "output_tokens": 20,
            "estimated_cost": 0.001,
        }

    monkeypatch.setattr(quality, "call_llm_logged", ok_call)

    stats = quality.run_window(
        MagicMock(),
        [1, 2],
        run_id="run1",
        stage_run_id="sr1",
        model="z-ai/glm-5.3-flash",
        batch_size=10,
        dry_run=False,
    )
    assert stats.papers_succeeded == 1
    assert stats.papers_failed == 1
    assert len(inserted) == 1
    assert inserted[0][0]["content_item_id"] == 1

    by_status = {}
    for row in capture.attempt_rows:
        by_status.setdefault(row["status"], set()).add(row["content_item_id"])
    assert by_status.get("succeeded") == {1}
    assert by_status.get("failed") == {2}


def test_failures_are_not_classification_results(quality_run_mocks, monkeypatch):
    """Failed papers must remain retryable: no classification_results row."""
    capture, inserted = quality_run_mocks

    monkeypatch.setattr(
        quality,
        "call_llm_logged",
        lambda *a, **k: (_ for _ in ()).throw(ValueError("parse boom")),
    )
    quality.run_window(
        MagicMock(),
        [99],
        run_id="r",
        stage_run_id="s",
        model="m",
        dry_run=False,
    )
    assert inserted == []
    assert capture.attempt_rows[0]["status"] == "failed"


def test_record_helpers_roundtrip_status():
    """Insert helpers write the expected status vocabulary."""
    capture = _CaptureConn()
    n = attempts_mod.record_quality_failures(
        capture,
        [1, 2],
        run_id="r",
        stage_run_id="s",
        model="m",
        error_summary="x",
    )
    assert n == 2
    assert all(r["status"] == "failed" for r in capture.attempt_rows)
    n2 = attempts_mod.record_quality_successes(
        capture,
        [1],
        run_id="r",
        stage_run_id="s",
        model="m",
    )
    assert n2 == 1
    assert capture.attempt_rows[-1]["status"] == "succeeded"
