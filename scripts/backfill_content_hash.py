#!/usr/bin/env python3
"""Backfill paper_intelligence.papers.content_hash (no LLM).

Idempotent: only updates rows where content_hash IS NULL or --force.
Does **not** touch modified_at (content_hash is independent of ingest timing).
Uses keyset batching (paper_id > last_id LIMIT N) — never loads the whole table.

  PYTHONPATH=src python3 scripts/backfill_content_hash.py
  PYTHONPATH=src python3 scripts/backfill_content_hash.py --force --batch-size 500
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--force", action="store_true", help="recompute even when set")
    parser.add_argument(
        "--limit",
        type=int,
        default=None,
        help="stop after updating this many rows (optional)",
    )
    parser.add_argument(
        "--batch-size",
        type=int,
        default=1000,
        help="keyset page size (default 1000)",
    )
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args(argv)

    from paper_intelligence.common.content_hash import compute_content_hash
    from paper_intelligence.db import connect

    updated = 0
    scanned = 0
    last_id = 0
    batch_size = max(1, int(args.batch_size))

    with connect() as conn:
        while True:
            if args.limit is not None and updated >= args.limit:
                break
            with conn.cursor() as cur:
                where = ["paper_id > %s"]
                params: list = [last_id]
                if not args.force:
                    where.append("content_hash IS NULL")
                sql = f"""
                    SELECT paper_id, title, abstract, content_hash
                    FROM paper_intelligence.papers
                    WHERE {" AND ".join(where)}
                    ORDER BY paper_id
                    LIMIT %s
                """
                params.append(batch_size)
                cur.execute(sql, params)
                rows = list(cur.fetchall())
            if not rows:
                break

            for row in rows:
                last_id = int(row["paper_id"])
                scanned += 1
                if args.limit is not None and updated >= args.limit:
                    break
                new_hash = compute_content_hash(row.get("title"), row.get("abstract"))
                old = row.get("content_hash")
                if old == new_hash:
                    continue
                if args.dry_run:
                    updated += 1
                    continue
                with conn.cursor() as cur:
                    cur.execute(
                        """
                        UPDATE paper_intelligence.papers
                        SET content_hash = %s
                        WHERE paper_id = %s
                        """,
                        (new_hash, last_id),
                    )
                updated += 1
                if updated % 1000 == 0:
                    conn.commit()
                    print(
                        f"  … {updated} updated / {scanned} scanned "
                        f"(last_id={last_id})",
                        flush=True,
                    )
            if not args.dry_run:
                conn.commit()
            if len(rows) < batch_size:
                break

    mode = "dry-run would update" if args.dry_run else "updated"
    print(f"content_hash backfill: scanned={scanned} {mode}={updated}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
