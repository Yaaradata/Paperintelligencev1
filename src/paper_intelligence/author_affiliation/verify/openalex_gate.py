"""Bounded OpenAlex access for verification (cache-first, semaphore, backoff)."""

from __future__ import annotations

import os
import random
import threading
import time
from dataclasses import dataclass
from typing import Any

from paper_intelligence.cache.raw_store import find_cached, request_hash
from paper_intelligence.evaluation.org_coverage import openalex_lookup_identifier
from paper_intelligence.external import openalex as openalex_client

OPENALEX_MAX_CONCURRENCY = int(os.getenv("OPENALEX_MAX_CONCURRENCY", "4"))
PDF_MAX_CONCURRENCY = int(os.getenv("PDF_MAX_CONCURRENCY", "3"))

_oa_sem = threading.Semaphore(max(1, OPENALEX_MAX_CONCURRENCY))
_pdf_sem = threading.Semaphore(max(1, PDF_MAX_CONCURRENCY))
_stats_lock = threading.Lock()


@dataclass
class ExternalStats:
    cache_hits: int = 0  # raw_store hits + PI evidence reuse
    pi_evidence_hits: int = 0
    cache_misses: int = 0
    api_calls: int = 0
    count_429: int = 0
    retries: int = 0
    pdf_fallbacks: int = 0
    errors: int = 0
    no_work_found: int = 0
    work_zero_institutions: int = 0
    identity_rejected: int = 0

    def as_dict(self) -> dict[str, int]:
        return {
            "cache_hits": self.cache_hits,
            "pi_evidence_hits": self.pi_evidence_hits,
            "cache_misses": self.cache_misses,
            "api_calls": self.api_calls,
            "429s": self.count_429,
            "retries": self.retries,
            "pdf_fallbacks": self.pdf_fallbacks,
            "errors": self.errors,
            "no_work_found": self.no_work_found,
            "work_zero_institutions": self.work_zero_institutions,
            "identity_rejected": self.identity_rejected,
        }


GLOBAL_STATS = ExternalStats()


def _bump(**kwargs: int) -> None:
    with _stats_lock:
        for k, v in kwargs.items():
            setattr(GLOBAL_STATS, k, getattr(GLOBAL_STATS, k) + int(v))


def note_pi_evidence_hit() -> None:
    """Count existing PI OpenAlex rows as a cache hit (no external call)."""
    _bump(cache_hits=1, pi_evidence_hits=1)


def reset_stats() -> None:
    with _stats_lock:
        for f in GLOBAL_STATS.__dataclass_fields__:
            setattr(GLOBAL_STATS, f, 0)


def peek_cache(doi: str | None, arxiv_id: str | None) -> tuple[bool, str | None, str]:
    """Return (hit, identifier, strategy) without fetching."""
    identifier, strategy = openalex_lookup_identifier(doi, arxiv_id)
    if not identifier:
        return False, None, strategy
    path = openalex_client._path_for(identifier)  # noqa: SLF001
    endpoint = f"{openalex_client.API_BASE}/{path}"
    req_hash = request_hash(openalex_client.PROVIDER, endpoint, {"path": path})
    hit = find_cached(openalex_client.PROVIDER, req_hash) is not None
    return hit, identifier, strategy


def _pairs_and_names(work: dict[str, Any]) -> tuple[list[dict[str, Any]], list[str]]:
    pairs = openalex_client.authorship_institutions(work or {})
    names = sorted(
        {
            (p.get("institution_name") or "").strip().casefold()
            for p in pairs
            if (p.get("institution_name") or "").strip()
        }
    )
    return pairs, names


def _result(
    *,
    ok: bool,
    error: str | None,
    strategy: str,
    identifier: str | None,
    cache_hit: bool,
    api_called: bool,
    work: dict[str, Any] | None,
    identity_ok: bool | None = None,
    identity_reason: str | None = None,
    work_status: str | None = None,
) -> dict[str, Any]:
    pairs, names = _pairs_and_names(work or {})
    status = work_status
    if status is None:
        if error:
            status = "fetch_failed"
        elif not work or not work.get("id"):
            status = "no_work_found"
        elif not identity_ok:
            status = "identity_unverified"
        elif names:
            status = "work_with_institutions"
        else:
            status = "work_zero_institutions"
            _bump(work_zero_institutions=1)
    return {
        "ok": ok and bool(names),
        "error": error,
        "strategy": strategy,
        "identifier": identifier,
        "cache_hit": cache_hit,
        "api_called": api_called,
        "pairs": pairs,
        "org_names": names,
        "work_id": (work or {}).get("id"),
        "work_title": (work or {}).get("display_name"),
        "identity_ok": identity_ok,
        "identity_reason": identity_reason,
        "work_status": status,
        "raw_ref": None,
    }


