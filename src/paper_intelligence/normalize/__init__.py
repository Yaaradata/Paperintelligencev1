"""normalize_authors stage package."""

from paper_intelligence.normalize.names import (
    authors_to_rows,
    coerce_author_entries,
    normalize_author_name,
)
from paper_intelligence.normalize.stage import STAGE_NAME, STAGE_VERSION, NormalizeAuthorsStage

__all__ = [
    "STAGE_NAME",
    "STAGE_VERSION",
    "NormalizeAuthorsStage",
    "authors_to_rows",
    "coerce_author_entries",
    "normalize_author_name",
]
