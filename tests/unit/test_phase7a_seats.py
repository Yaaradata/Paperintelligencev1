"""Phase 7a: seat-score classification policy, parser, pools, product-slice router."""

from __future__ import annotations

import json

import pytest

from paper_intelligence.audience_domain import pools
from paper_intelligence.audience_domain import stage as classify
from paper_intelligence.audience_domain import vocabulary
from paper_intelligence.audience_domain.stage import render_system_prompt
from paper_intelligence.editorial.seats import format_seats_xml
from paper_intelligence.quality.stage import (
    explain_quality_routing,
    select_product_slice_survivors,
    select_quality_candidates,
)


def test_policy_loads_v002():
    policy = vocabulary.load_policy("v002")
    assert policy["policy_version"] == "v002"
    assert "audience_relevance" not in policy
    assert "seat_scores" in policy
    assert "tech_relevance" in policy["seat_scores"]
    assert "product_relevance" in policy["seat_scores"]
    assert "computer_vision" in policy["domain"]
    assert "general_method" in policy["application_domain"]
    block = vocabulary.vocabulary_block("v002")
    assert "tech_relevance" in block
    assert "product_relevance" in block
    assert "audience_relevance" not in block
    assert vocabulary.audiences("v002") == []


def test_prompt_v003_contains_shared_seat_text_after_substitution():
    rendered = render_system_prompt("v003")
    seats = format_seats_xml("v001")
    assert "{{EDITORIAL_SEATS}}" not in rendered
    assert '<seat name="TECH">' in rendered
    assert '<seat name="PRODUCT">' in rendered
    # Shared seat text present verbatim (from format_seats_xml).
    assert "I can have my team try this on our stack this quarter" in rendered
    assert seats.splitlines()[0] in rendered
    # Per-paper scoring adaptation lives in the prompt, not the seat file.
    assert "A high score (8+) means the reader could plausibly say one of" in rendered
    assert "Sector mention alone does NOT raise" in rendered
    assert "audience_relevance" not in rendered.lower() or "Do **not** emit" in rendered


def test_parser_rejects_missing_seat_scores():
    entry = {
        "batch_index": 1,
        "domain": "computer_vision",
        "subdomains": [],
        "application_domain": ["general_method"],
        "confidence": 8.0,
        # tech_relevance / product_relevance missing
    }
    parsed, problems = classify.parse_response(
        json.dumps({"papers": [entry]}), {1: 42}, policy_version="v002"
    )
    assert 42 not in parsed
    assert any("tech_relevance" in p for p in problems)
    assert any("product_relevance" in p for p in problems)


def test_parser_rejects_non_half_increment_scores():
    entry = {
        "batch_index": 1,
        "tech_relevance": 7.3,
        "product_relevance": 4.0,
        "tech_reason": "x",
        "product_reason": "y",
        "domain": "computer_vision",
        "subdomains": [],
        "application_domain": ["general_method"],
        "confidence": 8.0,
    }
    parsed, problems = classify.parse_response(
        json.dumps({"papers": [entry]}), {1: 42}, policy_version="v002"
    )
    assert 42 not in parsed
    assert any("tech_relevance" in p for p in problems)


def test_parser_accepts_valid_seat_scores():
    entry = {
        "batch_index": 1,
        "tech_relevance": 8.0,
        "product_relevance": 3.5,
        "tech_reason": "Eval protocol an eng lead can trial.",
        "product_reason": "No product decision.",
        "domain": "computer_vision",
        "subdomains": ["object_detection"],
        "application_domain": ["general_method"],
        "confidence": 8.0,
    }
    values, oov = classify.validate_entry(entry, policy_version="v002")
    assert oov == []
    assert values is not None
    assert values["tech_relevance"] == 8.0
    assert values["product_relevance"] == 3.5
    assert "audience_relevance" not in values

    rows = classify._rows_for(
        42,
        values,
        model="test",
        run_id="r1",
        input_content_hash="abc",
        policy_version="v002",
        prompt_version="v003",
        stage_version="v002",
    )
    task_types = {r["task_type"] for r in rows}
    assert task_types == {
        "domain",
        "subdomain",
        "application_domain",
        "tech_relevance",
        "product_relevance",
    }
    assert "audience" not in task_types


@pytest.mark.parametrize(
    "tech,product,expect_tech,expect_product",
    [
        (8.0, 7.0, True, True),  # both
        (8.0, 2.0, True, False),  # tech-only
        (3.0, 7.5, False, True),  # product-only
        (2.0, 2.0, False, False),  # neither
    ],
)
def test_pool_membership_both_tech_product_neither(
    tech, product, expect_tech, expect_product
):
    row = {
        "audience_policy_version": "v002",
        "tech_relevance": tech,
        "product_relevance": product,
        "application_domains": ["healthcare_life_sciences"],
        "audiences": [],
    }
    m = pools.pool_membership(row, policy="v002", tech_min=6.0, product_min=6.0)
    assert m["tech"] is expect_tech
    assert m["product"] is expect_product


def test_sector_only_low_product_not_in_product_pool():
    """Sector application alone must not put a paper in the product pool."""
    row = {
        "audience_policy_version": "v002",
        "tech_relevance": 7.0,
        "product_relevance": 3.0,  # low — sector mention without product decision
        "application_domains": ["financial_services", "healthcare_life_sciences"],
        "audiences": [],
    }
    m = pools.pool_membership(row, policy="v002", tech_min=6.0, product_min=6.0)
    assert m["tech"] is True
    assert m["product"] is False


