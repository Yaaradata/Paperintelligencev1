"""Affiliation stage unit tests. No live API calls: HTTP and DB are stubbed."""

from __future__ import annotations

import itertools
from typing import Any

import pytest

from paper_intelligence.author_affiliation import extraction
from paper_intelligence.author_affiliation.grounding import is_grounded
from paper_intelligence.author_affiliation.stage import (
    EVIDENCE_EMAIL,
    EVIDENCE_EXPLICIT,
    EVIDENCE_ROR,
    OUTCOME_NO_EVIDENCE,
    OUTCOME_RESOLVED,
    OUTCOME_REVIEW,
    AffiliationStage,
)
from paper_intelligence.common import RunContext
from paper_intelligence.external import openalex, ror


# ---------------------------------------------------------------------------
# Fakes
# ---------------------------------------------------------------------------


class FakeDB:
    """In-memory stand-in for the three tables the stage touches."""

    def __init__(
        self,
        *,
        paper: dict[str, Any],
        authors: list[dict[str, Any]],
        organisations: list[dict[str, Any]] | None = None,
        aliases: list[dict[str, Any]] | None = None,
    ) -> None:
        self.paper = paper
        self.authors = authors
        self.organisations = organisations or []
        self.aliases = aliases or []
        self.affiliations: list[dict[str, Any]] = []
        self.committed = 0
        self._ids = itertools.count(1000)

    # psycopg-ish surface -------------------------------------------------
    def cursor(self) -> "FakeCursor":
        return FakeCursor(self)

    def commit(self) -> None:
        self.committed += 1

    def rollback(self) -> None:
        pass

    def close(self) -> None:
        pass

    # helpers -------------------------------------------------------------
    def add_organisation(self, name: str, **kwargs: Any) -> int:
        organisation_id = next(self._ids)
        self.organisations.append(
            {
                "id": organisation_id,
                "canonical_name": name,
                "ror_id": kwargs.get("ror_id"),
                "openalex_id": kwargs.get("openalex_id"),
                "country_code": kwargs.get("country_code"),
                "organisation_type": kwargs.get("organisation_type"),
                "priority": kwargs.get("priority", 0),
                "is_org_of_interest": kwargs.get("is_org_of_interest", False),
                "metadata": {},
            }
        )
        self.aliases.append(
            {"organisation_id": organisation_id, "alias": name, "alias_type": "name"}
        )
        return organisation_id

    def add_domain(self, organisation_id: int, domain: str) -> None:
        self.aliases.append(
            {"organisation_id": organisation_id, "alias": domain, "alias_type": "domain"}
        )


