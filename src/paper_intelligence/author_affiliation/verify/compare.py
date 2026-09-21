"""Load HTML / OpenAlex org evidence and classify without merging."""

from __future__ import annotations

import re
from typing import Any

OUTCOMES = (
    "verified_agreement",
    "partial_agreement",
    "verified_html_primary",
    "verified_openalex_primary",
    "conflict",
    "unresolved",
    "needs_openalex_lookup",
    "needs_pdf_review",
)

# Affiliation strings that are not organisation names for verification.
_NOISE_PREFIXES = (
    "note:",
    "orcid",
    "corresponding author",
    "equal contribution",
    "these authors",
)
_NOISE_EXACT = {
    "university",  # truncated parse
    "école",
    "ecole",
    "laboratoire",
    "department",
    "lab",
}
_ORG_HINT = re.compile(
    r"\b("
    r"universit|college|institut|inc\.?|ltd\.?|corp|gmbh|llc|labs?|"
    r"laborator|center|centre|academy|polytechnique|hospital|foundation|"
    r"research|national|agency|authority|school of|faculty|"
    r"inria|cnrs|epfl|eth\b|baidu|google|microsoft|ibm|meta\b"
    r")",
    re.I,
)


def _is_noise_affiliation(value: str) -> bool:
    v = value.strip()
    if len(v) < 3:
        return True
    low = v.casefold()
    if low in _NOISE_EXACT:
        return True
    if any(low.startswith(p) for p in _NOISE_PREFIXES):
        return True
    if low.startswith("independent researcher"):
        return True
    return False


def provisional_org_name_from_evidence(value: str | None) -> str | None:
    """Use unresolved HTML evidence_value as a provisional org name when ROR missed.

    Does not invent organisations — only surfaces non-noise affiliation text so
    verification does not falsely prefer OpenAlex when HTML had a real string.
    """
    if not value:
        return None
    v = value.strip()
    if _is_noise_affiliation(v):
        return None
    # Prefer strings that look institutional; still keep company-like short names
    # (e.g. "BrightMind AI", "Glasp") when they are the only affiliation text.
    if _ORG_HINT.search(v) or len(v) >= 4:
        return v.casefold()
    return None


def load_html_orgs(conn: Any, paper_id: int) -> dict[str, Any]:
    """Canonical + provisional org names from HTML-path evidence.

    When organisation_id is NULL, fall back to cleaned evidence_value so a ROR
    miss does not erase HTML evidence (asymmetry vs OpenAlex path).
    """
    rows = conn.execute(
        """
        SELECT a.organisation_id, o.canonical_name, a.evidence_type, a.evidence_source,
               a.evidence_value, a.confidence
        FROM paper_intelligence.paper_author_affiliations a
        LEFT JOIN paper_intelligence.organisations o ON o.id = a.organisation_id
        WHERE a.content_item_id = %s
          AND (
            a.evidence_source ILIKE '%%arxiv.org/html%%'
            OR a.evidence_source ILIKE '%%arxiv.html%%'
            OR a.evidence_type = 'explicit_paper_affiliation'
            OR (
              a.evidence_type IN ('ror_canonical_match', 'email_domain')
              AND EXISTS (
                SELECT 1 FROM paper_intelligence.paper_author_affiliations h
                WHERE h.content_item_id = a.content_item_id
                  AND (
                    h.evidence_source ILIKE '%%arxiv.org/html%%'
                    OR h.evidence_source ILIKE '%%arxiv.html%%'
                    OR h.evidence_type = 'explicit_paper_affiliation'
                  )
              )
            )
          )
        """,
        (int(paper_id),),
    ).fetchall()
    org_ids: set[int] = set()
    org_names: set[str] = set()
    provisional_names: set[str] = set()
    raw_values: list[str] = []
    linked_count = 0
    html_row_count = 0
    for r in rows:
        html_row_count += 1
        if r["organisation_id"] is not None:
            org_ids.add(int(r["organisation_id"]))
            linked_count += 1
        name = (r["canonical_name"] or "").strip()
        if name:
            org_names.add(name.casefold())
        val = (r["evidence_value"] or "").strip()
        if val:
            raw_values.append(val)
            if not name:
                prov = provisional_org_name_from_evidence(val)
                if prov:
                    provisional_names.add(prov)
                    org_names.add(prov)
    has_html = conn.execute(
        """
        SELECT EXISTS (
          SELECT 1 FROM paper_intelligence.paper_author_affiliations
          WHERE content_item_id = %s
            AND (
              evidence_source ILIKE '%%arxiv.org/html%%'
              OR evidence_source ILIKE '%%arxiv.html%%'
              OR evidence_type = 'explicit_paper_affiliation'
            )
        ) AS e
        """,
        (int(paper_id),),
    ).fetchone()["e"]
    return {
        "has_html_evidence": bool(has_html),
        "row_count": html_row_count,
        "linked_org_count": linked_count,
        "org_ids": sorted(org_ids),
        "org_names": sorted(org_names),
        "provisional_names": sorted(provisional_names),
        "raw_sample": raw_values[:20],
        "canonicalisation_gap": bool(provisional_names) and linked_count == 0,
    }


