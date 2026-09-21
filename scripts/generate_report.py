#!/usr/bin/env python3
"""Generate the PaperIntelligence run report for a published_at window.

Reads only current state and provenance tables — no LLM calls, no cost.
"""

from __future__ import annotations

import argparse
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from paper_intelligence.catalog.report_sql import funnel_sql
from paper_intelligence.common.config import PI_USE_PAPERS_CATALOG


def _rows(conn, sql: str, params: tuple = ()) -> list[dict]:
    with conn.cursor() as cur:
        cur.execute(sql, params)
        return [dict(r) for r in cur.fetchall()]


def _one(conn, sql: str, params: tuple = ()) -> dict:
    rows = _rows(conn, sql, params)
    return rows[0] if rows else {}


def _table(headers: list[str], rows: list[list]) -> str:
    if not rows:
        return "_no rows_\n"
    out = ["| " + " | ".join(headers) + " |", "|" + "|".join("---" for _ in headers) + "|"]
    for row in rows:
        out.append("| " + " | ".join("" if v is None else str(v) for v in row) + " |")
    return "\n".join(out) + "\n"


def build_report(conn, *, date_from: str, date_until: str, top_n: int) -> str:
    window = (date_from, date_until)
    if PI_USE_PAPERS_CATALOG:
        def _pj(cid: str) -> str:
            return (
                f"JOIN paper_intelligence.papers ci ON ci.paper_id = {cid} "
                "AND ci.published_at >= %s::timestamptz "
                "AND ci.published_at < (%s::timestamptz + interval '1 day')"
            )
        title_col = "ci.title"
    else:
        def _pj(cid: str) -> str:
            return (
                f"JOIN research_radar.content_items ci ON ci.id = {cid} "
                "AND ci.published_at >= %s::timestamptz "
                "AND ci.published_at < (%s::timestamptz + interval '1 day')"
            )
        title_col = "ci.title"

    funnel = _one(conn, funnel_sql(), window)

    stage_counts = _rows(
        conn,
        f"""
        SELECT r.task_type, COUNT(DISTINCT r.content_item_id) AS papers, COUNT(*) AS rows
        FROM paper_intelligence.paper_classification_results r
        {_pj("r.content_item_id")}
        GROUP BY r.task_type ORDER BY papers DESC
        """,
        window,
    )

    gate = _one(
        conn,
        f"""
        SELECT
            COUNT(*) FILTER (WHERE (result_json->'gate'->>'passed')::boolean) AS passed,
            COUNT(*) FILTER (WHERE NOT (result_json->'gate'->>'passed')::boolean) AS failed
        FROM (
            SELECT DISTINCT ON (r.content_item_id) r.result_json
            FROM paper_intelligence.paper_classification_results r
            {_pj("r.content_item_id")}
            WHERE r.task_type = 'screen'
            ORDER BY r.content_item_id, r.created_at DESC
        ) latest
        """,
        window,
    )

    cost = _rows(
        conn,
        """
        SELECT l.model,
               SPLIT_PART(e.endpoint, ':', 2) AS stage,
               COUNT(*) AS calls,
               SUM(l.input_tokens) AS input_tokens,
               SUM(l.output_tokens) AS output_tokens,
               ROUND(SUM(l.estimated_cost)::numeric, 4) AS cost_usd
        FROM paper_intelligence.llm_requests l
        JOIN paper_intelligence.external_requests e ON e.request_id = l.request_id
        GROUP BY 1, 2 ORDER BY cost_usd DESC
        """,
    )

    external = _rows(
        conn,
        """
        SELECT provider,
               COUNT(*) AS requests,
               COUNT(*) FILTER (WHERE cache_hit) AS cache_hits,
               COUNT(*) FILTER (WHERE NOT success) AS failures
        FROM paper_intelligence.external_requests
        GROUP BY provider ORDER BY requests DESC
        """,
    )

    top = _rows(
        conn,
        f"""
        SELECT c.content_item_id, {title_col}, c.final_score, c.quality_score,
               c.screen_score, c.organisation_score, c.org_boost,
               o.canonical_name AS organisation, c.domain,
               c.adjudication_json
        FROM paper_intelligence.paper_intelligence_current c
        {_pj("c.content_item_id")}
        LEFT JOIN paper_intelligence.organisations o ON o.id = c.top_organisation_id
        WHERE c.final_score IS NOT NULL
        ORDER BY c.final_score DESC NULLS LAST, c.quality_score DESC NULLS LAST
        LIMIT %s
        """,
        (*window, top_n),
    )

    orgs = _rows(
        conn,
        f"""
        SELECT o.canonical_name, o.is_org_of_interest, o.priority,
               COUNT(DISTINCT c.content_item_id) AS papers,
               ROUND(AVG(c.organisation_score)::numeric, 2) AS avg_org_score,
               ROUND(MAX(c.final_score)::numeric, 1) AS best_final_score
        FROM paper_intelligence.paper_intelligence_current c
        JOIN paper_intelligence.organisations o ON o.id = c.top_organisation_id
        {_pj("c.content_item_id")}
        GROUP BY 1, 2, 3 ORDER BY papers DESC, best_final_score DESC NULLS LAST
        LIMIT 25
        """,
        window,
    )

    domains = _rows(
        conn,
        f"""
        SELECT c.domain, COUNT(*) AS papers,
               ROUND(AVG(c.quality_score)::numeric, 2) AS avg_quality
        FROM paper_intelligence.paper_intelligence_current c
        {_pj("c.content_item_id")}
        WHERE c.domain IS NOT NULL
        GROUP BY 1 ORDER BY papers DESC
        """,
        window,
    )

    affiliation = _one(
        conn,
        f"""
        SELECT
            COUNT(*) AS papers,
            COUNT(*) FILTER (WHERE affiliation_resolution_status = 'resolved') AS resolved,
            COUNT(*) FILTER (WHERE affiliation_resolution_status = 'unresolved') AS unresolved,
            COUNT(*) FILTER (WHERE affiliation_resolution_status = 'no_evidence_supplied')
                AS no_evidence,
            COUNT(*) FILTER (WHERE (adjudication_json->>'screen_quality_disagreement')::numeric
                >= 3) AS disagreements
        FROM paper_intelligence.paper_intelligence_current c
        {_pj("c.content_item_id")}
        """,
        window,
    )

    runs = _rows(
        conn,
        """
        SELECT s.stage_name, s.stage_version, s.status, s.items_input,
               s.items_success, s.items_failed,
               ROUND((s.duration_ms / 1000.0)::numeric, 1) AS seconds
        FROM paper_intelligence.stage_runs s
        ORDER BY s.started_at
        """,
    )

    generated = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    parts: list[str] = [
        "# PaperIntelligence v1 — Run Report",
        "",
        f"**Window:** {date_from} → {date_until} (published_at)  ",
        f"**Generated:** {generated}  ",
        "**Pipeline:** relevance (free) → normalize_authors (free) → screen → classify → "
        "quality → affiliation → adjudication",
        "",
        "## 1. Funnel",
        "",
        _table(
            ["Step", "Papers"],
            [
                ["arXiv ingested in window", funnel.get("ingested")],
                ["Rejected by relevance (free, pre-LLM)", funnel.get("relevance_rejected")],
                ["Entered paid stages", funnel.get("relevance_kept")],
                ["Passed screen gate", gate.get("passed")],
                ["Failed screen gate (scores kept)", gate.get("failed")],
            ],
        ),
        "Relevance runs first precisely so the paid stages never see the rejected papers.",
        "",
        "## 2. Stage coverage",
        "",
        _table(
            ["Task type", "Papers", "Result rows"],
            [[r["task_type"], r["papers"], r["rows"]] for r in stage_counts],
        ),
        "",
        _table(
            ["Stage run", "Version", "Status", "In", "OK", "Failed", "Seconds"],
            [
                [
                    r["stage_name"],
                    r["stage_version"],
                    r["status"],
                    r["items_input"],
                    r["items_success"],
                    r["items_failed"],
                    r["seconds"],
                ]
                for r in runs
            ],
        ),
        "",
        "## 3. Cost",
        "",
        _table(
            ["Model", "Stage", "Calls", "Input tokens", "Output tokens", "Cost (USD)"],
            [
                [
                    r["model"],
                    r["stage"],
                    r["calls"],
                    r["input_tokens"],
                    r["output_tokens"],
                    f"${r['cost_usd']}",
                ]
                for r in cost
            ],
        ),
        f"**Total LLM spend:** ${sum(float(r['cost_usd'] or 0) for r in cost):.4f}",
        "",
        _table(
            ["External provider", "Requests", "Cache hits", "Failures"],
            [[r["provider"], r["requests"], r["cache_hits"], r["failures"]] for r in external],
        ),
        "",
        f"## 4. Top {top_n} papers by final score",
        "",
        "Final score = blinded quality composite × evidence factor + organisation boost "
        "(capped at 0.5). The quality model never saw authors or affiliations.",
        "",
        _table(
            ["#", "Title", "Final", "Quality", "Screen", "Org score", "Boost", "Organisation", "Domain"],
            [
                [
                    index,
                    (r["title"] or "")[:70],
                    r["final_score"],
                    r["quality_score"],
                    r["screen_score"],
                    r["organisation_score"],
                    r["org_boost"],
                    r["organisation"] or "—",
                    r["domain"] or "—",
                ]
                for index, r in enumerate(top, start=1)
            ],
        ),
        "",
        "### Why these papers",
        "",
    ]

    for index, row in enumerate(top, start=1):
        adjudication = row.get("adjudication_json") or {}
        so_what = ""
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT result_json->>'so_what' AS so_what,
                       result_json->>'reason_not_higher' AS reason_not_higher
                FROM paper_intelligence.paper_classification_results
                WHERE content_item_id = %s AND task_type = 'quality'
                ORDER BY created_at DESC LIMIT 1
                """,
                (row["content_item_id"],),
            )
            detail = cur.fetchone()
        if detail:
            so_what = detail.get("so_what") or ""
            reason = detail.get("reason_not_higher") or ""
        else:
            reason = ""
        org = (adjudication.get("organisation") or {})
        parts.append(
            f"**{index}. {row['title']}** (id {row['content_item_id']}, "
            f"final {row['final_score']})  \n"
            f"So what: {so_what or '—'}  \n"
            f"Not higher because: {reason or '—'}  \n"
            f"Organisation evidence: {org.get('organisation_name') or '—'} "
            f"via {org.get('evidence_type') or 'none'} "
            f"(org score {org.get('organisation_score', 0)}, boost {org.get('org_boost', 0)})\n"
        )

    parts += [
        "",
        "## 5. Organisation leaderboard",
        "",
        "Organisation score is derived from verified affiliation evidence (paper "
        "affiliation, email domain, ROR, OpenAlex) and applied only after scoring.",
        "",
        _table(
            ["Organisation", "On watchlist", "Priority", "Papers", "Avg org score", "Best final"],
            [
                [
                    r["canonical_name"],
                    "yes" if r["is_org_of_interest"] else "no",
                    r["priority"],
                    r["papers"],
                    r["avg_org_score"],
                    r["best_final_score"],
                ]
                for r in orgs
            ],
        ),
        "",
        "## 6. Domain distribution",
        "",
        _table(
            ["Domain", "Papers", "Avg quality"],
            [[r["domain"], r["papers"], r["avg_quality"]] for r in domains],
        ),
        "",
        "## 7. Data quality",
        "",
        _table(
            ["Check", "Count"],
            [
                ["Papers in current state", affiliation.get("papers")],
                ["Affiliation resolved", affiliation.get("resolved")],
                ["Affiliation evidence present but ambiguous", affiliation.get("unresolved")],
                ["No affiliation evidence supplied", affiliation.get("no_evidence")],
                ["Screen/quality disagreement ≥ 3.0", affiliation.get("disagreements")],
            ],
        ),
        "",
        "Unresolved affiliations are reported, not hidden: unknown beats wrong, and "
        "every raw affiliation string is preserved for re-resolution.",
        "",
    ]

    return "\n".join(parts)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Generate the PaperIntelligence run report")
    parser.add_argument("--from", dest="date_from", required=True)
    parser.add_argument("--until", dest="date_until", required=True)
    parser.add_argument("--top", type=int, default=25)
    parser.add_argument("--out", default=None)
    args = parser.parse_args(argv)

    from paper_intelligence.db import connect

    with connect() as conn:
        report = build_report(
            conn, date_from=args.date_from, date_until=args.date_until, top_n=args.top
        )

    out_path = Path(
        args.out
        or ROOT / "reports" / f"paper_intelligence_{args.date_from}_to_{args.date_until}.md"
    )
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(report, encoding="utf-8")
    print(f"report written: {out_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
