#!/usr/bin/env python3
"""Orchestrate the PaperIntelligence pipeline and write top-N reports.

Order:
  ingest → relevance → normalize_authors → screen → affiliation_fast
  → audience_domain → quality → affiliation_deep → hf_signals
  → adjudication → tech/business/audience reports

Example:
  python3 scripts/run_pipeline.py \\
    --from 2026-09-01 --until 2026-09-15 \\
    --allow-paid --gate-percentile 25 --top 20

Skip early stages when rows already exist:
  python3 scripts/run_pipeline.py --from ... --until ... --from-stage normalize_authors ...
"""

from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
SCRIPTS = ROOT / "scripts"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

DEFAULT_STAGES = (
    "ingest",
    "relevance",
    "normalize_authors",
    "screen",
    "affiliation_fast",
    "audience_domain",
    "quality",
    "affiliation_deep",
    "hf_signals",
    "adjudication",
    "reports",
)

# Backward-compatible alias: "affiliation" means deep enrichment.
STAGE_ALIASES = {
    "affiliation": "affiliation_deep",
    "classify": "audience_domain",
}


def _run_stage_cli(args: argparse.Namespace, stage: str) -> int:
    cmd = [
        sys.executable,
        str(SCRIPTS / "run_stage.py"),
        "--stage",
        stage,
        "--from",
        args.date_from,
        "--until",
        args.date_until,
    ]
    if args.dry_run:
        cmd.append("--dry-run")
    if args.allow_paid and stage in {"screen", "audience_domain", "quality"}:
        cmd.append("--allow-paid")
    # normalize_authors defaults used to silently cap at 100; always cover the window.
    if stage == "normalize_authors":
        cmd.extend(["--limit", str(args.limit if args.limit is not None else 100_000)])
    elif args.limit is not None and stage not in {"adjudication", "ingest"}:
        cmd.extend(["--limit", str(args.limit)])
    if args.reprocess:
        cmd.append("--reprocess")
    if stage == "ingest" and getattr(args, "force", False):
        cmd.append("--force")
    if stage == "quality" and args.gate_percentile is not None:
        cmd.extend(["--gate-percentile", str(args.gate_percentile)])
    print(f"\n=== pipeline stage: {stage} ===", flush=True)
    completed = subprocess.run(cmd, cwd=str(ROOT))
    return int(completed.returncode)


def _screen_survivor_ids(conn, date_from: str, date_until: str) -> list[int]:
    from paper_intelligence.db.results import latest_screen_scores

    return sorted(
        {
            int(row["content_item_id"])
            for row in latest_screen_scores(conn, date_from=date_from, date_until=date_until)
            if ((row["result_json"] or {}).get("gate") or {}).get("passed")
        }
    )


def _quality_ids(conn, date_from: str, date_until: str) -> list[int]:
    from paper_intelligence.common.config import PI_USE_PAPERS_CATALOG

    if PI_USE_PAPERS_CATALOG:
        sql = """
            SELECT DISTINCT q.content_item_id
            FROM paper_intelligence.paper_classification_results q
            JOIN paper_intelligence.papers p ON p.paper_id = q.content_item_id
            WHERE q.task_type = 'quality'
              AND p.published_at >= %s::timestamptz
              AND p.published_at < (%s::timestamptz + interval '1 day')
            ORDER BY q.content_item_id
            """
    else:
        sql = """
            SELECT DISTINCT q.content_item_id
            FROM paper_intelligence.paper_classification_results q
            JOIN research_radar.content_items ci ON ci.id = q.content_item_id
            WHERE q.task_type = 'quality'
              AND ci.published_at >= %s::timestamptz
              AND ci.published_at < (%s::timestamptz + interval '1 day')
            ORDER BY q.content_item_id
            """
    with conn.cursor() as cur:
        cur.execute(sql, (date_from, date_until))
        return [int(r["content_item_id"]) for r in cur.fetchall()]


def _run_affiliation(args: argparse.Namespace, *, mode: str) -> int:
    """Run affiliation_fast (pre-quality) or affiliation_deep (post-quality)."""
    if args.dry_run:
        print(f"affiliation_{mode} dry-run: skip live lookups", flush=True)
        return 0

    from paper_intelligence.author_affiliation import run_window
    from paper_intelligence.db import connect

    label = f"affiliation_{mode}"
    print(f"\n=== pipeline stage: {label} ===", flush=True)
    with connect() as conn:
        if mode == "fast":
            ids = _screen_survivor_ids(conn, args.date_from, args.date_until)
        else:
            ids = _quality_ids(conn, args.date_from, args.date_until)
        if args.limit:
            ids = ids[: args.limit]

    print(f"{label} candidates={len(ids)}", flush=True)
    if not ids:
        print(f"{label}: nothing to do", flush=True)
        return 0

    summary = run_window(
        args.date_from,
        args.date_until,
        content_item_ids=ids,
        allow_ror=(mode == "deep"),
        allow_openalex=(mode == "deep"),
        mode=mode,
        dry_run=False,
    )
    print(
        f"{label}: items={summary.get('items')} "
        f"by_outcome={summary.get('by_outcome')} "
        f"rows_written={summary.get('rows_written')}",
        flush=True,
    )
    return 0