def load_openalex_orgs_from_pi(conn: Any, paper_id: int) -> dict[str, Any]:
    """Existing PI-stored OpenAlex affiliation evidence (no API call)."""
    rows = conn.execute(
        """
        SELECT a.organisation_id, o.canonical_name, a.evidence_value, a.confidence,
               o.openalex_id, o.ror_id
        FROM paper_intelligence.paper_author_affiliations a
        LEFT JOIN paper_intelligence.organisations o ON o.id = a.organisation_id
        WHERE a.content_item_id = %s
          AND a.evidence_type = 'openalex_paper_specific'
        """,
        (int(paper_id),),
    ).fetchall()
    org_ids: set[int] = set()
    org_names: set[str] = set()
    raw_values: list[str] = []
    for r in rows:
        if r["organisation_id"] is not None:
            org_ids.add(int(r["organisation_id"]))
        name = (r["canonical_name"] or r["evidence_value"] or "").strip()
        if name:
            org_names.add(name.casefold())
        val = (r["evidence_value"] or "").strip()
        if val:
            raw_values.append(val)
    return {
        "has_pi_openalex_evidence": len(rows) > 0,
        "row_count": len(rows),
        "org_ids": sorted(org_ids),
        "org_names": sorted(org_names),
        "raw_sample": raw_values[:20],
        "complete": len(rows) > 0 and len(org_names) > 0,
    }


def org_names_from_openalex_pairs(pairs: list[dict[str, Any]]) -> set[str]:
    names: set[str] = set()
    for pair in pairs:
        name = (pair.get("institution_name") or "").strip()
        if name:
            names.add(name.casefold())
    return names


def classify_verification(
    *,
    html_names: set[str],
    oa_names: set[str],
    html_available: bool,
    oa_available: bool,
    has_doi_or_arxiv: bool = False,
    allow_deferred: bool = False,
    canonicalisation_gap: bool = False,
) -> str:
    """Classify without unioning conflicting sets.

    Phase 1 (allow_deferred): emit needs_openalex_lookup / needs_pdf_review only
    when neither side yields usable orgs (or HTML is a pure canonicalisation gap
    with no provisional text). HTML-only papers are html_primary — OA network is
    a later prioritised phase, not automatic for every HTML row.
    """
    if html_names and oa_names:
        if html_names == oa_names:
            return "verified_agreement"
        if html_names & oa_names:
            return "partial_agreement"
        return "conflict"
    if html_names and not oa_names:
        return "verified_html_primary" if (html_available or html_names) else "unresolved"
    if oa_names and not html_names:
        # OA-primary only when HTML truly has no usable org text.
        return "verified_openalex_primary" if (oa_available or oa_names) else "unresolved"
    # neither side has org names
    if allow_deferred:
        if html_available and canonicalisation_gap:
            # Had HTML rows but all filtered as noise / truncated — try OA before PDF
            return "needs_openalex_lookup" if has_doi_or_arxiv else "needs_pdf_review"
        if has_doi_or_arxiv:
            return "needs_openalex_lookup"
        return "needs_pdf_review"
    return "unresolved"


def needs_openalex_refresh(pi_oa: dict[str, Any], *, force: bool = False) -> bool:
    """Prefer existing PI OpenAlex evidence; refresh only if incomplete/suspicious."""
    if force:
        return True
    if not pi_oa.get("has_pi_openalex_evidence"):
        return True
    if not pi_oa.get("complete"):
        return True
    if pi_oa.get("row_count", 0) > 0 and not pi_oa.get("org_names"):
        return True
    return False
