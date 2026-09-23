#!/usr/bin/env python3
"""Audience-split top papers — manager-facing report.

AUDIENCE_POLICY=v001 (default until 7c) — exclusive pools among quality-scored papers:

  TECH — for ML/AI builders and technical leads
    application_domains ⊆ {general_method, scientific_research} (or empty)
    AND audiences overlap {practitioner, technical_leadership, student}

  BUSINESS / PRODUCT — for product / ops / risk / enterprise decision-makers
    audiences contains enterprise_adoption
    OR application_domains contains any sector other than
       general_method / scientific_research

AUDIENCE_POLICY=v002 — independent seat-score pools (a paper may be in both):

  TECH    = tech_relevance >= TECH_POOL_MIN (provisional default 6.0 until 7b)
  PRODUCT = product_relevance >= PRODUCT_POOL_MIN
  Only rows with audience_policy_version=v002 participate; v001 rows ignored.

Ranking (both policies): quality_score DESC, then final_score DESC.
Org boost and final_score are columns; organisation name is a label.
"""

from __future__ import annotations

import argparse
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from paper_intelligence.common.config import (
    AUDIENCE_POLICY,
    PI_USE_PAPERS_CATALOG,
    PRODUCT_POOL_MIN,
    TECH_POOL_MIN,
)


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


BUSINESS_SENDABLE_MIN_PCT = 15.0

# SQL fragments keyed by (policy, pool). product is the v002 name; business is
# retained as an alias for v001 / file-compat paths.
POOL_SQL = {
    ("v001", "tech"): """
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
    ("v001", "business"): """
        (
          audiences ? 'enterprise_adoption'
          OR EXISTS (
            SELECT 1 FROM jsonb_array_elements_text(c.application_domains) d
            WHERE d NOT IN ('general_method', 'scientific_research')
          )
        )
    """,
    ("v001", "product"): """
        (
          audiences ? 'enterprise_adoption'
          OR EXISTS (
            SELECT 1 FROM jsonb_array_elements_text(c.application_domains) d
            WHERE d NOT IN ('general_method', 'scientific_research')
          )
        )
    """,
    ("v002", "tech"): """
        (
          c.audience_policy_version = 'v002'
          AND c.tech_relevance IS NOT NULL
          AND c.tech_relevance >= %s
        )
    """,
    ("v002", "product"): """
        (
          c.audience_policy_version = 'v002'
          AND c.product_relevance IS NOT NULL
          AND c.product_relevance >= %s
        )
    """,
    ("v002", "business"): """
        (
          c.audience_policy_version = 'v002'
          AND c.product_relevance IS NOT NULL
          AND c.product_relevance >= %s
        )
    """,
}


def _policy() -> str:
    raw = os.getenv("AUDIENCE_POLICY", AUDIENCE_POLICY).strip().lower()
    return raw if raw in {"v001", "v002"} else "v001"


def _pool_predicate(pool: str, policy: str) -> tuple[str, list]:
    key = (policy, pool)
    if key not in POOL_SQL:
        raise ValueError(f"unknown pool/policy {pool!r}/{policy!r}")
    sql = POOL_SQL[key]
    if policy == "v002":
        threshold = TECH_POOL_MIN if pool == "tech" else PRODUCT_POOL_MIN
        return sql, [threshold]
    return sql, []


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
    policy = _policy()
    predicate, extra = _pool_predicate(pool, policy)
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
                c.tech_relevance,
                c.product_relevance,
                c.audience_policy_version,
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
              AND {predicate}
            ORDER BY
                c.quality_score DESC NULLS LAST,
                c.final_score DESC NULLS LAST,
                c.content_item_id
            LIMIT %s
            """,
            (date_from, date_until, *extra, limit),
        )
        return [dict(r) for r in cur.fetchall()]


