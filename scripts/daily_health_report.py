#!/usr/bin/env python3
"""Daily proof-of-life email: did the pipeline run, what happened, what needs attention.

Runs as its own cron job, separate from the pipeline, so a crashed or missing
pipeline run still produces an email. Read-only against the database. Plain
text, subject carries the verdict ([OK] / [ATTENTION] / [ERROR]).

If any check throws, that check is reported as failed; if the report itself
cannot be built, an [ERROR] email with the traceback is sent instead. Every
report is also written to reports/health/<date>.txt.

Config (.env): SES_FROM, ALERT_RECIPIENTS (comma-separated), SES_REGION
(default AWS_DEFAULT_REGION or ap-south-1), DAILY_SPEND_CAP (default 3),
MONTHLY_SPEND_CAP (default 50). SES credentials come from the EC2 instance
role, never from AWS_* keys in the environment.

  PYTHONPATH=src python scripts/daily_health_report.py --dry-run
  PYTHONPATH=src python scripts/daily_health_report.py            # send
"""

from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import sys
import tempfile
import traceback
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Callable
from zoneinfo import ZoneInfo

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

IST = ZoneInfo("Asia/Kolkata")
HEALTH_DIR = ROOT / "reports" / "health"
STATUS_DIR = ROOT / "reports" / "run_status"
DAILY_SPEND_CAP = float(os.getenv("DAILY_SPEND_CAP", "3"))
MONTHLY_SPEND_CAP = float(os.getenv("MONTHLY_SPEND_CAP", "50"))
LAST_RUN_MAX_HOURS = float(os.getenv("HEALTH_LAST_RUN_MAX_HOURS", "24"))
STAGE_FAILURE_MAX_PCT = float(os.getenv("HEALTH_STAGE_FAILURE_MAX_PCT", "5"))
STUCK_RUN_HOURS = float(os.getenv("HEALTH_STUCK_RUN_HOURS", "1"))
OOV_MAX_PCT = float(os.getenv("HEALTH_OOV_MAX_PCT", "2"))
FRESHNESS_MAX_DAYS = int(os.getenv("HEALTH_FRESHNESS_MAX_DAYS", "3"))
KEY_TABLES = (
    "papers", "pipeline_runs", "stage_runs", "external_requests", "llm_requests",
    "paper_classification_results", "paper_intelligence_current", "paper_author_affiliations",
    "paper_hf_signals", "quality_attempts", "ingest_checkpoints",
)
WRAPPER_RUNS = ("paper_intelligence.pipeline_detached", "paper_intelligence.backlog_chain")


@dataclass
class Check:
    name: str
    ok: bool
    detail: str = ""
    attention: str = ""


# ---------------------------------------------------------------- facts


def last_pipeline_run(conn) -> dict[str, Any] | None:
    row = conn.execute(
        """
        SELECT run_id::text, status, started_at, ended_at, metadata
        FROM paper_intelligence.pipeline_runs
        WHERE pipeline_name = 'paper_intelligence.pipeline_detached'
        ORDER BY started_at DESC LIMIT 1
        """
    ).fetchone()
    if not row:
        return None
    run = dict(row)
    args = (run["metadata"] or {}).get("args") or []
    run["date_from"] = args[args.index("--from") + 1] if "--from" in args else None
    run["date_until"] = args[args.index("--until") + 1] if "--until" in args else None
    return run


def stage_runs(conn, run: dict[str, Any]) -> list[dict[str, Any]]:
    rows = conn.execute(
        """
        SELECT run_id::text, pipeline_name, status, items_input, items_succeeded, items_failed,
               items_skipped, metadata, started_at, ended_at
        FROM paper_intelligence.pipeline_runs
        WHERE started_at >= %s AND started_at <= coalesce(%s, now())
          AND pipeline_name <> ALL(%s)
          AND coalesce(metadata->>'date_from', metadata->>'start', metadata->'window'->>0, %s) = %s
        ORDER BY started_at
        """,
        (run["started_at"], run["ended_at"], list(WRAPPER_RUNS), run["date_from"], run["date_from"]),
    ).fetchall()
    return [dict(r) for r in rows]


