"""arXiv OAI-PMH ingest for PaperIntelligence.

When ``PI_USE_PAPERS_CATALOG=1``, writes ``paper_intelligence.papers`` first
and uses PI ingest checkpoints. Radar dual-write is best-effort when
``PI_WRITE_RADAR_COMPAT=1`` and must not roll back PI success.

When catalog mode is off, preserves the legacy Radar-first path.

Does not run relevance, screen, affiliation, or any LLM stage.

`published_at` is the arXiv v1 submission date, taken from the ``arXivRaw``
version history. OAI ``<created>`` in the ``arXiv`` format is the latest
version's date and ``<datestamp>`` is last-modified, so neither is used.
A window harvest covers datestamps from the window start through today
(datestamp >= v1 date always) and keeps only records whose v1 date falls
inside the window.
"""

from __future__ import annotations

import logging
import time
import xml.etree.ElementTree as ET
from dataclasses import dataclass, field
from datetime import date, datetime, timezone
from email.utils import parsedate_to_datetime
from os import getenv
from typing import Any, Iterator

import requests

from paper_intelligence.common.config import PI_USE_PAPERS_CATALOG, PI_WRITE_RADAR_COMPAT
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
SOURCE = "arxiv_oai"
# Checkpoints written before the v1 fix were datestamp windows; a separate
# key keeps them from suppressing v1-window harvests.
CHECKPOINT_SOURCE = "arxiv_oai_v1"

BACKFILL_CATEGORIES = getenv(
    "ARXIV_BACKFILL_CATEGORIES",
    "cs,cs.AI,cs.CL,cs.CV,cs.LG,cs.NE,stat.ML",
).split(",")

OAI_NS = {
    "oai": "http://www.openarchives.org/OAI/2.0/",
    "arxiv": "http://arxiv.org/OAI/arXiv/",
    "raw": "http://arxiv.org/OAI/arXivRaw/",
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
    """``arXiv``-format records whose OAI *datestamp* is in the range."""
    params = {
        "verb": "ListRecords",
        "set": set_spec,
        "metadataPrefix": "arXiv",
        "from": window_from.isoformat(),
        "until": window_until.isoformat(),
    }
    for record_elem in _iter_list_records(params):
        yield parse_record(record_elem)


def parse_version_date(text: str | None) -> datetime | None:
    """arXivRaw version dates are RFC 2822, e.g. ``Wed, 25 Dec 2024 05:19:52 GMT``."""
    if not text:
        return None
    try:
        dt = parsedate_to_datetime(text.strip())
    except (TypeError, ValueError):
        return None
    return dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)


def parse_raw_record(record_elem: ET.Element) -> dict[str, Any]:
    """Parse an ``arXivRaw`` record into its per-version history."""
    header = record_elem.find("oai:header", OAI_NS)
    identifier = _text(header, "oai:identifier")
    datestamp = _text(header, "oai:datestamp")
    raw_elem = record_elem.find("oai:metadata/raw:arXivRaw", OAI_NS)
    if (header is not None and header.get("status") == "deleted") or raw_elem is None:
        return {"identifier": identifier, "datestamp": datestamp, "deleted": True}
    versions: dict[int, datetime] = {}
    for ver in raw_elem.findall("raw:version", OAI_NS):
        label = (ver.get("version") or "").lstrip("v")
        dt = parse_version_date(_text(ver, "raw:date"))
        if label.isdigit() and dt is not None:
            versions[int(label)] = dt
    categories_text = _text(raw_elem, "raw:categories") or ""
    return {
        "identifier": identifier,
        "datestamp": datestamp,
        "deleted": False,
        "arxiv_id": _text(raw_elem, "raw:id"),
        "categories": categories_text.split(),
        "versions": versions,
        "v1_date": versions.get(1),
    }


def fetch_v1_dates(
    set_spec: str, harvest_from: date, harvest_until: date
) -> dict[str, dict[str, Any]]:
    """Map arxiv_id -> {v1_date, categories} for datestamps in the range."""
    params = {
        "verb": "ListRecords",
        "set": set_spec,
        "metadataPrefix": "arXivRaw",
        "from": harvest_from.isoformat(),
        "until": harvest_until.isoformat(),
    }
    out: dict[str, dict[str, Any]] = {}
    for record_elem in _iter_list_records(params):
        rec = parse_raw_record(record_elem)
        if rec["deleted"] or not rec.get("arxiv_id") or rec["v1_date"] is None:
            continue
        out[rec["arxiv_id"]] = {
            "v1_date": rec["v1_date"],
            "categories": rec["categories"],
        }
    return out


