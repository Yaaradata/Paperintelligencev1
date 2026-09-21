"""Organisation extraction coverage vs OpenAlex (evaluation only).

Observational: does not mutate affiliation rows, scoring, or adjudication.
OpenAlex responses go through the existing raw cache / external_requests path.
"""

from __future__ import annotations

import csv
import json
import statistics
import time
from collections import Counter, defaultdict
from dataclasses import asdict, dataclass, field
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Iterable, Sequence

from paper_intelligence.adjudication.org_score import MIN_CONFIDENCE
from paper_intelligence.common.config import PI_USE_PAPERS_CATALOG
from paper_intelligence.external import openalex as openalex_client

STAGE_NAME = "org_coverage_validation"
STAGE_VERSION = "v001"
OPENALEX_UNMATCHED = "OPENALEX_UNMATCHED"

# Inclusive window: date_until − (days−1) … date_until
DEFAULT_WINDOWS = (7, 15, 31)


# ---------------------------------------------------------------------------
# Canonical keys + pure helpers (unit-tested)
# ---------------------------------------------------------------------------


def normalize_ror_id(value: str | None) -> str | None:
    if not value:
        return None
    text = str(value).strip()
    if not text:
        return None
    text = text.rstrip("/")
    if "ror.org/" in text:
        text = text.rsplit("ror.org/", 1)[-1]
    return text or None


def normalize_openalex_id(value: str | None) -> str | None:
    if not value:
        return None
    text = str(value).strip()
    if not text:
        return None
    text = text.rstrip("/")
    if "/" in text:
        text = text.rsplit("/", 1)[-1]
    return text or None


def organisation_canonical_key(
    *,
    ror_id: str | None = None,
    openalex_id: str | None = None,
    name: str | None = None,
) -> str | None:
    """Stable cross-source key. Prefer ROR, then OpenAlex institution id, then name."""
    ror = normalize_ror_id(ror_id)
    if ror:
        return f"ror:{ror}"
    oa = normalize_openalex_id(openalex_id)
    if oa:
        return f"openalex:{oa}"
    cleaned = " ".join((name or "").casefold().split())
    if cleaned:
        return f"name:{cleaned}"
    return None


def dedupe_organisation_ids(organisation_ids: Iterable[int | None]) -> set[int]:
    """Unique non-null organisation_ids (duplicate author rows must not inflate)."""
    return {int(oid) for oid in organisation_ids if oid is not None}


def window_start(date_until: date, days: int) -> date:
    if days < 1:
        raise ValueError(f"window days must be >= 1, got {days}")
    return date_until - timedelta(days=days - 1)


def paper_in_window(published_on: date, date_until: date, days: int) -> bool:
    start = window_start(date_until, days)
    return start <= published_on <= date_until


def classify_evidence_bucket(evidence_type: str | None, evidence_source: str | None) -> str:
    et = (evidence_type or "").strip().lower()
    es = (evidence_source or "").strip().lower()
    if et == "email_domain":
        return "email_domain"
    if et in {"ror_canonical_match", "ror_match"}:
        return "ror"
    if et in {"openalex_paper_specific", "openalex_authorship"}:
        return "openalex"
    if "oai.authors_structured" in es:
        return "oai"
    if es.startswith("arxiv.html") or "/html/" in es or "arxiv.org/html" in es:
        return "arxiv_html"
    if et in {"explicit_paper_affiliation", "paper_affiliation", "alias_match"}:
        return "local_watchlist_alias"
    return "other"


def infer_fast_deep_source(evidence_types: Sequence[str], evidence_sources: Sequence[str]) -> str:
    """Best-effort FAST/DEEP label from stored evidence (not item_stage_runs)."""
    deep_types = {"ror_canonical_match", "ror_match", "openalex_paper_specific", "openalex_authorship"}
    for et, es in zip(evidence_types, evidence_sources):
        bucket = classify_evidence_bucket(et, es)
        if bucket in {"ror", "openalex", "arxiv_html"} or (et or "").lower() in deep_types:
            return "deep"
    if evidence_types or evidence_sources:
        return "fast"
    return "unknown"


def extract_openalex_institutions(work: dict[str, Any]) -> list[dict[str, Any]]:
    """Unique institutions on a Work (dedupe by ROR / OpenAlex id / name)."""
    seen: set[str] = set()
    out: list[dict[str, Any]] = []
    for pair in openalex_client.authorship_institutions(work or {}):
        key = organisation_canonical_key(
            ror_id=pair.get("ror_id"),
            openalex_id=pair.get("openalex_institution_id"),
            name=pair.get("institution_name"),
        )
        if not key or key in seen:
            continue
        seen.add(key)
        out.append(
            {
                "canonical_key": key,
                "institution_name": pair.get("institution_name"),
                "ror_id": normalize_ror_id(pair.get("ror_id")),
                "openalex_institution_id": normalize_openalex_id(
                    pair.get("openalex_institution_id")
                ),
                "country_code": pair.get("country_code"),
                "institution_type": pair.get("institution_type"),
            }
        )
    return out


