"""Tests for quality candidate routing and version-aware skip logic."""

from __future__ import annotations

from paper_intelligence.quality.stage import select_quality_candidates


class _FakeCur:
    def __init__(self, db):
        self.db = db
        self._rows = []

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return None

    def execute(self, sql, params=None):
        text = " ".join(sql.split())
        if "paper_author_affiliations" in text and "is_org_of_interest" in text:
            survivors = set(params[0])
            self._rows = [
                {"content_item_id": cid}
                for cid in self.db.notable_org
                if cid in survivors
            ]
        elif "papers_people" in text:
            survivors = set(params[0])
            self._rows = [
                {"content_item_id": cid}
                for cid in self.db.notable_person
                if cid in survivors
            ]
        else:
            self._rows = []

    def fetchall(self):
        return list(self._rows)


class _FakeConn:
    def __init__(self, screens, notable_org=None, notable_person=None):
        self.screens = screens
        self.notable_org = notable_org or []
        self.notable_person = notable_person or []

    def cursor(self):
        return _FakeCur(self)


def test_quality_candidates_union_top_slice_and_notable_org(monkeypatch):
    screens = [
        {
            "content_item_id": 1,
            "result_json": {
                "gate": {"passed": True},
                "technical_significance": 9,
                "apparent_novelty": 9,
                "evidence_strength": 9,
            },
        },
        {
            "content_item_id": 2,
            "result_json": {
                "gate": {"passed": True},
                "technical_significance": 5,
                "apparent_novelty": 5,
                "evidence_strength": 5,
            },
        },
        {
            "content_item_id": 3,
            "result_json": {
                "gate": {"passed": True},
                "technical_significance": 4,
                "apparent_novelty": 4,
                "evidence_strength": 4,
            },
        },
        {
            "content_item_id": 4,
            "result_json": {
                "gate": {"passed": False},
                "technical_significance": 10,
                "apparent_novelty": 10,
                "evidence_strength": 10,
            },
        },
    ]
    conn = _FakeConn(screens, notable_org=[3], notable_person=[])

    def fake_latest(conn, *, date_from, date_until):
        return screens

    monkeypatch.setattr(
        "paper_intelligence.quality.stage.latest_screen_scores", fake_latest
    )

    # gate_percentile 50% of 3 survivors => keep 2 (ids 1,2); union notable org 3
    ids = select_quality_candidates(
        conn, date_from="2026-09-01", date_until="2026-09-02", gate_percentile=50
    )
    assert ids == [1, 2, 3]


def test_version_aware_skip_sql_includes_versions():
    """Build the NOT EXISTS clause shape via select_window_candidates parameterization."""
    from paper_intelligence.db import results as results_mod

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

    results_mod.select_window_candidates(
        Conn(),
        date_from="2026-09-01",
        date_until="2026-09-02",
        stage_task_type="domain",
        stage_version="v002",
        prompt_version="v003",
        policy_version="v004",
        model="z-ai/glm-5.3-flash",
    )
    assert "r.stage_version = %s" in captured["sql"]
    assert "r.prompt_version = %s" in captured["sql"]
    assert "r.policy_version = %s" in captured["sql"]
    assert "r.model = %s" in captured["sql"]
    assert captured["params"] == [
        "2026-09-01",
        "2026-09-02",
        "RELEVANT",
        "domain",
        "v002",
        "v003",
        "v004",
        "z-ai/glm-5.3-flash",
    ]
