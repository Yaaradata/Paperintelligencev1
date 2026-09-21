"""Editorial nomination and exploration sampling for quality scoring.

These routes reuse the production quality stage. They never change
GATE_PERCENTILE, screen scores, or org boosts. Provenance is stored as
``result_json.route``.
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass
from datetime import date
from typing import Any, Sequence

from psycopg import Connection

from paper_intelligence.common.config import GATE_PERCENTILE, PI_USE_PAPERS_CATALOG, QUALITY_MODEL
from paper_intelligence.db import fetch_papers, ids_with_result, latest_screen_scores
from paper_intelligence.quality.stage import (
    POLICY_VERSION,
    PROMPT_VERSION,
    RANK_DIMENSIONS,
    STAGE_VERSION,
    select_quality_candidates,
)

ROUTE_EDITORIAL = "editorial_nomination"
ROUTE_EXPLORATION = "exploration_sample"


@dataclass(frozen=True)
class NominationTarget:
    content_item_id: int
    arxiv_id: str | None
    title: str | None
    status: str | None
    published_at: str | None
    screen_gate_passed: bool | None
    screen_rank_mean: float | None
    already_quality_scored: bool
    exclusion_reason: str | None


def resolve_content_ids(
    conn: Connection,
    *,
    content_item_ids: Sequence[int] | None = None,
    arxiv_ids: Sequence[str] | None = None,
) -> list[int]:
    """Resolve content_item_id and/or arxiv_id inputs to unique content ids."""
    ids: list[int] = []
    seen: set[int] = set()
    for cid in content_item_ids or []:
        cid_i = int(cid)
        if cid_i not in seen:
            seen.add(cid_i)
            ids.append(cid_i)
    if arxiv_ids:
        cleaned = [a.strip() for a in arxiv_ids if a and a.strip()]
        if cleaned:
            with conn.cursor() as cur:
                if PI_USE_PAPERS_CATALOG:
                    from paper_intelligence.catalog.normalize import normalize_arxiv_id

                    norms = [normalize_arxiv_id(a) or a for a in cleaned]
                    cur.execute(
                        """
                        SELECT paper_id AS content_id, arxiv_id
                        FROM paper_intelligence.papers
                        WHERE arxiv_id = ANY(%s)
                        """,
                        (norms,),
                    )
                    found = {
                        row["arxiv_id"]: int(row["content_id"]) for row in cur.fetchall()
                    }
                    # Also accept raw inputs mapped via normalization.
                    by_norm = {normalize_arxiv_id(k) or k: v for k, v in found.items()}
                    resolved: dict[str, int] = {}
                    for raw, norm in zip(cleaned, norms):
                        if norm in by_norm:
                            resolved[raw] = by_norm[norm]
                        elif raw in found:
                            resolved[raw] = found[raw]
                    found = resolved
                else:
                    cur.execute(
                        """
                        SELECT pm.content_id, pm.arxiv_id
                        FROM research_radar.paper_metadata pm
                        WHERE pm.arxiv_id = ANY(%s)
                        """,
                        (cleaned,),
                    )
                    found = {
                        row["arxiv_id"]: int(row["content_id"]) for row in cur.fetchall()
                    }
            missing = [a for a in cleaned if a not in found]
            if missing:
                raise ValueError(f"arxiv_id not found: {missing}")
            for a in cleaned:
                cid_i = found[a]
                if cid_i not in seen:
                    seen.add(cid_i)
                    ids.append(cid_i)
    return ids


def _screen_stats(conn: Connection, content_item_id: int) -> tuple[bool | None, float | None]:
    with conn.cursor() as cur:
        cur.execute(
            """
            SELECT result_json
            FROM paper_intelligence.paper_classification_results
            WHERE content_item_id = %s AND task_type = 'screen'
            ORDER BY created_at DESC
            LIMIT 1
            """,
            (content_item_id,),
        )
        row = cur.fetchone()
    if not row:
        return None, None
    result = row["result_json"] or {}
    passed = bool((result.get("gate") or {}).get("passed"))
    try:
        mean = sum(float(result[d]) for d in RANK_DIMENSIONS) / len(RANK_DIMENSIONS)
    except (KeyError, TypeError, ValueError):
        mean = None
    return passed, mean


def describe_targets(
    conn: Connection,
    content_item_ids: Sequence[int],
    *,
    model: str = QUALITY_MODEL,
) -> list[NominationTarget]:
    """Build provenance snapshots for nominated papers (no LLM calls)."""
    if not content_item_ids:
        return []
    with conn.cursor() as cur:
        if PI_USE_PAPERS_CATALOG:
            cur.execute(
                """
                SELECT p.paper_id AS content_item_id, p.title, NULL::text AS status,
                       p.published_at, p.arxiv_id
                FROM paper_intelligence.papers p
                WHERE p.paper_id = ANY(%s)
                ORDER BY p.paper_id
                """,
                (list(content_item_ids),),
            )
        else:
            cur.execute(
                """
                SELECT ci.id AS content_item_id, ci.title, ci.status, ci.published_at,
                       pm.arxiv_id
                FROM research_radar.content_items ci
                LEFT JOIN research_radar.paper_metadata pm ON pm.content_id = ci.id
                WHERE ci.id = ANY(%s)
                ORDER BY ci.id
                """,
                (list(content_item_ids),),
            )
        rows = {int(r["content_item_id"]): dict(r) for r in cur.fetchall()}

    done = ids_with_result(
        conn,
        list(content_item_ids),
        "quality",
        stage_version=STAGE_VERSION,
        prompt_version=PROMPT_VERSION,
        policy_version=POLICY_VERSION,
        model=model,
    )

    out: list[NominationTarget] = []
    for cid in content_item_ids:
        row = rows.get(int(cid))
        if not row:
            out.append(
                NominationTarget(
                    content_item_id=int(cid),
                    arxiv_id=None,
                    title=None,
                    status=None,
                    published_at=None,
                    screen_gate_passed=None,
                    screen_rank_mean=None,
                    already_quality_scored=False,
                    exclusion_reason="content_item_id not found",
                )
            )
            continue
        passed, mean = _screen_stats(conn, int(cid))
        status = row.get("status")
        reasons: list[str] = []
        # PI routing eligibility is screen-gate based. Radar status is informational
        # only (still surfaced on NominationTarget for operators).
        if passed is None:
            reasons.append("no screen result")
        elif not passed:
            reasons.append("screen gate failed")
        already = int(cid) in done
        # Preserve original router decision when we can compute day window.
        pub = row.get("published_at")
        router_exclusion = None
        if pub is not None and passed:
            day = pub.date().isoformat() if hasattr(pub, "date") else str(pub)[:10]
            selected = set(
                select_quality_candidates(conn, date_from=day, date_until=day)
            )
            if int(cid) not in selected:
                router_exclusion = (
                    f"outside quality router on {day} "
                    f"(top {GATE_PERCENTILE}% ∪ notable-org/person); "
                    f"screen_rank_mean={mean}"
                )
        exclusion = "; ".join(reasons) if reasons else router_exclusion
        out.append(
            NominationTarget(
                content_item_id=int(cid),
                arxiv_id=row.get("arxiv_id"),
                title=row.get("title"),
                status=status,
                published_at=str(pub) if pub is not None else None,
                screen_gate_passed=passed,
                screen_rank_mean=round(mean, 4) if mean is not None else None,
                already_quality_scored=already,
                exclusion_reason=exclusion,
            )
        )
    return out


def filter_scoreable(
    targets: Sequence[NominationTarget],
    *,
    reprocess: bool = False,
) -> tuple[list[int], list[NominationTarget]]:
    """Return ids to score and skipped targets."""
    to_score: list[int] = []
    skipped: list[NominationTarget] = []
    for t in targets:
        if t.content_item_id is None:
            skipped.append(t)
            continue
        if t.screen_gate_passed is not True:
            skipped.append(t)
            continue
        if t.already_quality_scored and not reprocess:
            skipped.append(t)
            continue
        to_score.append(t.content_item_id)
    return to_score, skipped


def exploration_candidates(
    conn: Connection,
    *,
    date_from: str,
    date_until: str,
    gate_percentile: float = GATE_PERCENTILE,
) -> list[dict[str, Any]]:
    """Gate-passed papers outside the normal quality router for one window."""
    normal = set(
        select_quality_candidates(
            conn,
            date_from=date_from,
            date_until=date_until,
            gate_percentile=gate_percentile,
        )
    )
    ranked: list[dict[str, Any]] = []
    for row in latest_screen_scores(conn, date_from=date_from, date_until=date_until):
        result = row["result_json"] or {}
        if not (result.get("gate") or {}).get("passed"):
            continue
        cid = int(row["content_item_id"])
        if cid in normal:
            continue
        try:
            mean = sum(float(result[d]) for d in RANK_DIMENSIONS) / len(RANK_DIMENSIONS)
        except (KeyError, TypeError, ValueError):
            continue
        if mean >= 7.5:
            band = "high"
        elif mean >= 6.5:
            band = "mid"
        else:
            band = "low"
        ranked.append(
            {
                "content_item_id": cid,
                "rank_mean": round(mean, 4),
                "band": band,
            }
        )
    # Attach domain hint from current table when present.
    if ranked:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT content_item_id, domain
                FROM paper_intelligence.paper_intelligence_current
                WHERE content_item_id = ANY(%s)
                """,
                ([r["content_item_id"] for r in ranked],),
            )
            domains = {
                int(r["content_item_id"]): r.get("domain") for r in cur.fetchall()
            }
        for r in ranked:
            r["domain"] = domains.get(r["content_item_id"]) or "unknown"
    return ranked