def _pid_alive(pid: Any) -> bool:
    try:
        os.kill(int(pid), 0)
    except (TypeError, ValueError, ProcessLookupError):
        return False
    except PermissionError:
        return True
    return True


def live_wrapper_runs(conn) -> dict[str, datetime]:
    """Wrapper runs (detached pipeline / backlog chain) whose supervisor process is alive."""
    live: dict[str, datetime] = {}
    for path in list(STATUS_DIR.glob("pipeline_*.json")) + list(STATUS_DIR.glob("backlog_*.json")):
        try:
            status = json.loads(path.read_text())
        except (OSError, ValueError):
            continue
        if status.get("state") in ("running", "launching") and _pid_alive(status.get("supervisor_pid")):
            live[str(status.get("run_id"))] = None
    if live:
        for row in conn.execute(
            "SELECT run_id::text, started_at FROM paper_intelligence.pipeline_runs WHERE run_id::text = ANY(%s)",
            (list(live),),
        ).fetchall():
            live[row["run_id"]] = row["started_at"]
    return {k: v for k, v in live.items() if v is not None}


def _belongs_to_live_run(row: dict[str, Any], live: dict[str, datetime]) -> bool:
    if row["run_id"] in live:
        return True
    return row["pipeline_name"] not in WRAPPER_RUNS and any(row["started_at"] >= t for t in live.values())


def spend(conn, since: datetime) -> float:
    row = conn.execute(
        """
        SELECT coalesce(sum(coalesce(actual_cost, estimated_cost)), 0) AS usd
        FROM paper_intelligence.llm_requests WHERE created_at >= %s
        """,
        (since,),
    ).fetchone()
    return float(row["usd"])


def run_audit(date_from: str, date_until: str) -> dict[str, Any]:
    with tempfile.TemporaryDirectory() as tmp:
        js = Path(tmp) / "audit.json"
        done = subprocess.run(
            [sys.executable, str(ROOT / "scripts" / "audit_window_completeness.py"), "--from", date_from,
             "--until", date_until, "--out", str(Path(tmp) / "audit.md"), "--json", str(js)],
            cwd=str(ROOT), capture_output=True, text=True, timeout=900,
            env={**os.environ, "PYTHONPATH": str(SRC)},
        )
        data = json.loads(js.read_text()) if js.is_file() else {}
    return {"exit_code": done.returncode, **data, "tail": (done.stdout + done.stderr)[-600:]}


def run_unit_tests() -> dict[str, Any]:
    done = subprocess.run(
        [sys.executable, "-m", "pytest", "-q", "-p", "no:cacheprovider", "tests/unit"],
        cwd=str(ROOT), capture_output=True, text=True, timeout=900,
        env={**os.environ, "PYTHONPATH": str(SRC)},
    )
    out = done.stdout + done.stderr
    counts = {k: int(v) for v, k in re.findall(r"(\d+) (passed|failed|errors?)", out)}
    return {"exit_code": done.returncode, "passed": counts.get("passed", 0),
            "failed": counts.get("failed", 0) + counts.get("error", 0) + counts.get("errors", 0),
            "tail": out[-600:]}


