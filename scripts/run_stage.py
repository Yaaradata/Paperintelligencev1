#!/usr/bin/env python3
"""Run a single PaperIntelligence stage.

Paid stages require --from/--until and --allow-paid. normalize_authors is free.
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


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Run one pipeline stage")
    parser.add_argument("--stage", required=True)
    parser.add_argument("--from", dest="date_from", default=None)
    parser.add_argument("--until", dest="date_until", default=None)
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--allow-paid", action="store_true")
    parser.add_argument("--limit", type=int, default=None)
    parser.add_argument("--content-item-id", type=int, default=None)
    args = parser.parse_args(argv)

    if args.stage == "normalize_authors":
        return _run_normalize(args)

    print(
        f"run_stage.py: stage={args.stage} not implemented yet "
        f"(from={args.date_from} until={args.date_until} dry_run={args.dry_run})",
        file=sys.stderr,
    )
    return 2


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
        with connect() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT id FROM research_radar.content_items
                    WHERE published_at >= %s::timestamptz
                      AND published_at < (%s::timestamptz + interval '1 day')
                    ORDER BY id
                    LIMIT %s
                    """,
                    (args.date_from, args.date_until, args.limit or 100),
                )
                ids = [int(r["id"]) for r in cur.fetchall()]

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
