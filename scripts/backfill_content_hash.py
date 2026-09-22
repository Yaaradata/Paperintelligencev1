#!/usr/bin/env python3
"""Backfill paper_intelligence.papers.content_hash (no LLM).

Idempotent: only updates rows where content_hash IS NULL or --force.

  PYTHONPATH=src python3 scripts/backfill_content_hash.py
  PYTHONPATH=src python3 scripts/backfill_content_hash.py --force --limit 1000
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
    parser.add_argument("--limit", type=int, default=None)
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args(argv)

    from paper_intelligence.common.content_hash import compute_content_hash
    from paper_intelligence.db import connect

    updated = 0
    scanned = 0
    with connect() as conn:
        with conn.cursor() as cur:
            sql = """
                SELECT paper_id, title, abstract, content_hash
                FROM paper_intelligence.papers
            """
            if not args.force:
                sql += " WHERE content_hash IS NULL"
            sql += " ORDER BY paper_id"
            if args.limit:
                sql += f" LIMIT {int(args.limit)}"
            cur.execute(sql)
            rows = list(cur.fetchall())

        for row in rows:
            scanned += 1
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
                    SET content_hash = %s, modified_at = NOW()
                    WHERE paper_id = %s
                    """,
                    (new_hash, int(row["paper_id"])),
                )
            updated += 1
            if updated % 1000 == 0:
                conn.commit()
                print(f"  … {updated} updated / {scanned} scanned", flush=True)
        if not args.dry_run:
            conn.commit()

    mode = "dry-run would update" if args.dry_run else "updated"
    print(f"content_hash backfill: scanned={scanned} {mode}={updated}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
