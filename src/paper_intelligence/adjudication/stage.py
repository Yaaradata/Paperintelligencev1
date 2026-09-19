"""Stage: adjudication — free, deterministic, no LLM.

Collapses the append-only stage results into one current-state row per paper.
Reads the LATEST result per task_type, applies the organisation boost on top of
the blinded quality composite, and records what it did in adjudication_json.
"""

from __future__ import annotations

import json
from typing import Any

from psycopg import Connection

from paper_intelligence.adjudication.org_score import organisation_score
from paper_intelligence.common.config import GATE_PERCENTILE
from paper_intelligence.quality.stage import (
    composite_score,
    quality_selection_reason_map,
)

STAGE_NAME = "adjudication"
STAGE_VERSION = "v002"
POLICY_VERSION = "v001"

# Screen and quality disagreeing by this much is a review signal, not an error.
DISAGREEMENT_THRESHOLD = 3.0

LATEST_RESULTS_SQL = """
SELECT DISTINCT ON (r.content_item_id, r.task_type)
    r.content_item_id, r.task_type, r.result_json, r.confidence
FROM paper_intelligence.paper_classification_results r
JOIN research_radar.content_items ci ON ci.id = r.content_item_id
WHERE ci.published_at >= %s::timestamptz
  AND ci.published_at < (%s::timestamptz + interval '1 day')
ORDER BY r.content_item_id, r.task_type, r.created_at DESC
"""

AFFILIATION_SQL = """
SELECT a.content_item_id, a.organisation_id, a.evidence_type, a.confidence,
       o.canonical_name, o.priority, o.is_org_of_interest
FROM paper_intelligence.paper_author_affiliations a
LEFT JOIN paper_intelligence.organisations o ON o.id = a.organisation_id
JOIN research_radar.content_items ci ON ci.id = a.content_item_id
WHERE ci.published_at >= %s::timestamptz
  AND ci.published_at < (%s::timestamptz + interval '1 day')
"""

AUTHOR_COUNT_SQL = """
SELECT pa.content_item_id, COUNT(*) AS n
FROM paper_intelligence.paper_authors pa
JOIN research_radar.content_items ci ON ci.id = pa.content_item_id
WHERE ci.published_at >= %s::timestamptz
  AND ci.published_at < (%s::timestamptz + interval '1 day')
GROUP BY pa.content_item_id
"""

UPSERT_SQL = """
INSERT INTO paper_intelligence.paper_intelligence_current
    (content_item_id, domain, subdomains, audiences, application_domains,
     domain_confidence, audience_confidence, screen_score, quality_score,
     organisation_score, org_boost, person_boost, final_score,
     top_organisation_id, author_resolution_status, affiliation_resolution_status,
     quality_status, adjudication_json, run_id, updated_at)
VALUES (%s, %s, %s::jsonb, %s::jsonb, %s::jsonb, %s, %s, %s, %s, %s, %s, %s, %s,
        %s, %s, %s, %s, %s::jsonb, %s, NOW())
ON CONFLICT (content_item_id) DO UPDATE SET
    domain = EXCLUDED.domain,
    subdomains = EXCLUDED.subdomains,
    audiences = EXCLUDED.audiences,
    application_domains = EXCLUDED.application_domains,
    domain_confidence = EXCLUDED.domain_confidence,
    audience_confidence = EXCLUDED.audience_confidence,
    screen_score = EXCLUDED.screen_score,
    quality_score = EXCLUDED.quality_score,
    organisation_score = EXCLUDED.organisation_score,
    org_boost = EXCLUDED.org_boost,
    person_boost = EXCLUDED.person_boost,
    final_score = EXCLUDED.final_score,
    top_organisation_id = EXCLUDED.top_organisation_id,
    author_resolution_status = EXCLUDED.author_resolution_status,
    affiliation_resolution_status = EXCLUDED.affiliation_resolution_status,
    quality_status = EXCLUDED.quality_status,
    adjudication_json = EXCLUDED.adjudication_json,
    run_id = EXCLUDED.run_id,
    updated_at = NOW()
"""

SCREEN_DIMENSIONS = ("technical_significance", "apparent_novelty", "evidence_strength")


def _screen_score(result: dict[str, Any]) -> float | None:
    try:
        return round(
            sum(float(result[dim]) for dim in SCREEN_DIMENSIONS) / len(SCREEN_DIMENSIONS), 1
        )
    except (KeyError, TypeError, ValueError):
        return None


