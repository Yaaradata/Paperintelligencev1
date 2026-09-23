#!/usr/bin/env python3
"""September 1–15 affiliation judge: queue + bounded paid batch.

  # Classify + cost estimate only (no paid calls):
  PYTHONPATH=src python3 scripts/affiliation_judge_september.py --queue-only

  # Execute first N new disagreements (default 50), hard spend cap $0.10:
  PYTHONPATH=src python3 scripts/affiliation_judge_september.py --execute --batch-size 50
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import subprocess
import sys
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from paper_intelligence.adjudication.org_score import MIN_CONFIDENCE, organisation_score  # noqa: E402
from paper_intelligence.author_affiliation.verify.judge_compare import (  # noqa: E402
    collect_claims,
    compare_claims,
)
from paper_intelligence.author_affiliation.verify.judge_effective import (  # noqa: E402
    effective_organisation_ids,
)
from paper_intelligence.author_affiliation.verify.judge_llm import (  # noqa: E402
    build_judge_payload,
    estimate_judge_tokens,
)
from paper_intelligence.author_affiliation.verify.judge_persist import (  # noqa: E402
    JUDGE_VERSION_DEFAULT,
    get_existing_judgment,
)
from paper_intelligence.author_affiliation.verify.judge_workflow import (  # noqa: E402
    process_paper_affiliation_judge,
)
from paper_intelligence.common.config import read_prompt  # noqa: E402
from paper_intelligence.db import connect  # noqa: E402

DATE_FROM = "2026-09-01"
DATE_UNTIL = "2026-09-15"
HARD_SPEND_CAP_USD = 0.10
DEFAULT_BATCH = 50
PROMPT_VERSION = os.getenv("AFFILIATION_JUDGE_PROMPT_VERSION", "v001")


def evidence_version(claims: dict, compare: dict) -> str:
    payload = {
        "html_ids": compare.get("html_org_ids") or [],
        "html_names": compare.get("html_org_names") or [],
        "oa_ids": compare.get("oa_org_ids") or [],
        "oa_names": compare.get("oa_org_names") or [],
        "oa_work": (claims.get("openalex") or {}).get("work_id"),
    }
    raw = json.dumps(payload, sort_keys=True, ensure_ascii=False, default=str)
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()[:20]


def apply_migrations(db_url: str) -> int:
    try:
        with connect() as conn:
            has_rejected = conn.execute(
                """
                SELECT 1 FROM information_schema.columns
                WHERE table_schema='paper_intelligence'
                  AND table_name='affiliation_judgments'
                  AND column_name='rejected_organisation_ids'
                """
            ).fetchone()
            has_table = conn.execute(
                """
                SELECT 1 FROM information_schema.tables
                WHERE table_schema='paper_intelligence'
                  AND table_name='affiliation_judgments'
                """
            ).fetchone()
    except Exception as exc:  # noqa: BLE001
        print(f"DB connect failed: {exc}", file=sys.stderr)
        return 2
    needed = []
    if not has_table:
        needed.extend(
            [
                "010_affiliation_verifications.sql",
                "011_affiliation_verification_outcomes.sql",
                "012_affiliation_judgments.sql",
            ]
        )
    if not has_rejected:
        needed.append("013_affiliation_judgment_rejects.sql")
    for mig in needed:
        proc = subprocess.run(
            ["psql", db_url, "-v", "ON_ERROR_STOP=1", "-f", str(ROOT / "sql/migrations" / mig)],
            capture_output=True,
            text=True,
        )
        if proc.returncode != 0:
            print(proc.stderr or proc.stdout, file=sys.stderr)
            return 3
    return 0


def september_paper_ids(conn) -> list[int]:
    rows = conn.execute(
        """
        SELECT paper_id
        FROM paper_intelligence.papers
        WHERE published_at >= %s::timestamptz
          AND published_at < (%s::timestamptz + interval '1 day')
        ORDER BY paper_id
        """,
        (DATE_FROM, DATE_UNTIL),
    ).fetchall()
    return [int(r["paper_id"]) for r in rows]


def load_affiliation_rows(conn, paper_id: int) -> list[dict]:
    rows = conn.execute(
        """
        SELECT a.organisation_id, a.evidence_type, a.confidence,
               o.canonical_name, o.priority, o.is_org_of_interest
        FROM paper_intelligence.paper_author_affiliations a
        LEFT JOIN paper_intelligence.organisations o ON o.id = a.organisation_id
        WHERE a.content_item_id = %s
        """,
        (int(paper_id),),
    ).fetchall()
    return [dict(r) for r in rows]


def org_names(conn, ids: list[int]) -> dict[int, str]:
    if not ids:
        return {}
    rows = conn.execute(
        "SELECT id, canonical_name FROM paper_intelligence.organisations WHERE id = ANY(%s)",
        (ids,),
    ).fetchall()
    return {int(r["id"]): r["canonical_name"] for r in rows}


def existing_evidence_version(judgment: dict | None) -> str | None:
    if not judgment:
        return None
    result = judgment.get("result_json") or {}
    if isinstance(result, str):
        try:
            result = json.loads(result)
        except Exception:  # noqa: BLE001
            return None
    return result.get("evidence_version")


def is_reusable_judgment(judgment: dict | None, ev: str) -> bool:
    """Completed judgment for same judge_version + evidence fingerprint."""
    if not judgment:
        return False
    prior_ev = existing_evidence_version(judgment)
    if prior_ev and prior_ev != ev:
        return False  # evidence changed → not reusable
    # Auto paths and paid decisions are reusable when evidence matches (or unknown prior).
    if judgment.get("judge_called"):
        return True
    if judgment.get("decision") in (
        "AUTO_AGREE",
        "AUTO_HTML",
        "AUTO_SKIP",
        "HTML",
        "OPENALEX",
        "BOTH",
        "UNCERTAIN",
    ):
        # Reuse auto classifications when evidence fingerprint matches or missing
        # (legacy rows without fingerprint still reusable for non-disagreement).
        if prior_ev is None or prior_ev == ev:
            return True
    return False


def build_queue(
    conn,
    *,
    judge_version: str,
    allow_openalex_network: bool = False,
) -> dict:
    system_prompt = read_prompt("affiliation_judge", PROMPT_VERSION)
    paper_ids = september_paper_ids(conn)
    status_c: Counter[str] = Counter()
    papers: list[dict] = []
    new_judge_queue: list[dict] = []
    reused = 0
    total_est = 0.0

    for pid in paper_ids:
        claims = collect_claims(
            conn, pid, allow_openalex_network=allow_openalex_network
        )
        compare = compare_claims(claims)
        status = compare["compare_status"]
        status_c[status] += 1
        ev = evidence_version(claims, compare)
        existing = get_existing_judgment(conn, pid, judge_version=judge_version)
        reusable = is_reusable_judgment(existing, ev)

        rec = {
            "paper_id": pid,
            "arxiv_id": claims.get("arxiv_id"),
            "compare_status": status,
            "needs_judge": bool(compare.get("needs_judge")),
            "evidence_version": ev,
            "reusable_judgment": reusable,
            "prior_decision": (existing or {}).get("decision"),
            "prior_judge_called": bool((existing or {}).get("judge_called")),
        }

        if compare.get("needs_judge"):
            if reusable and existing and existing.get("judge_called"):
                reused += 1
                rec["queue"] = "skip_existing_judgment"
            else:
                payload = build_judge_payload(claims, compare)
                est = estimate_judge_tokens(payload, system_prompt)
                total_est += float(est.get("estimated_cost_usd") or 0)
                rec["queue"] = "new_paid_judge"
                rec["estimate"] = est
                new_judge_queue.append(rec)
        else:
            rec["queue"] = "no_judge"

        papers.append(rec)

    return {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "window": {"from": DATE_FROM, "until": DATE_UNTIL},
        "judge_version": judge_version,
        "paper_count": len(paper_ids),
        "compare_counts": dict(status_c),
        "reused_paid_judgments": reused,
        "new_judge_queue_size": len(new_judge_queue),
        "estimated_total_judge_cost_usd": round(total_est, 6),
        "new_judge_queue": new_judge_queue,
        "papers": papers,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--queue-only", action="store_true", help="Classify + estimate only")
    parser.add_argument("--execute", action="store_true", help="Run paid batch after queue")
    parser.add_argument(
        "--use-existing-queue",
        action="store_true",
        help="Load --queue-output JSON instead of re-classifying all papers",
    )
    parser.add_argument("--batch-size", type=int, default=DEFAULT_BATCH)
    parser.add_argument("--spend-cap-usd", type=float, default=HARD_SPEND_CAP_USD)
    parser.add_argument("--judge-version", default=JUDGE_VERSION_DEFAULT)
    parser.add_argument(
        "--allow-openalex-network",
        action="store_true",
        help="Permit OA HTTP on cache miss (default: PI/cache only)",
    )
    parser.add_argument("--call-pause-seconds", type=float, default=8.0)
    parser.add_argument("--rate-limit-sleep-seconds", type=float, default=90.0)
    parser.add_argument("--per-paper-retries", type=int, default=4)
    parser.add_argument(
        "--queue-output",
        default=str(ROOT / "reports/backfill/affiliation_judge_sep_queue.json"),
    )
    parser.add_argument(
        "--execute-output",
        default=str(ROOT / "reports/backfill/affiliation_judge_sep_batch50.json"),
    )
    args = parser.parse_args()
    if not args.queue_only and not args.execute:
        args.queue_only = True

    db_url = os.environ.get("DATABASE_URL") or os.environ.get("PG_DSN")
    if not db_url:
        print("DATABASE_URL required", file=sys.stderr)
        return 2
    if "sslmode=" not in db_url:
        db_url = db_url + ("&" if "?" in db_url else "?") + "sslmode=require"
    mig_rc = apply_migrations(db_url)
    if mig_rc:
        return mig_rc

    from paper_intelligence.openrouter import OpenRouterError  # local import
    import time

    with connect() as conn:
        queue_path = Path(args.queue_output)
        if args.use_existing_queue and queue_path.exists():
            queue = json.loads(queue_path.read_text())
            print(f"Loaded existing queue from {queue_path}")
        else:
            queue = build_queue(
                conn,
                judge_version=args.judge_version,
                allow_openalex_network=args.allow_openalex_network,
            )
            queue_path.parent.mkdir(parents=True, exist_ok=True)
            queue_path.write_text(json.dumps(queue, indent=2, default=str))
        summary = {
            k: queue[k]
            for k in queue
            if k not in ("papers", "new_judge_queue")
        }
        print("=== SEPTEMBER QUEUE ===")
        print(json.dumps(summary, indent=2, default=str))
        print(f"wrote/using {args.queue_output}")
        print(
            f"\nNEW paid judge calls: {queue['new_judge_queue_size']}  "
            f"est. ${queue['estimated_total_judge_cost_usd']:.4f}"
        )
        print(
            f"Batch plan: first {min(args.batch_size, queue['new_judge_queue_size'])} "
            f"of {queue['new_judge_queue_size']}  "
            f"spend_cap=${args.spend_cap_usd}"
        )

        if args.queue_only and not args.execute:
            return 0

        # Take first N queue items; skip those already paid for this judge version.
        planned = queue["new_judge_queue"][: args.batch_size]
        batch: list[dict] = []
        already_done: list[int] = []
        for item in planned:
            existing = get_existing_judgment(
                conn, int(item["paper_id"]), judge_version=args.judge_version
            )
            if existing and existing.get("judge_called"):
                already_done.append(int(item["paper_id"]))
                continue
            batch.append(item)
        # If some of the first-50 already done, pull more from the full queue to fill.
        if len(batch) < args.batch_size:
            planned_ids = {int(x["paper_id"]) for x in planned}
            for item in queue["new_judge_queue"]:
                if len(batch) >= args.batch_size:
                    break
                pid = int(item["paper_id"])
                if pid in planned_ids:
                    continue
                existing = get_existing_judgment(
                    conn, pid, judge_version=args.judge_version
                )
                if existing and existing.get("judge_called"):
                    continue
                batch.append(item)

        report: dict = {
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "window": queue["window"],
            "judge_version": args.judge_version,
            "queue_summary": summary,
            "batch_size_requested": args.batch_size,
            "batch_size_planned": len(batch),
            "already_done_in_first_n": already_done,
            "spend_cap_usd": args.spend_cap_usd,
            "papers": [],
            "before_after": [],
            "decision_counts": Counter(),
            "paid_calls": 0,
            "actual_cost_usd": 0.0,
            "errors": [],
            "idempotency": [],
            "remaining_unjudged": max(0, queue["new_judge_queue_size"] - args.batch_size),
        }
        print(
            f"Resume: {len(already_done)} already judged in first-{args.batch_size}; "
            f"will call {len(batch)} remaining"
        )

        for item in batch:
            if report["actual_cost_usd"] >= args.spend_cap_usd:
                report.setdefault("spend_blocked", []).append(item["paper_id"])
                break
            if report["paid_calls"] >= args.batch_size:
                break

            pid = int(item["paper_id"])
            rows_before = load_affiliation_rows(conn, pid)
            before_ids = effective_organisation_ids(
                rows_before, min_confidence=MIN_CONFIDENCE
            )

            out: dict | None = None
            last_err: str | None = None
            for attempt in range(1, args.per_paper_retries + 1):
                try:
                    out = process_paper_affiliation_judge(
                        conn,
                        pid,
                        dry_run=False,
                        allow_openalex_network=args.allow_openalex_network,
                        judge_version=args.judge_version,
                        persist=True,
                        force=False,
                    )
                    last_err = None
                    break
                except OpenRouterError as exc:
                    last_err = str(exc)
                    print(
                        f"paper {pid} attempt {attempt}/{args.per_paper_retries}: {exc}",
                        file=sys.stderr,
                    )
                    if attempt < args.per_paper_retries:
                        time.sleep(args.rate_limit_sleep_seconds)
                    else:
                        report["errors"].append(
                            {"paper_id": pid, "error": last_err[:500]}
                        )
            if out is None:
                continue

            # Stamp evidence_version onto judgment result
            jrow = get_existing_judgment(conn, pid, judge_version=args.judge_version)
            if jrow and not out.get("skipped_duplicate"):
                result = jrow.get("result_json") or {}
                if isinstance(result, str):
                    try:
                        result = json.loads(result)
                    except Exception:  # noqa: BLE001
                        result = {}
                result["evidence_version"] = item.get("evidence_version")
                conn.execute(
                    """
                    UPDATE paper_intelligence.affiliation_judgments
                    SET result_json = %s::jsonb
                    WHERE judgment_id = %s
                    """,
                    (json.dumps(result, default=str), jrow["judgment_id"]),
                )
                conn.commit()

            new_paid = bool(
                out.get("judge_called") and not out.get("skipped_duplicate")
            )
            cost = 0.0
            if new_paid:
                report["paid_calls"] += 1
                llm = ((out.get("judge") or {}).get("llm") or {})
                cost = float(llm.get("estimated_cost") or 0)
                if cost <= 0 and jrow and jrow.get("estimated_cost_usd") is not None:
                    cost = float(jrow["estimated_cost_usd"])
                report["actual_cost_usd"] += cost
                if args.call_pause_seconds > 0:
                    time.sleep(args.call_pause_seconds)

            decision = out.get("decision")
            report["decision_counts"][str(decision)] += 1

            accepted = list(out.get("accepted_organisation_ids") or [])
            rejected = list(out.get("rejected_organisation_ids") or [])
            if jrow:
                accepted = list(jrow.get("accepted_organisation_ids") or accepted)
                rejected = list(jrow.get("rejected_organisation_ids") or rejected)

            rows_after = load_affiliation_rows(conn, pid)
            after_ids = effective_organisation_ids(
                rows_after,
                rejected_organisation_ids=rejected,
                decision=decision,
                judge_called=bool(out.get("judge_called")),
                min_confidence=MIN_CONFIDENCE,
            )
            scored = organisation_score(
                rows_after,
                rejected_organisation_ids=rejected,
                judge_decision=decision,
                judge_called=bool(out.get("judge_called")),
            )
            name_map = org_names(
                conn,
                sorted(set(before_ids) | set(after_ids) | set(accepted) | set(rejected)),
            )

            evidence_preserved = conn.execute(
                """
                SELECT
                  count(*) FILTER (WHERE evidence_type IN (
                    'explicit_paper_affiliation','ror_canonical_match','email_domain'
                  )) AS htmlish,
                  count(*) FILTER (WHERE evidence_type LIKE 'openalex%%') AS oa
                FROM paper_intelligence.paper_author_affiliations
                WHERE content_item_id = %s
                """,
                (pid,),
            ).fetchone()

            paper_rec = {
                "paper_id": pid,
                "arxiv_id": out.get("arxiv_id") or item.get("arxiv_id"),
                "decision": decision,
                "judge_called": out.get("judge_called"),
                "skipped_duplicate": out.get("skipped_duplicate"),
                "cost_usd": cost,
                "accepted_organisation_ids": accepted,
                "rejected_organisation_ids": rejected,
                "accepted_names": [name_map.get(i, str(i)) for i in accepted],
                "rejected_names": [name_map.get(i, str(i)) for i in rejected],
                "effective_before": [name_map.get(i, str(i)) for i in before_ids],
                "effective_after": [name_map.get(i, str(i)) for i in after_ids],
                "removed_ids": sorted(set(before_ids) - set(after_ids)),
                "added_ids": sorted(set(after_ids) - set(before_ids)),
                "adjudication_top_org_id": scored.get("organisation_id"),
                "adjudication_excludes_rejected": (
                    scored.get("organisation_id") not in set(rejected)
                    if scored.get("organisation_id") is not None
                    else True
                ),
                "original_evidence_row_counts": dict(evidence_preserved or {}),
                "reason": (out.get("reason") or "")[:400],
            }
            report["papers"].append(paper_rec)
            report["before_after"].append(
                {
                    "paper_id": pid,
                    "arxiv_id": paper_rec["arxiv_id"],
                    "decision": decision,
                    "before": paper_rec["effective_before"],
                    "after": paper_rec["effective_after"],
                    "accepted_ids": accepted,
                    "rejected_ids": rejected,
                }
            )
            # Checkpoint after each paper so a later crash keeps progress.
            Path(args.execute_output).write_text(
                json.dumps(
                    {
                        **report,
                        "decision_counts": dict(report["decision_counts"]),
                        "actual_cost_usd": round(report["actual_cost_usd"], 6),
                        "partial": True,
                    },
                    indent=2,
                    default=str,
                )
            )
            print(
                f"progress {report['paid_calls']}/{len(batch)} "
                f"pid={pid} decision={decision} cost=${report['actual_cost_usd']:.4f}"
            )

        # Include already-done first-N papers in the report for completeness.
        for pid in already_done:
            jrow = get_existing_judgment(conn, pid, judge_version=args.judge_version)
            if not jrow:
                continue
            rows = load_affiliation_rows(conn, pid)
            rejected = list(jrow.get("rejected_organisation_ids") or [])
            accepted = list(jrow.get("accepted_organisation_ids") or [])
            after_ids = effective_organisation_ids(
                rows,
                rejected_organisation_ids=rejected,
                decision=jrow.get("decision"),
                judge_called=True,
                min_confidence=MIN_CONFIDENCE,
            )
            before_ids = effective_organisation_ids(rows, min_confidence=MIN_CONFIDENCE)
            name_map = org_names(
                conn, sorted(set(before_ids) | set(after_ids) | set(accepted) | set(rejected))
            )
            cost = float(jrow["estimated_cost_usd"] or 0)
            report["decision_counts"][str(jrow.get("decision"))] += 1
            report["paid_calls"] += 1
            report["actual_cost_usd"] += cost
            paper = conn.execute(
                "SELECT arxiv_id FROM paper_intelligence.papers WHERE paper_id=%s",
                (pid,),
            ).fetchone()
            report["papers"].append(
                {
                    "paper_id": pid,
                    "arxiv_id": (paper or {}).get("arxiv_id"),
                    "decision": jrow.get("decision"),
                    "judge_called": True,
                    "skipped_duplicate": True,
                    "resumed_from_prior_run": True,
                    "cost_usd": cost,
                    "accepted_organisation_ids": accepted,
                    "rejected_organisation_ids": rejected,
                    "accepted_names": [name_map.get(i, str(i)) for i in accepted],
                    "rejected_names": [name_map.get(i, str(i)) for i in rejected],
                    "effective_before": [name_map.get(i, str(i)) for i in before_ids],
                    "effective_after": [name_map.get(i, str(i)) for i in after_ids],
                    "removed_ids": sorted(set(before_ids) - set(after_ids)),
                    "added_ids": sorted(set(after_ids) - set(before_ids)),
                    "reason": (jrow.get("reason") or "")[:400],
                }
            )

        # Idempotency: re-run first few judged papers
        for paper_rec in report["papers"][:5]:
            pid = int(paper_rec["paper_id"])
            n_before = conn.execute(
                """
                SELECT count(*) AS n FROM paper_intelligence.paper_author_affiliations
                WHERE content_item_id=%s AND evidence_type='llm_affiliation_judge'
                """,
                (pid,),
            ).fetchone()["n"]
            out2 = process_paper_affiliation_judge(
                conn,
                pid,
                dry_run=False,
                judge_version=args.judge_version,
                persist=True,
                force=False,
            )
            n_after = conn.execute(
                """
                SELECT count(*) AS n FROM paper_intelligence.paper_author_affiliations
                WHERE content_item_id=%s AND evidence_type='llm_affiliation_judge'
                """,
                (pid,),
            ).fetchone()["n"]
            report["idempotency"].append(
                {
                    "paper_id": pid,
                    "skipped_duplicate": bool(out2.get("skipped_duplicate")),
                    "no_new_rows": int(n_after) == int(n_before),
                }
            )

        judged_ids = {int(p["paper_id"]) for p in report["papers"]}
        remaining = [
            q
            for q in queue["new_judge_queue"]
            if int(q["paper_id"]) not in judged_ids
        ]
        # Also exclude any other paid judgments in the full new queue
        still = []
        for q in remaining:
            ex = get_existing_judgment(
                conn, int(q["paper_id"]), judge_version=args.judge_version
            )
            if ex and ex.get("judge_called"):
                continue
            still.append(q)
        report["remaining_unjudged"] = len(still)
        report["remaining_unjudged_paper_ids"] = [q["paper_id"] for q in still[:100]]
        report["decision_counts"] = dict(report["decision_counts"])
        report["actual_cost_usd"] = round(report["actual_cost_usd"], 6)
        report["partial"] = False
        report["idempotent"] = all(
            i.get("skipped_duplicate") and i.get("no_new_rows")
            for i in report["idempotency"]
        ) if report["idempotency"] else None

        Path(args.execute_output).write_text(json.dumps(report, indent=2, default=str))
        print("\n=== BATCH EXECUTE ===")
        print(
            json.dumps(
                {
                    k: report[k]
                    for k in report
                    if k
                    not in (
                        "papers",
                        "before_after",
                        "remaining_unjudged_paper_ids",
                        "queue_summary",
                    )
                },
                indent=2,
                default=str,
            )
        )
        print(f"wrote {args.execute_output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
