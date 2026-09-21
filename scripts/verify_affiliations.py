#!/usr/bin/env python3
"""Parallel HTML ↔ OpenAlex affiliation verification (compare-only).

Worker-safe via FOR UPDATE SKIP LOCKED. Does not union conflicting org sets.

Examples:
  # Enqueue + verify the Sep both-HTML+OA set (prefer cache)
  PYTHONPATH=src python3 scripts/verify_affiliations.py \\
    --set both-sep --workers 8 --verification-version html-oa-v001

  # Resume
  PYTHONPATH=src python3 scripts/verify_affiliations.py \\
    --resume --workers 8 --verification-version html-oa-v001

  # Targeted candidate dry-run (no work)
  PYTHONPATH=src python3 scripts/verify_affiliations.py \\
    --targeted-dry-run --from 2026-09-01 --until 2026-09-15
"""

from __future__ import annotations

import argparse
import json
import os
import socket
import sys
import threading
import time
import uuid
from collections import Counter
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from paper_intelligence.author_affiliation.verify.claim import (  # noqa: E402
    VERIFICATION_VERSION_DEFAULT,
    claim_batch,
    counts_by_status,
    enqueue_papers,
    mark_complete,
    mark_failed,
    reclaim_stale,
)
from paper_intelligence.author_affiliation.verify.openalex_gate import (  # noqa: E402
    GLOBAL_STATS,
    peek_cache,
    reset_stats,
)
from paper_intelligence.author_affiliation.verify.worker import verify_one_paper  # noqa: E402
from paper_intelligence.db import connect  # noqa: E402
from paper_intelligence.quality.stage import GATE_PERCENTILE  # noqa: E402

DEFAULT_WORKERS = int(os.getenv("AFFILIATION_VERIFY_WORKERS", "8"))


def _worker_id() -> str:
    return f"{socket.gethostname()[:24]}-{os.getpid()}-{uuid.uuid4().hex[:8]}"


def select_both_html_oa_sep(conn: Any, date_from: str, date_until: str) -> list[int]:
    rows = conn.execute(
        """
        WITH win AS (
          SELECT paper_id FROM paper_intelligence.papers
          WHERE published_at >= %s::timestamptz
            AND published_at < (%s::timestamptz + interval '1 day')
        ),
        html_papers AS (
          SELECT DISTINCT a.content_item_id AS paper_id
          FROM paper_intelligence.paper_author_affiliations a
          JOIN win w ON w.paper_id = a.content_item_id
          WHERE a.evidence_source ILIKE '%%arxiv.org/html%%'
             OR a.evidence_source ILIKE '%%arxiv.html%%'
        ),
        oa_papers AS (
          SELECT DISTINCT a.content_item_id AS paper_id
          FROM paper_intelligence.paper_author_affiliations a
          JOIN win w ON w.paper_id = a.content_item_id
          WHERE a.evidence_type = 'openalex_paper_specific'
        )
        SELECT h.paper_id
        FROM html_papers h
        JOIN oa_papers o USING (paper_id)
        ORDER BY h.paper_id
        """,
        (date_from, date_until),
    ).fetchall()
    return [int(r["paper_id"]) for r in rows]


