"""A paper belongs to a window by its arXiv v1 submission date, and only that."""

from __future__ import annotations

import json
import xml.etree.ElementTree as ET
from datetime import date, datetime, timezone

import pytest

from paper_intelligence.common.v1_floor import clamp_window
from paper_intelligence.ingest import arxiv_api, arxiv_oai

JULY = date(2026, 7, 1), date(2026, 7, 31)
SEP_EDITION = date(2026, 9, 1), date(2026, 9, 21)
SEP_LATE = date(2026, 9, 21), date(2026, 9, 23)


def _raw_record(arxiv_id: str, *version_dates: str) -> ET.Element:
    versions = "".join(
        f'<version version="v{i}"><date>{d}</date><size>1kb</size></version>'
        for i, d in enumerate(version_dates, 1)
    )
    xml = f"""<OAI-PMH xmlns="http://www.openarchives.org/OAI/2.0/"><ListRecords>
      <record><header><identifier>oai:arXiv.org:{arxiv_id}</identifier>
        <datestamp>2026-09-17</datestamp></header>
      <metadata><arXivRaw xmlns="http://arxiv.org/OAI/arXivRaw/">
        <id>{arxiv_id}</id>{versions}
        <title>T</title><categories>cs.LG</categories>
      </arXivRaw></metadata></record></ListRecords></OAI-PMH>"""
    return ET.fromstring(xml).find("oai:ListRecords/oai:record", arxiv_oai.OAI_NS)


def _oai_rec(arxiv_id: str, created: str) -> dict:
    """arXiv-format record: <created> is the latest version's date."""
    return {
        "identifier": f"oai:arXiv.org:{arxiv_id}",
        "datestamp": "2026-09-17",
        "deleted": False,
        "arxiv_id": arxiv_id,
        "created": created,
        "updated": None,
        "title": "T",
        "abstract": "A",
        "categories": ["cs.LG"],
        "doi": None,
        "journal_ref": None,
        "authors": ["A B"],
        "authors_structured": [],
    }


def _window_ids(monkeypatch, raw_records, oai_records, window, lookups=None):
    """Run the OAI window filter over fixture harvests (no network)."""
    v1_map = {}
    for elem in raw_records:
        rec = arxiv_oai.parse_raw_record(elem)
        v1_map[rec["arxiv_id"]] = {"v1_date": rec["v1_date"], "categories": rec["categories"]}
    harvested = {}
    monkeypatch.setattr(
        arxiv_oai,
        "fetch_v1_dates",
        lambda s, f, u: harvested.setdefault("v1", (f, u)) and v1_map,
    )
    monkeypatch.setattr(
        arxiv_oai,
        "fetch_window_records",
        lambda s, f, u: harvested.setdefault("records", (f, u)) and iter(
            [dict(r) for r in oai_records]
        ),
    )
    monkeypatch.setattr(arxiv_oai, "get_v1_date", lambda a: (lookups or {}).get(a))
    stats = arxiv_oai.WindowStats()
    kept = list(
        arxiv_oai.iter_v1_window_records(
            "cs", window[0], window[1], stats, harvest_until=date(2026, 9, 28)
        )
    )
    return kept, stats, harvested


def test_parse_raw_record_v1_is_first_version():
    rec = arxiv_oai.parse_raw_record(
        _raw_record("2412.18783", "Wed, 25 Dec 2024 05:19:52 GMT",
                    "Mon, 6 Jan 2025 10:00:00 GMT", "Thu, 17 Sep 2026 08:00:00 GMT")
    )
    assert rec["v1_date"] == datetime(2024, 12, 25, 5, 19, 52, tzinfo=timezone.utc)
    assert rec["versions"][3].date() == date(2026, 9, 17)


