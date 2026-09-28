#!/usr/bin/env python3
"""Backfill GLM prose onto existing jev_glm score rows (prose only — never re-scores).

Targets papers in the window whose latest quality row is a jev_glm row
(model typesafe/jev-1.13, prompt_version prose_v001) with NULL/empty so_what or
reason_not_higher. Scores are read from that row; prose is merged back into the
same row (matched by its scoring run_id). Every failure is recorded per paper in
quality_attempts (stage_version quality_prose_v001) with raw output.

  PYTHONPATH=src python scripts/backfill_jev_glm_prose.py --from 2026-08-25 --until 2026-08-31 --dry-run
  PYTHONPATH=src python scripts/backfill_jev_glm_prose.py --from 2026-08-25 --until 2026-08-31 \
      --allow-paid --max-cost-usd 0.60 [--limit N]
"""
from __future__ import annotations

import argparse
import json
import sys
from datetime import date
from typing import Any

from paper_intelligence.common.batch_runner import BatchStats
from paper_intelligence.common.budget import BudgetCap
from paper_intelligence.common.config import require_model_priced
from paper_intelligence.common.runguard import RunGuard
from paper_intelligence.db import connect
from paper_intelligence.observability.runs import (
    finish_pipeline_run,
    finish_stage_run,
    start_pipeline_run,
    start_stage_run,
)
from paper_intelligence.quality.jev_glm_engine import (
    JEV_GLM_POLICY_VERSION,
    JEV_GLM_PROMPT_VERSION,
    PROSE_ATTEMPT_STAGE_VERSION,
    PROSE_MAX_ATTEMPTS,
    PROSE_MAX_TOKENS,
    PROSE_MODEL,
    PROSE_PROMPT_VERSION,
    SCORING_MODEL,
    project_prose_cost,
    run_prose_for_papers,
)
from paper_intelligence.quality.stage import RUBRIC_DIMENSIONS

TARGET_SQL = """
WITH q AS (
    SELECT DISTINCT ON (r.content_item_id)
        r.content_item_id, r.run_id::text AS score_run_id, r.model, r.prompt_version, r.result_json
    FROM paper_intelligence.paper_classification_results r
    JOIN paper_intelligence.papers p ON p.paper_id = r.content_item_id
    WHERE r.task_type = 'quality' AND p.published_at::date BETWEEN %(from)s AND %(until)s
    ORDER BY r.content_item_id, r.created_at DESC
)
SELECT q.content_item_id, q.score_run_id, q.result_json, p.title, p.abstract
FROM q JOIN paper_intelligence.papers p ON p.paper_id = q.content_item_id
WHERE q.model = %(model)s AND q.prompt_version = %(prompt_version)s
  AND (NULLIF(btrim(q.result_json->>'so_what'), '') IS NULL
       OR NULLIF(btrim(q.result_json->>'reason_not_higher'), '') IS NULL)
ORDER BY q.content_item_id
"""


