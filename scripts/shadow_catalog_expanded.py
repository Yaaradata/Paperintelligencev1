#!/usr/bin/env python3
"""Expanded FREE shadow comparison: Radar-backed vs PI-backed readers.

Classifies differences. No paid LLM work.
"""

from __future__ import annotations

import argparse
import json
import sys
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
    CLASSIFY_MODEL,
    GATE_PERCENTILE,
    SCREEN_MODEL,
)
from paper_intelligence.db import connect, latest_screen_scores, select_window_candidates
from paper_intelligence.db.results import PI_ELIGIBLE_STATUSES
from paper_intelligence.quality.stage import (
    explain_quality_routing,
    select_quality_candidates,
)
from paper_intelligence.screen import stage as screen_stage
from paper_intelligence.audience_domain import stage as audience_stage
import paper_intelligence.quality.stage as qstage
import paper_intelligence.db.results as results_mod


def _classify(name: str, cmp: dict, *, expected_fix: bool = False) -> str:
    if cmp["old_only_count"] == 0 and cmp["new_only_count"] == 0:
        return "match"
    if expected_fix:
        return "expected_fix"
    # Heuristic: if only old_only and related to RELEVANT-only vs keep, migrated_state
    if cmp["old_only_count"] > 0 or cmp["new_only_count"] > 0:
        return "migrated_state_difference"
    return "unexplained"


def _survivors(rows) -> list[int]:
    return sorted(
        {
            int(r["content_item_id"])
            for r in rows
            if ((r.get("result_json") or {}).get("gate") or {}).get("passed")
        }
    )


