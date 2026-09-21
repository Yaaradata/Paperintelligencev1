"""Per-paper verification flow (safe to run under many workers)."""

from __future__ import annotations

import time
from typing import Any

from paper_intelligence.author_affiliation.verify.compare import (
    classify_verification,
    load_html_orgs,
    load_openalex_orgs_from_pi,
    needs_openalex_refresh,
    org_names_from_openalex_pairs,
)
from paper_intelligence.author_affiliation.verify.openalex_gate import (
    fetch_openalex_work,
    note_pi_evidence_hit,
    pdf_fallback_probe,
)


def verify_one_paper(
    conn: Any,
    paper_id: int,
    *,
    allow_openalex_network: bool = True,
    force_openalex_refresh: bool = False,
    phase: str = "full",
) -> dict[str, Any]:
    """Run compare-only verification for one paper. Does not mutate affiliation rows.

    phase:
      local — PI/cache evidence only; may emit needs_openalex_lookup / needs_pdf_review
      oa    — allow OpenAlex network when PI incomplete
      full  — OA network + PDF probe markers
    """
    t0 = time.perf_counter()
    timing: dict[str, float] = {}
    allow_deferred = phase == "local"
    allow_network = bool(allow_openalex_network) and phase in ("oa", "full", "pdf")

    t = time.perf_counter()
    paper = conn.execute(
        """
        SELECT paper_id, arxiv_id, doi, title, published_at::date AS pub
        FROM paper_intelligence.papers
        WHERE paper_id = %s
        """,
        (int(paper_id),),
    ).fetchone()
    timing["db_paper_ms"] = (time.perf_counter() - t) * 1000
    if not paper:
        return {
            "ok": False,
            "error": "paper_not_found",
            "outcome": "unresolved",
            "timing_ms": timing,
        }

    t = time.perf_counter()
    html = load_html_orgs(conn, paper_id)
    timing["html_ms"] = (time.perf_counter() - t) * 1000

    t = time.perf_counter()
    pi_oa = load_openalex_orgs_from_pi(conn, paper_id)
    timing["pi_oa_ms"] = (time.perf_counter() - t) * 1000

    oa_source = "pi_evidence"
    oa_fetch: dict[str, Any] | None = None
    oa_names = set(pi_oa.get("org_names") or [])

    refresh = needs_openalex_refresh(pi_oa, force=force_openalex_refresh)
    if phase == "local":
        # Phase 1: never call network; only use existing PI OA (and raw_store is
        # checked only in phase oa via fetch).
        if pi_oa.get("complete"):
            note_pi_evidence_hit()
        refresh = False
        timing["oa_wait_ms"] = 0.0
    elif refresh:
        t = time.perf_counter()
        oa_fetch = fetch_openalex_work(
            paper.get("doi"),
            paper.get("arxiv_id"),
            title=paper.get("title"),
            conn=conn,
            paper_id=paper_id,
            allow_network=allow_network,
        )
        timing["oa_wait_ms"] = (time.perf_counter() - t) * 1000
        if oa_fetch.get("org_names"):
            oa_names = set(oa_fetch["org_names"])
            oa_source = "cache" if oa_fetch.get("cache_hit") else "api"
        elif oa_fetch.get("pairs"):
            oa_names = org_names_from_openalex_pairs(oa_fetch["pairs"])
            oa_source = "cache" if oa_fetch.get("cache_hit") else "api"
        else:
            oa_source = "fetch_empty_or_error"
    else:
        note_pi_evidence_hit()
        timing["oa_wait_ms"] = 0.0

    t = time.perf_counter()
    pdf = {"attempted": False, "needed": False, "reason": "phase_skip"}
    if phase in ("full", "pdf"):
        pdf = pdf_fallback_probe(
            paper.get("arxiv_id"),
            html_available=bool(html.get("has_html_evidence"))
            and bool(html.get("org_names")),
        )
    timing["pdf_ms"] = (time.perf_counter() - t) * 1000

    html_names = set(html.get("org_names") or [])
    has_id = bool(paper.get("doi") or paper.get("arxiv_id"))
    outcome = classify_verification(
        html_names=html_names,
        oa_names=oa_names,
        html_available=bool(html.get("has_html_evidence")),
        oa_available=bool(oa_names) or bool(pi_oa.get("has_pi_openalex_evidence")),
        has_doi_or_arxiv=has_id,
        allow_deferred=allow_deferred,
        canonicalisation_gap=bool(html.get("canonicalisation_gap")),
    )

    timing["total_ms"] = (time.perf_counter() - t0) * 1000
    return {
        "ok": True,
        "error": None
        if (oa_fetch is None or oa_fetch.get("ok") or not refresh)
        else oa_fetch.get("error"),
        "outcome": outcome,
        "paper_id": int(paper_id),
        "arxiv_id": paper.get("arxiv_id"),
        "doi": paper.get("doi"),
        "title": paper.get("title"),
        "published_on": str(paper.get("pub")),
        "phase": phase,
        "html": {
            "has_evidence": html.get("has_html_evidence"),
            "org_names": sorted(html_names),
            "org_ids": html.get("org_ids"),
            "row_count": html.get("row_count"),
            "linked_org_count": html.get("linked_org_count"),
            "provisional_names": html.get("provisional_names"),
            "canonicalisation_gap": html.get("canonicalisation_gap"),
            "raw_sample": html.get("raw_sample"),
        },
        "openalex": {
            "source": oa_source,
            "org_names": sorted(oa_names),
            "pi_complete": pi_oa.get("complete"),
            "refresh_attempted": refresh,
            "cache_hit": None if oa_fetch is None else oa_fetch.get("cache_hit"),
            "api_called": None if oa_fetch is None else oa_fetch.get("api_called"),
            "fetch_error": None if oa_fetch is None else oa_fetch.get("error"),
            "strategy": None if oa_fetch is None else oa_fetch.get("strategy"),
        },
        "pdf": pdf,
        "agreement": {
            "exact": html_names == oa_names and bool(html_names),
            "overlap": sorted(html_names & oa_names),
            "html_only": sorted(html_names - oa_names),
            "oa_only": sorted(oa_names - html_names),
        },
        "timing_ms": timing,
        "merged_orgs": None,
    }
