"""Two arXiv papers claiming one DOI: keep both papers, never merge, never crash ingest."""

from __future__ import annotations

import json
from datetime import datetime, timezone

from paper_intelligence.catalog import ingest as cat

DOI = "10.1109/isbi61048.2026.11515401"


class _Cur:
    def __init__(self, conn):
        self.conn = conn
        self.last = None

    def __enter__(self):
        return self

    def __exit__(self, *a):
        return None

    def execute(self, sql, params=None):
        text = " ".join(sql.split())
        self.conn.log.append((text, params))
        self.last = text

    def fetchone(self):
        if self.conn.row_id is None:
            return None
        return {"paper_id": self.conn.row_id, "content_hash": "h", "arxiv_version": 1,
                "title": "T", "abstract": "A"}


class _Conn:
    def __init__(self, row_id=7):
        self.log: list[tuple[str, tuple]] = []
        self.row_id = row_id

    def cursor(self):
        return _Cur(self)


def _rec(arxiv_id: str, doi: str | None = DOI) -> dict:
    return {
        "identifier": f"oai:arXiv.org:{arxiv_id}", "datestamp": "2026-09-17", "deleted": False,
        "arxiv_id": arxiv_id, "created": "2026-07-10", "updated": None, "title": "T",
        "abstract": "A", "categories": ["cs.CV"], "doi": doi, "journal_ref": None,
        "authors": ["A B"], "authors_structured": [],
        "v1_date": datetime(2026, 7, 10, 12, tzinfo=timezone.utc),
    }


def _papers_write(conn):
    return next(c for c in conn.log if c[0].startswith(("INSERT INTO paper_intelligence.papers",
                                                          "UPDATE paper_intelligence.papers SET arxiv_id")))


def test_update_drops_doi_held_by_another_paper(monkeypatch):
    monkeypatch.setattr(cat, "find_existing_paper_id", lambda *a, **k: 7)
    monkeypatch.setattr(cat, "doi_holder", lambda conn, doi, exclude_paper_id: 100029)
    conn = _Conn(row_id=7)
    cat.upsert_paper_from_oai(conn, _rec("2607.05555"), set_spec="cs")
    sql, params = _papers_write(conn)
    assert "doi = COALESCE(%s, doi)" in sql
    assert DOI not in params
    raw = json.loads(next(p for p in params if isinstance(p, str) and "doi_conflict" in p))
    assert raw["doi_conflict"] == {"doi": DOI, "held_by_paper_id": 100029}
    assert raw["doi"] == DOI
    assert not any(p and "'doi'" in c for c, p in conn.log if "paper_identity_map" in c)


def test_insert_drops_doi_held_by_another_paper(monkeypatch):
    monkeypatch.setattr(cat, "find_existing_paper_id", lambda *a, **k: None)
    monkeypatch.setattr(cat, "doi_holder", lambda conn, doi, exclude_paper_id: 100029)
    conn = _Conn(row_id=8)
    paper_id, is_new = cat.upsert_paper_from_oai(conn, _rec("2607.05555"), set_spec="cs")
    sql, params = _papers_write(conn)
    assert sql.startswith("INSERT") and is_new and paper_id == 8
    assert params[2] is None
    assert not any(c.startswith("INSERT INTO paper_intelligence.paper_identity_map") and "'doi'" in c
                   for c, _ in conn.log)


def test_doi_kept_when_no_other_paper_holds_it(monkeypatch):
    monkeypatch.setattr(cat, "find_existing_paper_id", lambda *a, **k: None)
    monkeypatch.setattr(cat, "doi_holder", lambda conn, doi, exclude_paper_id: None)
    conn = _Conn(row_id=8)
    cat.upsert_paper_from_oai(conn, _rec("2607.05555"), set_spec="cs")
    _, params = _papers_write(conn)
    assert params[2] == DOI


def test_doi_lookup_never_matches_a_different_arxiv_id():
    conn = _Conn(row_id=None)
    assert cat.find_existing_paper_id(conn, arxiv_id="2607.05555", doi=DOI, source="arxiv_oai",
                                      source_external_id=None) is None
    doi_sql, doi_params = next(c for c in conn.log if "WHERE doi = %s" in c[0])
    assert "arxiv_id IS NULL OR arxiv_id = %s" in doi_sql
    assert doi_params == (DOI, "2607.05555", "2607.05555")


def test_doi_holder_excludes_own_row():
    conn = _Conn(row_id=7)
    cat.doi_holder(conn, DOI, exclude_paper_id=7)
    sql, params = conn.log[-1]
    assert "paper_id <> %s" in sql and params == (DOI, 7, 7)
    assert cat.doi_holder(_Conn(), None, exclude_paper_id=None) is None
