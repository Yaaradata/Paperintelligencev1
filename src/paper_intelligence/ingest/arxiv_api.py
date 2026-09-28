"""arXiv API harvester by v1 submission date.

Queries ``search_query=cat:<C> AND submittedDate:[YYYYMMDD0000 TO YYYYMMDD2359]``
per category, paginated with ``start``/``max_results``, one request per
``ARXIV_API_DELAY`` seconds (arXiv asks for >= 3 s). The Atom ``<published>``
field is the v1 submission time and becomes ``published_at``; entries whose
``<published>`` falls outside the window are dropped defensively.

Records are mapped to the same dict shape as the OAI parser and written with
``upsert_paper_from_oai``. A status JSON is written every
``STATUS_EVERY`` papers.
"""

from __future__ import annotations

import json
import logging
import re
import time
import xml.etree.ElementTree as ET
from dataclasses import asdict, dataclass, field
from datetime import date, datetime, timezone
from os import getenv
from pathlib import Path
from typing import Any, Callable, Iterator

import requests

from paper_intelligence.ingest.arxiv_oai import v1_in_window

log = logging.getLogger("paper_intelligence.ingest.arxiv_api")

API_BASE = getenv("ARXIV_API_BASE", "https://export.arxiv.org/api/query")
API_DELAY_SECONDS = max(3.0, float(getenv("ARXIV_API_DELAY", "3")))
API_PAGE_SIZE = int(getenv("ARXIV_API_PAGE_SIZE", "200"))
API_TIMEOUT_SECONDS = int(getenv("ARXIV_API_TIMEOUT_SECONDS", "60"))
API_MAX_RETRIES = 3
STATUS_EVERY = 100
SOURCE_TAG = "arxiv_api"

CS_CATEGORIES = (
    "cs.AI cs.AR cs.CC cs.CE cs.CG cs.CL cs.CR cs.CV cs.CY cs.DB cs.DC cs.DL "
    "cs.DM cs.DS cs.ET cs.FL cs.GL cs.GR cs.GT cs.HC cs.IR cs.IT cs.LG cs.LO "
    "cs.MA cs.MM cs.MS cs.NA cs.NE cs.NI cs.OH cs.OS cs.PF cs.PL cs.RO cs.SC "
    "cs.SD cs.SE cs.SI cs.SY"
).split()
API_CATEGORIES = [
    c for c in getenv("ARXIV_API_CATEGORIES", " ".join(CS_CATEGORIES + ["stat.ML"]))
    .replace(",", " ").split() if c
]

NS = {
    "atom": "http://www.w3.org/2005/Atom",
    "arxiv": "http://arxiv.org/schemas/atom",
    "opensearch": "http://a9.com/-/spec/opensearch/1.1/",
}

SESSION = requests.Session()
SESSION.headers.update(
    {"User-Agent": getenv("HTTP_USER_AGENT", "PaperIntelligence/0.1 (arxiv-api)")}
)

_last_request_at = 0.0


class ArxivAPIError(RuntimeError):
    pass


def _throttle() -> None:
    global _last_request_at
    wait = _last_request_at + API_DELAY_SECONDS - time.monotonic()
    if wait > 0:
        time.sleep(wait)
    _last_request_at = time.monotonic()


def _fetch(params: dict[str, Any]) -> str:
    last_exc: Exception | None = None
    for _ in range(API_MAX_RETRIES):
        _throttle()
        try:
            resp = SESSION.get(API_BASE, params=params, timeout=API_TIMEOUT_SECONDS)
        except requests.RequestException as exc:
            last_exc = exc
            continue
        if resp.status_code in (429, 500, 502, 503):
            last_exc = ArxivAPIError(f"HTTP {resp.status_code}")
            time.sleep(API_DELAY_SECONDS * 3)
            continue
        if resp.status_code != 200:
            raise ArxivAPIError(f"HTTP {resp.status_code}: {resp.text[:500]}")
        return resp.text
    raise ArxivAPIError(f"arXiv API failed after {API_MAX_RETRIES} attempts: {last_exc}")


def submitted_date_query(category: str, date_from: date, date_until: date) -> str:
    return (
        f"cat:{category} AND submittedDate:"
        f"[{date_from:%Y%m%d}0000 TO {date_until:%Y%m%d}2359]"
    )


