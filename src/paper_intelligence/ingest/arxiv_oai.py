"""arXiv OAI-PMH ingest for PaperIntelligence.

Port of Research Radar's arxiv_backfill harvester. Writes the same shared
tables (`research_radar.content_items` / `paper_metadata`). Does not remove
or replace Research Radar's copy — both may run against the same RDS.

Does not run relevance, screen, affiliation, or any LLM stage.
`published_at` always comes from OAI `<created>`, never `<datestamp>`.
"""

from __future__ import annotations

import logging
import time
import xml.etree.ElementTree as ET
from dataclasses import dataclass, field
from datetime import date, datetime, timedelta, timezone
from os import getenv
from typing import Any, Iterator

import requests

from paper_intelligence.ingest.repository import (
    normalize_url,
    parse_iso_datetime,
    upsert_item,
    upsert_paper_metadata,
)

log = logging.getLogger("paper_intelligence.ingest")

STAGE_NAME = "ingest"
STAGE_VERSION = "v001"

OAI_BASE = getenv("ARXIV_OAI_BASE", "https://oaipmh.arxiv.org/oai")
OAI_DELAY_SECONDS = float(getenv("ARXIV_OAI_DELAY", "5"))
OAI_SETS = ("cs", "stat")
OAI_TIMEOUT_SECONDS = int(getenv("ARXIV_OAI_TIMEOUT_SECONDS", "60"))
OAI_DEFAULT_RETRY_AFTER = float(getenv("ARXIV_OAI_DEFAULT_RETRY_AFTER", "20"))
WINDOW_DAYS = 7
SOURCE = "arxiv_oai"

BACKFILL_CATEGORIES = getenv(
    "ARXIV_BACKFILL_CATEGORIES",
    "cs,cs.AI,cs.CL,cs.CV,cs.LG,cs.NE,stat.ML",
).split(",")

OAI_NS = {
    "oai": "http://www.openarchives.org/OAI/2.0/",
    "arxiv": "http://arxiv.org/OAI/arXiv/",
}

SESSION = requests.Session()
SESSION.headers.update(
    {"User-Agent": getenv("HTTP_USER_AGENT", "PaperIntelligence/0.1 (oai-ingest)")}
)

_last_request_at = 0.0
_request_count = 0


class ArxivOAIError(RuntimeError):
    """Non-recoverable OAI-PMH error response."""


class IngestWindowFailed(RuntimeError):
    def __init__(self, failures: list):
        self.failures = failures
        super().__init__(f"{len(failures)} window(s) failed: {failures}")


def _throttle() -> None:
    global _last_request_at
    now = time.monotonic()
    wait = _last_request_at + OAI_DELAY_SECONDS - now
    if wait > 0:
        time.sleep(wait)
    _last_request_at = time.monotonic()


def _fetch_page(params: dict[str, str]) -> str:
    global _request_count
    while True:
        _throttle()
        _request_count += 1
        resp = SESSION.get(OAI_BASE, params=params, timeout=OAI_TIMEOUT_SECONDS)
        if resp.status_code == 503:
            retry_after = resp.headers.get("Retry-After", "")
            try:
                wait = float(retry_after.strip())
            except (TypeError, ValueError):
                wait = OAI_DEFAULT_RETRY_AFTER
            log.info("ingest 503 Retry-After=%ss; sleeping", wait)
            time.sleep(wait)
            continue
        resp.raise_for_status()
        return resp.text


def _text(elem: ET.Element | None, path: str) -> str | None:
    if elem is None:
        return None
    node = elem.find(path, OAI_NS)
    return node.text.strip() if node is not None and node.text else None


def category_matches(categories: list[str], allowed: list[str] | None = None) -> bool:
    allowed = allowed if allowed is not None else BACKFILL_CATEGORIES
    allowed_exact = set(allowed)
    allowed_bare = {a for a in allowed if "." not in a}
    for cat in categories or []:
        if cat in allowed_exact:
            return True
        if cat.split(".", 1)[0] in allowed_bare:
            return True
    return False