def coverage(conn, *, date_from: str, date_until: str) -> dict:
    policy = _policy()
    tech_pred, tech_extra = _pool_predicate("tech", policy)
    prod_pool = "product" if policy == "v002" else "business"
    prod_pred, prod_extra = _pool_predicate(prod_pool, policy)
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
                WHERE final_score IS NOT NULL AND {tech_pred}
              ) AS tech_pool,
              COUNT(*) FILTER (
                WHERE final_score IS NOT NULL AND {prod_pred}
              ) AS product_pool,
              COUNT(*) FILTER (
                WHERE final_score IS NOT NULL AND {prod_pred}
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
              COUNT(*) FILTER (
                WHERE final_score IS NOT NULL AND c.audience_policy_version = 'v002'
              ) AS v002_scored,
              MIN(ci.published_at)::date AS earliest_published,
              MAX(ci.published_at)::date AS latest_published
            FROM paper_intelligence.paper_intelligence_current c
            {join}
            """,
            (date_from, date_until, *tech_extra, *prod_extra, *prod_extra),
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
        "Quality: date-mapped Sol/Terra · Screen/classify: `z-ai/glm-5.3-flash` · "
        "Affiliation: arXiv HTML + ROR + OpenAlex (no LLM).",
        "",
    ]


def _definitions_block() -> list[str]:
    policy = _policy()
    if policy == "v002":
        return [
            "## Seat / list definitions",
            "",
            f"**AUDIENCE_POLICY=v002** (thresholds provisional until 7b: "
            f"TECH_POOL_MIN={TECH_POOL_MIN}, PRODUCT_POOL_MIN={PRODUCT_POOL_MIN}).",
            "",
            "- **Tech** — `tech_relevance >= TECH_POOL_MIN` (audience_policy_version=v002).",
            "- **Product** — `product_relevance >= PRODUCT_POOL_MIN` (same). "
            "A paper may appear in **both** pools.",
            "- Sector `application_domain` alone does **not** raise product pool membership.",
            "- v001 / legacy audience-label rows are ignored by these pools.",
            "",
        ]
    return [
        "## Audience / list definitions",
        "",
        "These lists are **exclusive** among quality-scored papers "
        "(AUDIENCE_POLICY=v001):",
        "",
        "- **Tech** — method/systems papers for builders: application domain is only "
        "`general_method` / `scientific_research` (or empty), and audiences include "
        "practitioner / technical_leadership / student. Pure `practitioner` alone is "
        "**not** used as the tech filter (it matches almost every arXiv CS paper).",
        "- **Product (business)** — decision-maker papers: `enterprise_adoption` in "
        "audiences, **or** a concrete sector application "
        "(healthcare, finance, cybersecurity, transport, energy, legal, etc.).",
        "",
    ]


def _score_legend() -> list[str]:
    return [
        "## How to read Quality vs Final",
        "",
        "Lists are ranked by **quality_score** (then final_score). "
        "Final = quality × evidence_factor + org_boost. Final below Quality with "
        "org boost 0 means the evidence_factor discounted the rubric; that is correct.",
        "",
        "**Org standing** is a property of the organisation (constant across papers). "
        "**Org boost** is how much of that standing this paper's verified affiliation "
        "evidence earns. Org name is shown as a label, not a sort key.",
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
    policy = _policy()
    named = sum(1 for r in rows if r.get("organisation") or r.get("all_organisations"))
    headers = [
        "#",
        "Title",
        "Published",
        "Quality",
        "Org boost",
        "Final",
        "Organisation",
        "Domain",
    ]
    if policy == "v002":
        headers[7:7] = ["Tech rel", "Product rel"]
    else:
        headers[7:7] = ["Audiences", "Application"]

    table_rows = []
    for i, r in enumerate(rows, start=1):
        org_label = r.get("all_organisations") or r.get("organisation") or "—"
        base = [
            i,
            _title(r["title"]),
            _fmt_date(r.get("published_at")),
            r["quality_score"],
            r["org_boost"] if r.get("organisation") else "—",
            r["final_score"],
            org_label,
        ]
        if policy == "v002":
            base.extend(
                [
                    r.get("tech_relevance") if r.get("tech_relevance") is not None else "—",
                    r.get("product_relevance")
                    if r.get("product_relevance") is not None
                    else "—",
                ]
            )
        else:
            base.extend(
                [
                    ", ".join(r["audiences"] or []) or "—",
                    ", ".join(r.get("application_domains") or []) or "—",
                ]
            )
        base.append(r["domain"] or "—")
        table_rows.append(base)

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
        "Ranked by **quality_score → final_score** "
        "(org_boost / final shown as columns; org name as label).",
        "",
        _table(headers, table_rows),
        "",
    ]
    for i, r in enumerate(rows, start=1):
        org_ev = r.get("org_evidence") or {}
        if isinstance(org_ev, str):
            org_ev = {}
        orgs = r.get("all_organisations") or r.get("organisation") or "unresolved"
        apps = ", ".join(r.get("application_domains") or []) or "—"
        if policy == "v002":
            seat_line = (
                f"Tech relevance: {r.get('tech_relevance') if r.get('tech_relevance') is not None else '—'} · "
                f"Product relevance: {r.get('product_relevance') if r.get('product_relevance') is not None else '—'} · "
            )
        else:
            seat_line = f"Audiences: {', '.join(r['audiences'] or []) or '—'} · "
        parts.append(
            f"**{i}. {_title(r['title'])}**  \n"
            f"id {r['content_item_id']} · published {_fmt_date(r.get('published_at'))}  \n"
            f"Quality {r['quality_score']} · org_boost {r['org_boost'] or 0} · "
            f"Final {r['final_score']}  \n"
            f"Organisation(s): {orgs}"
            + (
                f" · standing {r['organisation_score']} · evidence "
                f"{org_ev.get('evidence_type') or '—'} @ "
                f"{org_ev.get('evidence_confidence') or '—'}"
                if r.get("organisation")
                else " · no verified affiliation evidence"
            )
            + "  \n"
            + seat_line
            + f"Application: {apps} · Domain: {r['domain'] or '—'}  \n"
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
    lines.append(f"**AUDIENCE_POLICY:** `{_policy()}`  ")
    return lines


def build_tech_report(conn, *, date_from: str, date_until: str, top_n: int) -> str:
    cov = coverage(conn, date_from=date_from, date_until=date_until)
    tech = fetch_pool(conn, date_from=date_from, date_until=date_until, pool="tech", limit=top_n)
    costs = provenance(conn)
    quality_n = int(cov["quality_papers"] or 0)
    tech_pool = int(cov["tech_pool"] or 0)
    pct = (100.0 * tech_pool / quality_n) if quality_n else 0.0
    policy = _policy()
    filter = (
        f"`tech_relevance >= {TECH_POOL_MIN}` (v002)"
        if policy == "v002"
        else "method papers (`general_method` / `scientific_research`) for builders"
    )
    parts = [
        f"# PaperIntelligence — Tech Top {top_n} (sendable)",
        "",
        f"**Requested window:** {date_from} → {date_until}  ",
        f"**Data scored:** {cov['earliest_published']} → {cov['latest_published']}  ",
        f"**Generated:** {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M UTC')}  ",
    ]
    parts += _quality_model_header(conn, date_from=date_from, date_until=date_until)
    parts += [
        f"**Pool:** {tech_pool}/{quality_n} ({pct:.1f}%) tech-seat / method papers.",
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
        filter_blurb=filter,
    )
    return "\n".join(parts)


def build_product_report(conn, *, date_from: str, date_until: str, top_n: int) -> str:
    """Product top-N (v002 name). Under v001 this is the former business pool."""
    cov = coverage(conn, date_from=date_from, date_until=date_until)
    policy = _policy()
    pool_name = "product" if policy == "v002" else "business"
    product = fetch_pool(
        conn, date_from=date_from, date_until=date_until, pool=pool_name, limit=top_n
    )
    costs = provenance(conn)
    quality_n = int(cov["quality_papers"] or 0)
    prod_pool = int(cov.get("product_pool") or cov.get("business_pool") or 0)
    pct = (100.0 * prod_pool / quality_n) if quality_n else 0.0
    sendable = pct >= BUSINESS_SENDABLE_MIN_PCT and len(product) >= min(top_n, 10)
    label = "Product" if policy == "v002" else "Business"
    filter = (
        f"`product_relevance >= {PRODUCT_POOL_MIN}` (v002)"
        if policy == "v002"
        else "`enterprise_adoption` OR concrete sector application"
    )
    header = (
        f"# PaperIntelligence — {label} Top {top_n} (sendable)"
        if sendable
        else f"# PaperIntelligence — {label} Top {top_n} (diagnostic)"
    )
    parts = [
        header,
        "",
        f"**Requested window:** {date_from} → {date_until}  ",
        f"**Data scored:** {cov['earliest_published']} → {cov['latest_published']}  ",
        f"**Generated:** {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M UTC')}  ",
    ]
    parts += _quality_model_header(conn, date_from=date_from, date_until=date_until)
    if policy == "v002":
        parts += [
            f"**Pool:** {prod_pool}/{quality_n} ({pct:.1f}%) — "
            f"v002 scored={cov.get('v002_scored')}.",
            "",
        ]
    else:
        parts += [
            f"**Pool:** {prod_pool}/{quality_n} ({pct:.1f}%) — "
            f"`enterprise_adoption` labels={cov['enterprise_adoption_label']}, "
            f"sector applications={cov['sector_application']}.",
            "",
        ]
    parts += _definitions_block()
    parts += _score_legend()
    parts += _provenance_block(costs)
    parts += section(
        f"Top {top_n} — {label} people",
        product,
        sendable=sendable,
        pool_size=prod_pool,
        quality_n=quality_n,
        filter_blurb=filter,
    )
    return "\n".join(parts)


# Compat alias
build_business_report = build_product_report


def build_combined_report(conn, *, date_from: str, date_until: str, top_n: int) -> str:
    cov = coverage(conn, date_from=date_from, date_until=date_until)
    costs = provenance(conn)
    policy = _policy()
    tech = fetch_pool(conn, date_from=date_from, date_until=date_until, pool="tech", limit=top_n)
    prod_pool_name = "product" if policy == "v002" else "business"
    product = fetch_pool(
        conn, date_from=date_from, date_until=date_until, pool=prod_pool_name, limit=top_n
    )
    quality_n = int(cov["quality_papers"] or 0)
    tech_pool = int(cov["tech_pool"] or 0)
    prod_pool = int(cov.get("product_pool") or cov.get("business_pool") or 0)
    tech_pct = (100.0 * tech_pool / quality_n) if quality_n else 0.0
    prod_pct = (100.0 * prod_pool / quality_n) if quality_n else 0.0
    prod_sendable = prod_pct >= BUSINESS_SENDABLE_MIN_PCT
    generated = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    label = "Product" if policy == "v002" else "Business"

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
        f"- **Tech list:** {tech_pool}/{quality_n} = **{tech_pct:.1f}%**. Sendable.",
        f"- **{label} list:** {prod_pool}/{quality_n} = **{prod_pct:.1f}%**. "
        + ("Sendable." if prod_sendable else "Still thin — check classify / thresholds."),
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
                ["Tech pool", f"{tech_pool} ({tech_pct:.1f}%)"],
                [f"{label} pool", f"{prod_pool} ({prod_pct:.1f}%)"],
                ["Raw enterprise_adoption labels", cov["enterprise_adoption_label"]],
                ["Papers with sector application_domain", cov["sector_application"]],
                ["v002 seat-scored", cov.get("v002_scored")],
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
        filter_blurb="tech seat / method papers",
    )
    parts += section(
        f"Top {top_n} — {label} people",
        product,
        sendable=prod_sendable,
        pool_size=prod_pool,
        quality_n=quality_n,
        filter_blurb="product seat / enterprise+sector",
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
    product_path = out_dir / f"product_top_{top_n}_{date_from}_to_{date_until}.md"
    business_path = out_dir / f"business_top_{top_n}_{date_from}_to_{date_until}.md"
    paths = {
        "tech": out_dir / f"tech_top_{top_n}_{date_from}_to_{date_until}.md",
        "product": product_path,
        "business": business_path,
        "combined": out_dir / f"audience_top_{top_n}_{date_from}_to_{date_until}.md",
    }
    paths["tech"].write_text(
        build_tech_report(conn, date_from=date_from, date_until=date_until, top_n=top_n),
        encoding="utf-8",
    )
    product_body = build_product_report(
        conn, date_from=date_from, date_until=date_until, top_n=top_n
    )
    product_path.write_text(product_body, encoding="utf-8")
    # Compat: also write business_ filename (same body).
    business_path.write_text(product_body, encoding="utf-8")
    paths["combined"].write_text(
        build_combined_report(conn, date_from=date_from, date_until=date_until, top_n=top_n),
        encoding="utf-8",
    )
    return paths


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Generate tech/product/combined audience top-N reports"
    )
    parser.add_argument("--from", dest="date_from", required=True)
    parser.add_argument("--until", dest="date_until", required=True)
    parser.add_argument("--top", type=int, default=20)
    parser.add_argument("--out", default=None)
    parser.add_argument("--tech-only", action="store_true")
    parser.add_argument("--business-only", action="store_true")
    parser.add_argument("--product-only", action="store_true")
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
        if args.business_only or args.product_only:
            report = build_product_report(
                conn, date_from=args.date_from, date_until=args.date_until, top_n=args.top
            )
            default_name = (
                f"product_top_{args.top}_{args.date_from}_to_{args.date_until}.md"
                if args.product_only or _policy() == "v002"
                else f"business_top_{args.top}_{args.date_from}_to_{args.date_until}.md"
            )
            out = Path(args.out or ROOT / "reports" / default_name)
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
