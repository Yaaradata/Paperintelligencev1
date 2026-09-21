"""HTML vs OpenAlex affiliation verification (compare-only; no blind merge)."""

from __future__ import annotations

from paper_intelligence.author_affiliation.verify.compare import (
    OUTCOMES,
    classify_verification,
    load_html_orgs,
    load_openalex_orgs_from_pi,
)
from paper_intelligence.author_affiliation.verify.claim import (
    VERIFICATION_VERSION_DEFAULT,
    claim_batch,
    enqueue_papers,
    mark_complete,
    mark_failed,
    reclaim_stale,
)

__all__ = [
    "OUTCOMES",
    "VERIFICATION_VERSION_DEFAULT",
    "claim_batch",
    "classify_verification",
    "enqueue_papers",
    "load_html_orgs",
    "load_openalex_orgs_from_pi",
    "mark_complete",
    "mark_failed",
    "reclaim_stale",
]
