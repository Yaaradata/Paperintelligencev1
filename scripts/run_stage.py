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
    parser.add_argument(
        "--max-cost-usd",
        type=float,
        default=None,
        help="refuse / stop paid work when projected or actual spend would exceed this "
        "(also env PI_MAX_COST_USD)",
    )
    parser.add_argument(
        "--force-over-projection",
        action="store_true",
        help="allow starting a paid run even when the dry-run projection exceeds the cap",
    )
    parser.add_argument(
        "--budget-state",
        default=None,
        help="optional JSON ledger path for pipeline cumulative spend tracking",
    )
    parser.add_argument(
        "--allow-quality-model-change",
        action="store_true",
        help="adjudication: allow quality rows whose model ≠ date mapping",
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
    from paper_intelligence.adjudication.model_guard import count_quality_rows_staled_by_model
    from paper_intelligence.common.budget import format_model_banner
    from paper_intelligence.common.config import (
        CLASSIFY_MODEL,
        QUALITY_MODEL,
        SCREEN_MODEL,
    )
    from paper_intelligence.db import connect
    from paper_intelligence.observability import (
        finish_pipeline_run,
        finish_stage_run,
        start_pipeline_run,
        start_stage_run,
    )
    from paper_intelligence.quality.model_policy import (
        load_quality_model_policy,
        quality_model_env_override,
    )

    if not (args.date_from and args.date_until):
        print("adjudication requires both --from and --until", file=sys.stderr)
        return 2

    policy = load_quality_model_policy()
    print(
        format_model_banner(
            screen_model=SCREEN_MODEL,
            classify_model=CLASSIFY_MODEL,
            quality_model=(
                quality_model_env_override()
                or f"mapped(pre={policy['pre_cutover_model']},post={policy['post_cutover_model']},"
                f"cutover={policy['cutover_date']})"
            ),
        ),
        flush=True,
    )

    with connect() as conn:
        guard = count_quality_rows_staled_by_model(
            conn,
            date_from=args.date_from,
            date_until=args.date_until,
        )
        mismatch = int(guard["mapping_mismatch"] or 0)
        if mismatch and not args.allow_quality_model_change:
            print(
                f"adjudication refused: {mismatch} quality row(s) in "
                f"{args.date_from}..{args.date_until} have model ≠ date mapping "
                f"(cutover={guard['cutover_date']}; "
                f"pre={guard['pre_cutover_model']}; post={guard['post_cutover_model']}). "
                f"Pass --allow-quality-model-change if intentional.",
                file=sys.stderr,
            )
            return 2
        if mismatch and args.allow_quality_model_change:
            print(
                f"WARNING: --allow-quality-model-change: {mismatch} mapping-mismatch "
                f"quality row(s) will not count as scored",
                flush=True,
            )
        if guard.get("env_override"):
            print(
                f"WARNING: QUALITY_MODEL env override={guard['env_override']!r} "
                f"is set; mapped models still drive adjudication currentness",
                flush=True,
            )

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
            metadata={
                "date_from": args.date_from,
                "date_until": args.date_until,
                "quality_model_policy": {
                    "cutover_date": str(policy["cutover_date"]),
                    "pre_cutover_model": policy["pre_cutover_model"],
                    "post_cutover_model": policy["post_cutover_model"],
                    "env_override": quality_model_env_override(),
                },
            },
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
            f"organisation, {stats['disagreements']} screen/quality disagreements, "
            f"inconsistent_attempt_without_result="
            f"{stats.get('inconsistent_attempt_without_result', 0)}, "
            f"stale_content={stats.get('stale_content', 0)}, "
            f"quality_models={stats.get('quality_models_seen')}"
        )
    return 0


