"""Canonical identity normalization for the PI paper catalog."""

from __future__ import annotations

import re

_ARXIV_VERSION_RE = re.compile(r"[vV](\d+)$")
_ARXIV_PREFIX_RE = re.compile(r"^(?:arxiv:|https?://arxiv\.org/(?:abs|pdf)/)", re.I)


def normalize_arxiv_id(value: str | None) -> str | None:
    """Return bare arXiv id without version suffix.

    Examples:
      2609.12345v2 -> 2609.12345
      arxiv:2609.12345 -> 2609.12345
      https://arxiv.org/abs/2609.12345v1 -> 2609.12345
    """
    if value is None:
        return None
    text = str(value).strip()
    if not text:
        return None
    text = _ARXIV_PREFIX_RE.sub("", text)
    text = text.split("?", 1)[0].split("#", 1)[0]
    if text.lower().endswith(".pdf"):
        text = text[:-4]
    text = _ARXIV_VERSION_RE.sub("", text)
    text = text.strip().lower()
    return text or None


def extract_arxiv_version(value: str | None) -> int | None:
    """Return version integer if present on the raw arXiv id string."""
    if value is None:
        return None
    match = _ARXIV_VERSION_RE.search(str(value).strip())
    if not match:
        return None
    return int(match.group(1))


def normalize_doi(value: str | None) -> str | None:
    """Trim, lowercase, and strip common DOI URL prefixes."""
    if value is None:
        return None
    text = str(value).strip()
    if not text:
        return None
    lower = text.lower()
    for prefix in (
        "https://doi.org/",
        "http://doi.org/",
        "https://dx.doi.org/",
        "http://dx.doi.org/",
        "doi:",
    ):
        if lower.startswith(prefix):
            text = text[len(prefix) :]
            break
    text = text.strip().lower()
    return text or None