def test_july_v1_with_september_revision_lands_in_july(monkeypatch):
    raw = [_raw_record("2607.01234", "Fri, 10 Jul 2026 12:00:00 GMT",
                       "Mon, 14 Sep 2026 09:00:00 GMT")]
    oai = [_oai_rec("2607.01234", created="2026-09-14")]

    kept, _, harvested = _window_ids(monkeypatch, raw, oai, JULY)
    assert [r["arxiv_id"] for r in kept] == ["2607.01234"]
    assert kept[0]["v1_date"].date() == date(2026, 7, 10)
    assert harvested["records"] == (JULY[0], date(2026, 9, 28))

    for window in (SEP_EDITION, SEP_LATE):
        kept, stats, _ = _window_ids(monkeypatch, raw, oai, window)
        assert kept == []
        assert stats.records_revision == 1


def test_2024_paper_revised_in_september_lands_in_no_september_window(monkeypatch):
    raw = [_raw_record("2412.18783", "Wed, 25 Dec 2024 05:19:52 GMT",
                       "Thu, 17 Sep 2026 08:00:00 GMT")]
    oai = [_oai_rec("2412.18783", created="2026-09-17")]
    for window in (SEP_EDITION, SEP_LATE, (date(2026, 9, 1), date(2026, 9, 30))):
        kept, stats, _ = _window_ids(monkeypatch, raw, oai, window)
        assert kept == []
        assert stats.records_revision == 1


def test_uncovered_record_uses_getrecord_v1(monkeypatch):
    oai = [_oai_rec("2412.18783", created="2026-09-17")]
    lookups = {"2412.18783": datetime(2024, 12, 25, tzinfo=timezone.utc)}
    kept, stats, _ = _window_ids(monkeypatch, [], oai, SEP_EDITION, lookups=lookups)
    assert kept == [] and stats.records_revision == 1


class _Cur:
    def __init__(self, log, existing_id=None):
        self.log = log
        self.existing_id = existing_id

    def __enter__(self):
        return self

    def __exit__(self, *a):
        return None

    def execute(self, sql, params=None):
        self.log.append((" ".join(sql.split()), params))

    def fetchone(self):
        return {"paper_id": self.existing_id or 7, "content_hash": "h",
                "arxiv_version": 1, "title": "T", "abstract": "A"}


class _Conn:
    def __init__(self, existing_id=None):
        self.log = []
        self.existing_id = existing_id

    def cursor(self):
        return _Cur(self.log, self.existing_id)


def test_upsert_writes_v1_not_created(monkeypatch):
    from paper_intelligence.catalog import ingest as cat

    monkeypatch.setattr(cat, "find_existing_paper_id", lambda *a, **k: None)
    rec = _oai_rec("2607.01234", created="2026-09-14")
    rec["v1_date"] = datetime(2026, 7, 10, 12, tzinfo=timezone.utc)
    conn = _Conn()
    cat.upsert_paper_from_oai(conn, rec, set_spec="cs")
    sql, params = next(c for c in conn.log if c[0].startswith("INSERT INTO paper_intelligence.papers"))
    assert rec["v1_date"] in params
    assert all(
        not (isinstance(p, datetime) and p.month == 9) for p in params
    ), "September revision date must not reach published_at"


def test_upsert_update_overwrites_published_at_with_v1(monkeypatch):
    from paper_intelligence.catalog import ingest as cat

    monkeypatch.setattr(cat, "find_existing_paper_id", lambda *a, **k: 7)
    rec = _oai_rec("2607.01234", created="2026-09-14")
    rec["v1_date"] = datetime(2026, 7, 10, 12, tzinfo=timezone.utc)
    conn = _Conn(existing_id=7)
    cat.upsert_paper_from_oai(conn, rec, set_spec="cs")
    sql, params = next(c for c in conn.log if c[0].startswith("UPDATE paper_intelligence.papers SET arxiv_id"))
    assert "published_at = COALESCE(%s, published_at)" in sql
    assert rec["v1_date"] in params


def test_upsert_refuses_insert_without_v1(monkeypatch):
    from paper_intelligence.catalog import ingest as cat

    monkeypatch.setattr(cat, "find_existing_paper_id", lambda *a, **k: None)
    with pytest.raises(ValueError, match="without a v1 date"):
        cat.upsert_paper_from_oai(_Conn(), _oai_rec("2607.01234", "2026-09-14"), set_spec="cs")