def _run_paid(args: argparse.Namespace) -> int:
    """screen / classify / quality: batched OpenRouter stages."""
    from paper_intelligence.common.budget import (
        format_budget_line,
        format_model_banner,
        resolve_max_cost_usd,
        update_budget_state_after_stage,
    )
    from paper_intelligence.common.config import (
        CLASSIFY_MODEL,
        GATE_PERCENTILE,
        QUALITY_MODEL,
        SCREEN_MIN_AI_RELEVANCE,
        SCREEN_MODEL,
        UnknownModelPriceError,
        require_model_priced,
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
        "quality": ("paper_intelligence.quality", "quality", None),
    }
    module_name, task_type, model = stage_modules[args.stage]
    module = __import__(module_name, fromlist=["run_window"])

    from paper_intelligence.quality.model_policy import (
        load_quality_model_policy,
        quality_model_env_override,
    )

    q_policy = load_quality_model_policy()
    quality_banner = quality_model_env_override() or (
        f"mapped(pre={q_policy['pre_cutover_model']},"
        f"post={q_policy['post_cutover_model']},cutover={q_policy['cutover_date']})"
    )
    print(
        format_model_banner(
            screen_model=SCREEN_MODEL,
            classify_model=CLASSIFY_MODEL,
            quality_model=quality_banner if args.stage == "quality" else (QUALITY_MODEL or quality_banner),
        ),
        flush=True,
    )
    try:
        if args.stage == "quality":
            require_model_priced(q_policy["pre_cutover_model"])
            require_model_priced(q_policy["post_cutover_model"])
            if quality_model_env_override():
                require_model_priced(quality_model_env_override())
        else:
            require_model_priced(model)
        require_model_priced(SCREEN_MODEL)
        require_model_priced(CLASSIFY_MODEL)
        require_model_priced(q_policy["pre_cutover_model"])
        require_model_priced(q_policy["post_cutover_model"])
    except UnknownModelPriceError as exc:
        print(f"paid stage refused: {exc}", file=sys.stderr)
        return 2

    max_cost = resolve_max_cost_usd(args.max_cost_usd)

    with connect() as conn:
        if args.stage == "quality":
            return _run_quality_paid(
                args, conn, module=module, max_cost=max_cost, q_policy=q_policy
            )

        if args.content_item_id is not None:
            ids = [args.content_item_id]
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
            print(
                format_budget_line(projected=0.0, actual=0.0, cap=max_cost, stopped=False),
                flush=True,
            )
            return 0

        projected = module.run_window(
            conn, ids, run_id="dry-run", stage_run_id="dry-run", dry_run=True, model=model
        )
        print(
            f"PROJECTION {args.stage}: {len(ids)} papers, ~{projected.calls} calls, "
            f"~{projected.input_tokens} in / ~{projected.output_tokens} out tokens, "
            f"~${projected.cost_usd:.2f}"
        )

        if args.dry_run:
            print(
                format_budget_line(
                    projected=projected.cost_usd,
                    actual=0.0,
                    cap=max_cost,
                    stopped=False,
                ),
                flush=True,
            )
            return 0

        if (
            max_cost is not None
            and projected.cost_usd > max_cost
            and not args.force_over_projection
        ):
            print(
                f"refusing {args.stage}: projected ${projected.cost_usd:.4f} exceeds "
                f"cap ${max_cost:.4f}. Pass --force-over-projection to override the "
                f"pre-check (live cap still enforced during the run).",
                file=sys.stderr,
            )
            print(
                format_budget_line(
                    projected=projected.cost_usd,
                    actual=0.0,
                    cap=max_cost,
                    stopped=True,
                ),
                flush=True,
            )
            return 2

        run_id = start_pipeline_run(
            conn,
            pipeline_name=f"paper_intelligence.{args.stage}",
            trigger_type="manual",
            metadata={
                "date_from": args.date_from,
                "date_until": args.date_until,
                "model": model,
                "models": {
                    "screen": SCREEN_MODEL,
                    "classify": CLASSIFY_MODEL,
                    "quality": QUALITY_MODEL,
                },
                "candidates": len(ids),
                "max_cost_usd": max_cost,
                "projected_cost_usd": round(projected.cost_usd, 6),
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

        stats = module.run_window(
            conn,
            ids,
            run_id=run_id,
            stage_run_id=stage_run_id,
            max_cost_usd=max_cost,
        )

        stopped = bool(stats.stopped_budget_cap)
        if stopped:
            status = "stopped_budget_cap"
        elif stats.papers_failed == 0:
            status = "succeeded"
        else:
            status = "partial"

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
            metadata={
                "cost_usd": round(stats.cost_usd, 4),
                "projected_cost_usd": round(projected.cost_usd, 6),
                "estimated_cost_usd": round(stats.estimated_cost_usd, 6),
                "actual_cost_usd": round(stats.actual_cost_usd, 6)
                if stats.calls_with_actual_cost
                else None,
                "calls_with_actual_cost": stats.calls_with_actual_cost,
                "max_cost_usd": max_cost,
                "calls": stats.calls,
                "stopped_budget_cap": stopped,
                "papers_skipped_budget": stats.papers_skipped_budget,
            },
        )

        update_budget_state_after_stage(
            args.budget_state,
            stage=args.stage,
            actual_usd=stats.cost_usd,
            projected_usd=projected.cost_usd,
            stopped_budget_cap=stopped,
        )

        from paper_intelligence.common.budget import cost_divergence_warning

        div_warn = None
        if stats.calls_with_actual_cost:
            div_warn = cost_divergence_warning(
                estimated_usd=stats.estimated_cost_usd,
                actual_usd=stats.actual_cost_usd,
            )
        print(stats.summary_line(args.stage))
        print(
            format_budget_line(
                projected=projected.cost_usd,
                actual=stats.cost_usd,
                cap=max_cost,
                stopped=stopped,
                estimated=stats.estimated_cost_usd if stats.calls_with_actual_cost else None,
                provider_actual=stats.actual_cost_usd if stats.calls_with_actual_cost else None,
                divergence_warned=bool(div_warn),
            ),
            flush=True,
        )
        if div_warn:
            print(div_warn, flush=True)
        for warning in stats.warnings[:10]:
            print(f"  WARN {warning}")
        for error in stats.errors[:10]:
            print(f"  ERROR {error}", file=sys.stderr)
        if stopped:
            return 1
        return 0 if stats.papers_failed == 0 else 1


def _run_quality_paid(
    args: argparse.Namespace,
    conn,
    *,
    module,
    max_cost: float | None,
    q_policy: dict,
) -> int:
    """Quality stage: partition candidates by date→model mapping (or env override)."""
    from paper_intelligence.common.budget import (
        format_budget_line,
        update_budget_state_after_stage,
        cost_divergence_warning,
    )
    from paper_intelligence.common.config import (
        CLASSIFY_MODEL,
        GATE_PERCENTILE,
        SCREEN_MODEL,
    )
    from paper_intelligence.db import fetch_papers, ids_with_result
    from paper_intelligence.observability import (
        finish_pipeline_run,
        finish_stage_run,
        start_pipeline_run,
        start_stage_run,
    )
    from paper_intelligence.quality import select_quality_candidates
    from paper_intelligence.quality.model_policy import (
        group_ids_by_quality_model,
        quality_model_env_override,
    )

    if args.content_item_id is not None:
        candidate_ids = [args.content_item_id]
    else:
        candidate_ids = select_quality_candidates(
            conn,
            date_from=args.date_from,
            date_until=args.date_until,
            gate_percentile=args.gate_percentile or GATE_PERCENTILE,
        )
    if args.limit:
        candidate_ids = candidate_ids[: args.limit]

    papers = fetch_papers(conn, candidate_ids) if candidate_ids else []
    # Preserve candidate order within each model group.
    paper_by_id = {int(p["content_item_id"]): p for p in papers}
    ordered_papers = [paper_by_id[i] for i in candidate_ids if i in paper_by_id]
    groups = group_ids_by_quality_model(ordered_papers)

    pending_by_model: dict[str, list[int]] = {}
    skipped_done = 0
    for model, ids in groups.items():
        if args.reprocess:
            pending_by_model[model] = ids
            continue
        done = ids_with_result(
            conn,
            ids,
            "quality",
            stage_version=module.STAGE_VERSION,
            prompt_version=module.PROMPT_VERSION,
            policy_version=module.POLICY_VERSION,
            model=model,
        )
        pending = [i for i in ids if i not in done]
        skipped_done += len(ids) - len(pending)
        if pending:
            pending_by_model[model] = pending

    total_pending = sum(len(v) for v in pending_by_model.values())
    override = quality_model_env_override()
    print(
        f"stage=quality models={dict((m, len(ids)) for m, ids in pending_by_model.items())} "
        f"candidates={len(candidate_ids)} pending={total_pending} "
        f"skipped_done={skipped_done} from={args.date_from} until={args.date_until} "
        f"dry_run={args.dry_run} env_override={override!r} "
        f"cutover={q_policy['cutover_date']}",
        flush=True,
    )
    if not total_pending:
        print("nothing to do")
        print(
            format_budget_line(projected=0.0, actual=0.0, cap=max_cost, stopped=False),
            flush=True,
        )
        return 0

    # Project per model then sum (token estimates are model-priced).
    projected_cost = 0.0
    projected_calls = 0
    projected_in = 0
    projected_out = 0
    for model, ids in pending_by_model.items():
        stats = module.run_window(
            conn, ids, run_id="dry-run", stage_run_id="dry-run", dry_run=True, model=model
        )
        projected_cost += stats.cost_usd
        projected_calls += stats.calls
        projected_in += stats.input_tokens
        projected_out += stats.output_tokens
        print(
            f"  PROJECTION quality model={model}: {len(ids)} papers, "
            f"~{stats.calls} calls, ~${stats.cost_usd:.4f}",
            flush=True,
        )
    print(
        f"PROJECTION quality: {total_pending} papers, ~{projected_calls} calls, "
        f"~{projected_in} in / ~{projected_out} out tokens, ~${projected_cost:.2f}",
        flush=True,
    )

    if args.dry_run:
        print(
            format_budget_line(
                projected=projected_cost,
                actual=0.0,
                cap=max_cost,
                stopped=False,
            ),
            flush=True,
        )
        return 0

    if (
        max_cost is not None
        and projected_cost > max_cost
        and not args.force_over_projection
    ):
        print(
            f"refusing quality: projected ${projected_cost:.4f} exceeds "
            f"cap ${max_cost:.4f}. Pass --force-over-projection to override the "
            f"pre-check (live cap still enforced during the run).",
            file=sys.stderr,
        )
        print(
            format_budget_line(
                projected=projected_cost,
                actual=0.0,
                cap=max_cost,
                stopped=True,
            ),
            flush=True,
        )
        return 2

    run_id = start_pipeline_run(
        conn,
        pipeline_name="paper_intelligence.quality",
        trigger_type="manual",
        metadata={
            "date_from": args.date_from,
            "date_until": args.date_until,
            "models": {
                "screen": SCREEN_MODEL,
                "classify": CLASSIFY_MODEL,
                "quality_by_group": {m: len(ids) for m, ids in pending_by_model.items()},
                "quality_policy": {
                    "cutover_date": str(q_policy["cutover_date"]),
                    "pre_cutover_model": q_policy["pre_cutover_model"],
                    "post_cutover_model": q_policy["post_cutover_model"],
                    "env_override": override,
                },
            },
            "candidates": total_pending,
            "max_cost_usd": max_cost,
            "projected_cost_usd": round(projected_cost, 6),
        },
    )
    print(f"  run_id={run_id}")

    # Shared budget across model groups.
    remaining_cap = max_cost
    total_succeeded = 0
    total_failed = 0
    total_cost = 0.0
    total_estimated = 0.0
    total_actual = 0.0
    total_calls = 0
    calls_with_actual = 0
    stopped = False
    papers_skipped_budget = 0
    all_warnings: list[str] = []
    all_errors: list[str] = []
    last_status = "succeeded"

    for model, ids in pending_by_model.items():
        if remaining_cap is not None and remaining_cap <= 0:
            stopped = True
            papers_skipped_budget += len(ids)
            break
        stage_run_id = start_stage_run(
            conn,
            run_id,
            stage_name="quality",
            stage_version=module.STAGE_VERSION,
            prompt_version=module.PROMPT_VERSION,
            policy_version=module.POLICY_VERSION,
            items_input=len(ids),
        )
        stats = module.run_window(
            conn,
            ids,
            run_id=run_id,
            stage_run_id=stage_run_id,
            model=model,
            max_cost_usd=remaining_cap,
        )
        group_stopped = bool(stats.stopped_budget_cap)
        if group_stopped:
            status = "stopped_budget_cap"
            stopped = True
        elif stats.papers_failed == 0:
            status = "succeeded"
        else:
            status = "partial"
        last_status = status
        finish_stage_run(
            conn,
            stage_run_id,
            status=status,
            items_success=stats.papers_succeeded,
            items_failed=stats.papers_failed,
            error_summary="; ".join(stats.errors)[:2000] or None,
        )
        total_succeeded += stats.papers_succeeded
        total_failed += stats.papers_failed
        total_cost += stats.cost_usd
        total_estimated += stats.estimated_cost_usd
        total_actual += stats.actual_cost_usd
        total_calls += stats.calls
        calls_with_actual += stats.calls_with_actual_cost
        papers_skipped_budget += stats.papers_skipped_budget
        all_warnings.extend(stats.warnings)
        all_errors.extend(stats.errors)
        if remaining_cap is not None:
            remaining_cap = max(0.0, remaining_cap - stats.cost_usd)
        print(
            f"  quality model={model}: ok={stats.papers_succeeded} "
            f"fail={stats.papers_failed} cost=${stats.cost_usd:.4f}",
            flush=True,
        )
        if stopped:
            break

    if stopped:
        pipeline_status = "stopped_budget_cap"
    elif total_failed == 0:
        pipeline_status = "succeeded"
    else:
        pipeline_status = "partial"

    finish_pipeline_run(
        conn,
        run_id,
        status=pipeline_status,
        items_input=total_pending,
        items_succeeded=total_succeeded,
        items_failed=total_failed,
        metadata={
            "cost_usd": round(total_cost, 4),
            "projected_cost_usd": round(projected_cost, 6),
            "estimated_cost_usd": round(total_estimated, 6),
            "actual_cost_usd": round(total_actual, 6) if calls_with_actual else None,
            "calls_with_actual_cost": calls_with_actual,
            "max_cost_usd": max_cost,
            "calls": total_calls,
            "stopped_budget_cap": stopped,
            "papers_skipped_budget": papers_skipped_budget,
            "quality_models": {m: len(ids) for m, ids in pending_by_model.items()},
        },
    )

    update_budget_state_after_stage(
        args.budget_state,
        stage="quality",
        actual_usd=total_cost,
        projected_usd=projected_cost,
        stopped_budget_cap=stopped,
    )

    div_warn = None
    if calls_with_actual:
        div_warn = cost_divergence_warning(
            estimated_usd=total_estimated,
            actual_usd=total_actual,
        )
    print(
        f"quality: papers={total_pending} ok={total_succeeded} fail={total_failed} "
        f"calls={total_calls} cost=${total_cost:.4f} status={last_status}",
        flush=True,
    )
    print(
        format_budget_line(
            projected=projected_cost,
            actual=total_cost,
            cap=max_cost,
            stopped=stopped,
            estimated=total_estimated if calls_with_actual else None,
            provider_actual=total_actual if calls_with_actual else None,
            divergence_warned=bool(div_warn),
        ),
        flush=True,
    )
    if div_warn:
        print(div_warn, flush=True)
    for warning in all_warnings[:10]:
        print(f"  WARN {warning}")
    for error in all_errors[:10]:
        print(f"  ERROR {error}", file=sys.stderr)
    if stopped:
        return 1
    return 0 if total_failed == 0 else 1


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
        from paper_intelligence.common.config import PI_USE_PAPERS_CATALOG
        from paper_intelligence.db.results import PI_ELIGIBLE_STATUSES

        with connect() as conn:
            if PI_USE_PAPERS_CATALOG:
                from paper_intelligence.catalog.relevance import papers_with_latest_decision

                ids = papers_with_latest_decision(
                    conn,
                    date_from=args.date_from,
                    date_until=args.date_until,
                    decision="keep",
                )
                if args.limit is not None:
                    ids = ids[: int(args.limit)]
            else:
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
