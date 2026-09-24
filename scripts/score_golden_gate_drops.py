#!/usr/bin/env python3
"""Phase G3b — Terra-score screen_failed + flagged golden papers (paid, cap $1).

Uses a dedicated pipeline run_id so scores do NOT become "current quality".
Records run metadata at reports/golden/g3b_run.json for evaluate to exclude.

  PYTHONPATH=src python3 scripts/score_golden_gate_drops.py [--dry-run]
"""

from __future__ import annotations

import argparse
import json
import sys
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from paper_intelligence.db import connect  # noqa: E402
from paper_intelligence.observability.runs import (  # noqa: E402
    finish_pipeline_run,
    start_pipeline_run,
    start_stage_run,
    finish_stage_run,
)
from paper_intelligence.quality.stage import (  # noqa: E402
    QUALITY_MODEL,
    RUBRIC_DIMENSIONS,
    STAGE_VERSION,
    PROMPT_VERSION,
    POLICY_VERSION,
    composite_score,
    run_window,
)

QUALITY_DIMS = RUBRIC_DIMENSIONS

REPORT_DIR = ROOT / "reports" / "golden"
RUN_META = REPORT_DIR / "g3b_run.json"
REPORT_JSON = REPORT_DIR / "g3b_gate_drop.json"
REPORT_MD = REPORT_DIR / "g3b_gate_drop.md"
MAX_COST_USD = 1.0
PIPELINE_NAME = "golden_g3b_gate_drop_eval"
STRATA = ("screen_failed", "flagged")


def _args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--labeller", default="subha")
    p.add_argument("--label-round", default="v1")
    p.add_argument("--dry-run", action="store_true")
    p.add_argument("--max-cost-usd", type=float, default=MAX_COST_USD)
    return p.parse_args()


def _load_gate_rows(labeller: str, label_round: str) -> list[dict[str, Any]]:
    with connect() as conn:
        rows = conn.execute(
            """
            SELECT paper_id, arxiv_id, sample_stratum, h_newsletter_verdict,
                   h_final_score
            FROM paper_intelligence.golden_human_scores
            WHERE labeller = %s AND label_round = %s
              AND sample_stratum = ANY(%s)
            ORDER BY sample_stratum, paper_id
            """,
            (labeller, label_round, list(STRATA)),
        ).fetchall()
    return [dict(r) for r in rows]


def _load_terra_for_run(ids: list[int], run_id: str) -> dict[int, dict[str, Any]]:
    with connect() as conn:
        rows = conn.execute(
            """
            SELECT content_item_id, result_json
            FROM paper_intelligence.paper_classification_results
            WHERE task_type = 'quality'
              AND model LIKE %s
              AND run_id = %s::uuid
              AND content_item_id = ANY(%s)
            """,
            ("%terra%", run_id, ids),
        ).fetchall()
    out: dict[int, dict[str, Any]] = {}
    for r in rows:
        rj = r["result_json"] or {}
        if isinstance(rj, str):
            rj = json.loads(rj)
        dims = {d: float(rj[d]) for d in QUALITY_DIMS if rj.get(d) is not None}
        if len(dims) < len(QUALITY_DIMS):
            continue
        comp = rj.get("composite") or {}
        if isinstance(comp, dict) and comp.get("quality") is not None:
            quality = float(comp["quality"])
        else:
            quality = float(composite_score(dims)["quality"])
        out[int(r["content_item_id"])] = {
            "scores": dims,
            "composite": quality,
            "final": float(comp["final"])
            if isinstance(comp, dict) and comp.get("final") is not None
            else float(composite_score(dims)["final"]),
        }
    return out


def _load_existing_terra_golden(labeller: str, label_round: str, exclude_run: str | None) -> dict[int, float]:
    """Terra composites for the other golden papers (non-gate), for ranking context."""
    with connect() as conn:
        humans = conn.execute(
            """
            SELECT paper_id FROM paper_intelligence.golden_human_scores
            WHERE labeller = %s AND label_round = %s
              AND sample_stratum <> ALL(%s)
            """,
            (labeller, label_round, list(STRATA)),
        ).fetchall()
        ids = [int(r["paper_id"]) for r in humans]
        if exclude_run:
            rows = conn.execute(
                """
                SELECT DISTINCT ON (q.content_item_id)
                  q.content_item_id, q.result_json
                FROM paper_intelligence.paper_classification_results q
                WHERE q.task_type = 'quality'
                  AND q.model LIKE %s
                  AND q.content_item_id = ANY(%s)
                  AND (q.run_id IS NULL OR q.run_id <> %s::uuid)
                ORDER BY q.content_item_id, q.created_at DESC
                """,
                ("%terra%", ids, exclude_run),
            ).fetchall()
        else:
            rows = conn.execute(
                """
                SELECT DISTINCT ON (q.content_item_id)
                  q.content_item_id, q.result_json
                FROM paper_intelligence.paper_classification_results q
                WHERE q.task_type = 'quality'
                  AND q.model LIKE %s
                  AND q.content_item_id = ANY(%s)
                ORDER BY q.content_item_id, q.created_at DESC
                """,
                ("%terra%", ids),
            ).fetchall()
    out: dict[int, float] = {}
    for r in rows:
        rj = r["result_json"] or {}
        if isinstance(rj, str):
            rj = json.loads(rj)
        dims = {d: float(rj[d]) for d in QUALITY_DIMS if rj.get(d) is not None}
        if len(dims) < len(QUALITY_DIMS):
            continue
        comp = rj.get("composite") or {}
        if isinstance(comp, dict) and comp.get("quality") is not None:
            out[int(r["content_item_id"])] = float(comp["quality"])
        else:
            out[int(r["content_item_id"])] = float(composite_score(dims)["quality"])
    return out


