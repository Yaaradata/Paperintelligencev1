"""Unit tests for relevance scoring and rejected-record shaping."""

from __future__ import annotations

from paper_intelligence.cache.s3_archive import build_rejected_record
from paper_intelligence.relevance.stage import score_relevance


def test_score_keeps_ai_category_paper():
    score, primary, _, reason = score_relevance(
        "A Transformer Language Model",
        "We train a large language model.",
        ["cs.LG", "cs.CL"],
        "arxiv",
    )
    assert score >= 5.0
    assert "AI/ML arXiv category" in reason
    assert primary is not None


def test_score_rejects_unrelated_math():
    score, primary, _, reason = score_relevance(
        "A Numerical Method for PDEs",
        "Finite element analysis of elliptic operators.",
        ["math.NA"],
        "arxiv",
    )
    assert score < 5.0
    assert primary is None
    assert "no strong deterministic" in reason or "source prior" in reason


def test_build_rejected_record_shape():
    rec = build_rejected_record(
        content_id=1,
        canonical_url="https://arxiv.org/abs/2601.00001",
        title="t",
        abstract="a",
        categories=["cs.LG"],
        relevance_score=2.1,
        primary_topic=None,
        rejection_reason="low_ai_relevance",
        relevance_version="pi-relevance-v1",
        arxiv_id="2601.00001",
    )
    assert rec["content_id"] == 1
    assert rec["pipeline"] == "paper_intelligence"
    assert rec["rejection_reason"] == "low_ai_relevance"
