"""Fetch author affiliation strings from arXiv HTML (or abs) pages.

arXiv Atom/OAI ingest usually leaves affiliation_text empty. The HTML
rendering of the paper often has the real institutions and emails, which is
what this client extracts. Structured data only — no canonicalisation.
"""

from __future__ import annotations

import os
import re
import threading
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any
from urllib.parse import urlencode

import requests
from bs4 import BeautifulSoup

from paper_intelligence.cache.raw_store import find_cached, read_cached, request_hash, write_raw
from paper_intelligence.observability.runs import record_external_request

PROVIDER = "arxiv"
REQUEST_SLEEP = float(os.getenv("ARXIV_HTML_REQUEST_SLEEP", "0.3"))
MAX_RETRIES = int(os.getenv("ARXIV_HTML_MAX_RETRIES", "3"))
TIMEOUT = float(os.getenv("ARXIV_HTML_TIMEOUT", "25"))
EMAIL_RE = re.compile(r"[A-Za-z0-9._%+\-]+@[A-Za-z0-9.\-]+\.[A-Za-z]{2,}")
# Many arXiv HTML papers put institutions only in LaTeXML footnotes:
#   <span class="ltx_note ltx_role_footnotetext">…Google Research.</span>
_FOOTNOTE_PREFIX_RE = re.compile(
    r"^(?:"
    r"(?:\d+\s*)+"  # note marks like "1" / "0 0"
    r"|footnotetext\s*:\s*"
    r"|footnote\s*:\s*"
    r")+",
    re.I,
)
_META_FOOTNOTE_RE = re.compile(
    r"^(?:"
    r"co[- ]?first authors?"
    r"|equal(?:ly)? contributing"
    r"|corresponding authors?"
    r"|these authors contributed equally"
    r")\b",
    re.I,
)

_LOCK = threading.Lock()
_NEXT_ALLOWED = 0.0


@dataclass(frozen=True)
class ArxivAffiliationPage:
    arxiv_id: str
    emails: list[str] = field(default_factory=list)
    affiliations: list[str] = field(default_factory=list)
    evidence_url: str | None = None
    raw_ref: str | None = None
    error: str | None = None


def _throttle() -> None:
    global _NEXT_ALLOWED
    with _LOCK:
        wait = _NEXT_ALLOWED - time.time()
        if wait > 0:
            time.sleep(wait)
        _NEXT_ALLOWED = time.time() + REQUEST_SLEEP


def _clean(text: str) -> str:
    return " ".join((text or "").split()).strip()


def _clean_footnote(text: str) -> str:
    """Strip LaTeXML footnote chrome; keep the institution / note body."""
    cleaned = _clean(text)
    # Drop leading note-mark / "footnotetext:" labels that soup concatenates.
    while True:
        updated = _FOOTNOTE_PREFIX_RE.sub("", cleaned).strip(" .;")
        updated = _clean(updated)
        if updated == cleaned:
            break
        cleaned = updated
    # Emails are returned separately; strip them from affiliation candidates.
    cleaned = EMAIL_RE.sub("", cleaned)
    cleaned = re.sub(r"(?i)\bemails?\s*:\s*", "", cleaned)
    return _clean(cleaned).strip(" .;,")


def _is_meta_footnote(text: str) -> bool:
    """True for authorship/email footnotes that are not organisation names."""
    if not text:
        return True
    if _META_FOOTNOTE_RE.match(text):
        return True
    # After stripping emails, a footnote that is only "Co-first authors" / empty.
    remainder = _META_FOOTNOTE_RE.sub("", text).strip(" .;,")
    return not remainder


def _add_affiliation(affiliations: list[str], seen: set[str], text: str) -> None:
    if not text:
        return
    if EMAIL_RE.fullmatch(text.replace("Email:", "").strip()):
        return
    key = text.casefold()
    if key in seen:
        return
    seen.add(key)
    affiliations.append(text[:1500])