def classify_disagreement(
    ours_keys: set[str],
    oa_keys: set[str],
) -> str:
    """Return one of: exact_set_match | overlap | ours_only | openalex_only | both_disagree | both_empty."""
    if not ours_keys and not oa_keys:
        return "both_empty"
    if ours_keys and not oa_keys:
        return "ours_only"
    if oa_keys and not ours_keys:
        return "openalex_only"
    if ours_keys == oa_keys:
        return "exact_set_match"
    if ours_keys & oa_keys:
        return "overlap"
    return "both_disagree"


def compute_denominators(
    *,
    total_arxiv_papers: int,
    papers_with_accepted_org: int,
    openalex_matched: int,
    openalex_matched_with_institution: int,
    matched_with_common_org: int,
    matched_either_has_org: int,
) -> dict[str, float | None]:
    """Explicit rates; None when denominator is zero (do not invent 0%)."""

    def ratio(num: int, den: int) -> float | None:
        if den <= 0:
            return None
        return round(num / den, 6)

    return {
        "ours_org_coverage": ratio(papers_with_accepted_org, total_arxiv_papers),
        "ours_org_coverage_denominator": "total_arxiv_papers",
        "openalex_org_coverage": ratio(openalex_matched_with_institution, openalex_matched),
        "openalex_org_coverage_denominator": "openalex_matched_papers",
        "openalex_match_rate": ratio(openalex_matched, total_arxiv_papers),
        "openalex_match_rate_denominator": "total_arxiv_papers",
        "agreement_rate": ratio(matched_with_common_org, matched_either_has_org),
        "agreement_rate_denominator": "matched_papers_where_either_side_has_org",
    }


def openalex_lookup_identifier(doi: str | None, arxiv_id: str | None) -> tuple[str | None, str]:
    """Strongest deterministic identifier. Returns (identifier, strategy)."""
    normalized = openalex_client.normalize_doi(doi)
    if normalized:
        return normalized, "doi"
    aid = (arxiv_id or "").strip()
    if aid:
        # OpenAlex indexes most arXiv papers under the DataCite DOI.
        synthetic = openalex_client.normalize_doi(f"10.48550/arxiv.{aid}")
        if synthetic:
            return synthetic, "arxiv_datacite_doi"
    return None, "none"


# ---------------------------------------------------------------------------
# Data loading
# ---------------------------------------------------------------------------


PAPERS_SQL_RADAR = """
SELECT
    ci.id AS content_item_id,
    ci.title,
    ci.status,
    ci.published_at::date AS published_on,
    pm.arxiv_id,
    pm.doi
FROM research_radar.content_items ci
JOIN research_radar.paper_metadata pm ON pm.content_id = ci.id
WHERE ci.published_at >= %s::timestamptz
  AND ci.published_at < (%s::timestamptz + interval '1 day')
  AND pm.arxiv_id IS NOT NULL
ORDER BY ci.id
"""

PAPERS_SQL_PI = """
SELECT
    p.paper_id AS content_item_id,
    p.title,
    COALESCE(lr.decision, NULL) AS status,
    p.published_at::date AS published_on,
    p.arxiv_id,
    p.doi
FROM paper_intelligence.papers p
LEFT JOIN LATERAL (
  SELECT decision
  FROM paper_intelligence.paper_relevance_results r
  WHERE r.paper_id = p.paper_id
  ORDER BY r.created_at DESC, r.relevance_id DESC
  LIMIT 1
) lr ON TRUE
WHERE p.published_at >= %s::timestamptz
  AND p.published_at < (%s::timestamptz + interval '1 day')
  AND p.arxiv_id IS NOT NULL
ORDER BY p.paper_id
"""

PAPERS_SQL = PAPERS_SQL_RADAR

AFFILIATIONS_SQL = """
SELECT
    a.content_item_id,
    a.organisation_id,
    a.evidence_type,
    a.evidence_source,
    a.evidence_value,
    a.confidence,
    a.stage_version,
    o.canonical_name,
    o.ror_id,
    o.openalex_id,
    o.is_org_of_interest,
    o.priority
FROM paper_intelligence.paper_author_affiliations a
LEFT JOIN paper_intelligence.organisations o ON o.id = a.organisation_id
WHERE a.content_item_id = ANY(%s)
ORDER BY a.content_item_id, a.id
"""


@dataclass
class PaperRecord:
    content_item_id: int
    title: str | None
    status: str | None
    published_on: date
    arxiv_id: str | None
    doi: str | None


@dataclass
class AffilRow:
    content_item_id: int
    organisation_id: int | None
    evidence_type: str | None
    evidence_source: str | None
    evidence_value: str | None
    confidence: float | None
    stage_version: str | None
    canonical_name: str | None
    ror_id: str | None
    openalex_id: str | None
    is_org_of_interest: bool
    priority: int | None


@dataclass
class OpenAlexPaperResult:
    content_item_id: int
    match_status: str  # matched | OPENALEX_UNMATCHED | no_identifier | error
    match_strategy: str
    identifier: str | None = None
    openalex_work_id: str | None = None
    cache_hit: bool | None = None
    error: str | None = None
    institutions: list[dict[str, Any]] = field(default_factory=list)


