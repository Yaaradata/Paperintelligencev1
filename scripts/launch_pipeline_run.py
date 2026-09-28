#!/usr/bin/env python3
"""Launch run_pipeline.py detached, with a run record written first.

Parent: inserts a ``paper_intelligence.pipeline_detached`` pipeline_runs row
(before any API call), writes the status file, starts a detached supervisor,
prints run_id / status file / pid, and exits.

Supervisor (``--supervise``): runs run_pipeline.py with the given arguments,
tees output to the log, updates the status file on each stage change and
every 30 s, and closes the run record from the exit code (0 succeeded,
3 cancelled by runguard, else partial).

Usage:
  PYTHONPATH=src python scripts/launch_pipeline_run.py -- \\
      --from 2026-08-25 --until 2026-08-31 --allow-paid --max-cost-usd 4
"""

from __future__ import annotations

import json
import os
import re
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from paper_intelligence.db import connect  # noqa: E402
from paper_intelligence.observability import (  # noqa: E402
    finish_pipeline_run,
    start_pipeline_run,
)

STATUS_DIR = ROOT / "reports" / "run_status"
ENV_KEYS = ("QUALITY_ENGINE", "SCREEN_MODEL", "CLASSIFY_MODEL", "QUALITY_MODEL")
STAGE_RE = re.compile(r"^=== pipeline stage: (\S+) ===")
BUDGET_RE = re.compile(r"budget: projected=\$([0-9.]+) actual=\$([0-9.]+)")


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _write(path: Path, data: dict) -> None:
    data["updated_at"] = _now()
    tmp = path.with_suffix(".tmp")
    tmp.write_text(json.dumps(data, indent=2))
    tmp.replace(path)


def launch(pipeline_args: list[str]) -> int:
    STATUS_DIR.mkdir(parents=True, exist_ok=True)
    env_flags = {k: os.environ[k] for k in ENV_KEYS if k in os.environ}
    with connect() as conn:
        run_id = start_pipeline_run(
            conn,
            pipeline_name="paper_intelligence.pipeline_detached",
            metadata={"args": pipeline_args, "env": env_flags},
        )
        conn.commit()
    status_path = STATUS_DIR / f"pipeline_{run_id}.json"
    log_path = STATUS_DIR / f"pipeline_{run_id}.log"
    status = {
        "run_id": run_id,
        "state": "launching",
        "args": pipeline_args,
        "env": env_flags,
        "log": str(log_path),
        "started_at": _now(),
    }
    _write(status_path, status)
    with open(log_path, "ab") as log:
        proc = subprocess.Popen(
            [sys.executable, str(Path(__file__).resolve()), "--supervise", run_id, "--",
             *pipeline_args],
            cwd=str(ROOT),
            stdin=subprocess.DEVNULL,
            stdout=log,
            stderr=subprocess.STDOUT,
            start_new_session=True,
        )
    status.update(state="running", supervisor_pid=proc.pid)
    _write(status_path, status)
    print(f"run_id={run_id}")
    print(f"status_file={status_path}")
    print(f"log={log_path}")
    print(f"supervisor_pid={proc.pid}")
    return 0


def supervise(run_id: str, pipeline_args: list[str]) -> int:
    status_path = STATUS_DIR / f"pipeline_{run_id}.json"
    status = json.loads(status_path.read_text())
    cmd = [sys.executable, "-u", str(ROOT / "scripts" / "run_pipeline.py"), *pipeline_args]
    proc = subprocess.Popen(
        cmd, cwd=str(ROOT), stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True,
        env={**os.environ, "PYTHONUNBUFFERED": "1"},
    )
    status.update(pipeline_pid=proc.pid, stage=None, stages_done=[])
    _write(status_path, status)
    last_write = time.monotonic()
    assert proc.stdout is not None
    for line in proc.stdout:
        sys.stdout.write(line)
        sys.stdout.flush()
        m = STAGE_RE.match(line)
        if m:
            if status.get("stage"):
                status["stages_done"].append(status["stage"])
            status["stage"] = m.group(1)
            _write(status_path, status)
            last_write = time.monotonic()
        b = BUDGET_RE.search(line)
        if b:
            status["last_budget_line"] = line.strip()
        if "STOP" in line or "STOPPED_RUNGUARD" in line:
            status.setdefault("stops", []).append(line.strip()[:500])
        if time.monotonic() - last_write > 30:
            _write(status_path, status)
            last_write = time.monotonic()
    code = proc.wait()
    final = "succeeded" if code == 0 else ("cancelled" if code == 3 else "partial")
    status.update(state=final, exit_code=code, finished_at=_now())
    _write(status_path, status)
    with connect() as conn:
        finish_pipeline_run(
            conn, run_id, status=final,
            metadata={"exit_code": code, "status_file": str(status_path),
                      "last_budget_line": status.get("last_budget_line"),
                      "stops": status.get("stops")},
        )
        conn.commit()
    return code


def main(argv: list[str]) -> int:
    if "--" not in argv:
        print(__doc__, file=sys.stderr)
        return 2
    split = argv.index("--")
    head, pipeline_args = argv[:split], argv[split + 1:]
    if head[:1] == ["--supervise"]:
        return supervise(head[1], pipeline_args)
    return launch(pipeline_args)


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
