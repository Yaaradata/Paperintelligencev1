"""Provider throttling (429/503/timeouts) counts as failure and stops affiliation."""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest
import requests

from paper_intelligence.external import openalex, ror, throttle_guard


@pytest.fixture(autouse=True)
def _fresh_guard(monkeypatch):
    throttle_guard.reset()
    monkeypatch.setattr(ror, "REQUEST_SLEEP", 0.0)
    monkeypatch.setattr(openalex, "REQUEST_SLEEP", 0.0)
    monkeypatch.setattr(ror.time, "sleep", lambda s: None)
    yield
    throttle_guard.reset()


def _resp(status):
    r = MagicMock()
    r.status_code = status
    r.json.return_value = {"items": []}
    return r


def test_404_is_ok_429_503_and_timeouts_are_failures():
    for status in (200, 404, 500):
        assert throttle_guard.record("ror", status=status) is False
    throttle_guard.record("ror", status=429)
    throttle_guard.record("ror", status=503)
    throttle_guard.record("arxiv", exception=requests.Timeout("slow"))
    c = throttle_guard.counts()
    assert c["ror:requests"] == 5 and c["ror:http_429"] == 1 and c["ror:http_503"] == 1
    assert c["arxiv:Timeout"] == 1


def test_trips_above_ten_percent_after_twenty():
    for _ in range(17):
        throttle_guard.record("ror", status=200)
    for _ in range(2):
        throttle_guard.record("ror", status=429)
    assert not throttle_guard.tripped()
    assert throttle_guard.record("ror", status=429) is True
    assert "3/20 failed" in throttle_guard.reason()


def test_ror_counts_every_429_attempt_and_stops_retrying_once_tripped(monkeypatch):
    calls = []

    def always_429(*a, **k):
        calls.append(1)
        return _resp(429)

    monkeypatch.setattr(ror.requests, "get", always_429)
    for _ in range(7):
        ror._get("https://api.ror.org/x", {})
    assert throttle_guard.tripped()
    assert len(calls) == 20
    payload, status, error = ror._get("https://api.ror.org/x", {})
    assert payload is None and error.startswith("throttle_guard_tripped")
    assert len(calls) == 20


def test_openalex_timeout_is_recorded(monkeypatch):
    def timeout(*a, **k):
        raise requests.Timeout("read timed out")

    monkeypatch.setattr(openalex.requests, "get", timeout)
    monkeypatch.setattr(openalex.time, "sleep", lambda s: None)
    openalex._get("https://api.openalex.org/works/x", {})
    assert throttle_guard.counts()["openalex:Timeout"] == openalex.MAX_RETRIES


def test_affiliation_runner_stops_and_cancels_when_tripped(monkeypatch):
    from paper_intelligence.author_affiliation import runner

    processed = []

    class FakeStage:
        stage_name = "affiliation"
        stage_version = "v1"

        def __init__(self, *a, **k):
            pass

        def process(self, cid, ctx):
            processed.append(cid)
            if len(processed) == 3:
                for _ in range(20):
                    throttle_guard.record("ror", status=429)
            res = MagicMock()
            res.status = "success"
            res.data = {"outcome": "resolved"}
            res.metadata = {}
            return res

    finished = {}
    monkeypatch.setattr(runner, "AffiliationStage", FakeStage)
    monkeypatch.setattr(runner, "start_pipeline_run", lambda *a, **k: "run")
    monkeypatch.setattr(runner, "start_stage_run", lambda *a, **k: "stage")
    monkeypatch.setattr(runner, "record_item_stage_run", lambda *a, **k: None)
    monkeypatch.setattr(runner, "code_commit_sha", lambda: "sha")
    monkeypatch.setattr(runner, "finish_stage_run", lambda conn, sid, **k: finished.update(stage=k["status"]))
    monkeypatch.setattr(runner, "finish_pipeline_run", lambda conn, rid, **k: finished.update(run=k["status"]))
    summary = runner.run_window("2026-08-01", "2026-08-07", conn=MagicMock(), content_item_ids=list(range(1, 11)))
    assert processed == [1, 2, 3]
    assert summary["stopped_runguard"] is True and "throttle" in summary["stop_reason"]
    assert finished == {"stage": "cancelled", "run": "cancelled"}
    assert summary["throttle_counts"]["ror:http_429"] == 20


def test_pipeline_treats_affiliation_trip_as_stop():
    import importlib.util
    from pathlib import Path

    path = Path(__file__).resolve().parents[2] / "scripts" / "run_pipeline.py"
    spec = importlib.util.spec_from_file_location("run_pipeline_guard", path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    assert {"affiliation_fast", "affiliation_deep"} <= mod.GUARDED_FREE_STAGES
