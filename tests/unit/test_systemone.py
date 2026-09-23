"""Unit tests for System One client pinning and score mapping."""

from __future__ import annotations

import pytest

from paper_intelligence.systemone.client import JEV_MODEL_PINNED, SystemOneError, assert_pinned_model
from paper_intelligence.systemone.policy import (
    build_questions,
    load_systemone_policy,
    score_to_screen_scale,
    state_from_paper,
)


def test_pin_rejects_latest() -> None:
    with pytest.raises(SystemOneError):
        assert_pinned_model("jev-latest")
    with pytest.raises(SystemOneError):
        assert_pinned_model("~typesafe/jev-latest")
    assert assert_pinned_model("jev-1.13") == JEV_MODEL_PINNED
    assert assert_pinned_model("typesafe/jev-1.13") == JEV_MODEL_PINNED


def test_score_mapping() -> None:
    assert score_to_screen_scale(0.0) == 0.0
    assert score_to_screen_scale(9.0) == 10.0
    assert score_to_screen_scale(4.5) == 5.0


def test_state_title_abstract_only() -> None:
    text = state_from_paper(
        {
            "title": "Hello",
            "abstract": "World",
            "categories": ["cs.AI"],
            "arxiv_id": "2609.00001",
        }
    )
    assert text == "Title: Hello\nAbstract: World"
    assert "cs.AI" not in text
    assert "2609" not in text


def test_screen_policy_loads() -> None:
    policy = load_systemone_policy("screen", "v001")
    qs = build_questions(policy)
    assert "gate_ai_relevance" in qs
    assert qs["gate_ai_relevance"]["type"] == "noul"
    assert qs["ai_relevance"]["type"] == "score"
    assert len(qs["ai_relevance"]["criteria"]) == 10


def test_audience_policy_loads() -> None:
    policy = load_systemone_policy("audience", "v001")
    qs = build_questions(policy)
    assert qs["tech_relevance"]["type"] == "score"
    assert qs["domain"]["type"] == "choice"
    assert "computer_vision" in qs["domain"]["criteria"]
    assert "general_method" in qs["application_domain"]["criteria"]


def test_jev_price_configured() -> None:
    from paper_intelligence.common.config import model_prices

    inp, out = model_prices("typesafe/jev-1.13")
    assert inp == 0.042
    assert out == 0.0
