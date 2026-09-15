"""arXiv client boundary for replayable metadata fetches (not OAI ingestion)."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True)
class ArxivResponse:
    arxiv_id: str
    payload: dict[str, Any] = field(default_factory=dict)
    raw_ref: str | None = None
    error: str | None = None


def get_paper(arxiv_id: str) -> ArxivResponse:
    """Fetch arXiv metadata for replay/cache. Does not replace OAI-PMH ingestion."""
    raise NotImplementedError(
        "arxiv.get_paper is a typed stub; Urmila implements behind this contract"
    )