def _author_affiliations(author_elem: ET.Element) -> list[str]:
    """OAI may attach zero or more `<affiliation>` children per author."""
    found: list[str] = []
    for aff in author_elem.findall("arxiv:affiliation", OAI_NS):
        text = (aff.text or "").strip()
        if text:
            found.append(" ".join(text.split()))
    return found


def parse_record(record_elem: ET.Element) -> dict[str, Any]:
    header = record_elem.find("oai:header", OAI_NS)
    identifier = _text(header, "oai:identifier")
    datestamp = _text(header, "oai:datestamp")
    if header is not None and header.get("status") == "deleted":
        return {"identifier": identifier, "datestamp": datestamp, "deleted": True}

    arxiv_elem = record_elem.find("oai:metadata/arxiv:arXiv", OAI_NS)
    if arxiv_elem is None:
        return {"identifier": identifier, "datestamp": datestamp, "deleted": True}

    # Backward-compatible name list plus structured author→affiliation mapping.
    authors: list[str] = []
    authors_structured: list[dict[str, Any]] = []
    authors_elem = arxiv_elem.find("arxiv:authors", OAI_NS)
    if authors_elem is not None:
        position = 0
        for author in authors_elem.findall("arxiv:author", OAI_NS):
            keyname = _text(author, "arxiv:keyname") or ""
            forenames = _text(author, "arxiv:forenames") or ""
            name = " ".join(part for part in (forenames, keyname) if part)
            if not name:
                continue
            position += 1
            affiliations = _author_affiliations(author)
            authors.append(name)
            authors_structured.append(
                {
                    "position": position,
                    "name": name,
                    "keyname": keyname or None,
                    "forenames": forenames or None,
                    # Single string when one affiliation; list when several.
                    "affiliation": affiliations[0] if len(affiliations) == 1 else (
                        affiliations or None
                    ),
                    "affiliations": affiliations,
                }
            )

    categories_text = _text(arxiv_elem, "arxiv:categories") or ""
    return {
        "identifier": identifier,
        "datestamp": datestamp,
        "deleted": False,
        "arxiv_id": _text(arxiv_elem, "arxiv:id"),
        "created": _text(arxiv_elem, "arxiv:created"),
        "updated": _text(arxiv_elem, "arxiv:updated"),
        "title": " ".join((_text(arxiv_elem, "arxiv:title") or "").split()),
        "abstract": " ".join((_text(arxiv_elem, "arxiv:abstract") or "").split()),
        "categories": categories_text.split(),
        "doi": _text(arxiv_elem, "arxiv:doi"),
        "journal_ref": _text(arxiv_elem, "arxiv:journal-ref"),
        "authors": authors,
        "authors_structured": authors_structured,
    }


def fetch_window_records(
    set_spec: str, window_from: date, window_until: date
) -> Iterator[dict[str, Any]]:
    params = {
        "verb": "ListRecords",
        "set": set_spec,
        "metadataPrefix": "arXiv",
        "from": window_from.isoformat(),
        "until": window_until.isoformat(),
    }
    while True:
        xml_text = _fetch_page(params)
        root = ET.fromstring(xml_text)
        error = root.find("oai:error", OAI_NS)
        if error is not None:
            code = error.get("code")
            if code == "noRecordsMatch":
                return
            raise ArxivOAIError(f"OAI error code={code} message={error.text}")

        list_records = root.find("oai:ListRecords", OAI_NS)
        if list_records is None:
            return
        for record_elem in list_records.findall("oai:record", OAI_NS):
            yield parse_record(record_elem)

        token_elem = list_records.find("oai:resumptionToken", OAI_NS)
        token = (
            token_elem.text.strip()
            if token_elem is not None and token_elem.text
            else None
        )
        if not token:
            return
        params = {"verb": "ListRecords", "resumptionToken": token}


