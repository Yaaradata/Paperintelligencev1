"""Unit tests for organisation coverage validation helpers (no network/DB)."""

from __future__ import annotations

from datetime import date

import pytest

from paper_intelligence.evaluation.org_coverage import (
    AffilRow,
    OpenAlexPaperResult,
    PaperRecord,
    classify_disagreement,
    compute_denominators,
    compute_window_metrics,
    dedupe_organisation_ids,
    extract_openalex_institutions,
    openalex_lookup_identifier,
    organisation_canonical_key,
    paper_in_window,
    window_start,
)


def test_window_boundaries_inclusive():
    until = date(2026, 8, 23)
    assert window_start(until, 7) == date(2026, 8, 17)
    assert window_start(until, 1) == until
    assert paper_in_window(date(2026, 8, 17), until, 7)
    assert paper_in_window(date(2026, 8, 23), until, 7)
    assert not paper_in_window(date(2026, 8, 16), until, 7)
    assert not paper_in_window(date(2026, 8, 24), until, 7)


def test_dedupe_organisation_ids_ignores_null_and_duplicates():
    assert dedupe_organisation_ids([1, 1, None, 2, 2, None, 3]) == {1, 2, 3}
    assert dedupe_organisation_ids([]) == set()


def test_canonical_key_prefers_ror_then_openalex_then_name():
    assert organisation_canonical_key(
        ror_id="https://ror.org/00f54p054",
        openalex_id="https://openalex.org/I123",
        name="Meta",
    ) == "ror:00f54p054"
    assert organisation_canonical_key(
        openalex_id="https://openalex.org/I999",
        name="Meta",
    ) == "openalex:I999"
    assert organisation_canonical_key(name="  Stanford University ") == "name:stanford university"
    assert organisation_canonical_key() is None


def test_extract_openalex_institutions_dedupes_author_rows():
    work = {
        "authorships": [
            {
                "author": {"display_name": "A", "id": "https://openalex.org/A1"},
                "institutions": [
                    {
                        "display_name": "Stanford University",
                        "ror": "https://ror.org/00f54p054",
                        "id": "https://openalex.org/I1",
                    }
                ],
            },
            {
                "author": {"display_name": "B", "id": "https://openalex.org/A2"},
                "institutions": [
                    {
                        "display_name": "Stanford University",
                        "ror": "https://ror.org/00f54p054",
                        "id": "https://openalex.org/I1",
                    },
                    {
                        "display_name": "Meta",
                        "ror": None,
                        "id": "https://openalex.org/I2",
                    },
                ],
            },
        ]
    }
    institutions = extract_openalex_institutions(work)
    keys = {i["canonical_key"] for i in institutions}
    assert keys == {"ror:00f54p054", "openalex:I2"}
    assert len(institutions) == 2


def test_ror_and_openalex_id_matching_across_sources():
    ours = {"ror:00f54p054", "openalex:I2"}
    oa = {
        organisation_canonical_key(ror_id="https://ror.org/00f54p054"),
        organisation_canonical_key(openalex_id="https://openalex.org/I2"),
    }
    assert classify_disagreement(ours, oa) == "exact_set_match"
    assert classify_disagreement({"ror:1"}, {"ror:2"}) == "both_disagree"
    assert classify_disagreement({"ror:1", "ror:2"}, {"ror:2", "ror:3"}) == "overlap"


def test_disagreement_classification_matrix():
    assert classify_disagreement(set(), set()) == "both_empty"
    assert classify_disagreement({"a"}, set()) == "ours_only"
    assert classify_disagreement(set(), {"a"}) == "openalex_only"
    assert classify_disagreement({"a"}, {"a"}) == "exact_set_match"
    assert classify_disagreement({"a", "b"}, {"b", "c"}) == "overlap"
    assert classify_disagreement({"a"}, {"b"}) == "both_disagree"


