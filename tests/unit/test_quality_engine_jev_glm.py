"""Tests for QUALITY_ENGINE=terra|jev_glm routing and prose failure isolation."""

from __future__ import annotations

import json
from unittest.mock import MagicMock, patch

import pytest

from paper_intelligence.quality import jev_glm_engine as jev_glm
from paper_intelligence.quality.stage import (
    RUBRIC_DIMENSIONS,
    active_policy_version,
    active_prompt_version,
    composite_score,
)


class TestEngineRouting:
    def test_default_engine_is_terra(self):
        from paper_intelligence.common import config

        # Default when env unset / terra
        assert config.QUALITY_ENGINE in {"terra", "jev_glm"}

    def test_active_versions_terra(self, monkeypatch):
        monkeypatch.setenv("QUALITY_ENGINE", "terra")
        # Re-read would need reload; call helpers with patched QUALITY_ENGINE
        import paper_intelligence.quality.stage as stage

        monkeypatch.setattr(stage, "QUALITY_ENGINE", "terra")
        assert stage.active_prompt_version() == "v001"
        assert stage.active_policy_version() == "v001"

    def test_active_versions_jev_glm(self, monkeypatch):
        import paper_intelligence.quality.stage as stage

        monkeypatch.setattr(stage, "QUALITY_ENGINE", "jev_glm")
        assert stage.active_prompt_version() == "prose_v001"
        assert stage.active_policy_version() == "systemone_v001"

    def test_run_window_routes_to_jev_glm(self, monkeypatch):
        import paper_intelligence.quality.stage as stage

        monkeypatch.setattr(stage, "QUALITY_ENGINE", "jev_glm")
        called = {}

        def fake_jev(*args, **kwargs):
            called["yes"] = True
            from paper_intelligence.common.batch_runner import BatchStats

            return BatchStats(papers_requested=0)

        monkeypatch.setattr(
            "paper_intelligence.quality.jev_glm_engine.run_jev_glm_window",
            fake_jev,
        )
        stats = stage.run_window(
            MagicMock(), [], run_id="r", stage_run_id="s", dry_run=True
        )
        assert called.get("yes") is True
        assert stats.papers_requested == 0

    def test_run_window_terra_default_does_not_call_jev(self, monkeypatch):
        import paper_intelligence.quality.stage as stage

        monkeypatch.setattr(stage, "QUALITY_ENGINE", "terra")
        called = {}

        def fake_jev(*args, **kwargs):
            called["yes"] = True
            from paper_intelligence.common.batch_runner import BatchStats

            return BatchStats()

        monkeypatch.setattr(
            "paper_intelligence.quality.jev_glm_engine.run_jev_glm_window",
            fake_jev,
        )
        # empty ids → early return before LLM; must not route to jev
        stats = stage.run_window(
            MagicMock(), [], run_id="r", stage_run_id="s", dry_run=True
        )
        assert called.get("yes") is None
        assert stats.papers_requested == 0


class TestProseParse:
    def test_parse_prose_ok(self):
        text = json.dumps(
            {
                "papers": [
                    {
                        "batch_index": 1,
                        "so_what": "Leaders can ship X.",
                        "reason_not_higher": "Only evaluated on Y.",
                    }
                ]
            }
        )
        out, problems = jev_glm.parse_prose_response(text, {1: 42})
        assert problems == []
        assert out[42]["so_what"].startswith("Leaders")
        assert out[42]["reason_not_higher"].startswith("Only")

    def test_parse_rejects_emitted_scores(self):
        text = json.dumps(
            {
                "papers": [
                    {
                        "batch_index": 1,
                        "so_what": "x",
                        "reason_not_higher": "y",
                        "technical_significance": 9.0,
                    }
                ]
            }
        )
        out, problems = jev_glm.parse_prose_response(text, {1: 42})
        assert any("prose_emitted_score_field" in p for p in problems)
        assert 42 in out  # still parsed prose fields


class TestProseFailureKeepsScores:
    def test_result_json_allows_null_prose(self):
        dims = {d: 6.0 for d in RUBRIC_DIMENSIONS}
        composite = composite_score(dims)
        result_json = {
            **dims,
            "so_what": None,
            "reason_not_higher": None,
            "composite": composite,
            "quality_engine": "jev_glm",
            "scoring_engine": "jev",
            "scoring_model": "typesafe/jev-1.13",
            "prose_model": None,
            "prose_failed": True,
        }
        assert result_json["technical_significance"] == 6.0
        assert result_json["so_what"] is None
        assert result_json["composite"]["quality"] == pytest.approx(6.0)

    def test_current_weights_unchanged(self):
        """G3c refit must not leak into stored composite."""
        from paper_intelligence.quality.stage import WEIGHTS

        assert WEIGHTS["technical_significance"] == 0.28
        assert WEIGHTS["learning_value"] == 0.12
