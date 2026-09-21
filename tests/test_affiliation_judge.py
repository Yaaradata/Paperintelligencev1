"""Unit tests for affiliation judge reject exclusion + NSA regression."""

from __future__ import annotations

from paper_intelligence.adjudication.org_score import organisation_score
from paper_intelligence.author_affiliation.verify.judge_compare import compare_claims
from paper_intelligence.author_affiliation.verify.judge_effective import (
    compute_rejected_organisation_ids,
    effective_organisation_ids,
    filter_affiliation_rows,
)
from paper_intelligence.author_affiliation.verify.judge_llm import (
    _literal_supported,
    validate_judge_output,
)


def _claims(html_ids=None, html_names=None, oa_ids=None, oa_names=None, oa_status="pi_evidence"):
    return {
        "html": {"org_ids": html_ids or [], "org_names": html_names or []},
        "openalex": {
            "org_ids": oa_ids or [],
            "org_names": oa_names or [],
            "work_status": oa_status,
        },
    }


def test_exact_match_by_ids():
    c = compare_claims(_claims(html_ids=[1, 2], oa_ids=[2, 1]))
    assert c["compare_status"] == "exact_match"
    assert c["needs_judge"] is False


def test_disagreement_invokes_judge():
    c = compare_claims(_claims(html_ids=[1], oa_ids=[2], html_names=["a"], oa_names=["b"]))
    assert c["compare_status"] == "disagreement"
    assert c["needs_judge"] is True


def test_html_only_missing_oa_not_disagreement():
    c = compare_claims(
        _claims(html_ids=[1], html_names=["mit"], oa_status="work_zero_institutions")
    )
    assert c["compare_status"] == "html_only"
    assert c["needs_judge"] is False


def test_neither():
    c = compare_claims(_claims())
    assert c["compare_status"] == "neither"
    assert c["needs_judge"] is False


def test_validate_judge_html():
    ok, err, cleaned = validate_judge_output(
        {
            "decision": "HTML",
            "accepted_organisations": [
                {
                    "organisation_name": "MIT",
                    "existing_organisation_id": None,
                    "author_names": [],
                    "supporting_evidence": "Affiliation: MIT",
                }
            ],
            "reason": "HTML text names MIT",
            "unsupported_claims": ["OpenAlex Lab X"],
        }
    )
    assert ok and err == ""
    assert cleaned["decision"] == "HTML"


def test_validate_uncertain_clears_orgs():
    ok, err, cleaned = validate_judge_output(
        {
            "decision": "UNCERTAIN",
            "accepted_organisations": [
                {
                    "organisation_name": "Guess U",
                    "supporting_evidence": "none",
                }
            ],
            "reason": "unclear",
            "unsupported_claims": [],
        }
    )
    assert ok
    assert cleaned["accepted_organisations"] == []


def test_validate_rejects_bad_decision():
    ok, err, _ = validate_judge_output({"decision": "MAYBE", "accepted_organisations": []})
    assert not ok


def test_nsa_rejected_authority_not_in_effective_set():
    """Paper 2601.10511: judge rejects National Security Authority (174).

    Original HTML explicit_paper_affiliation rows must remain in storage, but
    the effective accepted set after adjudication must exclude 174.
    """
    authority = 174
    agency = 1362
    umd = 801
    compare = {
        "html_org_ids": [authority],
        "html_org_names": ["national security authority"],
        "oa_org_ids": [agency, umd],
        "oa_org_names": ["national security agency", "university of maryland, college park"],
    }
    accepted = [agency, umd]
    rejected = compute_rejected_organisation_ids(
        compare=compare,
        accepted_organisation_ids=accepted,
        unsupported_claims=["national security authority"],
        name_to_id={"national security authority": authority},
    )
    assert authority in rejected
    assert agency not in rejected
    assert umd not in rejected

    # Stored evidence (audit): Authority still present as HTML evidence.
    stored_rows = [
        {
            "organisation_id": authority,
            "canonical_name": "National Security Authority",
            "evidence_type": "explicit_paper_affiliation",
            "confidence": 0.637,
            "priority": 0,
            "is_org_of_interest": False,
        },
        {
            "organisation_id": agency,
            "canonical_name": "National Security Agency",
            "evidence_type": "llm_affiliation_judge",
            "confidence": 0.88,
            "priority": 0,
            "is_org_of_interest": False,
        },
        {
            "organisation_id": umd,
            "canonical_name": "University of Maryland, College Park",
            "evidence_type": "llm_affiliation_judge",
            "confidence": 0.88,
            "priority": 0,
            "is_org_of_interest": False,
        },
        {
            "organisation_id": agency,
            "canonical_name": "National Security Agency",
            "evidence_type": "openalex_paper_specific",
            "confidence": 0.85,
            "priority": 0,
            "is_org_of_interest": False,
        },
    ]

    # Without reject filter (old behaviour): Authority still accepted.
    before = effective_organisation_ids(stored_rows)
    assert authority in before

    # With judge rejection: Authority excluded; Agency + UMD remain.
    after = effective_organisation_ids(
        stored_rows,
        rejected_organisation_ids=rejected,
        decision="OPENALEX",
        judge_called=True,
    )
    assert authority not in after
    assert agency in after
    assert umd in after

    scored = organisation_score(
        stored_rows,
        rejected_organisation_ids=rejected,
        judge_decision="OPENALEX",
        judge_called=True,
    )
    assert scored["status"] == "resolved"
    assert scored["organisation_id"] != authority


