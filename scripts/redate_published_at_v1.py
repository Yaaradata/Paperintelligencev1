#!/usr/bin/env python3
"""Re-date ``published_at`` to the arXiv v1 submission date.

Phases (run in order; each is idempotent):

  snapshot  Write reports/review_fixes/published_at_snapshot.csv (papers) and
            published_at_snapshot_content_items.csv (legacy Radar rows).
            Refuses to overwrite an existing snapshot.
  harvest   OAI arXivRaw ListRecords for cs + stat over datestamps
            --since .. today, then GetRecord for catalog papers with
            published_at >= --lookup-since that the harvest did not cover.
            Writes a v1 cache JSON and a status file every page.
  report    Compare current published_at with v1; write changed rows, window
            moves and the Sep 1-21 mover list. No DB writes.
  apply     UPDATE papers.published_at (and linked content_items) to v1 in
            one transaction. Requires the snapshot to exist.
"""

from __future__ import annotations

import argparse
import csv
import json
import sys
import time
from datetime import date, datetime, timezone
from pathlib import Path

from paper_intelligence.db import connect
from paper_intelligence.ingest import arxiv_oai

OUT_DIR = Path("reports/review_fixes")
SNAPSHOT = OUT_DIR / "published_at_snapshot.csv"
SNAPSHOT_CI = OUT_DIR / "published_at_snapshot_content_items.csv"
CACHE = OUT_DIR / "v1_dates_cache.json"
STATUS = OUT_DIR / "redate_status.json"
REPORT = OUT_DIR / "published_at_redate_report.json"
CHANGES = OUT_DIR / "published_at_redate_changes.csv"
SEP_MOVERS = OUT_DIR / "published_at_sep01_21_movers.csv"

WINDOWS = {
    "2026-08-23": (date(2026, 8, 23), date(2026, 8, 23)),
    "2026-08-25..31": (date(2026, 8, 25), date(2026, 8, 31)),
    "2026-09-01..21": (date(2026, 9, 1), date(2026, 9, 21)),
    "2026-09-21..23": (date(2026, 9, 21), date(2026, 9, 23)),
}
SEP_EDITION = "2026-09-01..21"


def _write_status(**fields) -> None:
    fields["updated_at"] = datetime.now(timezone.utc).isoformat()
    STATUS.write_text(json.dumps(fields, indent=2, default=str))


def _load_cache() -> dict:
    if CACHE.exists():
        return json.loads(CACHE.read_text())
    return {"harvested_sets": [], "v1": {}, "lookup_missing": []}


def _save_cache(cache: dict) -> None:
    tmp = CACHE.with_suffix(".tmp")
    tmp.write_text(json.dumps(cache))
    tmp.replace(CACHE)


def cmd_snapshot(_args) -> int:
    if SNAPSHOT.exists() or SNAPSHOT_CI.exists():
        print(f"snapshot already exists ({SNAPSHOT}); not overwriting")
        return 0
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    with connect() as conn, conn.cursor() as cur:
        cur.execute(
            """
            SELECT paper_id, arxiv_id, published_at, source_updated_at
            FROM paper_intelligence.papers ORDER BY paper_id
            """
        )
        rows = cur.fetchall()
        with SNAPSHOT.open("w", newline="") as fh:
            w = csv.writer(fh)
            w.writerow(["paper_id", "arxiv_id", "published_at", "source_updated_at"])
            for r in rows:
                w.writerow(
                    [r["paper_id"], r["arxiv_id"], r["published_at"], r["source_updated_at"]]
                )
        cur.execute(
            """
            SELECT ci.id, pm.arxiv_id, ci.published_at, ci.updated_at
            FROM research_radar.content_items ci
            JOIN research_radar.paper_metadata pm ON pm.content_id = ci.id
            WHERE pm.arxiv_id IS NOT NULL ORDER BY ci.id
            """
        )
        ci_rows = cur.fetchall()
        with SNAPSHOT_CI.open("w", newline="") as fh:
            w = csv.writer(fh)
            w.writerow(["content_item_id", "arxiv_id", "published_at", "updated_at"])
            for r in ci_rows:
                w.writerow([r["id"], r["arxiv_id"], r["published_at"], r["updated_at"]])
    print(f"snapshot: {len(rows)} papers -> {SNAPSHOT}")
    print(f"snapshot: {len(ci_rows)} content_items -> {SNAPSHOT_CI}")
    return 0


