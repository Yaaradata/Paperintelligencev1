"""Unit tests for PI catalog normalization helpers."""

from paper_intelligence.catalog.normalize import (
    extract_arxiv_version,
    normalize_arxiv_id,
    normalize_doi,
)


def test_normalize_arxiv_strips_version_and_url():
    assert normalize_arxiv_id("2609.12345v2") == "2609.12345"
    assert normalize_arxiv_id("arxiv:2609.12345") == "2609.12345"
    assert normalize_arxiv_id("https://arxiv.org/abs/2609.12345v1") == "2609.12345"
    assert normalize_arxiv_id("https://arxiv.org/pdf/2609.12345.pdf") == "2609.12345"
    assert normalize_arxiv_id("") is None
    assert normalize_arxiv_id(None) is None


def test_extract_arxiv_version():
    assert extract_arxiv_version("2609.12345v2") == 2
    assert extract_arxiv_version("2609.12345") is None


def test_normalize_doi():
    assert normalize_doi("10.1234/ABC") == "10.1234/abc"
    assert normalize_doi("https://doi.org/10.1234/ABC") == "10.1234/abc"
    assert normalize_doi("doi:10.1/x") == "10.1/x"
    assert normalize_doi("  ") is None
