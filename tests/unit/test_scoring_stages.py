"""Unit tests for the paid scoring stages: parsing, gating, vocabulary, org score."""

from __future__ import annotations

import json

import pytest

from paper_intelligence.adjudication.org_score import organisation_score
from paper_intelligence.audience_domain import stage as classify
from paper_intelligence.common.llm_stage import paper_block, parse_json_object, random_batches
from paper_intelligence.quality import stage as quality
from paper_intelligence.screen import stage as screen


def _screen_payload(content_id: int, **overrides) -> str:
    entry = {
        "content_item_id": content_id,
        "ai_relevance": 7.0,
        "technical_significance": 6.5,
        "apparent_novelty": 6.0,
        "evidence_strength": 5.5,
    }
    entry.update(overrides)
    return json.dumps({"papers": [entry]})


class TestScreenParsing:
    def test_valid_scores_parse(self):
        parsed, problems = screen.parse_response(_screen_payload(1), {1})
        assert problems == []
        assert parsed[1]["ai_relevance"] == 7.0

    def test_fenced_json_is_accepted(self):
        text = f"```json\n{_screen_payload(1)}\n```"
        parsed, _ = screen.parse_response(text, {1})
        assert parsed[1]["technical_significance"] == 6.5

    def test_off_scale_score_is_rejected_not_clamped(self):
        parsed, problems = screen.parse_response(_screen_payload(1, ai_relevance=12.0), {1})
        assert parsed == {}
        assert any("invalid ai_relevance" in p for p in problems)

    def test_non_half_increment_is_rejected(self):
        parsed, problems = screen.parse_response(_screen_payload(1, apparent_novelty=6.3), {1})
        assert parsed == {}
        assert any("apparent_novelty" in p for p in problems)

    def test_unexpected_and_missing_ids_are_reported(self):
        parsed, problems = screen.parse_response(_screen_payload(99), {1})
        assert parsed == {}
        assert any("unexpected content_item_id 99" in p for p in problems)
        assert any("missing ids: [1]" in p for p in problems)


class TestScreenGate:
    def test_gate_is_code_not_model(self):
        scores = {"ai_relevance": 4.5}
        assert screen.gate_decision(scores, 5.0) is False
        assert screen.gate_decision({"ai_relevance": 5.0}, 5.0) is True

    def test_failing_paper_keeps_its_other_scores(self):
        """A gate failure must not zero or suppress the honest dimension scores."""
        parsed, _ = screen.parse_response(
            _screen_payload(1, ai_relevance=1.0, technical_significance=9.0), {1}
        )
        assert parsed[1]["technical_significance"] == 9.0
        assert screen.gate_decision(parsed[1], 5.0) is False


class TestClassifyVocabulary:
    def test_in_vocabulary_values_pass(self):
        values, oov = classify.validate_entry(
            {
                "audience_relevance": ["practitioner"],
                "domain": "computer_vision",
                "subdomains": ["object_detection"],
                "application_domain": ["general_method"],
                "confidence": 8.0,
            }
        )
        assert oov == []
        assert values["domain"] == "computer_vision"
        assert values["subdomains"] == ["object_detection"]

    def test_invented_values_are_reported_not_dropped_silently(self):
        values, oov = classify.validate_entry(
            {"domain": "quantum_telepathy", "audience_relevance": ["wizards"]}
        )
        assert values["domain"] is None
        assert any(o.startswith("domain:quantum_telepathy") for o in oov)
        assert any(o.startswith("audience:wizards") for o in oov)

    def test_subdomain_must_belong_to_chosen_domain(self):
        values, oov = classify.validate_entry(
            {"domain": "computer_vision", "subdomains": ["language_modeling"]}
        )
        assert values["subdomains"] == []
        assert any("subdomain:language_modeling" in o for o in oov)

    def test_general_method_is_exclusive(self):
        values, _ = classify.validate_entry(
            {"domain": "computer_vision", "application_domain": ["general_method", "healthcare"]}
        )
        assert values["application_domain"] == ["general_method"]


class TestQualityScoring:
    def test_composite_applies_evidence_factor_once(self):
        scores = {dim: 6.0 for dim in quality.RUBRIC_DIMENSIONS}
        result = quality.composite_score(scores)
        assert result["quality"] == pytest.approx(6.0, abs=1e-6)
        assert result["evidence_factor"] == pytest.approx(0.88, abs=1e-6)
        assert result["final"] == pytest.approx(5.28, abs=1e-4)

    def test_org_boost_is_capped(self):
        scores = {dim: 6.0 for dim in quality.RUBRIC_DIMENSIONS}
        result = quality.composite_score(scores, org_boost=5.0, person_boost=5.0)
        assert result["org_boost"] == quality.MAX_ORG_BOOST
        assert result["person_boost"] == quality.MAX_PERSON_BOOST

    def test_final_score_never_exceeds_ten(self):
        scores = {dim: 10.0 for dim in quality.RUBRIC_DIMENSIONS}
        assert quality.composite_score(scores, org_boost=0.5)["final"] == 10.0

    def test_missing_reason_not_higher_is_flagged(self):
        entry = {dim: 6.0 for dim in quality.RUBRIC_DIMENSIONS}
        entry["content_item_id"] = 1
        entry["so_what"] = "useful"
        parsed, problems = quality.parse_response(json.dumps({"papers": [entry]}), {1})
        assert 1 in parsed
        assert any("missing reason_not_higher" in p for p in problems)