def _run_reports(args: argparse.Namespace) -> int:
    from paper_intelligence.db import connect

    # Import sibling script as a module.
    import importlib.util

    spec = importlib.util.spec_from_file_location(
        "generate_audience_tops", SCRIPTS / "generate_audience_tops.py"
    )
    assert spec and spec.loader
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)

    print("\n=== pipeline stage: reports ===", flush=True)
    with connect() as conn:
        paths = mod.write_all_reports(
            conn,
            date_from=args.date_from,
            date_until=args.date_until,
            top_n=args.top,
            reports_dir=ROOT / "reports",
        )
    for kind, path in paths.items():
        print(f"  {kind}: {path}", flush=True)

    # Keep the operational funnel report too.
    funnel = subprocess.run(
        [
            sys.executable,
            str(SCRIPTS / "generate_report.py"),
            "--from",
            args.date_from,
            "--until",
            args.date_until,
            "--top",
            str(args.top),
        ],
        cwd=str(ROOT),
    )
    return 0 if funnel.returncode == 0 else funnel.returncode


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Run PaperIntelligence stages and write tech/business top-N reports"
    )
    parser.add_argument("--from", dest="date_from", required=True)
    parser.add_argument("--until", dest="date_until", required=True)
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--allow-paid", action="store_true")
    parser.add_argument("--limit", type=int, default=None)
    parser.add_argument("--reprocess", action="store_true")
    parser.add_argument(
        "--force",
        action="store_true",
        help="ingest: re-harvest windows already COMPLETE in backfill_checkpoints",
    )
    parser.add_argument("--gate-percentile", type=float, default=None)
    parser.add_argument("--top", type=int, default=20, help="top-N for audience reports")
    parser.add_argument(
        "--stages",
        default=",".join(DEFAULT_STAGES),
        help=f"comma-separated stages (default: {','.join(DEFAULT_STAGES)})",
    )
    parser.add_argument(
        "--from-stage",
        default=None,
        help="start at this stage (inclusive), skipping earlier ones",
    )
    args = parser.parse_args(argv)

    stages = [STAGE_ALIASES.get(s.strip(), s.strip()) for s in args.stages.split(",") if s.strip()]
    unknown = [s for s in stages if s not in DEFAULT_STAGES]
    if unknown:
        print(f"unknown stages: {unknown}", file=sys.stderr)
        return 2

    if args.from_stage:
        from_stage = STAGE_ALIASES.get(args.from_stage, args.from_stage)
        if from_stage not in stages:
            print(f"--from-stage {args.from_stage} not in --stages", file=sys.stderr)
            return 2
        stages = stages[stages.index(from_stage) :]

    paid = [s for s in stages if s in {"screen", "audience_domain", "quality"}]
    if paid and not args.dry_run and not args.allow_paid:
        print(
            "Paid stages require --allow-paid (or pass --dry-run for projections). "
            f"Paid in this run: {', '.join(paid)}",
            file=sys.stderr,
        )
        return 2

    failures: list[str] = []
    for stage in stages:
        if stage == "affiliation_fast":
            code = _run_affiliation(args, mode="fast")
        elif stage == "affiliation_deep":
            code = _run_affiliation(args, mode="deep")
        elif stage == "reports":
            code = _run_reports(args)
        else:
            code = _run_stage_cli(args, stage)
        if code != 0:
            failures.append(f"{stage}={code}")
            # Continue so later free stages (adjudication/reports) still run when
            # a paid stage is only partial; hard-stop only if reports themselves fail.
            if stage == "reports":
                return code
            print(f"WARNING: stage {stage} exited {code}; continuing", flush=True)

    print("\n=== pipeline complete ===", flush=True)
    if failures:
        print(f"partial failures: {', '.join(failures)}", flush=True)
        return 1
    print(
        f"reports: reports/tech_top_{args.top}_{args.date_from}_to_{args.date_until}.md , "
        f"reports/business_top_{args.top}_{args.date_from}_to_{args.date_until}.md",
        flush=True,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