def stratified_sample(
    pool: Sequence[dict[str, Any]],
    *,
    per_day: int,
    seed: str,
    bands: Sequence[str] = ("mid", "low"),
) -> list[dict[str, Any]]:
    """Deterministic stratified sample. Does not call the LLM.

    Spreads ``per_day`` slots across bands, then across domains within a band.
    Records sampling_probability ≈ slots_in_stratum / stratum_size.
    """
    if per_day <= 0 or not pool:
        return []
    by_band: dict[str, list[dict[str, Any]]] = {b: [] for b in bands}
    for row in pool:
        band = row.get("band")
        if band in by_band:
            by_band[band].append(dict(row))

    # Allocate slots roughly evenly across non-empty bands.
    nonempty = [b for b in bands if by_band[b]]
    if not nonempty:
        return []
    base, rem = divmod(per_day, len(nonempty))
    allocation = {b: base + (1 if i < rem else 0) for i, b in enumerate(nonempty)}

    selected: list[dict[str, Any]] = []
    for band in nonempty:
        items = by_band[band]
        # Secondary stratum: domain
        by_domain: dict[str, list[dict[str, Any]]] = {}
        for item in items:
            by_domain.setdefault(item.get("domain") or "unknown", []).append(item)
        domains = sorted(by_domain)
        slots = allocation[band]
        if not domains or slots <= 0:
            continue
        d_base, d_rem = divmod(slots, len(domains))
        d_alloc = {d: d_base + (1 if i < d_rem else 0) for i, d in enumerate(domains)}
        for domain in domains:
            stratum = by_domain[domain]
            k = min(d_alloc[domain], len(stratum))
            if k <= 0:
                continue
            # Stable shuffle via hash seed.
            ordered = sorted(
                stratum,
                key=lambda r: hashlib.sha256(
                    f"{seed}:{band}:{domain}:{r['content_item_id']}".encode()
                ).hexdigest(),
            )
            prob = k / len(stratum)
            for row in ordered[:k]:
                row = dict(row)
                row["sampling_probability"] = round(prob, 6)
                row["stratum"] = f"{band}|{domain}"
                row["route"] = ROUTE_EXPLORATION
                selected.append(row)
    return selected