class TestBlinding:
    def test_paper_payload_excludes_authors_and_affiliations(self):
        block = paper_block(
            {
                "content_item_id": 1,
                "title": "T",
                "abstract": "A",
                "categories": ["cs.LG"],
                "authors_raw": ["Yann LeCun"],
                "affiliation_text": ["Meta AI"],
            }
        )
        assert "LeCun" not in block
        assert "Meta" not in block

    def test_quality_prompt_is_blinded(self):
        prompt = quality.build_user_prompt(
            [
                {
                    "content_item_id": 1,
                    "title": "T",
                    "abstract": "A",
                    "categories": [],
                    "authors_raw": ["Geoffrey Hinton"],
                }
            ]
        )
        assert "Hinton" not in prompt


class TestOrganisationScore:
    def test_watchlist_org_scores_higher_than_unlisted(self):
        listed = organisation_score(
            [
                {
                    "organisation_id": 1,
                    "canonical_name": "DeepMind",
                    "priority": 3,
                    "is_org_of_interest": True,
                    "evidence_type": "paper_affiliation",
                    "confidence": 0.95,
                }
            ]
        )
        unlisted = organisation_score(
            [
                {
                    "organisation_id": 2,
                    "canonical_name": "Small Lab",
                    "priority": 0,
                    "is_org_of_interest": False,
                    "evidence_type": "paper_affiliation",
                    "confidence": 0.95,
                }
            ]
        )
        assert listed["organisation_score"] > unlisted["organisation_score"]
        assert unlisted["status"] == "resolved"

    def test_same_org_has_constant_standing(self):
        """organisation_score is a property of the org; only org_boost varies by evidence."""
        base = {
            "organisation_id": 1,
            "canonical_name": "Stanford University",
            "priority": 0,
            "is_org_of_interest": False,
        }
        strong = organisation_score([{**base, "evidence_type": "email_domain", "confidence": 0.9}])
        weak = organisation_score(
            [{**base, "evidence_type": "explicit_paper_affiliation", "confidence": 0.637}]
        )
        assert strong["organisation_score"] == weak["organisation_score"] == 3.0
        assert strong["org_boost"] > weak["org_boost"]

    def test_boost_never_exceeds_cap(self):
        result = organisation_score(
            [
                {
                    "organisation_id": 1,
                    "canonical_name": "DeepMind",
                    "priority": 3,
                    "is_org_of_interest": True,
                    "evidence_type": "paper_affiliation",
                    "confidence": 1.0,
                }
            ]
        )
        assert result["org_boost"] <= quality.MAX_ORG_BOOST

    def test_author_profile_evidence_earns_weaker_boost(self):
        base = {
            "organisation_id": 1,
            "canonical_name": "DeepMind",
            "priority": 3,
            "is_org_of_interest": True,
            "confidence": 1.0,
        }
        paper = organisation_score([{**base, "evidence_type": "paper_affiliation"}])
        profile = organisation_score([{**base, "evidence_type": "author_profile"}])
        assert paper["organisation_score"] == profile["organisation_score"]
        assert profile["org_boost"] < paper["org_boost"]

    def test_no_evidence_differs_from_unresolved(self):
        assert organisation_score([])["status"] == "no_evidence_supplied"
        unresolved = organisation_score(
            [
                {
                    "organisation_id": None,
                    "canonical_name": None,
                    "evidence_type": "paper_affiliation",
                    "confidence": 0.9,
                }
            ]
        )
        assert unresolved["status"] == "unresolved"
        assert unresolved["org_boost"] == 0.0

    def test_low_confidence_evidence_is_ignored(self):
        result = organisation_score(
            [
                {
                    "organisation_id": 1,
                    "canonical_name": "DeepMind",
                    "priority": 3,
                    "is_org_of_interest": True,
                    "evidence_type": "paper_affiliation",
                    "confidence": 0.2,
                }
            ]
        )
        assert result["status"] == "unresolved"


class TestBatching:
    def test_batches_cover_every_item_exactly_once(self):
        items = list(range(37))
        batches = random_batches(items, 15)
        flat = [item for batch in batches for item in batch]
        assert sorted(flat) == items
        assert len(batches) == 3

    def test_parse_json_object_rejects_prose(self):
        with pytest.raises(ValueError):
            parse_json_object("I cannot score these papers.")
