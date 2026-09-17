"""Unit tests for HF signal shaping (no network)."""

from __future__ import annotations

from paper_intelligence.hf_signals.stage import _merge_detail, _normalize_daily_entry


def test_normalize_daily_entry():
    entry = {
        "numComments": 3,
        "submittedBy": {"name": "alice"},
        "publishedAt": "2026-09-10T00:00:00.000Z",
        "paper": {
            "id": "2609.06966",
            "title": "MOLE",
            "upvotes": 19,
            "githubRepo": "https://github.com/x/y",
            "submittedOnDailyAt": "2026-09-09T00:00:00.000Z",
        },
    }
    norm = _normalize_daily_entry(entry, day="2026-09-10", rank=2)
    assert norm["arxiv_id"] == "2609.06966"
    assert norm["hf_featured"] is True
    assert str(norm["hf_featured_date"]) == "2026-09-09"
    assert norm["hf_upvotes"] == 19
    assert norm["hf_daily_upvote_rank"] == 2
    assert norm["hf_submitter"] == "alice"


def test_merge_detail_counts():
    base = {"arxiv_id": "2609.06966", "hf_featured": True, "hf_upvotes": 1}
    detail = {
        "upvotes": 19,
        "numTotalModels": 2,
        "numTotalDatasets": 1,
        "numTotalSpaces": 0,
        "githubRepo": "https://github.com/a/b",
        "githubStars": 5,
        "projectPage": "https://example.com",
        "submittedOnDailyAt": "2026-09-09T00:00:00.000Z",
    }
    merged = _merge_detail(base, detail)
    assert merged["hf_upvotes"] == 19
    assert merged["linked_models_count"] == 2
    assert merged["linked_datasets_count"] == 1
    assert merged["github_stars"] == 5
