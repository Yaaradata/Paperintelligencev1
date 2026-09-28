"""One retry when a batched LLM stage gets a reply that is not valid JSON."""

from __future__ import annotations

import json
from contextlib import contextmanager
from typing import Any
from unittest.mock import MagicMock

import pytest

from paper_intelligence.audience_domain import stage as ad
from paper_intelligence.common.llm_stage import call_until_parsed, parse_json_object


def _reply(content: str, cost: float = 0.001, actual: float | None = 0.001) -> dict[str, Any]:
    return {
        "content": content,
        "input_tokens": 100,
        "output_tokens": 50,
        "estimated_cost": cost,
        "estimated_cost_usd": cost,
        "actual_cost_usd": actual,
    }


BAD = '{"papers": [{"batch_index": 1 "x": 2}]}'
GOOD = '{"papers": []}'


def _calls(*contents: str):
    replies = iter([_reply(c) for c in contents])
    made: list[int] = []

    def call() -> dict[str, Any]:
        made.append(1)
        return next(replies)

    return call, made


def test_valid_reply_makes_one_call():
    call, made = _calls(GOOD)
    result, parsed, retries = call_until_parsed(call, parse_json_object)
    assert parsed == {"papers": []}
    assert retries == 0
    assert len(made) == 1
    assert result["input_tokens"] == 100


def test_malformed_then_valid_retries_once_and_sums_cost():
    call, made = _calls(BAD, GOOD)
    result, parsed, retries = call_until_parsed(call, parse_json_object)
    assert parsed == {"papers": []}
    assert retries == 1
    assert len(made) == 2
    assert result["input_tokens"] == 200
    assert result["output_tokens"] == 100
    assert result["estimated_cost"] == pytest.approx(0.002)
    assert result["actual_cost_usd"] == pytest.approx(0.002)


def test_malformed_twice_raises_after_two_calls():
    call, made = _calls(BAD, BAD, GOOD)
    with pytest.raises(json.JSONDecodeError):
        call_until_parsed(call, parse_json_object)
    assert len(made) == 2


def test_no_json_object_counts_as_malformed():
    call, made = _calls("sorry, no JSON", GOOD)
    _, parsed, retries = call_until_parsed(call, parse_json_object)
    assert parsed == {"papers": []} and retries == 1 and len(made) == 2


def test_provider_error_is_not_retried():
    def call() -> dict[str, Any]:
        raise RuntimeError("provider down")

    with pytest.raises(RuntimeError):
        call_until_parsed(call, parse_json_object)


@pytest.fixture
def ad_mocks(monkeypatch):
    inserted: list[list[dict]] = []

    @contextmanager
    def fake_connect():
        yield MagicMock()

    monkeypatch.setattr(ad, "connect", fake_connect)
    monkeypatch.setattr(ad, "fetch_papers", lambda conn, ids: [
        {"content_item_id": i, "title": f"T{i}", "abstract": "A", "categories": ["cs.LG"]} for i in ids
    ])
    monkeypatch.setattr(ad, "render_system_prompt", lambda *a, **k: "system")
    monkeypatch.setattr(ad, "build_user_prompt", lambda batch, **k: ("user", {
        n: p["content_item_id"] for n, p in enumerate(batch, 1)
    }))
    monkeypatch.setattr(ad, "random_batches", lambda papers, size: [list(papers)])
    monkeypatch.setattr(ad, "_rows_for", lambda cid, values, **k: [{"content_item_id": cid}])
    monkeypatch.setattr(ad, "insert_classification_results", lambda conn, rows: inserted.append(list(rows)))
    monkeypatch.setattr("paper_intelligence.common.batch_runner.STAGE_CONCURRENCY", 1)

    def fake_parse(text, index_to_id, **k):
        payload = parse_json_object(text)
        return {cid: {"ok": True} for cid in index_to_id.values()} if payload.get("all") else {}, []

    monkeypatch.setattr(ad, "parse_response", fake_parse)
    return inserted


def _run(ids):
    return ad.run_window(MagicMock(), ids, run_id="r", stage_run_id="s", model="z-ai/glm-5.3-flash",
                         batch_size=15, policy_version="v001")


def test_audience_domain_recovers_from_one_malformed_reply(ad_mocks, monkeypatch):
    replies = iter([_reply(BAD), _reply('{"all": true}')])
    monkeypatch.setattr(ad, "call_llm_logged", lambda *a, **k: next(replies))
    stats = _run(list(range(1, 16)))
    assert stats.papers_succeeded == 15
    assert stats.papers_failed == 0
    assert stats.calls == 1
    assert stats.cost_usd == pytest.approx(0.002)
    assert len(ad_mocks) == 1 and len(ad_mocks[0]) == 15


def test_audience_domain_fails_batch_after_second_malformed_reply(ad_mocks, monkeypatch):
    calls: list[int] = []

    def bad(*a, **k):
        calls.append(1)
        return _reply(BAD)

    monkeypatch.setattr(ad, "call_llm_logged", bad)
    stats = _run(list(range(1, 16)))
    assert len(calls) == 2
    assert stats.papers_failed == 15
    assert stats.papers_succeeded == 0
    assert ad_mocks == []