def gather(conn, *, now: datetime, with_tests: bool, with_audit: bool) -> dict[str, Any]:
    local = now.astimezone(IST)
    day_start = local.replace(hour=0, minute=0, second=0, microsecond=0)
    facts: dict[str, Any] = {"now": now, "local": local}
    facts["run"] = run = last_pipeline_run(conn)
    facts["stages"] = stage_runs(conn, run) if run and run["date_from"] else []
    facts["newest_paper"] = conn.execute(
        "SELECT max(published_at) AS d FROM paper_intelligence.papers").fetchone()["d"]
    facts["spend_today"] = spend(conn, day_start)
    facts["spend_month"] = spend(conn, day_start.replace(day=1))
    facts["stuck"] = [dict(r) for r in conn.execute(
        """
        SELECT run_id::text, pipeline_name, started_at FROM paper_intelligence.pipeline_runs
        WHERE status = 'running' AND started_at < now() - make_interval(secs => %s)
        ORDER BY started_at
        """,
        (STUCK_RUN_HOURS * 3600,),
    ).fetchall()]
    live = live_wrapper_runs(conn)
    facts["stuck"] = [r for r in facts["stuck"] if not _belongs_to_live_run(r, live)]
    present = {r["table_name"] for r in conn.execute(
        "SELECT table_name FROM information_schema.tables WHERE table_schema = 'paper_intelligence'"
    ).fetchall()}
    facts["missing_tables"] = [t for t in KEY_TABLES if t not in present]
    scored = any(s["pipeline_name"].endswith("quality") for s in facts["stages"])
    facts["audit"] = run_audit(run["date_from"], run["date_until"]) if with_audit and scored else None
    facts["tests"] = run_unit_tests() if with_tests else None
    return facts


# ---------------------------------------------------------------- checks


def _short(name: str) -> str:
    return name.replace("paper_intelligence.", "")


def _failure_pct(stage: dict[str, Any]) -> float:
    total = stage["items_input"] or 0
    return 100.0 * (stage["items_failed"] or 0) / total if total else 0.0