def get_v1_date(arxiv_id: str) -> datetime | None:
    """Single-record arXivRaw lookup (GetRecord)."""
    xml_text = _fetch_page(
        {
            "verb": "GetRecord",
            "identifier": f"oai:arXiv.org:{arxiv_id}",
            "metadataPrefix": "arXivRaw",
        }
    )
    root = ET.fromstring(xml_text)
    if root.find("oai:error", OAI_NS) is not None:
        return None
    record_elem = root.find("oai:GetRecord/oai:record", OAI_NS)
    if record_elem is None:
        return None
    return parse_raw_record(record_elem).get("v1_date")


def v1_in_window(v1_date: datetime | None, window_from: date, window_until: date) -> bool:
    if v1_date is None:
        return False
    return window_from <= v1_date.astimezone(timezone.utc).date() <= window_until


def _iter_list_records(params: dict[str, str]) -> Iterator[ET.Element]:
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
        yield from list_records.findall("oai:record", OAI_NS)

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
        "published_at": parse_iso_datetime(rec.get("v1_date")),
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
            "v1_date": rec.get("v1_date"),
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
    # Records harvested by datestamp whose v1 date is outside the window.
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


def _radar_compat_write(conn: Any, rec: dict[str, Any], paper_id: int) -> bool:
    """Best-effort Radar dual-write after PI success. Never raises to caller."""
    if not PI_WRITE_RADAR_COMPAT:
        return False
    try:
        from paper_intelligence.catalog.ingest import link_legacy_content_item

        item = record_to_item(rec)
        content_id, _ = upsert_item(conn, item)
        upsert_paper_metadata(conn, content_id, rec)
        link_legacy_content_item(conn, paper_id, content_id)
        return True
    except Exception:  # noqa: BLE001
        log.exception(
            "Radar compat ingest write failed after PI success paper_id=%s arxiv=%s",
            paper_id,
            rec.get("arxiv_id"),
        )
        return False


def _today_utc() -> date:
    return datetime.now(timezone.utc).date()


def iter_v1_window_records(
    set_spec: str,
    window_from: date,
    window_until: date,
    stats: "WindowStats",
    *,
    harvest_until: date | None = None,
) -> Iterator[dict[str, Any]]:
    """Yield category-matching records whose arXiv v1 date is in the window.

    Harvests datestamps ``window_from .. harvest_until`` (default today) so
    that a paper first submitted in the window is found even if it was
    revised later. Records with v1 outside the window are counted in
    ``stats.records_revision`` and not yielded.
    """
    harvest_until = harvest_until or _today_utc()
    v1_map = fetch_v1_dates(set_spec, window_from, harvest_until)
    for rec in fetch_window_records(set_spec, window_from, harvest_until):
        stats.records_seen += 1
        if rec["deleted"] or not rec.get("arxiv_id"):
            stats.records_deleted += 1
            continue
        if not category_matches(rec["categories"]):
            continue
        entry = v1_map.get(rec["arxiv_id"])
        v1_date = entry["v1_date"] if entry else get_v1_date(rec["arxiv_id"])
        if not v1_in_window(v1_date, window_from, window_until):
            stats.records_revision += 1
            continue
        stats.records_kept += 1
        rec["v1_date"] = v1_date
        rec["_set_spec"] = set_spec
        yield rec


def _run_one_window_radar(
    conn: Any, set_spec: str, window_from: date, window_until: date
) -> WindowStats:
    """DEPRECATED: legacy Radar-first ingest (compatibility-only).

    Not used when ``PI_USE_PAPERS_CATALOG=1``. Must not be treated as a
    production rollback after final cutover — Radar may be stale.
    """
    stats = WindowStats()
    for rec in iter_v1_window_records(set_spec, window_from, window_until, stats):
        item = record_to_item(rec)
        content_id, is_new = upsert_item(conn, item)
        if is_new:
            stats.records_new += 1
        else:
            stats.records_dupe += 1
        upsert_paper_metadata(conn, content_id, rec)
    return stats


