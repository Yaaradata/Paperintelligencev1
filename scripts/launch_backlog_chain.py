#!/usr/bin/env python3
"""Run backlog weeks one after another from one detached supervisor, with gates.

Parent: inserts a ``paper_intelligence.backlog_chain`` pipeline_runs row,
writes reports/run_status/backlog_<run_id>.json, starts the detached
supervisor, prints run_id / status file / log, and exits.

Supervisor, for each week in order (never in parallel):
  1. Key credit (OpenRouter /api/v1/key limit_remaining) >= --min-key-credit.
  2. v1 completeness: reports/ingest_status/v1_completeness_<from>_<until>.json
     must say complete (OAI v1 ids all in the DB; OAI is the ingest source, so
     the check is not independent). Produced beforehand by one harvest:
     check_v1_window_completeness.py --split. No ingest runs per week.
  3. Dry run: per-stage projection and papers already scored (reused). Stop if
     the projection exceeds --max-week-projection or credit < projection + $1.
  4. Week run: its own pipeline_detached run record is written before the
     first request (launch_pipeline_run.supervise); cap =
     min(--per-week-cap, --cumulative-stop - spent, credit - --min-key-credit).
  5. Only when the week run closed succeeded AND audit_window_completeness.py
     prints YES does the next week start.
Stops the whole backlog when cumulative actual spend reaches --cumulative-stop
or key credit drops below --min-key-credit.

  PYTHONPATH=src python scripts/launch_backlog_chain.py \\
      --weeks 2026-08-01:2026-08-07,2026-08-08:2026-08-14,2026-08-15:2026-08-21,2026-08-22:2026-08-24
"""

from __future__ import annotations

import argparse
import importlib.util
import json
import os
import re
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import requests

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from paper_intelligence.db import connect  # noqa: E402
from paper_intelligence.observability import finish_pipeline_run, start_pipeline_run  # noqa: E402

STATUS_DIR = ROOT / "reports" / "run_status"
INGEST_STATUS_DIR = ROOT / "reports" / "ingest_status"
WEEK_STAGES = (
    "relevance,normalize_authors,screen,affiliation_fast,audience_domain,quality,"
    "affiliation_deep,hf_signals,adjudication,reports"
)
WEEK_ENV = {
    "QUALITY_ENGINE": "jev_glm",
    "SCREEN_MODEL": "z-ai/glm-5.3-flash",
    "CLASSIFY_MODEL": "z-ai/glm-5.3-flash",
}
PROJECTION_RE = re.compile(r"^PROJECTION (\w+): (\d+) papers.*~\$([0-9.]+)\s*$")
BUDGET_RE = re.compile(r"budget: projected=\$([0-9.]+) actual=\$([0-9.]+)")
REUSE_SQL = """
WITH win AS (
    SELECT paper_id FROM paper_intelligence.papers
    WHERE published_at >= %(f)s::timestamptz AND published_at < (%(u)s::timestamptz + interval '1 day')
), q AS (
    SELECT DISTINCT ON (r.content_item_id) r.content_item_id, r.result_json
    FROM paper_intelligence.paper_classification_results r JOIN win ON win.paper_id = r.content_item_id
    WHERE r.task_type = 'quality' ORDER BY r.content_item_id, r.created_at DESC
)
SELECT (SELECT count(*) FROM win) AS window_papers,
       count(*) FILTER (WHERE result_json->>'quality_engine' = 'jev_glm') AS scored_jev_glm,
       count(*) FILTER (WHERE result_json->>'quality_engine' = 'jev_glm'
                        AND NULLIF(btrim(result_json->>'so_what'), '') IS NOT NULL) AS scored_with_prose,
       count(*) AS scored_any_engine
FROM q
"""
CHILD_RUNS_SQL = """
SELECT run_id::text, pipeline_name, status, items_input, items_succeeded, items_failed, items_skipped
FROM paper_intelligence.pipeline_runs
WHERE started_at >= %s AND started_at <= %s AND run_id <> ALL(%s::uuid[])
ORDER BY started_at
"""
CHILD_COST_SQL = """
SELECT coalesce(sum(coalesce(l.actual_cost, l.estimated_cost)), 0) AS cost, count(*) AS calls
FROM paper_intelligence.external_requests e JOIN paper_intelligence.llm_requests l USING (request_id)
WHERE e.run_id = ANY(%s::uuid[])
"""


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _write(path: Path, data: dict) -> None:
    data["updated_at"] = _now()
    tmp = path.with_suffix(".tmp")
    tmp.write_text(json.dumps(data, indent=2, default=str))
    tmp.replace(path)