def estimate_exploration_pilot(
    conn: Connection,
    *,
    day: str,
    per_day: int = 12,
    seed: str = "exploration-pilot-v1",
) -> dict[str, Any]:
    """Compute sample size + dry-run cost for one day (no LLM)."""
    from paper_intelligence.quality.stage import run_window

    pool = exploration_candidates(conn, date_from=day, date_until=day)
    sample = stratified_sample(pool, per_day=per_day, seed=f"{seed}:{day}")
    ids = [r["content_item_id"] for r in sample]
    # Deduplicate against already-scored quality versions.
    done = ids_with_result(
        conn,
        ids,
        "quality",
        stage_version=STAGE_VERSION,
        prompt_version=PROMPT_VERSION,
        policy_version=POLICY_VERSION,
        model=QUALITY_MODEL,
    )
    to_score = [i for i in ids if i not in done]
    stats = run_window(
        conn,
        to_score,
        run_id="dry-run",
        stage_run_id="dry-run",
        dry_run=True,
        route=ROUTE_EXPLORATION,
    )
    return {
        "day": day,
        "outside_router_pool": len(pool),
        "sample_size": len(sample),
        "already_scored": len(ids) - len(to_score),
        "to_score": len(to_score),
        "projected_calls": stats.calls,
        "projected_cost_usd": round(stats.cost_usd, 4),
        "bands": {
            b: sum(1 for r in sample if r.get("band") == b) for b in ("mid", "low", "high")
        },
        "sample": sample,
    }