def fetch_openalex_work(
    doi: str | None,
    arxiv_id: str | None,
    *,
    title: str | None = None,
    conn: Any | None = None,
    paper_id: int | None = None,
    allow_network: bool = True,
) -> dict[str, Any]:
    """Cache-first OpenAlex work fetch under a global concurrency bound.

    On DOI/DataCite 404, optionally falls back to title search with strict
    identity validation. Distinguishes fetch failure / no work / zero institutions.
    """
    identifier, strategy = openalex_lookup_identifier(doi, arxiv_id)
    if not identifier and not (title or "").strip():
        return _result(
            ok=False,
            error="no_identifier",
            strategy=strategy,
            identifier=None,
            cache_hit=False,
            api_called=False,
            work=None,
            work_status="no_identifier",
        )

    work: dict[str, Any] = {}
    cache_hit = False
    api_called = False
    last_err: str | None = None
    used_strategy = strategy
    used_ident = identifier

    if identifier:
        path = openalex_client._path_for(identifier)  # noqa: SLF001
        endpoint = f"{openalex_client.API_BASE}/{path}"
        req_hash = request_hash(openalex_client.PROVIDER, endpoint, {"path": path})
        cached = find_cached(openalex_client.PROVIDER, req_hash)
        if cached is not None:
            _bump(cache_hits=1)
            fetched = openalex_client.get_work(
                identifier, conn=conn, content_item_id=paper_id
            )
            cache_hit = True
            if fetched.error:
                last_err = fetched.error
                # Fall through to network/title if cache was error-shaped / miss.
            else:
                work = fetched.work or {}
        else:
            _bump(cache_misses=1)
            if allow_network:
                acquired = _oa_sem.acquire(timeout=120)
                if not acquired:
                    _bump(errors=1)
                    return _result(
                        ok=False,
                        error="openalex_semaphore_timeout",
                        strategy=strategy,
                        identifier=identifier,
                        cache_hit=False,
                        api_called=False,
                        work=None,
                        work_status="fetch_failed",
                    )
                try:
                    for attempt in range(4):
                        _bump(api_calls=1)
                        api_called = True
                        time.sleep(random.uniform(0.05, 0.35) * (1 + attempt * 0.25))
                        fetched = openalex_client.get_work(
                            identifier, conn=conn, content_item_id=paper_id
                        )
                        err = fetched.error or ""
                        last_err = err or None
                        retriable = any(
                            tok in err.lower()
                            for tok in (
                                "429",
                                "500",
                                "502",
                                "503",
                                "504",
                                "timeout",
                                "timed out",
                                "connection",
                            )
                        )
                        if not err:
                            work = fetched.work or {}
                            break
                        if "429" in err:
                            _bump(count_429=1)
                        if not retriable or attempt == 3:
                            _bump(errors=1)
                            break
                        _bump(retries=1)
                        time.sleep(min(60.0, (2.0 ** attempt) + random.uniform(0, 1.5)))
                finally:
                    _oa_sem.release()
            else:
                last_err = "cache_miss_network_disabled"

    # Title-search fallback when DOI/DataCite path found no work (404 / empty).
    need_title_fallback = (not work.get("id")) and bool((title or "").strip()) and allow_network
    if need_title_fallback and (last_err in (None, "http_404") or strategy == "arxiv_datacite_doi"):
        acquired = _oa_sem.acquire(timeout=120)
        if acquired:
            try:
                _bump(api_calls=1)
                api_called = True
                time.sleep(random.uniform(0.05, 0.25))
                results, search_err = openalex_client.search_works(
                    title=title,
                    arxiv_id=arxiv_id,
                    conn=conn,
                    content_item_id=paper_id,
                    per_page=5,
                )
                if search_err:
                    last_err = search_err
                    _bump(errors=1)
                else:
                    used_strategy = f"{strategy}+title_search" if strategy else "title_search"
                    chosen = None
                    chosen_reason = None
                    for cand in results:
                        ok_id, reason = openalex_client.validate_work_identity(
                            cand, doi=doi, arxiv_id=arxiv_id, title=title
                        )
                        if ok_id:
                            chosen = cand
                            chosen_reason = reason
                            break
                        _bump(identity_rejected=1)
                    if chosen:
                        work = chosen
                        last_err = None
                        used_ident = chosen.get("id")
                        identity_ok, identity_reason = True, chosen_reason
                        pairs, names = _pairs_and_names(work)
                        status = (
                            "work_with_institutions"
                            if names
                            else "work_zero_institutions"
                        )
                        if status == "work_zero_institutions":
                            _bump(work_zero_institutions=1)
                        return {
                            **_result(
                                ok=bool(names),
                                error=None,
                                strategy=used_strategy,
                                identifier=used_ident,
                                cache_hit=False,
                                api_called=True,
                                work=work,
                                identity_ok=True,
                                identity_reason=identity_reason,
                                work_status=status,
                            ),
                        }
                    last_err = last_err or "no_identity_verified_search_hit"
                    _bump(no_work_found=1)
                    return _result(
                        ok=False,
                        error=last_err,
                        strategy=used_strategy,
                        identifier=used_ident,
                        cache_hit=cache_hit,
                        api_called=True,
                        work=None,
                        identity_ok=False,
                        identity_reason="no_candidate_passed_identity",
                        work_status="no_work_found",
                    )
            finally:
                _oa_sem.release()

    if not work.get("id"):
        if last_err == "http_404":
            _bump(no_work_found=1)
            return _result(
                ok=False,
                error="http_404",
                strategy=used_strategy,
                identifier=used_ident,
                cache_hit=cache_hit,
                api_called=api_called,
                work=None,
                work_status="no_work_found",
            )
        if last_err:
            return _result(
                ok=False,
                error=last_err,
                strategy=used_strategy,
                identifier=used_ident,
                cache_hit=cache_hit,
                api_called=api_called,
                work=None,
                work_status="fetch_failed",
            )
        _bump(no_work_found=1)
        return _result(
            ok=False,
            error="no_work_found",
            strategy=used_strategy,
            identifier=used_ident,
            cache_hit=cache_hit,
            api_called=api_called,
            work=None,
            work_status="no_work_found",
        )

    identity_ok, identity_reason = openalex_client.validate_work_identity(
        work, doi=doi, arxiv_id=arxiv_id, title=title
    )
    # DOI-path fetches already used a strong identifier; accept with doi/arxiv strategy.
    if not identity_ok and strategy in ("doi", "arxiv_datacite_doi") and not need_title_fallback:
        # Soft-accept DOI-path works but record reason — DOI path is deterministic.
        if strategy == "doi":
            identity_ok, identity_reason = True, "doi_path_fetch"
        elif strategy == "arxiv_datacite_doi":
            # User rule: do not assume arxiv_datacite_doi is automatically correct.
            # Require title corroboration when available.
            if (title or "").strip():
                identity_ok, identity_reason = openalex_client.validate_work_identity(
                    work, doi=None, arxiv_id=arxiv_id, title=title
                )
            else:
                identity_ok, identity_reason = False, "arxiv_datacite_unconfirmed"

    if not identity_ok:
        _bump(identity_rejected=1)
        return _result(
            ok=False,
            error="work_identity_unverified",
            strategy=used_strategy,
            identifier=used_ident,
            cache_hit=cache_hit,
            api_called=api_called,
            work=work,
            identity_ok=False,
            identity_reason=identity_reason,
            work_status="identity_unverified",
        )

    pairs, names = _pairs_and_names(work)
    status = "work_with_institutions" if names else "work_zero_institutions"
    if status == "work_zero_institutions":
        _bump(work_zero_institutions=1)
    return {
        **_result(
            ok=bool(names),
            error=None,
            strategy=used_strategy,
            identifier=used_ident,
            cache_hit=cache_hit,
            api_called=api_called,
            work=work,
            identity_ok=True,
            identity_reason=identity_reason,
            work_status=status,
        ),
    }


def pdf_fallback_probe(
    arxiv_id: str | None,
    *,
    html_available: bool,
) -> dict[str, Any]:
    """Bounded PDF slot — record need only; do not download unless caller extracts."""
    if html_available or not arxiv_id:
        return {"attempted": False, "needed": False, "reason": "html_present_or_no_arxiv"}
    acquired = _pdf_sem.acquire(timeout=30)
    if not acquired:
        return {"attempted": False, "needed": True, "reason": "pdf_semaphore_timeout"}
    try:
        _bump(pdf_fallbacks=1)
        return {
            "attempted": False,
            "needed": True,
            "reason": "pdf_extraction_pending",
            "arxiv_pdf_url": f"https://arxiv.org/pdf/{arxiv_id}",
        }
    finally:
        _pdf_sem.release()
