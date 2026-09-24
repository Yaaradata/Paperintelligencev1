#!/usr/bin/env python3
"""Score golden 200 papers via QUALITY_ENGINE=jev_glm under a dedicated eval run_id.

Never writes "current quality" stamps that collide with Terra (uses prose_v001 /
systemone_v001). Cap enforced via --max-cost-usd.

  QUALITY_ENGINE=jev_glm PYTHONPATH=src python3 scripts/score_golden_jev_glm.py \
    --allow-paid --max-cost-usd 0.75
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

# Force engine before importing quality modules that read QUALITY_ENGINE at call time.
os.environ["QUALITY_ENGINE"] = "jev_glm"

from paper_intelligence.db import connect  # noqa: E402
from paper_intelligence.observability.runs import (  # noqa: E402
    finish_pipeline_run,
    finish_stage_run,
    start_pipeline_run,
    start_stage_run,
)
from paper_intelligence.quality.jev_glm_engine import (  # noqa: E402
    JEV_GLM_POLICY_VERSION,
    JEV_GLM_PROMPT_VERSION,
    SCORING_MODEL,
    run_jev_glm_window,
)
from paper_intelligence.quality.stage import STAGE_VERSION  # noqa: E402

REPORT_DIR = ROOT / "reports" / "golden"
RUN_META = REPORT_DIR / "jev_glm_golden_run.json"
PIPELINE_NAME = "golden_jev_glm_eval"


def _args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--labeller", default="subha")
    p.add_argument("--label-round", default="v1")
    p.add_argument("--allow-paid", action="store_true")
    p.add_argument("--max-cost-usd", type=float, default=0.75)
    p.add_argument("--dry-run", action="store_true")
    p.add_argument("--limit", type=int, default=0)
    return p.parse_args()


def main() -> int:
    args = _args()
    if not args.dry_run and not args.allow_paid:
        print("refusing: pass --allow-paid or --dry-run", file=sys.stderr)
        return 2

    with connect() as conn:
        rows = conn.execute(
            """
            SELECT paper_id FROM paper_intelligence.golden_human_scores
            WHERE labeller = %s AND label_round = %s
            ORDER BY paper_id
            """,
            (args.labeller, args.label_round),
        ).fetchall()
    ids = [int(r["paper_id"]) for r in rows]
    if args.limit:
        ids = ids[: args.limit]
    print(f"golden_n={len(ids)} engine=jev_glm model={SCORING_MODEL}", flush=True)

    REPORT_DIR.mkdir(parents=True, exist_ok=True)

    with connect() as conn:
        if args.dry_run:
            stats = run_jev_glm_window(
                conn, ids, run_id="dry-run", stage_run_id="dry-run", dry_run=True
            )
            print(
                json.dumps(
                    {
                        "dry_run": True,
                        "n": len(ids),
                        "est_cost_usd": stats.cost_usd,
                        "calls": stats.calls,
                        "warnings": stats.warnings,
                    },
                    indent=2,
                )
            )
            return 0

        run_id = start_pipeline_run(
            conn,
            pipeline_name=PIPELINE_NAME,
            trigger_type="manual",
            created_by="golden_jev_glm",
            metadata={
                "purpose": "golden gate eval for jev_glm",
                "not_current_quality": True,
                "labeller": args.labeller,
                "label_round": args.label_round,
                "paper_ids_n": len(ids),
                "max_cost_usd": args.max_cost_usd,
            },
        )
        stage_run_id = start_stage_run(
            conn,
            run_id,
            stage_name="quality",
            stage_version=STAGE_VERSION,
            prompt_version=JEV_GLM_PROMPT_VERSION,
            policy_version=JEV_GLM_POLICY_VERSION,
            items_input=len(ids),
        )
        RUN_META.write_text(
            json.dumps(
                {
                    "run_id": run_id,
                    "stage_run_id": stage_run_id,
                    "pipeline_name": PIPELINE_NAME,
                    "quality_engine": "jev_glm",
                    "scoring_model": SCORING_MODEL,
                    "generated_at": datetime.now(timezone.utc).isoformat(),
                    "n": len(ids),
                    "not_current_quality": True,
                    "status": "running",
                },
                indent=2,
            ),
            encoding="utf-8",
        )
        try:
            stats = run_jev_glm_window(
                conn,
                ids,
                run_id=run_id,
                stage_run_id=stage_run_id,
                dry_run=False,
                max_cost_usd=args.max_cost_usd,
            )
            finish_stage_run(
                conn,
                stage_run_id,
                status="succeeded" if stats.papers_failed == 0 else "partial",
                items_success=stats.papers_succeeded,
                items_failed=stats.papers_failed,
                error_summary="; ".join(stats.errors)[:500] or None,
            )
            finish_pipeline_run(
                conn,
                run_id,
                status="succeeded" if stats.papers_failed == 0 else "partial",
                items_input=len(ids),
                items_succeeded=stats.papers_succeeded,
                items_failed=stats.papers_failed,
                metadata={"cost_usd": stats.cost_usd, "calls": stats.calls},
            )
        except Exception as exc:
            finish_stage_run(
                conn, stage_run_id, status="failed", error_summary=str(exc)[:500]
            )
            finish_pipeline_run(
                conn, run_id, status="failed", metadata={"error": str(exc)[:500]}
            )
            raise

    meta = json.loads(RUN_META.read_text(encoding="utf-8"))
    meta.update(
        {
            "status": "done",
            "cost_usd": stats.cost_usd,
            "papers_succeeded": stats.papers_succeeded,
            "papers_failed": stats.papers_failed,
            "finished_at": datetime.now(timezone.utc).isoformat(),
        }
    )
    RUN_META.write_text(json.dumps(meta, indent=2), encoding="utf-8")
    print(json.dumps(meta, indent=2))
    return 0 if stats.papers_failed == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