def _text(elem: ET.Element, path: str) -> str | None:
    node = elem.find(path, NS)
    return " ".join(node.text.split()) if node is not None and node.text else None


def _parse_ts(text: str | None) -> datetime | None:
    if not text:
        return None
    return datetime.fromisoformat(text.replace("Z", "+00:00")).astimezone(timezone.utc)


def parse_entry(entry: ET.Element) -> dict[str, Any]:
    abs_url = _text(entry, "atom:id") or ""
    arxiv_id = re.sub(r"v\d+$", "", abs_url.rsplit("/abs/", 1)[-1])
    authors: list[str] = []
    authors_structured: list[dict[str, Any]] = []
    for pos, author in enumerate(entry.findall("atom:author", NS), 1):
        name = _text(author, "atom:name") or ""
        if not name:
            continue
        affiliations = [
            " ".join(a.text.split())
            for a in author.findall("arxiv:affiliation", NS)
            if a.text and a.text.strip()
        ]
        authors.append(name)
        authors_structured.append(
            {
                "position": pos,
                "name": name,
                "keyname": None,
                "forenames": None,
                "affiliation": affiliations[0] if len(affiliations) == 1 else (
                    affiliations or None
                ),
                "affiliations": affiliations,
            }
        )
    categories = [c.get("term") for c in entry.findall("atom:category", NS) if c.get("term")]
    published = _parse_ts(_text(entry, "atom:published"))
    updated = _parse_ts(_text(entry, "atom:updated"))
    return {
        "identifier": f"oai:arXiv.org:{arxiv_id}",
        "datestamp": None,
        "deleted": False,
        "arxiv_id": arxiv_id,
        "created": None,
        "updated": updated.isoformat() if updated else None,
        "v1_date": published,
        "title": _text(entry, "atom:title") or "",
        "abstract": _text(entry, "atom:summary") or "",
        "categories": categories,
        "doi": _text(entry, "arxiv:doi"),
        "journal_ref": _text(entry, "arxiv:journal_ref"),
        "authors": authors,
        "authors_structured": authors_structured,
        "_source": SOURCE_TAG,
    }


def parse_feed(xml_text: str) -> tuple[int, list[dict[str, Any]]]:
    root = ET.fromstring(xml_text)
    total_text = _text(root, "opensearch:totalResults")
    total = int(total_text) if total_text and total_text.isdigit() else 0
    return total, [parse_entry(e) for e in root.findall("atom:entry", NS)]


def iter_category(
    category: str,
    date_from: date,
    date_until: date,
    *,
    fetch: Callable[[dict[str, Any]], str] = _fetch,
    page_size: int = API_PAGE_SIZE,
) -> Iterator[dict[str, Any]]:
    """Yield entries for one category whose v1 date is inside the window."""
    query = submitted_date_query(category, date_from, date_until)
    start = 0
    while True:
        total, entries = parse_feed(
            fetch(
                {
                    "search_query": query,
                    "start": start,
                    "max_results": page_size,
                    "sortBy": "submittedDate",
                    "sortOrder": "ascending",
                }
            )
        )
        for rec in entries:
            if v1_in_window(rec["v1_date"], date_from, date_until):
                yield rec
        start += len(entries)
        if not entries or start >= total:
            return


def count_category(
    category: str,
    date_from: date,
    date_until: date,
    *,
    fetch: Callable[[dict[str, Any]], str] = _fetch,
) -> int:
    total, _ = parse_feed(
        fetch(
            {
                "search_query": submitted_date_query(category, date_from, date_until),
                "start": 0,
                "max_results": 1,
            }
        )
    )
    return total


@dataclass
class ApiHarvestStats:
    run_id: str | None = None
    date_from: str = ""
    date_until: str = ""
    category: str | None = None
    categories_done: list[str] = field(default_factory=list)
    entries_seen: int = 0
    unique_papers: int = 0
    records_new: int = 0
    records_dupe: int = 0
    status: str = "running"
    error: str | None = None
    updated_at: str | None = None


def _write_status(path: Path, stats: ApiHarvestStats) -> None:
    stats.updated_at = datetime.now(timezone.utc).isoformat()
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(".tmp")
    tmp.write_text(json.dumps(asdict(stats), indent=2))
    tmp.replace(path)


