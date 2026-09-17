"""Tests for HF validation ranking comparison (no network)."""

from __future__ import annotations

from datetime import date

import pytest

from paper_intelligence.evaluation.hf_validation import (
    DEFAULT_WINDOW_END,
    DEFAULT_WINDOW_START,
    assign_cohort,
    compute_overlap,
    daily_upvote_ranks,
    inclusive_days,
    summarize_cohort,
    top_n,
)


def test_window_is_thirty_days():
    assert inclusive_days(DEFAULT_WINDOW_START, DEFAULT_WINDOW_END) == 30


def test_daily_upvote_rank_ordering_and_ties():
    papers = [
        {"arxiv_id": "2609.00003", "upvotes": 10},
        {"arxiv_id": "2609.00001", "upvotes": 50},
        {"arxiv_id": "2609.00002", "upvotes": 50},  # tie → arxiv_id asc wins rank 1
        {"arxiv_id": "2609.00004", "upvotes": None},
    ]
    ranks = daily_upvote_ranks(papers)
    assert ranks["2609.00001"] == 1
    assert ranks["2609.00002"] == 2
    assert ranks["2609.00003"] == 3
    assert ranks["2609.00004"] == 4


def test_same_day_rank_is_dense_from_one():
    ranks = daily_upvote_ranks(
        [
            {"arxiv_id": "a", "upvotes": 3},
            {"arxiv_id": "b", "upvotes": 2},
        ]
    )
    assert set(ranks.values()) == {1, 2}


def test_papers_without_hf_records_not_in_rank_map():
    ranks = daily_upvote_ranks([{"arxiv_id": None, "upvotes": 9}])
    assert ranks == {}


def test_overlap_and_intersection():
    hf = {"a", "b", "c"}
    ours = {"b", "c", "d", "e"}
    stats = compute_overlap(hf, ours)
    assert stats.intersection == 2
    assert stats.hf_only == 1
    assert stats.ours_only == 2
    assert stats.hf_to_ours_pct == pytest.approx(66.7)
    assert stats.ours_to_hf_pct == pytest.approx(50.0)


def test_cohort_assignment_exclusive():
    assert assign_cohort(in_hf=True, in_high_quality=True) == "BOTH"
    assert assign_cohort(in_hf=False, in_high_quality=True) == "OURS_ONLY"
    assert assign_cohort(in_hf=True, in_high_quality=False) == "HF_ONLY"
    assert assign_cohort(in_hf=False, in_high_quality=False) is None


def test_duplicate_arxiv_handled_by_set_overlap():
    # Sets collapse duplicates by construction.
    stats = compute_overlap({"a", "a", "b"}, {"a", "c"})
    assert stats.hf_unique == 2
    assert stats.intersection == 1


def test_null_scores_in_summary():
    rows = [
        {"final_score": None, "hf_upvotes": 10, "audiences": [], "subdomains": []},
        {"final_score": 8.0, "hf_upvotes": None, "audiences": ["practitioner"], "subdomains": ["x"]},
    ]
    m = summarize_cohort(rows)
    assert m.count == 2
    assert m.avg_score == 8.0
    assert m.mean_hf_upvotes == 10.0


def test_top_n_reproducible():
    rows = [
        {"arxiv_id": "2", "final_score": 9.0, "quality_score": 9.0, "hf_upvotes": 1},
        {"arxiv_id": "1", "final_score": 9.0, "quality_score": 8.0, "hf_upvotes": 99},
        {"arxiv_id": "3", "final_score": 7.0, "quality_score": 7.0, "hf_upvotes": 5},
    ]
    a = top_n(rows, 2, cohort="BOTH")
    b = top_n(rows, 2, cohort="BOTH")
    assert [r["arxiv_id"] for r in a] == [r["arxiv_id"] for r in b] == ["2", "1"]


def test_date_filtering_helper():
    assert inclusive_days(date(2026, 8, 18), date(2026, 9, 16)) == 30
