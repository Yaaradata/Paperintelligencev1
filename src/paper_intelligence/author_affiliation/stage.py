"""Stage: affiliation — resolve paper authors to organisations from grounded evidence.

Evidence precedence follows policies/affiliation_resolution/v001.yaml. Every
tier writes append-only rows into paper_intelligence.paper_author_affiliations,
always via a paper_author_id; a bare paper→organisation link is never stored.
Unknown beats wrong: ambiguous evidence is preserved with organisation_id NULL
rather than guessed.
"""

from __future__ import annotations

import os
import re
from dataclasses import dataclass, field
from typing import Any, Iterable

from paper_intelligence.author_affiliation import extraction, repository
from paper_intelligence.author_affiliation.grounding import grounding_span, is_grounded, normalise
from paper_intelligence.author_affiliation.policy import (
    DEFAULT_POLICY_VERSION,
    policy_version as resolve_policy_version,
)
from paper_intelligence.common import Evidence, RunContext, StageResult
from paper_intelligence.db import connect
from paper_intelligence.external import arxiv_html as arxiv_html_client
from paper_intelligence.external import openalex as openalex_client
from paper_intelligence.external import ror as ror_client
from paper_intelligence.organisation_resolution import (
    add_alias,
    apply_watchlist,
    domain_of,
    find_or_create_organisation,
    find_organisation_by_alias,
    find_organisation_by_email_domain,
    find_organisation_by_name,
    get_organisation,
    is_public_email_domain,
    load_watchlist,
)

STAGE_NAME = "affiliation"
STAGE_NAME_FAST = "affiliation_fast"
STAGE_NAME_DEEP = "affiliation_deep"
STAGE_VERSION = "v002"
STAGE_VERSION_FAST = "v003"  # v003: arXiv HTML when OAI empty (still no ROR/OpenAlex)
STAGE_VERSION_DEEP = "v002"

EVIDENCE_EXPLICIT = "explicit_paper_affiliation"
EVIDENCE_EMAIL = "email_domain"
EVIDENCE_ROR = "ror_canonical_match"
EVIDENCE_OPENALEX = "openalex_paper_specific"
EVIDENCE_PROFILE = "author_profile_secondary"
EVIDENCE_OAI = "oai_author_affiliation"

# Evidence types affiliation_fast can produce (no ROR / OpenAlex). Used by the
# pre-quality notable-org router so deep-first rows still count when FAST also
# resolved them (stage_version alone was wrong after deep dedupe).
FAST_ROUTER_EVIDENCE_TYPES = (
    EVIDENCE_EXPLICIT,
    EVIDENCE_EMAIL,
    EVIDENCE_OAI,
)

SCOPE_AUTHOR = "author_specific"
SCOPE_PAPER = "paper_level_unassigned"
SCOPE_UNRESOLVED = "unresolved_raw"

OUTCOME_RESOLVED = "resolved"
OUTCOME_NO_EVIDENCE = "no_evidence_supplied"
OUTCOME_REVIEW = "review_required"

# A floor only: grounding, not ROR's own score or `chosen` flag, decides acceptance.
ROR_MIN_SCORE = float(os.getenv("PI_ROR_MIN_SCORE", "0.5"))
ROR_MAX_LOOKUPS = int(os.getenv("PI_ROR_MAX_LOOKUPS", "3"))
# Beyond this, a paper-level affiliation string says nothing useful about any
# individual author, so we record it as ambiguous instead of fanning it out.
MAX_AUTHORS_FOR_PAPER_LEVEL = int(os.getenv("PI_AFFILIATION_MAX_FANOUT", "50"))


def _authors_structured_from_paper(paper: dict[str, Any]) -> list[dict[str, Any]]:
    """Prefer OAI structured authors from enrichment_metadata, else raw_metadata."""
    enrichment = paper.get("enrichment_metadata") or {}
    if isinstance(enrichment, str):
        enrichment = {}
    oai = enrichment.get("oai_ingest") if isinstance(enrichment, dict) else None
    if isinstance(oai, dict) and oai.get("authors_structured"):
        return list(oai["authors_structured"])
    raw = paper.get("raw_metadata") or {}
    if isinstance(raw, dict) and raw.get("authors_structured"):
        return list(raw["authors_structured"])
    return []