def cmd_harvest(args) -> int:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    cache = _load_cache()
    since = date.fromisoformat(args.since)
    today = datetime.now(timezone.utc).date()
    started = time.monotonic()
    for set_spec in arxiv_oai.OAI_SETS:
        if set_spec in cache["harvested_sets"]:
            continue
        params = {
            "verb": "ListRecords",
            "set": set_spec,
            "metadataPrefix": "arXivRaw",
            "from": since.isoformat(),
            "until": today.isoformat(),
        }
        seen = 0
        for record_elem in arxiv_oai._iter_list_records(params):
            rec = arxiv_oai.parse_raw_record(record_elem)
            seen += 1
            if not rec["deleted"] and rec.get("arxiv_id") and rec["v1_date"]:
                cache["v1"][rec["arxiv_id"]] = rec["v1_date"].isoformat()
            if seen % 1300 == 0:
                _write_status(
                    phase="harvest", set=set_spec, records_seen=seen,
                    v1_known=len(cache["v1"]), requests=arxiv_oai._request_count,
                    elapsed_s=int(time.monotonic() - started),
                )
        cache["harvested_sets"].append(set_spec)
        _save_cache(cache)
        print(f"harvest set={set_spec} records={seen} v1_known={len(cache['v1'])}")

    with connect() as conn, conn.cursor() as cur:
        cur.execute(
            """
            SELECT arxiv_id FROM paper_intelligence.papers
            WHERE arxiv_id IS NOT NULL AND published_at >= %s::timestamptz
            """,
            (args.lookup_since,),
        )
        need = sorted({r["arxiv_id"] for r in cur.fetchall()} - set(cache["v1"]))
    need = [a for a in need if a not in set(cache["lookup_missing"])]
    print(f"GetRecord lookups needed: {len(need)}")
    for i, arxiv_id in enumerate(need, 1):
        v1 = arxiv_oai.get_v1_date(arxiv_id)
        if v1 is None:
            cache["lookup_missing"].append(arxiv_id)
        else:
            cache["v1"][arxiv_id] = v1.isoformat()
        if i % 100 == 0 or i == len(need):
            _save_cache(cache)
            _write_status(
                phase="getrecord", done=i, total=len(need),
                missing=len(cache["lookup_missing"]),
                elapsed_s=int(time.monotonic() - started),
            )
    _save_cache(cache)
    _write_status(phase="done", v1_known=len(cache["v1"]),
                  missing=len(cache["lookup_missing"]))
    print(f"done v1_known={len(cache['v1'])} missing={len(cache['lookup_missing'])}")
    return 0


def _window_of(d: date | None) -> set[str]:
    if d is None:
        return set()
    return {name for name, (lo, hi) in WINDOWS.items() if lo <= d <= hi}


def _utc_date(dt: datetime | None) -> date | None:
    return dt.astimezone(timezone.utc).date() if dt else None


def _compute(conn, cache: dict) -> list[dict]:
    v1 = cache["v1"]
    with conn.cursor() as cur:
        cur.execute(
            """
            SELECT paper_id, arxiv_id, title, published_at, source_updated_at
            FROM paper_intelligence.papers WHERE arxiv_id IS NOT NULL
            """
        )
        rows = cur.fetchall()
    changes = []
    for r in rows:
        v1_iso = v1.get(r["arxiv_id"])
        if v1_iso is None:
            continue
        new = datetime.fromisoformat(v1_iso)
        old = r["published_at"]
        if old is not None and old == new:
            continue
        changes.append({**r, "v1_date": new})
    return changes


