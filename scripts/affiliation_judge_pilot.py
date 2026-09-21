#!/usr/bin/env python3
"""Dry-run / execute HTML↔OpenAlex affiliation judge pilot (max 20 papers).

Default is DRY-RUN: no paid LLM calls.

  PYTHONPATH=src python3 scripts/affiliation_judge_pilot.py --dry-run
  PYTHONPATH=src python3 scripts/affiliation_judge_pilot.py --execute  # paid; needs approval
"""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from paper_intelligence.adjudication.org_score import MIN_CONFIDENCE  # noqa: E402
from paper_intelligence.author_affiliation.verify.judge_effective import (  # noqa: E402
    effective_organisation_ids,
)
from paper_intelligence.author_affiliation.verify.judge_persist import (  # noqa: E402
    JUDGE_VERSION_DEFAULT,
    get_existing_judgment,
)
from paper_intelligence.author_affiliation.verify.judge_workflow import (  # noqa: E402
    process_paper_affiliation_judge,
)
from paper_intelligence.db import connect  # noqa: E402

HARD_SPEND_CAP_USD = 0.05
MAX_PAID_CALLS = 6


def select_pilot_ids(conn, limit: int = 20) -> list[dict]:
    """Stratified sample from prior verification outcomes."""
    local = "html-oa-targeted-local-v002"
    buckets = {
        "exact": [],
        "disagreement": [],
        "html_only": [],
        "oa_only": [],
        "neither": [],
    }
    for outcome, key in (
        ("verified_agreement", "exact"),
        ("conflict", "disagreement"),
        ("partial_agreement", "disagreement"),
        ("verified_html_primary", "html_only"),
        ("verified_openalex_primary", "oa_only"),
        ("unresolved", "neither"),
        ("needs_openalex_lookup", "neither"),
    ):
        rows = conn.execute(
            """
            SELECT paper_id, outcome, result_json->>'arxiv_id' AS arxiv_id,
                   left(result_json->>'title', 80) AS title
            FROM paper_intelligence.affiliation_verifications
            WHERE verification_version = %s AND status = 'complete' AND outcome = %s
            ORDER BY paper_id
            LIMIT 8
            """,
            (local, outcome),
        ).fetchall()
        for r in rows:
            buckets[key].append(dict(r))

    picks: list[dict] = []
    plan = [
        ("exact", 4),
        ("disagreement", 6),
        ("html_only", 4),
        ("oa_only", 3),
        ("neither", 3),
    ]
    for key, n in plan:
        for item in buckets[key][:n]:
            item["pilot_bucket"] = key
            picks.append(item)
            if len(picks) >= limit:
                return picks[:limit]
    return picks[:limit]


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
        """
        SELECT id, canonical_name FROM paper_intelligence.organisations
        WHERE id = ANY(%s)
        """,
        (ids,),
    ).fetchall()
    return {int(r["id"]): r["canonical_name"] for r in rows}


def count_judge_evidence_rows(conn, paper_id: int) -> int:
    row = conn.execute(
        """
        SELECT count(*) AS n
        FROM paper_intelligence.paper_author_affiliations
        WHERE content_item_id = %s AND evidence_type = 'llm_affiliation_judge'
        """,
        (int(paper_id),),
    ).fetchone()
    return int(row["n"])