@dataclass
class FetchStats:
    attempted: int = 0
    matched: int = 0
    unmatched: int = 0
    no_identifier: int = 0
    errors: int = 0
    requests: int = 0
    cache_hits: int = 0
    cache_misses: int = 0
    runtime_seconds: float = 0.0


def load_papers(conn: Any, date_from: date, date_until: date, *, limit: int | None = None) -> list[PaperRecord]:
    sql = (PAPERS_SQL_PI if PI_USE_PAPERS_CATALOG else PAPERS_SQL_RADAR) + (
        " LIMIT %s" if limit else ""
    )
    params: tuple[Any, ...] = (date_from.isoformat(), date_until.isoformat())
    if limit:
        params = (*params, int(limit))
    with conn.cursor() as cur:
        cur.execute(sql, params)
        rows = cur.fetchall()
    out: list[PaperRecord] = []
    for row in rows:
        pub = row["published_on"]
        if isinstance(pub, datetime):
            published_on = pub.date()
        elif isinstance(pub, date):
            published_on = pub
        else:
            published_on = date.fromisoformat(str(pub)[:10])
        status = row.get("status")
        # Normalize PI keep/reject to RELEVANT/REJECTED for metrics compatibility.
        if status == "keep":
            status = "RELEVANT"
        elif status == "reject":
            status = "REJECTED"
        out.append(
            PaperRecord(
                content_item_id=int(row["content_item_id"]),
                title=row.get("title"),
                status=status,
                published_on=published_on,
                arxiv_id=row.get("arxiv_id"),
                doi=row.get("doi"),
            )
        )
    return out


def load_affiliations(conn: Any, content_item_ids: Sequence[int]) -> dict[int, list[AffilRow]]:
    if not content_item_ids:
        return {}
    with conn.cursor() as cur:
        cur.execute(AFFILIATIONS_SQL, (list(content_item_ids),))
        rows = cur.fetchall()
    by_paper: dict[int, list[AffilRow]] = defaultdict(list)
    for row in rows:
        conf = row.get("confidence")
        by_paper[int(row["content_item_id"])].append(
            AffilRow(
                content_item_id=int(row["content_item_id"]),
                organisation_id=int(row["organisation_id"]) if row.get("organisation_id") is not None else None,
                evidence_type=row.get("evidence_type"),
                evidence_source=row.get("evidence_source"),
                evidence_value=row.get("evidence_value"),
                confidence=float(conf) if conf is not None else None,
                stage_version=row.get("stage_version"),
                canonical_name=row.get("canonical_name"),
                ror_id=row.get("ror_id"),
                openalex_id=row.get("openalex_id"),
                is_org_of_interest=bool(row.get("is_org_of_interest")),
                priority=int(row["priority"]) if row.get("priority") is not None else None,
            )
        )
    return dict(by_paper)


def accepted_affiliation_rows(rows: Sequence[AffilRow], *, min_confidence: float = MIN_CONFIDENCE) -> list[AffilRow]:
    accepted: list[AffilRow] = []
    for row in rows:
        if row.organisation_id is None:
            continue
        conf = 1.0 if row.confidence is None else float(row.confidence)
        if conf < min_confidence:
            continue
        accepted.append(row)
    return accepted


def ours_org_set(rows: Sequence[AffilRow], *, min_confidence: float = MIN_CONFIDENCE) -> dict[str, dict[str, Any]]:
    """canonical_key → org metadata for adjudication-acceptable evidence."""
    by_key: dict[str, dict[str, Any]] = {}
    for row in accepted_affiliation_rows(rows, min_confidence=min_confidence):
        key = organisation_canonical_key(
            ror_id=row.ror_id,
            openalex_id=row.openalex_id,
            name=row.canonical_name,
        )
        if not key:
            continue
        entry = by_key.get(key)
        if entry is None:
            by_key[key] = {
                "canonical_key": key,
                "organisation_id": row.organisation_id,
                "canonical_name": row.canonical_name,
                "ror_id": normalize_ror_id(row.ror_id),
                "openalex_id": normalize_openalex_id(row.openalex_id),
                "is_org_of_interest": bool(row.is_org_of_interest),
                "evidence_types": {row.evidence_type} if row.evidence_type else set(),
                "evidence_sources": {row.evidence_source} if row.evidence_source else set(),
                "confidences": [float(row.confidence) if row.confidence is not None else 1.0],
                "stage_versions": {row.stage_version} if row.stage_version else set(),
            }
        else:
            if row.evidence_type:
                entry["evidence_types"].add(row.evidence_type)
            if row.evidence_source:
                entry["evidence_sources"].add(row.evidence_source)
            entry["confidences"].append(float(row.confidence) if row.confidence is not None else 1.0)
            if row.stage_version:
                entry["stage_versions"].add(row.stage_version)
            entry["is_org_of_interest"] = entry["is_org_of_interest"] or bool(row.is_org_of_interest)
    return by_key


# ---------------------------------------------------------------------------
# OpenAlex fetch (cached)
# ---------------------------------------------------------------------------


