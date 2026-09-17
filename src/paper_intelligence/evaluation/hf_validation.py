"""HF Daily Papers validation — observational ranking comparison.

Does NOT change final_score or adjudication. Pure analysis over existing
paper_intelligence_current + paper_hf_signals (+ optional HF daily index).
"""

from __future__ import annotations

import csv
import json
import statistics
from collections import Counter
from dataclasses import asdict, dataclass, field
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Iterable, Sequence

STAGE_NAME = "hf_validation"
STAGE_VERSION = "v001"

# Fixed 30-day window (inclusive). HF Daily Papers available through 2026-09-16.
DEFAULT_WINDOW_START = date(2026, 8, 18)
DEFAULT_WINDOW_END = date(2026, 9, 16)

# Existing system: quality stage scores top GATE_PERCENTILE of screen survivors;
# adjudication writes final_score. That is our high-quality set — no new threshold.
SCORE_FIELD = "final_score"
SELECTION_METHOD = "final_score_is_not_null"
SELECTION_DETAIL = (
    "High-quality = papers with paper_intelligence_current.final_score IS NOT NULL "
    "(already selected by screen gate + quality GATE_PERCENTILE slice + adjudication). "
    "No new score threshold invented."
)


@dataclass(frozen=True)
class OverlapStats:
    hf_unique: int
    our_unique: int
    intersection: int
    hf_to_ours_pct: float
    ours_to_hf_pct: float
    hf_only: int
    ours_only: int


@dataclass
class CohortMetrics:
    count: int = 0
    avg_score: float | None = None
    median_score: float | None = None
    pct_notable_org: float | None = None
    pct_notable_person: float | None = None
    pct_tech_product_audience: float | None = None
    pct_student_audience: float | None = None
    domain_distribution: dict[str, int] = field(default_factory=dict)
    subdomain_distribution: dict[str, int] = field(default_factory=dict)
    mean_hf_upvotes: float | None = None


def inclusive_days(start: date, end: date) -> int:
    return (end - start).days + 1


def assign_cohort(*, in_hf: bool, in_high_quality: bool) -> str | None:
    """Return BOTH / OURS_ONLY / HF_ONLY, or None if outside comparison universe.

    Comparison universe = high-quality ∪ HF-featured (in our corpus).
    Each paper in that universe maps to exactly one cohort.
    """
    if in_hf and in_high_quality:
        return "BOTH"
    if in_high_quality and not in_hf:
        return "OURS_ONLY"
    if in_hf and not in_high_quality:
        return "HF_ONLY"
    return None


def compute_overlap(hf_ids: set[str], our_ids: set[str]) -> OverlapStats:
    intersection = hf_ids & our_ids
    hf_n = len(hf_ids)
    our_n = len(our_ids)
    inter_n = len(intersection)
    return OverlapStats(
        hf_unique=hf_n,
        our_unique=our_n,
        intersection=inter_n,
        hf_to_ours_pct=round(100.0 * inter_n / hf_n, 1) if hf_n else 0.0,
        ours_to_hf_pct=round(100.0 * inter_n / our_n, 1) if our_n else 0.0,
        hf_only=len(hf_ids - our_ids),
        ours_only=len(our_ids - hf_ids),
    )


def daily_upvote_ranks(
    papers: Sequence[dict[str, Any]],
) -> dict[str, int]:
    """Same-day rank by upvotes desc, ties broken by arxiv_id asc. 1 = highest."""
    ranked = sorted(
        papers,
        key=lambda p: (
            -(int(p["upvotes"]) if p.get("upvotes") is not None else -1),
            str(p.get("arxiv_id") or ""),
        ),
    )
    return {
        str(p["arxiv_id"]): i
        for i, p in enumerate(ranked, start=1)
        if p.get("arxiv_id")
    }


def _as_list(value: Any) -> list[Any]:
    if value is None:
        return []
    if isinstance(value, list):
        return value
    return list(value) if value else []


def _mean(values: Sequence[float]) -> float | None:
    return round(statistics.mean(values), 3) if values else None


def _median(values: Sequence[float]) -> float | None:
    return round(float(statistics.median(values)), 3) if values else None


def _pct(num: int, den: int) -> float | None:
    return round(100.0 * num / den, 1) if den else None


TECH_PRODUCT = {"practitioner", "technical_leadership", "enterprise_adoption"}
STUDENT = {"student"}


def summarize_cohort(rows: Sequence[dict[str, Any]]) -> CohortMetrics:
    scores = [
        float(r["final_score"])
        for r in rows
        if r.get("final_score") is not None
    ]
    upvotes = [
        float(r["hf_upvotes"])
        for r in rows
        if r.get("hf_upvotes") is not None
    ]
    n = len(rows)
    notable_org = sum(1 for r in rows if r.get("notable_organisation"))
    notable_person = sum(1 for r in rows if r.get("notable_person"))
    tech = sum(
        1
        for r in rows
        if TECH_PRODUCT.intersection({str(a) for a in _as_list(r.get("audiences"))})
    )
    student = sum(
        1
        for r in rows
        if STUDENT.intersection({str(a) for a in _as_list(r.get("audiences"))})
    )
    domains: Counter[str] = Counter()
    subdomains: Counter[str] = Counter()
    for r in rows:
        if r.get("domain"):
            domains[str(r["domain"])] += 1
        for s in _as_list(r.get("subdomains")):
            subdomains[str(s)] += 1
    return CohortMetrics(
        count=n,
        avg_score=_mean(scores),
        median_score=_median(scores),
        pct_notable_org=_pct(notable_org, n),
        pct_notable_person=_pct(notable_person, n),
        pct_tech_product_audience=_pct(tech, n),
        pct_student_audience=_pct(student, n),
        domain_distribution=dict(domains.most_common()),
        subdomain_distribution=dict(subdomains.most_common(20)),
        mean_hf_upvotes=_mean(upvotes),
    )


