#!/usr/bin/env python3
"""Run a single PaperIntelligence stage.

Paid stages require --from/--until and --allow-paid.
Free stages: ingest, normalize_authors, adjudication.
"""

from __future__ import annotations

import argparse
import sys
import uuid
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))


PAID_STAGES = frozenset({"screen", "audience_domain", "classify", "quality"})
FREE_STAGES = frozenset(
    {"ingest", "relevance", "normalize_authors", "hf_signals", "adjudication"}
)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Run one pipeline stage")
    parser.add_argument("--stage", required=True)
    parser.add_argument("--from", dest="date_from", default=None)
    parser.add_argument("--until", dest="date_until", default=None)
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--allow-paid", action="store_true")
    parser.add_argument("--limit", type=int, default=None)
    parser.add_argument("--content-item-id", type=int, default=None)
    parser.add_argument(
        "--reprocess",
        action="store_true",
        help="re-run papers that already have a result for this stage",
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="ingest only: re-harvest windows already marked COMPLETE",
    )
    parser.add_argument(
        "--gate-percentile",
        type=float,
        default=None,
        help="quality only: top %% of screen survivors to score (default GATE_PERCENTILE)",
    )
    args = parser.parse_args(argv)

    # Brief name is audience_domain; classify kept as alias.
    if args.stage == "classify":
        args.stage = "audience_domain"

    if args.stage == "ingest":
        return _run_ingest(args)

    if args.stage == "relevance":
        return _run_relevance(args)

    if args.stage == "hf_signals":
        return _run_hf_signals(args)

    if args.stage == "normalize_authors":
        return _run_normalize(args)

    if args.stage == "adjudication":
        return _run_adjudication(args)

    if args.stage in PAID_STAGES:
        return _run_paid(args)

    known = ", ".join(sorted((FREE_STAGES | PAID_STAGES) - {"classify"}))
    print(f"run_stage.py: unknown stage={args.stage} (known: {known})", file=sys.stderr)
    return 2


def _run_relevance(args: argparse.Namespace) -> int:
    """Free deterministic relevance; rejected papers archived to S3."""
    from paper_intelligence.db import connect
    from paper_intelligence.observability import (
        finish_pipeline_run,
        finish_stage_run,
        start_pipeline_run,
        start_stage_run,
    )
    from paper_intelligence.relevance import STAGE_VERSION, run_window

    if not (args.date_from and args.date_until):
        print("relevance requires both --from and --until", file=sys.stderr)
        return 2

    if args.dry_run:
        summary = run_window(
            args.date_from,
            args.date_until,
            dry_run=True,
            limit=args.limit,
            reprocess=bool(args.reprocess),
        )
        print(f"PROJECTION relevance: {summary}")
        return 0

    with connect() as conn:
        run_id = start_pipeline_run(
            conn,
            pipeline_name="paper_intelligence.relevance",
            trigger_type="manual",
            metadata={"date_from": args.date_from, "date_until": args.date_until},
        )
        stage_run_id = start_stage_run(
            conn, run_id, stage_name="relevance", stage_version=STAGE_VERSION
        )
        try:
            summary = run_window(
                args.date_from,
                args.date_until,
                conn=conn,
                limit=args.limit,
                reprocess=bool(args.reprocess),
                run_id=run_id,
            )
            finish_stage_run(
                conn,
                stage_run_id,
                status="succeeded",
                items_success=int(summary.get("kept") or 0),
                items_failed=int(summary.get("errors") or 0),
            )
            finish_pipeline_run(
                conn,
                run_id,
                status="succeeded",
                items_input=int(summary.get("candidates") or 0),
                items_succeeded=int(summary.get("kept") or 0),
                items_skipped=int(summary.get("rejected") or 0),
                items_failed=int(summary.get("errors") or 0),
                metadata=summary,
            )
            print(f"relevance ok: {summary}")
            return 0
        except Exception as exc:  # noqa: BLE001
            finish_stage_run(
                conn, stage_run_id, status="failed", error_summary=str(exc)[:500]
            )
            finish_pipeline_run(conn, run_id, status="failed")
            print(f"relevance failed: {exc}", file=sys.stderr)
            return 1


