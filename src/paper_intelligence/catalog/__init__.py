"""PI-owned paper catalog (additive / shadow). Production cutover not enabled."""

from paper_intelligence.catalog.normalize import normalize_arxiv_id, normalize_doi
from paper_intelligence.catalog.papers import (
    fetch_papers_by_ids,
    resolve_paper_id,
)
from paper_intelligence.catalog.relevance import (
    RELEVANCE_KEEP_STATUSES,
    RELEVANCE_REJECT_STATUSES,
    current_relevance,
    latest_relevance_decision,
)

__all__ = [
    "normalize_arxiv_id",
    "normalize_doi",
    "fetch_papers_by_ids",
    "resolve_paper_id",
    "RELEVANCE_KEEP_STATUSES",
    "RELEVANCE_REJECT_STATUSES",
    "current_relevance",
    "latest_relevance_decision",
]