class FakeCursor:
    def __init__(self, db: FakeDB) -> None:
        self.db = db
        self._rows: list[dict[str, Any]] = []

    def __enter__(self) -> "FakeCursor":
        return self

    def __exit__(self, *exc: Any) -> None:
        return None

    def execute(self, sql: str, params: Any = ()) -> None:
        text = " ".join(sql.split())
        params = params or ()
        if "FROM research_radar.content_items" in text and "paper_metadata" in text:
            self._rows = [self.db.paper]
        elif "FROM paper_intelligence.paper_authors" in text:
            self._rows = list(self.db.authors)
        elif "SELECT * FROM paper_intelligence.organisations" in text:
            self._rows = [o for o in self.db.organisations if o["id"] == params[0]]
        elif "FROM paper_intelligence.organisations" in text and "ror_id = " in text:
            self._rows = [o for o in self.db.organisations if o["ror_id"] == params[0]]
        elif "FROM paper_intelligence.organisations" in text and "openalex_id = " in text:
            self._rows = [o for o in self.db.organisations if o["openalex_id"] == params[0]]
        elif "lower(canonical_name)" in text:
            target = str(params[0]).lower()
            self._rows = [
                o for o in self.db.organisations if o["canonical_name"].lower() == target
            ]
        elif "FROM paper_intelligence.organisation_aliases" in text:
            alias, alias_type = str(params[0]).lower(), params[1]
            self._rows = [
                a
                for a in self.db.aliases
                if a["alias"].lower() == alias
                and (alias_type is None or a["alias_type"] == alias_type)
            ]
        elif "INSERT INTO paper_intelligence.organisation_aliases" in text:
            organisation_id, alias, alias_type, _confidence = params
            if not any(
                a["organisation_id"] == organisation_id
                and a["alias"] == alias
                and a["alias_type"] == alias_type
                for a in self.db.aliases
            ):
                self.db.aliases.append(
                    {"organisation_id": organisation_id, "alias": alias, "alias_type": alias_type}
                )
            self._rows = []
        elif "INSERT INTO paper_intelligence.organisations" in text:
            name, org_type, country, ror_id, openalex_id, _metadata = params
            organisation_id = self.db.add_organisation(
                name,
                organisation_type=org_type,
                country_code=country,
                ror_id=ror_id,
                openalex_id=openalex_id,
            )
            self._rows = [{"id": organisation_id}]
        elif "UPDATE paper_intelligence.organisations" in text:
            self._rows = []
        elif "SELECT 1 FROM paper_intelligence.paper_author_affiliations" in text:
            content_item_id, paper_author_id, organisation_id, etype, evalue = params
            self._rows = [
                {"?column?": 1}
                for row in self.db.affiliations
                if (
                    row["content_item_id"] == content_item_id
                    and row["paper_author_id"] == paper_author_id
                    and row["organisation_id"] == organisation_id
                    and row["evidence_type"] == etype
                    and row["evidence_value"] == evalue
                )
            ][:1]
        elif "INSERT INTO paper_intelligence.paper_author_affiliations" in text:
            keys = [
                "content_item_id",
                "paper_author_id",
                "organisation_id",
                "raw_affiliation",
                "relationship_scope",
                "evidence_type",
                "evidence_source",
                "evidence_value",
                "confidence",
                "run_id",
                "stage_version",
                "policy_version",
            ]
            row = dict(zip(keys, params))
            row["id"] = next(self.db._ids)
            self.db.affiliations.append(row)
            self._rows = [{"id": row["id"]}]
        else:  # pragma: no cover - guards against silently ignored SQL
            raise AssertionError(f"unexpected SQL in test: {text[:120]}")

    def fetchone(self) -> dict[str, Any] | None:
        return self._rows[0] if self._rows else None

    def fetchall(self) -> list[dict[str, Any]]:
        return list(self._rows)


def make_paper(**overrides: Any) -> dict[str, Any]:
    paper = {
        "content_item_id": 1,
        "title": "A paper",
        "doi": None,
        "arxiv_id": "2608.00001",
        "affiliation_text": [],
        "extracted_emails": [],
        "raw_metadata": {},
        "enrichment_metadata": {},
    }
    paper.update(overrides)
    return paper


def make_authors(*names: str) -> list[dict[str, Any]]:
    return [
        {
            "id": 10 + index,
            "author_position": index + 1,
            "raw_name": name,
            "normalized_name": name,
            "openalex_author_id": None,
            "orcid": None,
        }
        for index, name in enumerate(names)
    ]


RUN = RunContext(run_id="00000000-0000-0000-0000-000000000001", stage_run_id="sr-1")


@pytest.fixture(autouse=True)
def no_network(monkeypatch: pytest.MonkeyPatch) -> None:
    """Any unstubbed HTTP call is a test failure, not a live request."""

    def explode(*args: Any, **kwargs: Any) -> None:
        raise AssertionError("unit tests must not perform HTTP requests")

    monkeypatch.setattr(ror.requests, "get", explode)
    monkeypatch.setattr(openalex.requests, "get", explode)
    monkeypatch.setattr(
        "paper_intelligence.author_affiliation.stage.arxiv_html_client.fetch_affiliations",
        lambda *a, **k: type(
            "Page",
            (),
            {"error": "disabled_in_tests", "affiliations": [], "emails": [], "evidence_url": None},
        )(),
    )


# ---------------------------------------------------------------------------
# Grounding
# ---------------------------------------------------------------------------


PARAPHRASED = (
    "The experiments described here were carried out by the team at "
    "Stanford University during the 2026 academic year."
)


def test_grounding_accepts_paraphrased_sentence_containing_org_name() -> None:
    assert is_grounded("Stanford University", PARAPHRASED)


def test_grounding_rejects_org_name_absent_from_evidence() -> None:
    assert not is_grounded("Google DeepMind", PARAPHRASED)


def test_grounding_ignores_punctuation_and_case_but_not_missing_words() -> None:
    assert is_grounded("stanford university", "Affiliation: Stanford University, CA, USA")
    assert not is_grounded("Stanford Medicine", "Affiliation: Stanford University, CA, USA")


