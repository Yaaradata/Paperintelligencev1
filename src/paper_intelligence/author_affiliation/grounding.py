"""Grounding check: an organisation name must appear literally in the evidence text.

The policy deliberately does NOT require the evidence sentence itself to be a
literal substring of the source, so a paraphrased sentence that still contains
the organisation name is grounded.
"""

from __future__ import annotations

import re

_NON_WORD = re.compile(r"[^\w]+", re.UNICODE)


def normalise(text: str) -> str:
    """Casefold and reduce punctuation to single spaces, preserving unicode letters."""
    return _NON_WORD.sub(" ", (text or "")).casefold().strip()


def is_grounded(organisation_name: str, *evidence_texts: str) -> bool:
    """True when the organisation name appears literally in any supplied evidence text."""
    needle = normalise(organisation_name)
    if not needle:
        return False
    padded_needle = f" {needle} "
    for text in evidence_texts:
        haystack = normalise(text)
        if haystack and padded_needle in f" {haystack} ":
            return True
    return False


def grounding_span(organisation_name: str, evidence_text: str) -> str | None:
    """Return the literal slice of `evidence_text` that matched, for evidence_value."""
    if not is_grounded(organisation_name, evidence_text):
        return None
    pattern = re.compile(
        r"\W+".join(re.escape(tok) for tok in normalise(organisation_name).split()),
        re.IGNORECASE | re.UNICODE,
    )
    match = pattern.search(evidence_text or "")
    return match.group(0) if match else organisation_name