def select_targeted_candidates(
    conn: Any,
    *,
    date_from: str,
    date_until: str,
    audit_sample: int = 50,
    seed: int = 42,
) -> dict[str, Any]:
    """Deduplicated Sep targeted set (dry-run planning only)."""
    from paper_intelligence.db import latest_screen_scores
    from paper_intelligence.quality.stage import RANK_DIMENSIONS

    buckets: dict[str, set[int]] = {
        "quality_selected": set(),
        "notable_ooi": set(),
        "newsletter_pool": set(),
        "linkedin_pool": set(),
        "low_confidence": set(),
        "ambiguous_ror": set(),
        "affiliation_conflict_prior": set(),
        "random_audit": set(),
    }

    # Quality router (single screen scan — avoid 3× latest_screen_scores).
    try:
        ranked: list[tuple[float, int]] = []
        survivors: set[int] = set()
        for row in latest_screen_scores(conn, date_from=date_from, date_until=date_until):
            result = row["result_json"] or {}
            gate = result.get("gate") or {}
            if not gate.get("passed"):
                continue
            cid = int(row["content_item_id"])
            survivors.add(cid)
            try:
                mean = sum(float(result[dim]) for dim in RANK_DIMENSIONS) / len(RANK_DIMENSIONS)
            except (KeyError, TypeError, ValueError):
                continue
            ranked.append((mean, cid))
        ranked.sort(key=lambda pair: (-pair[0], pair[1]))
        keep = max(1, int(round(len(ranked) * (GATE_PERCENTILE / 100.0)))) if ranked else 0
        top_slice = {cid for _, cid in ranked[:keep]}
        ooi_in_survivors: set[int] = set()
        if survivors:
            for r in conn.execute(
                """
                SELECT DISTINCT a.content_item_id
                FROM paper_intelligence.paper_author_affiliations a
                JOIN paper_intelligence.organisations o ON o.id = a.organisation_id
                WHERE a.content_item_id = ANY(%s)
                  AND o.is_org_of_interest IS TRUE
                  AND o.active IS TRUE
                  AND a.organisation_id IS NOT NULL
                """,
                (list(survivors),),
            ).fetchall():
                ooi_in_survivors.add(int(r["content_item_id"]))
        buckets["quality_selected"] = top_slice | ooi_in_survivors
    except Exception:  # noqa: BLE001
        buckets["quality_selected"] = set()

    for r in conn.execute(
        """
        SELECT DISTINCT a.content_item_id
        FROM paper_intelligence.paper_author_affiliations a
        JOIN paper_intelligence.organisations o ON o.id = a.organisation_id
        JOIN paper_intelligence.papers p ON p.paper_id = a.content_item_id
        WHERE p.published_at >= %s::timestamptz
          AND p.published_at < (%s::timestamptz + interval '1 day')
          AND (o.is_org_of_interest IS TRUE OR COALESCE(o.priority, 0) > 0)
        """,
        (date_from, date_until),
    ).fetchall():
        buckets["notable_ooi"].add(int(r["content_item_id"]))

    for r in conn.execute(
        """
        SELECT c.content_item_id
        FROM paper_intelligence.paper_intelligence_current c
        JOIN paper_intelligence.papers p ON p.paper_id = c.content_item_id
        WHERE p.published_at >= %s::timestamptz
          AND p.published_at < (%s::timestamptz + interval '1 day')
          AND (
            c.quality_score IS NOT NULL
            OR COALESCE(c.final_score, 0) >= 7
            OR (c.audiences IS NOT NULL AND c.audiences <> '[]'::jsonb)
          )
        """,
        (date_from, date_until),
    ).fetchall():
        buckets["newsletter_pool"].add(int(r["content_item_id"]))
        buckets["linkedin_pool"].add(int(r["content_item_id"]))

    for r in conn.execute(
        """
        SELECT DISTINCT a.content_item_id
        FROM paper_intelligence.paper_author_affiliations a
        JOIN paper_intelligence.papers p ON p.paper_id = a.content_item_id
        WHERE p.published_at >= %s::timestamptz
          AND p.published_at < (%s::timestamptz + interval '1 day')
          AND a.confidence IS NOT NULL AND a.confidence < 0.6
        """,
        (date_from, date_until),
    ).fetchall():
        buckets["low_confidence"].add(int(r["content_item_id"]))

    for r in conn.execute(
        """
        SELECT DISTINCT a.content_item_id
        FROM paper_intelligence.paper_author_affiliations a
        JOIN paper_intelligence.papers p ON p.paper_id = a.content_item_id
        WHERE p.published_at >= %s::timestamptz
          AND p.published_at < (%s::timestamptz + interval '1 day')
          AND a.evidence_type = 'ror_canonical_match'
        GROUP BY a.content_item_id, a.paper_author_id
        HAVING count(DISTINCT a.organisation_id) > 1
        """,
        (date_from, date_until),
    ).fetchall():
        buckets["ambiguous_ror"].add(int(r["content_item_id"]))

    for r in conn.execute(
        """
        SELECT paper_id FROM paper_intelligence.affiliation_verifications
        WHERE outcome = 'conflict'
        """
    ).fetchall():
        buckets["affiliation_conflict_prior"].add(int(r["paper_id"]))

    for r in conn.execute(
        """
        SELECT paper_id FROM paper_intelligence.papers
        WHERE published_at >= %s::timestamptz
          AND published_at < (%s::timestamptz + interval '1 day')
        ORDER BY md5(paper_id::text || %s::text)
        LIMIT %s
        """,
        (date_from, date_until, str(seed), int(audit_sample)),
    ).fetchall():
        buckets["random_audit"].add(int(r["paper_id"]))

    all_ids: set[int] = set()
    bucket_sizes: dict[str, int] = {}
    for k, v in buckets.items():
        bucket_sizes[k] = len(v)
        all_ids |= v

    ids = sorted(all_ids)
    already: set[int] = set()
    html_avail: set[int] = set()
    oa_pi: set[int] = set()
    if ids:
        already = {
            int(r["paper_id"])
            for r in conn.execute(
                """
                SELECT paper_id FROM paper_intelligence.affiliation_verifications
                WHERE status = 'complete' AND paper_id = ANY(%s)
                """,
                (ids,),
            ).fetchall()
        }
        html_avail = {
            int(r["content_item_id"])
            for r in conn.execute(
                """
                SELECT DISTINCT content_item_id
                FROM paper_intelligence.paper_author_affiliations
                WHERE content_item_id = ANY(%s)
                  AND (evidence_source ILIKE '%%arxiv.org/html%%'
                       OR evidence_source ILIKE '%%arxiv.html%%')
                """,
                (ids,),
            ).fetchall()
        }
        oa_pi = {
            int(r["content_item_id"])
            for r in conn.execute(
                """
                SELECT DISTINCT content_item_id
                FROM paper_intelligence.paper_author_affiliations
                WHERE content_item_id = ANY(%s)
                  AND evidence_type = 'openalex_paper_specific'
                """,
                (ids,),
            ).fetchall()
        }

    remaining_ids = [pid for pid in ids if pid not in already]
    need_lookup_ids = [pid for pid in remaining_ids if pid not in oa_pi]
    oa_cached = 0
    oa_lookup_required = 0
    if need_lookup_ids:
        # Sample cache peeks (full N filesystem peeks are too slow for planning).
        sample_n = min(200, len(need_lookup_ids))
        sample = need_lookup_ids[:: max(1, len(need_lookup_ids) // sample_n)][:sample_n]
        rows = conn.execute(
            """
            SELECT paper_id, doi, arxiv_id
            FROM paper_intelligence.papers
            WHERE paper_id = ANY(%s)
            """,
            (sample,),
        ).fetchall()
        hits = 0
        for row in rows:
            hit, _, _ = peek_cache(row.get("doi"), row.get("arxiv_id"))
            if hit:
                hits += 1
        hit_rate = hits / len(rows) if rows else 0.0
        oa_cached = int(round(hit_rate * len(need_lookup_ids)))
        oa_lookup_required = len(need_lookup_ids) - oa_cached

    pdf_likely = sum(1 for pid in remaining_ids if pid not in html_avail)

    return {
        "bucket_sizes": bucket_sizes,
        "total_candidates": len(ids),
        "paper_ids": ids,
        "already_verified": len(already),
        "html_available": len(html_avail),
        "oa_pi_evidence": len(oa_pi),
        "oa_cached_among_remaining": oa_cached,
        "oa_lookup_required_among_remaining": oa_lookup_required,
        "pdf_likely_required": pdf_likely,
        "remaining_to_verify": len(remaining_ids),
    }



def _process_claim(
    claim: dict[str, Any], *, allow_network: bool, phase: str = "full"
) -> dict[str, Any]:
    from paper_intelligence.db import connect as db_connect

    vid = int(claim["verification_id"])
    pid = int(claim["paper_id"])
    with db_connect() as conn:
        try:
            result = verify_one_paper(
                conn, pid, allow_openalex_network=allow_network, phase=phase
            )
            if not result.get("ok"):
                mark_failed(
                    conn,
                    vid,
                    error=str(result.get("error") or "verify_failed"),
                    result_json=result,
                )
                return {"verification_id": vid, "paper_id": pid, "status": "failed", **result}
            mark_complete(
                conn,
                vid,
                outcome=str(result["outcome"]),
                result_json=result,
            )
            return {"verification_id": vid, "paper_id": pid, "status": "complete", **result}
        except Exception as exc:  # noqa: BLE001
            try:
                mark_failed(conn, vid, error=f"{type(exc).__name__}: {exc}")
            except Exception:  # noqa: BLE001
                pass
            return {
                "verification_id": vid,
                "paper_id": pid,
                "status": "failed",
                "error": f"{type(exc).__name__}: {exc}",
            }


def run_workers(
    *,
    workers: int,
    verification_version: str,
    allow_network: bool,
    max_papers: int | None,
    phase: str = "full",
) -> dict[str, Any]:
    reset_stats()
    reclaim_stale_n = 0
    with connect() as conn:
        reclaim_stale_n = reclaim_stale(conn, verification_version=verification_version)

    worker_id = _worker_id()
    outcomes: Counter[str] = Counter()
    errors = 0
    processed = 0
    timings: list[float] = []
    detailed: list[dict[str, Any]] = []
    t0 = time.perf_counter()
    stop = threading.Event()
    _counter_lock = threading.Lock()

    def pull_and_run() -> None:
        nonlocal processed, errors
        wid = f"{worker_id}-{threading.get_ident()}"
        while not stop.is_set():
            with _counter_lock:
                if max_papers is not None and processed >= max_papers:
                    stop.set()
                    break
            with connect() as conn:
                batch = claim_batch(
                    conn,
                    worker_id=wid,
                    limit=1,
                    verification_version=verification_version,
                )
            if not batch:
                break
            claim = batch[0]
            result = _process_claim(claim, allow_network=allow_network, phase=phase)
            with _counter_lock:
                processed += 1
                if result.get("status") == "failed":
                    errors += 1
                oc = result.get("outcome")
                if oc:
                    outcomes[str(oc)] += 1
                ms = (result.get("timing_ms") or {}).get("total_ms")
                if ms is not None:
                    timings.append(float(ms))
                detailed.append(
                    {
                        "paper_id": result.get("paper_id"),
                        "arxiv_id": result.get("arxiv_id"),
                        "outcome": result.get("outcome"),
                        "status": result.get("status"),
                        "agreement": result.get("agreement"),
                        "openalex": {
                            "source": (result.get("openalex") or {}).get("source"),
                            "cache_hit": (result.get("openalex") or {}).get("cache_hit"),
                            "api_called": (result.get("openalex") or {}).get("api_called"),
                        },
                        "timing_ms": result.get("timing_ms"),
                        "error": result.get("error"),
                    }
                )

    with ThreadPoolExecutor(max_workers=max(1, workers)) as pool:
        futs = [pool.submit(pull_and_run) for _ in range(max(1, workers))]
        for f in as_completed(futs):
            f.result()

    wall = time.perf_counter() - t0
    ppm = (processed / wall * 60.0) if wall > 0 else 0.0
    with connect() as conn:
        status_counts = counts_by_status(conn, verification_version=verification_version)

    return {
        "workers": workers,
        "verification_version": verification_version,
        "reclaimed_stale": reclaim_stale_n,
        "processed": processed,
        "errors": errors,
        "outcomes": dict(outcomes),
        "wall_seconds": round(wall, 3),
        "papers_per_minute": round(ppm, 2),
        "external": GLOBAL_STATS.as_dict(),
        "status_counts": status_counts,
        "timing_ms_avg": round(sum(timings) / len(timings), 2) if timings else None,
        "details": detailed,
    }


def investigate_prior_cases(conn: Any, verification_version: str) -> dict[str, Any]:
    """Fully investigate exact/partial/disjoint from completed verification rows + prior report."""
    rows = [
        dict(r)
        for r in conn.execute(
            """
            SELECT paper_id, outcome, result_json
            FROM paper_intelligence.affiliation_verifications
            WHERE verification_version = %s AND status = 'complete'
            ORDER BY paper_id
            """,
            (verification_version,),
        ).fetchall()
    ]
    by_outcome: dict[str, list[dict[str, Any]]] = {}
    for r in rows:
        oc = r.get("outcome") or "unknown"
        payload = r.get("result_json") or {}
        if isinstance(payload, str):
            payload = json.loads(payload)
        by_outcome.setdefault(oc, []).append(
            {
                "paper_id": r["paper_id"],
                "arxiv_id": payload.get("arxiv_id"),
                "html_orgs": (payload.get("html") or {}).get("org_names"),
                "oa_orgs": (payload.get("openalex") or {}).get("org_names"),
                "agreement": payload.get("agreement"),
                "title": payload.get("title"),
            }
        )
    return by_outcome


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--workers", type=int, default=DEFAULT_WORKERS)
    parser.add_argument("--verification-version", default=VERIFICATION_VERSION_DEFAULT)
    parser.add_argument("--from", dest="date_from", default="2026-09-01")
    parser.add_argument("--until", dest="date_until", default="2026-09-15")
    parser.add_argument("--limit", type=int, default=None)
    parser.add_argument("--resume", action="store_true")
    parser.add_argument("--dry-run", action="store_true", help="Enqueue only / plan only")
    parser.add_argument(
        "--set",
        dest="paper_set",
        choices=["both-sep", "targeted", "ids", "none"],
        default="none",
        help="both-sep=45 HTML+OA; targeted=Sep candidate set",
    )
    parser.add_argument(
        "--phase",
        choices=["local", "oa", "pdf", "full"],
        default="full",
        help="local=no OA network; oa=OA network; pdf=PDF queue; full=default",
    )
    parser.add_argument("--paper-id", type=int, action="append", default=[])
    parser.add_argument(
        "--allow-openalex-network",
        action="store_true",
        help="Permit OpenAlex HTTP on cache miss (default: cache/PI only for both-sep)",
    )
    parser.add_argument(
        "--prefer-cache",
        action="store_true",
        default=True,
        help="Do not call OpenAlex unless PI evidence incomplete (default)",
    )
    parser.add_argument("--benchmark", action="store_true", help="Run 1/4/8 worker micro-bench")
    parser.add_argument("--targeted-dry-run", action="store_true")
    parser.add_argument("--audit-sample", type=int, default=50)
    parser.add_argument(
        "--output",
        default=str(ROOT / "reports/backfill/affiliation_verify_run.json"),
    )
    args = parser.parse_args()

    # Ensure table exists (idempotent). Prefer psql when available.
    import subprocess

    db_url = os.environ.get("DATABASE_URL") or os.environ.get("PG_DSN")
    if not db_url:
        print("DATABASE_URL/PG_DSN required", file=sys.stderr)
        return 2
    for mig_name in (
        "010_affiliation_verifications.sql",
        "011_affiliation_verification_outcomes.sql",
    ):
        mig = ROOT / "sql/migrations" / mig_name
        subprocess.run(
            ["psql", db_url, "-v", "ON_ERROR_STOP=1", "-f", str(mig)],
            check=True,
            capture_output=True,
            text=True,
        )

    report: dict[str, Any] = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "args": {
            "workers": args.workers,
            "verification_version": args.verification_version,
            "date_from": args.date_from,
            "date_until": args.date_until,
            "set": args.paper_set,
            "resume": args.resume,
            "dry_run": args.dry_run,
            "allow_openalex_network": args.allow_openalex_network,
            "phase": getattr(args, "phase", "full"),
        },
    }

    if args.targeted_dry_run:
        with connect() as conn:
            targeted = select_targeted_candidates(
                conn,
                date_from=args.date_from,
                date_until=args.date_until,
                audit_sample=args.audit_sample,
            )
        report["targeted"] = {k: v for k, v in targeted.items() if k != "paper_ids"}
        report["targeted"]["paper_id_count"] = targeted["total_candidates"]

        measured_ppm: dict[int, float] = {}
        prior = ROOT / "reports/backfill/affiliation_verify_45_html_oa.json"
        bench_path = ROOT / "reports/backfill/affiliation_verify_benchmark.json"
        if bench_path.exists():
            bj = json.loads(bench_path.read_text())
            for k, v in (bj.get("benchmark") or {}).items():
                measured_ppm[int(k)] = float(v.get("papers_per_minute") or 0)
            if bj.get("recommended_workers"):
                report["targeted"]["recommended_workers"] = bj["recommended_workers"]
        if 8 not in measured_ppm and prior.exists():
            pj = json.loads(prior.read_text())
            run = pj.get("run") or {}
            if run.get("papers_per_minute"):
                measured_ppm[8] = float(run["papers_per_minute"])

        remaining = int(targeted.get("remaining_to_verify") or targeted["total_candidates"])
        projections: dict[str, Any] = {}
        best_measured_w = max(measured_ppm, key=measured_ppm.get) if measured_ppm else None
        best_measured_ppm = measured_ppm[best_measured_w] if best_measured_w else 0.0
        for w in (1, 4, 8, 16):
            if w in measured_ppm and measured_ppm[w] > 0:
                ppm = measured_ppm[w]
                source = "measured"
            elif best_measured_ppm and best_measured_w:
                # Do not invent gains past the best measured worker count —
                # bench showed 8 workers slower than 4 (DB contention).
                if w > best_measured_w:
                    ppm = best_measured_ppm
                    source = f"capped_at_best_measured_w{best_measured_w}"
                else:
                    ppm = best_measured_ppm * (w / best_measured_w)
                    source = f"scaled_from_w{best_measured_w}"
            else:
                ppm = 0
                source = "unavailable"
            mins = (remaining / ppm) if ppm > 0 else None
            projections[str(w)] = {
                "papers_per_minute": round(ppm, 2) if ppm else None,
                "estimated_minutes": round(mins, 2) if mins is not None else None,
                "source": source,
            }
        report["targeted"]["runtime_projections"] = projections
        report["targeted"]["estimated_external_api_calls"] = targeted[
            "oa_lookup_required_among_remaining"
        ]
        report["targeted"]["measured_ppm_inputs"] = measured_ppm

        Path(args.output).parent.mkdir(parents=True, exist_ok=True)
        Path(args.output).write_text(json.dumps(report, indent=2, default=str))
        print(json.dumps(report["targeted"], indent=2, default=str))
        print(f"wrote {args.output}")
        return 0

    paper_ids: list[int] = list(args.paper_id)
    if args.paper_set == "both-sep":
        with connect() as conn:
            paper_ids = select_both_html_oa_sep(conn, args.date_from, args.date_until)
        print(f"both-sep papers: {len(paper_ids)}")
    elif args.paper_set == "targeted":
        with connect() as conn:
            targeted = select_targeted_candidates(
                conn,
                date_from=args.date_from,
                date_until=args.date_until,
                audit_sample=args.audit_sample,
            )
            paper_ids = list(targeted["paper_ids"])
        print(f"targeted papers: {len(paper_ids)}")
    if args.limit is not None:
        paper_ids = paper_ids[: args.limit]

    if paper_ids and not args.resume:
        with connect() as conn:
            n = enqueue_papers(
                conn, paper_ids, verification_version=args.verification_version
            )
        print(f"enqueued_new={n} total_ids={len(paper_ids)}")
        report["enqueued_new"] = n
        report["enqueued_total_ids"] = len(paper_ids)

    if args.dry_run:
        with connect() as conn:
            report["status_counts"] = counts_by_status(
                conn, verification_version=args.verification_version
            )
        Path(args.output).write_text(json.dumps(report, indent=2, default=str))
        print(json.dumps(report, indent=2, default=str))
        return 0

    allow_network = bool(args.allow_openalex_network)
    phase = args.phase
    if phase == "local":
        allow_network = False

    if args.benchmark:
        # Micro-bench: same papers, distinct verification_version per worker count.
        # Cache/PI only — no duplicate OpenAlex network calls.
        bench: dict[str, Any] = {}
        base_ids = paper_ids[: min(45, len(paper_ids))] if paper_ids else []
        if not base_ids:
            with connect() as conn:
                base_ids = select_both_html_oa_sep(conn, args.date_from, args.date_until)
        timing_breakdown: dict[str, dict[str, float]] = {}
        for w in (1, 4, 8):
            ver = f"{args.verification_version}-bench{w}-{uuid.uuid4().hex[:6]}"
            with connect() as conn:
                enqueue_papers(conn, base_ids, verification_version=ver)
            stats = run_workers(
                workers=w,
                verification_version=ver,
                allow_network=False,  # never duplicate external calls in bench
                max_papers=len(base_ids),
                phase="local",
            )
            details = stats.get("details") or []
            db_ms = html_ms = oa_ms = pdf_ms = 0.0
            n = 0
            for d in details:
                tm = d.get("timing_ms") or {}
                if not tm:
                    continue
                n += 1
                db_ms += float(tm.get("db_paper_ms") or 0) + float(tm.get("pi_oa_ms") or 0)
                html_ms += float(tm.get("html_ms") or 0)
                oa_ms += float(tm.get("oa_wait_ms") or 0)
                pdf_ms += float(tm.get("pdf_ms") or 0)
            timing_breakdown[str(w)] = {
                "db_ms_avg": round(db_ms / n, 2) if n else 0,
                "html_ms_avg": round(html_ms / n, 2) if n else 0,
                "oa_wait_ms_avg": round(oa_ms / n, 2) if n else 0,
                "pdf_ms_avg": round(pdf_ms / n, 2) if n else 0,
            }
            bench[str(w)] = {
                "papers": stats["processed"],
                "wall_seconds": stats["wall_seconds"],
                "papers_per_minute": stats["papers_per_minute"],
                "external": stats["external"],
                "timing_ms_avg": stats["timing_ms_avg"],
                "timing_breakdown": timing_breakdown[str(w)],
                "outcomes": stats["outcomes"],
            }
            print(f"bench workers={w}: {bench[str(w)]}")
        report["benchmark"] = bench
        # Recommend where throughput stops improving materially (>10%)
        rates = [(int(k), v["papers_per_minute"]) for k, v in bench.items()]
        rates.sort()
        recommended = rates[0][0]
        best = rates[0][1]
        for w, ppm in rates[1:]:
            if best <= 0 or (ppm - best) / max(best, 1e-6) >= 0.10:
                recommended = w
                best = ppm
            else:
                break
        report["recommended_workers"] = recommended
        Path(args.output).parent.mkdir(parents=True, exist_ok=True)
        Path(args.output).write_text(json.dumps(report, indent=2, default=str))
        print(json.dumps({"recommended_workers": recommended, "benchmark": bench}, indent=2))
        return 0

    # Main run
    stats = run_workers(
        workers=args.workers,
        verification_version=args.verification_version,
        allow_network=allow_network,
        max_papers=args.limit,
        phase=phase,
    )
    report["run"] = {k: v for k, v in stats.items() if k != "details"}
    report["run_details"] = stats.get("details")

    with connect() as conn:
        report["investigation_by_outcome"] = investigate_prior_cases(
            conn, args.verification_version
        )

    Path(args.output).parent.mkdir(parents=True, exist_ok=True)
    Path(args.output).write_text(json.dumps(report, indent=2, default=str))
    print(json.dumps(report["run"], indent=2, default=str))
    print(f"wrote {args.output}")
    return 0 if stats.get("errors", 0) == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