def _fetch_one_openalex_paper(
    paper: PaperRecord,
    *,
    refresh: bool,
    oa_conn: Any,
    run_id: str | None,
    stage_run_id: str | None,
) -> tuple[OpenAlexPaperResult, bool, bool]:
    """Return (result, cache_hit, counted_as_request)."""
    from paper_intelligence.cache.raw_store import find_cached, request_hash

    identifier, strategy = openalex_lookup_identifier(paper.doi, paper.arxiv_id)
    if not identifier:
        return (
            OpenAlexPaperResult(
                content_item_id=paper.content_item_id,
                match_status=OPENALEX_UNMATCHED,
                match_strategy=strategy,
                error="no_identifier",
            ),
            False,
            False,
        )

    path = openalex_client._path_for(identifier)  # noqa: SLF001
    endpoint = f"{openalex_client.API_BASE}/{path}"
    req_hash = request_hash(openalex_client.PROVIDER, endpoint, {"path": path})
    cached_path = find_cached(openalex_client.PROVIDER, req_hash)

    if refresh and cached_path is not None:
        try:
            Path(cached_path).unlink(missing_ok=True)
        except OSError:
            pass
        cached_path = None

    cache_hit = cached_path is not None
    work = openalex_client.get_work(
        identifier,
        conn=oa_conn,
        run_id=run_id if oa_conn is not None else None,
        stage_run_id=stage_run_id if oa_conn is not None else None,
        content_item_id=paper.content_item_id if oa_conn is not None else None,
    )

    if work.error or not work.work:
        return (
            OpenAlexPaperResult(
                content_item_id=paper.content_item_id,
                match_status=OPENALEX_UNMATCHED,
                match_strategy=strategy,
                identifier=identifier,
                cache_hit=cache_hit,
                error=work.error or "empty_work",
            ),
            cache_hit,
            True,
        )

    institutions = extract_openalex_institutions(work.work)
    oa_id = normalize_openalex_id((work.work or {}).get("id"))
    return (
        OpenAlexPaperResult(
            content_item_id=paper.content_item_id,
            match_status="matched",
            match_strategy=strategy,
            identifier=identifier,
            openalex_work_id=oa_id,
            cache_hit=cache_hit,
            institutions=institutions,
        ),
        cache_hit,
        True,
    )


def fetch_openalex_for_papers(
    conn: Any,
    papers: Sequence[PaperRecord],
    *,
    refresh: bool = False,
    run_id: str | None = None,
    stage_run_id: str | None = None,
    progress_every: int = 500,
    log_external_requests: bool = False,
    workers: int = 8,
) -> tuple[dict[int, OpenAlexPaperResult], FetchStats]:
    """Fetch OpenAlex Works for papers using the shared raw cache.

    By default `log_external_requests=False` so validation can traverse tens of
    thousands of papers without a DB commit per call. Cache hits/misses are
    still counted locally. Parallel workers overlap HTTP latency only; the
    production client throttle still applies.
    """
    from concurrent.futures import ThreadPoolExecutor, as_completed

    stats = FetchStats()
    results: dict[int, OpenAlexPaperResult] = {}
    started = time.perf_counter()
    oa_conn = conn if log_external_requests else None
    worker_n = max(1, int(workers))

    def _handle(result: OpenAlexPaperResult, cache_hit: bool, counted: bool) -> None:
        stats.attempted += 1
        if not counted:
            stats.no_identifier += 1
            stats.unmatched += 1
        else:
            stats.requests += 1
            if cache_hit:
                stats.cache_hits += 1
            else:
                stats.cache_misses += 1
            if result.match_status == "matched":
                stats.matched += 1
            else:
                stats.unmatched += 1
                if result.error and "http_404" not in (result.error or "") and "empty" not in (
                    result.error or ""
                ):
                    stats.errors += 1
        results[result.content_item_id] = result

    if worker_n == 1:
        for index, paper in enumerate(papers, start=1):
            result, cache_hit, counted = _fetch_one_openalex_paper(
                paper,
                refresh=refresh,
                oa_conn=oa_conn,
                run_id=run_id,
                stage_run_id=stage_run_id,
            )
            _handle(result, cache_hit, counted)
            if progress_every and index % progress_every == 0:
                print(
                    f"  OpenAlex progress {index}/{len(papers)} "
                    f"matched={stats.matched} unmatched={stats.unmatched} "
                    f"cache_hits={stats.cache_hits} misses={stats.cache_misses}",
                    flush=True,
                )
    else:
        done = 0
        with ThreadPoolExecutor(max_workers=worker_n) as pool:
            futures = [
                pool.submit(
                    _fetch_one_openalex_paper,
                    paper,
                    refresh=refresh,
                    oa_conn=oa_conn,
                    run_id=run_id,
                    stage_run_id=stage_run_id,
                )
                for paper in papers
            ]
            for fut in as_completed(futures):
                result, cache_hit, counted = fut.result()
                _handle(result, cache_hit, counted)
                done += 1
                if progress_every and done % progress_every == 0:
                    print(
                        f"  OpenAlex progress {done}/{len(papers)} "
                        f"matched={stats.matched} unmatched={stats.unmatched} "
                        f"cache_hits={stats.cache_hits} misses={stats.cache_misses}",
                        flush=True,
                    )

    stats.runtime_seconds = round(time.perf_counter() - started, 3)
    return results, stats


