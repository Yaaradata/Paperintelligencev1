#!/usr/bin/env python3
"""One-day SHADOW E2E using PI catalog + PI relevance. No paid LLM calls."""

from __future__ import annotations

import argparse
import json
import sys
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from paper_intelligence.catalog.relevance import papers_with_latest_decision
from paper_intelligence.catalog.shadow import (
    compare_id_sets,
    latest_screen_scores_pi,
    select_window_candidates_pi,
)
from paper_intelligence.common.config import (
    GATE_PERCENTILE,
    QUALITY_BATCH_SIZE,
    QUALITY_MODEL,
    SCREEN_MODEL,
)
from paper_intelligence.db import connect, ids_with_result, latest_screen_scores
from paper_intelligence.quality.stage import (
    POLICY_VERSION,
    PROMPT_VERSION,
    STAGE_VERSION,
    explain_quality_routing,
    run_window as quality_run_window,
    select_quality_candidates,
)
import paper_intelligence.quality.stage as qstage


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--from", dest="date_from", default="2026-09-02")
    parser.add_argument("--until", dest="date_until", default="2026-09-02")
    parser.add_argument("--focus-id", type=int, default=137619)
    parser.add_argument(
        "--output-dir", default=str(ROOT / "reports" / "architecture")
    )
    args = parser.parse_args()
    out = Path(args.output_dir)
    out.mkdir(parents=True, exist_ok=True)

    with connect() as conn:
        keep_ids = papers_with_latest_decision(
            conn, date_from=args.date_from, date_until=args.date_until, decision="keep"
        )
        reject_ids = papers_with_latest_decision(
            conn,
            date_from=args.date_from,
            date_until=args.date_until,
            decision="reject",
        )
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT count(*) AS n FROM paper_intelligence.papers
                WHERE published_at >= %s::timestamptz
                  AND published_at < (%s::timestamptz + interval '1 day')
                """,
                (args.date_from, args.date_until),
            )
            papers_in_day = int(cur.fetchone()["n"])

        # Patch quality router to use PI screen window
        orig = qstage.latest_screen_scores
        qstage.latest_screen_scores = latest_screen_scores_pi
        try:
            screens = latest_screen_scores_pi(
                conn, date_from=args.date_from, date_until=args.date_until
            )
            decisions = explain_quality_routing(
                conn,
                date_from=args.date_from,
                date_until=args.date_until,
                gate_percentile=GATE_PERCENTILE,
            )
            selected = select_quality_candidates(
                conn,
                date_from=args.date_from,
                date_until=args.date_until,
                gate_percentile=GATE_PERCENTILE,
            )
        finally:
            qstage.latest_screen_scores = orig

        already = ids_with_result(
            conn,
            selected,
            "quality",
            stage_version=STAGE_VERSION,
            prompt_version=PROMPT_VERSION,
            policy_version=POLICY_VERSION,
            model=QUALITY_MODEL,
        )
        need_paid = [i for i in selected if i not in already]
        cost = quality_run_window(
            conn,
            need_paid,
            run_id="shadow-dry-run",
            stage_run_id="shadow-dry-run",
            model=QUALITY_MODEL,
            batch_size=QUALITY_BATCH_SIZE,
            dry_run=True,
        )

        # Compare vs production (Radar-window) screen survivors
        old_screens = latest_screen_scores(
            conn, date_from=args.date_from, date_until=args.date_until
        )
        old_surv = sorted(
            {
                int(r["content_item_id"])
                for r in old_screens
                if ((r.get("result_json") or {}).get("gate") or {}).get("passed")
            }
        )
        new_surv = sorted(
            {
                int(r["content_item_id"])
                for r in screens
                if ((r.get("result_json") or {}).get("gate") or {}).get("passed")
            }
        )

        focus_dec = next(
            (d.as_dict() for d in decisions if d.content_item_id == args.focus_id),
            None,
        )
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT p.*, ci.status AS radar_status
                FROM paper_intelligence.papers p
                LEFT JOIN research_radar.content_items ci ON ci.id = p.legacy_content_item_id
                WHERE p.paper_id = %s
                """,
                (args.focus_id,),
            )
            focus_paper = cur.fetchone()
            focus_paper = dict(focus_paper) if focus_paper else None

        by_dec = Counter(d.decision for d in decisions)
        by_reason = Counter(d.reason for d in decisions)

        report = {
            "mode": "shadow_dry_run",
            "day": {"from": args.date_from, "until": args.date_until},
            "pi_catalog": {
                "papers_in_day": papers_in_day,
                "relevance_keep": len(keep_ids),
                "relevance_reject": len(reject_ids),
            },
            "funnel_shadow": {
                "screen_rows": len(screens),
                "screen_passed": by_dec.get("selected", 0) + by_dec.get("not_selected", 0),
                "blocked": by_dec.get("blocked", 0),
                "quality_selected": len(selected),
                "already_scored": len(already),
                "would_need_paid_quality": len(need_paid),
                "estimated_paid_calls": cost.calls,
                "estimated_cost_usd": round(cost.cost_usd, 4),
                "by_reason": dict(by_reason),
            },
            "screen_survivor_compare_radar_window_vs_pi_window": compare_id_sets(
                old_surv, new_surv
            ),
            "focus_137619": {
                "exists_as_one_pi_paper": focus_paper is not None,
                "paper_id": (focus_paper or {}).get("paper_id"),
                "arxiv_id": (focus_paper or {}).get("arxiv_id"),
                "radar_status": (focus_paper or {}).get("radar_status"),
                "routing": focus_dec,
                "enters_router": bool(
                    focus_dec and focus_dec.get("decision") in {"selected", "not_selected"}
                ),
                "below_gate_percentile": bool(
                    focus_dec
                    and focus_dec.get("reason") == "not_selected_below_gate_percentile"
                ),
                "radar_status_affects_routing": False,
            },
            "paid_llm_executed": False,
            "production_cutover": False,
        }

    path = out / f"pi_catalog_shadow_e2e_{args.date_from}.json"
    path.write_text(json.dumps(report, indent=2, default=str) + "\n")
    print(json.dumps(report, indent=2, default=str))
    print(f"wrote {path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
