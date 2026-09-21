"""OpenAlex client boundary — structured data only; no business decisions."""

from __future__ import annotations

import os
import re
import threading
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any
from urllib.parse import quote, urlencode

import requests

from paper_intelligence.cache.raw_store import find_cached, read_cached, request_hash, write_raw
from paper_intelligence.observability.runs import record_external_request

PROVIDER = "openalex"
API_BASE = os.getenv("OPENALEX_API_BASE", "https://api.openalex.org")
REQUEST_SLEEP = float(os.getenv("OPENALEX_REQUEST_SLEEP", "1.0"))
MAX_RETRIES = int(os.getenv("OPENALEX_MAX_RETRIES", "3"))
TIMEOUT = float(os.getenv("OPENALEX_TIMEOUT", "30"))

_LOCK = threading.Lock()
_NEXT_ALLOWED = 0.0

_DOI_PREFIX = re.compile(r"^(https?://(dx\.)?doi\.org/|doi:)", re.I)


@dataclass(frozen=True)
class OpenAlexWork:
    identifier: str
    work: dict[str, Any] = field(default_factory=dict)
    raw_ref: str | None = None
    error: str | None = None


def _throttle() -> None:
    global _NEXT_ALLOWED
    with _LOCK:
        wait = _NEXT_ALLOWED - time.time()
        if wait > 0:
            time.sleep(wait)
        _NEXT_ALLOWED = time.time() + REQUEST_SLEEP


def normalize_doi(value: str | None) -> str | None:
    if not value:
        return None
    return _DOI_PREFIX.sub("", str(value).strip()).strip().lower() or None


def _path_for(identifier: str) -> str:
    """DOIs go to /works/doi:<doi>; anything else is treated as an OpenAlex id."""
    ident = identifier.strip()
    if _DOI_PREFIX.match(ident) or ident.lower().startswith("10."):
        return f"works/doi:{quote(normalize_doi(ident) or ident, safe='')}"
    ident = ident.rsplit("/", 1)[-1]
    return f"works/{quote(ident, safe='')}"


def get_work(
    identifier: str,
    *,
    conn: Any | None = None,
    run_id: str | None = None,
    stage_run_id: str | None = None,
    content_item_id: int | None = None,
) -> OpenAlexWork:
    """Fetch an OpenAlex work by DOI, OpenAlex ID, or other supported identifier.

    Returns structured work payload. Calling stages decide matching and persistence.
    Error-shaped cache payloads (e.g. OpenAlex ``message`` without ``id``) are
    treated as cache misses — never as valid empty-institution works.
    """
    ident = (identifier or "").strip()
    if not ident:
        return OpenAlexWork(identifier=ident, error="empty_identifier")

    path = _path_for(ident)
    endpoint = f"{API_BASE}/{path}"
    params: dict[str, str] = {}
    mailto = os.getenv("OPENALEX_MAILTO", "").strip()
    if mailto:
        params["mailto"] = mailto

    url = f"{endpoint}?{urlencode(params)}" if params else endpoint
    # mailto is a politeness header, not part of the identity of the request.
    req_hash = request_hash(PROVIDER, endpoint, {"path": path})
    started_at = datetime.now(timezone.utc)

    cached_path = find_cached(PROVIDER, req_hash)
    if cached_path is not None:
        try:
            payload = read_cached(cached_path)
        except Exception:  # noqa: BLE001 — a corrupt cache entry must not be fatal
            payload = None
        else:
            if _is_error_shaped_payload(payload):
                # Do not treat failed lookups cached as JSON errors as valid works.
                payload = None
            elif isinstance(payload, dict) and payload.get("id"):
                _log(
                    conn,
                    run_id=run_id,
                    stage_run_id=stage_run_id,
                    content_item_id=content_item_id,
                    endpoint=url,
                    req_hash=req_hash,
                    started_at=started_at,
                    http_status=200,
                    success=True,
                    cache_hit=True,
                    response_path=str(cached_path),
                )
                return OpenAlexWork(
                    identifier=ident,
                    work=payload,
                    raw_ref=str(cached_path),
                )

    payload, status, error = _get(endpoint, params)

    response_path: str | None = None
    response_sha: str | None = None
    # Only cache successful work payloads — never 404/error bodies.
    if payload is not None and error is None and not _is_error_shaped_payload(payload):
        response_path, response_sha = write_raw(PROVIDER, req_hash, ident[:60], payload)

    _log(
        conn,
        run_id=run_id,
        stage_run_id=stage_run_id,
        content_item_id=content_item_id,
        endpoint=url,
        req_hash=req_hash,
        started_at=started_at,
        http_status=status,
        success=error is None,
        cache_hit=False,
        response_path=response_path,
        response_sha256=response_sha,
        error_message=error,
    )

    return OpenAlexWork(
        identifier=ident,
        work=payload if isinstance(payload, dict) and not _is_error_shaped_payload(payload) else {},
        raw_ref=response_path,
        error=error,
    )


