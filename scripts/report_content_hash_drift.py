#!/usr/bin/env python3
"""List papers whose content changed after their latest LLM result (no rescore).

Read-only. Reports per-stage counts and a dry-run cost to rescore mismatches.
Does not call the LLM.

  PYTHONPATH=src python3 scripts/report_content_hash_drift.py \\
    --from 2026-09-01 --until 2026-09-15 \\
    --out reports/review_fixes/content_hash_drift.json
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
    parser.add_argument("--from", dest="date_from", required=True)
    parser.add_argument("--until", dest="date_until", required=True)
    parser.add_argument(
        "--out",
        default=str(ROOT / "reports/review_fixes/content_hash_drift.json"),
    )
    args = parser.parse_args(argv)

    from paper_intelligence.common.config import (
        CLASSIFY_MODEL,
        QUALITY_MODEL,
        SCREEN_MODEL,
    )
    from paper_intelligence.db import connect
    from paper_intelligence.screen import stage as screen_stage
    from paper_intelligence.audience_domain import stage as audience_stage
    from paper_intelligence.quality import stage as quality_stage

    sql = """
        WITH latest AS (
            SELECT DISTINCT ON (r.content_item_id, r.task_type)
                r.content_item_id,
                r.task_type,
                r.input_content_hash,
                r.model,
                r.stage_version,
                r.prompt_version,
                r.policy_version,
                r.created_at,
                p.content_hash AS paper_content_hash,
                p.title,
                p.abstract,
                p.arxiv_id,
                p.arxiv_version
            FROM paper_intelligence.paper_classification_results r
            JOIN paper_intelligence.papers p ON p.paper_id = r.content_item_id
            WHERE p.published_at >= %s::timestamptz
              AND p.published_at < (%s::timestamptz + interval '1 day')
              AND r.task_type = ANY(%s)
            ORDER BY r.content_item_id, r.task_type, r.created_at DESC
        )
        SELECT *
        FROM latest
        WHERE input_content_hash IS NOT NULL
          AND paper_content_hash IS NOT NULL
          AND input_content_hash <> paper_content_hash
        ORDER BY content_item_id, task_type
    """

    with connect() as conn:
        with conn.cursor() as cur:
            try:
                cur.execute(sql, (args.date_from, args.date_until, list(LLM_TASKS)))
                drift_rows = [dict(r) for r in cur.fetchall()]
            except Exception as exc:
                print(
                    f"query failed (apply migration 016 + backfill?): {exc}",
                    file=sys.stderr,
                )
                return 2

            cur.execute(
                """
                SELECT COUNT(*) AS n
                FROM paper_intelligence.paper_content_hash_changes c
                JOIN paper_intelligence.papers p ON p.paper_id = c.paper_id
                WHERE p.published_at >= %s::timestamptz
                  AND p.published_at < (%s::timestamptz + interval '1 day')
                """,
                (args.date_from, args.date_until),
            )
            change_log_n = int(cur.fetchone()["n"])

        by_stage: dict[str, list[int]] = {}
        for row in drift_rows:
            by_stage.setdefault(row["task_type"], []).append(int(row["content_item_id"]))

        # Dry-run cost for unique papers needing rescore per paid stage family.
        screen_ids = sorted(set(by_stage.get("screen") or []))
        # audience_domain writes four task types; one LLM call covers all.
        audience_ids = sorted(
            set(by_stage.get("audience") or [])
            | set(by_stage.get("domain") or [])
            | set(by_stage.get("subdomain") or [])
            | set(by_stage.get("application_domain") or [])
        )
        quality_ids = sorted(set(by_stage.get("quality") or []))

        projections: dict[str, Any] = {}
        for label, ids, module, model in (
            ("screen", screen_ids, screen_stage, SCREEN_MODEL),
            ("audience_domain", audience_ids, audience_stage, CLASSIFY_MODEL),
            ("quality", quality_ids, quality_stage, QUALITY_MODEL),
        ):
            if not ids:
                projections[label] = {
                    "papers": 0,
                    "projected_cost_usd": 0.0,
                    "model": model,
                }
                continue
            stats = module.run_window(
                conn, ids, run_id="dry-run", stage_run_id="dry-run", dry_run=True
            )
            projections[label] = {
                "papers": len(ids),
                "projected_cost_usd": round(stats.cost_usd, 4),
                "model": model,
                "calls": stats.calls,
                "input_tokens": stats.input_tokens,
                "output_tokens": stats.output_tokens,
            }

    report = {
        "date_from": args.date_from,
        "date_until": args.date_until,
        "content_hash_change_log_rows": change_log_n,
        "drift_result_rows": len(drift_rows),
        "counts_by_stage": {k: len(set(v)) for k, v in by_stage.items()},
        "dry_run_rescore_projection": projections,
        "total_projected_usd": round(
            sum(float(p["projected_cost_usd"]) for p in projections.values()), 4
        ),
        "sample": [
            {
                "content_item_id": r["content_item_id"],
                "arxiv_id": r.get("arxiv_id"),
                "arxiv_version": r.get("arxiv_version"),
                "task_type": r["task_type"],
                "input_content_hash": r["input_content_hash"],
                "paper_content_hash": r["paper_content_hash"],
            }
            for r in drift_rows[:50]
        ],
        "note": "NULL input_content_hash legacy rows are NOT listed (treated as reusable).",
    }

    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(report, indent=2, default=str) + "\n", encoding="utf-8")

    md = out.with_suffix(".md")
    lines = [
        f"# Content-hash drift {args.date_from} → {args.date_until}",
        "",
        f"Change-log rows in window: **{change_log_n}**",
        f"Latest results with hash mismatch: **{len(drift_rows)}** row(s)",
        "",
        "## Counts by stage (distinct papers)",
        "",
    ]
    for stage, n in sorted(report["counts_by_stage"].items()):
        lines.append(f"- `{stage}`: {n}")
    if not report["counts_by_stage"]:
        lines.append("- (none)")
    lines += ["", "## Dry-run rescore cost (table estimate; not executed)", ""]
    for label, proj in projections.items():
        lines.append(
            f"- **{label}**: {proj['papers']} papers · "
            f"~${proj['projected_cost_usd']:.4f} · model `{proj['model']}`"
        )
    lines.append(f"- **total**: ~${report['total_projected_usd']:.4f}")
    lines.append("")
    lines.append("No papers were rescored.")
    md.write_text("\n".join(lines) + "\n", encoding="utf-8")

    print(f"wrote {out}")
    print(f"wrote {md}")
    print(f"drift_rows={len(drift_rows)} projected_rescore≈${report['total_projected_usd']:.4f}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