def apply_migrations(db_url: str) -> int:
    try:
        with connect() as conn:
            have = {
                r["relname"]
                for r in conn.execute(
                    """
                    SELECT relname FROM pg_class c
                    JOIN pg_namespace n ON n.oid = c.relnamespace
                    WHERE n.nspname = 'paper_intelligence'
                      AND relname = ANY(%s)
                    """,
                    (["affiliation_verifications", "affiliation_judgments"],),
                ).fetchall()
            }
            has_rejected_col = conn.execute(
                """
                SELECT 1 FROM information_schema.columns
                WHERE table_schema = 'paper_intelligence'
                  AND table_name = 'affiliation_judgments'
                  AND column_name = 'rejected_organisation_ids'
                """
            ).fetchone()
    except Exception as exc:  # noqa: BLE001
        print(f"DB connect failed: {exc}", file=sys.stderr)
        print(
            "Hint: export DATABASE_URL from Paperintelligencev1/.env "
            "(neural_admin + password). A passwordless neural_rw URL will fail.",
            file=sys.stderr,
        )
        return 2

    needed: list[str] = []
    if "affiliation_verifications" not in have:
        needed.append("010_affiliation_verifications.sql")
    if "affiliation_verifications" in have or "010_affiliation_verifications.sql" in needed:
        needed.append("011_affiliation_verification_outcomes.sql")
    if "affiliation_judgments" not in have:
        needed.append("012_affiliation_judgments.sql")
    if not has_rejected_col:
        needed.append("013_affiliation_judgment_rejects.sql")

    for mig in needed:
        path = ROOT / "sql/migrations" / mig
        proc = subprocess.run(
            ["psql", db_url, "-v", "ON_ERROR_STOP=1", "-f", str(path)],
            capture_output=True,
            text=True,
        )
        if proc.returncode != 0:
            print(f"Migration {mig} failed (exit {proc.returncode}):", file=sys.stderr)
            if proc.stdout:
                print(proc.stdout, file=sys.stderr)
            if proc.stderr:
                print(proc.stderr, file=sys.stderr)
            return 3
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dry-run", action="store_true", default=True)
    parser.add_argument(
        "--execute",
        action="store_true",
        help="Actually call the paid LLM judge (requires prior approval)",
    )
    parser.add_argument("--limit", type=int, default=20)
    parser.add_argument("--judge-version", default=JUDGE_VERSION_DEFAULT)
    parser.add_argument("--spend-cap-usd", type=float, default=HARD_SPEND_CAP_USD)
    parser.add_argument("--max-paid-calls", type=int, default=MAX_PAID_CALLS)
    parser.add_argument(
        "--force-repair-empty-accept",
        action="store_true",
        help="Re-call judge for resolved decisions that stored zero accepted orgs",
    )
    parser.add_argument(
        "--allow-openalex-network",
        action="store_true",
        help="Permit OpenAlex HTTP on cache miss (default: PI/cache only)",
    )
    parser.add_argument(
        "--output",
        default=str(ROOT / "reports/backfill/affiliation_judge_pilot_dry_run.json"),
    )
    args = parser.parse_args()
    dry_run = not args.execute

    db_url = os.environ.get("DATABASE_URL") or os.environ.get("PG_DSN")
    if not db_url:
        print("DATABASE_URL required (source Paperintelligencev1/.env)", file=sys.stderr)
        return 2
    if "sslmode=" not in db_url:
        db_url = db_url + ("&" if "?" in db_url else "?") + "sslmode=require"

    mig_rc = apply_migrations(db_url)
    if mig_rc:
        return mig_rc

    report: dict = {
        "dry_run": dry_run,
        "judge_version": args.judge_version,
        "spend_cap_usd": args.spend_cap_usd,
        "max_paid_calls": args.max_paid_calls,
        "papers": [],
        "before_after": [],
        "judge_decisions": [],
    }
    with connect() as conn:
        pilots = select_pilot_ids(conn, limit=args.limit)
        report["pilot_count"] = len(pilots)
        status_c: Counter[str] = Counter()
        judge_needed = 0
        total_est_cost = 0.0
        paid_calls = 0
        actual_cost = 0.0
        examples: dict = {}
        spend_blocked = 0

        # Snapshot BEFORE effective sets (no reject filter).
        before_by_pid: dict[int, list[int]] = {}
        judge_row_counts_before: dict[int, int] = {}
        for p in pilots:
            pid = int(p["paper_id"])
            rows = load_affiliation_rows(conn, pid)
            before_by_pid[pid] = effective_organisation_ids(
                rows, min_confidence=MIN_CONFIDENCE
            )
            judge_row_counts_before[pid] = count_judge_evidence_rows(conn, pid)

        for p in pilots:
            pid = int(p["paper_id"])
            existing = get_existing_judgment(
                conn, pid, judge_version=args.judge_version
            )
            force = False
            if (
                args.force_repair_empty_accept
                and not dry_run
                and existing
                and existing.get("judge_called")
                and str(existing.get("decision") or "").upper()
                in ("HTML", "OPENALEX", "BOTH")
                and not list(existing.get("accepted_organisation_ids") or [])
            ):
                force = True
            would_call = not dry_run and (
                force or not (existing and existing.get("judge_called"))
            )
            # Cap paid spend / call count before invoking.
            if would_call:
                # Only disagreements need paid calls; cheap pre-check via process
                # after skip/auto paths. Soft estimate gate:
                if paid_calls >= args.max_paid_calls:
                    spend_blocked += 1
                    report["papers"].append(
                        {
                            "pilot_bucket": p.get("pilot_bucket"),
                            "paper_id": pid,
                            "blocked": "max_paid_calls",
                        }
                    )
                    continue
                if actual_cost >= args.spend_cap_usd:
                    spend_blocked += 1
                    report["papers"].append(
                        {
                            "pilot_bucket": p.get("pilot_bucket"),
                            "paper_id": pid,
                            "blocked": "spend_cap",
                        }
                    )
                    continue

            out = process_paper_affiliation_judge(
                conn,
                pid,
                dry_run=dry_run,
                allow_openalex_network=args.allow_openalex_network,
                judge_version=args.judge_version,
                persist=True,
                force=force,
            )
            status = (out.get("compare") or {}).get("compare_status") or out.get(
                "compare_status"
            )
            status_c[str(status)] += 1

            new_paid = bool(
                out.get("judge_called")
                and not out.get("skipped_duplicate")
                and not dry_run
            )
            if new_paid:
                paid_calls += 1
                llm_cost = 0.0
                judge = out.get("judge") or {}
                llm = judge.get("llm") or {}
                if llm.get("estimated_cost") is not None:
                    llm_cost = float(llm["estimated_cost"])
                elif out.get("estimate"):
                    llm_cost = float(out["estimate"].get("estimated_cost_usd") or 0)
                actual_cost += llm_cost
                if actual_cost > args.spend_cap_usd:
                    print(
                        f"HARD SPEND CAP exceeded after paper {pid}: "
                        f"${actual_cost:.4f} > ${args.spend_cap_usd}",
                        file=sys.stderr,
                    )
                    # Stop further paid work; remaining papers still get auto paths
                    # via subsequent loop with existing judgments / no-call.

            if out.get("needs_judge"):
                judge_needed += 1
                est = out.get("estimate") or {}
                total_est_cost += float(est.get("estimated_cost_usd") or 0)
                if "disagreement_example" not in examples:
                    examples["disagreement_example"] = {
                        "paper_id": pid,
                        "arxiv_id": out.get("arxiv_id"),
                        "title": out.get("title"),
                        "compare": out.get("compare"),
                        "estimate": est,
                    }
            elif status == "exact_match" and "exact_example" not in examples:
                examples["exact_example"] = {
                    "paper_id": pid,
                    "arxiv_id": out.get("arxiv_id"),
                    "decision": out.get("decision"),
                    "org_ids": out.get("accepted_organisation_ids"),
                }
            elif status == "html_only" and "html_only_example" not in examples:
                examples["html_only_example"] = {
                    "paper_id": pid,
                    "decision": out.get("decision"),
                    "needs_judge": out.get("needs_judge"),
                }

            accepted_ids = list(out.get("accepted_organisation_ids") or [])
            rejected_ids = list(out.get("rejected_organisation_ids") or [])
            # Prefer DB judgment after persist/backfill
            jrow = get_existing_judgment(conn, pid, judge_version=args.judge_version)
            if jrow:
                accepted_ids = list(jrow.get("accepted_organisation_ids") or accepted_ids)
                rejected_ids = list(jrow.get("rejected_organisation_ids") or rejected_ids)

            rows_after = load_affiliation_rows(conn, pid)
            after_ids = effective_organisation_ids(
                rows_after,
                rejected_organisation_ids=rejected_ids,
                decision=out.get("decision") or (jrow or {}).get("decision"),
                judge_called=bool(
                    out.get("judge_called") or (jrow or {}).get("judge_called")
                ),
                min_confidence=MIN_CONFIDENCE,
            )
            name_map = org_names(
                conn, sorted(set(before_by_pid[pid]) | set(after_ids) | set(accepted_ids) | set(rejected_ids))
            )

            paper_rec = {
                "pilot_bucket": p.get("pilot_bucket"),
                "paper_id": pid,
                "arxiv_id": out.get("arxiv_id") or p.get("arxiv_id"),
                "compare_status": status,
                "needs_judge": out.get("needs_judge"),
                "decision": out.get("decision"),
                "judge_called": out.get("judge_called"),
                "skipped_duplicate": out.get("skipped_duplicate"),
                "estimate": out.get("estimate"),
                "reason": out.get("reason"),
                "accepted_organisation_ids": accepted_ids,
                "rejected_organisation_ids": rejected_ids,
                "accepted_organisation_names": [name_map.get(i, str(i)) for i in accepted_ids],
                "rejected_organisation_names": [name_map.get(i, str(i)) for i in rejected_ids],
                "effective_before_ids": before_by_pid[pid],
                "effective_after_ids": after_ids,
                "effective_before_names": [name_map.get(i, str(i)) for i in before_by_pid[pid]],
                "effective_after_names": [name_map.get(i, str(i)) for i in after_ids],
                "judge_evidence_rows_before": judge_row_counts_before[pid],
                "judge_evidence_rows_after": count_judge_evidence_rows(conn, pid),
            }
            report["papers"].append(paper_rec)
            report["before_after"].append(
                {
                    "paper_id": pid,
                    "arxiv_id": paper_rec["arxiv_id"],
                    "decision": paper_rec["decision"],
                    "before": paper_rec["effective_before_names"],
                    "after": paper_rec["effective_after_names"],
                    "accepted_ids": accepted_ids,
                    "rejected_ids": rejected_ids,
                    "removed": sorted(set(before_by_pid[pid]) - set(after_ids)),
                    "added": sorted(set(after_ids) - set(before_by_pid[pid])),
                }
            )
            if status == "disagreement" or out.get("judge_called"):
                report["judge_decisions"].append(
                    {
                        "paper_id": pid,
                        "arxiv_id": paper_rec["arxiv_id"],
                        "decision": paper_rec["decision"],
                        "accepted_organisation_ids": accepted_ids,
                        "rejected_organisation_ids": rejected_ids,
                        "reason": (paper_rec.get("reason") or "")[:300],
                        "skipped_duplicate": paper_rec.get("skipped_duplicate"),
                    }
                )

        # Idempotency pass: re-run disagreements; expect skip + no new rows.
        idempotency: list[dict] = []
        if not dry_run:
            for p in pilots:
                if p.get("pilot_bucket") != "disagreement":
                    continue
                pid = int(p["paper_id"])
                before_n = count_judge_evidence_rows(conn, pid)
                out2 = process_paper_affiliation_judge(
                    conn,
                    pid,
                    dry_run=False,
                    allow_openalex_network=False,
                    judge_version=args.judge_version,
                    persist=True,
                    force=False,
                )
                after_n = count_judge_evidence_rows(conn, pid)
                idempotency.append(
                    {
                        "paper_id": pid,
                        "skipped_duplicate": bool(out2.get("skipped_duplicate")),
                        "judge_called": bool(out2.get("judge_called")),
                        "rows_before": before_n,
                        "rows_after": after_n,
                        "no_new_rows": after_n == before_n,
                        "no_new_paid_call": bool(out2.get("skipped_duplicate")),
                    }
                )

    report["counts"] = {
        "exact_match": status_c.get("exact_match", 0),
        "disagreement": status_c.get("disagreement", 0),
        "html_only": status_c.get("html_only", 0),
        "openalex_only": status_c.get("openalex_only", 0),
        "neither": status_c.get("neither", 0),
        "oa_unavailable": status_c.get("oa_unavailable", 0),
        "by_status": dict(status_c),
    }
    report["proposed_judge_calls"] = judge_needed
    report["estimated_total_judge_cost_usd"] = round(total_est_cost, 6)
    report["paid_calls_this_run"] = paid_calls
    report["actual_judge_cost_usd"] = round(actual_cost, 6)
    report["spend_blocked"] = spend_blocked
    report["examples"] = examples
    report["idempotency"] = idempotency if not dry_run else []
    report["verification_checks"] = {
        "matched_sources_do_not_invoke_judge": all(
            not p.get("needs_judge")
            for p in report["papers"]
            if p.get("compare_status") == "exact_match"
        ),
        "missing_oa_does_not_invoke_judge": all(
            not p.get("needs_judge")
            for p in report["papers"]
            if p.get("compare_status") in ("html_only", "oa_unavailable", "neither", "openalex_only")
        ),
        "disagreements_would_invoke_once": all(
            p.get("needs_judge") or p.get("skipped_duplicate") or p.get("judge_called")
            for p in report["papers"]
            if p.get("compare_status") == "disagreement"
        ),
        "paid_calls_this_run": paid_calls,
        "under_spend_cap": actual_cost <= args.spend_cap_usd,
        "idempotent_rerun": all(
            i.get("skipped_duplicate") and i.get("no_new_rows") for i in (report.get("idempotency") or [])
        )
        if not dry_run
        else None,
        "nsa_authority_excluded": any(
            174 in (ba.get("removed") or [])
            for ba in report["before_after"]
            if ba.get("paper_id") == 12243
        )
        if not dry_run
        else None,
    }

    Path(args.output).parent.mkdir(parents=True, exist_ok=True)
    Path(args.output).write_text(json.dumps(report, indent=2, default=str))
    summary_keys = [
        k
        for k in report
        if k
        not in (
            "papers",
            "before_after",
            "judge_decisions",
            "idempotency",
            "examples",
        )
    ]
    print(json.dumps({k: report[k] for k in summary_keys}, indent=2, default=str))
    print("--- judge_decisions ---")
    print(json.dumps(report["judge_decisions"], indent=2, default=str))
    print("--- before_after (judged only) ---")
    print(
        json.dumps(
            [b for b in report["before_after"] if b.get("decision") in
             ("HTML", "OPENALEX", "BOTH", "UNCERTAIN") or b.get("rejected_ids")],
            indent=2,
            default=str,
        )
    )
    print(f"wrote {args.output}")
    if dry_run:
        print(
            f"\nDRY-RUN complete: {judge_needed} judge calls proposed, "
            f"est. ${total_est_cost:.4f}. No paid LLM calls made."
        )
    else:
        print(
            f"\nEXECUTE complete: paid_calls={paid_calls}, "
            f"actual_cost=${actual_cost:.4f} (cap ${args.spend_cap_usd})."
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