def record_to_item(rec: dict[str, Any]) -> dict[str, Any]:
    arxiv_id = rec["arxiv_id"]
    authors_structured = rec.get("authors_structured") or []
    return {
        "source": SOURCE,
        "source_external_id": rec["identifier"],
        "source_type": "arxiv",
        "canonical_url": normalize_url(f"https://arxiv.org/abs/{arxiv_id}"),
        "title": rec["title"] or "(untitled)",
        "summary": rec["abstract"],
        "published_at": parse_iso_datetime(rec["created"]),
        "source_seen_at": datetime.now(timezone.utc),
        "updated_at": parse_iso_datetime(rec["updated"]) if rec.get("updated") else None,
        "authors_raw": rec["authors"],
        "categories_raw": rec["categories"],
        "inoreader_tags": [],
        "raw_metadata": {
            "oai_identifier": rec["identifier"],
            "datestamp": rec["datestamp"],
            "created": rec["created"],
            "updated": rec["updated"],
            "categories": rec["categories"],
            "authors": rec["authors"],
            "authors_structured": authors_structured,
            "doi": rec["doi"],
            "journal_ref": rec["journal_ref"],
            "title": rec["title"],
            "abstract": rec["abstract"],
            "ingested_by": "paper_intelligence.ingest",
        },
    }


def _iter_windows(date_from: date, date_until: date):
    cur = date_from
    while cur <= date_until:
        end = min(cur + timedelta(days=WINDOW_DAYS - 1), date_until)
        yield cur, end
        cur = end + timedelta(days=1)


def _created_year(created_str: str | None) -> int | None:
    dt = parse_iso_datetime(created_str) if created_str else None
    return dt.year if dt else None


def checkpoint_status(
    conn: Any, source: str, set_spec: str, window_from: date, window_until: date
) -> str | None:
    row = conn.execute(
        """
        SELECT status FROM research_radar.backfill_checkpoints
        WHERE source=%s AND set_spec=%s AND window_from=%s AND window_until=%s
        """,
        (source, set_spec, window_from, window_until),
    ).fetchone()
    return row["status"] if row else None


def start_checkpoint(
    conn: Any, source: str, set_spec: str, window_from: date, window_until: date
) -> None:
    conn.execute(
        """
        INSERT INTO research_radar.backfill_checkpoints
            (source, set_spec, window_from, window_until, status, started_at)
        VALUES (%s, %s, %s, %s, 'RUNNING', NOW())
        ON CONFLICT (source, set_spec, window_from, window_until) DO UPDATE SET
            status = 'RUNNING', started_at = NOW(), ended_at = NULL, error = NULL,
            records_seen = 0, records_kept = 0, records_new = 0, records_dupe = 0
        """,
        (source, set_spec, window_from, window_until),
    )


def finish_checkpoint(
    conn: Any,
    source: str,
    set_spec: str,
    window_from: date,
    window_until: date,
    *,
    status: str,
    stats: "WindowStats",
    error: str | None = None,
) -> None:
    conn.execute(
        """
        UPDATE research_radar.backfill_checkpoints
        SET status=%s, records_seen=%s, records_kept=%s, records_new=%s, records_dupe=%s,
            error=%s, ended_at=NOW()
        WHERE source=%s AND set_spec=%s AND window_from=%s AND window_until=%s
        """,
        (
            status,
            stats.records_seen,
            stats.records_kept,
            stats.records_new,
            stats.records_dupe,
            error,
            source,
            set_spec,
            window_from,
            window_until,
        ),
    )


@dataclass
class WindowStats:
    records_seen: int = 0
    records_kept: int = 0
    records_new: int = 0
    records_dupe: int = 0
    records_deleted: int = 0
    records_revision: int = 0


@dataclass
class IngestTotals:
    records_seen: int = 0
    records_kept: int = 0
    records_new: int = 0
    records_dupe: int = 0
    records_deleted: int = 0
    records_revision: int = 0
    windows_run: int = 0
    windows_skipped: int = 0
    windows_failed: int = 0
    failures: list = field(default_factory=list)

    def add(self, window: WindowStats) -> None:
        self.records_seen += window.records_seen
        self.records_kept += window.records_kept
        self.records_new += window.records_new
        self.records_dupe += window.records_dupe
        self.records_deleted += window.records_deleted
        self.records_revision += window.records_revision

    def as_dict(self) -> dict[str, Any]:
        return {
            "windows_run": self.windows_run,
            "windows_skipped": self.windows_skipped,
            "windows_failed": self.windows_failed,
            "records_seen": self.records_seen,
            "records_kept": self.records_kept,
            "records_new": self.records_new,
            "records_dupe": self.records_dupe,
            "records_deleted": self.records_deleted,
            "records_revision": self.records_revision,
            "failures": self.failures,
        }