def run_window(
    conn: Connection,
    *,
    date_from: str,
    date_until: str,
    run_id: str | None = None,
    dry_run: bool = False,
) -> dict[str, int]:
    """Rebuild current state for every paper in the window that has any result."""
    by_paper: dict[int, dict[str, Any]] = {}
    with conn.cursor() as cur:
        cur.execute(LATEST_RESULTS_SQL, (date_from, date_until))
        for row in cur.fetchall():
            entry = by_paper.setdefault(int(row["content_item_id"]), {})
            entry[row["task_type"]] = {
                "result": row["result_json"] or {},
                "confidence": row["confidence"],
            }

        affiliations: dict[int, list[dict[str, Any]]] = {}
        cur.execute(AFFILIATION_SQL, (date_from, date_until))
        for row in cur.fetchall():
            affiliations.setdefault(int(row["content_item_id"]), []).append(dict(row))

        cur.execute(AUTHOR_COUNT_SQL, (date_from, date_until))
        author_counts = {int(r["content_item_id"]): int(r["n"]) for r in cur.fetchall()}

    stats = {
        "papers": 0,
        "with_quality": 0,
        "with_org": 0,
        "disagreements": 0,
        "written": 0,
    }
    rows: list[tuple] = []
    routing = quality_selection_reason_map(
        conn,
        date_from=date_from,
        date_until=date_until,
        gate_percentile=GATE_PERCENTILE,
    )

    for content_id, results in by_paper.items():
        stats["papers"] += 1

        screen = results.get("screen", {}).get("result") or {}
        quality = results.get("quality", {}).get("result") or {}
        domain_row = results.get("domain", {})
        subdomain_row = results.get("subdomain", {})
        audience_row = results.get("audience", {})
        application_row = results.get("application_domain", {})

        screen_score = _screen_score(screen) if screen else None

        org = organisation_score(affiliations.get(content_id, []))
        if org["status"] == "resolved":
            stats["with_org"] += 1

        quality_score = None
        final_score = None
        if quality:
            stats["with_quality"] += 1
            # Recompute from the stored dimensions so the boost is applied here,
            # not baked into the scoring stage's own row.
            try:
                composite = composite_score(quality, org_boost=org["org_boost"])
                quality_score = round(
                    float((quality.get("composite") or {}).get("quality", composite["quality"])), 1
                )
                final_score = round(composite["final"], 1)
            except (KeyError, TypeError, ValueError):
                stored = quality.get("composite") or {}
                quality_score = stored.get("quality")
                final_score = stored.get("final")

        disagreement = None
        if screen_score is not None and quality_score is not None:
            disagreement = round(abs(quality_score - screen_score), 2)
            if disagreement >= DISAGREEMENT_THRESHOLD:
                stats["disagreements"] += 1

        affiliation_status = (
            "resolved"
            if org["status"] == "resolved"
            else ("unresolved" if affiliations.get(content_id) else "no_evidence_supplied")
        )

        gate_passed = bool((screen.get("gate") or {}).get("passed")) if screen else False
        route = routing.get(content_id)
        if quality_score is not None:
            quality_status = "scored"
            selection_reason = "scored_quality_result_present"
        elif route is not None:
            if route.decision == "selected":
                # Selected by router but no quality row yet (pending paid run).
                quality_status = "not_selected"
                selection_reason = f"pending_quality_score:{route.reason}"
            elif route.decision == "not_selected":
                quality_status = "not_selected"
                selection_reason = route.reason
            else:
                quality_status = "skipped"
                selection_reason = route.reason
        elif gate_passed:
            quality_status = "not_selected"
            selection_reason = "screen_gate_passed_router_decision_unavailable"
        elif screen:
            quality_status = "skipped"
            selection_reason = "blocked_or_no_screen_gate_pass"
        else:
            quality_status = "skipped"
            selection_reason = "no_screen_result"

        rows.append(
            (
                content_id,
                (domain_row.get("result") or {}).get("domain"),
                json.dumps((subdomain_row.get("result") or {}).get("subdomains") or []),
                json.dumps((audience_row.get("result") or {}).get("audiences") or []),
                json.dumps((application_row.get("result") or {}).get("application_domains") or []),
                domain_row.get("confidence"),
                audience_row.get("confidence"),
                screen_score,
                quality_score,
                org["organisation_score"],
                org["org_boost"],
                0.0,  # person_boost: reserved for people-graph evidence, not yet scored
                final_score,
                org["organisation_id"],
                "resolved" if author_counts.get(content_id) else "no_authors",
                affiliation_status,
                quality_status,
                json.dumps(
                    {
                        "screen_dimensions": {k: screen.get(k) for k in SCREEN_DIMENSIONS},
                        "screen_gate": screen.get("gate"),
                        "quality_present": bool(quality),
                        "quality_status": quality_status,
                        "quality_selection_reason": selection_reason,
                        "quality_routing": route.as_dict() if route is not None else None,
                        "screen_quality_disagreement": disagreement,
                        "organisation": org,
                        "author_count": author_counts.get(content_id, 0),
                        "stage_version": STAGE_VERSION,
                        "policy_version": POLICY_VERSION,
                    },
                    default=str,
                ),
                run_id,
            )
        )

    if dry_run:
        return stats

    with conn.cursor() as cur:
        for row in rows:
            cur.execute(UPSERT_SQL, row)
            stats["written"] += 1
    conn.commit()
    return stats
