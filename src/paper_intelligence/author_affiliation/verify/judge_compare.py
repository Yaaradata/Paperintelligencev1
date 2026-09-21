"""Compare HTML vs OpenAlex affiliation claims for the LLM-judge workflow.

Missing OpenAlex data is NOT a disagreement. Only nonempty differing sets conflict.

HTML text without an organisation_id is still usable evidence: compare its
conservatively normalized name with OpenAlex before classifying. Same grounded
organisation → agreement (no LLM). Do not fuzzy-merge distinct organisations.
"""

from __future__ import annotations

from typing import Any, Iterable

from paper_intelligence.author_affiliation.verify.compare import (
    load_html_orgs,
    load_openalex_orgs_from_pi,
)
from paper_intelligence.author_affiliation.verify.html_resolve import (
    normalize_affiliation_candidate,
    resolve_local_organisation,
)
from paper_intelligence.author_affiliation.verify.openalex_gate import (
    fetch_openalex_work,
    note_pi_evidence_hit,
)
from paper_intelligence.author_affiliation.repository import fetch_paper, list_paper_authors


COMPARE_EXACT_MATCH = "exact_match"
COMPARE_DISAGREEMENT = "disagreement"
COMPARE_HTML_ONLY = "html_only"
COMPARE_OPENALEX_ONLY = "openalex_only"
COMPARE_NEITHER = "neither"
COMPARE_OA_UNAVAILABLE = "oa_unavailable"


def _resolve_ids_from_names(conn: Any, names: list[str]) -> set[int]:
    ids: set[int] = set()
    for name in names:
        res = resolve_local_organisation(conn, name)
        if res.get("organisation_id") is not None:
            ids.add(int(res["organisation_id"]))
    return ids


def normalized_name_keys(names: Iterable[str]) -> set[str]:
    """Conservative normalized keys for affiliation name comparison.

    Uses normalize_affiliation_candidate (strip geography/dept noise) plus the
    raw casefolded form. Exact key equality only — no fuzzy / edit-distance merge.
    """
    keys: set[str] = set()
    for raw in names:
        text = (raw or "").strip()
        if not text:
            continue
        keys.add(text.casefold())
        for cand in normalize_affiliation_candidate(text):
            keys.add(cand.casefold())
    return keys


def bridge_html_names_to_oa_ids(
    html_names: Iterable[str],
    oa_names: list[str],
    oa_ids: list[int],
) -> set[int]:
    """Map HTML name-only claims onto OA org IDs via normalized name equality.

    When OA provides parallel name/id lists, an HTML name whose normalized key
    matches an OA name key inherits that OA organisation_id. No fuzzy matching.
    """
    bridged: set[int] = set()
    if not oa_names or not oa_ids:
        return bridged
    key_to_ids: dict[str, set[int]] = {}
    n = min(len(oa_names), len(oa_ids))
    for i in range(n):
        try:
            oid = int(oa_ids[i])
        except (TypeError, ValueError):
            continue
        for key in normalized_name_keys([oa_names[i]]):
            key_to_ids.setdefault(key, set()).add(oid)

    for html_name in html_names:
        html_keys = normalized_name_keys([html_name])
        matched: set[int] = set()
        for key in html_keys:
            matched |= key_to_ids.get(key) or set()
        # Only accept when the HTML name maps to exactly one OA id (unambiguous).
        if len(matched) == 1:
            bridged |= matched
    return bridged


