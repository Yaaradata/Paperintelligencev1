"""Grounding check: an organisation name must appear literally in the evidence text.

The policy deliberately does NOT require the evidence sentence itself to be a
literal substring of the source, so a paraphrased sentence that still contains
the organisation name is grounded.

Unicode letters are compared after NFKD diacritic folding so
`Universität Trier` grounds against `Universitat Trier` and vice versa.

Short single-token aliases (e.g. FAIR, MSR) are ambiguous English/common tokens
after casefolding. Those require an acronym-cased surface form in the raw
evidence so phrases like "fair comparison" never ground to Meta.
"""

from __future__ import annotations

import re
import unicodedata

_NON_WORD = re.compile(r"[^\w]+", re.UNICODE)
# Single alphabetic tokens this short collide with ordinary English after casefold.
_SHORT_ALIAS_MAX_LEN = 4


def normalise(text: str) -> str:
    """Casefold, strip diacritics, and reduce punctuation to single spaces."""
    decomposed = unicodedata.normalize("NFKD", text or "")
    folded = "".join(ch for ch in decomposed if not unicodedata.combining(ch))
    return _NON_WORD.sub(" ", folded).casefold().strip()


def requires_acronym_surface(organisation_name: str) -> bool:
    """True for short single-token names that must not match lowercase prose."""
    tokens = [t for t in (organisation_name or "").split() if t]
    if len(tokens) != 1:
        return False
    token = tokens[0]
    return token.isalpha() and len(token) <= _SHORT_ALIAS_MAX_LEN


def has_acronym_surface(organisation_name: str, evidence_text: str) -> bool:
    """True when `organisation_name` appears with mostly-uppercase letters in evidence.

    `FAIR` / `Fair` in affiliation text pass; bare `fair` in "fair comparison" fails.
    """
    token = (organisation_name or "").strip()
    if not token:
        return False
    pattern = re.compile(rf"(?<!\w){re.escape(token)}(?!\w)", re.IGNORECASE | re.UNICODE)
    for match in pattern.finditer(evidence_text or ""):
        surface = match.group(0)
        letters = [ch for ch in surface if ch.isalpha()]
        if not letters:
            continue
        upper = sum(1 for ch in letters if ch.isupper())
        if upper >= max(1, (len(letters) + 1) // 2):
            return True
    return False


def is_grounded(organisation_name: str, *evidence_texts: str) -> bool:
    """True when the organisation name appears literally in any supplied evidence text."""
    needle = normalise(organisation_name)
    if not needle:
        return False
    if requires_acronym_surface(organisation_name):
        return any(has_acronym_surface(organisation_name, text) for text in evidence_texts)
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
    if requires_acronym_surface(organisation_name):
        pattern = re.compile(
            rf"(?<!\w){re.escape(organisation_name.strip())}(?!\w)",
            re.IGNORECASE | re.UNICODE,
        )
        match = pattern.search(evidence_text or "")
        return match.group(0) if match else organisation_name
    # Match against a diacritic-folded view of the evidence, then map back to the
    # original slice length when possible; fall back to the canonical name.
    pattern = re.compile(
        r"\W+".join(re.escape(tok) for tok in normalise(organisation_name).split()),
        re.IGNORECASE | re.UNICODE,
    )
    folded_evidence = "".join(
        ch
        for ch in unicodedata.normalize("NFKD", evidence_text or "")
        if not unicodedata.combining(ch)
    )
    match = pattern.search(folded_evidence) or pattern.search(evidence_text or "")
    return match.group(0) if match else organisation_name
