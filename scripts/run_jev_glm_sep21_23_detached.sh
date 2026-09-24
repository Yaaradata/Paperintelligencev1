#!/usr/bin/env bash
set -euo pipefail
cd /home/ubuntu/Paperintelligencev1/worktrees/subha
export PYTHONPATH=src
export QUALITY_ENGINE=jev_glm
export CLASSIFY_MODEL=z-ai/glm-5.3-flash
export SCREEN_MODEL=z-ai/glm-5.3-flash

LOG=reports/golden/jev_glm_sep21_23_pipeline.log
RECORD=reports/golden/jev_glm_sep21_23_run.json

echo "[$(date -u +%Y-%m-%dT%H:%M:%SZ)] pipeline start pid=$$" | tee -a "$LOG"
python3 - <<PY
import json
from datetime import datetime, timezone
from pathlib import Path
p = Path("reports/golden/jev_glm_sep21_23_run.json")
m = json.loads(p.read_text())
m["status"] = "running"
m["pipeline_pid"] = $$
m["pipeline_started_at"] = datetime.now(timezone.utc).isoformat()
p.write_text(json.dumps(m, indent=2))
PY

set +e
PYTHONPATH=src python3 scripts/run_pipeline.py \
  --from 2026-09-21 --until 2026-09-23 \
  --stages screen,affiliation_fast,audience_domain,quality,affiliation_deep,hf_signals,adjudication,reports \
  --allow-paid --max-cost-usd 1.50 \
  --allow-quality-model-change \
  >>"$LOG" 2>&1
EC=$?
set -e
echo "[$(date -u +%Y-%m-%dT%H:%M:%SZ)] pipeline exit=$EC" | tee -a "$LOG"

python3 - <<PY
import json
from datetime import datetime, timezone
from pathlib import Path
p = Path("reports/golden/jev_glm_sep21_23_run.json")
m = json.loads(p.read_text())
m["status"] = "finished"
m["pipeline_exit_code"] = $EC
m["pipeline_finished_at"] = datetime.now(timezone.utc).isoformat()
p.write_text(json.dumps(m, indent=2))
PY

QUALITY_ENGINE=jev_glm PYTHONPATH=src python3 scripts/write_jev_glm_report.py >>"$LOG" 2>&1 || true
echo "[$(date -u +%Y-%m-%dT%H:%M:%SZ)] report rewrite done" | tee -a "$LOG"
exit $EC
