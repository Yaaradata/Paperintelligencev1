"""ROR client boundary — returns structured data only; no business decisions.

Implementation (cache, HTTP, persistence) is Urmila's stream.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True)
class RorResponse:
    """Structured ROR lookup result. Empty matches mean unresolved, not error."""

    query: str
    matches: list[dict[str, Any]] = field(default_factory=list)
    raw_ref: str | None = None  # cache path or request id when available
    error: str | None = None


def resolve_affiliation(raw: str) -> RorResponse:
    """Resolve a raw affiliation string via ROR.

    Returns structured candidates. The calling affiliation stage decides
    acceptance, precedence, and persistence.
    """
    raise NotImplementedError(
        "ror.resolve_affiliation is a typed stub; Urmila implements behind this contract"
    )