def main() -> int:
    args = _args()
    gate = _load_gate_rows(args.labeller, args.label_round)
    if len(gate) != 24:
        print(f"WARNING: expected 24 gate-drop rows, got {len(gate)}", flush=True)
    ids = [int(r["paper_id"]) for r in gate]
    print(f"gate_drop_n={len(ids)} model={QUALITY_MODEL}", flush=True)

    REPORT_DIR.mkdir(parents=True, exist_ok=True)

    with connect() as conn:
        if args.dry_run:
            run_id = str(uuid.uuid4())
            stage_run_id = str(uuid.uuid4())
            stats = run_window(
                conn,
                ids,
                run_id=run_id,
                stage_run_id=stage_run_id,
                model=QUALITY_MODEL,
                dry_run=True,
                max_cost_usd=args.max_cost_usd,
            )
            print(
                json.dumps(
                    {
                        "dry_run": True,
                        "papers": len(ids),
                        "est_cost_usd": stats.cost_usd,
                        "calls": stats.calls,
                    },
                    indent=2,
                )
            )
            return 0

        run_id = start_pipeline_run(
            conn,
            pipeline_name=PIPELINE_NAME,
            trigger_type="manual",
            created_by="golden_g3b",
            metadata={
                "purpose": "score screen_failed+flagged for gate-drop measurement",
                "not_current_quality": True,
                "labeller": args.labeller,
                "label_round": args.label_round,
                "paper_ids": ids,
                "max_cost_usd": args.max_cost_usd,
            },
        )
        stage_run_id = start_stage_run(
            conn,
            run_id,
            stage_name="quality",
            stage_version=STAGE_VERSION,
            prompt_version=PROMPT_VERSION,
            policy_version=POLICY_VERSION,
            items_input=len(ids),
        )
        try:
            stats = run_window(
                conn,
                ids,
                run_id=run_id,
                stage_run_id=stage_run_id,
                model=QUALITY_MODEL,
                dry_run=False,
                max_cost_usd=args.max_cost_usd,
            )
            finish_stage_run(
                conn,
                stage_run_id,
                status="succeeded" if stats.papers_failed == 0 else "partial",
                items_success=stats.papers_succeeded,
                items_failed=stats.papers_failed,
                error_summary=None
                if not stats.errors
                else "; ".join(stats.errors)[:500],
            )
            finish_pipeline_run(
                conn,
                run_id,
                status="succeeded" if stats.papers_failed == 0 else "partial",
                items_input=stats.papers_requested,
                items_succeeded=stats.papers_succeeded,
                items_failed=stats.papers_failed,
                metadata={
                    "cost_usd": stats.cost_usd,
                    "pipeline": PIPELINE_NAME,
                    "calls": stats.calls,
                },
            )
        except Exception as exc:
            finish_stage_run(
                conn,
                stage_run_id,
                status="failed",
                error_summary=str(exc)[:500],
            )
            finish_pipeline_run(
                conn, run_id, status="failed", metadata={"error": str(exc)[:500]}
            )
            raise

    RUN_META.write_text(
        json.dumps(
            {
                "run_id": run_id,
                "pipeline_name": PIPELINE_NAME,
                "model": QUALITY_MODEL,
                "generated_at": datetime.now(timezone.utc).isoformat(),
                "paper_ids": ids,
                "cost_usd": getattr(stats, "cost_usd", None),
                "not_current_quality": True,
            },
            indent=2,
        ),
        encoding="utf-8",
    )

    scored = _load_terra_for_run(ids, run_id)
    existing = _load_existing_terra_golden(args.labeller, args.label_round, exclude_run=run_id)

    # Rank among the other 200 = gate drops + existing scored golden papers
    # Build full list of (paper_id, composite) for all golden with a terra score
    all_scores: dict[int, float] = dict(existing)
    for cid, rec in scored.items():
        all_scores[cid] = float(rec["composite"])

    ranked = sorted(all_scores.items(), key=lambda t: (-t[1], t[0]))
    rank_of = {cid: i + 1 for i, (cid, _) in enumerate(ranked)}
    n_pool = len(ranked)

    shortlist_or_winner = [
        r
        for r in gate
        if r.get("h_newsletter_verdict") in ("shortlist", "winner_material")
    ]

    per_paper = []
    for r in gate:
        cid = int(r["paper_id"])
        rec = scored.get(cid)
        per_paper.append(
            {
                "paper_id": cid,
                "arxiv_id": r.get("arxiv_id"),
                "sample_stratum": r["sample_stratum"],
                "h_verdict": r.get("h_newsletter_verdict"),
                "h_final_score": float(r["h_final_score"])
                if r.get("h_final_score") is not None
                else None,
                "terra_composite": rec["composite"] if rec else None,
                "terra_final": rec.get("final") if rec else None,
                "terra_dims": rec["scores"] if rec else None,
                "rank_among_golden_with_terra": rank_of.get(cid),
                "pool_n": n_pool,
            }
        )

    # How gate-drop human shortlist/winner would have ranked
    interesting = [
        p
        for p in per_paper
        if p["h_verdict"] in ("shortlist", "winner_material")
    ]

    report = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "run_id": run_id,
        "pipeline_name": PIPELINE_NAME,
        "model": QUALITY_MODEL,
        "cost_usd": getattr(stats, "cost_usd", None),
        "n_gate_drop": len(gate),
        "n_scored": len(scored),
        "n_existing_terra_golden": len(existing),
        "pool_n": n_pool,
        "human_shortlist_or_winner_n": len(shortlist_or_winner),
        "human_shortlist_or_winner": [
            {
                "paper_id": int(r["paper_id"]),
                "stratum": r["sample_stratum"],
                "verdict": r["h_newsletter_verdict"],
                "h_final": float(r["h_final_score"])
                if r.get("h_final_score") is not None
                else None,
            }
            for r in shortlist_or_winner
        ],
        "interesting_ranks": interesting,
        "per_paper": per_paper,
        "notes": [
            "Scores written under dedicated pipeline run; excluded from current-quality "
            "comparison via reports/golden/g3b_run.json.",
            "Rank is among all golden papers that have a Terra quality composite "
            f"(gate drops + previously scored non-gate; pool_n={n_pool}).",
        ],
    }
    REPORT_JSON.write_text(json.dumps(report, indent=2, default=str), encoding="utf-8")

    lines = [
        "# G3b — Terra scores for screen_failed + flagged (gate-drop eval)",
        "",
        f"**Generated:** {report['generated_at']}  ",
        f"**run_id:** `{run_id}` (pipeline `{PIPELINE_NAME}` — NOT current quality)  ",
        f"**Model:** `{QUALITY_MODEL}` · **cost:** ${report['cost_usd'] or 0:.4f} (cap ${args.max_cost_usd})  ",
        f"**Scored:** {len(scored)}/{len(gate)}  ",
        f"**Rank pool:** {n_pool} golden papers with Terra composites  ",
        "",
        "## What the screen gate drops (human labels)",
        "",
        f"Of the **{len(gate)}** screen_failed+flagged papers, "
        f"**{len(shortlist_or_winner)}** were labelled `shortlist` or `winner_material`:",
        "",
        "| paper_id | stratum | verdict | h_final | terra_composite | rank / pool |",
        "|---:|---|---|---:|---:|---:|",
    ]
    for p in interesting:
        lines.append(
            f"| {p['paper_id']} | {p['sample_stratum']} | {p['h_verdict']} | "
            f"{p['h_final_score']} | {p['terra_composite']} | "
            f"{p['rank_among_golden_with_terra']} / {p['pool_n']} |"
        )
    if not interesting:
        lines.append("| _(none)_ | | | | | |")

    lines += [
        "",
        "## All 24 gate-drop papers",
        "",
        "| paper_id | stratum | h_verdict | h_final | terra_composite | rank / pool |",
        "|---:|---|---|---:|---:|---:|",
    ]
    for p in per_paper:
        lines.append(
            f"| {p['paper_id']} | {p['sample_stratum']} | {p['h_verdict']} | "
            f"{p['h_final_score']} | {p['terra_composite']} | "
            f"{p['rank_among_golden_with_terra']} / {p['pool_n']} |"
        )
    lines += [
        "",
        "## Notes",
        "",
    ]
    for n in report["notes"]:
        lines.append(f"- {n}")
    lines.append("")
    REPORT_MD.write_text("\n".join(lines), encoding="utf-8")

    print(f"wrote {RUN_META}", flush=True)
    print(f"wrote {REPORT_JSON}", flush=True)
    print(f"wrote {REPORT_MD}", flush=True)
    print(
        json.dumps(
            {
                "run_id": run_id,
                "cost_usd": report["cost_usd"],
                "n_scored": len(scored),
                "human_shortlist_or_winner_n": len(shortlist_or_winner),
            },
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