def why_high(row: dict[str, Any]) -> str:
    """Deterministic explanation from stored components only."""
    parts: list[str] = []
    if row.get("final_score") is not None:
        parts.append(f"final_score={row['final_score']}")
    if row.get("quality_score") is not None:
        parts.append(f"quality={row['quality_score']}")
    if row.get("org_boost"):
        parts.append(f"org_boost={row['org_boost']}")
    if row.get("notable_organisation"):
        parts.append(f"notable_org={row['notable_organisation']}")
    aud = _as_list(row.get("audiences"))
    if aud:
        parts.append("audiences=" + ",".join(str(a) for a in aud))
    if row.get("domain"):
        parts.append(f"domain={row['domain']}")
    return "; ".join(parts) if parts else "no stored score components"


def why_low(row: dict[str, Any]) -> str:
    """Why HF paper missed our high-quality set — stored fields only."""
    if row.get("final_score") is None:
        parts = ["no final_score (not in quality/adjudication slice)"]
        if row.get("screen_score") is not None:
            parts.append(f"screen_score={row['screen_score']}")
        return "; ".join(parts)
    return why_high(row)


def top_n(
    rows: Sequence[dict[str, Any]],
    n: int = 20,
    *,
    cohort: str,
) -> list[dict[str, Any]]:
    if cohort == "HF_ONLY":
        key = lambda r: (
            -(float(r["hf_upvotes"]) if r.get("hf_upvotes") is not None else -1),
            str(r.get("arxiv_id") or ""),
        )
    else:
        key = lambda r: (
            -(float(r["final_score"]) if r.get("final_score") is not None else -1),
            -(float(r["quality_score"]) if r.get("quality_score") is not None else -1),
            str(r.get("arxiv_id") or ""),
        )
    ordered = sorted(rows, key=key)
    out: list[dict[str, Any]] = []
    for rank, row in enumerate(ordered[:n], start=1):
        item = dict(row)
        item["our_rank"] = rank if cohort != "HF_ONLY" else row.get("our_rank")
        item["sample_rank"] = rank
        if cohort == "OURS_ONLY":
            item["why_high"] = why_high(row)
        if cohort == "HF_ONLY":
            item["why_lower"] = why_low(row)
        out.append(item)
    return out


SAMPLE_COLUMNS = [
    "arxiv_id",
    "title",
    "published_at",
    "domain",
    "subdomains",
    "audiences",
    "application_domains",
    "final_score",
    "quality_score",
    "our_rank",
    "sample_rank",
    "hf_featured",
    "hf_featured_date",
    "hf_upvotes",
    "hf_daily_upvote_rank",
    "notable_organisation",
    "notable_person",
    "why_high",
    "why_lower",
]


def write_csv(path: Path, rows: Sequence[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(fh, fieldnames=SAMPLE_COLUMNS, extrasaction="ignore")
        writer.writeheader()
        for row in rows:
            serialised = dict(row)
            for key in ("subdomains", "audiences", "application_domains"):
                if key in serialised and not isinstance(serialised[key], str):
                    serialised[key] = json.dumps(serialised[key], default=str)
            if serialised.get("published_at") is not None:
                serialised["published_at"] = str(serialised["published_at"])
            if serialised.get("hf_featured_date") is not None:
                serialised["hf_featured_date"] = str(serialised["hf_featured_date"])
            writer.writerow({k: serialised.get(k) for k in SAMPLE_COLUMNS})


def build_report_payload(
    *,
    window_start: date,
    window_end: date,
    overlap: OverlapStats,
    cohorts: dict[str, list[dict[str, Any]]],
    metrics: dict[str, CohortMetrics],
    run_meta: dict[str, Any],
) -> dict[str, Any]:
    return {
        "window": {
            "start": window_start.isoformat(),
            "end": window_end.isoformat(),
            "inclusive_days": inclusive_days(window_start, window_end),
        },
        "overlap": asdict(overlap),
        "ranking_method": {
            "score_field": SCORE_FIELD,
            "selection_method": SELECTION_METHOD,
            "threshold_or_top_n": SELECTION_DETAIL,
        },
        "cohorts": {
            name: {
                "count": metrics[name].count,
                "metrics": asdict(metrics[name]),
            }
            for name in ("BOTH", "OURS_ONLY", "HF_ONLY")
        },
        "run": run_meta,
        "generated_at": datetime.now(timezone.utc).isoformat(),
    }


def console_summary(
    overlap: OverlapStats, metrics: dict[str, CohortMetrics]
) -> str:
    lines = [
        "HF VALIDATION — 30 DAY WINDOW",
        "",
        f"HF papers: {overlap.hf_unique}",
        f"Our papers: {overlap.our_unique}",
        f"Intersection: {overlap.intersection}",
        "",
        f"HF → ours: {overlap.hf_to_ours_pct}%",
        f"Ours → HF: {overlap.ours_to_hf_pct}%",
        "",
        f"BOTH: {metrics['BOTH'].count}",
        f"OURS ONLY: {metrics['OURS_ONLY'].count}",
        f"HF ONLY: {metrics['HF_ONLY'].count}",
        "",
        "Avg score:",
        f"Both: {metrics['BOTH'].avg_score}",
        f"Ours only: {metrics['OURS_ONLY'].avg_score}",
        f"HF only: {metrics['HF_ONLY'].avg_score}",
    ]
    return "\n".join(lines)
