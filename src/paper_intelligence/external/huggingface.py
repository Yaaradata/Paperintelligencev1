"""Hugging Face Papers / Daily Papers client — structured data only.

HF Daily Papers is a curation layer on arXiv (ids are arXiv ids). This client
returns payloads for enrichment; stages decide joins and persistence.
"""

from __future__ import annotations

import os
import threading
import time
from dataclasses import dataclass, field
from datetime import date, datetime, timezone
from typing import Any
from urllib.parse import urlencode

import requests

from paper_intelligence.cache.raw_store import find_cached, read_cached, request_hash, write_raw
from paper_intelligence.observability.runs import record_external_request

PROVIDER = "huggingface"
API_BASE = os.getenv("HF_API_BASE", "https://huggingface.co/api").rstrip("/")
REQUEST_SLEEP = float(os.getenv("HF_REQUEST_SLEEP", "0.3"))
MAX_RETRIES = int(os.getenv("HF_MAX_RETRIES", "3"))
TIMEOUT = float(os.getenv("HF_TIMEOUT", "30"))
HF_TOKEN = os.getenv("HF_TOKEN", "").strip() or os.getenv("HUGGINGFACE_HUB_TOKEN", "").strip()

_LOCK = threading.Lock()
_NEXT_ALLOWED = 0.0


@dataclass(frozen=True)
class HfDailyPapersPage:
    day: str
    papers: list[dict[str, Any]] = field(default_factory=list)
    raw_ref: str | None = None
    error: str | None = None


@dataclass(frozen=True)
class HfPaper:
    arxiv_id: str
    paper: dict[str, Any] = field(default_factory=dict)
    raw_ref: str | None = None
    error: str | None = None


def _throttle() -> None:
    global _NEXT_ALLOWED
    with _LOCK:
        wait = _NEXT_ALLOWED - time.time()
        if wait > 0:
            time.sleep(wait)
        _NEXT_ALLOWED = time.time() + REQUEST_SLEEP


def _headers() -> dict[str, str]:
    headers = {"User-Agent": "paper-intelligence/1.0 (hf-enrichment)"}
    if HF_TOKEN:
        headers["Authorization"] = f"Bearer {HF_TOKEN}"
    return headers


def _get_json(
    path: str,
    params: dict[str, Any] | None = None,
    *,
    conn: Any | None = None,
    run_id: str | None = None,
    stage_run_id: str | None = None,
    content_item_id: int | None = None,
    entity: str = "hf",
) -> tuple[Any | None, str | None, str | None]:
    """Return (payload, raw_ref, error)."""
    query = dict(params or {})
    endpoint = f"{API_BASE}/{path.lstrip('/')}"
    if query:
        endpoint_with_q = f"{endpoint}?{urlencode(query)}"
    else:
        endpoint_with_q = endpoint
    req_hash = request_hash(PROVIDER, endpoint, query)
    started = datetime.now(timezone.utc)

    cached = find_cached(PROVIDER, req_hash)
    if cached is not None:
        try:
            payload = read_cached(cached)
        except Exception:  # noqa: BLE001
            payload = None
        else:
            if conn is not None:
                record_external_request(
                    conn,
                    run_id=run_id,
                    stage_run_id=stage_run_id,
                    content_item_id=content_item_id,
                    provider=PROVIDER,
                    endpoint=endpoint_with_q,
                    request_hash=req_hash,
                    started_at=started,
                    http_status=200,
                    success=True,
                    cache_hit=True,
                    response_path=str(cached),
                )
            return payload, str(cached), None

    payload = None
    status = None
    error = None
    for attempt in range(1, MAX_RETRIES + 1):
        try:
            _throttle()
            response = requests.get(
                endpoint, params=query or None, headers=_headers(), timeout=TIMEOUT
            )
            status = response.status_code
            if status == 404:
                error = "not_found"
                break
            if status == 429 or status >= 500:
                if attempt < MAX_RETRIES:
                    time.sleep(min(20.0, 2 ** (attempt - 1)))
                    continue
                error = f"HTTP {status}"
                break
            if status >= 400:
                error = f"HTTP {status}: {response.text[:200]}"
                break
            payload = response.json()
            error = None
            break
        except Exception as exc:  # noqa: BLE001
            error = str(exc)
            if attempt < MAX_RETRIES:
                time.sleep(min(20.0, 2 ** (attempt - 1)))
                continue

    response_path = response_sha = None
    if payload is not None:
        response_path, response_sha = write_raw(PROVIDER, req_hash, entity, payload)

    if conn is not None:
        record_external_request(
            conn,
            run_id=run_id,
            stage_run_id=stage_run_id,
            content_item_id=content_item_id,
            provider=PROVIDER,
            endpoint=endpoint_with_q,
            request_hash=req_hash,
            started_at=started,
            http_status=status,
            success=error is None,
            cache_hit=False,
            response_path=response_path,
            response_sha256=response_sha,
            error_message=error,
        )
        conn.commit()

    return payload, response_path, error


def list_daily_papers(
    day: date | str,
    *,
    sort: str | None = None,
    limit: int | None = None,
    conn: Any | None = None,
    run_id: str | None = None,
    stage_run_id: str | None = None,
) -> HfDailyPapersPage:
    """Fetch HF Daily Papers for one calendar day (arXiv ids in paper.id).

    Do not use sort=trending with a date — HF returns a global trending list and
    ignores the day. Omit sort (or use publishedAt) for day-local curation.
    """
    day_str = day.isoformat() if isinstance(day, date) else str(day)[:10]
    params: dict[str, Any] = {"date": day_str}
    if sort:
        params["sort"] = sort
    if limit is not None:
        params["limit"] = int(limit)
    payload, raw_ref, error = _get_json(
        "daily_papers",
        params,
        conn=conn,
        run_id=run_id,
        stage_run_id=stage_run_id,
        entity=f"daily_{day_str}",
    )
    if error:
        return HfDailyPapersPage(day=day_str, error=error, raw_ref=raw_ref)
    papers = payload if isinstance(payload, list) else []
    return HfDailyPapersPage(day=day_str, papers=papers, raw_ref=raw_ref)


def get_paper(
    arxiv_id: str,
    *,
    conn: Any | None = None,
    run_id: str | None = None,
    stage_run_id: str | None = None,
    content_item_id: int | None = None,
) -> HfPaper:
    """Fetch one HF Paper Page by arXiv id."""
    aid = (arxiv_id or "").strip()
    if not aid:
        return HfPaper(arxiv_id=aid, error="empty_arxiv_id")
    payload, raw_ref, error = _get_json(
        f"papers/{aid}",
        None,
        conn=conn,
        run_id=run_id,
        stage_run_id=stage_run_id,
        content_item_id=content_item_id,
        entity=aid,
    )
    if error:
        return HfPaper(arxiv_id=aid, error=error, raw_ref=raw_ref)
    paper = payload if isinstance(payload, dict) else {}
    return HfPaper(arxiv_id=aid, paper=paper, raw_ref=raw_ref)