def _run_one_window_pi(
    conn: Any, set_spec: str, window_from: date, window_until: date
) -> WindowStats:
    """PI-first ingest: papers table is authoritative."""
    from paper_intelligence.catalog.ingest import upsert_paper_from_oai

    stats = WindowStats()
    compat_failures = 0
    for rec in iter_v1_window_records(set_spec, window_from, window_until, stats):
        paper_id, is_new = upsert_paper_from_oai(conn, rec, set_spec=set_spec)
        if is_new:
            stats.records_new += 1
        else:
            stats.records_dupe += 1
        # Commit PI row before optional Radar write so a Radar failure cannot
        # roll back the catalog paper.
        conn.commit()
        if not _radar_compat_write(conn, rec, paper_id):
            if PI_WRITE_RADAR_COMPAT:
                compat_failures += 1
                try:
                    conn.rollback()
                except Exception:  # noqa: BLE001
                    pass
        else:
            try:
                conn.commit()
            except Exception:  # noqa: BLE001
                log.exception(
                    "Radar compat commit failed paper_id=%s; PI paper retained",
                    paper_id,
                )
                try:
                    conn.rollback()
                except Exception:  # noqa: BLE001
                    pass
    if compat_failures:
        log.warning(
            "ingest PI window set=%s %s..%s radar_compat_failures=%d",
            set_spec,
            window_from,
            window_until,
            compat_failures,
        )
    return stats


def _run_one_window(
    conn: Any, set_spec: str, window_from: date, window_until: date
) -> WindowStats:
    if PI_USE_PAPERS_CATALOG:
        return _run_one_window_pi(conn, set_spec, window_from, window_until)
    return _run_one_window_radar(conn, set_spec, window_from, window_until)


