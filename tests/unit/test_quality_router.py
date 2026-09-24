"""Tests for quality candidate routing and version-aware skip logic."""

from __future__ import annotations

import pytest

from paper_intelligence.quality.stage import (
    explain_quality_routing,
    select_quality_candidates,
)


@pytest.fixture(autouse=True)
def _legacy_router_default(monkeypatch):
    """Pin legacy top-slice union unless a test opts into score-all."""
    monkeypatch.setattr(
        "paper_intelligence.quality.stage.ROUTER_SCORE_ALL_SURVIVORS", False
    )

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
            # params[1] = FAST evidence types; params[2] = society email domains
            self._rows = [
                {
                    "content_item_id": cid,
                    "organisation_id": 1000 + int(cid),
                    "confidence": 0.9,
                    "is_org_of_interest": True,
                }
                for cid in self.db.notable_org
                if cid in survivors
            ]
        elif "affiliation_judgments" in text:
            # Default: no judgments → notable-org path unchanged.
            self._rows = list(getattr(self.db, "judgments", []) or [])
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
    def __init__(self, screens, notable_org=None, notable_person=None, judgments=None):
        self.screens = screens
        self.notable_org = notable_org or []
        self.notable_person = notable_person or []
        self.judgments = judgments or []

    def cursor(self):
        return _FakeCur(self)


def _screens_for_router():
    return [
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
        {
            # ENTITY_RESOLVED analogue: still present in latest_screen_scores
            # because router no longer filters Radar status.
            "content_item_id": 137619,
            "result_json": {
                "gate": {"passed": True},
                "technical_significance": 7.0,
                "apparent_novelty": 5.5,
                "evidence_strength": 7.5,
            },
        },
    ]


def test_quality_candidates_union_top_slice_and_notable_org(monkeypatch):
    screens = _screens_for_router()[:4]
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


def test_entity_resolved_screen_pass_enters_router_population(monkeypatch):
    """Case 1+6: PI screen passed + Radar ENTITY_RESOLVED still in router population."""
    screens = _screens_for_router()
    conn = _FakeConn(screens, notable_org=[], notable_person=[])

    monkeypatch.setattr(
        "paper_intelligence.quality.stage.latest_screen_scores",
        lambda *a, **k: screens,
    )

    decisions = {
        d.content_item_id: d
        for d in explain_quality_routing(
            conn, date_from="2026-09-02", date_until="2026-09-02", gate_percentile=15
        )
    }
    assert 137619 in decisions
    assert decisions[137619].decision in {"selected", "not_selected"}
    assert decisions[137619].reason != "blocked_screen_gate_failed"


def test_below_cutoff_gets_explicit_not_selected(monkeypatch):
    """Case 2: screen passed + below cutoff → not_selected with reason."""
    screens = _screens_for_router()
    conn = _FakeConn(screens)

    monkeypatch.setattr(
        "paper_intelligence.quality.stage.latest_screen_scores",
        lambda *a, **k: screens,
    )

    decisions = explain_quality_routing(
        conn, date_from="2026-09-02", date_until="2026-09-02", gate_percentile=15
    )
    by_id = {d.content_item_id: d for d in decisions}
    # With 4 survivors (1,2,3,137619), keep max(1, round(4*0.15))=1 → only id 1
    assert by_id[137619].decision == "not_selected"
    assert by_id[137619].reason == "not_selected_below_gate_percentile"
    assert by_id[2].decision == "not_selected"
    assert by_id[3].decision == "not_selected"


def test_notable_org_override_selects_below_cutoff(monkeypatch):
    """Case 3: notable-org override selects below-cutoff survivor."""
    screens = _screens_for_router()
    conn = _FakeConn(screens, notable_org=[137619], notable_person=[])

    monkeypatch.setattr(
        "paper_intelligence.quality.stage.latest_screen_scores",
        lambda *a, **k: screens,
    )

    ids = select_quality_candidates(
        conn, date_from="2026-09-02", date_until="2026-09-02", gate_percentile=15
    )
    assert 137619 in ids

    decisions = {
        d.content_item_id: d
        for d in explain_quality_routing(
            conn, date_from="2026-09-02", date_until="2026-09-02", gate_percentile=15
        )
    }
    assert decisions[137619].decision == "selected"
    assert decisions[137619].reason == "selected_notable_org"


def test_screen_failed_blocked_from_quality_routing(monkeypatch):
    """Case 4: screen gate failed → blocked."""
    screens = _screens_for_router()
    conn = _FakeConn(screens)

    monkeypatch.setattr(
        "paper_intelligence.quality.stage.latest_screen_scores",
        lambda *a, **k: screens,
    )

    ids = select_quality_candidates(
        conn, date_from="2026-09-02", date_until="2026-09-02", gate_percentile=50
    )
    assert 4 not in ids

    decisions = {
        d.content_item_id: d
        for d in explain_quality_routing(
            conn, date_from="2026-09-02", date_until="2026-09-02", gate_percentile=50
        )
    }
    assert decisions[4].decision == "blocked"
    assert decisions[4].reason == "blocked_screen_gate_failed"


