"""Golden dataset loader unit tests (no DB required)."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from paper_intelligence.evaluation.golden import load_golden_file


def test_load_golden_audience_fixture():
    path = Path(__file__).resolve().parents[2] / "data/golden/audience_domain_200_v1.json"
    payload = load_golden_file(path)
    assert payload["task_type"] == "audience_domain"
    assert len(payload["items"]) >= 200
    sources = {item["gold_label_source"] for item in payload["items"]}
    assert sources <= {"manual", "llm_adjudicated"}
    assert "manual" in sources


def test_load_golden_affiliation_fixture():
    path = Path(__file__).resolve().parents[2] / "data/golden/author_affiliation_200_v1.json"
    payload = load_golden_file(path)
    assert payload["task_type"] == "author_affiliation"
    assert len(payload["items"]) == 200
    assert payload["items"][0]["label_json"]["organisations"]


def test_load_golden_rejects_empty(tmp_path: Path):
    bad = tmp_path / "bad.json"
    bad.write_text(json.dumps({"name": "x", "version": "v1", "task_type": "domain", "items": []}))
    with pytest.raises(ValueError):
        load_golden_file(bad)