def _run_hf_signals(args: argparse.Namespace) -> int:
    """Free HF Daily Papers enrichment joined by arxiv_id (not a second ingest)."""
    from paper_intelligence.db import connect
    from paper_intelligence.hf_signals import STAGE_VERSION, run_window
    from paper_intelligence.observability import (
        finish_pipeline_run,
        finish_stage_run,
        start_pipeline_run,
        start_stage_run,
    )

    if not (args.date_from and args.date_until):
        print("hf_signals requires both --from and --until", file=sys.stderr)
        return 2

    if args.dry_run:
        summary = run_window(
            args.date_from, args.date_until, dry_run=True, limit=args.limit
        )
        print(f"PROJECTION hf_signals: {summary}")
        return 0

    with connect() as conn:
        run_id = start_pipeline_run(
            conn,
            pipeline_name="paper_intelligence.hf_signals",
            trigger_type="manual",
            metadata={"date_from": args.date_from, "date_until": args.date_until},
        )
        stage_run_id = start_stage_run(
            conn, run_id, stage_name="hf_signals", stage_version=STAGE_VERSION
        )
        try:
            summary = run_window(
                args.date_from,
                args.date_until,
                conn=conn,
                limit=args.limit,
                run_id=run_id,
                stage_run_id=stage_run_id,
            )
            finish_stage_run(
                conn,
                stage_run_id,
                status="succeeded",
                items_success=int(summary.get("wrote") or 0),
            )
            finish_pipeline_run(
                conn,
                run_id,
                status="succeeded",
                items_input=int(summary.get("window_arxiv_papers") or 0),
                items_succeeded=int(summary.get("wrote") or 0),
                metadata=summary,
            )
            print(f"hf_signals ok: {summary}")
            return 0
        except Exception as exc:  # noqa: BLE001
            finish_stage_run(
                conn, stage_run_id, status="failed", error_summary=str(exc)[:500]
            )
            finish_pipeline_run(conn, run_id, status="failed")
            print(f"hf_signals failed: {exc}", file=sys.stderr)
            return 1


def _run_ingest(args: argparse.Namespace) -> int:
    """Free OAI-PMH harvest into research_radar.content_items / paper_metadata."""
    from paper_intelligence.db import connect
    from paper_intelligence.ingest import STAGE_VERSION, run_window
    from paper_intelligence.observability import (
        finish_pipeline_run,
        finish_stage_run,
        start_pipeline_run,
        start_stage_run,
    )

    if not (args.date_from and args.date_until):
        print("ingest requires both --from and --until", file=sys.stderr)
        return 2

    if args.dry_run:
        summary = run_window(args.date_from, args.date_until, dry_run=True)
        print(f"PROJECTION ingest: windows={summary.get('total_windows')}")
        return 0

    with connect() as conn:
        run_id = start_pipeline_run(
            conn,
            pipeline_name="paper_intelligence.ingest",
            trigger_type="manual",
            metadata={"date_from": args.date_from, "date_until": args.date_until},
        )
        stage_run_id = start_stage_run(
            conn, run_id, stage_name="ingest", stage_version=STAGE_VERSION
        )
        try:
            summary = run_window(
                args.date_from,
                args.date_until,
                conn=conn,
                force=bool(args.force),
            )
            finish_stage_run(
                conn,
                stage_run_id,
                status="succeeded",
                items_success=int(summary.get("records_new") or 0),
            )
            finish_pipeline_run(
                conn,
                run_id,
                status="succeeded",
                items_input=int(summary.get("records_seen") or 0),
                items_succeeded=int(summary.get("records_new") or 0),
                items_skipped=int(summary.get("records_dupe") or 0),
                metadata=summary,
            )
            print(f"ingest ok: {summary}")
            return 0
        except Exception as exc:  # noqa: BLE001
            finish_stage_run(conn, stage_run_id, status="failed", error_summary=str(exc)[:500])
            finish_pipeline_run(conn, run_id, status="failed")
            print(f"ingest failed: {exc}", file=sys.stderr)
            return 1