def test_stale_missing_rank_dimensions_blocked(monkeypatch):
    """Case 5: incomplete screen JSON → blocked_missing_rank_dimensions."""
    screens = [
        {
            "content_item_id": 99,
            "result_json": {
                "gate": {"passed": True},
                "technical_significance": 8,
                # missing apparent_novelty / evidence_strength
            },
        }
    ]
    conn = _FakeConn(screens)
    monkeypatch.setattr(
        "paper_intelligence.quality.stage.latest_screen_scores",
        lambda *a, **k: screens,
    )
    decisions = explain_quality_routing(
        conn, date_from="2026-09-02", date_until="2026-09-02", gate_percentile=15
    )
    assert decisions[0].decision == "blocked"
    assert decisions[0].reason == "blocked_missing_rank_dimensions"
    assert select_quality_candidates(
        conn, date_from="2026-09-02", date_until="2026-09-02", gate_percentile=15
    ) == []


def test_latest_screen_scores_sql_has_no_status_filter(monkeypatch):
    """Case 6: Radar status must not appear in latest_screen_scores SQL."""
    from paper_intelligence.db import results as results_mod

    monkeypatch.setattr(results_mod, "PI_USE_PAPERS_CATALOG", False)
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

    results_mod.latest_screen_scores(Conn(), date_from="2026-09-01", date_until="2026-09-02")
    assert "ci.status" not in captured["sql"]
    assert "RELEVANT" not in captured["params"]
    assert "published_at" in captured["sql"]
    assert captured["params"] == ["2026-09-01", "2026-09-02"]


def test_day_scope_invariant_to_window_size(monkeypatch):
    """Same UTC day selection whether run as 1-day or multi-day window."""
    from datetime import datetime, timezone

    screens = [
        {
            "content_item_id": 1,
            "published_at": datetime(2026, 9, 1, 12, tzinfo=timezone.utc),
            "result_json": {
                "gate": {"passed": True},
                "technical_significance": 9,
                "apparent_novelty": 9,
                "evidence_strength": 9,
            },
        },
        {
            "content_item_id": 2,
            "published_at": datetime(2026, 9, 1, 15, tzinfo=timezone.utc),
            "result_json": {
                "gate": {"passed": True},
                "technical_significance": 5,
                "apparent_novelty": 5,
                "evidence_strength": 5,
            },
        },
        {
            "content_item_id": 3,
            "published_at": datetime(2026, 9, 2, 12, tzinfo=timezone.utc),
            "result_json": {
                "gate": {"passed": True},
                "technical_significance": 8,
                "apparent_novelty": 8,
                "evidence_strength": 8,
            },
        },
        {
            "content_item_id": 4,
            "published_at": datetime(2026, 9, 2, 15, tzinfo=timezone.utc),
            "result_json": {
                "gate": {"passed": True},
                "technical_significance": 4,
                "apparent_novelty": 4,
                "evidence_strength": 4,
            },
        },
    ]
    conn = _FakeConn(screens)

    def fake_latest(conn, *, date_from, date_until):
        # Filter like the real query would.
        out = []
        for row in screens:
            day = row["published_at"].date().isoformat()
            if date_from <= day <= date_until:
                out.append(row)
        return out

    monkeypatch.setattr(
        "paper_intelligence.quality.stage.latest_screen_scores", fake_latest
    )

    # 50% per day: day1 survivors 2 → keep 1 (id 1); day2 survivors 2 → keep 1 (id 3)
    day_window = select_quality_candidates(
        conn,
        date_from="2026-09-01",
        date_until="2026-09-02",
        gate_percentile=50,
        percentile_scope="day",
    )
    day_only = select_quality_candidates(
        conn,
        date_from="2026-09-01",
        date_until="2026-09-01",
        gate_percentile=50,
        percentile_scope="day",
    )
    assert day_only == [1]
    assert set(day_window) == {1, 3}

    # Window scope over 2 days: 4 survivors × 50% → keep 2 (ids 1,3)
    window = select_quality_candidates(
        conn,
        date_from="2026-09-01",
        date_until="2026-09-02",
        gate_percentile=50,
        percentile_scope="window",
    )
    assert window == [1, 3]

    decisions = explain_quality_routing(
        conn,
        date_from="2026-09-01",
        date_until="2026-09-02",
        gate_percentile=50,
        percentile_scope="day",
    )
    by_id = {d.content_item_id: d for d in decisions}
    assert by_id[1].percentile_scope == "day"
    assert by_id[1].decision == "selected"
    assert by_id[2].decision == "not_selected"