def _run_one_window(
    conn: Any, set_spec: str, window_from: date, window_until: date
) -> WindowStats:
    stats = WindowStats()
    for rec in fetch_window_records(set_spec, window_from, window_until):
        stats.records_seen += 1
        if rec["deleted"] or not rec.get("arxiv_id"):
            stats.records_deleted += 1
            continue
        if not category_matches(rec["categories"]):
            continue
        stats.records_kept += 1

        created_year = _created_year(rec.get("created"))
        if created_year is not None and created_year < window_from.year:
            stats.records_revision += 1

        item = record_to_item(rec)
        content_id, is_new = upsert_item(conn, item)
        if is_new:
            stats.records_new += 1
        else:
            stats.records_dupe += 1
        rec["_set_spec"] = set_spec
        upsert_paper_metadata(conn, content_id, rec)
    return stats


def run_ingest(
    conn: Any, date_from: date, date_until: date, *, force: bool = False
) -> IngestTotals:
    totals = IngestTotals()
    for set_spec in OAI_SETS:
        for window_from, window_until in _iter_windows(date_from, date_until):
            if (
                not force
                and checkpoint_status(conn, SOURCE, set_spec, window_from, window_until)
                == "COMPLETE"
            ):
                log.info(
                    "ingest set=%s window=%s..%s SKIP (checkpoint COMPLETE)",
                    set_spec,
                    window_from,
                    window_until,
                )
                totals.windows_skipped += 1
                continue

            start_checkpoint(conn, SOURCE, set_spec, window_from, window_until)
            conn.commit()
            started = time.monotonic()
            try:
                stats = _run_one_window(conn, set_spec, window_from, window_until)
                finish_checkpoint(
                    conn,
                    SOURCE,
                    set_spec,
                    window_from,
                    window_until,
                    status="COMPLETE",
                    stats=stats,
                )
                conn.commit()
                totals.add(stats)
                totals.windows_run += 1
                log.info(
                    "ingest set=%s window=%s..%s seen=%d kept=%d new=%d dupe=%d elapsed=%ds",
                    set_spec,
                    window_from,
                    window_until,
                    stats.records_seen,
                    stats.records_kept,
                    stats.records_new,
                    stats.records_dupe,
                    int(time.monotonic() - started),
                )
            except Exception as exc:  # noqa: BLE001 — window isolation
                conn.rollback()
                finish_checkpoint(
                    conn,
                    SOURCE,
                    set_spec,
                    window_from,
                    window_until,
                    status="FAILED",
                    stats=WindowStats(),
                    error=str(exc)[:2000],
                )
                conn.commit()
                totals.windows_failed += 1
                totals.failures.append(
                    (set_spec, str(window_from), str(window_until), str(exc))
                )
                log.exception(
                    "ingest set=%s window=%s..%s FAILED",
                    set_spec,
                    window_from,
                    window_until,
                )
    return totals


