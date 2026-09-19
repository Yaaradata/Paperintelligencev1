"""Tests for PI catalog feature flag, relevance, and independence."""

from __future__ import annotations

import paper_intelligence.common.config as cfg
import paper_intelligence.db.results as results_mod
from paper_intelligence.catalog.normalize import normalize_arxiv_id, normalize_doi
from paper_intelligence.catalog.relevance import (
    RELEVANCE_KEEP_STATUSES,
    current_relevance,
    latest_relevance_decision,
)


def test_normalize_arxiv_rediscovery_same_id():
    assert normalize_arxiv_id("2609.03181") == normalize_arxiv_id("2609.03181v2")
    assert normalize_arxiv_id("https://arxiv.org/abs/2609.03181v3") == "2609.03181"


def test_doi_normalization():
    assert normalize_doi("DOI:10.1/X") == "10.1/x"


def test_entity_resolved_in_keep_mapping():
    assert "ENTITY_RESOLVED" in RELEVANCE_KEEP_STATUSES
    assert "REJECTED" not in RELEVANCE_KEEP_STATUSES


def test_feature_flag_default_off(monkeypatch):
    monkeypatch.delenv("PI_USE_PAPERS_CATALOG", raising=False)
    monkeypatch.setenv("PI_USE_PAPERS_CATALOG", "0")
    import importlib

    importlib.reload(cfg)
    importlib.reload(results_mod)
    assert cfg.PI_USE_PAPERS_CATALOG is False
    # restore default for other tests
    monkeypatch.setenv("PI_USE_PAPERS_CATALOG", "0")
    importlib.reload(cfg)
    importlib.reload(results_mod)


def test_feature_flag_on_uses_pi_sql(monkeypatch):
    monkeypatch.setenv("PI_USE_PAPERS_CATALOG", "1")
    import importlib

    importlib.reload(cfg)
    importlib.reload(results_mod)
    assert cfg.PI_USE_PAPERS_CATALOG is True
    assert "paper_intelligence.papers" in results_mod.PAPER_FIELDS_SQL_PI
    assert "research_radar.content_items" in results_mod.PAPER_FIELDS_SQL_RADAR
    monkeypatch.setenv("PI_USE_PAPERS_CATALOG", "0")
    importlib.reload(cfg)
    importlib.reload(results_mod)


def test_latest_screen_scores_sql_no_status_when_flag_off():
    """Legacy path still must not filter quality screens by Radar status."""
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

    # Ensure flag off
    results_mod.PI_USE_PAPERS_CATALOG = False
    results_mod.latest_screen_scores(Conn(), date_from="2026-09-01", date_until="2026-09-02")
    assert "ci.status" not in captured["sql"]


def test_select_window_candidates_pi_path_no_eligible_statuses(monkeypatch):
    monkeypatch.setenv("PI_USE_PAPERS_CATALOG", "1")
    import importlib

    importlib.reload(cfg)
    importlib.reload(results_mod)

    called = {}

    def fake_pi(**kwargs):
        called.update(kwargs)
        return [1, 2]

    monkeypatch.setattr(
        "paper_intelligence.catalog.shadow.select_window_candidates_pi",
        lambda *a, **k: fake_pi(**k),
    )
    ids = results_mod.select_window_candidates(
        object(),
        date_from="2026-09-01",
        date_until="2026-09-02",
        stage_task_type="screen",
    )
    assert ids == [1, 2]
    assert called["stage_task_type"] == "screen"
    monkeypatch.setenv("PI_USE_PAPERS_CATALOG", "0")
    importlib.reload(cfg)
    importlib.reload(results_mod)
