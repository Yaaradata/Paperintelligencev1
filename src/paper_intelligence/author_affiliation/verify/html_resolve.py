"""Conservative HTML affiliation text → local organisation resolution.

Does not call ROR network by default. Does not promote provisional names to
canonical organisations without a grounded local match. Never unions sources.
"""

from __future__ import annotations

import re
from typing import Any

from paper_intelligence.organisation_resolution.repository import (
    find_organisation_by_alias,
    find_organisation_by_name,
)

# Strip trailing geography / noise that blocks exact alias match.
_COUNTRY_SUFFIX = re.compile(
    r"[,\s]+("
    r"usa|u\.s\.a\.|u\.s\.|united states(?: of america)?|uk|u\.k\.|"
    r"united kingdom|england|scotland|wales|ireland|canada|australia|"
    r"germany|france|italy|spain|china|japan|india|korea|brazil|"
    r"switzerland|sweden|norway|finland|netherlands|belgium|austria|"
    r"poland|portugal|denmark|israel|singapore|taiwan|hong kong|"
    r"beijing|shanghai|shenzhen|hangzhou|nanjing|wuhan|guangzhou|"
    r"london|paris|berlin|munich|zurich|geneva|tokyo|seoul|sydney|"
    r"new york|california|massachusetts|texas|illinois"
    r")\s*$",
    re.I,
)
_PUNCT_RUN = re.compile(r"[\u2013\u2014\-_/|]+")
_MULTI_SPACE = re.compile(r"\s+")
_DEPT_PREFIX = re.compile(
    r"^(department|dept|school|faculty|laboratory|laboratoire|lab|center|centre|"
    r"institute of|institut)\b.*?\b(of|for|de|di|für)\b\s+",
    re.I,
)
_TRUNCATED = frozenset(
    {
        "university",
        "université",
        "universität",
        "college",
        "institute",
        "institut",
        "laboratoire",
        "laboratory",
        "école",
        "ecole",
        "department",
        "lab",
        "school",
    }
)
_NON_ORG = re.compile(
    r"^(note:|orcid|corresponding author|independent researcher|equal contribution)",
    re.I,
)


def normalize_affiliation_candidate(raw: str) -> list[str]:
    """Generate conservative lookup candidates from one affiliation string."""
    if not raw or not raw.strip():
        return []
    text = _MULTI_SPACE.sub(" ", raw.strip())
    if _NON_ORG.match(text):
        return []
    low = text.casefold()
    if low in _TRUNCATED or len(text) < 4:
        return []

    out: list[str] = []
    seen: set[str] = set()

    def add(s: str) -> None:
        s = _MULTI_SPACE.sub(" ", s).strip(" ,;")
        if len(s) < 4:
            return
        key = s.casefold()
        if key in seen or key in _TRUNCATED:
            return
        seen.add(key)
        out.append(s)

    add(text)
    # Split multi-org "A; B" / "A and B" cautiously (only on semicolon)
    if ";" in text:
        for part in text.split(";"):
            add(part)

    stripped = _COUNTRY_SUFFIX.sub("", text).strip(" ,;")
    add(stripped)
    stripped2 = _COUNTRY_SUFFIX.sub("", stripped).strip(" ,;")
    add(stripped2)

    no_punct = _PUNCT_RUN.sub(" ", stripped2)
    add(no_punct)

    # Drop leading department clause when a university/institute remains after.
    dept_stripped = _DEPT_PREFIX.sub("", stripped2)
    if dept_stripped.casefold() != stripped2.casefold():
        add(dept_stripped)

    # "X University of Y" keep as-is; also try without Inc./Ltd.
    for suf in (", Inc.", " Inc.", ", Ltd.", " Ltd.", ", LLC", " LLC", " GmbH"):
        if text.endswith(suf) or text.lower().endswith(suf.lower()):
            add(text[: -len(suf)])
            add(stripped2[: -len(suf)] if stripped2.lower().endswith(suf.lower()) else stripped2)

    return out


def classify_html_evidence_value(raw: str) -> str:
    """Bucket a single evidence_value string."""
    if not raw or not raw.strip():
        return "empty"
    text = raw.strip()
    low = text.casefold()
    if _NON_ORG.match(text) or low in {"ling chen"}:  # known author-as-affiliation
        return "non_organisation_text"
    if low in _TRUNCATED or len(text) < 4:
        return "truncated_affiliation_text"
    if _DEPT_PREFIX.match(text) and not re.search(
        r"\b(universit|college|institut|inc\.?|ltd\.?|corp|gmbh|labs?)\b", text, re.I
    ):
        return "department_only"
    # Ambiguous short brand / lab names
    if len(text) <= 12 and not re.search(
        r"\b(universit|college|institut|inc\.?|ltd|corp|gmbh)\b", text, re.I
    ):
        return "ambiguous_institution_name"
    return "valid_organisation_text"


def resolve_local_organisation(
    conn: Any, raw: str
) -> dict[str, Any]:
    """Try local name/alias match on normalized candidates. No network. No writes."""
    candidates = normalize_affiliation_candidate(raw)
    value_class = classify_html_evidence_value(raw)
    if not candidates:
        return {
            "organisation_id": None,
            "matched_candidate": None,
            "match_type": None,
            "value_class": value_class,
            "candidates_tried": [],
        }
    for cand in candidates:
        oid = find_organisation_by_name(conn, cand)
        if oid is not None:
            return {
                "organisation_id": int(oid),
                "matched_candidate": cand,
                "match_type": "canonical_name",
                "value_class": value_class,
                "candidates_tried": candidates,
            }
        oid = find_organisation_by_alias(conn, cand)
        if oid is not None:
            return {
                "organisation_id": int(oid),
                "matched_candidate": cand,
                "match_type": "alias",
                "value_class": value_class,
                "candidates_tried": candidates,
            }
    return {
        "organisation_id": None,
        "matched_candidate": None,
        "match_type": None,
        "value_class": value_class,
        "candidates_tried": candidates,
    }