def cmd_report(_args) -> int:
    cache = _load_cache()
    with connect() as conn:
        changes = _compute(conn, cache)
        with conn.cursor() as cur:
            cur.execute(
                "SELECT count(*) AS n, count(*) FILTER (WHERE arxiv_id IS NOT NULL) AS a "
                "FROM paper_intelligence.papers"
            )
            totals = cur.fetchone()
            cur.execute(
                "SELECT arxiv_id, published_at FROM paper_intelligence.papers "
                "WHERE arxiv_id IS NOT NULL"
            )
            all_rows = cur.fetchall()
    uncovered = [r for r in all_rows if r["arxiv_id"] not in cache["v1"]]
    date_changed = [c for c in changes if _utc_date(c["published_at"]) != _utc_date(c["v1_date"])]
    month_changed = [
        c for c in changes
        if (_utc_date(c["published_at"]) or date.min).replace(day=1)
        != _utc_date(c["v1_date"]).replace(day=1)
    ]
    per_window = {}
    for name in WINDOWS:
        out_of = [c for c in changes
                  if name in _window_of(_utc_date(c["published_at"]))
                  and name not in _window_of(_utc_date(c["v1_date"]))]
        into = [c for c in changes
                if name not in _window_of(_utc_date(c["published_at"]))
                and name in _window_of(_utc_date(c["v1_date"]))]
        per_window[name] = {"moved_out": len(out_of), "moved_in": len(into)}
    moved_any_window = [
        c for c in changes
        if _window_of(_utc_date(c["published_at"])) != _window_of(_utc_date(c["v1_date"]))
    ]
    floor = date(2026, 7, 1)
    to_pre_floor = [c for c in changes
                    if _utc_date(c["v1_date"]) < floor
                    and (_utc_date(c["published_at"]) or date.min) >= floor]

    with CHANGES.open("w", newline="") as fh:
        w = csv.writer(fh)
        w.writerow(["paper_id", "arxiv_id", "old_published_at", "v1_date"])
        for c in changes:
            w.writerow([c["paper_id"], c["arxiv_id"], c["published_at"], c["v1_date"]])
    lo, hi = WINDOWS[SEP_EDITION]
    sep_out = [c for c in changes
               if SEP_EDITION in _window_of(_utc_date(c["published_at"]))
               and SEP_EDITION not in _window_of(_utc_date(c["v1_date"]))]
    sep_in = [c for c in changes
              if SEP_EDITION not in _window_of(_utc_date(c["published_at"]))
              and SEP_EDITION in _window_of(_utc_date(c["v1_date"]))]
    with SEP_MOVERS.open("w", newline="") as fh:
        w = csv.writer(fh)
        w.writerow(["direction", "paper_id", "arxiv_id", "old_published_at", "v1_date", "title"])
        for direction, group in (("out", sep_out), ("in", sep_in)):
            for c in sorted(group, key=lambda c: c["arxiv_id"]):
                w.writerow([direction, c["paper_id"], c["arxiv_id"],
                            c["published_at"], c["v1_date"], (c["title"] or "")[:200]])

    report = {
        "papers_total": totals["n"],
        "papers_with_arxiv_id": totals["a"],
        "v1_known": sum(1 for r in all_rows if r["arxiv_id"] in cache["v1"]),
        "v1_unknown": len(uncovered),
        "v1_unknown_by_month": _by_month(uncovered),
        "rows_changed_timestamp": len(changes),
        "rows_changed_date": len(date_changed),
        "rows_changed_month": len(month_changed),
        "rows_moved_between_windows": len(moved_any_window),
        "rows_moving_below_2026_07_01_floor": len(to_pre_floor),
        "per_window": per_window,
        "sep01_21_moved_out": len(sep_out),
        "sep01_21_moved_in": len(sep_in),
        "files": {"changes": str(CHANGES), "sep01_21_movers": str(SEP_MOVERS)},
    }
    REPORT.write_text(json.dumps(report, indent=2, default=str))
    print(json.dumps(report, indent=2, default=str))
    return 0


def _by_month(rows) -> dict:
    out: dict[str, int] = {}
    for r in rows:
        d = _utc_date(r["published_at"])
        key = d.strftime("%Y-%m") if d else "none"
        out[key] = out.get(key, 0) + 1
    return dict(sorted(out.items()))


def cmd_apply(_args) -> int:
    if not (SNAPSHOT.exists() and SNAPSHOT_CI.exists()):
        print("snapshot missing; run the snapshot phase first", file=sys.stderr)
        return 2
    cache = _load_cache()
    with connect() as conn:
        changes = _compute(conn, cache)
        with conn.cursor() as cur:
            cur.execute(
                "CREATE TEMP TABLE v1_redate (arxiv_id text PRIMARY KEY, v1 timestamptz) "
                "ON COMMIT DROP"
            )
            with cur.copy("COPY v1_redate (arxiv_id, v1) FROM STDIN") as cp:
                for arxiv_id, iso in cache["v1"].items():
                    cp.write_row((arxiv_id, iso))
            cur.execute(
                """
                UPDATE paper_intelligence.papers p
                SET raw_metadata = p.raw_metadata || jsonb_build_object(
                        'v1_date', v.v1,
                        'published_at_before_v1_redate', p.published_at),
                    published_at = v.v1,
                    modified_at = NOW()
                FROM v1_redate v
                WHERE v.arxiv_id = p.arxiv_id
                  AND p.published_at IS DISTINCT FROM v.v1
                """
            )
            papers_updated = cur.rowcount
            cur.execute(
                """
                UPDATE research_radar.content_items ci
                SET published_at = v.v1, modified_at = NOW()
                FROM research_radar.paper_metadata pm, v1_redate v
                WHERE pm.content_id = ci.id AND v.arxiv_id = pm.arxiv_id
                  AND ci.published_at IS DISTINCT FROM v.v1
                """
            )
            ci_updated = cur.rowcount
        conn.commit()
    print(f"applied: papers={papers_updated} (expected {len(changes)}) content_items={ci_updated}")
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="cmd", required=True)
    sub.add_parser("snapshot")
    h = sub.add_parser("harvest")
    h.add_argument("--since", default="2026-05-25")
    h.add_argument("--lookup-since", default="2026-06-01")
    sub.add_parser("report")
    sub.add_parser("apply")
    args = parser.parse_args(argv)
    return {"snapshot": cmd_snapshot, "harvest": cmd_harvest,
            "report": cmd_report, "apply": cmd_apply}[args.cmd](args)


if __name__ == "__main__":
    sys.exit(main())