def test_grounding_requires_whole_token_not_prefix() -> None:
    assert not is_grounded("Open University", "Affiliation: OpenUniversity Press")


# ---------------------------------------------------------------------------
# Outcomes
# ---------------------------------------------------------------------------


def test_no_evidence_supplied_when_nothing_to_work_with() -> None:
    db = FakeDB(paper=make_paper(), authors=make_authors("Ada Lovelace"))
    result = AffiliationStage(db).process(1, RUN)

    assert result.status == "unresolved"
    assert result.data["outcome"] == OUTCOME_NO_EVIDENCE
    assert db.affiliations == []


def test_fast_mode_uses_oai_structured_affiliation_without_html(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """FAST affiliation resolves local/OAI evidence and never calls HTML/ROR/OpenAlex."""
    html_calls: list[str] = []

    def mark_html(*args: Any, **kwargs: Any) -> Any:
        html_calls.append("called")
        raise AssertionError("FAST mode must not fetch arXiv HTML")

    monkeypatch.setattr(
        "paper_intelligence.author_affiliation.stage.arxiv_html_client.fetch_affiliations",
        mark_html,
    )
    monkeypatch.setattr(
        "paper_intelligence.author_affiliation.stage.load_watchlist",
        lambda: type(
            "W",
            (),
            {
                "match": lambda *a, **k: None,
                "entries": [],
            },
        )(),
    )

    db = FakeDB(
        paper=make_paper(
            affiliation_text=[],
            enrichment_metadata={
                "oai_ingest": {
                    "authors_structured": [
                        {
                            "position": 1,
                            "name": "Ada Lovelace",
                            "affiliations": ["Stanford University"],
                        }
                    ]
                }
            },
        ),
        authors=make_authors("Ada Lovelace"),
    )
    stanford = db.add_organisation(
        "Stanford University", priority=8, is_org_of_interest=True
    )
    db.aliases.append(
        {"organisation_id": stanford, "alias": "Stanford University", "alias_type": "name"}
    )

    result = AffiliationStage(db, mode="fast").process(1, RUN)
    assert html_calls == []
    assert result.status == "success"
    assert result.data["outcome"] == OUTCOME_RESOLVED
    assert any(row["organisation_id"] == stanford for row in db.affiliations)


def test_review_required_is_distinct_from_no_evidence_supplied() -> None:
    db = FakeDB(
        paper=make_paper(affiliation_text=["Affiliation: Independent Researchers"]),
        authors=make_authors("Ada Lovelace"),
    )
    result = AffiliationStage(db, allow_ror=False, allow_openalex=False).process(1, RUN)

    assert result.status == "unresolved"
    assert result.data["outcome"] == OUTCOME_REVIEW
    assert result.data["outcome"] != OUTCOME_NO_EVIDENCE
    # The evidence still exists in the table, with no organisation attached.
    assert len(db.affiliations) == 1
    assert db.affiliations[0]["organisation_id"] is None
    assert "Independent Researchers" in db.affiliations[0]["raw_affiliation"]


# ---------------------------------------------------------------------------
# Unlisted organisations are preserved
# ---------------------------------------------------------------------------


def test_unlisted_organisation_is_stored_not_discarded(monkeypatch: pytest.MonkeyPatch) -> None:
    """An org that matches nothing on the watchlist is still created and linked."""
    db = FakeDB(
        paper=make_paper(
            affiliation_text=["Affiliation: Department of Physics, Obscure University, Freedonia"]
        ),
        authors=make_authors("Ada Lovelace"),
    )

    def fake_ror(raw: str, **kwargs: Any) -> ror.RorResponse:
        return ror.RorResponse(
            query=raw,
            matches=[
                {
                    "score": 1.0,
                    "chosen": True,
                    "organization": {
                        "id": "https://ror.org/0zzzzzz99",
                        "name": "Obscure University",
                        "country": {"country_code": "FD"},
                        "types": ["Education"],
                    },
                }
            ],
        )

    monkeypatch.setattr(
        "paper_intelligence.author_affiliation.stage.ror_client.resolve_affiliation", fake_ror
    )

    result = AffiliationStage(db, allow_openalex=False).process(1, RUN)

    assert result.status == "success"
    assert result.data["outcome"] == OUTCOME_RESOLVED
    stored = [row for row in db.affiliations if row["organisation_id"] is not None]
    # Two facts about the same link: the paper named it, and ROR canonicalised it.
    assert {row["evidence_type"] for row in stored} == {EVIDENCE_ROR, EVIDENCE_EXPLICIT}
    assert len({row["organisation_id"] for row in stored}) == 1

    organisation = next(o for o in db.organisations if o["id"] == stored[0]["organisation_id"])
    assert organisation["canonical_name"] == "Obscure University"
    assert organisation["is_org_of_interest"] is False  # unlisted, but stored


def test_ror_v2_names_array_is_understood(monkeypatch: pytest.MonkeyPatch) -> None:
    """The live API serves schema v2: display name in `names`, country in `locations`."""
    db = FakeDB(
        paper=make_paper(affiliation_text=["Affiliation: University of Bamberg, Germany"]),
        authors=make_authors("Sebastian Doerrich"),
    )

    def fake_ror(raw: str, **kwargs: Any) -> ror.RorResponse:
        return ror.RorResponse(
            query=raw,
            matches=[
                {
                    "score": 1.0,
                    "chosen": True,
                    "organization": {
                        "id": "https://ror.org/01c1w6d29",
                        "domains": ["uni-bamberg.de"],
                        "types": ["education"],
                        "names": [
                            {"value": "Otto-Friedrich-Universität Bamberg", "types": ["label"]},
                            {"value": "University of Bamberg", "types": ["ror_display", "label"]},
                            {"value": "UBA", "types": ["acronym"]},
                        ],
                        "locations": [{"geonames_details": {"country_code": "DE"}}],
                    },
                }
            ],
        )

    monkeypatch.setattr(
        "paper_intelligence.author_affiliation.stage.ror_client.resolve_affiliation", fake_ror
    )

    result = AffiliationStage(db, allow_openalex=False).process(1, RUN)

    assert result.status == "success"
    assert len(db.organisations) == 1
    organisation = db.organisations[0]
    assert organisation["canonical_name"] == "University of Bamberg"
    assert organisation["ror_id"] == "https://ror.org/01c1w6d29"
    assert organisation["country_code"] == "DE"
    # The ROR domain becomes a reusable deterministic alias for later papers.
    assert {"organisation_id": organisation["id"], "alias": "uni-bamberg.de", "alias_type": "domain"} in db.aliases
    assert {"organisation_id": organisation["id"], "alias": "UBA", "alias_type": "abbreviation"} in db.aliases


def test_ungrounded_ror_match_is_rejected(monkeypatch: pytest.MonkeyPatch) -> None:
    """Unknown beats wrong: ROR's name must literally appear in the evidence.

    The live matcher really does return `chosen: true` for unrelated orgs, so
    ROR's own ranking is never sufficient on its own.
    """
    db = FakeDB(
        paper=make_paper(affiliation_text=["Affiliation: Obscure University, Freedonia"]),
        authors=make_authors("Ada Lovelace"),
    )

    def fake_ror(raw: str, **kwargs: Any) -> ror.RorResponse:
        return ror.RorResponse(
            query=raw,
            matches=[
                {
                    "score": 1.0,
                    "chosen": True,
                    "organization": {
                        "id": "https://ror.org/01an7q238",
                        "name": "University of California, Berkeley",
                    },
                }
            ],
        )

    monkeypatch.setattr(
        "paper_intelligence.author_affiliation.stage.ror_client.resolve_affiliation", fake_ror
    )

    result = AffiliationStage(db, allow_openalex=False).process(1, RUN)

    assert result.status == "unresolved"
    assert result.data["outcome"] == OUTCOME_REVIEW
    assert all(row["organisation_id"] is None for row in db.affiliations)
    assert not any(o["canonical_name"].startswith("University of California") for o in db.organisations)


# ---------------------------------------------------------------------------
# Deterministic tiers
# ---------------------------------------------------------------------------


def test_ror_grounding_beats_ror_ranking(monkeypatch: pytest.MonkeyPatch) -> None:
    """The top-ranked match loses to a lower-ranked one that is actually grounded."""
    db = FakeDB(
        paper=make_paper(
            affiliation_text=["Affiliation: Department of Mathematics, Purdue University, IN, USA"]
        ),
        authors=make_authors("Alex Gracyk"),
    )

    def fake_ror(raw: str, **kwargs: Any) -> ror.RorResponse:
        return ror.RorResponse(
            query=raw,
            matches=[
                {
                    "score": 0.96,
                    "chosen": True,
                    "organization": {
                        "id": "https://ror.org/04bm3wy68",
                        "name": "Hue University of Education",
                    },
                },
                {
                    "score": 0.80,
                    "chosen": False,
                    "organization": {
                        "id": "https://ror.org/02dqehb95",
                        "name": "Purdue University",
                    },
                },
            ],
        )

    monkeypatch.setattr(
        "paper_intelligence.author_affiliation.stage.ror_client.resolve_affiliation", fake_ror
    )

    result = AffiliationStage(db, allow_openalex=False).process(1, RUN)

    assert result.status == "success"
    resolved = [row for row in db.affiliations if row["organisation_id"] is not None]
    organisation = next(
        o for o in db.organisations if o["id"] == resolved[0]["organisation_id"]
    )
    assert organisation["canonical_name"] == "Purdue University"


def test_openalex_authorship_matches_reversed_and_mojibake_names(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """OpenAlex writes `Surname, Given`; upstream rows sometimes carry mojibake."""
    db = FakeDB(
        paper=make_paper(doi="10.1016/j.cmpb.2026.109614"),
        # 'PekÃ¡r' is how 'Pekár' arrives when UTF-8 was decoded as Latin-1.
        authors=make_authors("Mat\u00c4\u203aj Pek\u00c3\u00a1r", "Petr Holub"),
    )

    def fake_work(identifier: str, **kwargs: Any) -> openalex.OpenAlexWork:
        return openalex.OpenAlexWork(
            identifier=identifier,
            work={
                "authorships": [
                    {
                        "raw_author_name": "Pekár, Matěj",
                        "author": {"display_name": "Matěj Pekár"},
                        "institutions": [
                            {
                                "display_name": "Masaryk University",
                                "ror": "https://ror.org/02j46qs45",
                                "country_code": "CZ",
                            }
                        ],
                        "raw_affiliation_strings": ["Masaryk University, Brno"],
                    }
                ]
            },
        )

    monkeypatch.setattr(
        "paper_intelligence.author_affiliation.stage.openalex_client.get_work", fake_work
    )

    result = AffiliationStage(db, allow_ror=False).process(1, RUN)

    assert result.status == "success"
    row = db.affiliations[0]
    assert row["relationship_scope"] == "author_specific"
    assert row["paper_author_id"] == db.authors[0]["id"]


def test_ror_match_that_is_only_a_fragment_of_the_name_is_rejected(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """`American International University` must not become `International University`."""
    db = FakeDB(
        paper=make_paper(
            affiliation_text=["Affiliation: American International University - Bangladesh"]
        ),
        authors=make_authors("Ada Lovelace"),
    )

    def fake_ror(raw: str, **kwargs: Any) -> ror.RorResponse:
        return ror.RorResponse(
            query=raw,
            matches=[
                {
                    "score": 0.95,
                    "chosen": True,
                    "organization": {
                        "id": "https://ror.org/02knr1992",
                        "name": "International University",
                    },
                }
            ],
        )

    monkeypatch.setattr(
        "paper_intelligence.author_affiliation.stage.ror_client.resolve_affiliation", fake_ror
    )

    result = AffiliationStage(db, allow_openalex=False).process(1, RUN)

    assert result.status == "unresolved"
    assert result.data["outcome"] == OUTCOME_REVIEW
    assert db.organisations == []
    assert all(row["organisation_id"] is None for row in db.affiliations)


def test_leading_article_does_not_block_a_ror_match(monkeypatch: pytest.MonkeyPatch) -> None:
    """`The University of Manchester` still matches ROR's `University of Manchester`."""
    db = FakeDB(
        paper=make_paper(affiliation_text=["Affiliation: The University of Manchester, UK"]),
        authors=make_authors("Ada Lovelace"),
    )

    def fake_ror(raw: str, **kwargs: Any) -> ror.RorResponse:
        return ror.RorResponse(
            query=raw,
            matches=[
                {
                    "score": 0.95,
                    "chosen": True,
                    "organization": {
                        "id": "https://ror.org/027m9bs27",
                        "name": "University of Manchester",
                    },
                }
            ],
        )

    monkeypatch.setattr(
        "paper_intelligence.author_affiliation.stage.ror_client.resolve_affiliation", fake_ror
    )

    result = AffiliationStage(db, allow_openalex=False).process(1, RUN)

    assert result.status == "success"
    assert db.organisations[0]["canonical_name"] == "University of Manchester"


def test_email_domain_deterministic_match() -> None:
    db = FakeDB(
        paper=make_paper(
            affiliation_text=["Email: mahir.tamim@northsouth.edu"],
            extracted_emails=["mahir.tamim@northsouth.edu"],
        ),
        authors=make_authors("Mahir Tamim"),
    )
    organisation_id = db.add_organisation("North South University")
    db.add_domain(organisation_id, "northsouth.edu")

    result = AffiliationStage(db, allow_ror=False, allow_openalex=False).process(1, RUN)

    assert result.status == "success"
    row = next(r for r in db.affiliations if r["organisation_id"] == organisation_id)
    assert row["evidence_type"] == EVIDENCE_EMAIL
    assert row["evidence_value"] == "northsouth.edu"
    assert row["relationship_scope"] == "author_specific"
    assert row["paper_author_id"] == db.authors[0]["id"]


def test_public_email_domain_is_never_used_as_an_organisation() -> None:
    db = FakeDB(
        paper=make_paper(extracted_emails=["ada@gmail.com"]),
        authors=make_authors("Ada Lovelace"),
    )
    organisation_id = db.add_organisation("Gmail Inc")
    db.add_domain(organisation_id, "gmail.com")

    result = AffiliationStage(db, allow_ror=False, allow_openalex=False).process(1, RUN)

    assert result.status == "unresolved"
    assert all(row["organisation_id"] is None for row in db.affiliations)


def test_known_alias_resolves_without_any_external_call() -> None:
    db = FakeDB(
        paper=make_paper(affiliation_text=["Affiliation: Stanford University, CA, USA"]),
        authors=make_authors("Ada Lovelace"),
    )
    organisation_id = db.add_organisation("Stanford University")

    # allow_ror stays on: tier 3 must not be reached, and the autouse fixture
    # would turn any real HTTP into a failure.
    result = AffiliationStage(db, allow_openalex=False).process(1, RUN)

    assert result.status == "success"
    assert result.data["tier_counts"].get(EVIDENCE_EXPLICIT) == 1
    assert result.data["external_calls"] == {}
    assert db.affiliations[0]["organisation_id"] == organisation_id


def test_rows_always_hang_off_a_paper_author() -> None:
    db = FakeDB(
        paper=make_paper(affiliation_text=["Affiliation: Stanford University, CA, USA"]),
        authors=make_authors("Ada Lovelace", "Grace Hopper"),
    )
    db.add_organisation("Stanford University")

    AffiliationStage(db, allow_ror=False, allow_openalex=False).process(1, RUN)

    author_ids = {a["id"] for a in db.authors}
    assert db.affiliations
    assert all(row["paper_author_id"] in author_ids for row in db.affiliations)
    # Paper-level evidence with several authors is marked as unassigned.
    assert all(row["relationship_scope"] == "paper_level_unassigned" for row in db.affiliations)


def test_reprocessing_is_idempotent() -> None:
    db = FakeDB(
        paper=make_paper(affiliation_text=["Affiliation: Stanford University, CA, USA"]),
        authors=make_authors("Ada Lovelace", "Grace Hopper"),
    )
    db.add_organisation("Stanford University")
    stage = AffiliationStage(db, allow_ror=False, allow_openalex=False)

    first = stage.process(1, RUN)
    count_after_first = len(db.affiliations)
    second = stage.process(1, RUN)

    assert first.data["rows_written"] == count_after_first
    assert second.data["rows_written"] == 0
    assert second.data["rows_deduped"] == count_after_first
    assert len(db.affiliations) == count_after_first


def test_rerun_after_ror_resolution_adds_nothing(monkeypatch: pytest.MonkeyPatch) -> None:
    """The second pass finds the org locally and must reach the same evidence set.

    Without recording the tier-1 fact on the first pass, the rerun would take a
    cheaper route and append a new row for a conclusion already stored.
    """
    db = FakeDB(
        paper=make_paper(
            affiliation_text=["Affiliation: Obscure University, Freedonia"],
            extracted_emails=["a.scholar@obscure.fd"],
        ),
        authors=make_authors("Ada Lovelace", "Grace Hopper"),
    )
    calls: list[str] = []

    def fake_ror(raw: str, **kwargs: Any) -> ror.RorResponse:
        calls.append(raw)
        return ror.RorResponse(
            query=raw,
            matches=[
                {
                    "score": 1.0,
                    "chosen": True,
                    "organization": {
                        "id": "https://ror.org/0zzzzzz99",
                        "name": "Obscure University",
                        "domains": ["obscure.fd"],
                    },
                }
            ],
        )

    monkeypatch.setattr(
        "paper_intelligence.author_affiliation.stage.ror_client.resolve_affiliation", fake_ror
    )
    stage = AffiliationStage(db, allow_openalex=False)

    first = stage.process(1, RUN)
    after_first = len(db.affiliations)
    second = stage.process(1, RUN)

    assert first.status == "success"
    assert second.data["rows_written"] == 0
    assert len(db.affiliations) == after_first
    assert len(calls) == 1  # the second pass needs no external lookup at all


# ---------------------------------------------------------------------------
# External clients: cache and logging
# ---------------------------------------------------------------------------


def test_ror_cache_hit_avoids_http(monkeypatch: pytest.MonkeyPatch, tmp_path: Any) -> None:
    payload = {"items": [{"score": 1.0, "chosen": True, "organization": {"name": "Cached Org"}}]}
    cached = tmp_path / "cached.json.gz"

    monkeypatch.setattr(ror, "find_cached", lambda provider, req_hash: cached)
    monkeypatch.setattr(ror, "read_cached", lambda path: payload)

    def explode(*args: Any, **kwargs: Any) -> None:
        raise AssertionError("cache hit must not reach the network")

    monkeypatch.setattr(ror.requests, "get", explode)

    response = ror.resolve_affiliation("Cached Org, Nowhere")

    assert response.error is None
    assert response.matches == payload["items"]
    assert response.raw_ref == str(cached)


def test_openalex_cache_hit_avoids_http(monkeypatch: pytest.MonkeyPatch, tmp_path: Any) -> None:
    payload = {"id": "https://openalex.org/W1", "authorships": []}
    cached = tmp_path / "work.json.gz"

    monkeypatch.setattr(openalex, "find_cached", lambda provider, req_hash: cached)
    monkeypatch.setattr(openalex, "read_cached", lambda path: payload)

    def explode(*args: Any, **kwargs: Any) -> None:
        raise AssertionError("cache hit must not reach the network")

    monkeypatch.setattr(openalex.requests, "get", explode)

    work = openalex.get_work("10.1234/abcd")

    assert work.error is None
    assert work.work == payload
    assert work.raw_ref == str(cached)


def test_external_clients_report_errors_instead_of_raising(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(ror, "find_cached", lambda provider, req_hash: None)
    monkeypatch.setattr(ror, "MAX_RETRIES", 1)
    monkeypatch.setattr(ror, "REQUEST_SLEEP", 0.0)
    monkeypatch.setattr(
        ror.requests, "get", lambda *a, **k: (_ for _ in ()).throw(OSError("boom"))
    )

    response = ror.resolve_affiliation("Somewhere")

    assert response.matches == []
    assert response.error and "boom" in response.error


def test_openalex_builds_doi_and_id_paths() -> None:
    assert openalex._path_for("10.1234/abcd") == "works/doi:10.1234%2Fabcd"
    assert openalex._path_for("https://doi.org/10.1234/AbCd") == "works/doi:10.1234%2Fabcd"
    assert openalex._path_for("https://openalex.org/W123") == "works/W123"


# ---------------------------------------------------------------------------
# Extraction
# ---------------------------------------------------------------------------


def test_extraction_reads_labels_orgs_and_emails() -> None:
    evidence = extraction.extract(
        [
            "Affiliation: Asian Institute of Digital Finance, National University of Singapore",
            "Affiliation: {yaoxuan, koreydai}@nus.edu.sg",
            "Corresponding author: Corresponding author",
        ],
        [],
    )
    candidates = [c for line in evidence.lines for c in line.candidates]

    assert "National University of Singapore" in candidates
    assert "Asian Institute of Digital Finance" in candidates
    # `{a, b}@nus.edu.sg` is not a parseable email but the domain is still usable.
    assert evidence.emails == []
    assert extraction.institutional_domains(evidence) == ["nus.edu.sg"]


def test_extraction_drops_sub_units_but_keeps_the_institution() -> None:
    candidates = extraction.organisation_candidates(
        "Department of Electrical and Computer Engineering, North South University, Dhaka, Bangladesh"
    )
    assert candidates == ["North South University"]