def load_targets(date_from: date, date_until: date) -> list[dict[str, Any]]:
    with connect() as conn:
        rows = conn.execute(
            TARGET_SQL,
            {"from": date_from, "until": date_until, "model": SCORING_MODEL,
             "prompt_version": JEV_GLM_PROMPT_VERSION},
        ).fetchall()
    out = []
    for r in rows:
        rj = r["result_json"] if isinstance(r["result_json"], dict) else json.loads(r["result_json"])
        if any(rj.get(d) is None for d in RUBRIC_DIMENSIONS):
            continue
        out.append({
            "content_item_id": int(r["content_item_id"]),
            "title": r["title"],
            "abstract": r["abstract"],
            "score_run_id": r["score_run_id"],
            "dims": {d: rj[d] for d in RUBRIC_DIMENSIONS},
        })
    return out


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--from", dest="date_from", required=True, type=date.fromisoformat)
    ap.add_argument("--until", dest="date_until", required=True, type=date.fromisoformat)
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--allow-paid", action="store_true")
    ap.add_argument("--max-cost-usd", type=float)
    ap.add_argument("--limit", type=int)
    args = ap.parse_args()

    require_model_priced(PROSE_MODEL)
    targets = load_targets(args.date_from, args.date_until)
    if args.limit:
        targets = targets[: args.limit]
    runs = sorted({t["score_run_id"] for t in targets})
    print(f"prose_backfill: window={args.date_from}..{args.date_until} targets={len(targets)} "
          f"score_runs={runs}", flush=True)

    calls, tin, tout, expected = project_prose_cost(targets)
    _, _, tout_hi, worst = project_prose_cost(
        targets, out_tokens_per_call=PROSE_MAX_TOKENS, calls_per_paper=PROSE_MAX_ATTEMPTS
    )
    print(
        f"PROJECTION prose_backfill model={PROSE_MODEL} max_tokens={PROSE_MAX_TOKENS}: "
        f"{len(targets)} papers, {calls} calls, ~{tin} in / ~{tout} out tokens, "
        f"~${expected:.4f} expected (table price)",
        flush=True,
    )
    print(
        f"PROJECTION prose_backfill worst case (every paper retried, every call hits max_tokens): "
        f"{calls * PROSE_MAX_ATTEMPTS} calls, ~{tout_hi} out tokens, ~${worst:.4f}",
        flush=True,
    )
    if args.dry_run:
        return 0
    if not args.allow_paid or args.max_cost_usd is None:
        print("refusing: paid run needs --allow-paid and --max-cost-usd", file=sys.stderr)
        return 2

    scored = {t["content_item_id"]: t["dims"] for t in targets}
    score_run_ids = {t["content_item_id"]: t["score_run_id"] for t in targets}
    budget = BudgetCap(args.max_cost_usd)
    stats = BatchStats(papers_requested=len(targets), budget=budget)
    guard = RunGuard(window=100, max_failure_rate=0.10, min_items=min(20, max(1, len(targets))))
    print(f"  runguard: window=100 max_failure_rate=10% evaluated from item {guard.min_items}", flush=True)
    with connect() as conn:
        run_id = start_pipeline_run(
            conn, pipeline_name="paper_intelligence.quality_prose_backfill", trigger_type="manual",
            created_by="backfill_jev_glm_prose",
            metadata={"window": [str(args.date_from), str(args.date_until)], "targets": len(targets),
                      "score_run_ids": runs, "max_cost_usd": args.max_cost_usd,
                      "prose_only": True, "rescored": False},
        )
        stage_run_id = start_stage_run(
            conn, run_id, stage_name="quality_prose", stage_version=PROSE_ATTEMPT_STAGE_VERSION,
            prompt_version=PROSE_PROMPT_VERSION, policy_version=JEV_GLM_POLICY_VERSION,
            items_input=len(targets),
        )
        conn.commit()
    print(f"  run_id={run_id}", flush=True)
    try:
        prose, failures = run_prose_for_papers(
            papers=targets, scored=scored, run_id=run_id, stage_run_id=stage_run_id,
            stats=stats, budget=budget, score_run_ids=score_run_ids, guard=guard,
        )
        status = "succeeded" if not failures and not stats.papers_skipped_budget else "partial"
        with connect() as conn:
            finish_stage_run(conn, stage_run_id, status=status, items_success=len(prose),
                             items_failed=len(failures))
            finish_pipeline_run(
                conn, run_id, status=status, items_input=len(targets), items_succeeded=len(prose),
                items_failed=len(failures), items_skipped=stats.papers_skipped_budget,
                metadata={"cost_usd": stats.cost_usd, "actual_cost_usd": stats.actual_cost_usd,
                          "calls": stats.calls},
            )
            conn.commit()
    except BaseException as exc:
        print(guard.status(), flush=True)
        print(f"prose_backfill: aborted calls={stats.calls} cost=${stats.cost_usd:.4f} "
              f"(usage.cost=${stats.actual_cost_usd:.4f})", flush=True)
        status = "cancelled" if isinstance(exc, KeyboardInterrupt) else "failed"
        with connect() as conn:
            finish_stage_run(conn, stage_run_id, status="failed", error_summary=f"{status}: {exc}"[:500])
            finish_pipeline_run(conn, run_id, status=status, metadata={"error": str(exc)[:500],
                                "cost_usd": stats.cost_usd})
            conn.commit()
        raise
    print(guard.status(), flush=True)
    print(
        f"prose_backfill: done ok={len(prose)} failed={len(failures)} "
        f"skipped_budget={stats.papers_skipped_budget} calls={stats.calls} "
        f"cost=${stats.cost_usd:.4f} (usage.cost=${stats.actual_cost_usd:.4f}, "
        f"table est ${stats.estimated_cost_usd:.4f}) cap=${args.max_cost_usd:.2f}",
        flush=True,
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
