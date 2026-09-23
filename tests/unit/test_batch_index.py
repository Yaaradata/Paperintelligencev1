"""Unit tests for batch-local index parsing in paid LLM stages."""

from __future__ import annotations

import json

from paper_intelligence.audience_domain import stage as classify
from paper_intelligence.common.llm_stage import indexed_paper_blocks
from paper_intelligence.quality import stage as quality
from paper_intelligence.screen import stage as screen


def _screen_payload(batch_index: int, **overrides) -> str:
    entry = {
        "batch_index": batch_index,
        "ai_relevance": 7.0,
        "technical_significance": 6.5,
        "apparent_novelty": 6.0,
        "evidence_strength": 5.5,
    }
    entry.update(overrides)
    return json.dumps({"papers": [entry]})


class TestBatchIndexMapping:
    def test_indexed_blocks_are_one_based(self):
        papers = [
            {"content_item_id": 100, "title": "a", "abstract": "x", "categories": []},
            {"content_item_id": 200, "title": "b", "abstract": "y", "categories": []},
        ]
        text, mapping = indexed_paper_blocks(papers)
        assert mapping == {1: 100, 2: 200}
        assert "batch_index: 1" in text
        assert "content_item_id:" not in text
        assert "100" not in text.split("batch_index")[0]  # first header has no paper id


class TestScreenBatchIndex:
    def test_valid_scores_map_to_paper_id(self):
        parsed, problems = screen.parse_response(_screen_payload(1), {1: 42})
        assert problems == []
        assert 42 in parsed
        assert parsed[42]["ai_relevance"] == 7.0

    def test_unexpected_batch_index_reported(self):
        parsed, problems = screen.parse_response(_screen_payload(9), {1: 42})
        assert parsed == {}
        assert any("unexpected batch_index 9" in p for p in problems)
        assert any("missing batch_index: [1]" in p for p in problems)

    def test_echoed_content_item_id_is_ignored(self):
        """Model must not be trusted to echo paper ids — only batch_index counts."""
        text = json.dumps(
            {
                "papers": [
                    {
                        "content_item_id": 999,
                        "ai_relevance": 7.0,
                        "technical_significance": 6.5,
                        "apparent_novelty": 6.0,
                        "evidence_strength": 5.5,
                    }
                ]
            }
        )
        parsed, problems = screen.parse_response(text, {1: 42})
        assert parsed == {}
        assert any("unparseable batch_index" in p for p in problems)


class TestQualityBatchIndex:
    def test_maps_batch_index(self):
        entry = {
            "batch_index": 1,
            "technical_significance": 7.0,
            "apparent_novelty": 6.5,
            "practical_applicability": 6.0,
            "professional_value": 6.5,
            "learning_value": 6.0,
            "evidence_strength": 7.0,
            "so_what": "x",
            "reason_not_higher": "y",
            "confidence": 7.5,
        }
        parsed, problems = quality.parse_response(
            json.dumps({"papers": [entry]}), {1: 55}
        )
        assert problems == []
        assert 55 in parsed


class TestClassifyBatchIndex:
    def test_maps_batch_index(self):
        entry = {
            "batch_index": 1,
            "audience_relevance": ["practitioner"],
            "domain": "computer_vision",
            "subdomains": ["object_detection"],
            "application_domain": ["general_method"],
            "confidence": 8.0,
        }
        parsed, problems = classify.parse_response(
            json.dumps({"papers": [entry]}), {1: 77}
        )
        assert problems == []
        assert 77 in parsed