def dry_run_projection(date_from: date, date_until: date) -> dict[str, Any]:
    windows = list(_iter_windows(date_from, date_until))
    total_windows = len(windows)
    first_from, first_until = windows[0]

    per_set: dict[str, Any] = {}
    kept_arxiv_ids: set[str] = set()
    seen_total = deleted_total = kept_total = revision_total = 0
    requests_total = 0

    for set_spec in OAI_SETS:
        seen = deleted = kept = revision = 0
        requests_before = _request_count
        for rec in fetch_window_records(set_spec, first_from, first_until):
            seen += 1
            if rec["deleted"] or not rec.get("arxiv_id"):
                deleted += 1
                continue
            if not category_matches(rec["categories"]):
                continue
            kept += 1
            kept_arxiv_ids.add(rec["arxiv_id"])
            created_year = _created_year(rec.get("created"))
            if created_year is not None and created_year < first_from.year:
                revision += 1
        requests_this_set = _request_count - requests_before
        requests_total += requests_this_set
        per_set[set_spec] = {
            "records_seen": seen,
            "records_deleted": deleted,
            "records_kept": kept,
            "records_revision": revision,
            "oai_requests": requests_this_set,
        }
        seen_total += seen
        deleted_total += deleted
        kept_total += kept
        revision_total += revision

    unique_kept = len(kept_arxiv_ids)
    revision_fraction = (revision_total / kept_total) if kept_total else 0.0
    projected_kept_unique = unique_kept * total_windows
    projected_revisions = round(projected_kept_unique * revision_fraction)
    projected_requests = requests_total * total_windows
    wall_clock_seconds = projected_requests * OAI_DELAY_SECONDS

    return {
        "first_window": {"from": str(first_from), "until": str(first_until)},
        "total_windows": total_windows,
        "per_set_first_window": per_set,
        "first_window_totals": {
            "records_seen": seen_total,
            "records_deleted": deleted_total,
            "records_kept_raw": kept_total,
            "records_kept_unique_across_sets": unique_kept,
            "records_revision": revision_total,
            "oai_requests": requests_total,
        },
        "projected_full_range": {
            "date_from": str(date_from),
            "date_until": str(date_until),
            "records_seen": seen_total * total_windows,
            "records_kept_unique_across_sets": projected_kept_unique,
            "estimated_genuinely_new": projected_kept_unique - projected_revisions,
            "estimated_revisions_of_older_papers": projected_revisions,
            "oai_requests": projected_requests,
            "wall_clock_seconds": wall_clock_seconds,
            "wall_clock_hours": round(wall_clock_seconds / 3600, 1),
        },
    }


def print_dry_run(projection: dict[str, Any]) -> None:
    print("\nINGEST DRY RUN (first window live fetch, zero DB writes)")
    fw = projection["first_window"]
    print(
        f"  first window: {fw['from']}..{fw['until']} "
        f"(1 of {projection['total_windows']} windows)"
    )
    for set_spec, stats in projection["per_set_first_window"].items():
        print(
            f"  set={set_spec} seen={stats['records_seen']} "
            f"kept={stats['records_kept']} requests={stats['oai_requests']}"
        )
    pr = projection["projected_full_range"]
    print(f"\n  PROJECTION {pr['date_from']}..{pr['date_until']}:")
    print(f"    kept unique ~{pr['records_kept_unique_across_sets']:,}")
    print(f"    OAI requests ~{pr['oai_requests']:,}")
    print(f"    wall-clock ~{pr['wall_clock_hours']:.1f}h at {OAI_DELAY_SECONDS}s/req")


def run_window(
    date_from: str | date,
    date_until: str | date,
    *,
    conn: Any | None = None,
    dry_run: bool = False,
    force: bool = False,
) -> dict[str, Any]:
    """Public entry used by scripts/run_stage.py and run_pipeline.py."""
    from paper_intelligence.db import connect

    if isinstance(date_from, str):
        date_from = date.fromisoformat(date_from[:10])
    if isinstance(date_until, str):
        date_until = date.fromisoformat(date_until[:10])
    if date_from > date_until:
        raise ValueError(f"--from ({date_from}) must be <= --until ({date_until})")

    if dry_run:
        projection = dry_run_projection(date_from, date_until)
        print_dry_run(projection)
        return {"dry_run": True, **projection}

    owns = conn is None
    conn = conn or connect()
    try:
        totals = run_ingest(conn, date_from, date_until, force=force)
        print("\nINGEST SUMMARY")
        print(
            f"  windows run={totals.windows_run} skipped={totals.windows_skipped} "
            f"failed={totals.windows_failed}"
        )
        print(
            f"  seen={totals.records_seen} kept={totals.records_kept} "
            f"new={totals.records_new} dupe={totals.records_dupe}"
        )
        if totals.windows_failed:
            raise IngestWindowFailed(totals.failures)
        return totals.as_dict()
    finally:
        if owns:
            conn.close()
