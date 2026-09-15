"""Typed stub contracts for external clients — no live API calls."""

from __future__ import annotations

import pytest

from paper_intelligence.external import arxiv, openalex, ror
from paper_intelligence.openrouter import LLMRequest, complete


def test_ror_resolve_affiliation_stub() -> None:
    with pytest.raises(NotImplementedError):
        ror.resolve_affiliation("Massachusetts Institute of Technology")


def test_openalex_get_work_stub() -> None:
    with pytest.raises(NotImplementedError):
        openalex.get_work("W123")


def test_arxiv_get_paper_stub() -> None:
    with pytest.raises(NotImplementedError):
        arxiv.get_paper("2608.02345")


def test_openrouter_complete_stub() -> None:
    req = LLMRequest(model="glm-5.3-flash", messages=[{"role": "user", "content": "hi"}])
    with pytest.raises(NotImplementedError):
        complete(req)