def test_v001_rows_ignored_by_v002_pools():
    row = {
        "audience_policy_version": "v001",
        "tech_relevance": None,
        "product_relevance": None,
        "audiences": ["enterprise_adoption", "practitioner"],
        "application_domains": ["healthcare_life_sciences"],
    }
    m = pools.pool_membership(row, policy="v002")
    assert m["tech"] is False
    assert m["product"] is False

    # Even if someone stuffed scores without policy version, still ignored.
    row2 = {
        "audience_policy_version": None,
        "tech_relevance": 9.0,
        "product_relevance": 9.0,
        "audiences": [],
        "application_domains": [],
    }
    m2 = pools.pool_membership(row2, policy="v002")
    assert m2["tech"] is False
    assert m2["product"] is False


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
            self._rows = list(getattr(self.db, "judgments", []) or [])
        elif "papers_people" in text:
            survivors = set(params[0])
            self._rows = [
                {"content_item_id": cid}
                for cid in self.db.notable_person
                if cid in survivors
            ]
        elif "product_relevance" in text and "paper_classification_results" in text:
            wanted = set(params[0])
            self._rows = [
                {"content_item_id": cid, "product_relevance": score}
                for cid, score in (self.db.product_scores or {}).items()
                if cid in wanted
            ]
        else:
            self._rows = []

    def fetchall(self):
        return list(self._rows)


class _FakeConn:
    def __init__(
        self,
        screens,
        notable_org=None,
        notable_person=None,
        judgments=None,
        product_scores=None,
    ):
        self.screens = screens
        self.notable_org = notable_org or []
        self.notable_person = notable_person or []
        self.judgments = judgments or []
        self.product_scores = product_scores or {}

    def cursor(self):
        return _FakeCur(self)


def _screens_for_product_slice():
    return [
        {
            "content_item_id": 1,
            "published_at": "2026-09-16",
            "result_json": {
                "gate": {"passed": True},
                "technical_significance": 9,
                "apparent_novelty": 9,
                "evidence_strength": 9,
            },
        },
        {
            "content_item_id": 2,
            "published_at": "2026-09-16",
            "result_json": {
                "gate": {"passed": True},
                "technical_significance": 5,
                "apparent_novelty": 5,
                "evidence_strength": 5,
            },
        },
        {
            "content_item_id": 3,
            "published_at": "2026-09-16",
            "result_json": {
                "gate": {"passed": True},
                "technical_significance": 4,
                "apparent_novelty": 4,
                "evidence_strength": 4,
            },
        },
        {
            "content_item_id": 4,
            "published_at": "2026-09-16",
            "result_json": {
                "gate": {"passed": False},
                "technical_significance": 10,
                "apparent_novelty": 10,
                "evidence_strength": 10,
            },
        },
        {
            "content_item_id": 5,
            "published_at": "2026-09-16",
            "result_json": {
                "gate": {"passed": True},
                "technical_significance": 3,
                "apparent_novelty": 3,
                "evidence_strength": 3,
            },
        },
    ]


def test_router_invariant_when_product_slice_pct_zero(monkeypatch):
    screens = _screens_for_product_slice()
    conn = _FakeConn(
        screens,
        notable_org=[],
        product_scores={3: 9.5, 5: 9.0, 2: 8.0},
    )
    monkeypatch.setattr(
        "paper_intelligence.quality.stage.latest_screen_scores",
        lambda *a, **k: screens,
    )
    monkeypatch.setattr(
        "paper_intelligence.quality.stage.ROUTER_PRODUCT_SLICE_PCT",
        0,
    )

    base = select_quality_candidates(
        conn,
        date_from="2026-09-16",
        date_until="2026-09-16",
        gate_percentile=50,
        percentile_scope="window",
        product_slice_pct=0,
        score_all_survivors=False,
    )
    # 4 screen-passed survivors; 50% => keep 2 (ids 1,2). No product slice.
    assert base == [1, 2]
    assert select_product_slice_survivors(
        conn,
        date_from="2026-09-16",
        date_until="2026-09-16",
        product_slice_pct=0,
    ) == []


def test_product_slice_grows_union_when_flag_on(monkeypatch):
    screens = _screens_for_product_slice()
    # id 5 is below gate percentile on screen rank but has high product_relevance
    conn = _FakeConn(
        screens,
        notable_org=[],
        product_scores={5: 9.5, 3: 8.0, 2: 7.0, 1: 6.0},
    )
    monkeypatch.setattr(
        "paper_intelligence.quality.stage.latest_screen_scores",
        lambda *a, **k: screens,
    )

    off = select_quality_candidates(
        conn,
        date_from="2026-09-16",
        date_until="2026-09-16",
        gate_percentile=50,
        percentile_scope="window",
        product_slice_pct=0,
        score_all_survivors=False,
    )
    on = select_quality_candidates(
        conn,
        date_from="2026-09-16",
        date_until="2026-09-16",
        gate_percentile=50,
        percentile_scope="window",
        product_slice_pct=25,  # of 4 scored survivors → keep 1 → id 5
        score_all_survivors=False,
    )
    assert set(off).issubset(set(on))
    assert set(on) - set(off)  # union grew
    assert 5 in on

    decisions = {
        d.content_item_id: d
        for d in explain_quality_routing(
            conn,
            date_from="2026-09-16",
            date_until="2026-09-16",
            gate_percentile=50,
            percentile_scope="window",
            product_slice_pct=25,
            score_all_survivors=False,
        )
    }
    assert decisions[5].decision == "selected"
    assert decisions[5].reason == "selected_product_slice"