def test_denominator_calculations_explicit_and_null_safe():
    rates = compute_denominators(
        total_arxiv_papers=100,
        papers_with_accepted_org=25,
        openalex_matched=80,
        openalex_matched_with_institution=40,
        matched_with_common_org=10,
        matched_either_has_org=50,
    )
    assert rates["ours_org_coverage"] == pytest.approx(0.25)
    assert rates["ours_org_coverage_denominator"] == "total_arxiv_papers"
    assert rates["openalex_org_coverage"] == pytest.approx(0.5)
    assert rates["openalex_org_coverage_denominator"] == "openalex_matched_papers"
    assert rates["agreement_rate"] == pytest.approx(0.2)
    empty = compute_denominators(
        total_arxiv_papers=0,
        papers_with_accepted_org=0,
        openalex_matched=0,
        openalex_matched_with_institution=0,
        matched_with_common_org=0,
        matched_either_has_org=0,
    )
    assert empty["ours_org_coverage"] is None
    assert empty["openalex_org_coverage"] is None
    assert empty["agreement_rate"] is None


def test_openalex_lookup_prefers_doi_then_arxiv_datacite():
    doi_id, strategy = openalex_lookup_identifier("https://doi.org/10.1234/abc", "2608.00001")
    assert strategy == "doi"
    assert doi_id == "10.1234/abc"
    arxiv_id, strategy = openalex_lookup_identifier(None, "2608.00001")
    assert strategy == "arxiv_datacite_doi"
    assert arxiv_id == "10.48550/arxiv.2608.00001"
    none_id, strategy = openalex_lookup_identifier(None, None)
    assert none_id is None and strategy == "none"


def test_window_metrics_do_not_inflate_duplicate_author_org_rows():
    until = date(2026, 8, 23)
    papers = [
        PaperRecord(
            content_item_id=1,
            title="t",
            status="RELEVANT",
            published_on=date(2026, 8, 23),
            arxiv_id="2608.00001",
            doi=None,
        )
    ]
    # Three author rows for the same organisation must count as one org.
    affiliations = {
        1: [
            AffilRow(
                content_item_id=1,
                organisation_id=10,
                evidence_type="email_domain",
                evidence_source="paper_metadata.extracted_emails",
                evidence_value="nvidia.com",
                confidence=0.75,
                stage_version="v002",
                canonical_name="NVIDIA",
                ror_id=None,
                openalex_id="I10",
                is_org_of_interest=True,
                priority=10,
            ),
            AffilRow(
                content_item_id=1,
                organisation_id=10,
                evidence_type="email_domain",
                evidence_source="paper_metadata.extracted_emails",
                evidence_value="nvidia.com",
                confidence=0.75,
                stage_version="v002",
                canonical_name="NVIDIA",
                ror_id=None,
                openalex_id="I10",
                is_org_of_interest=True,
                priority=10,
            ),
            AffilRow(
                content_item_id=1,
                organisation_id=10,
                evidence_type="email_domain",
                evidence_source="paper_metadata.extracted_emails",
                evidence_value="nvidia.com",
                confidence=0.75,
                stage_version="v002",
                canonical_name="NVIDIA",
                ror_id=None,
                openalex_id="I10",
                is_org_of_interest=True,
                priority=10,
            ),
        ]
    }
    openalex = {
        1: OpenAlexPaperResult(
            content_item_id=1,
            match_status="matched",
            match_strategy="arxiv_datacite_doi",
            institutions=[
                {
                    "canonical_key": "openalex:I10",
                    "institution_name": "NVIDIA",
                    "ror_id": None,
                    "openalex_institution_id": "I10",
                }
            ],
        )
    }
    metrics = compute_window_metrics(
        papers,
        affiliations,
        openalex,
        days=7,
        date_until=until,
    )
    assert metrics["internal"]["unique_canonical_organisations"] == 1
    assert metrics["internal"]["paper_organisation_pairs"] == 1
    assert metrics["internal"]["avg_organisations_per_affiliated_paper"] == 1.0
    assert metrics["openalex_agreement"]["exact_set_match_count"] == 1
