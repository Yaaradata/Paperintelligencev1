#!/usr/bin/env bash
# Daily free stages. Cron: 30 20 * * * (server is UTC; = 02:00 IST).
# Never passes --allow-paid: cron does not run paid stages (decision 30 Sep 2026).
# Rolling 6-day window: Thursday-afternoon submissions are announced Sunday 20:00 ET,
# after Sunday's run, so Monday's run must still reach back to Thursday (more over holidays).
set -euo pipefail
REPO=/home/ubuntu/Paperintelligencev1/worktrees/subha
PY="/home/ubuntu/theneural/Newsletter agent/.venv/bin/python"
set -a; . /home/ubuntu/Paperintelligencev1/.env; set +a
export PYTHONPATH="$REPO/src"
FROM=$(date -u -d '6 days ago' +%F)
UNTIL=$(date -u -d 'yesterday' +%F)
mkdir -p "$REPO/reports/cron"
cd "$REPO"
"$PY" scripts/launch_pipeline_run.py -- --from "$FROM" --until "$UNTIL" \
  --stages ingest,relevance,normalize_authors,affiliation_fast,affiliation_deep,hf_signals \
  >> "$REPO/reports/cron/free_stages.log" 2>&1
