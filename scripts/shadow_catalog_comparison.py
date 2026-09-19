#!/usr/bin/env python3
"""Shadow-compare Radar-backed vs PI-catalog selectors for one day. No paid work."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from paper_intelligence.catalog.shadow import (
    compare_id_sets,
    latest_screen_scores_pi,
    select_window_candidates_pi,
)
from paper_intelligence.common.config import GATE_PERCENTILE, SCREEN_MODEL
from paper_intelligence.db import connect, latest_screen_scores, select_window_candidates
from paper_intelligence.quality.stage import (
    STAGE_VERSION as Q_STAGE,
    PROMPT_VERSION as Q_PROMPT,
    POLICY_VERSION as Q_POLICY,
    explain_quality_routing,
    select_quality_candidates,
)
from paper_intelligence.screen.stage import (
    STAGE_VERSION as S_STAGE,
    PROMPT_VERSION as S_PROMPT,
    POLICY_VERSION as S_POLICY,
)


def _screen_survivor_ids(rows) -> list[int]:
    return sorted(
        {
            int(r["content_item_id"])
            for r in rows
            if ((r.get("result_json") or {}).get("gate") or {}).get("passed")
        }
    )


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--from", dest="date_from", required=True)
    parser.add_argument("--until", dest="date_until", required=True)
    parser.add_argument(
        "--output-dir", default=str(ROOT / "reports" / "architecture")
    )
    parser.add_argument("--focus-id", type=int, default=137619)
    args = parser.parse_args()
    out = Path(args.output_dir)
    out.mkdir(parents=True, exist_ok=True)

    with connect() as conn:
        old_screen = select_window_candidates(
            conn,
            date_from=args.date_from,
            date_until=args.date_until,
            stage_task_type="screen",
            skip_done=True,
            stage_version=S_STAGE,
            prompt_version=S_PROMPT,
            policy_version=S_POLICY,
            model=SCREEN_MODEL,
        )
        new_screen = select_window_candidates_pi(
            conn,
            date_from=args.date_from,
            date_until=args.date_until,
            stage_task_type="screen",
            skip_done=True,
            stage_version=S_STAGE,
            prompt_version=S_PROMPT,
            policy_version=S_POLICY,
            model=SCREEN_MODEL,
        )

        old_screens = latest_screen_scores(
            conn, date_from=args.date_from, date_until=args.date_until
        )
        new_screens = latest_screen_scores_pi(
            conn, date_from=args.date_from, date_until=args.date_until
        )
        old_surv = _screen_survivor_ids(old_screens)
        new_surv = _screen_survivor_ids(new_screens)

        # Quality router: monkeypatch latest_screen_scores temporarily for PI path
        import paper_intelligence.quality.stage as qstage

        old_selected = select_quality_candidates(
            conn,
            date_from=args.date_from,
            date_until=args.date_until,
            gate_percentile=GATE_PERCENTILE,
        )
        orig = qstage.latest_screen_scores
        qstage.latest_screen_scores = latest_screen_scores_pi
        try:
            new_selected = select_quality_candidates(
                conn,
                date_from=args.date_from,
                date_until=args.date_until,
                gate_percentile=GATE_PERCENTILE,
            )
            new_decisions = explain_quality_routing(
                conn,
                date_from=args.date_from,
                date_until=args.date_until,
                gate_percentile=GATE_PERCENTILE,
            )
        finally:
            qstage.latest_screen_scores = orig

        focus = next(
            (d.as_dict() for d in new_decisions if d.content_item_id == args.focus_id),
            None,
        )
        with conn.cursor() as cur:
            cur.execute(
                "SELECT paper_id, arxiv_id, title FROM paper_intelligence.papers WHERE paper_id=%s",
                (args.focus_id,),
            )
            focus_paper = cur.fetchone()
            focus_paper = dict(focus_paper) if focus_paper else None
            cur.execute(
                """
                SELECT decision, reason FROM paper_intelligence.paper_relevance_results
                WHERE paper_id=%s ORDER BY created_at DESC LIMIT 1
                """,
                (args.focus_id,),
            )
            focus_rel = cur.fetchone()
            focus_rel = dict(focus_rel) if focus_rel else None

        # Explain screen candidate differences
        screen_cmp = compare_id_sets(old_screen, new_screen)
        reasons = []
        if screen_cmp["old_only_count"] or screen_cmp["new_only_count"]:
            reasons.append(
                "Expected until production cutover: old uses PI_ELIGIBLE_STATUSES on Radar; "
                "new uses latest PI relevance keep (migrated). INGESTED papers lack relevance "
                "and are excluded from PI keep; REJECTED are reject."
            )

        report = {
            "window": {"from": args.date_from, "until": args.date_until},
            "readers": {
                "screen_candidates_needing_work": {
                    **screen_cmp,
                    "notes": reasons,
                },
                "screen_survivors_gate_passed": compare_id_sets(old_surv, new_surv),
                "quality_selected": compare_id_sets(old_selected, new_selected),
            },
            "focus_137619": {
                "pi_paper": focus_paper,
                "pi_relevance": focus_rel,
                "quality_routing": focus,
            },
            "production_cutover": False,
            "note": "Shadow comparison only. Production still uses Radar-backed selectors.",
        }

    path = out / f"pi_catalog_shadow_compare_{args.date_from}_to_{args.date_until}.json"
    path.write_text(json.dumps(report, indent=2, default=str) + "\n")
    print(json.dumps(report, indent=2, default=str))
    print(f"wrote {path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
