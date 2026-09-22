#!/usr/bin/env python3
"""One-time pre-016 revision report (read-only; no rescore).

Legacy results (input_content_hash IS NULL) where papers.source_updated_at >
result.created_at — i.e. the paper was revised after the score was written,
but we have no content hash to prove it.

Counts per stage and per month, plus a dry-run rescore cost.

  PYTHONPATH=src python3 scripts/report_pre016_revision_drift.py \\
    --out reports/review_fixes/pre016_revision_drift.json
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

LLM_TASKS = ("screen", "audience", "domain", "subdomain", "application_domain", "quality")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--out",
        default=str(ROOT / "reports/review_fixes/pre016_revision_drift.json"),
    )
    parser.add_argument("--from", dest="date_from", default=None)
    parser.add_argument("--until", dest="date_until", default=None)
    args = parser.parse_args(argv)

    from paper_intelligence.common.config import (
        CLASSIFY_MODEL,
        SCREEN_MODEL,
    )
    from paper_intelligence.db import connect, fetch_papers
    from paper_intelligence.screen import stage as screen_stage
    from paper_intelligence.audience_domain import stage as audience_stage
    from paper_intelligence.quality import stage as quality_stage
    from paper_intelligence.quality.model_policy import group_ids_by_quality_model

    clauses = [
        "r.input_content_hash IS NULL",
        "p.source_updated_at IS NOT NULL",
        "p.source_updated_at > r.created_at",
        "r.task_type = ANY(%s)",
    ]
    params: list[Any] = [list(LLM_TASKS)]
    if args.date_from:
        clauses.append("p.published_at >= %s::timestamptz")
        params.append(args.date_from)
    if args.date_until:
        clauses.append("p.published_at < (%s::timestamptz + interval '1 day')")
        params.append(args.date_until)

    sql = f"""
        WITH latest AS (
            SELECT DISTINCT ON (r.content_item_id, r.task_type)
                r.content_item_id,
                r.task_type,
                r.created_at AS result_created_at,
                p.source_updated_at,
                p.published_at,
                date_trunc('month', p.published_at)::date AS published_month
            FROM paper_intelligence.paper_classification_results r
            JOIN paper_intelligence.papers p ON p.paper_id = r.content_item_id
            WHERE {" AND ".join(clauses)}
            ORDER BY r.content_item_id, r.task_type, r.created_at DESC
        )
        SELECT * FROM latest
        ORDER BY published_month, task_type, content_item_id
    """

    with connect() as conn:
        with conn.cursor() as cur:
            try:
                cur.execute(sql, params)
                rows = [dict(r) for r in cur.fetchall()]
            except Exception as exc:
                print(f"query failed: {exc}", file=sys.stderr)
                return 2

        by_stage: dict[str, set[int]] = {}
        by_month: dict[str, dict[str, set[int]]] = {}
        for row in rows:
            stage = row["task_type"]
            cid = int(row["content_item_id"])
            by_stage.setdefault(stage, set()).add(cid)
            month = str(row["published_month"])[:10]
            by_month.setdefault(month, {}).setdefault(stage, set()).add(cid)

        screen_ids = sorted(by_stage.get("screen") or [])
        audience_ids = sorted(
            (by_stage.get("audience") or set())
            | (by_stage.get("domain") or set())
            | (by_stage.get("subdomain") or set())
            | (by_stage.get("application_domain") or set())
        )
        quality_ids = sorted(by_stage.get("quality") or [])

        projections: dict[str, Any] = {}
        if screen_ids:
            stats = screen_stage.run_window(
                conn,
                screen_ids,
                run_id="dry-run",
                stage_run_id="dry-run",
                dry_run=True,
                model=SCREEN_MODEL,
            )
            projections["screen"] = {
                "papers": len(screen_ids),
                "projected_cost_usd": round(stats.cost_usd, 4),
                "model": SCREEN_MODEL,
            }
        if audience_ids:
            stats = audience_stage.run_window(
                conn,
                audience_ids,
                run_id="dry-run",
                stage_run_id="dry-run",
                dry_run=True,
                model=CLASSIFY_MODEL,
            )
            projections["audience_domain"] = {
                "papers": len(audience_ids),
                "projected_cost_usd": round(stats.cost_usd, 4),
                "model": CLASSIFY_MODEL,
            }
        if quality_ids:
            papers = fetch_papers(conn, quality_ids)
            groups = group_ids_by_quality_model(papers)
            q_total = 0.0
            q_detail = {}
            for model, ids in groups.items():
                stats = quality_stage.run_window(
                    conn,
                    ids,
                    run_id="dry-run",
                    stage_run_id="dry-run",
                    dry_run=True,
                    model=model,
                )
                q_detail[model] = {
                    "papers": len(ids),
                    "projected_cost_usd": round(stats.cost_usd, 4),
                }
                q_total += stats.cost_usd
            projections["quality"] = {
                "papers": len(quality_ids),
                "projected_cost_usd": round(q_total, 4),
                "by_model": q_detail,
            }

    report = {
        "date_from": args.date_from,
        "date_until": args.date_until,
        "definition": (
            "latest result per (paper, task) with input_content_hash IS NULL "
            "AND papers.source_updated_at > result.created_at"
        ),
        "legacy_revision_result_rows": len(rows),
        "counts_by_stage": {k: len(v) for k, v in sorted(by_stage.items())},
        "counts_by_month": {
            month: {stage: len(ids) for stage, ids in sorted(stages.items())}
            for month, stages in sorted(by_month.items())
        },
        "dry_run_rescore_projection": projections,
        "total_projected_usd": round(
            sum(float(p["projected_cost_usd"]) for p in projections.values()), 4
        ),
        "note": "Report only — no rescore executed.",
    }

    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(report, indent=2, default=str) + "\n", encoding="utf-8")

    md = out.with_suffix(".md")
    lines = [
        "# Pre-016 revision drift (legacy NULL content hash)",
        "",
        report["definition"],
        "",
        f"Matching latest result rows: **{len(rows)}**",
        f"Dry-run rescore total: **~${report['total_projected_usd']:.4f}**",
        "",
        "## By stage (distinct papers)",
        "",
    ]
    for stage, n in report["counts_by_stage"].items():
        lines.append(f"- `{stage}`: {n}")
    if not report["counts_by_stage"]:
        lines.append("- (none)")
    lines += ["", "## By published month", ""]
    for month, stages in report["counts_by_month"].items():
        parts = ", ".join(f"{s}={n}" for s, n in stages.items())
        lines.append(f"- **{month}**: {parts}")
    if not report["counts_by_month"]:
        lines.append("- (none)")
    lines += ["", "## Dry-run rescore cost (not executed)", ""]
    for label, proj in projections.items():
        lines.append(
            f"- **{label}**: {proj['papers']} papers · ~${proj['projected_cost_usd']:.4f}"
        )
    lines.append("")
    lines.append("No papers were rescored.")
    md.write_text("\n".join(lines) + "\n", encoding="utf-8")

    print(f"wrote {out}")
    print(f"wrote {md}")
    print(
        f"legacy_revision_rows={len(rows)} "
        f"projected_rescore≈${report['total_projected_usd']:.4f}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