def collect_claims(
    conn: Any,
    paper_id: int,
    *,
    allow_openalex_network: bool = False,
) -> dict[str, Any]:
    """Gather HTML + OpenAlex claims for one paper (cache/PI preferred)."""
    paper = fetch_paper(conn, paper_id)
    authors = list_paper_authors(conn, paper_id)
    html = load_html_orgs(conn, paper_id)
    pi_oa = load_openalex_orgs_from_pi(conn, paper_id)

    html_ids = set(html.get("org_ids") or [])
    html_names = [
        n
        for n in (html.get("org_names") or [])
        if n and len(n) <= 120 and "default value of" not in n
    ]
    # Resolve provisional HTML names to IDs when possible (same org ≠ disagreement).
    html_ids |= _resolve_ids_from_names(conn, html_names)

    oa_ids = set(pi_oa.get("org_ids") or [])
    oa_names = list(pi_oa.get("org_names") or [])
    oa_source = "pi_evidence"
    oa_work: dict[str, Any] = {
        "work_id": None,
        "work_title": None,
        "identity_ok": bool(pi_oa.get("complete")),
        "identity_reason": "pi_evidence" if pi_oa.get("complete") else None,
        "work_status": "pi_evidence" if pi_oa.get("complete") else "missing",
        "pairs": [],
        "error": None,
    }

    if pi_oa.get("complete"):
        note_pi_evidence_hit()
        oa_ids |= _resolve_ids_from_names(conn, oa_names)
    else:
        fetch = fetch_openalex_work(
            paper.get("doi"),
            paper.get("arxiv_id"),
            title=paper.get("title"),
            conn=conn,
            paper_id=paper_id,
            allow_network=allow_openalex_network,
        )
        oa_work = {
            "work_id": fetch.get("work_id"),
            "work_title": fetch.get("work_title"),
            "identity_ok": fetch.get("identity_ok"),
            "identity_reason": fetch.get("identity_reason"),
            "work_status": fetch.get("work_status"),
            "pairs": fetch.get("pairs") or [],
            "error": fetch.get("error"),
            "strategy": fetch.get("strategy"),
            "cache_hit": fetch.get("cache_hit"),
            "api_called": fetch.get("api_called"),
        }
        if fetch.get("identity_ok") and fetch.get("org_names"):
            oa_names = list(fetch["org_names"])
            oa_ids |= _resolve_ids_from_names(conn, oa_names)
            oa_source = "cache" if fetch.get("cache_hit") else "api"
        elif fetch.get("work_status") in (
            "work_zero_institutions",
            "no_work_found",
            "fetch_failed",
            "identity_unverified",
            "no_identifier",
        ):
            oa_source = fetch.get("work_status") or "unavailable"

    # Bridge HTML name-only claims onto OA IDs via normalized name equality.
    bridged = bridge_html_names_to_oa_ids(html_names, list(oa_names), sorted(oa_ids))
    html_ids |= bridged

    return {
        "paper_id": int(paper_id),
        "arxiv_id": paper.get("arxiv_id"),
        "doi": paper.get("doi"),
        "title": paper.get("title"),
        "authors": [
            {
                "id": a["id"],
                "position": a.get("author_position"),
                "name": a.get("raw_name"),
            }
            for a in authors
        ],
        "html": {
            "has_evidence": bool(html.get("has_html_evidence")),
            "raw_sample": html.get("raw_sample") or [],
            "org_names": sorted(set(html_names)),
            "org_ids": sorted(html_ids),
            "linked_org_count": html.get("linked_org_count"),
            "provisional_names": html.get("provisional_names") or [],
            "bridged_oa_ids": sorted(bridged),
        },
        "openalex": {
            "source": oa_source,
            "org_names": sorted(set(oa_names)),
            "org_ids": sorted(oa_ids),
            **oa_work,
        },
    }


def names_agree_conservatively(
    html_names: Iterable[str], oa_names: Iterable[str]
) -> bool:
    """True when every name on each side shares a normalized key with the other.

    Requires mutual coverage (no leftover unmatched claim on either side).
    Does not use edit-distance or substring fuzzy merge across different orgs.
    """
    html_list = [n for n in html_names if (n or "").strip()]
    oa_list = [n for n in oa_names if (n or "").strip()]
    if not html_list or not oa_list:
        return False
    html_sets = [normalized_name_keys([n]) for n in html_list]
    oa_sets = [normalized_name_keys([n]) for n in oa_list]

    def _covers(src_sets: list[set[str]], dst_sets: list[set[str]]) -> bool:
        for sk in src_sets:
            if not any(sk & dk for dk in dst_sets):
                return False
        return True

    return _covers(html_sets, oa_sets) and _covers(oa_sets, html_sets)


def compare_claims(claims: dict[str, Any]) -> dict[str, Any]:
    """Classify compare path. Missing OA is not a disagreement.

    HTML usable text without organisation_id still counts as HTML evidence and is
    compared via conservative normalized names (and ID bridging done in collect).
    """
    html_ids = set(claims["html"].get("org_ids") or [])
    oa_ids = set(claims["openalex"].get("org_ids") or [])
    html_names = set(claims["html"].get("org_names") or [])
    oa_names = set(claims["openalex"].get("org_names") or [])
    html_keys = normalized_name_keys(html_names)
    oa_keys = normalized_name_keys(oa_names)

    html_usable = bool(html_ids or html_names or html_keys)
    oa_usable = bool(oa_ids or oa_names or oa_keys)

    # Prefer ID-set comparison when both sides resolved any IDs.
    if html_ids and oa_ids:
        if html_ids == oa_ids:
            status = COMPARE_EXACT_MATCH
        else:
            status = COMPARE_DISAGREEMENT
    elif html_usable and oa_usable:
        # Name-level compare with conservative normalization.
        # Missing HTML organisation_id ≠ missing HTML affiliation evidence.
        if names_agree_conservatively(html_names, oa_names):
            status = COMPARE_EXACT_MATCH
        else:
            status = COMPARE_DISAGREEMENT
    elif html_usable and not oa_usable:
        # Missing OA institutions / lookup failure → NOT disagreement
        status = COMPARE_HTML_ONLY
    elif oa_usable and not html_usable:
        status = COMPARE_OPENALEX_ONLY
    else:
        status = COMPARE_NEITHER

    needs_judge = status == COMPARE_DISAGREEMENT
    return {
        "compare_status": status,
        "needs_judge": needs_judge,
        "html_org_ids": sorted(html_ids),
        "oa_org_ids": sorted(oa_ids),
        "html_org_names": sorted(html_names),
        "oa_org_names": sorted(oa_names),
        "html_name_keys": sorted(html_keys),
        "oa_name_keys": sorted(oa_keys),
        "overlap_ids": sorted(html_ids & oa_ids),
        "html_only_ids": sorted(html_ids - oa_ids),
        "oa_only_ids": sorted(oa_ids - html_ids),
    }
