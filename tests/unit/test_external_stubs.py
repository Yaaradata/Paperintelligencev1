"""Typed external-client contracts — no live API calls."""

from __future__ import annotations

import pytest

from paper_intelligence.external import arxiv, openalex, ror
from paper_intelligence.openrouter import LLMRequest, LLMResponse


def test_ror_response_contract() -> None:
    response = ror.RorResponse(query="Massachusetts Institute of Technology")
    assert response.query == "Massachusetts Institute of Technology"
    assert response.matches == []


def test_openalex_work_contract() -> None:
    response = openalex.OpenAlexWork(identifier="W123")
    assert response.identifier == "W123"
    assert response.work == {}


def test_arxiv_get_paper_stub() -> None:
    with pytest.raises(NotImplementedError):
        arxiv.get_paper("2608.02345")


def test_openrouter_request_response_contracts() -> None:
    req = LLMRequest(model="glm-5.3-flash", messages=[{"role": "user", "content": "hi"}])
    response = LLMResponse(model=req.model, content="{}")
    assert req.messages[0]["content"] == "hi"
    assert response.content == "{}"
