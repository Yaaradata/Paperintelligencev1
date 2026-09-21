"""Unit tests for PI-first ingest, relevance candidates, and catalog independence."""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import MagicMock

import paper_intelligence.common.config as cfg
import paper_intelligence.relevance.stage as relevance_stage
from paper_intelligence.catalog.normalize import (
    extract_arxiv_version,
    normalize_arxiv_id,
    normalize_doi,
)


def test_arxiv_version_preserved_separately():
    assert normalize_arxiv_id("2609.03181v2") == "2609.03181"
    assert extract_arxiv_version("2609.03181v2") == 2
    assert extract_arxiv_version("2609.03181") is None


def test_doi_normalization_strips_url():
    assert normalize_doi("https://doi.org/10.1234/AbC") == "10.1234/abc"


def test_select_candidates_pi_sql_has_no_radar_status(monkeypatch):
    monkeypatch.setenv("PI_USE_PAPERS_CATALOG", "1")
    import importlib

    importlib.reload(cfg)
    importlib.reload(relevance_stage)

    captured = {}

    class Cur:
        def __enter__(self):
            return self

        def __exit__(self, *a):
            return None

        def execute(self, sql, params):
            captured["sql"] = " ".join(sql.split())
            captured["params"] = list(params)

        def fetchall(self):
            return []

    class Conn:
        def cursor(self):
            return Cur()

    relevance_stage._select_candidates_pi(
        Conn(), "2026-09-01", "2026-09-02", limit=10, reprocess=False
    )
    assert "research_radar" not in captured["sql"]
    assert "INGESTED" not in captured["sql"]
    assert "paper_intelligence.papers" in captured["sql"]
    assert "paper_relevance_results" in captured["sql"]

    monkeypatch.setenv("PI_USE_PAPERS_CATALOG", "0")
    importlib.reload(cfg)
    importlib.reload(relevance_stage)


def test_select_candidates_pi_reprocess_uses_version_rules(monkeypatch):
    captured = {}

    class Cur:
        def __enter__(self):
            return self

        def __exit__(self, *a):
            return None

        def execute(self, sql, params):
            captured["sql"] = " ".join(sql.split())
            captured["params"] = list(params)

        def fetchall(self):
            return []

    class Conn:
        def cursor(self):
            return Cur()

    relevance_stage._select_candidates_pi(
        Conn(), "2026-09-01", "2026-09-02", limit=5, reprocess=True
    )
    assert "migrated_legacy_state" in captured["sql"]
    assert "stage_version" in captured["sql"]
    assert "research_radar" not in captured["sql"]


def test_upsert_paper_find_existing_prefers_arxiv(monkeypatch):
    from paper_intelligence.catalog import ingest as ingest_mod

    calls = []

    class Cur:
        def __enter__(self):
            return self

        def __exit__(self, *a):
            return None

        def execute(self, sql, params):
            calls.append((" ".join(sql.split()), params))
            self._sql = sql

        def fetchone(self):
            # First query (by arxiv) hits
            if "WHERE arxiv_id" in self._sql and "identity_map" not in self._sql:
                return {"paper_id": 42}
            return None

    class Conn:
        def cursor(self):
            return Cur()

    pid = ingest_mod.find_existing_paper_id(
        Conn(),
        arxiv_id="2609.03181",
        doi="10.1/x",
        source="arxiv_oai",
        source_external_id="oai:arXiv.org:2609.03181",
    )
    assert pid == 42
    assert any("arxiv_id" in c[0] for c in calls)


def test_radar_compat_failure_does_not_raise(monkeypatch):
    """Simulated Radar write failure after PI success must be swallowed."""
    from paper_intelligence.ingest import arxiv_oai as oai

    monkeypatch.setattr(oai, "PI_WRITE_RADAR_COMPAT", True)
    monkeypatch.setattr(
        oai,
        "upsert_item",
        lambda *a, **k: (_ for _ in ()).throw(RuntimeError("radar down")),
    )
    ok = oai._radar_compat_write(
        MagicMock(),
        {
            "arxiv_id": "2609.03181",
            "identifier": "oai:arXiv.org:2609.03181",
            "title": "t",
            "abstract": "a",
            "categories": ["cs.AI"],
            "authors": ["A"],
            "authors_structured": [],
            "created": "2026-09-02",
            "updated": None,
            "doi": None,
            "journal_ref": None,
            "datestamp": "2026-09-02",
            "deleted": False,
        },
        paper_id=999,
    )
    assert ok is False


def test_store_relevance_skips_when_compat_off(monkeypatch):
    monkeypatch.setattr(relevance_stage, "PI_WRITE_RADAR_COMPAT", False)
    # Would raise if it tried to use cursor
    relevance_stage._store_relevance(SimpleNamespace(), 1, 9.0, None, [], "x")


def test_newsletter_candidate_sql_pi_has_no_radar():
    from scripts import select_newsletter as sn  # type: ignore

    # scripts may not be a package — import via path already on sys in runtime.
    import importlib.util
    from pathlib import Path

    path = Path(__file__).resolve().parents[2] / "scripts" / "select_newsletter.py"
    spec = importlib.util.spec_from_file_location("select_newsletter", path)
    mod = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(mod)
    assert "research_radar" not in mod.CANDIDATE_SQL_PI
    assert "paper_intelligence.papers" in mod.CANDIDATE_SQL_PI
    assert "research_radar" in mod.CANDIDATE_SQL_RADAR