def run_window(conn, date_from: str, date_until: str) -> dict:
    # Paper window
    with conn.cursor() as cur:
        cur.execute(
            """
            SELECT id FROM research_radar.content_items
            WHERE published_at >= %s::timestamptz
              AND published_at < (%s::timestamptz + interval '1 day')
            ORDER BY id
            """,
            (date_from, date_until),
        )
        old_papers = [int(r["id"]) for r in cur.fetchall()]
        cur.execute(
            """
            SELECT paper_id FROM paper_intelligence.papers
            WHERE published_at >= %s::timestamptz
              AND published_at < (%s::timestamptz + interval '1 day')
            ORDER BY paper_id
            """,
            (date_from, date_until),
        )
        new_papers = [int(r["paper_id"]) for r in cur.fetchall()]

    # Relevance keep/reject (old approximates PI_ELIGIBLE / REJECTED)
    with conn.cursor() as cur:
        cur.execute(
            """
            SELECT id FROM research_radar.content_items
            WHERE published_at >= %s::timestamptz
              AND published_at < (%s::timestamptz + interval '1 day')
              AND status = ANY(%s)
            ORDER BY id
            """,
            (date_from, date_until, list(PI_ELIGIBLE_STATUSES)),
        )
        old_keep = [int(r["id"]) for r in cur.fetchall()]
        cur.execute(
            """
            SELECT id FROM research_radar.content_items
            WHERE published_at >= %s::timestamptz
              AND published_at < (%s::timestamptz + interval '1 day')
              AND status = 'REJECTED'
            ORDER BY id
            """,
            (date_from, date_until),
        )
        old_reject = [int(r["id"]) for r in cur.fetchall()]
    new_keep = papers_with_latest_decision(
        conn, date_from=date_from, date_until=date_until, decision="keep"
    )
    new_reject = papers_with_latest_decision(
        conn, date_from=date_from, date_until=date_until, decision="reject"
    )

    old_screen_cand = select_window_candidates(
        conn,
        date_from=date_from,
        date_until=date_until,
        stage_task_type="screen",
        skip_done=True,
        stage_version=screen_stage.STAGE_VERSION,
        prompt_version=screen_stage.PROMPT_VERSION,
        policy_version=screen_stage.POLICY_VERSION,
        model=SCREEN_MODEL,
    )
    # Force legacy path for "old" even if env flag set: call radar SQL directly
    # by temporarily disabling catalog flag
    flag = results_mod.PI_USE_PAPERS_CATALOG
    results_mod.PI_USE_PAPERS_CATALOG = False
    try:
        old_screen_cand = select_window_candidates(
            conn,
            date_from=date_from,
            date_until=date_until,
            stage_task_type="screen",
            skip_done=True,
            stage_version=screen_stage.STAGE_VERSION,
            prompt_version=screen_stage.PROMPT_VERSION,
            policy_version=screen_stage.POLICY_VERSION,
            model=SCREEN_MODEL,
        )
        old_audience = select_window_candidates(
            conn,
            date_from=date_from,
            date_until=date_until,
            stage_task_type="domain",
            skip_done=True,
            stage_version=audience_stage.STAGE_VERSION,
            prompt_version=audience_stage.PROMPT_VERSION,
            policy_version=audience_stage.POLICY_VERSION,
            model=CLASSIFY_MODEL,
        )
        old_screens = latest_screen_scores(conn, date_from=date_from, date_until=date_until)
        old_selected = select_quality_candidates(
            conn, date_from=date_from, date_until=date_until, gate_percentile=GATE_PERCENTILE
        )
    finally:
        results_mod.PI_USE_PAPERS_CATALOG = flag

    new_screen_cand = select_window_candidates_pi(
        conn,
        date_from=date_from,
        date_until=date_until,
        stage_task_type="screen",
        skip_done=True,
        stage_version=screen_stage.STAGE_VERSION,
        prompt_version=screen_stage.PROMPT_VERSION,
        policy_version=screen_stage.POLICY_VERSION,
        model=SCREEN_MODEL,
    )
    new_audience = select_window_candidates_pi(
        conn,
        date_from=date_from,
        date_until=date_until,
        stage_task_type="domain",
        skip_done=True,
        stage_version=audience_stage.STAGE_VERSION,
        prompt_version=audience_stage.PROMPT_VERSION,
        policy_version=audience_stage.POLICY_VERSION,
        model=CLASSIFY_MODEL,
    )
    new_screens = latest_screen_scores_pi(conn, date_from=date_from, date_until=date_until)
    orig = qstage.latest_screen_scores
    qstage.latest_screen_scores = latest_screen_scores_pi
    try:
        new_selected = select_quality_candidates(
            conn, date_from=date_from, date_until=date_until, gate_percentile=GATE_PERCENTILE
        )
        new_router_pop = [
            d.content_item_id
            for d in explain_quality_routing(
                conn, date_from=date_from, date_until=date_until, gate_percentile=GATE_PERCENTILE
            )
            if d.decision in {"selected", "not_selected"}
        ]
    finally:
        qstage.latest_screen_scores = orig

    old_surv = _survivors(old_screens)
    new_surv = _survivors(new_screens)

    # Normalize candidates ≈ keep set (legacy eligible)
    old_norm = old_keep
    new_norm = new_keep

    # Affiliation FAST = screen survivors; DEEP = quality scored ids
    with conn.cursor() as cur:
        cur.execute(
            """
            SELECT DISTINCT q.content_item_id
            FROM paper_intelligence.paper_classification_results q
            JOIN research_radar.content_items ci ON ci.id = q.content_item_id
            WHERE q.task_type = 'quality'
              AND ci.published_at >= %s::timestamptz
              AND ci.published_at < (%s::timestamptz + interval '1 day')
            ORDER BY 1
            """,
            (date_from, date_until),
        )
        old_deep = [int(r["content_item_id"]) for r in cur.fetchall()]
        cur.execute(
            """
            SELECT DISTINCT q.content_item_id
            FROM paper_intelligence.paper_classification_results q
            JOIN paper_intelligence.papers p ON p.paper_id = q.content_item_id
            WHERE q.task_type = 'quality'
              AND p.published_at >= %s::timestamptz
              AND p.published_at < (%s::timestamptz + interval '1 day')
            ORDER BY 1
            """,
            (date_from, date_until),
        )
        new_deep = [int(r["content_item_id"]) for r in cur.fetchall()]

        # HF window arxiv lookup
        cur.execute(
            """
            SELECT pm.arxiv_id, pm.content_id
            FROM research_radar.paper_metadata pm
            JOIN research_radar.content_items ci ON ci.id = pm.content_id
            WHERE pm.arxiv_id IS NOT NULL
              AND ci.published_at >= %s::timestamptz
              AND ci.published_at < (%s::timestamptz + interval '1 day')
            """,
            (date_from, date_until),
        )
        old_hf = sorted(int(r["content_id"]) for r in cur.fetchall())
        cur.execute(
            """
            SELECT paper_id FROM paper_intelligence.papers
            WHERE arxiv_id IS NOT NULL
              AND published_at >= %s::timestamptz
              AND published_at < (%s::timestamptz + interval '1 day')
            ORDER BY paper_id
            """,
            (date_from, date_until),
        )
        new_hf = [int(r["paper_id"]) for r in cur.fetchall()]

        # Adjudication / editorial population = papers with any classification in window
        cur.execute(
            """
            SELECT DISTINCT r.content_item_id
            FROM paper_intelligence.paper_classification_results r
            JOIN research_radar.content_items ci ON ci.id = r.content_item_id
            WHERE ci.published_at >= %s::timestamptz
              AND ci.published_at < (%s::timestamptz + interval '1 day')
            ORDER BY 1
            """,
            (date_from, date_until),
        )
        old_adj = [int(r["content_item_id"]) for r in cur.fetchall()]
        cur.execute(
            """
            SELECT DISTINCT r.content_item_id
            FROM paper_intelligence.paper_classification_results r
            JOIN paper_intelligence.papers p ON p.paper_id = r.content_item_id
            WHERE p.published_at >= %s::timestamptz
              AND p.published_at < (%s::timestamptz + interval '1 day')
            ORDER BY 1
            """,
            (date_from, date_until),
        )
        new_adj = [int(r["content_item_id"]) for r in cur.fetchall()]

    comparisons = {}
    pairs = [
        # (name, old, new, expected_diff_class if any diff else None)
        ("paper_window", old_papers, new_papers, "migrated_state_difference"),
        ("relevance_keep", old_keep, new_keep, "migrated_state_difference"),
        ("relevance_reject", old_reject, new_reject, "migrated_state_difference"),
        ("screen_candidates", old_screen_cand, new_screen_cand, "migrated_state_difference"),
        ("screen_survivors", old_surv, new_surv, None),
        ("audience_candidates", old_audience, new_audience, "migrated_state_difference"),
        ("normalize_candidates", old_norm, new_norm, "migrated_state_difference"),
        ("quality_router_population", old_surv, new_router_pop, None),
        ("quality_selected", old_selected, new_selected, None),
        ("affiliation_fast_candidates", old_surv, new_surv, None),
        ("affiliation_deep_candidates", old_deep, new_deep, None),
        ("hf_window_papers", old_hf, new_hf, "migrated_state_difference"),
        ("adjudication_editorial_population", old_adj, new_adj, None),
    ]
    for name, old, new, expected_class in pairs:
        cmp = compare_id_sets(old, new)
        if cmp["old_only_count"] == 0 and cmp["new_only_count"] == 0:
            klass = "match"
            reason = "identical"
        elif expected_class:
            klass = expected_class
            reason = (
                "PI catalog/relevance is PI-referenced subset or keep-seeded; "
                "legacy path uses full Radar window / PI_ELIGIBLE_STATUSES"
            )
        else:
            klass = "unexplained"
            reason = "unexpected divergence; investigate before canary"
        comparisons[name] = {**cmp, "classification": klass, "difference_reason": reason}

    unexplained = sum(1 for v in comparisons.values() if v["classification"] == "unexplained")

    return {
        "window": {"from": date_from, "until": date_until},
        "comparisons": comparisons,
        "unexplained_difference_count": unexplained,
        "paid_llm_executed": False,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--from", dest="date_from", required=True)
    parser.add_argument("--until", dest="date_until", required=True)
    parser.add_argument("--label", required=True, help="e.g. 7d or 15d")
    parser.add_argument("--output-dir", default=str(ROOT / "reports" / "architecture"))
    args = parser.parse_args()
    out = Path(args.output_dir)
    out.mkdir(parents=True, exist_ok=True)

    with connect() as conn:
        report = run_window(conn, args.date_from, args.date_until)

    json_path = out / f"pi_catalog_shadow_{args.label}.json"
    md_path = out / f"pi_catalog_shadow_{args.label}.md"
    json_path.write_text(json.dumps(report, indent=2, default=str) + "\n")

    lines = [
        f"# PI Catalog Shadow Comparison ({args.label})",
        "",
        f"Window: `{args.date_from}` → `{args.date_until}`",
        "",
        f"Unexplained differences: **{report['unexplained_difference_count']}**",
        "",
        "| Reader | old | new | ∩ | old_only | new_only | class | reason |",
        "|---|---:|---:|---:|---:|---:|---|---|",
    ]
    for name, c in report["comparisons"].items():
        lines.append(
            f"| {name} | {c['old_count']} | {c['new_count']} | {c['intersection']} | "
            f"{c['old_only_count']} | {c['new_only_count']} | {c['classification']} | "
            f"{c['difference_reason']} |"
        )
    md_path.write_text("\n".join(lines) + "\n")
    print(json.dumps(report, indent=2, default=str))
    print(f"wrote {json_path}")
    print(f"wrote {md_path}")
    return 0 if report["unexplained_difference_count"] == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