def parse_weeks(value: str) -> list[tuple[str, str]]:
    weeks = []
    for part in value.split(","):
        start, end = part.split(":")
        weeks.append((start, end))
    return weeks


def key_credit() -> float | None:
    resp = requests.get(
        "https://openrouter.ai/api/v1/key",
        headers={"Authorization": f"Bearer {os.environ['OPENROUTER_API_KEY']}"},
        timeout=20,
    )
    resp.raise_for_status()
    remaining = (resp.json().get("data") or {}).get("limit_remaining")
    return float(remaining) if remaining is not None else None


def completeness(week: tuple[str, str]) -> dict[str, Any]:
    path = INGEST_STATUS_DIR / f"v1_completeness_{week[0]}_{week[1]}.json"
    if not path.is_file():
        return {"complete": False, "error": f"missing {path.name}"}
    data = json.loads(path.read_text())
    return {k: data.get(k) for k in (
        "oai_v1_count", "db_count", "missing_from_db", "in_db_not_in_oai", "complete",
        "checked_at", "reference_source")}


def parse_projection(output: str) -> dict[str, Any]:
    """Per-stage projection and pipeline total from the pre-run projection block.

    A dry run then walks every stage and prints more budget lines, so only the
    part before the first ``=== pipeline stage:`` header is read.
    """
    head = output.split("=== pipeline stage:", 1)[0]
    stages: dict[str, dict[str, Any]] = {}
    total = None
    for line in head.splitlines():
        m = PROJECTION_RE.match(line)
        if m:
            stages[m.group(1)] = {"papers": int(m.group(2)), "usd": float(m.group(3))}
        b = BUDGET_RE.search(line)
        if b:
            total = float(b.group(1))
    return {"stages": stages, "total_usd": total}


def dry_run(week: tuple[str, str], env: dict[str, str], cap: float) -> dict[str, Any]:
    cmd = [sys.executable, "-u", str(ROOT / "scripts" / "run_pipeline.py"), "--from", week[0],
           "--until", week[1], "--stages", WEEK_STAGES, "--dry-run", "--max-cost-usd", str(cap)]
    done = subprocess.run(cmd, cwd=str(ROOT), env=env, capture_output=True, text=True, timeout=1800)
    out = done.stdout + done.stderr
    return {"exit_code": done.returncode, **parse_projection(out), "tail": out[-1500:]}


def reuse_counts(week: tuple[str, str]) -> dict[str, int]:
    with connect() as conn:
        row = conn.execute(REUSE_SQL, {"f": week[0], "u": week[1]}).fetchone()
    return dict(row)


def run_week(chain_run_id: str, week: tuple[str, str], env: dict[str, str], cap: float) -> dict[str, Any]:
    spec = importlib.util.spec_from_file_location("launch_pipeline_run", ROOT / "scripts" / "launch_pipeline_run.py")
    launcher = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(launcher)
    args = ["--from", week[0], "--until", week[1], "--stages", WEEK_STAGES, "--allow-paid",
            "--max-cost-usd", f"{cap:.4f}"]
    env_flags = {k: env[k] for k in (*WEEK_ENV, *launcher.ENV_KEYS) if k in env}
    started = datetime.now(timezone.utc)
    with connect() as conn:
        run_id = start_pipeline_run(
            conn, pipeline_name="paper_intelligence.pipeline_detached",
            metadata={"args": args, "env": env_flags, "chain_run_id": chain_run_id},
        )
        conn.commit()
    status_path = STATUS_DIR / f"pipeline_{run_id}.json"
    _write(status_path, {"run_id": run_id, "state": "running", "args": args, "env": env_flags,
                         "chain_run_id": chain_run_id, "started_at": _now()})
    print(f"week {week[0]}..{week[1]} run_id={run_id} cap=${cap:.4f}", flush=True)
    saved = dict(os.environ)
    os.environ.clear()
    os.environ.update(env)
    try:
        code = launcher.supervise(run_id, args)
    finally:
        os.environ.clear()
        os.environ.update(saved)
    ended = datetime.now(timezone.utc)
    status = json.loads(status_path.read_text())
    budget = BUDGET_RE.search(status.get("last_budget_line") or "")
    with connect() as conn:
        children = [dict(r) for r in conn.execute(
            CHILD_RUNS_SQL, (started, ended, [run_id, chain_run_id])).fetchall()]
        child_ids = [c["run_id"] for c in children]
        db_cost = dict(conn.execute(CHILD_COST_SQL, (child_ids,)).fetchone())
    return {
        "run_id": run_id,
        "exit_code": code,
        "state": status.get("state"),
        "started_at": started.isoformat(),
        "ended_at": ended.isoformat(),
        "cap_usd": round(cap, 4),
        "pipeline_actual_usd": float(budget.group(2)) if budget else None,
        "db_llm_cost_usd": round(float(db_cost["cost"]), 6),
        "db_llm_calls": int(db_cost["calls"]),
        "stages": children,
        "stops": status.get("stops"),
    }


