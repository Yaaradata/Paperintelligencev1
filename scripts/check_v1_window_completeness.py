#!/usr/bin/env python3
"""Compare catalog papers in a v1 window with a live OAI arXivRaw v1 count.

The reference count comes from the same OAI source ingest uses, so it is not
independent of the ingest source: it catches ingest gaps, not OAI gaps.
Writes reports/ingest_status/v1_completeness_<from>_<until>.json.

--split FROM:UNTIL,... checks each sub-window from the one harvest of
--from..--until (one OAI pass, not one per sub-window) and writes one JSON per
sub-window.
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import date, datetime, timezone
from pathlib import Path

from paper_intelligence.db import connect
from paper_intelligence.ingest.arxiv_oai import count_v1_window

REFERENCE = "OAI-PMH arXivRaw (same source as ingest; not independent)"


def parse_split(value: str) -> list[tuple[date, date]]:
    out = []
    for part in value.split(","):
        start, end = part.split(":")
        out.append((date.fromisoformat(start), date.fromisoformat(end)))
    return out


def db_ids(date_from: date, date_until: date) -> set[str]:
    with connect() as conn, conn.cursor() as cur:
        cur.execute(
            """
            SELECT arxiv_id FROM paper_intelligence.papers
            WHERE published_at >= %s::timestamptz
              AND published_at < (%s::timestamptz + interval '1 day')
            """,
            (date_from, date_until),
        )
        return {r["arxiv_id"] for r in cur.fetchall()}


def compare(oai_ids: set[str], in_db: set[str], date_from: date, date_until: date, extra: dict) -> dict:
    missing = sorted(oai_ids - in_db)
    surplus = sorted(in_db - oai_ids)
    return {
        **extra,
        "date_from": str(date_from),
        "date_until": str(date_until),
        "checked_at": datetime.now(timezone.utc).isoformat(),
        "reference_source": REFERENCE,
        "oai_v1_count": len(oai_ids),
        "db_count": len(in_db),
        "missing_from_db": len(missing),
        "in_db_not_in_oai": len(surplus),
        "missing_sample": missing[:50],
        "extra_sample": surplus[:50],
        "complete": not missing,
    }


def write(result: dict) -> None:
    out = Path("reports/ingest_status") / f"v1_completeness_{result['date_from']}_{result['date_until']}.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(result, indent=2))
    print(json.dumps({k: v for k, v in result.items() if not k.endswith("_sample")}, indent=2))


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--from", dest="date_from", required=True, type=date.fromisoformat)
    ap.add_argument("--until", dest="date_until", required=True, type=date.fromisoformat)
    ap.add_argument("--split", type=parse_split, help="FROM:UNTIL,... sub-windows inside --from..--until")
    args = ap.parse_args()

    counts = count_v1_window(args.date_from, args.date_until)
    v1_by_id: dict[str, str] = counts.pop("v1_by_id")
    counts.pop("arxiv_ids")
    windows = args.split or [(args.date_from, args.date_until)]
    for start, end in windows:
        if start < args.date_from or end > args.date_until:
            print(f"sub-window {start}..{end} is outside {args.date_from}..{args.date_until}", file=sys.stderr)
            return 1
    results = []
    for start, end in windows:
        oai_ids = {a for a, d in v1_by_id.items() if start.isoformat() <= d <= end.isoformat()}
        extra = {"harvest": counts} if args.split else {k: v for k, v in counts.items() if k not in {"date_from", "date_until"}}
        result = compare(oai_ids, db_ids(start, end), start, end, extra)
        write(result)
        results.append(result)
    return 0 if all(r["complete"] for r in results) else 2


if __name__ == "__main__":
    sys.exit(main())
