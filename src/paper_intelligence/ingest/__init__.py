"""OAI-PMH ingest stage — harvest arXiv into shared research_radar tables."""

from paper_intelligence.ingest.arxiv_oai import (
    STAGE_NAME,
    STAGE_VERSION,
    IngestWindowFailed,
    run_window,
)

__all__ = [
    "STAGE_NAME",
    "STAGE_VERSION",
    "IngestWindowFailed",
    "run_window",
]