def run_ingest(
    conn: Any, date_from: date, date_until: date, *, force: bool = False
) -> IngestTotals:
    from paper_intelligence.catalog.ingest import (
        checkpoint_status_pi,
        finish_checkpoint_pi,
        start_checkpoint_pi,
    )

    totals = IngestTotals()
    use_pi = PI_USE_PAPERS_CATALOG
    # One harvest per set covers the whole v1 range: each harvest already
    # reads datestamps through today, so chunking would re-read the tail.
    window_from, window_until = date_from, date_until
    for set_spec in OAI_SETS:
        if use_pi:
            done = checkpoint_status_pi(
                conn, CHECKPOINT_SOURCE, set_spec, window_from, window_until
            )
        else:
            done = checkpoint_status(
                conn, CHECKPOINT_SOURCE, set_spec, window_from, window_until
            )
        if not force and done == "COMPLETE":
            log.info(
                "ingest set=%s window=%s..%s SKIP (checkpoint COMPLETE)",
                set_spec,
                window_from,
                window_until,
            )
            totals.windows_skipped += 1
            continue

        pi_ckpt_id: int | None = None
        if use_pi:
            pi_ckpt_id = start_checkpoint_pi(
                conn, CHECKPOINT_SOURCE, set_spec, window_from, window_until
            )
            # Optional Radar checkpoint mirror (does not control resume).
            if PI_WRITE_RADAR_COMPAT:
                try:
                    start_checkpoint(
                        conn, CHECKPOINT_SOURCE, set_spec, window_from, window_until
                    )
                except Exception:  # noqa: BLE001
                    log.exception("Radar compat start_checkpoint failed")
        else:
            start_checkpoint(conn, CHECKPOINT_SOURCE, set_spec, window_from, window_until)
        conn.commit()
        started = time.monotonic()
        try:
            stats = _run_one_window(conn, set_spec, window_from, window_until)
            if use_pi and pi_ckpt_id is not None:
                finish_checkpoint_pi(
                    conn,
                    pi_ckpt_id,
                    status="COMPLETE",
                    records_seen=stats.records_seen,
                    records_kept=stats.records_kept,
                    records_new=stats.records_new,
                    records_dupe=stats.records_dupe,
                )
                if PI_WRITE_RADAR_COMPAT:
                    try:
                        finish_checkpoint(
                            conn,
                            CHECKPOINT_SOURCE,
                            set_spec,
                            window_from,
                            window_until,
                            status="COMPLETE",
                            stats=stats,
                        )
                    except Exception:  # noqa: BLE001
                        log.exception("Radar compat finish_checkpoint failed")
            else:
                finish_checkpoint(
                    conn,
                    CHECKPOINT_SOURCE,
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
                "ingest set=%s window=%s..%s seen=%d kept=%d new=%d dupe=%d elapsed=%ds catalog=%s",
                set_spec,
                window_from,
                window_until,
                stats.records_seen,
                stats.records_kept,
                stats.records_new,
                stats.records_dupe,
                int(time.monotonic() - started),
                use_pi,
            )
        except Exception as exc:  # noqa: BLE001 — window isolation
            conn.rollback()
            if use_pi and pi_ckpt_id is not None:
                try:
                    finish_checkpoint_pi(
                        conn,
                        pi_ckpt_id,
                        status="FAILED",
                        error=str(exc)[:2000],
                    )
                    conn.commit()
                except Exception:  # noqa: BLE001
                    log.exception("PI finish_checkpoint FAILED write failed")
            else:
                finish_checkpoint(
                    conn,
                    CHECKPOINT_SOURCE,
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


def count_v1_window(
    date_from: date, date_until: date, *, harvest_until: date | None = None
) -> dict[str, Any]:
    """Live arXivRaw count of category-matching papers with v1 in the window.

    Harvests datestamps ``date_from .. harvest_until`` (default today); zero
    DB writes. ``arxiv_ids`` is the union across sets.
    """
    harvest_until = harvest_until or _today_utc()
    per_set: dict[str, Any] = {}
    kept_ids: set[str] = set()
    v1_by_id: dict[str, str] = {}
    requests_total = 0
    for set_spec in OAI_SETS:
        requests_before = _request_count
        v1_map = fetch_v1_dates(set_spec, date_from, harvest_until)
        in_window = {
            arxiv_id
            for arxiv_id, entry in v1_map.items()
            if category_matches(entry["categories"])
            and v1_in_window(entry["v1_date"], date_from, date_until)
        }
        requests_this_set = _request_count - requests_before
        requests_total += requests_this_set
        per_set[set_spec] = {
            "records_harvested": len(v1_map),
            "v1_in_window": len(in_window),
            "oai_requests": requests_this_set,
        }
        kept_ids |= in_window
        for arxiv_id in in_window:
            v1_by_id[arxiv_id] = v1_map[arxiv_id]["v1_date"].astimezone(timezone.utc).date().isoformat()
    return {
        "date_from": str(date_from),
        "date_until": str(date_until),
        "harvest_until": str(harvest_until),
        "per_set": per_set,
        "v1_in_window_unique": len(kept_ids),
        "oai_requests": requests_total,
        "arxiv_ids": sorted(kept_ids),
        "v1_by_id": v1_by_id,
    }


def dry_run_projection(date_from: date, date_until: date) -> dict[str, Any]:
    counts = count_v1_window(date_from, date_until)
    # A real run also fetches the arXiv-format pages over the same range.
    projected_requests = counts["oai_requests"] * 2
    return {
        **{k: v for k, v in counts.items() if k not in {"arxiv_ids", "v1_by_id"}},
        "projected_oai_requests": projected_requests,
        "wall_clock_minutes": round(projected_requests * OAI_DELAY_SECONDS / 60, 1),
    }


def print_dry_run(projection: dict[str, Any]) -> None:
    print("\nINGEST DRY RUN (live arXivRaw harvest, zero DB writes)")
    print(
        f"  v1 window {projection['date_from']}..{projection['date_until']} "
        f"harvesting datestamps through {projection['harvest_until']}"
    )
    for set_spec, stats in projection["per_set"].items():
        print(
            f"  set={set_spec} harvested={stats['records_harvested']} "
            f"v1_in_window={stats['v1_in_window']} requests={stats['oai_requests']}"
        )
    print(f"  v1-in-window unique papers: {projection['v1_in_window_unique']:,}")
    print(
        f"  full run ~{projection['projected_oai_requests']} OAI requests, "
        f"~{projection['wall_clock_minutes']} min at {OAI_DELAY_SECONDS}s/req"
    )


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