def _run_adjudication(args: argparse.Namespace) -> int:
    """Free deterministic collapse of stage results into current state."""
    from paper_intelligence.adjudication import run_window
    from paper_intelligence.db import connect
    from paper_intelligence.observability import (
        finish_pipeline_run,
        finish_stage_run,
        start_pipeline_run,
        start_stage_run,
    )

    if not (args.date_from and args.date_until):
        print("adjudication requires both --from and --until", file=sys.stderr)
        return 2

    with connect() as conn:
        if args.dry_run:
            stats = run_window(
                conn, date_from=args.date_from, date_until=args.date_until, dry_run=True
            )
            print(f"PROJECTION adjudication: {stats}")
            return 0

        run_id = start_pipeline_run(
            conn,
            pipeline_name="paper_intelligence.adjudication",
            trigger_type="manual",
            metadata={"date_from": args.date_from, "date_until": args.date_until},
        )
        stage_run_id = start_stage_run(
            conn, run_id, stage_name="adjudication", stage_version="v001", policy_version="v001"
        )
        stats = run_window(
            conn, date_from=args.date_from, date_until=args.date_until, run_id=run_id
        )
        finish_stage_run(
            conn,
            stage_run_id,
            status="succeeded",
            items_success=stats["written"],
        )
        finish_pipeline_run(
            conn,
            run_id,
            status="succeeded",
            items_input=stats["papers"],
            items_succeeded=stats["written"],
            metadata=stats,
        )
        print(
            f"adjudication: {stats['papers']} papers, {stats['written']} current-state rows, "
            f"{stats['with_quality']} with quality, {stats['with_org']} with a resolved "
            f"organisation, {stats['disagreements']} screen/quality disagreements"
        )
    return 0


def _run_paid(args: argparse.Namespace) -> int:
    """screen / classify / quality: batched OpenRouter stages."""
    from paper_intelligence.common.config import (
        CLASSIFY_MODEL,
        GATE_PERCENTILE,
        QUALITY_MODEL,
        SCREEN_MIN_AI_RELEVANCE,
        SCREEN_MODEL,
    )
    from paper_intelligence.db import connect, select_window_candidates
    from paper_intelligence.observability import (
        finish_pipeline_run,
        finish_stage_run,
        start_pipeline_run,
        start_stage_run,
    )

    if not (args.date_from and args.date_until):
        print(f"{args.stage} requires both --from and --until", file=sys.stderr)
        return 2
    if not args.dry_run and not args.allow_paid:
        print(
            f"{args.stage} spends money. Re-run with --allow-paid, or use --dry-run "
            "for a cost projection.",
            file=sys.stderr,
        )
        return 2

    stage_modules = {
        "screen": ("paper_intelligence.screen", "screen", SCREEN_MODEL),
        "audience_domain": (
            "paper_intelligence.audience_domain",
            "domain",
            CLASSIFY_MODEL,
        ),
        "quality": ("paper_intelligence.quality", "quality", QUALITY_MODEL),
    }
    module_name, task_type, model = stage_modules[args.stage]
    module = __import__(module_name, fromlist=["run_window"])

    with connect() as conn:
        if args.content_item_id is not None:
            ids = [args.content_item_id]
        elif args.stage == "quality":
            from paper_intelligence.quality import select_quality_candidates

            ids = select_quality_candidates(
                conn,
                date_from=args.date_from,
                date_until=args.date_until,
                gate_percentile=args.gate_percentile or GATE_PERCENTILE,
            )
            if not args.reprocess:
                from paper_intelligence.db import ids_with_result

                done = ids_with_result(
                    conn,
                    ids,
                    "quality",
                    stage_version=module.STAGE_VERSION,
                    prompt_version=module.PROMPT_VERSION,
                    policy_version=module.POLICY_VERSION,
                    model=model,
                )
                ids = [i for i in ids if i not in done]
        elif args.stage == "audience_domain":
            ids = _audience_domain_candidates(conn, args, module=module, model=model)
        else:
            ids = select_window_candidates(
                conn,
                date_from=args.date_from,
                date_until=args.date_until,
                stage_task_type=task_type,
                limit=args.limit,
                skip_done=not args.reprocess,
                stage_version=module.STAGE_VERSION,
                prompt_version=module.PROMPT_VERSION,
                policy_version=module.POLICY_VERSION,
                model=model,
            )

        if args.limit:
            ids = ids[: args.limit]

        print(
            f"stage={args.stage} model={model} candidates={len(ids)} "
            f"from={args.date_from} until={args.date_until} dry_run={args.dry_run}"
        )
        if args.stage == "screen" and not args.dry_run:
            print(f"  gate: ai_relevance >= {SCREEN_MIN_AI_RELEVANCE}")
        if not ids:
            print("nothing to do")
            return 0

        if args.dry_run:
            stats = module.run_window(
                conn, ids, run_id="dry-run", stage_run_id="dry-run", dry_run=True
            )
            print(
                f"PROJECTION {args.stage}: {len(ids)} papers, ~{stats.calls} calls, "
                f"~{stats.input_tokens} in / ~{stats.output_tokens} out tokens, "
                f"~${stats.cost_usd:.2f}"
            )
            return 0

        run_id = start_pipeline_run(
            conn,
            pipeline_name=f"paper_intelligence.{args.stage}",
            trigger_type="manual",
            metadata={
                "date_from": args.date_from,
                "date_until": args.date_until,
                "model": model,
                "candidates": len(ids),
            },
        )
        stage_run_id = start_stage_run(
            conn,
            run_id,
            stage_name=task_type,
            stage_version=module.STAGE_VERSION,
            prompt_version=module.PROMPT_VERSION,
            policy_version=module.POLICY_VERSION,
            items_input=len(ids),
        )
        print(f"  run_id={run_id}")

        stats = module.run_window(conn, ids, run_id=run_id, stage_run_id=stage_run_id)

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
            items_input=len(ids),
            items_succeeded=stats.papers_succeeded,
            items_failed=stats.papers_failed,
            metadata={"cost_usd": round(stats.cost_usd, 4), "calls": stats.calls},
        )

        print(stats.summary_line(args.stage))
        for warning in stats.warnings[:10]:
            print(f"  WARN {warning}")
        for error in stats.errors[:10]:
            print(f"  ERROR {error}", file=sys.stderr)
        return 0 if stats.papers_failed == 0 else 1