def build_checks(f: dict[str, Any]) -> list[Check]:
    run, now = f["run"], f["now"]

    def schema() -> Check:
        missing = f["missing_tables"]
        return Check("schema: key tables present", not missing,
                     f"missing: {', '.join(missing)}" if missing else "",
                     f"schema: tables missing ({', '.join(missing)}) — a migration was not applied" if missing else "")

    def ran_recently() -> Check:
        if not run:
            return Check("pipeline ran in last 24h", False, "no pipeline run recorded",
                         "no pipeline run has ever been recorded")
        age_h = (now - run["started_at"]).total_seconds() / 3600
        ok = age_h <= LAST_RUN_MAX_HOURS
        return Check(f"pipeline ran in last {LAST_RUN_MAX_HOURS:g}h", ok, f"last start {age_h:.1f}h ago",
                     "" if ok else f"pipeline has not started for {age_h:.0f}h — cron or the box may be down")

    def run_closed_ok() -> Check:
        if not run:
            return Check("last run succeeded", False, "no run")
        ok = run["status"] == "succeeded"
        stops = (run["metadata"] or {}).get("stops") or []
        return Check("last run succeeded", ok, f"status={run['status']}",
                     "" if ok else f"last run closed {run['status']}" + (f": {stops[0][:200]}" if stops else ""))

    def freshness() -> Check:
        newest = f["newest_paper"]
        if newest is None:
            return Check("newest paper within limit", False, "no papers", "papers table is empty")
        allowed = FRESHNESS_MAX_DAYS + (1 if f["local"].weekday() in (6, 0) else 0)
        age = (f["local"].date() - newest.astimezone(IST).date()).days
        ok = age <= allowed
        return Check(f"newest paper within {allowed} days", ok, f"newest {newest.date()} ({age}d old)",
                     "" if ok else f"newest paper is {age} days old — the pull ran but fetched nothing new")

    def stage_failures() -> Check:
        bad = [s for s in f["stages"] if _failure_pct(s) > STAGE_FAILURE_MAX_PCT or s["status"] not in ("succeeded",)]
        detail = "; ".join(
            f"{_short(s['pipeline_name'])} {s['status']} {s['items_failed']}/{s['items_input']} failed" for s in bad)
        attention = "; ".join(
            f"{_short(s['pipeline_name'])}: {s['items_failed']} of {s['items_input']} failed ({s['status']})"
            + (f" — {(s['metadata'] or {}).get('stop_reason')}" if (s["metadata"] or {}).get("stop_reason") else "")
            for s in bad)
        return Check(f"no stage failure rate above {STAGE_FAILURE_MAX_PCT:g}%", not bad, detail, attention)

    def stuck() -> Check:
        rows = f["stuck"]
        if not rows:
            return Check(f"no runs stuck in RUNNING over {STUCK_RUN_HOURS:g}h", True)
        names = sorted({_short(r["pipeline_name"]) for r in rows})
        shown = ", ".join(names[:5]) + (f" +{len(names) - 5} more" if len(names) > 5 else "")
        span = f"oldest {rows[0]['started_at']:%d %b}, newest {rows[-1]['started_at']:%d %b}"
        return Check(f"no runs stuck in RUNNING over {STUCK_RUN_HOURS:g}h", False, f"{len(rows)} runs ({span})",
                     f"{len(rows)} run(s) stuck in RUNNING ({span}): {shown}")

    def daily_spend() -> Check:
        ok = f["spend_today"] <= DAILY_SPEND_CAP
        return Check(f"daily spend under cap (${DAILY_SPEND_CAP:g})", ok, f"${f['spend_today']:.2f}",
                     "" if ok else f"today's spend ${f['spend_today']:.2f} is over the ${DAILY_SPEND_CAP:g} cap")

    def monthly_spend() -> Check:
        ok = f["spend_month"] <= MONTHLY_SPEND_CAP
        return Check(f"month-to-date spend under cap (${MONTHLY_SPEND_CAP:g})", ok, f"${f['spend_month']:.2f}",
                     "" if ok else f"month-to-date ${f['spend_month']:.2f} is over the ${MONTHLY_SPEND_CAP:g} cap")

    def oov() -> Check:
        ad = [s for s in f["stages"] if s["pipeline_name"].endswith("audience_domain")]
        if not ad:
            return Check(f"classify out-of-vocabulary rate under {OOV_MAX_PCT:g}%", True, "no classify run in last run")
        s = ad[-1]
        count = (s["metadata"] or {}).get("oov_papers")
        if count is None:
            return Check(f"classify out-of-vocabulary rate under {OOV_MAX_PCT:g}%", False,
                         "not recorded by this run", "classify out-of-vocabulary count was not recorded")
        pct = 100.0 * count / max(1, s["items_succeeded"] or 0)
        ok = pct <= OOV_MAX_PCT
        return Check(f"classify out-of-vocabulary rate under {OOV_MAX_PCT:g}%", ok, f"{count} papers ({pct:.1f}%)",
                     "" if ok else f"classify: {count} papers ({pct:.1f}%) got labels outside the vocabulary")

    def audit() -> Check:
        a = f["audit"]
        if a is None:
            return Check("window audit: complete enough to publish", True, "skipped (no quality stage in last run)")
        ok = bool(a.get("publishable")) and a["exit_code"] == 0
        reasons = a.get("blocking_reasons") or []
        return Check("window audit: complete enough to publish", ok,
                     f"prose missing {a.get('prose_missing')}" if ok else "; ".join(reasons)[:200],
                     "" if ok else "audit not publishable: " + ("; ".join(reasons) or a["tail"][-200:]))

    def tests() -> Check:
        t = f["tests"]
        if t is None:
            return Check("unit tests", True, "skipped")
        ok = t["exit_code"] == 0 and t["failed"] == 0 and t["passed"] > 0
        return Check(f"unit tests: {t['passed']} passed" + (f", {t['failed']} failed" if t["failed"] else ""), ok, "",
                     "" if ok else f"unit tests failing ({t['failed']} failed)")

    checks = []
    for fn in (schema, ran_recently, run_closed_ok, freshness, stage_failures, stuck, daily_spend, monthly_spend,
               oov, audit, tests):
        checks.append(_safe(fn))
    return checks