def _merge_oai_affiliation_lines(
    affiliation_text: Any, authors_structured: list[dict[str, Any]]
) -> list[str]:
    """Combine existing affiliation_text with OAI per-author affiliations."""
    lines: list[str] = []
    seen: set[str] = set()

    def _add(value: str) -> None:
        text = " ".join(value.split())
        if not text:
            return
        key = text.casefold()
        if key in seen:
            return
        seen.add(key)
        lines.append(text if text.lower().startswith("affiliation") else f"Affiliation: {text}")

    if isinstance(affiliation_text, list):
        for entry in affiliation_text:
            if entry is not None:
                _add(str(entry))
    elif isinstance(affiliation_text, str) and affiliation_text.strip():
        _add(affiliation_text)

    for author in authors_structured:
        for aff in author.get("affiliations") or []:
            _add(str(aff))
    return lines


@dataclass
class _Row:
    paper_author_id: int
    organisation_id: int | None
    raw_affiliation: str | None
    relationship_scope: str
    evidence_type: str
    evidence_source: str
    evidence_value: str | None
    confidence: float


@dataclass
class _Context:
    conn: Any
    content_item_id: int
    run_context: RunContext
    authors: list[dict[str, Any]]
    evidence: extraction.ExtractedEvidence
    doi: str | None
    watchlist: Any
    affiliation_source: str = "paper_metadata.affiliation_text"
    email_source: str = "paper_metadata.extracted_emails"
    rows: list[_Row] = field(default_factory=list)
    resolved_authors: set[int] = field(default_factory=set)
    resolved_names: set[str] = field(default_factory=set)
    used_lines: set[str] = field(default_factory=set)
    tier_counts: dict[str, int] = field(default_factory=dict)
    external_calls: dict[str, int] = field(default_factory=dict)
    name_cache: dict[int, str | None] = field(default_factory=dict)

    @property
    def resolved(self) -> bool:
        return any(row.organisation_id is not None for row in self.rows)


