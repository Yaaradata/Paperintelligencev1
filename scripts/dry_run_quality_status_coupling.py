#!/usr/bin/env python3
"""Dry-run: measure status-coupling impact and quality-router outcomes.

No LLM calls. No writes unless --write-report only (filesystem).

Example:
  PYTHONPATH=src python3 scripts/dry_run_quality_status_coupling.py \\
    --from 2026-09-01 --until 2026-09-15 \\
    --output-dir reports/architecture
"""

from __future__ import annotations

import argparse
import json
import sys
from collections import Counter
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from paper_intelligence.common.config import GATE_PERCENTILE, QUALITY_BATCH_SIZE, QUALITY_MODEL
from paper_intelligence.db import connect, ids_with_result
from paper_intelligence.quality import (
    STAGE_VERSION,
    PROMPT_VERSION,
    POLICY_VERSION,
    explain_quality_routing,
    run_window as quality_run_window,
    select_quality_candidates,
)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--from", dest="date_from", required=True)
    parser.add_argument("--until", dest="date_until", required=True)
    parser.add_argument("--gate-percentile", type=float, default=GATE_PERCENTILE)
    parser.add_argument("--output-dir", default=str(ROOT / "reports" / "architecture"))
    parser.add_argument("--focus-id", type=int, default=137619)
    args = parser.parse_args(argv)

    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    with connect() as conn:
        with conn.cursor() as cur:
            # Papers with PI screen gate passed but Radar status ≠ RELEVANT
            # (the historical coupling exclusion set).
            cur.execute(
                """
                WITH latest_screen AS (
                  SELECT DISTINCT ON (r.content_item_id)
                         r.content_item_id, r.result_json, ci.status, ci.published_at
                  FROM paper_intelligence.paper_classification_results r
                  JOIN research_radar.content_items ci ON ci.id = r.content_item_id
                  WHERE r.task_type = 'screen'
                    AND ci.published_at >= %s::timestamptz
                    AND ci.published_at < (%s::timestamptz + interval '1 day')
                  ORDER BY r.content_item_id, r.created_at DESC
                )
                SELECT
                  count(*) FILTER (
                    WHERE (result_json->'gate'->>'passed')::boolean IS TRUE
                  ) AS screen_passed,
                  count(*) FILTER (
                    WHERE (result_json->'gate'->>'passed')::boolean IS TRUE
                      AND status = 'RELEVANT'
                  ) AS screen_passed_relevant,
                  count(*) FILTER (
                    WHERE (result_json->'gate'->>'passed')::boolean IS TRUE
                      AND status IS DISTINCT FROM 'RELEVANT'
                  ) AS screen_passed_non_relevant,
                  count(*) FILTER (
                    WHERE (result_json->'gate'->>'passed')::boolean IS TRUE
                      AND status = 'ENTITY_RESOLVED'
                  ) AS screen_passed_entity_resolved,
                  count(*) FILTER (
                    WHERE content_item_id = %s
                  ) AS focus_present
                FROM latest_screen
                """,
                (args.date_from, args.date_until, args.focus_id),
            )
            coupling = dict(cur.fetchone())

            cur.execute(
                """
                SELECT ci.id, ci.title, ci.status, ci.published_at::date AS published_at,
                       pm.arxiv_id,
                       (r.result_json->'gate'->>'passed')::boolean AS gate_passed
                FROM research_radar.content_items ci
                LEFT JOIN research_radar.paper_metadata pm ON pm.content_id = ci.id
                JOIN LATERAL (
                  SELECT result_json
                  FROM paper_intelligence.paper_classification_results r
                  WHERE r.content_item_id = ci.id AND r.task_type = 'screen'
                  ORDER BY r.created_at DESC
                  LIMIT 1
                ) r ON TRUE
                WHERE ci.id = %s
                """,
                (args.focus_id,),
            )
            focus_row = cur.fetchone()
            focus = dict(focus_row) if focus_row else None

        decisions = explain_quality_routing(
            conn,
            date_from=args.date_from,
            date_until=args.date_until,
            gate_percentile=args.gate_percentile,
        )
        by_decision = Counter(d.decision for d in decisions)
        by_reason = Counter(d.reason for d in decisions)
        selected_ids = select_quality_candidates(
            conn,
            date_from=args.date_from,
            date_until=args.date_until,
            gate_percentile=args.gate_percentile,
        )
        already = ids_with_result(
            conn,
            selected_ids,
            "quality",
            stage_version=STAGE_VERSION,
            prompt_version=PROMPT_VERSION,
            policy_version=POLICY_VERSION,
            model=QUALITY_MODEL,
        )
        need_paid = [i for i in selected_ids if i not in already]

        # Cost projection for newly selected unpaid papers only.
        cost_stats = quality_run_window(
            conn,
            need_paid,
            run_id="dry-run",
            stage_run_id="dry-run",
            model=QUALITY_MODEL,
            batch_size=QUALITY_BATCH_SIZE,
            dry_run=True,
        )

        focus_decision = next(
            (d.as_dict() for d in decisions if d.content_item_id == args.focus_id),
            None,
        )

    report = {
        "generated_on": date.today().isoformat(),
        "window": {"from": args.date_from, "until": args.date_until},
        "gate_percentile": args.gate_percentile,
        "quality_model": QUALITY_MODEL,
        "status_coupling_impact": coupling,
        "focus_paper": {
            "content_item_id": args.focus_id,
            "row": focus,
            "routing": focus_decision,
            "A_entered_router_population": bool(
                focus_decision and focus_decision.get("decision") in {"selected", "not_selected"}
            ),
            "B_selected_by_policy": bool(
                focus_decision and focus_decision.get("decision") == "selected"
            ),
            "C_explicit_reason": (focus_decision or {}).get("reason"),
        },
        "routing_summary": {
            "screen_rows_considered": len(decisions),
            "by_decision": dict(by_decision),
            "by_reason": dict(by_reason),
            "selected_for_quality": len(selected_ids),
            "already_quality_scored_current_versions": len(already),
            "would_require_paid_quality_calls": len(need_paid),
        },
        "paid_quality_dry_run": {
            "papers": len(need_paid),
            "projected_calls": cost_stats.calls,
            "projected_input_tokens": cost_stats.input_tokens,
            "projected_output_tokens": cost_stats.output_tokens,
            "projected_cost_usd": round(cost_stats.cost_usd, 4),
            "note": "Projection only for selected papers missing current-version quality rows. No LLM calls made.",
        },
    }

    out = output_dir / f"quality_status_coupling_dry_run_{args.date_from}_to_{args.date_until}.json"
    out.write_text(json.dumps(report, indent=2, default=str) + "\n", encoding="utf-8")
    print(json.dumps(report, indent=2, default=str))
    print(f"\nwrote {out}", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
