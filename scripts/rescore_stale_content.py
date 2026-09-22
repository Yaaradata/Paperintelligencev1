#!/usr/bin/env python3
"""Rescore papers whose latest LLM result hash mismatches papers.content_hash.

Dry-run by default. Respects --max-cost-usd and --allow-paid.
Only rescored papers appear in the drift report for the window (or --drift-json).

  PYTHONPATH=src python3 scripts/rescore_stale_content.py \\
    --from 2026-09-01 --until 2026-09-15

  PYTHONPATH=src python3 scripts/rescore_stale_content.py \\
    --from 2026-09-01 --until 2026-09-15 \\
    --only-editorial --allow-paid --max-cost-usd 5
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


def _load_drift_ids(
    conn,
    *,
    date_from: str,
    date_until: str,
    drift_json: Path | None,
) -> dict[str, list[int]]:
    if drift_json is not None:
        data = json.loads(drift_json.read_text(encoding="utf-8"))
        counts = data.get("counts_by_stage") or {}
        # Prefer explicit id lists from sample+full if present; else re-query.
        if data.get("ids_by_stage"):
            return {k: [int(x) for x in v] for k, v in data["ids_by_stage"].items()}
        # Fall through to DB using window from file if present.
        date_from = data.get("date_from") or date_from
        date_until = data.get("date_until") or date_until

    sql = """
        WITH latest AS (
            SELECT DISTINCT ON (r.content_item_id, r.task_type)
                r.content_item_id,
                r.task_type,
                r.input_content_hash,
                p.content_hash AS paper_content_hash
            FROM paper_intelligence.paper_classification_results r
            JOIN paper_intelligence.papers p ON p.paper_id = r.content_item_id
            WHERE p.published_at >= %s::timestamptz
              AND p.published_at < (%s::timestamptz + interval '1 day')
              AND r.task_type = ANY(%s)
            ORDER BY r.content_item_id, r.task_type, r.created_at DESC
        )
        SELECT content_item_id, task_type
        FROM latest
        WHERE input_content_hash IS NOT NULL
          AND paper_content_hash IS NOT NULL
          AND input_content_hash <> paper_content_hash
    """
    by_stage: dict[str, list[int]] = {}
    with conn.cursor() as cur:
        cur.execute(sql, (date_from, date_until, list(LLM_TASKS)))
        for row in cur.fetchall():
            by_stage.setdefault(row["task_type"], []).append(int(row["content_item_id"]))
    return {k: sorted(set(v)) for k, v in by_stage.items()}


def _editorial_ids(conn, *, date_from: str, date_until: str) -> set[int]:
    """Papers quality-selected or appearing in newsletter/LinkedIn selections."""
    ids: set[int] = set()
    with conn.cursor() as cur:
        cur.execute(
            """
            SELECT content_item_id
            FROM paper_intelligence.paper_intelligence_current c
            JOIN paper_intelligence.papers p ON p.paper_id = c.content_item_id
            WHERE p.published_at >= %s::timestamptz
              AND p.published_at < (%s::timestamptz + interval '1 day')
              AND (
                c.quality_status IN ('scored', 'pending', 'failed', 'stale_content')
                OR c.final_score IS NOT NULL
                OR COALESCE(c.adjudication_json->>'quality_selection_reason', '')
                     LIKE 'selected%%'
                OR COALESCE(c.adjudication_json->'quality_routing'->>'decision', '')
                     = 'selected'
              )
            """,
            (date_from, date_until),
        )
        ids.update(int(r["content_item_id"]) for r in cur.fetchall())

        # Newsletter / LinkedIn selection artifacts if tables exist.
        for table, col in (
            ("paper_intelligence.newsletter_selections", "content_item_id"),
            ("paper_intelligence.linkedin_selections", "content_item_id"),
            ("paper_intelligence.editorial_selections", "content_item_id"),
        ):
            try:
                cur.execute(
                    f"""
                    SELECT DISTINCT {col} AS content_item_id
                    FROM {table}
                    WHERE {col} IS NOT NULL
                    """
                )
                ids.update(int(r["content_item_id"]) for r in cur.fetchall())
            except Exception:
                conn.rollback()
    return ids


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--from", dest="date_from", required=True)
    parser.add_argument("--until", dest="date_until", required=True)
    parser.add_argument(
        "--drift-json",
        type=Path,
        default=None,
        help="optional prior report_content_hash_drift.py JSON",
    )
    parser.add_argument(
        "--only-editorial",
        action="store_true",
        help="limit to quality-selected / newsletter / LinkedIn papers",
    )
    parser.add_argument("--max-cost-usd", type=float, default=None)
    parser.add_argument("--allow-paid", action="store_true")
    parser.add_argument(
        "--stages",
        default="screen,audience_domain,quality",
        help="comma list of run_stage names to rescore (default all paid)",
    )
    args = parser.parse_args(argv)

    from paper_intelligence.common.budget import resolve_max_cost_usd
    from paper_intelligence.db import connect
    from paper_intelligence.screen import stage as screen_stage
    from paper_intelligence.audience_domain import stage as audience_stage
    from paper_intelligence.quality import stage as quality_stage
    from paper_intelligence.quality.model_policy import (
        group_ids_by_quality_model,
    )
    from paper_intelligence.db import fetch_papers
    from paper_intelligence.common.config import SCREEN_MODEL, CLASSIFY_MODEL

    max_cost = resolve_max_cost_usd(args.max_cost_usd)
    stages = [s.strip() for s in args.stages.split(",") if s.strip()]

    with connect() as conn:
        by_stage = _load_drift_ids(
            conn,
            date_from=args.date_from,
            date_until=args.date_until,
            drift_json=args.drift_json,
        )
        editorial: set[int] | None = None
        if args.only_editorial:
            editorial = _editorial_ids(
                conn, date_from=args.date_from, date_until=args.date_until
            )

        screen_ids = sorted(set(by_stage.get("screen") or []))
        audience_ids = sorted(
            set(by_stage.get("audience") or [])
            | set(by_stage.get("domain") or [])
            | set(by_stage.get("subdomain") or [])
            | set(by_stage.get("application_domain") or [])
        )
        quality_ids = sorted(set(by_stage.get("quality") or []))

        if editorial is not None:
            screen_ids = [i for i in screen_ids if i in editorial]
            audience_ids = [i for i in audience_ids if i in editorial]
            quality_ids = [i for i in quality_ids if i in editorial]

        plan: list[tuple[str, list[int], Any, str | None]] = []
        if "screen" in stages and screen_ids:
            plan.append(("screen", screen_ids, screen_stage, SCREEN_MODEL))
        if "audience_domain" in stages and audience_ids:
            plan.append(("audience_domain", audience_ids, audience_stage, CLASSIFY_MODEL))
        if "quality" in stages and quality_ids:
            papers = fetch_papers(conn, quality_ids)
            groups = group_ids_by_quality_model(papers)
            for model, ids in groups.items():
                plan.append(("quality", ids, quality_stage, model))

        projections: dict[str, Any] = {}
        total_proj = 0.0
        for label, ids, module, model in plan:
            key = f"{label}:{model}" if label == "quality" else label
            stats = module.run_window(
                conn,
                ids,
                run_id="dry-run",
                stage_run_id="dry-run",
                dry_run=True,
                model=model,
            )
            projections[key] = {
                "papers": len(ids),
                "projected_cost_usd": round(stats.cost_usd, 4),
                "model": model,
                "ids": ids,
            }
            total_proj += stats.cost_usd

        print(
            f"stale_content rescore plan: dry_run={not args.allow_paid} "
            f"only_editorial={args.only_editorial} "
            f"projected≈${total_proj:.4f} cap={max_cost}",
            flush=True,
        )
        for key, proj in projections.items():
            print(
                f"  {key}: {proj['papers']} papers · ~${proj['projected_cost_usd']:.4f} "
                f"· model={proj['model']}",
                flush=True,
            )

        if not args.allow_paid:
            print("dry-run only (pass --allow-paid to execute)")
            return 0

        if max_cost is not None and total_proj > max_cost:
            print(
                f"refusing: projected ${total_proj:.4f} exceeds cap ${max_cost:.4f}",
                file=sys.stderr,
            )
            return 2

        # Execute via run_stage per content-item for budget clarity, or batched.
        # Batch by stage using subprocess with --content-item-id is too slow;
        # call modules directly with --reprocess semantics (append-only inserts).
        remaining = max_cost
        for label, ids, module, model in plan:
            if remaining is not None and remaining <= 0:
                print("budget exhausted; stopping", flush=True)
                return 1
            run_id = f"rescore-stale-{label}"
            stage_run_id = f"rescore-stale-{label}-stage"
            stats = module.run_window(
                conn,
                ids,
                run_id=run_id,
                stage_run_id=stage_run_id,
                dry_run=False,
                model=model,
                max_cost_usd=remaining,
            )
            print(
                f"  ran {label} model={model}: ok={stats.papers_succeeded} "
                f"fail={stats.papers_failed} cost=${stats.cost_usd:.4f}",
                flush=True,
            )
            if remaining is not None:
                remaining = max(0.0, remaining - stats.cost_usd)
            if stats.stopped_budget_cap:
                print("stopped on budget cap", flush=True)
                return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
