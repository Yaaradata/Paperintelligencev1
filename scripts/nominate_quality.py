#!/usr/bin/env python3
"""Editorial nomination: score specific papers with the production quality stage.

Reuses paper_intelligence.quality.run_window. Records route=editorial_nomination.
Does not change GATE_PERCENTILE, screen scores, or newsletter eligibility.

Examples:
  # Cost projection only
  PYTHONPATH=src python3 scripts/nominate_quality.py \\
    --content-item-id 137619 --dry-run

  # Paid run (after reviewing dry-run)
  PYTHONPATH=src python3 scripts/nominate_quality.py \\
    --content-item-id 137619 --allow-paid

  PYTHONPATH=src python3 scripts/nominate_quality.py \\
    --arxiv-id 2609.03181 --dry-run
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from paper_intelligence.common.config import QUALITY_MODEL
from paper_intelligence.db import connect
from paper_intelligence.observability import (
    finish_pipeline_run,
    finish_stage_run,
    start_pipeline_run,
    start_stage_run,
)
from paper_intelligence.quality.nomination import (
    ROUTE_EDITORIAL,
    describe_targets,
    filter_scoreable,
    resolve_content_ids,
)
from paper_intelligence.quality.stage import (
    POLICY_VERSION,
    PROMPT_VERSION,
    STAGE_VERSION,
    run_window,
)


def _write_report(
    output_dir: Path,
    *,
    targets: list,
    scored_ids: list[int],
    skipped: list,
    stats: dict,
    dry_run: bool,
) -> Path:
    output_dir.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    path = output_dir / f"editorial_nomination_{stamp}.json"
    payload = {
        "route": ROUTE_EDITORIAL,
        "dry_run": dry_run,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "model": QUALITY_MODEL,
        "prompt_version": PROMPT_VERSION,
        "policy_version": POLICY_VERSION,
        "stage_version": STAGE_VERSION,
        "targets": [t.__dict__ for t in targets],
        "to_score": scored_ids,
        "skipped": [t.__dict__ for t in skipped],
        "stats": stats,
        "notes": [
            "Does not mark papers newsletter-worthy.",
            "Original quality-router exclusion is preserved in exclusion_reason.",
            "Re-run adjudication after paid scoring to refresh paper_intelligence_current.",
        ],
    }
    path.write_text(json.dumps(payload, indent=2, default=str) + "\n", encoding="utf-8")
    return path


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Editorial quality nomination")
    parser.add_argument("--content-item-id", type=int, action="append", default=[])
    parser.add_argument("--arxiv-id", action="append", default=[])
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--allow-paid", action="store_true")
    parser.add_argument(
        "--reprocess",
        action="store_true",
        help="re-score even if current quality version already exists",
    )
    parser.add_argument(
        "--output-dir",
        default=str(ROOT / "reports" / "editorial"),
    )
    parser.add_argument("--nominated-by", default="editorial")
    args = parser.parse_args(argv)

    if not args.content_item_id and not args.arxiv_id:
        print("provide --content-item-id and/or --arxiv-id", file=sys.stderr)
        return 2
    if not args.dry_run and not args.allow_paid:
        print(
            "nomination spends money. Re-run with --allow-paid, or use --dry-run.",
            file=sys.stderr,
        )
        return 2

    with connect() as conn:
        try:
            ids = resolve_content_ids(
                conn,
                content_item_ids=args.content_item_id,
                arxiv_ids=args.arxiv_id,
            )
        except ValueError as exc:
            print(str(exc), file=sys.stderr)
            return 2

        targets = describe_targets(conn, ids, model=QUALITY_MODEL)
        to_score, skipped = filter_scoreable(targets, reprocess=args.reprocess)

        print("=== EDITORIAL NOMINATION ===", flush=True)
        for t in targets:
            print(
                f"  id={t.content_item_id} status={t.status} "
                f"screen_passed={t.screen_gate_passed} "
                f"rank_mean={t.screen_rank_mean} "
                f"already_scored={t.already_quality_scored}",
                flush=True,
            )
            if t.exclusion_reason:
                print(f"    router/exclusion: {t.exclusion_reason}", flush=True)
        print(f"to_score={len(to_score)} skipped={len(skipped)}", flush=True)

        if not to_score:
            report = _write_report(
                Path(args.output_dir),
                targets=targets,
                scored_ids=[],
                skipped=skipped,
                stats={"cost_usd": 0, "calls": 0, "reason": "nothing to score"},
                dry_run=args.dry_run,
            )
            print(f"wrote {report}", flush=True)
            return 0

        route_meta = {
            "nominated_by": args.nominated_by,
            "preserves_router_exclusion": True,
        }

        if args.dry_run:
            stats = run_window(
                conn,
                to_score,
                run_id="dry-run",
                stage_run_id="dry-run",
                dry_run=True,
                route=ROUTE_EDITORIAL,
                route_meta=route_meta,
            )
            report = _write_report(
                Path(args.output_dir),
                targets=targets,
                scored_ids=to_score,
                skipped=skipped,
                stats={
                    "calls": stats.calls,
                    "input_tokens": stats.input_tokens,
                    "output_tokens": stats.output_tokens,
                    "cost_usd": round(stats.cost_usd, 4),
                },
                dry_run=True,
            )
            print(
                f"PROJECTION quality nomination: {len(to_score)} papers, "
                f"~{stats.calls} calls, ~${stats.cost_usd:.4f}",
                flush=True,
            )
            print(f"wrote {report}", flush=True)
            return 0

        run_id = start_pipeline_run(
            conn,
            pipeline_name="paper_intelligence.quality_editorial_nomination",
            trigger_type="manual",
            metadata={
                "route": ROUTE_EDITORIAL,
                "model": QUALITY_MODEL,
                "candidates": to_score,
                "nominated_by": args.nominated_by,
            },
        )
        stage_run_id = start_stage_run(
            conn,
            run_id,
            stage_name="quality",
            stage_version=STAGE_VERSION,
            prompt_version=PROMPT_VERSION,
            policy_version=POLICY_VERSION,
            items_input=len(to_score),
        )
        print(f"  run_id={run_id}", flush=True)
        stats = run_window(
            conn,
            to_score,
            run_id=run_id,
            stage_run_id=stage_run_id,
            route=ROUTE_EDITORIAL,
            route_meta=route_meta,
        )
        status = "succeeded" if stats.papers_failed == 0 else "partial"
        finish_stage_run(
            conn,
            stage_run_id,
            status=status,
            items_success=stats.papers_succeeded,
            items_failed=stats.papers_failed,
            error_summary="; ".join(stats.errors)[:2000] or None,
        )
        finish_pipeline_run(
            conn,
            run_id,
            status=status,
            items_input=len(to_score),
            items_succeeded=stats.papers_succeeded,
            items_failed=stats.papers_failed,
            metadata={
                "route": ROUTE_EDITORIAL,
                "cost_usd": round(stats.cost_usd, 4),
                "calls": stats.calls,
            },
        )
        report = _write_report(
            Path(args.output_dir),
            targets=targets,
            scored_ids=to_score,
            skipped=skipped,
            stats={
                "run_id": str(run_id),
                "calls": stats.calls,
                "cost_usd": round(stats.cost_usd, 4),
                "papers_succeeded": stats.papers_succeeded,
                "papers_failed": stats.papers_failed,
            },
            dry_run=False,
        )
        print(stats.summary_line("quality_nomination"), flush=True)
        print(f"wrote {report}", flush=True)
        return 0 if stats.papers_failed == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
