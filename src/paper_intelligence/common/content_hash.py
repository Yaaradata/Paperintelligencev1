"""Deterministic paper content fingerprint for reuse / staleness checks."""

from __future__ import annotations

import hashlib
import unicodedata


def normalize_content_text(value: str | None) -> str:
    """Whitespace-collapse + NFC normalize (title/abstract fingerprint input)."""
    text = unicodedata.normalize("NFC", value or "")
    return " ".join(text.split())


def compute_content_hash(title: str | None, abstract: str | None) -> str:
    """sha256 hex of normalized title + abstract (separated by a newline)."""
    payload = f"{normalize_content_text(title)}\n{normalize_content_text(abstract)}"
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()