class AffiliationStage:
    stage_name = STAGE_NAME
    stage_version = STAGE_VERSION

    def __init__(
        self,
        conn: Any | None = None,
        *,
        policy_version: str = DEFAULT_POLICY_VERSION,
        allow_ror: bool = True,
        allow_openalex: bool = True,
        enable_author_profile: bool = False,
        mode: str = "deep",
    ) -> None:
        if mode not in {"fast", "deep"}:
            raise ValueError(f"affiliation mode must be 'fast' or 'deep', got {mode!r}")
        self._conn = conn
        self._policy_version = resolve_policy_version(policy_version)
        self._mode = mode
        # FAST: OAI + local alias/domain + arXiv HTML (no ROR/OpenAlex).
        # DEEP: same plus ROR + OpenAlex after quality.
        if mode == "fast":
            self.stage_name = STAGE_NAME_FAST
            self.stage_version = STAGE_VERSION_FAST
            self._allow_ror = False
            self._allow_openalex = False
            self._allow_html = True
        else:
            self.stage_name = STAGE_NAME_DEEP
            self.stage_version = STAGE_VERSION_DEEP
            self._allow_ror = allow_ror
            self._allow_openalex = allow_openalex
            self._allow_html = True
        # Tier 5 is enrichment only and is off by default: an author profile
        # must never stand in for the paper's own affiliation.
        self._enable_author_profile = enable_author_profile

    # -- public API ---------------------------------------------------------

    def process(self, content_item_id: int, run_context: RunContext) -> StageResult:
        owns_conn = self._conn is None
        conn = self._conn or connect()
        try:
            return self._process(conn, content_item_id, run_context)
        except Exception as exc:  # noqa: BLE001 — stage boundary returns failed
            try:
                conn.rollback()
            except Exception:  # noqa: BLE001
                pass
            return StageResult(
                status="failed",
                data={"content_item_id": content_item_id},
                metadata={
                    "error_type": type(exc).__name__,
                    "error_message": str(exc),
                    "stage_name": self.stage_name,
                    "stage_version": self.stage_version,
                    "policy_version": self._policy_version,
                },
            )
        finally:
            if owns_conn:
                conn.close()

    # -- implementation -----------------------------------------------------

    def _process(self, conn: Any, content_item_id: int, run_context: RunContext) -> StageResult:
        paper = repository.fetch_paper(conn, content_item_id)
        authors = repository.list_paper_authors(conn, content_item_id)
        authors_structured = _authors_structured_from_paper(paper)
        affiliation_lines = _merge_oai_affiliation_lines(
            paper.get("affiliation_text"), authors_structured
        )

        evidence = extraction.extract(affiliation_lines, paper.get("extracted_emails"))
        doi = openalex_client.normalize_doi(paper.get("doi"))
        arxiv_id = (paper.get("arxiv_id") or "").strip() or None
        affiliation_source = (
            "oai.authors_structured+paper_metadata.affiliation_text"
            if authors_structured
            else "paper_metadata.affiliation_text"
        )
        email_source = "paper_metadata.extracted_emails"

        if not authors:
            # Every row must hang off a paper_author_id; without authors there
            # is nothing we are allowed to write.
            return self._result(
                "unresolved",
                content_item_id,
                OUTCOME_NO_EVIDENCE,
                reason="no_paper_authors",
                run_context=run_context,
            )

        # When local/OAI evidence is empty, pull arXiv HTML footnotes (fast+deep).
        # Fast still skips ROR/OpenAlex; HTML + watchlist/alias/domain only.
        if evidence.is_empty and self._allow_html and arxiv_id:
            page = arxiv_html_client.fetch_affiliations(
                arxiv_id,
                conn=conn,
                run_id=run_context.run_id,
                stage_run_id=run_context.stage_run_id,
                content_item_id=content_item_id,
            )
            if not page.error and (page.affiliations or page.emails):
                evidence = extraction.extract(page.affiliations, page.emails)
                affiliation_source = page.evidence_url or f"arxiv.html/{arxiv_id}"
                email_source = affiliation_source
            # OpenAlex indexes most arXiv papers under the DataCite DOI even
            # when paper_metadata.doi is null.
            if not doi:
                doi = openalex_client.normalize_doi(f"10.48550/arxiv.{arxiv_id}")

        if evidence.is_empty and not (doi and self._allow_openalex):
            return self._result(
                "unresolved",
                content_item_id,
                OUTCOME_NO_EVIDENCE,
                reason="no_affiliation_text_no_emails_no_doi",
                run_context=run_context,
                data={
                    "author_count": len(authors),
                    "arxiv_id": arxiv_id,
                    "mode": self._mode,
                },
            )

        ctx = _Context(
            conn=conn,
            content_item_id=content_item_id,
            run_context=run_context,
            authors=authors,
            evidence=evidence,
            doi=doi,
            watchlist=load_watchlist(),
            affiliation_source=affiliation_source,
            email_source=email_source,
        )

        self._tier1_explicit(ctx)
        self._tier2_email_domain(ctx)
        # ROR also runs when some lines already matched locally but others
        # remain (common with multi-footnote orgs: "Google Research" + "CMU").
        if self._allow_ror and (not ctx.resolved or self._unused_affiliation_lines(ctx)):
            self._tier3_ror(ctx)
        if not ctx.resolved and self._allow_openalex:
            self._tier4_openalex(ctx)
        if self._enable_author_profile:
            self._tier5_author_profile(ctx)
        # Tiers 3 and 4 store domain aliases for organisations they create, so
        # re-run the deterministic tier to consume what this pass just learned.
        # Without this a rerun would discover the same fact a pass later.
        self._tier2_email_domain(ctx)
        self._preserve_unresolved(ctx)

        if run_context.dry_run:
            conn.rollback()
            return self._result(
                "success" if ctx.resolved else "unresolved",
                content_item_id,
                OUTCOME_RESOLVED if ctx.resolved else OUTCOME_REVIEW,
                run_context=run_context,
                data={
                    "dry_run": True,
                    "author_count": len(authors),
                    "planned_rows": len(ctx.rows),
                    "tier_counts": ctx.tier_counts,
                },
            )

        written, skipped = self._write(ctx)
        conn.commit()

        resolved_rows = sum(1 for row in ctx.rows if row.organisation_id is not None)
        reason: str | None = None
        if resolved_rows:
            status, outcome = "success", OUTCOME_RESOLVED
        elif ctx.rows:
            # Evidence existed and is preserved, but nothing canonicalised.
            status, outcome = "unresolved", OUTCOME_REVIEW
        else:
            status, outcome = "unresolved", OUTCOME_NO_EVIDENCE
            reason = (
                "external_lookup_returned_no_affiliation"
                if ctx.external_calls
                else "no_usable_affiliation_text"
            )

        organisation_ids = sorted(
            {row.organisation_id for row in ctx.rows if row.organisation_id is not None}
        )
        return self._result(
            status,
            content_item_id,
            outcome,
            run_context=run_context,
            reason=reason,
            data={
                "author_count": len(authors),
                "rows_written": written,
                "rows_deduped": skipped,
                "rows_total": len(ctx.rows),
                "resolved_rows": resolved_rows,
                "unresolved_rows": len(ctx.rows) - resolved_rows,
                "organisation_ids": organisation_ids,
                "tier_counts": ctx.tier_counts,
                "external_calls": ctx.external_calls,
            },
            evidence=[
                Evidence(
                    evidence_type=row.evidence_type,
                    evidence_source=row.evidence_source,
                    evidence_value=row.evidence_value,
                    confidence=row.confidence,
                    metadata={
                        "paper_author_id": row.paper_author_id,
                        "organisation_id": row.organisation_id,
                        "relationship_scope": row.relationship_scope,
                    },
                )
                for row in ctx.rows
            ],
        )

    # -- tiers --------------------------------------------------------------

    def _tier1_explicit(self, ctx: _Context) -> None:
        """Paper's own affiliation text, canonicalised only against what we already know."""
        for line in ctx.evidence.lines:
            for candidate in line.candidates:
                organisation_id = find_organisation_by_name(ctx.conn, candidate)
                if organisation_id is None:
                    organisation_id = find_organisation_by_alias(ctx.conn, candidate)
                if organisation_id is None:
                    # Watchlist aliases (e.g. "FAIR at Meta") may not yet be in
                    # organisation_aliases; resolve via canonical watchlist name.
                    entry = ctx.watchlist.match(candidate)
                    if entry is not None:
                        organisation_id = find_organisation_by_name(
                            ctx.conn, entry.canonical_name
                        )
                        if organisation_id is not None and candidate.casefold() != (
                            entry.canonical_name or ""
                        ).casefold():
                            add_alias(
                                ctx.conn,
                                organisation_id,
                                candidate,
                                "name",
                                confidence=1.0,
                            )
                if organisation_id is None:
                    continue
                name = self._canonical_name(ctx, organisation_id) or candidate
                if not is_grounded(name, line.raw) and not is_grounded(candidate, line.raw):
                    continue
                apply_watchlist(ctx.conn, organisation_id, name, watchlist=ctx.watchlist)
                self._emit_paper_level(
                    ctx,
                    organisation_id=organisation_id,
                    raw=line.raw,
                    evidence_type=EVIDENCE_EXPLICIT,
                    evidence_source=ctx.affiliation_source,
                    evidence_value=grounding_span(candidate, line.raw) or candidate,
                    base_confidence=0.85,
                )
                ctx.used_lines.add(line.raw)

    def _emit_explicit_backing(
        self,
        ctx: _Context,
        organisation_id: int,
        candidate: str,
        line: extraction.AffiliationLine,
    ) -> None:
        """Record the tier-1 fact that the paper itself named this organisation.

        A later tier only supplied the canonicalisation. Writing both rows now
        means a rerun — where tier 1 finds the newly stored organisation and
        never reaches the later tier — produces exactly the same evidence set.
        """
        self._emit_paper_level(
            ctx,
            organisation_id=organisation_id,
            raw=line.raw,
            evidence_type=EVIDENCE_EXPLICIT,
            evidence_source=ctx.affiliation_source,
            evidence_value=grounding_span(candidate, line.raw) or candidate,
            base_confidence=0.85,
        )

    def _tier2_email_domain(self, ctx: _Context) -> None:
        """Deterministic email-domain match against existing 'domain' aliases."""
        seen: set[str] = set()
        for email in ctx.evidence.emails:
            domain = domain_of(email)
            if not domain or domain in seen or is_public_email_domain(domain):
                continue
            seen.add(domain)
            organisation_id = find_organisation_by_email_domain(ctx.conn, domain)
            if organisation_id is None:
                continue
            author = self._author_for_email(ctx, email)
            if author is not None:
                self._emit(
                    ctx,
                    _Row(
                        paper_author_id=author["id"],
                        organisation_id=organisation_id,
                        raw_affiliation=email,
                        relationship_scope=SCOPE_AUTHOR,
                        evidence_type=EVIDENCE_EMAIL,
                        evidence_source=ctx.email_source,
                        evidence_value=domain,
                        confidence=0.9,
                    ),
                )
            else:
                self._emit_paper_level(
                    ctx,
                    organisation_id=organisation_id,
                    raw=email,
                    evidence_type=EVIDENCE_EMAIL,
                    evidence_source=ctx.email_source,
                    evidence_value=domain,
                    base_confidence=0.75,
                )

        for domain in extraction.institutional_domains(ctx.evidence):
            if domain in seen:
                continue
            seen.add(domain)
            organisation_id = find_organisation_by_email_domain(ctx.conn, domain)
            if organisation_id is not None:
                self._emit_paper_level(
                    ctx,
                    organisation_id=organisation_id,
                    raw=domain,
                    evidence_type=EVIDENCE_EMAIL,
                    evidence_source=ctx.affiliation_source,
                    evidence_value=domain,
                    base_confidence=0.75,
                )

    def _unused_affiliation_lines(self, ctx: _Context) -> bool:
        return any(line.raw not in ctx.used_lines for line in ctx.evidence.lines)

    def _tier3_ror(self, ctx: _Context) -> None:
        """Canonical ROR match for affiliation lines not yet resolved locally."""
        lookups = 0
        for line in ctx.evidence.lines:
            if line.raw in ctx.used_lines:
                continue
            for candidate in line.candidates:
                if lookups >= ROR_MAX_LOOKUPS:
                    return
                lookups += 1
                ctx.external_calls["ror"] = ctx.external_calls.get("ror", 0) + 1
                response = ror_client.resolve_affiliation(
                    candidate,
                    conn=ctx.conn,
                    run_id=ctx.run_context.run_id,
                    stage_run_id=ctx.run_context.stage_run_id,
                    content_item_id=ctx.content_item_id,
                )
                if response.error:
                    continue
                chosen = self._choose_ror_match(response.matches, line.raw, candidate)
                if chosen is None:
                    continue
                organisation, span, confidence = chosen
                organisation_id = find_or_create_organisation(
                    ctx.conn,
                    organisation["name"],
                    ror_id=organisation.get("ror_id"),
                    country_code=organisation.get("country_code"),
                    organisation_type=organisation.get("type"),
                    metadata={"source": "ror", "matched_query": candidate},
                    watchlist=ctx.watchlist,
                )
                for alias in organisation.get("aliases") or []:
                    add_alias(ctx.conn, organisation_id, alias, "name", confidence=0.9)
                for acronym in organisation.get("acronyms") or []:
                    add_alias(ctx.conn, organisation_id, acronym, "abbreviation", confidence=0.9)
                for link in organisation.get("domains") or []:
                    add_alias(ctx.conn, organisation_id, link, "domain", confidence=0.9)
                self._emit_paper_level(
                    ctx,
                    organisation_id=organisation_id,
                    raw=line.raw,
                    evidence_type=EVIDENCE_ROR,
                    evidence_source="ror.organizations.affiliation",
                    evidence_value=span,
                    base_confidence=confidence,
                )
                self._emit_explicit_backing(ctx, organisation_id, candidate, line)
                ctx.used_lines.add(line.raw)
                break

    def _tier4_openalex(self, ctx: _Context) -> None:
        """Paper-specific authorship institutions via DOI. Never the author profile."""
        if not ctx.doi:
            return
        ctx.external_calls["openalex"] = ctx.external_calls.get("openalex", 0) + 1
        work = openalex_client.get_work(
            ctx.doi,
            conn=ctx.conn,
            run_id=ctx.run_context.run_id,
            stage_run_id=ctx.run_context.stage_run_id,
            content_item_id=ctx.content_item_id,
        )
        if work.error or not work.work:
            return
        for pair in openalex_client.authorship_institutions(work.work):
            name = pair["institution_name"]
            supplied = " ; ".join(
                [*(pair.get("raw_affiliation_strings") or []), *(l.raw for l in ctx.evidence.lines)]
            )
            grounded = is_grounded(name, supplied)
            if not grounded and not pair.get("ror_id"):
                continue
            organisation_id = find_or_create_organisation(
                ctx.conn,
                name,
                ror_id=_ror_id(pair.get("ror_id")),
                openalex_id=pair.get("openalex_institution_id"),
                country_code=pair.get("country_code"),
                organisation_type=pair.get("institution_type"),
                metadata={"source": "openalex", "doi": ctx.doi},
                watchlist=ctx.watchlist,
            )
            for line in ctx.evidence.lines:
                if any(normalise(c) == normalise(name) for c in line.candidates):
                    self._emit_explicit_backing(ctx, organisation_id, name, line)
                    ctx.used_lines.add(line.raw)

            author = self._author_by_name(ctx, pair.get("author_name"))
            evidence_value = (
                grounding_span(name, supplied) if grounded else name
            ) or name
            if author is not None:
                self._emit(
                    ctx,
                    _Row(
                        paper_author_id=author["id"],
                        organisation_id=organisation_id,
                        raw_affiliation=(pair.get("raw_affiliation_strings") or [None])[0] or name,
                        relationship_scope=SCOPE_AUTHOR,
                        evidence_type=EVIDENCE_OPENALEX,
                        evidence_source="openalex.works.authorships",
                        evidence_value=evidence_value,
                        confidence=0.85 if grounded else 0.7,
                    ),
                )
            else:
                self._emit_paper_level(
                    ctx,
                    organisation_id=organisation_id,
                    raw=(pair.get("raw_affiliation_strings") or [None])[0] or name,
                    evidence_type=EVIDENCE_OPENALEX,
                    evidence_source="openalex.works.authorships",
                    evidence_value=evidence_value,
                    # OpenAlex asserts the institution for this paper; only the
                    # author it belongs to is uncertain.
                    base_confidence=0.8 if grounded else 0.6,
                )

    def _tier5_author_profile(self, ctx: _Context) -> None:
        """Secondary enrichment hook. Author-profile evidence may only be attached
        to authors that already carry paper-specific evidence, so it can never
        become the paper affiliation on its own. v001 fetches no profiles."""
        ctx.tier_counts.setdefault(EVIDENCE_PROFILE, 0)

    def _preserve_unresolved(self, ctx: _Context) -> None:
        """Never discard extracted evidence: keep the raw text with organisation_id NULL."""
        for line in ctx.evidence.lines:
            if line.raw in ctx.used_lines:
                continue
            if any(is_grounded(name, line.raw) for name in ctx.resolved_names):
                continue
            self._emit_paper_level(
                ctx,
                organisation_id=None,
                raw=line.raw,
                evidence_type=EVIDENCE_EXPLICIT,
                evidence_source=ctx.affiliation_source,
                evidence_value=(line.candidates[0] if line.candidates else line.raw)[:500],
                base_confidence=0.5,
                scope=SCOPE_UNRESOLVED,
            )

    # -- helpers ------------------------------------------------------------

    def _choose_ror_match(
        self, matches: Iterable[dict[str, Any]], raw_line: str, candidate: str
    ) -> tuple[dict[str, Any], str, float] | None:
        """Acceptance policy for ROR candidates.

        Grounding decides, not ROR's ranking: the live affiliation matcher
        happily returns `chosen: true` for unrelated organisations. We take the
        candidate whose canonical name has the longest literal match in the
        evidence, and fall back to an alias or acronym that literally names it.
        """
        best_name: tuple[dict[str, Any], str, float] | None = None
        best_alias: tuple[dict[str, Any], str, float] | None = None
        for item in matches or []:
            payload = _ror_organisation(item.get("organization") or {})
            name = payload["name"]
            score = float(item.get("score") or 0.0)
            if not name or score < ROR_MIN_SCORE:
                continue
            if _is_less_specific(name, candidate):
                continue
            span = grounding_span(name, raw_line) or grounding_span(name, candidate)
            if span:
                confidence = min(0.85, 0.6 + 0.25 * score)
                if best_name is None or len(span) > len(best_name[1]):
                    best_name = (payload, span, confidence)
                continue
            if best_alias is None:
                for alias in [*payload["aliases"], *payload["acronyms"]]:
                    alias_span = grounding_span(alias, raw_line) or grounding_span(alias, candidate)
                    if alias_span:
                        best_alias = (payload, alias_span, 0.6)
                        break
        return best_name or best_alias

    def _emit_paper_level(
        self,
        ctx: _Context,
        *,
        organisation_id: int | None,
        raw: str | None,
        evidence_type: str,
        evidence_source: str,
        evidence_value: str | None,
        base_confidence: float,
        scope: str | None = None,
    ) -> None:
        """Attach paper-level evidence to every author, or flag it as too ambiguous."""
        if len(ctx.authors) > MAX_AUTHORS_FOR_PAPER_LEVEL:
            ctx.tier_counts["skipped_fanout"] = ctx.tier_counts.get("skipped_fanout", 0) + 1
            return
        single = len(ctx.authors) == 1
        # relationship_scope still records author↔org ambiguity on multi-author papers.
        # confidence answers a different question: "is this organisation represented
        # on the paper?" — do not discount that merely because fan-out is unassigned.
        # (Discounting 0.75 * 0.75 pushed email-domain rows to 0.562, below the
        # adjudication MIN_CONFIDENCE floor, while NVIDIA/@nvidia.com is strong.)
        confidence = float(base_confidence)
        if organisation_id is None and not single:
            # Unresolved raw lines keep a mild ambiguity discount; resolved org
            # attribution does not.
            confidence = round(base_confidence * 0.75, 3)
        effective_scope = scope or (SCOPE_AUTHOR if single else SCOPE_PAPER)
        for author in ctx.authors:
            self._emit(
                ctx,
                _Row(
                    paper_author_id=author["id"],
                    organisation_id=organisation_id,
                    raw_affiliation=raw,
                    relationship_scope=effective_scope,
                    evidence_type=evidence_type,
                    evidence_source=evidence_source,
                    evidence_value=evidence_value,
                    confidence=confidence,
                ),
            )

    def _emit(self, ctx: _Context, row: _Row) -> None:
        key = (
            row.paper_author_id,
            row.organisation_id,
            row.evidence_type,
            row.evidence_value,
        )
        if any(
            (r.paper_author_id, r.organisation_id, r.evidence_type, r.evidence_value) == key
            for r in ctx.rows
        ):
            return
        ctx.rows.append(row)
        if row.organisation_id is not None:
            name = self._canonical_name(ctx, row.organisation_id)
            if name:
                ctx.resolved_names.add(name)
            ctx.tier_counts[row.evidence_type] = ctx.tier_counts.get(row.evidence_type, 0) + 1
            if row.relationship_scope == SCOPE_AUTHOR:
                ctx.resolved_authors.add(row.paper_author_id)
        else:
            ctx.tier_counts["unresolved_raw"] = ctx.tier_counts.get("unresolved_raw", 0) + 1

    def _write(self, ctx: _Context) -> tuple[int, int]:
        written = 0
        skipped = 0
        for row in ctx.rows:
            row_id = repository.insert_affiliation(
                ctx.conn,
                content_item_id=ctx.content_item_id,
                paper_author_id=row.paper_author_id,
                organisation_id=row.organisation_id,
                raw_affiliation=row.raw_affiliation,
                relationship_scope=row.relationship_scope,
                evidence_type=row.evidence_type,
                evidence_source=row.evidence_source,
                evidence_value=row.evidence_value,
                confidence=row.confidence,
                run_id=ctx.run_context.run_id,
                stage_version=self.stage_version,
                policy_version=self._policy_version,
            )
            if row_id is None:
                skipped += 1
            else:
                written += 1
        return written, skipped

    def _canonical_name(self, ctx: _Context, organisation_id: int) -> str | None:
        if organisation_id not in ctx.name_cache:
            organisation = get_organisation(ctx.conn, organisation_id)
            ctx.name_cache[organisation_id] = (
                organisation["canonical_name"] if organisation else None
            )
        return ctx.name_cache[organisation_id]

    def _author_for_email(self, ctx: _Context, email: str) -> dict[str, Any] | None:
        """Attach an email to an author only when the local part clearly names them."""
        local = email.split("@", 1)[0]
        tokens = {t for t in re.split(r"[._\-+0-9]+", local.casefold()) if len(t) > 2}
        if not tokens:
            return None
        for author in ctx.authors:
            name_tokens = set(normalise(author.get("normalized_name") or author["raw_name"]).split())
            if tokens and tokens.issubset(name_tokens):
                return author
        return None

    def _author_by_name(self, ctx: _Context, name: str | None) -> dict[str, Any] | None:
        """Match an external author name to a paper_authors row.

        OpenAlex writes `Surname, Given` where our rows hold `Given Surname`,
        and some upstream rows carry mojibake, so both are compared across
        several equivalent spellings.
        """
        if not name:
            return None
        target_forms = _name_forms(name)
        if not target_forms:
            return None
        for author in ctx.authors:
            stored = author.get("normalized_name") or author["raw_name"]
            if target_forms & _name_forms(stored):
                return author

        target_keys = {key for key in (_surname_key(form) for form in target_forms) if key}
        matches = [
            author
            for author in ctx.authors
            if target_keys
            & {
                key
                for key in (
                    _surname_key(form)
                    for form in _name_forms(author.get("normalized_name") or author["raw_name"])
                )
                if key
            }
        ]
        return matches[0] if len(matches) == 1 else None

    def _result(
        self,
        status: str,
        content_item_id: int,
        outcome: str,
        *,
        run_context: RunContext,
        reason: str | None = None,
        data: dict[str, Any] | None = None,
        evidence: list[Evidence] | None = None,
    ) -> StageResult:
        payload: dict[str, Any] = {"content_item_id": content_item_id, "outcome": outcome}
        if reason:
            payload["reason"] = reason
        payload.update(data or {})
        return StageResult(
            status=status,  # type: ignore[arg-type]
            data=payload,
            evidence=evidence or [],
            metadata={
                "stage_name": self.stage_name,
                "stage_version": self.stage_version,
                "policy_version": self._policy_version,
                "run_id": run_context.run_id,
                "stage_run_id": run_context.stage_run_id,
                "code_commit_sha": run_context.code_commit_sha,
            },
        )