def _audience_domain_candidates(
    conn, args: argparse.Namespace, *, module=None, model: str | None = None
) -> list[int]:
    """Screen survivors that still need audience/domain classification."""
    from paper_intelligence.db import latest_screen_scores, select_window_candidates

    survivors = {
        int(row["content_item_id"])
        for row in latest_screen_scores(
            conn, date_from=args.date_from, date_until=args.date_until
        )
        if ((row["result_json"] or {}).get("gate") or {}).get("passed")
    }
    pending = select_window_candidates(
        conn,
        date_from=args.date_from,
        date_until=args.date_until,
        stage_task_type="domain",
        skip_done=not args.reprocess,
        stage_version=getattr(module, "STAGE_VERSION", None),
        prompt_version=getattr(module, "PROMPT_VERSION", None),
        policy_version=getattr(module, "POLICY_VERSION", None),
        model=model,
    )
    return [i for i in pending if i in survivors]


def _classify_candidates(conn, args: argparse.Namespace) -> list[int]:
    """Alias kept for older call sites."""
    return _audience_domain_candidates(conn, args)


def _run_normalize(args: argparse.Namespace) -> int:
    from paper_intelligence.common import RunContext
    from paper_intelligence.db import connect
    from paper_intelligence.normalize import NormalizeAuthorsStage

    if args.content_item_id is None and not (args.date_from and args.date_until):
        print(
            "normalize_authors requires --content-item-id or both --from and --until",
            file=sys.stderr,
        )
        return 2

    ctx = RunContext(
        run_id=str(uuid.uuid4()),
        stage_run_id=str(uuid.uuid4()),
        dry_run=args.dry_run,
    )
    stage = NormalizeAuthorsStage()

    ids: list[int]
    if args.content_item_id is not None:
        ids = [args.content_item_id]
    else:
        from paper_intelligence.db.results import PI_ELIGIBLE_STATUSES

        with connect() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT id FROM research_radar.content_items
                    WHERE published_at >= %s::timestamptz
                      AND published_at < (%s::timestamptz + interval '1 day')
                      AND status = ANY(%s)
                    ORDER BY id
                    LIMIT %s
                    """,
                    (
                        args.date_from,
                        args.date_until,
                        list(PI_ELIGIBLE_STATUSES),
                        args.limit if args.limit is not None else 100_000,
                    ),
                )
                ids = [int(r["id"]) for r in cur.fetchall()]

    # Date-window runs should cover the full window unless --limit is set.
    # The old default of 100 silently truncated multi-day backfills.

    print(
        f"stage=normalize_authors version=v001 dry_run={args.dry_run} "
        f"candidates={len(ids)} from={args.date_from} until={args.date_until}"
    )
    ok = fail = 0
    for content_id in ids:
        result = stage.process(content_id, ctx)
        if result.status == "success":
            ok += 1
            print(
                f"  ok content_item_id={content_id} "
                f"authors={result.data.get('author_count')}"
            )
        else:
            fail += 1
            print(
                f"  FAIL content_item_id={content_id} "
                f"{result.metadata.get('error_message')}",
                file=sys.stderr,
            )
    print(f"done succeeded={ok} failed={fail}")
    return 0 if fail == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