def _is_error_shaped_payload(payload: Any) -> bool:
    """True when a cached/parsed body is an OpenAlex error, not a Work."""
    if not isinstance(payload, dict):
        return True
    if payload.get("id") and str(payload.get("id")).startswith("https://openalex.org/W"):
        return False
    if payload.get("id") and "/works/" in str(payload.get("id")):
        return False
    # OpenAlex error JSON often has message/error without a work id.
    if payload.get("message") or payload.get("error"):
        return True
    if not payload.get("id") and not payload.get("authorships") and not payload.get("display_name"):
        return True
    return False


def search_works(
    *,
    title: str | None = None,
    arxiv_id: str | None = None,
    conn: Any | None = None,
    content_item_id: int | None = None,
    per_page: int = 5,
) -> tuple[list[dict[str, Any]], str | None]:
    """Search OpenAlex works. Returns (results, error). Does not invent matches."""
    params: dict[str, str] = {"per_page": str(per_page)}
    mailto = os.getenv("OPENALEX_MAILTO", "").strip()
    if mailto:
        params["mailto"] = mailto
    query = (title or "").strip()
    if not query and arxiv_id:
        query = (arxiv_id or "").strip()
    if not query:
        return [], "empty_search_query"
    params["search"] = query
    endpoint = f"{API_BASE}/works"
    # Cache key includes search string.
    req_hash = request_hash(PROVIDER, endpoint, {"search": query, "per_page": str(per_page)})
    cached_path = find_cached(PROVIDER, req_hash)
    if cached_path is not None:
        try:
            payload = read_cached(cached_path)
            if isinstance(payload, dict) and "results" in payload:
                return list(payload.get("results") or []), None
        except Exception:  # noqa: BLE001
            pass

    payload, status, error = _get(endpoint, params)
    if payload is not None and error is None and isinstance(payload, dict):
        write_raw(PROVIDER, req_hash, f"search:{(query or '')[:40]}", payload)
        return list(payload.get("results") or []), None
    return [], error or f"http_{status}"


def validate_work_identity(
    work: dict[str, Any],
    *,
    doi: str | None,
    arxiv_id: str | None,
    title: str | None,
) -> tuple[bool, str]:
    """Conservative identity check before trusting an OpenAlex Work.

    Returns (ok, reason). arxiv_datacite_doi alone is not sufficient — prefer
    arXiv id / DOI in work.ids or a strong title match.
    """
    if not work or not work.get("id"):
        return False, "not_a_work"
    ids = work.get("ids") or {}
    work_doi = normalize_doi(ids.get("doi") or "")
    want_doi = normalize_doi(doi)
    if want_doi and work_doi and want_doi == work_doi:
        return True, "doi_match"

    aid = (arxiv_id or "").strip().lower()
    if aid:
        # ids may include arxiv forms; also scan locations landing pages.
        blob = json_dumps_lower(ids)
        if aid in blob or f"arxiv.org/abs/{aid}" in blob or f"arxiv.org/pdf/{aid}" in blob:
            return True, "arxiv_id_in_work_ids"
        for loc in work.get("locations") or []:
            if not isinstance(loc, dict):
                continue
            for key in ("landing_page_url", "pdf_url"):
                url = (loc.get(key) or "").lower()
                if aid in url:
                    return True, "arxiv_id_in_location_url"
        # DataCite DOI on the work
        if work_doi and work_doi.endswith(aid):
            return True, "arxiv_datacite_on_work"

    # Title fallback — require high similarity; never accept weak first-hit search.
    wt = (work.get("display_name") or "").strip().casefold()
    pt = (title or "").strip().casefold()
    if wt and pt:
        if wt == pt:
            return True, "exact_title"
        # Token Jaccard on significant tokens
        def toks(s: str) -> set[str]:
            return {t for t in re.findall(r"[a-z0-9]+", s) if len(t) > 2}

        a, b = toks(wt), toks(pt)
        if a and b:
            j = len(a & b) / len(a | b)
            if j >= 0.85 and abs(len(wt) - len(pt)) <= max(20, int(0.2 * max(len(wt), len(pt)))):
                return True, f"title_jaccard_{j:.2f}"
            return False, f"title_mismatch_jaccard_{j:.2f}"
        return False, "title_token_empty"
    return False, "insufficient_identity_evidence"


