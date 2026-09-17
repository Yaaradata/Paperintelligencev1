"""ROR client boundary — returns structured data only; no business decisions.

Every call is content-addressed: the request hash is computed first, the raw
cache is consulted, and only a miss reaches the network. Raw responses are
persisted verbatim so a rerun can replay without HTTP.
"""

from __future__ import annotations

import os
import threading
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any
from urllib.parse import urlencode

import requests

from paper_intelligence.cache.raw_store import find_cached, read_cached, request_hash, write_raw
from paper_intelligence.observability.runs import record_external_request

PROVIDER = "ror"
API_BASE = os.getenv("ROR_API_BASE", "https://api.ror.org")
REQUEST_SLEEP = float(os.getenv("ROR_REQUEST_SLEEP", "0.2"))
MAX_RETRIES = int(os.getenv("ROR_MAX_RETRIES", "3"))
TIMEOUT = float(os.getenv("ROR_TIMEOUT", "20"))

_LOCK = threading.Lock()
_NEXT_ALLOWED = 0.0


@dataclass(frozen=True)
class RorResponse:
    """Structured ROR lookup result. Empty matches mean unresolved, not error."""

    query: str
    matches: list[dict[str, Any]] = field(default_factory=list)
    raw_ref: str | None = None  # cache path or request id when available
    error: str | None = None


def _throttle() -> None:
    global _NEXT_ALLOWED
    with _LOCK:
        wait = _NEXT_ALLOWED - time.time()
        if wait > 0:
            time.sleep(wait)
        _NEXT_ALLOWED = time.time() + REQUEST_SLEEP


def _matches_from_payload(payload: Any) -> list[dict[str, Any]]:
    """ROR's affiliation endpoint returns scored `items`; pass them through as-is."""
    if not isinstance(payload, dict):
        return []
    items = payload.get("items")
    return [item for item in items if isinstance(item, dict)] if isinstance(items, list) else []


def resolve_affiliation(
    raw: str,
    *,
    conn: Any | None = None,
    run_id: str | None = None,
    stage_run_id: str | None = None,
    content_item_id: int | None = None,
) -> RorResponse:
    """Resolve a raw affiliation string via ROR.

    Returns structured candidates. The calling affiliation stage decides
    acceptance, precedence, and persistence.
    """
    query = (raw or "").strip()
    if not query:
        return RorResponse(query=query, matches=[], error="empty_query")

    endpoint = f"{API_BASE}/organizations"
    url = f"{endpoint}?{urlencode({'affiliation': query})}"
    req_hash = request_hash(PROVIDER, endpoint, {"affiliation": query})
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
            return RorResponse(
                query=query,
                matches=_matches_from_payload(payload),
                raw_ref=str(cached_path),
            )

    payload, status, error = _get(endpoint, {"affiliation": query})

    response_path: str | None = None
    response_sha: str | None = None
    if payload is not None:
        response_path, response_sha = write_raw(PROVIDER, req_hash, query[:60], payload)

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

    return RorResponse(
        query=query,
        matches=_matches_from_payload(payload),
        raw_ref=response_path,
        error=error,
    )


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