def audit(chain_run_id: str, week: tuple[str, str], env: dict[str, str]) -> dict[str, Any]:
    stem = STATUS_DIR / f"backlog_{chain_run_id}_audit_{week[0]}_{week[1]}"
    cmd = [sys.executable, str(ROOT / "scripts" / "audit_window_completeness.py"), "--from", week[0],
           "--until", week[1], "--out", f"{stem}.md", "--json", f"{stem}.json"]
    done = subprocess.run(cmd, cwd=str(ROOT), env=env, capture_output=True, text=True, timeout=1800)
    out = done.stdout + done.stderr
    defects: dict[str, Any] = {}
    if Path(f"{stem}.json").is_file():
        data = json.loads(Path(f"{stem}.json").read_text())
        defects = {k: data.get(k) for k in (
            "publishable", "totals", "prose_missing", "prose_missing_rate", "blocking_reasons", "defects",
        ) if k in data}
    return {
        "exit_code": done.returncode,
        "yes": done.returncode == 0 and "Complete enough to publish: YES" in out,
        "report": f"{stem}.md",
        **defects,
        "tail": out[-2000:],
    }


def supervise(chain_run_id: str) -> int:
    status_path = STATUS_DIR / f"backlog_{chain_run_id}.json"
    status = json.loads(status_path.read_text())
    cfg = status["config"]
    env = {**os.environ, **WEEK_ENV, **cfg["extra_env"], "PYTHONPATH": str(SRC), "PYTHONUNBUFFERED": "1"}
    spent = 0.0
    stop_reason = None
    status.update(state="running", supervisor_pid=os.getpid(), weeks=[])
    _write(status_path, status)

    def stop(reason: str) -> None:
        nonlocal stop_reason
        stop_reason = reason
        print(f"BACKLOG STOP: {reason}", flush=True)

    for week in [tuple(w) for w in cfg["weeks"]]:
        rec: dict[str, Any] = {"week": list(week)}
        status["weeks"].append(rec)
        _write(status_path, status)
        print(f"\n##### week {week[0]}..{week[1]} (spent so far ${spent:.4f}) #####", flush=True)
        if spent >= cfg["cumulative_stop"]:
            stop(f"cumulative spend ${spent:.4f} reached ${cfg['cumulative_stop']}")
            break
        try:
            credit = key_credit()
        except Exception as exc:  # noqa: BLE001
            stop(f"could not read key credit: {exc}")
            break
        rec["key_credit_before"] = credit
        if credit is None or credit < cfg["min_key_credit"]:
            stop(f"key credit {credit} below ${cfg['min_key_credit']}")
            break
        rec["completeness"] = completeness(week)
        if not rec["completeness"].get("complete"):
            stop(f"{week[0]}..{week[1]} v1 completeness not met: {rec['completeness']}")
            break
        rec["reuse"] = reuse_counts(week)
        rec["dry_run"] = dry_run(week, env, cfg["per_week_cap"])
        _write(status_path, status)
        projected = rec["dry_run"]["total_usd"]
        print(f"dry-run: {json.dumps({k: v for k, v in rec['dry_run'].items() if k != 'tail'})}", flush=True)
        print(f"reuse: {rec['reuse']}", flush=True)
        if rec["dry_run"]["exit_code"] != 0 or projected is None:
            stop(f"dry run failed (exit {rec['dry_run']['exit_code']})")
            break
        if projected > cfg["max_week_projection"]:
            stop(f"projection ${projected:.4f} exceeds ${cfg['max_week_projection']}")
            break
        if credit < projected + 1.0:
            stop(f"key credit ${credit:.2f} below projection ${projected:.4f} + $1")
            break
        cap = min(cfg["per_week_cap"], cfg["cumulative_stop"] - spent, credit - cfg["min_key_credit"])
        if cap < projected:
            stop(f"remaining allowance ${cap:.4f} below projection ${projected:.4f}")
            break
        rec["run"] = run_week(chain_run_id, week, env, cap)
        week_cost = max(rec["run"]["pipeline_actual_usd"] or 0.0, rec["run"]["db_llm_cost_usd"])
        spent += week_cost
        rec["actual_usd"] = round(week_cost, 6)
        status["spent_usd"] = round(spent, 6)
        _write(status_path, status)
        if rec["run"]["state"] != "succeeded":
            stop(f"week run {rec['run']['run_id']} closed {rec['run']['state']} (exit {rec['run']['exit_code']})")
            break
        rec["audit"] = audit(chain_run_id, week, env)
        _write(status_path, status)
        print(f"audit: exit={rec['audit']['exit_code']} yes={rec['audit']['yes']}", flush=True)
        if not rec["audit"]["yes"]:
            stop(f"audit for {week[0]}..{week[1]} did not print YES; see {rec['audit']['report']}")
            break

    done_weeks = sum(1 for w in status["weeks"] if (w.get("audit") or {}).get("yes"))
    final = "succeeded" if stop_reason is None else "partial"
    status.update(state=final, stop_reason=stop_reason, spent_usd=round(spent, 6),
                  weeks_completed=done_weeks, finished_at=_now())
    _write(status_path, status)
    with connect() as conn:
        finish_pipeline_run(conn, chain_run_id, status=final, items_input=len(cfg["weeks"]),
                            items_succeeded=done_weeks,
                            metadata={"spent_usd": round(spent, 6), "stop_reason": stop_reason,
                                      "status_file": str(status_path)})
        conn.commit()
    print(f"\nBACKLOG {final}: weeks_completed={done_weeks}/{len(cfg['weeks'])} spent=${spent:.4f} "
          f"stop_reason={stop_reason}", flush=True)
    return 0 if final == "succeeded" else 1


