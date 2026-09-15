"""OpenAlex client boundary — structured data only; no business decisions."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True)
class OpenAlexWork:
    identifier: str
    work: dict[str, Any] = field(default_factory=dict)
    raw_ref: str | None = None
    error: str | None = None


def get_work(identifier: str) -> OpenAlexWork:
    """Fetch an OpenAlex work by DOI, OpenAlex ID, or other supported identifier.

    Returns structured work payload. Calling stages decide matching and persistence.
    """
    raise NotImplementedError(
        "openalex.get_work is a typed stub; Urmila implements behind this contract"
    )