_NAME_STOPWORDS = frozenset({"the", "a", "an"})


def _is_less_specific(name: str, candidate: str) -> bool:
    """True when the candidate names a more specific organisation than `name`.

    `American International University` must not resolve to ROR's
    `International University`: the name is grounded only because it is a
    fragment of the one the paper actually gives.
    """
    name_tokens = normalise(name).split()
    candidate_tokens = normalise(candidate).split()
    if not name_tokens or len(name_tokens) >= len(candidate_tokens):
        return False
    for start in range(len(candidate_tokens) - len(name_tokens) + 1):
        if candidate_tokens[start : start + len(name_tokens)] != name_tokens:
            continue
        extra = candidate_tokens[:start] + candidate_tokens[start + len(name_tokens) :]
        return any(token not in _NAME_STOPWORDS for token in extra)
    return False


def _ror_organisation(organisation: dict[str, Any]) -> dict[str, Any]:
    """Flatten a ROR organisation record. Handles both v1 (`name`) and v2 (`names`)."""
    names = organisation.get("names")
    display = organisation.get("name")
    aliases: list[str] = list(organisation.get("aliases") or [])
    acronyms: list[str] = list(organisation.get("acronyms") or [])
    if isinstance(names, list):
        labels: list[str] = []
        for entry in names:
            if not isinstance(entry, dict) or not entry.get("value"):
                continue
            types = entry.get("types") or []
            if "ror_display" in types:
                display = entry["value"]
            elif "acronym" in types:
                acronyms.append(entry["value"])
            elif "alias" in types:
                aliases.append(entry["value"])
            else:
                labels.append(entry["value"])
        if not display and labels:
            display = labels[0]
        aliases.extend(label for label in labels if label != display)

    country_code = (organisation.get("country") or {}).get("country_code")
    if not country_code:
        for location in organisation.get("locations") or []:
            details = (location or {}).get("geonames_details") or {}
            if details.get("country_code"):
                country_code = details["country_code"]
                break

    return {
        "name": display,
        "ror_id": organisation.get("id"),
        "country_code": country_code,
        "type": (organisation.get("types") or [None])[0],
        "aliases": aliases,
        "acronyms": acronyms,
        "domains": organisation.get("domains") or [],
    }


def _surname_key(name: str) -> tuple[str, str] | None:
    parts = normalise(name).split()
    if len(parts) < 2:
        return None
    return parts[-1], parts[0][0]


def _repair_mojibake(text: str) -> str | None:
    """Undo UTF-8 bytes that were decoded as cp1252/Latin-1 upstream (`PekÃ¡r` → `Pekár`)."""
    for encoding in ("cp1252", "latin-1"):
        try:
            repaired = text.encode(encoding).decode("utf-8")
        except (UnicodeEncodeError, UnicodeDecodeError):
            continue
        if repaired != text:
            return repaired
    return None


def _name_forms(name: str) -> set[str]:
    """Normalised spellings a person's name may appear under."""
    forms: set[str] = set()
    for variant in (name, _repair_mojibake(name)):
        if not variant:
            continue
        cleaned = normalise(variant)
        if not cleaned:
            continue
        forms.add(cleaned)
        if "," in variant:
            surname, _, given = variant.partition(",")
            swapped = normalise(f"{given} {surname}")
            if swapped:
                forms.add(swapped)
    return forms


def _ror_id(value: str | None) -> str | None:
    return value.strip() if value else None