# ---------------------------------------------------------------------------
# Window metrics
# ---------------------------------------------------------------------------


def _median(values: list[float]) -> float | None:
    if not values:
        return None
    return float(statistics.median(values))


def compute_window_metrics(
    papers: Sequence[PaperRecord],
    affiliations_by_paper: dict[int, list[AffilRow]],
    openalex_by_paper: dict[int, OpenAlexPaperResult],
    *,
    days: int,
    date_until: date,
    min_confidence: float = MIN_CONFIDENCE,
    disagreement_sample_size: int = 20,
) -> dict[str, Any]:
    start = window_start(date_until, days)
    window_papers = [p for p in papers if paper_in_window(p.published_on, date_until, days)]

    total = len(window_papers)
    relevant = sum(1 for p in window_papers if (p.status or "") == "RELEVANT")

    papers_with_aff_row = 0
    papers_with_org_id = 0
    papers_with_accepted = 0
    unique_org_ids: set[int] = set()
    paper_org_pairs: set[tuple[int, int]] = set()
    orgs_per_paper: list[float] = []
    orgs_per_affiliated: list[float] = []
    oi_papers = 0
    oi_org_ids: set[int] = set()
    evidence_bucket_papers: dict[str, set[int]] = defaultdict(set)

    ours_keys_all: set[str] = set()
    oa_keys_all: set[str] = set()

    matched = 0
    matched_with_inst = 0
    exact_set = 0
    overlap_at_least_one = 0
    ours_only = 0
    oa_only = 0
    both_disagree = 0
    both_empty = 0
    matched_with_common = 0
    matched_either_has = 0

    samples: dict[str, list[dict[str, Any]]] = {
        "openalex_has_ours_none": [],
        "ours_has_openalex_none": [],
        "both_disagree": [],
        "org_of_interest_disagreement": [],
    }

    for paper in window_papers:
        rows = affiliations_by_paper.get(paper.content_item_id, [])
        if rows:
            papers_with_aff_row += 1
        org_ids = dedupe_organisation_ids(r.organisation_id for r in rows)
        if org_ids:
            papers_with_org_id += 1

        ours = ours_org_set(rows, min_confidence=min_confidence)
        ours_keys = set(ours.keys())
        accepted_ids = dedupe_organisation_ids(v["organisation_id"] for v in ours.values())
        n_accepted = len(accepted_ids)
        orgs_per_paper.append(float(n_accepted))
        if n_accepted:
            papers_with_accepted += 1
            orgs_per_affiliated.append(float(n_accepted))
            unique_org_ids.update(accepted_ids)
            for oid in accepted_ids:
                paper_org_pairs.add((paper.content_item_id, oid))
            if any(v["is_org_of_interest"] for v in ours.values()):
                oi_papers += 1
                for v in ours.values():
                    if v["is_org_of_interest"] and v["organisation_id"] is not None:
                        oi_org_ids.add(int(v["organisation_id"]))
            for v in ours.values():
                for et in v["evidence_types"]:
                    # map via any matching source on the org entry
                    sources = list(v["evidence_sources"]) or [None]
                    for es in sources:
                        bucket = classify_evidence_bucket(et, es)
                        evidence_bucket_papers[bucket].add(paper.content_item_id)
                        break

        ours_keys_all |= ours_keys

        oa = openalex_by_paper.get(paper.content_item_id)
        oa_inst = oa.institutions if oa and oa.match_status == "matched" else []
        oa_keys = {inst["canonical_key"] for inst in oa_inst if inst.get("canonical_key")}
        if oa and oa.match_status == "matched":
            matched += 1
            if oa_keys:
                matched_with_inst += 1
            oa_keys_all |= oa_keys

            label = classify_disagreement(ours_keys, oa_keys)
            if label == "exact_set_match":
                exact_set += 1
                overlap_at_least_one += 1
                matched_with_common += 1
                matched_either_has += 1
            elif label == "overlap":
                overlap_at_least_one += 1
                matched_with_common += 1
                matched_either_has += 1
            elif label == "ours_only":
                ours_only += 1
                matched_either_has += 1
            elif label == "openalex_only":
                oa_only += 1
                matched_either_has += 1
            elif label == "both_disagree":
                both_disagree += 1
                matched_either_has += 1
            else:
                both_empty += 1

            sample = _sample_row(paper, rows, ours, oa)
            oi_ours = {k for k, v in ours.items() if v["is_org_of_interest"]}
            if label == "openalex_only" and len(samples["openalex_has_ours_none"]) < disagreement_sample_size:
                samples["openalex_has_ours_none"].append(sample)
            elif label == "ours_only" and len(samples["ours_has_openalex_none"]) < disagreement_sample_size:
                samples["ours_has_openalex_none"].append(sample)
            elif label == "both_disagree" and len(samples["both_disagree"]) < disagreement_sample_size:
                samples["both_disagree"].append(sample)

            # OoI disagreement: we have OoI keys that do not overlap OA, or OA has
            # institutions while our only accepted orgs are OoI and sets disagree.
            oi_disagrees = bool(oi_ours) and (
                not (oi_ours & oa_keys) if oa_keys or ours_keys != oa_keys else False
            )
            if oi_disagrees and ours_keys != oa_keys:
                if len(samples["org_of_interest_disagreement"]) < disagreement_sample_size:
                    samples["org_of_interest_disagreement"].append(sample)

    rates = compute_denominators(
        total_arxiv_papers=total,
        papers_with_accepted_org=papers_with_accepted,
        openalex_matched=matched,
        openalex_matched_with_institution=matched_with_inst,
        matched_with_common_org=matched_with_common,
        matched_either_has_org=matched_either_has,
    )

    intersection = ours_keys_all & oa_keys_all
    metrics = {
        "window_days": days,
        "date_from": start.isoformat(),
        "date_until": date_until.isoformat(),
        "min_confidence": min_confidence,
        "internal": {
            "total_arxiv_papers": total,
            "relevant_papers": relevant,
            "papers_with_affiliation_row": papers_with_aff_row,
            "papers_with_organisation_id": papers_with_org_id,
            "papers_with_accepted_org": papers_with_accepted,
            "unique_canonical_organisations": len(unique_org_ids),
            "paper_organisation_pairs": len(paper_org_pairs),
            "avg_organisations_per_paper": round(sum(orgs_per_paper) / total, 6) if total else None,
            "avg_organisations_per_affiliated_paper": (
                round(sum(orgs_per_affiliated) / len(orgs_per_affiliated), 6) if orgs_per_affiliated else None
            ),
            "median_organisations_per_affiliated_paper": _median(orgs_per_affiliated),
            "org_of_interest_paper_count": oi_papers,
            "unique_org_of_interest_organisations": len(oi_org_ids),
            "resolution_by_evidence_bucket_papers": {
                bucket: len(ids) for bucket, ids in sorted(evidence_bucket_papers.items())
            },
        },
        "openalex": {
            "papers_attempted": total,
            "works_matched": matched,
            "match_rate": rates["openalex_match_rate"],
            "match_rate_denominator": rates["openalex_match_rate_denominator"],
            "matched_with_institution": matched_with_inst,
            "unique_institutions": len(oa_keys_all),
            "paper_institution_pairs": sum(
                1
                for p in window_papers
                if (oa := openalex_by_paper.get(p.content_item_id))
                and oa.match_status == "matched"
                for _ in oa.institutions
            ),
            "avg_institutions_per_matched_paper": (
                round(
                    sum(
                        len(openalex_by_paper[p.content_item_id].institutions)
                        for p in window_papers
                        if openalex_by_paper.get(p.content_item_id)
                        and openalex_by_paper[p.content_item_id].match_status == "matched"
                    )
                    / matched,
                    6,
                )
                if matched
                else None
            ),
            "avg_institutions_among_papers_with_institutions": (
                round(
                    sum(
                        len(openalex_by_paper[p.content_item_id].institutions)
                        for p in window_papers
                        if openalex_by_paper.get(p.content_item_id)
                        and openalex_by_paper[p.content_item_id].match_status == "matched"
                        and openalex_by_paper[p.content_item_id].institutions
                    )
                    / matched_with_inst,
                    6,
                )
                if matched_with_inst
                else None
            ),
            "org_coverage": rates["openalex_org_coverage"],
            "org_coverage_denominator": rates["openalex_org_coverage_denominator"],
        },
        "openalex_agreement": {
            "exact_set_match_count": exact_set,
            "at_least_one_org_overlap_count": overlap_at_least_one,
            "ours_has_org_openalex_none": ours_only,
            "openalex_has_org_ours_none": oa_only,
            "both_have_org_sets_disagree": both_disagree,
            "both_empty": both_empty,
            "matched_papers": matched,
            "matched_either_has_org": matched_either_has,
            "matched_with_common_org": matched_with_common,
            "agreement_rate": rates["agreement_rate"],
            "agreement_rate_denominator": rates["agreement_rate_denominator"],
        },
        "openalex_coverage_comparison": {
            "unique_organisations_ours": len(ours_keys_all),
            "unique_institutions_openalex": len(oa_keys_all),
            "canonical_intersection": len(intersection),
            "ours_only_canonical_orgs": len(ours_keys_all - oa_keys_all),
            "openalex_only_canonical_institutions": len(oa_keys_all - ours_keys_all),
        },
        "rates": rates,
        "ours_org_coverage": rates["ours_org_coverage"],
        "disagreement_samples": samples,
    }
    return metrics


