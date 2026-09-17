"""Parse upstream affiliation text into candidate organisation names and emails.

Extraction is textual only: nothing here infers an institution from author
names, paper topic, or writing style.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any

_LABEL = re.compile(
    r"^\s*(affiliation|affiliations|email|e-mail|emails|address|corresponding author|"
    r"correspondence|institution|authors?|thanks|acknowledg\w*|keywords?|subjects?|"
    r"comments?|title|abstract|cite as|doi)\s*:\s*",
    re.IGNORECASE,
)
# Labels whose content is never an affiliation. Author lists in particular must
# never be read as institutional evidence.
_DROP_LABELS = frozenset(
    {
        "author",
        "authors",
        "keyword",
        "keywords",
        "subject",
        "subjects",
        "comment",
        "comments",
        "title",
        "abstract",
        "cite as",
        "doi",
    }
)
_ARXIV_NOISE = re.compile(r"^\[?\s*(submitted|revised|updated|v\d+)\b", re.IGNORECASE)
# HTML/PDF footnote junk that is not institutional evidence.
# Include Unicode asterisk ∗ (U+2217) and dagger forms common in PDF extracts.
_FOOTNOTE_MARKERS = r"[*∗†‡※✦•·∙⋆]+"
_FOOTNOTE_NOISE = re.compile(
    r"^(?:"
    r"footnot(?:e|etext)\b|"
    rf"{_FOOTNOTE_MARKERS}\s*equal\s+contribution|"
    r"equal\s+contribution|"
    rf"{_FOOTNOTE_MARKERS}\s*equal\b|"
    r"contributed\s+equally|"
    r"these\s+authors\s+contributed\s+equally"
    r")",
    re.IGNORECASE,
)
# Author-list lines sometimes arrive without a clean label match.
_AUTHORS_LINE = re.compile(r"^\s*authors?\s*:", re.IGNORECASE)
# Acknowledgement prose often names the institution, but is mostly boilerplate.
# Keep it only when it actually yields an organisation name.
_CANDIDATES_ONLY_LABELS = frozenset({"thanks", "acknowledgement", "acknowledgements", "acknowledgment", "acknowledgments"})
_EMAIL = re.compile(r"[\w.+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}")
_DOMAIN_IN_TEXT = re.compile(r"@([A-Za-z0-9.-]+\.[A-Za-z]{2,})")
# Glued corruption like `hariharanr@arizona.edusomeshwaran` or `a@x.comedub`.
_GLUED_EMAIL_DOMAIN = re.compile(
    r"\.(edu|com|org|net|gov|ac)([a-z0-9])",
    re.IGNORECASE,
)
_WS = re.compile(r"\s+")
_FOOTNOTE = re.compile(r"^[\s\d*∗†‡§¶#,.;()\[\]-]+")

# Tokens that make a comma-separated segment look like a standalone organisation.
_ORG_TOKENS = (
    "university",
    "universite",
    "université",
    "universität",
    "universitat",
    "universidad",
    "universidade",
    "università",
    "universiteit",
    "univ",
    "institute",
    "institution",
    "instituto",
    "institut",
    "college",
    "academy",
    "academia",
    "akademi",
    "polytechnic",
    "politecnico",
    "laboratory",
    "laboratories",
    "laboratoire",
    "hospital",
    "clinic",
    "medical center",
    "medical centre",
    "foundation",
    "corporation",
    "company",
    "technologies",
    "research center",
    "research centre",
    "research institute",
    "research lab",
    "research laboratory",
    "observatory",
    "museum",
    "ministry",
    "agency",
    "consortium",
    "society",
    "hochschule",
    "escuela",
    "ecole",
    "école",
)
_ORG_SUFFIXES = ("inc", "ltd", "llc", "plc", "gmbh", "ag", "bv", "sa", "spa", "pte", "pvt")

# Head nouns an organisation name is built around.
_HEAD_TOKEN = re.compile(
    r"(?:Universit(?:y|ies|e|é|ät|at|à|eit|y's)|Univ\.?|Institute|Institut|Instituto|Institutes|"
    r"College|Academy|Akademie|Polytechnic|Politecnico|Laboratory|Laboratories|Laboratoire|"
    r"Hospital|Clinic|Observatory|Museum|Foundation|Corporation|Consortium|Hochschule|"
    r"Universidad|Universidade|Universit\u00e0|Universiteit|\u00c9cole|Ecole|Escuela)",
    re.IGNORECASE,
)
_NAME_JOINERS = frozenset({"of", "for", "the", "and", "de", "del", "di", "du", "des", "der", "von"})
_PREPOSITIONS = frozenset({"of", "for", "de", "del", "di", "du", "des", "der", "von", "in", "at"})

# A segment starting with one of these is an internal sub-unit, not the organisation.
_SUBUNIT_PREFIXES = (
    "department",
    "dept",
    "faculty",
    "division",
    "group",
    "section",
    "chair",
    "unit",
    "program",
    "programme",
)

PUBLIC_EMAIL_DOMAINS = frozenset(
    {
        "gmail.com",
        "googlemail.com",
        "yahoo.com",
        "hotmail.com",
        "outlook.com",
        "live.com",
        "icloud.com",
        "me.com",
        "aol.com",
        "protonmail.com",
        "proton.me",
        "qq.com",
        "163.com",
        "126.com",
        "foxmail.com",
        "mail.ru",
        "yandex.ru",
        "example.com",
    }
)


@dataclass(frozen=True)
class AffiliationLine:
    """One raw affiliation string plus the organisation names we could read out of it."""

    raw: str
    candidates: list[str] = field(default_factory=list)


@dataclass(frozen=True)
class ExtractedEvidence:
    lines: list[AffiliationLine] = field(default_factory=list)
    emails: list[str] = field(default_factory=list)
    domains: list[str] = field(default_factory=list)

    @property
    def is_empty(self) -> bool:
        return not self.lines and not self.emails and not self.domains


def _clean(text: str) -> str:
    return _WS.sub(" ", _FOOTNOTE.sub("", (text or "").strip())).strip(" ,;.")


def _looks_like_organisation(segment: str) -> bool:
    lowered = segment.casefold()
    if any(lowered.startswith(prefix) for prefix in _SUBUNIT_PREFIXES):
        return False
    if any(token in lowered for token in _ORG_TOKENS):
        return True
    tail = lowered.rstrip(".").rsplit(" ", 1)[-1].strip(".")
    return tail in _ORG_SUFFIXES


def _is_head(token: str) -> bool:
    return bool(_HEAD_TOKEN.fullmatch(token.strip(".,;:()[]")))


def _is_capitalised(token: str) -> bool:
    stripped = token.strip(".,;:()[]&")
    return bool(stripped) and stripped[0].isupper()


def _is_name_word(token: str) -> bool:
    """A word that can belong to an organisation name: capitalised, or a lowercase joiner."""
    stripped = token.strip(".,;:()[]&")
    if not stripped:
        return False
    return stripped.casefold() in _NAME_JOINERS or _is_capitalised(stripped)


def organisation_phrases(segment: str) -> list[str]:
    """Pull organisation-name phrases out of a free-text segment.

    Grows outwards from a head noun such as `University` or `Institute`, so
    `Department of Mathematics Purdue University` yields `Purdue University`
    and `Massachusetts Institute of Technology` survives intact.
    """
    tokens = segment.split()
    phrases: list[str] = []
    for index, token in enumerate(tokens):
        if not _is_head(token):
            continue
        # Grow left over capitalised words only. Crossing a joiner such as `of`
        # would swallow the sub-unit that owns it (`Department of Mathematics`).
        start = index
        while start > 0 and _is_capitalised(tokens[start - 1]) and index - start < 4:
            start -= 1
        # `Department of Mathematics Purdue University`: the word right after
        # `of` is the sub-unit's object, not part of this organisation's name.
        if start > 0 and start < index and tokens[start - 1].casefold() in _PREPOSITIONS:
            start += 1

        end = index + 1
        if (
            end < len(tokens)
            and tokens[end].casefold() in _NAME_JOINERS
            and end + 1 < len(tokens)
            and _is_name_word(tokens[end + 1])
        ):
            end += 1
            while end < len(tokens) and _is_name_word(tokens[end]) and end - index < 6:
                end += 1

        phrase = _clean(" ".join(tokens[start:end]))
        if len(phrase) >= 4 and phrase not in phrases:
            phrases.append(phrase)
    return phrases


def organisation_candidates(line: str) -> list[str]:
    """Organisation names readable from an affiliation line, longest form first."""
    candidates: list[str] = []
    seen: set[str] = set()

    def add(value: str) -> None:
        key = value.casefold()
        if key not in seen and len(value) >= 4:
            seen.add(key)
            candidates.append(value)

    for segment in re.split(r"[,;|]|\s+–\s+|\s+-\s+", line or ""):
        cleaned = _clean(segment)
        if len(cleaned) < 4 or _EMAIL.search(cleaned):
            continue
        phrases = organisation_phrases(cleaned)
        if phrases:
            for phrase in phrases:
                add(phrase)
        elif _looks_like_organisation(cleaned) or _is_name_like_segment(cleaned):
            add(cleaned)
    return candidates


def _is_name_like_segment(segment: str) -> bool:
    """A short proper-noun phrase with no head noun, e.g. `Google DeepMind`.

    These only become organisations if a later tier canonicalises them and the
    grounding check passes, so a city or venue here is harmless.
    """
    tokens = segment.split()
    if not 2 <= len(tokens) <= 6 or any(ch.isdigit() for ch in segment):
        return False
    if tokens[0].casefold() in _SUBUNIT_PREFIXES:
        return False
    if len(tokens[-1].strip(".")) <= 3 and tokens[-1].strip(".").isupper():
        return False  # trailing state / country code, e.g. `Cambridge MA`
    return all(_is_name_word(token) for token in tokens) and any(
        _is_capitalised(token) for token in tokens
    )


def _is_noise_affiliation_line(text: str) -> bool:
    """True for author-list / equal-contribution / footnote markers, not orgs."""
    body = (text or "").strip()
    if not body:
        return True
    if _AUTHORS_LINE.match(body):
        return True
    if _FOOTNOTE_NOISE.match(body):
        return True
    # PDF extracts often prefix footnotes with ∗ / † before the prose.
    without_markers = _FOOTNOTE.sub("", body).strip()
    if without_markers and _FOOTNOTE_NOISE.match(without_markers):
        return True
    # After stripping a leading label, body may still be pure contribution noise.
    stripped = _LABEL.sub("", body).strip()
    if stripped and _FOOTNOTE_NOISE.match(stripped):
        return True
    stripped_markers = _FOOTNOTE.sub("", stripped).strip() if stripped else ""
    if stripped_markers and _FOOTNOTE_NOISE.match(stripped_markers):
        return True
    return False


def is_corrupt_email(email: str) -> bool:
    """Conservative guard against HTML/PDF-glued addresses.

    Accepts normal institutional emails. Rejects clear concatenations such as
    `user@arizona.edusomeshwaran` or locals that start with `.`.
    """
    value = (email or "").strip().lower()
    if not value or value.startswith(".") or value.endswith("."):
        return True
    if value.count("@") != 1:
        return True
    local, _, domain = value.partition("@")
    if not local or not domain or "." not in domain:
        return True
    if _GLUED_EMAIL_DOMAIN.search(domain):
        return True
    # Domain labels must look like DNS labels; reject empties / leading dots.
    labels = domain.split(".")
    if any(not label or label.startswith("-") or label.endswith("-") for label in labels):
        return True
    tld = labels[-1]
    if not tld.isalpha() or len(tld) > 24:
        return True
    return False


def emails_from_text(text: str) -> list[str]:
    out: list[str] = []
    for match in _EMAIL.finditer(text or ""):
        email = match.group(0).lower()
        if not is_corrupt_email(email) and email not in out:
            out.append(email)
    return out


def domains_from_text(text: str) -> list[str]:
    """Domains including brace-grouped forms like `{a, b}@nus.edu.sg` that are not full emails."""
    out: list[str] = []
    for match in _DOMAIN_IN_TEXT.finditer(text or ""):
        domain = match.group(1).lower().strip(".")
        if not domain or domain in out:
            continue
        # Reuse the glued-email guard against `arizona.edusomeshwaran`.
        if is_corrupt_email(f"x@{domain}"):
            continue
        out.append(domain)
    return out


def _coerce_strings(value: Any) -> list[str]:
    if value is None:
        return []
    if isinstance(value, str):
        return [value] if value.strip() else []
    if isinstance(value, list):
        out: list[str] = []
        for item in value:
            if isinstance(item, str) and item.strip():
                out.append(item)
            elif isinstance(item, dict):
                for key in ("affiliation", "text", "name", "value", "email"):
                    if isinstance(item.get(key), str) and item[key].strip():
                        out.append(item[key])
                        break
        return out
    return []


def extract(affiliation_text: Any, extracted_emails: Any) -> ExtractedEvidence:
    """Turn `paper_metadata.affiliation_text` / `extracted_emails` into usable evidence."""
    lines: list[AffiliationLine] = []
    emails: list[str] = []
    domains: list[str] = []
    seen_lines: set[str] = set()

    def note_contacts(text: str) -> bool:
        found = emails_from_text(text)
        emails.extend(found)
        seen_domain = False
        for domain in domains_from_text(text):
            seen_domain = True
            if domain not in domains and domain not in PUBLIC_EMAIL_DOMAINS:
                domains.append(domain)
        return bool(found) or seen_domain

    for entry in _coerce_strings(affiliation_text):
        if _is_noise_affiliation_line(entry):
            continue
        label = _LABEL.match(entry)
        body = _clean(_LABEL.sub("", entry))
        if not body:
            continue
        if _is_noise_affiliation_line(body):
            continue
        has_contact = note_contacts(body)
        label_name = (label.group(1).lower() if label else "")
        if label_name in {"email", "e-mail", "emails"} or label_name in _DROP_LABELS:
            continue
        if _ARXIV_NOISE.match(body) or _ARXIV_NOISE.match(entry.strip()):
            continue
        if body.casefold() in {"corresponding author", "n/a", "none"}:
            continue
        key = body.casefold()
        if key in seen_lines:
            continue
        seen_lines.add(key)
        candidates = organisation_candidates(body)
        if (
            not candidates
            and label_name in {"affiliation", "affiliations", "institution"}
            and 0 < len(body.split()) <= 6
        ):
            # Short labelled lines like "FAIR at Meta" have no university/institute
            # token but are still the paper's own affiliation string.
            candidates = [body]
        if not candidates and (has_contact or label_name in _CANDIDATES_ONLY_LABELS):
            # Contact-only lines add nothing beyond their domains, and
            # acknowledgement boilerplate is not affiliation evidence.
            continue
        lines.append(AffiliationLine(raw=body, candidates=candidates))

    for entry in _coerce_strings(extracted_emails):
        note_contacts(entry)

    deduped_emails: list[str] = []
    for email in emails:
        if email not in deduped_emails:
            deduped_emails.append(email)

    return ExtractedEvidence(lines=lines, emails=deduped_emails, domains=domains)


def institutional_domains(evidence: ExtractedEvidence) -> list[str]:
    """Non-public email domains visible in the evidence, in order of first appearance."""
    return [d for d in evidence.domains if d not in PUBLIC_EMAIL_DOMAINS]