def launch(args: argparse.Namespace) -> int:
    STATUS_DIR.mkdir(parents=True, exist_ok=True)
    extra_env = dict(kv.split("=", 1) for kv in args.env)
    cfg = {
        "weeks": args.weeks,
        "per_week_cap": args.per_week_cap,
        "max_week_projection": args.max_week_projection,
        "cumulative_stop": args.cumulative_stop,
        "min_key_credit": args.min_key_credit,
        "stages": WEEK_STAGES,
        "week_env": WEEK_ENV,
        "extra_env": extra_env,
    }
    with connect() as conn:
        run_id = start_pipeline_run(conn, pipeline_name="paper_intelligence.backlog_chain", metadata=cfg)
        conn.commit()
    status_path = STATUS_DIR / f"backlog_{run_id}.json"
    log_path = STATUS_DIR / f"backlog_{run_id}.log"
    _write(status_path, {"run_id": run_id, "state": "launching", "config": cfg, "log": str(log_path),
                         "started_at": _now()})
    with open(log_path, "ab") as log:
        proc = subprocess.Popen(
            [sys.executable, "-u", str(Path(__file__).resolve()), "--supervise", run_id],
            cwd=str(ROOT), stdin=subprocess.DEVNULL, stdout=log, stderr=subprocess.STDOUT,
            start_new_session=True, env={**os.environ, "PYTHONPATH": str(SRC)},
        )
    print(f"run_id={run_id}")
    print(f"status_file={status_path}")
    print(f"log={log_path}")
    print(f"supervisor_pid={proc.pid}")
    return 0


def main(argv: list[str]) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--supervise")
    ap.add_argument("--weeks", type=parse_weeks)
    ap.add_argument("--per-week-cap", type=float, default=3.0)
    ap.add_argument("--max-week-projection", type=float, default=2.50)
    ap.add_argument("--cumulative-stop", type=float, default=7.0)
    ap.add_argument("--min-key-credit", type=float, default=2.0)
    ap.add_argument("--env", action="append", default=[], help="KEY=VALUE for every week run")
    args = ap.parse_args(argv)
    if args.supervise:
        return supervise(args.supervise)
    if not args.weeks:
        ap.error("--weeks is required")
    return launch(args)


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