def _sample_row(
    paper: PaperRecord,
    rows: Sequence[AffilRow],
    ours: dict[str, dict[str, Any]],
    oa: OpenAlexPaperResult | None,
) -> dict[str, Any]:
    evidence_types = [r.evidence_type for r in rows if r.evidence_type]
    evidence_sources = [r.evidence_source for r in rows if r.evidence_source]
    return {
        "content_item_id": paper.content_item_id,
        "arxiv_id": paper.arxiv_id,
        "doi": paper.doi,
        "title": paper.title,
        "our_organisations": [
            {
                "organisation_id": v["organisation_id"],
                "canonical_name": v["canonical_name"],
                "canonical_key": v["canonical_key"],
                "ror_id": v["ror_id"],
                "openalex_id": v["openalex_id"],
                "is_org_of_interest": v["is_org_of_interest"],
                "evidence_types": sorted(v["evidence_types"]),
                "confidences": v["confidences"],
            }
            for v in ours.values()
        ],
        "our_evidence_types": sorted({t for t in evidence_types if t}),
        "our_confidence_values": [
            float(r.confidence) if r.confidence is not None else None for r in rows if r.organisation_id is not None
        ],
        "openalex_institutions": (oa.institutions if oa else []),
        "openalex_match_status": oa.match_status if oa else OPENALEX_UNMATCHED,
        "openalex_match_strategy": oa.match_strategy if oa else "none",
        "fast_deep_source": infer_fast_deep_source(evidence_types, evidence_sources),
        "disagreement_class": classify_disagreement(
            set(ours.keys()),
            {i["canonical_key"] for i in (oa.institutions if oa else []) if i.get("canonical_key")},
        ),
    }


