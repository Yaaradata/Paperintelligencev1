#!/usr/bin/env python3
"""Compare catalog papers in a v1 window with a live OAI arXivRaw v1 count.

The reference count comes from the same OAI source ingest uses, so it is not
independent of the ingest source: it catches ingest gaps, not OAI gaps.
Writes reports/ingest_status/v1_completeness_<from>_<until>.json.
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import date, datetime, timezone
from pathlib import Path

from paper_intelligence.db import connect
from paper_intelligence.ingest.arxiv_oai import count_v1_window


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--from", dest="date_from", required=True, type=date.fromisoformat)
    ap.add_argument("--until", dest="date_until", required=True, type=date.fromisoformat)
    args = ap.parse_args()

    counts = count_v1_window(args.date_from, args.date_until)
    oai_ids = set(counts.pop("arxiv_ids"))
    with connect() as conn, conn.cursor() as cur:
        cur.execute(
            """
            SELECT arxiv_id FROM paper_intelligence.papers
            WHERE published_at >= %s::timestamptz
              AND published_at < (%s::timestamptz + interval '1 day')
            """,
            (args.date_from, args.date_until),
        )
        db_ids = {r["arxiv_id"] for r in cur.fetchall()}
    missing = sorted(oai_ids - db_ids)
    extra = sorted(db_ids - oai_ids)
    result = {
        **counts,
        "checked_at": datetime.now(timezone.utc).isoformat(),
        "reference_source": "OAI-PMH arXivRaw (same source as ingest; not independent)",
        "oai_v1_count": len(oai_ids),
        "db_count": len(db_ids),
        "missing_from_db": len(missing),
        "in_db_not_in_oai": len(extra),
        "missing_sample": missing[:50],
        "extra_sample": extra[:50],
        "complete": not missing,
    }
    out = Path("reports/ingest_status") / f"v1_completeness_{args.date_from}_{args.date_until}.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(result, indent=2))
    print(json.dumps({k: v for k, v in result.items() if not k.endswith("_sample")}, indent=2))
    return 0 if result["complete"] else 2


if __name__ == "__main__":
    sys.exit(main())