def _safe(fn: Callable[[], Check]) -> Check:
    try:
        return fn()
    except Exception as exc:  # noqa: BLE001
        return Check(f"{fn.__name__} (check errored)", False, f"{type(exc).__name__}: {exc}"[:200],
                     f"health check '{fn.__name__}' itself failed: {type(exc).__name__}: {exc}"[:300])


# ---------------------------------------------------------------- render


def _stage_line(s: dict[str, Any]) -> str:
    m = s["metadata"] or {}
    name = _short(s["pipeline_name"])
    if name == "ingest":
        text = f"{m.get('records_seen', s['items_input'])} seen → {m.get('records_new', s['items_succeeded'])} new, " \
               f"{m.get('records_dupe', s['items_skipped'])} already had"
    elif name == "relevance":
        text = f"{m.get('candidates', s['items_input'])} in → {m.get('kept')} relevant, {m.get('rejected')} rejected"
    elif name.startswith("affiliation"):
        text = f"{s['items_input']} → {s['items_succeeded']} ok, {s['items_failed']} failed, " \
               f"{s['items_skipped']} unresolved"
    else:
        text = f"{s['items_input']} → {s['items_succeeded']} ok, {s['items_failed']} failed"
    cost = m.get("cost_usd")
    if cost:
        text += f"  (${float(cost):.2f})"
    if s["status"] != "succeeded":
        text += f"  [{s['status']}]"
    return f"  {name:<18} {text}"


def render(f: dict[str, Any], checks: list[Check]) -> tuple[str, str]:
    run, local, stages = f["run"], f["local"], f["stages"]
    failed_checks = [c for c in checks if not c.ok]
    failures = sum(s["items_failed"] or 0 for s in stages)
    ingest = next((s for s in stages if _short(s["pipeline_name"]) == "ingest"), None)
    new_papers = (ingest["metadata"] or {}).get("records_new") if ingest else None
    day = local.strftime("%d %b")
    headline = f"{new_papers} new papers, {failures} failures" if new_papers is not None else \
        f"window {run['date_from']}→{run['date_until']}, {failures} failures" if run else "no pipeline run"
    if failed_checks:
        subject = f"[ATTENTION] PaperIntelligence — {day} — {failed_checks[0].attention or failed_checks[0].name}"[:150]
    else:
        subject = f"[OK] PaperIntelligence — {day} — {headline}"
    lines: list[str] = []
    if failed_checks:
        lines += ["NEEDS ATTENTION"] + [f"  {c.attention or c.name + ': ' + c.detail}" for c in failed_checks] + [""]
    lines.append(f"PIPELINE STATUS: {'ATTENTION' if failed_checks else 'OK'}")
    if run:
        age_h = (f["now"] - run["started_at"]).total_seconds() / 3600
        ended = f"{run['ended_at']:%Y-%m-%d %H:%M} UTC" if run["ended_at"] else "still running"
        lines += [f"Last run: {run['started_at']:%Y-%m-%d %H:%M} UTC ({age_h:.0f}h ago), {run['status']}, ended {ended}"]
    else:
        lines.append("Last run: none recorded")
    newest = f["newest_paper"]
    lines += ["", "PULL",
              f"  Window             {run['date_from']} → {run['date_until']}" if run else "  Window             —",
              f"  Papers ingested    {new_papers if new_papers is not None else '— (no ingest stage in last run)'}",
              f"  Newest paper       {newest.date() if newest else '—'}"]
    lines += ["", "PROCESSING"] + ([_stage_line(s) for s in stages] or ["  (no stage runs found for the last run)"])
    lines += ["", "SPEND",
              f"  Today (IST)        ${f['spend_today']:.2f}   (cap ${DAILY_SPEND_CAP:g})",
              f"  Month to date      ${f['spend_month']:.2f}   (cap ${MONTHLY_SPEND_CAP:g})"]
    passed = sum(1 for c in checks if c.ok)
    lines += ["", f"CHECKS                          {passed} passed, {len(checks) - passed} failed"]
    for c in checks:
        lines.append(f"  {'✓' if c.ok else '✗'} {c.name}" + (f" — {c.detail}" if c.detail else ""))
    lines += ["", "Nothing needs attention." if not failed_checks else "See NEEDS ATTENTION above.",
              "", "No email by 08:00 IST means the box or this health check is down — treat silence as urgent."]
    return subject, "\n".join(lines) + "\n"


