#!/usr/bin/env python3
"""Validate organisation extraction coverage vs OpenAlex (evaluation only).

Does not change scoring, affiliation confidence, quality routing, or adjudication.

Example:
  PYTHONPATH=src python3 scripts/validate_org_coverage.py \\
    --date-until 2026-09-15 \\
    --windows 7,15,31
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from dataclasses import asdict
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from paper_intelligence.db import connect
from paper_intelligence.evaluation.org_coverage import (
    DEFAULT_WINDOWS,
    STAGE_NAME,
    STAGE_VERSION,
    compute_window_metrics,
    disagreement_rows_for_csv,
    fetch_openalex_for_papers,
    flatten_coverage_row,
    load_affiliations,
    load_papers,
    observe_disagreement_causes,
    render_summary_markdown,
    window_start,
    write_csv,
)
from paper_intelligence.observability import (
    code_commit_sha,
    finish_pipeline_run,
    finish_stage_run,
    start_pipeline_run,
    start_stage_run,
)


def _parse_windows(raw: str) -> list[int]:
    parts = [p.strip() for p in (raw or "").split(",") if p.strip()]
    if not parts:
        return list(DEFAULT_WINDOWS)
    out = sorted({int(p) for p in parts})
    if any(d < 1 for d in out):
        raise argparse.ArgumentTypeError("windows must be positive integers")
    return out


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Organisation coverage vs OpenAlex validation")
    parser.add_argument("--date-until", required=True, help="Inclusive end date YYYY-MM-DD")
    parser.add_argument(
        "--windows",
        default="7,15,31",
        help="Comma-separated inclusive window lengths in days (default: 7,15,31)",
    )
    parser.add_argument(
        "--output-dir",
        default=str(ROOT / "reports" / "org_validation"),
        help="Directory for CSV/JSON/MD outputs",
    )
    parser.add_argument("--limit", type=int, default=None, help="Optional cap on papers loaded")
    parser.add_argument(
        "--refresh-openalex",
        action="store_true",
        help="Ignore existing OpenAlex raw-cache entries and refetch",
    )
    parser.add_argument(
        "--log-external-requests",
        action="store_true",
        help="Write each OpenAlex call to external_requests (slow on large windows)",
    )
    parser.add_argument(
        "--workers",
        type=int,
        default=8,
        help="Parallel OpenAlex fetch workers (validation only; default 8)",
    )
    args = parser.parse_args(argv)

    date_until = date.fromisoformat(args.date_until[:10])
    windows = _parse_windows(args.windows)
    max_days = max(windows)
    date_from = window_start(date_until, max_days)
    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    wall_start = time.perf_counter()
    commit = code_commit_sha()

    print(
        f"org_coverage_validation: date_from={date_from} date_until={date_until} "
        f"windows={windows} limit={args.limit} refresh={args.refresh_openalex}",
        flush=True,
    )

    with connect() as conn:
        run_id = start_pipeline_run(
            conn,
            pipeline_name="paper_intelligence.org_coverage_validation",
            trigger_type="manual",
            metadata={
                "date_until": date_until.isoformat(),
                "windows": windows,
                "limit": args.limit,
                "refresh_openalex": bool(args.refresh_openalex),
                "code_commit_sha": commit,
            },
        )
        stage_run_id = start_stage_run(
            conn,
            run_id,
            stage_name=STAGE_NAME,
            stage_version=STAGE_VERSION,
        )
        try:
            papers = load_papers(conn, date_from, date_until, limit=args.limit)
            print(f"loaded papers={len(papers)} for {max_days}d population", flush=True)
            ids = [p.content_item_id for p in papers]
            affiliations = load_affiliations(conn, ids)
            print(
                f"loaded affiliation rows for {sum(1 for i in ids if i in affiliations)} papers",
                flush=True,
            )

            openalex_by_paper, fetch_stats = fetch_openalex_for_papers(
                conn,
                papers,
                refresh=bool(args.refresh_openalex),
                run_id=run_id,
                stage_run_id=stage_run_id,
                log_external_requests=bool(args.log_external_requests),
                workers=int(args.workers),
            )
            print(
                f"OpenAlex done: matched={fetch_stats.matched} unmatched={fetch_stats.unmatched} "
                f"requests={fetch_stats.requests} cache_hits={fetch_stats.cache_hits} "
                f"cache_misses={fetch_stats.cache_misses} runtime_s={fetch_stats.runtime_seconds}",
                flush=True,
            )

            window_metrics: list[dict] = []
            for days in windows:
                metrics = compute_window_metrics(
                    papers,
                    affiliations,
                    openalex_by_paper,
                    days=days,
                    date_until=date_until,
                )
                window_metrics.append(metrics)
                coverage_path = output_dir / f"org_coverage_{days}d.csv"
                write_csv(coverage_path, [flatten_coverage_row(metrics)])
                disagree_path = output_dir / f"org_disagreements_{days}d.csv"
                write_csv(disagree_path, disagreement_rows_for_csv(metrics))
                print(
                    f"{days}d: papers={metrics['internal']['total_arxiv_papers']} "
                    f"ours_cov={metrics['ours_org_coverage']} "
                    f"oa_match={metrics['openalex']['match_rate']} "
                    f"oa_cov={metrics['openalex']['org_coverage']} "
                    f"overlap={metrics['openalex_agreement']['at_least_one_org_overlap_count']}",
                    flush=True,
                )

            wall_s = round(time.perf_counter() - wall_start, 3)
            fetch_stats.runtime_seconds = fetch_stats.runtime_seconds or wall_s
            causes = observe_disagreement_causes(window_metrics)
            summary = {
                "stage_name": STAGE_NAME,
                "stage_version": STAGE_VERSION,
                "code_commit_sha": commit,
                "date_from": date_from.isoformat(),
                "date_until": date_until.isoformat(),
                "windows": windows,
                "limit": args.limit,
                "refresh_openalex": bool(args.refresh_openalex),
                "fetch_stats": asdict(fetch_stats),
                "wall_runtime_seconds": wall_s,
                "windows_metrics": window_metrics,
                "observed_disagreement_causes": causes,
            }
            # Drop bulky samples from JSON? Keep them — useful for review.
            json_path = output_dir / "org_validation_summary.json"
            json_path.write_text(json.dumps(summary, indent=2, default=str) + "\n", encoding="utf-8")
            md = render_summary_markdown(
                date_until=date_until,
                windows=window_metrics,
                fetch_stats=fetch_stats,
                commit_sha=commit,
            )
            md += "## Observed disagreement causes (from counts + samples)\n\n"
            for cause in causes:
                md += f"- {cause}\n"
            md_path = output_dir / "org_validation_summary.md"
            md_path.write_text(md, encoding="utf-8")

            finish_stage_run(
                conn,
                stage_run_id,
                status="succeeded",
                items_success=fetch_stats.matched,
                items_failed=fetch_stats.errors,
                items_cached=fetch_stats.cache_hits,
            )
            finish_pipeline_run(
                conn,
                run_id,
                status="succeeded",
                items_input=len(papers),
                items_succeeded=fetch_stats.matched,
                items_failed=fetch_stats.errors,
                items_skipped=fetch_stats.unmatched,
                metadata={
                    "unmatched": fetch_stats.unmatched,
                    "cache_hits": fetch_stats.cache_hits,
                    "cache_misses": fetch_stats.cache_misses,
                },
            )
            conn.commit()
        except Exception as exc:
            finish_stage_run(
                conn, stage_run_id, status="failed", error_summary=str(exc)[:500]
            )
            finish_pipeline_run(conn, run_id, status="failed")
            conn.commit()
            raise

    print(f"wrote outputs under {output_dir}", flush=True)
    print(f"wall_runtime_seconds={round(time.perf_counter() - wall_start, 3)}", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