def _atom_feed(total: int, entries: list[tuple[str, str]]) -> str:
    body = "".join(
        f"""<entry><id>http://arxiv.org/abs/{aid}v2</id>
        <published>{pub}</published><updated>2026-09-20T00:00:00Z</updated>
        <title>Paper {aid}</title><summary>Abs</summary>
        <author><name>Ada Smith</name><arxiv:affiliation>Amazon</arxiv:affiliation></author>
        <arxiv:primary_category term="cs.LG"/><category term="cs.LG"/><category term="stat.ML"/>
        </entry>"""
        for aid, pub in entries
    )
    return f"""<feed xmlns="http://www.w3.org/2005/Atom"
      xmlns:arxiv="http://arxiv.org/schemas/atom"
      xmlns:opensearch="http://a9.com/-/spec/opensearch/1.1/">
      <opensearch:totalResults>{total}</opensearch:totalResults>{body}</feed>"""


def test_api_harvester_returns_only_papers_inside_submitted_range():
    pages = {
        0: _atom_feed(4, [("2608.00001", "2026-08-25T00:05:00Z"),
                          ("2608.00002", "2026-08-24T23:59:00Z")]),
        2: _atom_feed(4, [("2608.00003", "2026-08-31T23:00:00Z"),
                          ("2609.00004", "2026-09-01T00:00:01Z")]),
    }
    calls = []

    def fetch(params):
        calls.append(params)
        return pages[params["start"]]

    got = list(arxiv_api.iter_category(
        "cs.LG", date(2026, 8, 25), date(2026, 8, 31), fetch=fetch, page_size=2
    ))
    assert [r["arxiv_id"] for r in got] == ["2608.00001", "2608.00003"]
    assert all(date(2026, 8, 25) <= r["v1_date"].date() <= date(2026, 8, 31) for r in got)
    assert [c["start"] for c in calls] == [0, 2]
    assert calls[0]["search_query"] == (
        "cat:cs.LG AND submittedDate:[202608250000 TO 202608312359]"
    )
    assert got[0]["authors_structured"][0]["affiliation"] == "Amazon"
    assert got[0]["categories"] == ["cs.LG", "stat.ML"]


def test_api_harvest_window_dedupes_and_writes_status(tmp_path, monkeypatch):
    monkeypatch.setattr(arxiv_api, "STATUS_EVERY", 2)
    feed = _atom_feed(3, [("2608.00001", "2026-08-26T00:00:00Z"),
                          ("2608.00002", "2026-08-27T00:00:00Z"),
                          ("2608.00003", "2026-08-28T00:00:00Z")])
    upserts, snapshots = [], []
    status = tmp_path / "status.json"
    real_write = arxiv_api._write_status

    def spy_write(path, stats):
        real_write(path, stats)
        snapshots.append(json.loads(path.read_text())["unique_papers"])

    monkeypatch.setattr(arxiv_api, "_write_status", spy_write)

    class Conn:
        def commit(self):
            pass

    stats = arxiv_api.harvest_window(
        Conn(), date(2026, 8, 25), date(2026, 8, 31),
        run_id="r1", categories=["cs.LG", "stat.ML"], status_path=status,
        fetch=lambda p: feed,
        upsert=lambda conn, rec, set_spec: (upserts.append(rec["arxiv_id"]) or 1, True),
    )
    assert upserts == ["2608.00001", "2608.00002", "2608.00003"]
    assert stats.entries_seen == 6 and stats.unique_papers == 3
    assert 2 in snapshots
    final = json.loads(status.read_text())
    assert final["status"] == "succeeded" and final["run_id"] == "r1"


def test_v1_floor_clamps_reports_and_scoring():
    assert clamp_window("2026-06-15", "2026-07-10") == ("2026-07-01", "2026-07-10", True)
    assert clamp_window("2026-05-01", "2026-06-30")[2] is False
    assert clamp_window("2026-08-25", "2026-08-31") == ("2026-08-25", "2026-08-31", True)
    assert clamp_window("2026-06-15", "2026-07-10", include_pre_floor=True)[0] == "2026-06-15"
    assert clamp_window(date(2026, 6, 1), date(2026, 7, 2))[0] == date(2026, 7, 1)