def default_status_path(date_from: date, date_until: date) -> Path:
    return Path("reports/ingest_status") / f"arxiv_api_{date_from}_{date_until}.json"


def harvest_window(
    conn: Any,
    date_from: date,
    date_until: date,
    *,
    run_id: str | None = None,
    categories: list[str] | None = None,
    status_path: Path | None = None,
    fetch: Callable[[dict[str, Any]], str] = _fetch,
    upsert: Callable[..., tuple[int, bool]] | None = None,
) -> ApiHarvestStats:
    """Harvest every category and upsert unique papers (v1 in window only)."""
    if upsert is None:
        from paper_intelligence.catalog.ingest import upsert_paper_from_oai as upsert
    status_path = status_path or default_status_path(date_from, date_until)
    stats = ApiHarvestStats(
        run_id=run_id, date_from=str(date_from), date_until=str(date_until)
    )
    seen_ids: set[str] = set()
    _write_status(status_path, stats)
    try:
        for category in categories or API_CATEGORIES:
            stats.category = category
            for rec in iter_category(category, date_from, date_until, fetch=fetch):
                stats.entries_seen += 1
                if rec["arxiv_id"] in seen_ids:
                    continue
                seen_ids.add(rec["arxiv_id"])
                _, is_new = upsert(conn, rec, set_spec=category.split(".", 1)[0])
                conn.commit()
                stats.unique_papers += 1
                if is_new:
                    stats.records_new += 1
                else:
                    stats.records_dupe += 1
                if stats.unique_papers % STATUS_EVERY == 0:
                    _write_status(status_path, stats)
            stats.categories_done.append(category)
            _write_status(status_path, stats)
        stats.status = "succeeded"
    except Exception as exc:
        stats.status = "failed"
        stats.error = str(exc)[:2000]
        raise
    finally:
        _write_status(status_path, stats)
    return stats


def run_window(
    date_from: str | date,
    date_until: str | date,
    *,
    conn: Any | None = None,
    dry_run: bool = False,
    force: bool = False,  # noqa: ARG001 — signature parity with OAI run_window
) -> dict[str, Any]:
    """API counterpart of ``arxiv_oai.run_window``.

    Standalone calls (no ``conn``) write their own pipeline run record before
    the first API request.
    """
    from paper_intelligence.db import connect
    from paper_intelligence.observability import finish_pipeline_run, start_pipeline_run

    if isinstance(date_from, str):
        date_from = date.fromisoformat(date_from[:10])
    if isinstance(date_until, str):
        date_until = date.fromisoformat(date_until[:10])
    if date_from > date_until:
        raise ValueError(f"--from ({date_from}) must be <= --until ({date_until})")

    if dry_run:
        per_cat = {c: count_category(c, date_from, date_until) for c in API_CATEGORIES}
        return {
            "dry_run": True,
            "source": SOURCE_TAG,
            "per_category_total": per_cat,
            "entries_total_with_crosslists": sum(per_cat.values()),
        }

    owns = conn is None
    conn = conn or connect()
    run_id = None
    try:
        if owns:
            run_id = start_pipeline_run(
                conn,
                pipeline_name="paper_intelligence.ingest_arxiv_api",
                metadata={"date_from": str(date_from), "date_until": str(date_until)},
            )
            conn.commit()
        status_path = default_status_path(date_from, date_until)
        print(f"arxiv_api run_id={run_id} status={status_path}")
        try:
            stats = harvest_window(
                conn, date_from, date_until, run_id=run_id, status_path=status_path
            )
        except Exception:
            if run_id:
                conn.rollback()
                finish_pipeline_run(conn, run_id, status="failed")
                conn.commit()
            raise
        summary = {
            "source": SOURCE_TAG,
            "status_file": str(status_path),
            "records_seen": stats.entries_seen,
            "records_kept": stats.unique_papers,
            "records_new": stats.records_new,
            "records_dupe": stats.records_dupe,
        }
        if run_id:
            finish_pipeline_run(
                conn,
                run_id,
                status="succeeded",
                items_input=stats.entries_seen,
                items_succeeded=stats.records_new,
                items_skipped=stats.records_dupe,
                metadata=summary,
            )
            conn.commit()
        return summary
    finally:
        if owns:
            conn.close()
