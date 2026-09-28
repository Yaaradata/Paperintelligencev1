"""arXiv ingest stage — harvest by v1 submission date into the PI catalog.

``ARXIV_INGEST_SOURCE`` selects the harvester: ``oai`` (default, OAI-PMH
arXivRaw + arXiv) or ``api`` (arXiv API ``submittedDate`` search).
"""

from os import getenv
from typing import Any

from paper_intelligence.ingest import arxiv_api, arxiv_oai
from paper_intelligence.ingest.arxiv_oai import (
    STAGE_NAME,
    STAGE_VERSION,
    IngestWindowFailed,
)


def run_window(*args: Any, **kwargs: Any) -> dict[str, Any]:
    source = getenv("ARXIV_INGEST_SOURCE", "oai").strip().lower()
    if source == "api":
        return arxiv_api.run_window(*args, **kwargs)
    if source != "oai":
        raise ValueError(f"ARXIV_INGEST_SOURCE must be 'oai' or 'api', got {source!r}")
    return arxiv_oai.run_window(*args, **kwargs)


__all__ = [
    "STAGE_NAME",
    "STAGE_VERSION",
    "IngestWindowFailed",
    "run_window",
]