def _parse(html: str) -> tuple[list[str], list[str]]:
    emails = sorted(set(EMAIL_RE.findall(html or "")))
    soup = BeautifulSoup(html or "", "lxml")
    affiliations: list[str] = []
    seen: set[str] = set()

    # Explicit affiliation nodes (common when authors list institutions inline).
    for selector in (
        ".ltx_contact.ltx_role_affiliation",
        ".ltx_role_affiliation",
        ".ltx_affiliation",
        ".ltx_contact",
        ".authors",
        ".author",
        ".dateline",
    ):
        for node in soup.select(selector):
            _add_affiliation(affiliations, seen, _clean(node.get_text(" ", strip=True)))

    # Footnotes — many papers only declare orgs here (e.g. "1 Google Research.").
    for selector in (
        ".ltx_role_footnotetext",
        ".ltx_note.ltx_role_footnotetext",
        "span.ltx_note",
        ".ltx_author_notes",
    ):
        for node in soup.select(selector):
            body = _clean_footnote(node.get_text(" ", strip=True))
            if _is_meta_footnote(body):
                continue
            _add_affiliation(affiliations, seen, body)

    return emails, affiliations[:30]


def fetch_affiliations(
    arxiv_id: str,
    *,
    conn: Any | None = None,
    run_id: str | None = None,
    stage_run_id: str | None = None,
    content_item_id: int | None = None,
) -> ArxivAffiliationPage:
    """Return emails + affiliation strings from arXiv HTML (falls back to /abs)."""
    aid = (arxiv_id or "").strip()
    if not aid:
        return ArxivAffiliationPage(arxiv_id=aid, error="empty_arxiv_id")

    last_error: str | None = None
    for path in (f"html/{aid}", f"abs/{aid}"):
        endpoint = f"https://arxiv.org/{path}"
        req_hash = request_hash(PROVIDER, endpoint, {"arxiv_id": aid, "path": path})
        started = datetime.now(timezone.utc)

        cached = find_cached(PROVIDER, req_hash)
        if cached is not None:
            try:
                payload = read_cached(cached)
            except Exception:  # noqa: BLE001
                payload = None
            else:
                if isinstance(payload, dict) and "html" in payload:
                    emails, affiliations = _parse(payload["html"])
                elif isinstance(payload, dict):
                    emails = list(payload.get("emails") or [])
                    affiliations = list(payload.get("affiliations") or [])
                else:
                    emails, affiliations = [], []
                if conn is not None:
                    record_external_request(
                        conn,
                        run_id=run_id,
                        stage_run_id=stage_run_id,
                        content_item_id=content_item_id,
                        provider=PROVIDER,
                        endpoint=endpoint,
                        request_hash=req_hash,
                        started_at=started,
                        http_status=200,
                        success=True,
                        cache_hit=True,
                        response_path=str(cached),
                    )
                return ArxivAffiliationPage(
                    arxiv_id=aid,
                    emails=emails,
                    affiliations=affiliations,
                    evidence_url=endpoint,
                    raw_ref=str(cached),
                )

        payload = None
        status = None
        error = None
        for attempt in range(1, MAX_RETRIES + 1):
            try:
                _throttle()
                response = requests.get(
                    endpoint,
                    timeout=TIMEOUT,
                    headers={"User-Agent": "paper-intelligence/1.0 (affiliation)"},
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
                    error = f"HTTP {status}"
                    break
                payload = {
                    "html": response.text,
                    "url": endpoint,
                    "arxiv_id": aid,
                }
                error = None
                break
            except Exception as exc:  # noqa: BLE001
                error = str(exc)
                if attempt < MAX_RETRIES:
                    time.sleep(min(20.0, 2 ** (attempt - 1)))
                    continue

        response_path = response_sha = None
        if payload is not None:
            response_path, response_sha = write_raw(PROVIDER, req_hash, aid, payload)

        if conn is not None:
            record_external_request(
                conn,
                run_id=run_id,
                stage_run_id=stage_run_id,
                content_item_id=content_item_id,
                provider=PROVIDER,
                endpoint=endpoint,
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

        if error is None and payload is not None:
            emails, affiliations = _parse(payload["html"])
            return ArxivAffiliationPage(
                arxiv_id=aid,
                emails=emails,
                affiliations=affiliations,
                evidence_url=endpoint,
                raw_ref=response_path,
            )
        last_error = error
        if error != "not_found":
            break

    return ArxivAffiliationPage(arxiv_id=aid, error=last_error or "fetch_failed")
