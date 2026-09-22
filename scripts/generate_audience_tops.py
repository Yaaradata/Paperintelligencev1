#!/usr/bin/env python3
"""Audience-split top papers — manager-facing report.

List definitions (exclusive pools among quality-scored papers):

  TECH — for ML/AI builders and technical leads
    application_domains ⊆ {general_method, scientific_research} (or empty)
    AND audiences overlap {practitioner, technical_leadership, student}

  BUSINESS — for product / ops / risk / enterprise decision-makers
    audiences contains enterprise_adoption
    OR application_domains contains any sector other than
       general_method / scientific_research

This is intentional: raw `practitioner` alone covers ~99% of arXiv CS papers,
so it cannot define the tech list. Sector application + enterprise_adoption
defines business; pure method work defines tech.

Default deliverables from write_all_reports / run_pipeline:
  - tech_top_{N}_{from}_to_{until}.md
  - business_top_{N}_{from}_to_{until}.md
  - audience_top_{N}_{from}_to_{until}.md
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

from paper_intelligence.common.config import PI_USE_PAPERS_CATALOG


def _current_window_join() -> str:
    """Join paper_intelligence_current rows to the date window paper table."""
    if PI_USE_PAPERS_CATALOG:
        return (
            "JOIN paper_intelligence.papers ci ON ci.paper_id = c.content_item_id "
            "AND ci.published_at >= %s::timestamptz "
            "AND ci.published_at < (%s::timestamptz + interval '1 day')"
        )
    return (
        "JOIN research_radar.content_items ci ON ci.id = c.content_item_id "
        "AND ci.published_at >= %s::timestamptz "
        "AND ci.published_at < (%s::timestamptz + interval '1 day')"
    )


TECH_AUDIENCES = ("practitioner", "technical_leadership", "student")
BUSINESS_AUDIENCE = "enterprise_adoption"
METHOD_APPLICATIONS = ("general_method", "scientific_research")
BUSINESS_SENDABLE_MIN_PCT = 15.0

POOL_SQL = {
    # Method / systems papers for builders.
    "tech": """
        (
          audiences ?| ARRAY['practitioner','technical_leadership','student']
          AND NOT (
            audiences ? 'enterprise_adoption'
            OR EXISTS (
              SELECT 1 FROM jsonb_array_elements_text(c.application_domains) d
              WHERE d NOT IN ('general_method', 'scientific_research')
            )
          )
        )
    """,
    # Decision-maker papers: explicit enterprise label OR a real sector.
    "business": """
        (
          audiences ? 'enterprise_adoption'
          OR EXISTS (
            SELECT 1 FROM jsonb_array_elements_text(c.application_domains) d
            WHERE d NOT IN ('general_method', 'scientific_research')
          )
        )
    """,
}


def _table(headers: list[str], rows: list[list]) -> str:
    if not rows:
        return "_no rows_\n"
    out = [
        "| " + " | ".join(headers) + " |",
        "|" + "|".join("---" for _ in headers) + "|",
    ]
    for row in rows:
        out.append("| " + " | ".join("" if v is None else str(v) for v in row) + " |")
    return "\n".join(out) + "\n"


def _fmt_date(value) -> str:
    if value is None:
        return "—"
    if hasattr(value, "date"):
        return value.date().isoformat()
    text = str(value)
    return text[:10] if len(text) >= 10 else text


def _title(value: str | None) -> str:
    return (value or "").replace("|", "\\|").strip()


def fetch_pool(conn, *, date_from: str, date_until: str, pool: str, limit: int):
    if pool not in POOL_SQL:
        raise ValueError(f"unknown pool {pool!r}")
    join = _current_window_join()
    with conn.cursor() as cur:
        cur.execute(
            f"""
            SELECT
                c.content_item_id,
                ci.title,
                ci.published_at,
                c.final_score,
                c.quality_score,
                c.screen_score,
                c.organisation_score,
                c.org_boost,
                o.canonical_name AS organisation,
                c.domain,
                c.subdomains,
                c.audiences,
                c.application_domains,
                c.adjudication_json->'organisation' AS org_evidence,
                (
                    SELECT r.result_json->>'so_what'
                    FROM paper_intelligence.paper_classification_results r
                    WHERE r.content_item_id = c.content_item_id AND r.task_type = 'quality'
                    ORDER BY r.created_at DESC LIMIT 1
                ) AS so_what,
                (
                    SELECT r.result_json->>'reason_not_higher'
                    FROM paper_intelligence.paper_classification_results r
                    WHERE r.content_item_id = c.content_item_id AND r.task_type = 'quality'
                    ORDER BY r.created_at DESC LIMIT 1
                ) AS reason_not_higher,
                (
                    SELECT string_agg(DISTINCT o2.canonical_name, '; ' ORDER BY o2.canonical_name)
                    FROM paper_intelligence.paper_author_affiliations a
                    JOIN paper_intelligence.organisations o2 ON o2.id = a.organisation_id
                    WHERE a.content_item_id = c.content_item_id
                      AND a.organisation_id IS NOT NULL
                      AND COALESCE(a.confidence, 1) >= 0.6
                ) AS all_organisations
            FROM paper_intelligence.paper_intelligence_current c
            {join}
            LEFT JOIN paper_intelligence.organisations o ON o.id = c.top_organisation_id
            WHERE c.final_score IS NOT NULL
              AND {POOL_SQL[pool]}
            ORDER BY
                c.final_score DESC NULLS LAST,
                COALESCE(c.organisation_score, 0) DESC,
                COALESCE(c.quality_score, 0) DESC,
                c.content_item_id
            LIMIT %s
            """,
            (date_from, date_until, limit),
        )
        return [dict(r) for r in cur.fetchall()]


def coverage(conn, *, date_from: str, date_until: str) -> dict:
    join = _current_window_join()
    with conn.cursor() as cur:
        cur.execute(
            f"""
            SELECT
              COUNT(*) FILTER (WHERE final_score IS NOT NULL) AS quality_papers,
              COUNT(*) FILTER (
                WHERE final_score IS NOT NULL AND jsonb_array_length(audiences) > 0
              ) AS quality_with_audience,
              COUNT(*) FILTER (
                WHERE final_score IS NOT NULL AND {POOL_SQL['tech']}
              ) AS tech_pool,
              COUNT(*) FILTER (
                WHERE final_score IS NOT NULL AND {POOL_SQL['business']}
              ) AS business_pool,
              COUNT(*) FILTER (
                WHERE final_score IS NOT NULL AND audiences ? 'enterprise_adoption'
              ) AS enterprise_adoption_label,
              COUNT(*) FILTER (
                WHERE final_score IS NOT NULL
                  AND EXISTS (
                    SELECT 1 FROM jsonb_array_elements_text(application_domains) d
                    WHERE d NOT IN ('general_method', 'scientific_research')
                  )
              ) AS sector_application,
              MIN(ci.published_at)::date AS earliest_published,
              MAX(ci.published_at)::date AS latest_published
            FROM paper_intelligence.paper_intelligence_current c
            {join}
            """,
            (date_from, date_until),
        )
        return dict(cur.fetchone())


def provenance(conn) -> list[dict]:
    with conn.cursor() as cur:
        cur.execute(
            """
            SELECT l.model,
                   SPLIT_PART(e.endpoint, ':', 2) AS stage,
                   COUNT(*) AS calls,
                   ROUND(SUM(l.estimated_cost)::numeric, 4) AS cost_usd,
                   MAX(l.prompt_version) AS prompt_version
            FROM paper_intelligence.llm_requests l
            JOIN paper_intelligence.external_requests e ON e.request_id = l.request_id
            WHERE e.success
            GROUP BY 1, 2
            ORDER BY cost_usd DESC
            """
        )
        return [dict(r) for r in cur.fetchall()]


def _provenance_block(costs: list[dict]) -> list[str]:
    return [
        "## Provenance",
        "",
        _table(
            ["Model", "Stage", "Prompt", "Calls", "Cost"],
            [
                [
                    r["model"],
                    r["stage"],
                    r["prompt_version"] or "—",
                    r["calls"],
                    f"${r['cost_usd']}",
                ]
                for r in costs
            ],
        ),
        f"**Total LLM spend:** ${sum(float(r['cost_usd'] or 0) for r in costs):.4f}  ",
        "Quality: `openai/gpt-5.6-sol` · Screen/classify: `z-ai/glm-5.3-flash` · "
        "Affiliation: arXiv HTML + ROR + OpenAlex (no LLM).",
        "",
    ]


def _definitions_block() -> list[str]:
    return [
        "## Audience / list definitions",
        "",
        "These lists are **exclusive** among quality-scored papers:",
        "",
        "- **Tech** — method/systems papers for builders: application domain is only "
        "`general_method` / `scientific_research` (or empty), and audiences include "
        "practitioner / technical_leadership / student. Pure `practitioner` alone is "
        "**not** used as the tech filter (it matches almost every arXiv CS paper).",
        "- **Business** — decision-maker papers: `enterprise_adoption` in audiences, "
        "**or** a concrete sector application "
        "(healthcare, finance, cybersecurity, transport, energy, legal, etc.).",
        "",
        "Classifier audience labels still matter for provenance; the list split above "
        "uses application_domain because `enterprise_adoption` was under-assigned "
        "(~2.5%) while sector applications are common (~25%+).",
        "",
    ]


def _score_legend() -> list[str]:
    return [
        "## How to read Final vs Quality",
        "",
        "Final = quality × evidence_factor + org_boost. Final below Quality with "
        "org boost 0 means the evidence_factor discounted the rubric; that is correct.",
        "",
        "**Org standing** is a property of the organisation (constant across papers). "
        "**Org boost** is how much of that standing this paper's verified affiliation "
        "evidence earns.",
        "",
    ]


def section(
    title: str,
    rows: list[dict],
    *,
    sendable: bool,
    pool_size: int,
    quality_n: int,
    filter_blurb: str,
) -> list[str]:
    named = sum(1 for r in rows if r.get("organisation") or r.get("all_organisations"))
    parts = [
        f"## {title}",
        "",
        f"**Status:** {'SENDABLE' if sendable else 'NOT SENDABLE'}  ",
        f"Filter: {filter_blurb}  ",
        f"Pool: **{pool_size}** of {quality_n} quality papers "
        f"({(100.0 * pool_size / quality_n) if quality_n else 0:.1f}%)  ",
        f"Organisation named in this list: **{named}/{len(rows)}** "
        f"({(100.0 * named / len(rows)) if rows else 0:.0f}% affiliation coverage)",
        "",
        "Ranked by **final_score → organisation standing → quality_score**.",
        "",
        _table(
            [
                "#",
                "Title",
                "Published",
                "Final",
                "Quality",
                "Org standing",
                "Org boost",
                "Organisation(s)",
                "Audiences",
                "Application",
                "Domain",
                "Subdomains",
            ],
            [
                [
                    i,
                    _title(r["title"]),
                    _fmt_date(r.get("published_at")),
                    r["final_score"],
                    r["quality_score"],
                    r["organisation_score"] if r.get("organisation") else "—",
                    r["org_boost"] if r.get("organisation") else "—",
                    (r.get("all_organisations") or r.get("organisation") or "—"),
                    ", ".join(r["audiences"] or []) or "—",
                    ", ".join(r.get("application_domains") or []) or "—",
                    r["domain"] or "—",
                    ", ".join(r.get("subdomains") or []) or "—",
                ]
                for i, r in enumerate(rows, start=1)
            ],
        ),
        "",
    ]
    for i, r in enumerate(rows, start=1):
        org_ev = r.get("org_evidence") or {}
        if isinstance(org_ev, str):
            org_ev = {}
        orgs = r.get("all_organisations") or r.get("organisation") or "unresolved"
        apps = ", ".join(r.get("application_domains") or []) or "—"
        subs = ", ".join(r.get("subdomains") or []) or "—"
        parts.append(
            f"**{i}. {_title(r['title'])}**  \n"
            f"id {r['content_item_id']} · published {_fmt_date(r.get('published_at'))}  \n"
            f"Final {r['final_score']} (= quality {r['quality_score']} × evidence_factor "
            f"+ org_boost {r['org_boost'] or 0})  \n"
            f"Organisation(s): {orgs}"
            + (
                f" · standing {r['organisation_score']} · evidence "
                f"{org_ev.get('evidence_type') or '—'} @ "
                f"{org_ev.get('evidence_confidence') or '—'}"
                if r.get("organisation")
                else " · no verified affiliation evidence"
            )
            + "  \n"
            f"Audiences: {', '.join(r['audiences'] or []) or '—'} · "
            f"Application: {apps} · Domain: {r['domain'] or '—'} · "
            f"Subdomains: {subs}  \n"
            f"So what: {r.get('so_what') or '—'}  \n"
            f"Not higher: {r.get('reason_not_higher') or '—'}\n"
        )
    return parts


def _quality_model_header(conn, *, date_from: str, date_until: str) -> list[str]:
    from paper_intelligence.quality.model_policy import summarize_quality_models_for_window

    q_models = summarize_quality_models_for_window(
        conn, date_from=date_from, date_until=date_until
    )
    model_line = ", ".join(
        f"`{m}` ×{n}" for m, n in q_models["quality_models"].items()
    ) or "(none)"
    lines = [f"**Quality models:** {model_line}  "]
    if q_models.get("mixed_models"):
        lines.append(
            "⚠ **MIXED quality models** in scored pool — treat cross-cutover ranks with care."
        )
        lines.append("")
    stale = int((q_models.get("status_counts") or {}).get("stale_content") or 0)
    if stale:
        lines.append(f"**stale_content papers in window:** {stale}  ")
    return lines


def build_tech_report(conn, *, date_from: str, date_until: str, top_n: int) -> str:
    cov = coverage(conn, date_from=date_from, date_until=date_until)
    tech = fetch_pool(conn, date_from=date_from, date_until=date_until, pool="tech", limit=top_n)
    costs = provenance(conn)
    quality_n = int(cov["quality_papers"] or 0)
    tech_pool = int(cov["tech_pool"] or 0)
    pct = (100.0 * tech_pool / quality_n) if quality_n else 0.0
    parts = [
        f"# PaperIntelligence — Tech Top {top_n} (sendable)",
        "",
        f"**Requested window:** {date_from} → {date_until}  ",
        f"**Data scored:** {cov['earliest_published']} → {cov['latest_published']}  ",
        f"**Generated:** {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M UTC')}  ",
    ]
    parts += _quality_model_header(conn, date_from=date_from, date_until=date_until)
    parts += [
        f"**Pool:** {tech_pool}/{quality_n} ({pct:.1f}%) method/systems papers "
        f"(exclusive of business/sector papers).",
        "",
    ]
    parts += _definitions_block()
    parts += _score_legend()
    parts += _provenance_block(costs)
    parts += section(
        f"Top {top_n} — Tech people",
        tech,
        sendable=True,
        pool_size=tech_pool,
        quality_n=quality_n,
        filter_blurb="method papers (`general_method` / `scientific_research`) for builders",
    )
    return "\n".join(parts)


def build_business_report(conn, *, date_from: str, date_until: str, top_n: int) -> str:
    cov = coverage(conn, date_from=date_from, date_until=date_until)
    business = fetch_pool(
        conn, date_from=date_from, date_until=date_until, pool="business", limit=top_n
    )
    costs = provenance(conn)
    quality_n = int(cov["quality_papers"] or 0)
    biz_pool = int(cov["business_pool"] or 0)
    pct = (100.0 * biz_pool / quality_n) if quality_n else 0.0
    sendable = pct >= BUSINESS_SENDABLE_MIN_PCT and len(business) >= min(top_n, 10)
    header = (
        f"# PaperIntelligence — Business Top {top_n} (sendable)"
        if sendable
        else f"# PaperIntelligence — Business Top {top_n} (diagnostic)"
    )
    parts = [
        header,
        "",
        f"**Requested window:** {date_from} → {date_until}  ",
        f"**Data scored:** {cov['earliest_published']} → {cov['latest_published']}  ",
        f"**Generated:** {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M UTC')}  ",
    ]
    parts += _quality_model_header(conn, date_from=date_from, date_until=date_until)
    parts += [
        f"**Pool:** {biz_pool}/{quality_n} ({pct:.1f}%) — "
        f"`enterprise_adoption` labels={cov['enterprise_adoption_label']}, "
        f"sector applications={cov['sector_application']}.",
        "",
    ]
    parts += _definitions_block()
    parts += _score_legend()
    parts += _provenance_block(costs)
    parts += section(
        f"Top {top_n} — Business people",
        business,
        sendable=sendable,
        pool_size=biz_pool,
        quality_n=quality_n,
        filter_blurb="`enterprise_adoption` OR concrete sector application",
    )
    return "\n".join(parts)


def build_combined_report(conn, *, date_from: str, date_until: str, top_n: int) -> str:
    cov = coverage(conn, date_from=date_from, date_until=date_until)
    costs = provenance(conn)
    tech = fetch_pool(conn, date_from=date_from, date_until=date_until, pool="tech", limit=top_n)
    business = fetch_pool(
        conn, date_from=date_from, date_until=date_until, pool="business", limit=top_n
    )
    quality_n = int(cov["quality_papers"] or 0)
    tech_pool = int(cov["tech_pool"] or 0)
    biz_pool = int(cov["business_pool"] or 0)
    tech_pct = (100.0 * tech_pool / quality_n) if quality_n else 0.0
    biz_pct = (100.0 * biz_pool / quality_n) if quality_n else 0.0
    biz_sendable = biz_pct >= BUSINESS_SENDABLE_MIN_PCT
    generated = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")

    parts = [
        "# PaperIntelligence — Audience Top Lists",
        "",
        f"**Requested window:** {date_from} → {date_until}  ",
        f"**Data scored:** {cov['earliest_published']} → {cov['latest_published']}  ",
        f"**Generated:** {generated}",
        "",
    ]
    parts += _quality_model_header(conn, date_from=date_from, date_until=date_until)
    parts += [
        "",
        "## Verdict",
        "",
        f"- **Tech list:** {tech_pool}/{quality_n} = **{tech_pct:.1f}%** "
        f"(method/systems papers). Sendable.",
        f"- **Business list:** {biz_pool}/{quality_n} = **{biz_pct:.1f}%** "
        f"(enterprise_adoption label={cov['enterprise_adoption_label']}; "
        f"sector applications={cov['sector_application']}). "
        + ("Sendable." if biz_sendable else "Still thin — check sector classify quality."),
        "",
        "Earlier 99.5%/2.5% skew was from defining tech=`practitioner` and "
        "business=`enterprise_adoption` alone. That was wrong: arXiv CS tags almost "
        "everything practitioner, and the model under-uses enterprise_adoption.",
        "",
    ]
    parts += _definitions_block()
    parts += _score_legend()
    parts += [
        "## Coverage",
        "",
        _table(
            ["Metric", "Count"],
            [
                ["Quality-scored papers", quality_n],
                ["Tech pool (method papers)", f"{tech_pool} ({tech_pct:.1f}%)"],
                ["Business pool (sector / enterprise)", f"{biz_pool} ({biz_pct:.1f}%)"],
                ["Raw enterprise_adoption labels", cov["enterprise_adoption_label"]],
                ["Papers with sector application_domain", cov["sector_application"]],
            ],
        ),
        "",
    ]
    parts += _provenance_block(costs)
    parts += section(
        f"Top {top_n} — Tech people",
        tech,
        sendable=True,
        pool_size=tech_pool,
        quality_n=quality_n,
        filter_blurb="method papers for builders",
    )
    parts += section(
        f"Top {top_n} — Business people",
        business,
        sendable=biz_sendable,
        pool_size=biz_pool,
        quality_n=quality_n,
        filter_blurb="enterprise_adoption OR sector application",
    )
    return "\n".join(parts)


def write_all_reports(
    conn,
    *,
    date_from: str,
    date_until: str,
    top_n: int = 20,
    reports_dir: Path | None = None,
) -> dict[str, Path]:
    out_dir = Path(reports_dir or ROOT / "reports")
    out_dir.mkdir(parents=True, exist_ok=True)
    paths = {
        "tech": out_dir / f"tech_top_{top_n}_{date_from}_to_{date_until}.md",
        "business": out_dir / f"business_top_{top_n}_{date_from}_to_{date_until}.md",
        "combined": out_dir / f"audience_top_{top_n}_{date_from}_to_{date_until}.md",
    }
    paths["tech"].write_text(
        build_tech_report(conn, date_from=date_from, date_until=date_until, top_n=top_n),
        encoding="utf-8",
    )
    paths["business"].write_text(
        build_business_report(conn, date_from=date_from, date_until=date_until, top_n=top_n),
        encoding="utf-8",
    )
    paths["combined"].write_text(
        build_combined_report(conn, date_from=date_from, date_until=date_until, top_n=top_n),
        encoding="utf-8",
    )
    return paths


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Generate tech/business/combined audience top-N reports"
    )
    parser.add_argument("--from", dest="date_from", required=True)
    parser.add_argument("--until", dest="date_until", required=True)
    parser.add_argument("--top", type=int, default=20)
    parser.add_argument("--out", default=None)
    parser.add_argument("--tech-only", action="store_true")
    parser.add_argument("--business-only", action="store_true")
    parser.add_argument("--all", action="store_true")
    args = parser.parse_args(argv)

    from paper_intelligence.db import connect

    with connect() as conn:
        if args.tech_only:
            report = build_tech_report(
                conn, date_from=args.date_from, date_until=args.date_until, top_n=args.top
            )
            out = Path(
                args.out
                or ROOT / "reports" / f"tech_top_{args.top}_{args.date_from}_to_{args.date_until}.md"
            )
            out.parent.mkdir(parents=True, exist_ok=True)
            out.write_text(report, encoding="utf-8")
            print(f"report written: {out}")
            return 0
        if args.business_only:
            report = build_business_report(
                conn, date_from=args.date_from, date_until=args.date_until, top_n=args.top
            )
            out = Path(
                args.out
                or ROOT
                / "reports"
                / f"business_top_{args.top}_{args.date_from}_to_{args.date_until}.md"
            )
            out.parent.mkdir(parents=True, exist_ok=True)
            out.write_text(report, encoding="utf-8")
            print(f"report written: {out}")
            return 0

        paths = write_all_reports(
            conn, date_from=args.date_from, date_until=args.date_until, top_n=args.top
        )
        for kind, path in paths.items():
            print(f"report written ({kind}): {path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