def test_unevaluated_affiliation_not_suppressed():
    """Orgs the judge never saw must remain in the effective set."""
    rows = [
        {
            "organisation_id": 1,
            "canonical_name": "Rejected HTML Org",
            "evidence_type": "explicit_paper_affiliation",
            "confidence": 0.9,
            "priority": 0,
            "is_org_of_interest": False,
        },
        {
            "organisation_id": 99,
            "canonical_name": "Email Domain Org (unevaluated)",
            "evidence_type": "email_domain",
            "confidence": 0.9,
            "priority": 0,
            "is_org_of_interest": False,
        },
        {
            "organisation_id": 2,
            "canonical_name": "Accepted OA Org",
            "evidence_type": "llm_affiliation_judge",
            "confidence": 0.88,
            "priority": 0,
            "is_org_of_interest": False,
        },
    ]
    filtered = filter_affiliation_rows(
        rows,
        rejected_organisation_ids=[1],
        decision="OPENALEX",
        judge_called=True,
    )
    ids = {int(r["organisation_id"]) for r in filtered if r.get("organisation_id")}
    assert 1 not in ids
    assert 99 in ids
    assert 2 in ids


def test_uncertain_does_not_exclude():
    rows = [
        {
            "organisation_id": 174,
            "evidence_type": "explicit_paper_affiliation",
            "confidence": 0.7,
            "canonical_name": "X",
            "priority": 0,
            "is_org_of_interest": False,
        }
    ]
    filtered = filter_affiliation_rows(
        rows,
        rejected_organisation_ids=[174],
        decision="UNCERTAIN",
        judge_called=True,
    )
    assert len(filtered) == 1


def test_html_name_without_id_matches_oa_via_normalization():
    """HTML has usable text but no organisation_id; normalized name equals OA.

    Must be exact_match (no LLM), not treated as missing HTML evidence.
    """
    from paper_intelligence.author_affiliation.verify.judge_compare import (
        bridge_html_names_to_oa_ids,
        compare_claims,
        normalized_name_keys,
    )

    # Same org: HTML missing id, OA has id + name with country suffix.
    html_names = ["Massachusetts Institute of Technology"]
    oa_names = ["Massachusetts Institute of Technology, USA"]
    oa_ids = [42]
    bridged = bridge_html_names_to_oa_ids(html_names, oa_names, oa_ids)
    assert bridged == {42}

    claims = {
        "html": {
            "org_ids": [42],  # after collect_claims bridging
            "org_names": html_names,
        },
        "openalex": {
            "org_ids": [42],
            "org_names": oa_names,
            "work_status": "pi_evidence",
        },
    }
    c = compare_claims(claims)
    assert c["compare_status"] == "exact_match"
    assert c["needs_judge"] is False

    # Name-key agreement path when neither side has IDs yet (suffix stripped).
    claims2 = {
        "html": {"org_ids": [], "org_names": ["Stanford University, California"]},
        "openalex": {
            "org_ids": [],
            "org_names": ["Stanford University"],
            "work_status": "pi_evidence",
        },
    }
    c2 = compare_claims(claims2)
    assert c2["compare_status"] == "exact_match"
    assert c2["needs_judge"] is False

    # Usable HTML text with no id must NOT become "neither" / missing HTML.
    claims3 = {
        "html": {"org_ids": [], "org_names": ["Some Lab Without Id"]},
        "openalex": {
            "org_ids": [],
            "org_names": [],
            "work_status": "work_zero_institutions",
        },
    }
    c3 = compare_claims(claims3)
    assert c3["compare_status"] == "html_only"
    assert c3["needs_judge"] is False


def test_html_name_without_id_does_not_fuzzy_merge_different_orgs():
    from paper_intelligence.author_affiliation.verify.judge_compare import (
        bridge_html_names_to_oa_ids,
        compare_claims,
    )

    bridged = bridge_html_names_to_oa_ids(
        ["National Security Authority"],
        ["National Security Agency", "University of Maryland"],
        [1362, 801],
    )
    assert bridged == set()  # Authority ≠ Agency

    claims = {
        "html": {
            "org_ids": [],
            "org_names": ["national security authority"],
        },
        "openalex": {
            "org_ids": [1362],
            "org_names": ["national security agency"],
            "work_status": "pi_evidence",
        },
    }
    c = compare_claims(claims)
    assert c["compare_status"] == "disagreement"
    assert c["needs_judge"] is True


def test_empty_accept_does_not_wipe_affiliations():
    compare = {
        "html_org_ids": [1],
        "html_org_names": ["a"],
        "oa_org_ids": [2],
        "oa_org_names": ["b"],
    }
    assert (
        compute_rejected_organisation_ids(
            compare=compare,
            accepted_organisation_ids=[],
            decision="HTML",
        )
        == []
    )


def test_literal_support_requires_evidence():
    payload = {
        "html_affiliation_text": ["Note: National Security Agency", "University of Maryland"],
        "html_organisation_claims": {"org_names": ["national security authority"]},
        "openalex": {
            "organisation_claims": {
                "org_names": ["national security agency", "university of maryland, college park"]
            }
        },
    }
    assert _literal_supported(
        "National Security Agency",
        "Note: National Security Agency",
        payload,
    )
    assert not _literal_supported(
        "Invented Institute of Prestige",
        "because it is famous",
        payload,
    )
