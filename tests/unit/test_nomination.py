"""Tests for PI eligibility statuses and nomination helpers."""

from __future__ import annotations

from paper_intelligence.db.results import PI_ELIGIBLE_STATUSES, EXCLUDED_UPSTREAM_STATUSES
from paper_intelligence.quality.nomination import (
    NominationTarget,
    filter_scoreable,
    stratified_sample,
)


def test_pi_eligible_includes_entity_resolved_not_rejected():
    assert "ENTITY_RESOLVED" in PI_ELIGIBLE_STATUSES
    assert "RELEVANT" in PI_ELIGIBLE_STATUSES
    assert "SCORED" in PI_ELIGIBLE_STATUSES
    assert "REJECTED" not in PI_ELIGIBLE_STATUSES
    assert "REJECTED" in EXCLUDED_UPSTREAM_STATUSES
    assert "INGESTED" not in PI_ELIGIBLE_STATUSES


def test_filter_scoreable_uses_screen_gate_not_radar_status():
    """Radar REJECTED/ENTITY_RESOLVED must not block when PI screen passed."""
    targets = [
        NominationTarget(
            content_item_id=1,
            arxiv_id="a",
            title="t",
            status="ENTITY_RESOLVED",
            published_at="2026-09-02",
            screen_gate_passed=True,
            screen_rank_mean=6.67,
            already_quality_scored=False,
            exclusion_reason="outside router",
        ),
        NominationTarget(
            content_item_id=2,
            arxiv_id="b",
            title="t",
            status="ENTITY_RESOLVED",
            published_at="2026-09-02",
            screen_gate_passed=True,
            screen_rank_mean=7.0,
            already_quality_scored=True,
            exclusion_reason=None,
        ),
        NominationTarget(
            content_item_id=3,
            arxiv_id="c",
            title="t",
            status="REJECTED",
            published_at="2026-09-02",
            screen_gate_passed=True,
            screen_rank_mean=9.0,
            already_quality_scored=False,
            exclusion_reason=None,
        ),
        NominationTarget(
            content_item_id=4,
            arxiv_id="d",
            title="t",
            status="ENTITY_RESOLVED",
            published_at="2026-09-02",
            screen_gate_passed=False,
            screen_rank_mean=9.0,
            already_quality_scored=False,
            exclusion_reason="screen gate failed",
        ),
    ]
    to_score, skipped = filter_scoreable(targets)
    assert to_score == [1, 3]
    assert {t.content_item_id for t in skipped} == {2, 4}

    to_score_rp, _ = filter_scoreable(targets, reprocess=True)
    assert to_score_rp == [1, 2, 3]


def test_stratified_sample_is_deterministic_and_records_probability():
    pool = [
        {"content_item_id": i, "rank_mean": 6.7, "band": "mid", "domain": "ml"}
        for i in range(1, 9)
    ] + [
        {"content_item_id": i, "rank_mean": 5.0, "band": "low", "domain": "systems"}
        for i in range(10, 18)
    ]
    a = stratified_sample(pool, per_day=4, seed="pilot")
    b = stratified_sample(pool, per_day=4, seed="pilot")
    assert [r["content_item_id"] for r in a] == [r["content_item_id"] for r in b]
    assert len(a) == 4
    assert all(r["route"] == "exploration_sample" for r in a)
    assert all(0 < r["sampling_probability"] <= 1 for r in a)