def test_judge_rejected_org_no_longer_selects(monkeypatch):
    """Judge-rejected OOI org must not trigger selected_notable_org."""
    screens = _screens_for_router()[:4]
    # Paper 3 is below top slice at 50% (keep 1,2) but has OOI — unless rejected.
    judgments = [
        {
            "paper_id": 3,
            "decision": "HTML",
            "judge_called": True,
            "accepted_organisation_ids": [],
            "rejected_organisation_ids": [1003],
        }
    ]
    # Empty accepted with resolved decision → fail-open (no exclusions) per
    # judge_effective. Use non-empty accepted of a different org so 1003 rejects.
    judgments[0]["accepted_organisation_ids"] = [9999]
    conn = _FakeConn(screens, notable_org=[3], judgments=judgments)

    monkeypatch.setattr(
        "paper_intelligence.quality.stage.latest_screen_scores",
        lambda *a, **k: screens,
    )

    ids_raw = select_quality_candidates(
        conn,
        date_from="2026-09-01",
        date_until="2026-09-02",
        gate_percentile=50,
        apply_judge_effective=False,
    )
    assert 3 in ids_raw

    ids = select_quality_candidates(
        conn,
        date_from="2026-09-01",
        date_until="2026-09-02",
        gate_percentile=50,
        apply_judge_effective=True,
    )
    assert 3 not in ids
    assert ids == [1, 2]


def test_select_and_explain_agree_on_selected_ids(monkeypatch):
    screens = _screens_for_router()[:4]
    conn = _FakeConn(screens, notable_org=[3])
    monkeypatch.setattr(
        "paper_intelligence.quality.stage.latest_screen_scores",
        lambda *a, **k: screens,
    )
    ids = set(
        select_quality_candidates(
            conn, date_from="2026-09-01", date_until="2026-09-02", gate_percentile=50
        )
    )
    explained = {
        d.content_item_id
        for d in explain_quality_routing(
            conn, date_from="2026-09-01", date_until="2026-09-02", gate_percentile=50
        )
        if d.decision == "selected"
    }
    assert ids == explained


def test_version_aware_skip_sql_includes_versions(monkeypatch):
    """Build the NOT EXISTS clause shape via select_window_candidates parameterization.

    Uses the deprecated Radar reader branch explicitly — PI-catalog skip SQL
    is version-aware via classification_results joins, not Radar status.
    """
    monkeypatch.setenv("PI_USE_PAPERS_CATALOG", "0")
    import importlib

    import paper_intelligence.common.config as cfg
    from paper_intelligence.db import results as results_mod

    importlib.reload(cfg)
    importlib.reload(results_mod)

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
    assert "ci.status = ANY(%s)" in captured["sql"]
    assert captured["params"][0] == "2026-09-01"
    assert captured["params"][1] == "2026-09-02"
    assert "ENTITY_RESOLVED" in captured["params"][2]
    assert "RELEVANT" in captured["params"][2]
    assert captured["params"][3:] == [
        "domain",
        "v002",
        "v003",
        "v004",
        "z-ai/glm-5.3-flash",
    ]
    monkeypatch.setenv("PI_USE_PAPERS_CATALOG", "1")
    importlib.reload(cfg)
    importlib.reload(results_mod)


def test_score_all_survivors_selects_every_rankable(monkeypatch):
    monkeypatch.setattr(
        "paper_intelligence.quality.stage.ROUTER_SCORE_ALL_SURVIVORS", True
    )
    screens = _screens_for_router()[:4]
    conn = _FakeConn(screens, notable_org=[3])
    monkeypatch.setattr(
        "paper_intelligence.quality.stage.latest_screen_scores",
        lambda *a, **k: screens,
    )
    ids = select_quality_candidates(
        conn, date_from="2026-09-01", date_until="2026-09-02", gate_percentile=50
    )
    # survivors 1,2,3 (4 blocked) — all selected regardless of GATE_PERCENTILE
    assert ids == [1, 2, 3]
    by_id = {
        d.content_item_id: d
        for d in explain_quality_routing(
            conn, date_from="2026-09-01", date_until="2026-09-02", gate_percentile=50
        )
    }
    assert by_id[1].reason == "selected_all_survivors"
    assert by_id[1].would_have_been_top_slice is True
    assert by_id[3].reason == "selected_all_survivors"
    assert by_id[3].would_have_been_top_slice is False
    assert by_id[3].notable_org is True
    assert by_id[4].decision == "blocked"


def test_score_all_survivors_param_overrides_config(monkeypatch):
    monkeypatch.setattr(
        "paper_intelligence.quality.stage.ROUTER_SCORE_ALL_SURVIVORS", False
    )
    screens = _screens_for_router()[:4]
    conn = _FakeConn(screens)
    monkeypatch.setattr(
        "paper_intelligence.quality.stage.latest_screen_scores",
        lambda *a, **k: screens,
    )
    ids = select_quality_candidates(
        conn,
        date_from="2026-09-01",
        date_until="2026-09-02",
        gate_percentile=50,
        score_all_survivors=True,
    )
    assert ids == [1, 2, 3]
