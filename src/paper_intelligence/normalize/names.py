"""Author name parsing and light normalisation (unicode-preserving)."""

from __future__ import annotations

import re
from typing import Any

_WS = re.compile(r"\s+")


def normalize_author_name(raw: str) -> str:
    """Collapse whitespace only. Preserve unicode / non-Latin characters and case."""
    return _WS.sub(" ", raw.strip())


def coerce_author_entries(authors_raw: Any) -> list[str]:
    """Turn authors_raw JSON into an ordered list of raw name strings.

    Production shape is a JSON array of strings. Also accepts a single string,
    or objects with name/fullname/raw_name. Empty / null → []. Never raises.
    """
    if authors_raw is None:
        return []
    if isinstance(authors_raw, str):
        text = authors_raw.strip()
        return [text] if text else []
    if not isinstance(authors_raw, list):
        return []

    names: list[str] = []
    for entry in authors_raw:
        if entry is None:
            continue
        if isinstance(entry, str):
            text = entry.strip()
            if text:
                names.append(text)
            continue
        if isinstance(entry, dict):
            candidate = entry.get("name") or entry.get("fullname") or entry.get("raw_name")
            if isinstance(candidate, str) and candidate.strip():
                names.append(candidate.strip())
    return names


def authors_to_rows(authors_raw: Any) -> list[dict[str, str | int]]:
    """Build paper_authors payloads: 1-based position, raw_name, normalized_name."""
    rows: list[dict[str, str | int]] = []
    for index, raw in enumerate(coerce_author_entries(authors_raw), start=1):
        rows.append(
            {
                "author_position": index,
                "raw_name": raw,
                "normalized_name": normalize_author_name(raw),
            }
        )
    return rows
