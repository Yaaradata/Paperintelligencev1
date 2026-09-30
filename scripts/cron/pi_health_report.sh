#!/usr/bin/env bash
# Daily health email. Cron: 30 0 * * * (server is UTC; = 06:00 IST).
# Separate job from the pipeline on purpose: it must report even if the pipeline never ran.
set -uo pipefail
REPO=/home/ubuntu/Paperintelligencev1/worktrees/subha
PY="/home/ubuntu/theneural/Newsletter agent/.venv/bin/python"
set -a; . /home/ubuntu/Paperintelligencev1/.env; set +a
mkdir -p "$REPO/reports/cron"
cd "$REPO"
echo "=== $(date -u +%FT%TZ)" >> "$REPO/reports/cron/health.log"
PYTHONPATH="$REPO/src" "$PY" scripts/daily_health_report.py >> "$REPO/reports/cron/health.log" 2>&1