# ---------------------------------------------------------------------------
# Reporting
# ---------------------------------------------------------------------------


def flatten_coverage_row(metrics: dict[str, Any]) -> dict[str, Any]:
    internal = metrics["internal"]
    oa = metrics["openalex"]
    agree = metrics["openalex_agreement"]
    cmp_ = metrics["openalex_coverage_comparison"]
    row = {
        "window_days": metrics["window_days"],
        "date_from": metrics["date_from"],
        "date_until": metrics["date_until"],
        "min_confidence": metrics["min_confidence"],
        **{f"internal_{k}": v for k, v in internal.items() if k != "resolution_by_evidence_bucket_papers"},
        **{f"evidence_{k}": v for k, v in internal.get("resolution_by_evidence_bucket_papers", {}).items()},
        **{f"openalex_{k}": v for k, v in oa.items()},
        **{f"agreement_{k}": v for k, v in agree.items()},
        **{f"comparison_{k}": v for k, v in cmp_.items()},
        "ours_org_coverage": metrics["ours_org_coverage"],
        "ours_org_coverage_denominator": metrics["rates"]["ours_org_coverage_denominator"],
    }
    return row


def disagreement_rows_for_csv(metrics: dict[str, Any]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    samples = metrics.get("disagreement_samples") or {}
    for kind, items in samples.items():
        for item in items:
            rows.append(
                {
                    "sample_kind": kind,
                    "content_item_id": item["content_item_id"],
                    "arxiv_id": item.get("arxiv_id"),
                    "doi": item.get("doi"),
                    "title": item.get("title"),
                    "disagreement_class": item.get("disagreement_class"),
                    "fast_deep_source": item.get("fast_deep_source"),
                    "our_organisations": json.dumps(item.get("our_organisations") or [], ensure_ascii=False),
                    "our_evidence_types": json.dumps(item.get("our_evidence_types") or [], ensure_ascii=False),
                    "our_confidence_values": json.dumps(item.get("our_confidence_values") or [], ensure_ascii=False),
                    "openalex_institutions": json.dumps(item.get("openalex_institutions") or [], ensure_ascii=False),
                    "openalex_match_status": item.get("openalex_match_status"),
                    "openalex_match_strategy": item.get("openalex_match_strategy"),
                }
            )
    return rows


def write_csv(path: Path, rows: Sequence[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if not rows:
        path.write_text("", encoding="utf-8")
        return
    # Union of keys for stable header
    fieldnames: list[str] = []
    seen: set[str] = set()
    for row in rows:
        for key in row:
            if key not in seen:
                seen.add(key)
                fieldnames.append(key)
    with path.open("w", encoding="utf-8", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=fieldnames, extrasaction="ignore")
        writer.writeheader()
        for row in rows:
            writer.writerow(row)


def render_summary_markdown(
    *,
    date_until: date,
    windows: Sequence[dict[str, Any]],
    fetch_stats: FetchStats,
    commit_sha: str | None,
) -> str:
    lines = [
        "# Organisation coverage validation",
        "",
        f"- date_until: `{date_until.isoformat()}`",
        f"- min_confidence: `{MIN_CONFIDENCE}`",
        f"- commit: `{commit_sha or 'unknown'}`",
        f"- generated_at: `{datetime.now(timezone.utc).isoformat()}`",
        "",
        "## Comparison table",
        "",
        "| Window | Papers | Ours org coverage | Unique ours orgs | OA match rate | OA org coverage | Unique OA orgs | At least one overlap |",
        "|---|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for m in windows:
        days = m["window_days"]
        total = m["internal"]["total_arxiv_papers"]
        ours_cov = m["ours_org_coverage"]
        ours_unique = m["internal"]["unique_canonical_organisations"]
        oa_match = m["openalex"]["match_rate"]
        oa_cov = m["openalex"]["org_coverage"]
        oa_unique = m["openalex"]["unique_institutions"]
        overlap = m["openalex_agreement"]["at_least_one_org_overlap_count"]
        lines.append(
            f"| {days}d | {total} | {_pct(ours_cov)} | {ours_unique} | {_pct(oa_match)} | {_pct(oa_cov)} | {oa_unique} | {overlap} |"
        )

    lines.extend(["", "## Denominators (explicit)", ""])
    lines.append(
        "- **Ours org coverage** = papers_with_accepted_org / total_arxiv_papers "
        f"(accepted = organisation_id present and confidence ≥ {MIN_CONFIDENCE})"
    )
    lines.append(
        "- **OA match rate** = openalex_matched_papers / total_arxiv_papers"
    )
    lines.append(
        "- **OA org coverage** = matched_openalex_papers_with_institution / openalex_matched_papers"
    )
    lines.append(
        "- **Agreement rate** = matched papers with ≥1 common canonical org / "
        "matched papers where either side has ≥1 org"
    )

    lines.extend(["", "## Disagreement counts (matched papers only)", ""])
    lines.append(
        "| Window | Exact set | ≥1 overlap | Ours only | OA only | Both disagree | Agreement rate |"
    )
    lines.append("|---|---:|---:|---:|---:|---:|---:|")
    for m in windows:
        a = m["openalex_agreement"]
        lines.append(
            f"| {m['window_days']}d | {a['exact_set_match_count']} | {a['at_least_one_org_overlap_count']} | "
            f"{a['ours_has_org_openalex_none']} | {a['openalex_has_org_ours_none']} | "
            f"{a['both_have_org_sets_disagree']} | {_pct(a['agreement_rate'])} |"
        )

    lines.extend(
        [
            "",
            "## OpenAlex fetch statistics (31d population)",
            "",
            f"- papers attempted: {fetch_stats.attempted}",
            f"- works matched: {fetch_stats.matched}",
            f"- unmatched / no id / errors: {fetch_stats.unmatched} "
            f"(no_identifier={fetch_stats.no_identifier}, errors={fetch_stats.errors})",
            f"- OpenAlex requests logged: {fetch_stats.requests}",
            f"- cache hits: {fetch_stats.cache_hits}",
            f"- cache misses: {fetch_stats.cache_misses}",
            f"- runtime_seconds: {fetch_stats.runtime_seconds}",
            "",
            "## Notes",
            "",
            "- OpenAlex is a public baseline, not ground truth; rates are labeled "
            "**OpenAlex agreement** / **OpenAlex coverage comparison**, not precision/recall.",
            "- Canonical comparison prefers ROR ID, then OpenAlex institution ID, then casefolded name.",
            "- Duplicate author→institution rows are deduplicated by organisation/institution id before counting.",
            "",
        ]
    )
    return "\n".join(lines) + "\n"


def _pct(value: float | None) -> str:
    if value is None:
        return "n/a"
    return f"{100.0 * value:.1f}%"


def observe_disagreement_causes(windows: Sequence[dict[str, Any]]) -> list[str]:
    """Short factual causes from sampled disagreements only."""
    causes: list[str] = []
    # Aggregate sample kinds across windows
    totals = Counter()
    match_strategies = Counter()
    for m in windows:
        agree = m["openalex_agreement"]
        totals["oa_only"] += agree["openalex_has_org_ours_none"]
        totals["ours_only"] += agree["ours_has_org_openalex_none"]
        totals["disagree"] += agree["both_have_org_sets_disagree"]
        totals["exact"] += agree["exact_set_match_count"]
        for kind, items in (m.get("disagreement_samples") or {}).items():
            for item in items:
                match_strategies[item.get("openalex_match_strategy") or "none"] += 1
                if kind == "openalex_has_ours_none":
                    if not item.get("our_organisations"):
                        causes.append("sample: OA institutions present while we stored no accepted organisation_id")
                if kind == "ours_has_openalex_none":
                    causes.append("sample: we resolved organisations while OpenAlex Work has empty institutions")
                if kind == "both_disagree":
                    causes.append("sample: both sides non-empty but canonical key sets disjoint (ROR/OpenAlex/name)")

    summary: list[str] = []
    if totals["oa_only"]:
        summary.append(
            f"OpenAlex-only orgs dominate residual gaps in counts "
            f"(summed across windows: {totals['oa_only']} matched papers)."
        )
    if totals["ours_only"]:
        summary.append(
            f"Ours-only orgs appear on {totals['ours_only']} matched papers across windows "
            "(often email_domain / local alias where OpenAlex authorships lack institutions)."
        )
    if totals["disagree"]:
        summary.append(
            f"{totals['disagree']} matched papers have both sides non-empty but disagree on canonical sets "
            "(canonicalisation / ROR linkage mismatches are visible in disagreement CSVs)."
        )
    if not summary:
        summary.append("Insufficient matched disagreements to summarise causes.")
    # Dedupe cause bullets while keeping order
    seen: set[str] = set()
    for c in causes:
        if c not in seen:
            seen.add(c)
            summary.append(c)
        if len(summary) >= 8:
            break
    return summary