def json_dumps_lower(obj: Any) -> str:
    try:
        import json as _json

        return _json.dumps(obj, default=str).lower()
    except Exception:  # noqa: BLE001
        return str(obj).lower()


def authorship_institutions(work: dict[str, Any]) -> list[dict[str, Any]]:
    """Flatten a work's authorships into author/institution pairs. No matching logic."""
    pairs: list[dict[str, Any]] = []
    for authorship in (work or {}).get("authorships") or []:
        if not isinstance(authorship, dict):
            continue
        author = authorship.get("author") or {}
        raw_name = authorship.get("raw_author_name") or author.get("display_name")
        for institution in authorship.get("institutions") or []:
            if not isinstance(institution, dict) or not institution.get("display_name"):
                continue
            pairs.append(
                {
                    "author_name": raw_name,
                    "author_position": authorship.get("author_position"),
                    "openalex_author_id": author.get("id"),
                    "institution_name": institution["display_name"],
                    "ror_id": institution.get("ror"),
                    "openalex_institution_id": institution.get("id"),
                    "country_code": institution.get("country_code"),
                    "institution_type": institution.get("type"),
                    "raw_affiliation_strings": authorship.get("raw_affiliation_strings") or [],
                }
            )
    return pairs


def _get(endpoint: str, params: dict[str, str]) -> tuple[Any | None, int | None, str | None]:
    """GET with polite throttling and bounded retries. Never raises."""
    status: int | None = None
    error: str | None = None
    for attempt in range(MAX_RETRIES):
        _throttle()
        try:
            response = requests.get(
                endpoint,
                params=params,
                timeout=TIMEOUT,
                headers={"Accept": "application/json", "User-Agent": _user_agent()},
            )
        except Exception as exc:  # noqa: BLE001 — network failure is data, not a crash
            error = f"{type(exc).__name__}: {exc}"
            time.sleep(min(8.0, 2**attempt))
            continue

        status = response.status_code
        if status == 200:
            try:
                return response.json(), status, None
            except ValueError as exc:
                return None, status, f"invalid_json: {exc}"
        if status == 429 or status >= 500:
            error = f"http_{status}"
            time.sleep(min(30.0, 2**attempt))
            continue
        return None, status, f"http_{status}"

    return None, status, error or "retries_exhausted"


def _user_agent() -> str:
    mailto = os.getenv("OPENALEX_MAILTO", "").strip()
    return f"PaperIntelligenceV1/1.0 (mailto:{mailto})" if mailto else "PaperIntelligenceV1/1.0"


def _log(conn: Any | None, **kwargs: Any) -> None:
    """Best-effort external_requests logging; skipped entirely when conn is None."""
    if conn is None:
        return
    try:
        record_external_request(
            conn,
            provider=PROVIDER,
            request_hash=kwargs.pop("req_hash"),
            **kwargs,
        )
        conn.commit()
    except Exception:  # noqa: BLE001 — observability must never break the caller
        try:
            conn.rollback()
        except Exception:  # noqa: BLE001
            pass