def render_crash(exc: BaseException, now: datetime) -> tuple[str, str]:
    day = now.astimezone(IST).strftime("%d %b")
    subject = f"[ERROR] PaperIntelligence — {day} — health check crashed: {type(exc).__name__}"[:150]
    body = ("HEALTH CHECK CRASHED\n\nThe health check could not build its report, so pipeline status is UNKNOWN.\n"
            "Treat this as urgent: check the box and the database.\n\n"
            + "".join(traceback.format_exception(exc))[-3000:])
    return subject, body


# ---------------------------------------------------------------- send


def send_ses(subject: str, body: str) -> str:
    import boto3
    from botocore.credentials import InstanceMetadataFetcher, InstanceMetadataProvider

    sender = os.environ["SES_FROM"]
    recipients = [r.strip() for r in os.environ["ALERT_RECIPIENTS"].split(",") if r.strip()]
    creds = InstanceMetadataProvider(
        iam_role_fetcher=InstanceMetadataFetcher(timeout=3, num_attempts=3)).load()
    if creds is None:
        raise RuntimeError("no EC2 instance-role credentials available for SES")
    frozen = creds.get_frozen_credentials()
    client = boto3.client(
        "sesv2", region_name=os.getenv("SES_REGION") or os.getenv("AWS_DEFAULT_REGION") or "ap-south-1",
        aws_access_key_id=frozen.access_key, aws_secret_access_key=frozen.secret_key,
        aws_session_token=frozen.token,
    )
    resp = client.send_email(
        FromEmailAddress=sender,
        Destination={"ToAddresses": recipients},
        Content={"Simple": {"Subject": {"Data": subject, "Charset": "UTF-8"},
                            "Body": {"Text": {"Data": body, "Charset": "UTF-8"}}}},
    )
    return resp.get("MessageId", "")


def build_report(*, with_tests: bool, with_audit: bool, now: datetime | None = None) -> tuple[str, str]:
    now = now or datetime.now(timezone.utc)
    try:
        from paper_intelligence.db import connect

        with connect() as conn:
            facts = gather(conn, now=now, with_tests=with_tests, with_audit=with_audit)
        return render(facts, build_checks(facts))
    except Exception as exc:  # noqa: BLE001
        return render_crash(exc, now)


def main(argv: list[str]) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--dry-run", action="store_true", help="print the email instead of sending it")
    ap.add_argument("--skip-tests", action="store_true")
    ap.add_argument("--skip-audit", action="store_true")
    args = ap.parse_args(argv)
    subject, body = build_report(with_tests=not args.skip_tests, with_audit=not args.skip_audit)
    HEALTH_DIR.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now(IST).strftime("%Y-%m-%d_%H%M")
    (HEALTH_DIR / f"{stamp}.txt").write_text(f"Subject: {subject}\n\n{body}", encoding="utf-8")
    if args.dry_run:
        print(f"Subject: {subject}\n\n{body}")
        return 0
    try:
        message_id = send_ses(subject, body)
    except Exception as exc:  # noqa: BLE001
        print(f"SEND FAILED: {type(exc).__name__}: {exc}\nSubject: {subject}\n\n{body}", file=sys.stderr)
        return 1
    print(f"sent {message_id}: {subject}")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
