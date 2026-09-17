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
                work=payload if isinstance(payload, dict) else {},
                raw_ref=str(cached_path),
            )

    payload, status, error = _get(endpoint, params)

    response_path: str | None = None
    response_sha: str | None = None
    if payload is not None:
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
        work=payload if isinstance(payload, dict) else {},
        raw_ref=response_path,
        error=error,
    )


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
