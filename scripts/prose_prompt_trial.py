#!/usr/bin/env python3
"""Trial a quality_prose prompt version on papers already audited, JSON output only.

Regenerates so_what / reason_not_higher with prompts/quality_prose/<version>.md
for exactly the papers in an audit results file, using the scores on each
paper's current quality row. Nothing is written to scoring tables; calls are
logged to external_requests/llm_requests like every other LLM call.

  PYTHONPATH=src python scripts/prose_prompt_trial.py \
      --papers-from reports/golden/prose_audit_luna_2026-09-21_2026-09-23_v002.json \
      --prompt-version v002 --max-cost-usd 0.15 [--dry-run] [--limit N]

Feed the output to audit_prose_luna.py --prose-from to compare prompts.
"""
from __future__ import annotations

import argparse
import json
import sys
import threading
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from paper_intelligence.common.config import read_prompt, require_model_priced
from paper_intelligence.common.llm_stage import call_llm_logged
from paper_intelligence.db import connect
from paper_intelligence.quality.jev_glm_engine import (
    PROSE_EXTRA_BODY,
    PROSE_MAX_ATTEMPTS,
    PROSE_MAX_TOKENS,
    PROSE_MODEL,
    PROSE_PROMPT_STAGE,
    PROSE_RESPONSE_FORMAT,
    build_prose_user_prompt,
    parse_prose_response,
    project_prose_cost,
)
from paper_intelligence.quality.stage import RUBRIC_DIMENSIONS

CONCURRENCY = 8
CURRENT_QUALITY_SQL = """
SELECT DISTINCT ON (r.content_item_id) r.content_item_id, r.result_json, p.title, p.abstract
FROM paper_intelligence.paper_classification_results r
JOIN paper_intelligence.papers p ON p.paper_id = r.content_item_id
WHERE r.task_type = 'quality' AND r.content_item_id = ANY(%s)
ORDER BY r.content_item_id, r.created_at DESC
"""


def load_papers(ids: list[int]) -> list[dict[str, Any]]:
    with connect() as conn:
        rows = [dict(r) for r in conn.execute(CURRENT_QUALITY_SQL, (ids,)).fetchall()]
    for r in rows:
        if isinstance(r["result_json"], str):
            r["result_json"] = json.loads(r["result_json"])
    return rows


def scores_of(row: dict[str, Any]) -> dict[str, Any]:
    return {d: row["result_json"].get(d) for d in RUBRIC_DIMENSIONS}


class Spend:
    def __init__(self, cap: float) -> None:
        self.cap, self.total, self.max_call, self.calls = cap, 0.0, 0.0, 0
        self.lock = threading.Lock()

    def may_start(self) -> bool:
        with self.lock:
            reserve = self.max_call * CONCURRENCY if self.max_call else 0.01
            return self.total + reserve <= self.cap

    def add(self, cost: float) -> None:
        with self.lock:
            self.calls += 1
            self.total += cost
            self.max_call = max(self.max_call, cost)


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--papers-from", type=Path, required=True, help="audit results JSON; its paper ids are used")
    ap.add_argument("--prompt-version", required=True)
    ap.add_argument("--max-cost-usd", type=float, required=True)
    ap.add_argument("--limit", type=int)
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--out", type=Path)
    args = ap.parse_args()

    ids = sorted(int(k) for k in json.loads(args.papers_from.read_text())["results"])
    if args.limit:
        ids = ids[: args.limit]
    out_path = args.out or Path(
        f"reports/golden/prose_trial_{args.prompt_version}_{args.papers_from.stem}.json"
    )
    require_model_priced(PROSE_MODEL)
    system_prompt = read_prompt(PROSE_PROMPT_STAGE, args.prompt_version)
    papers = load_papers(ids)
    prompt_version = f"{PROSE_PROMPT_STAGE}_{args.prompt_version}_trial"
    print(f"prose_trial: papers={len(papers)} model={PROSE_MODEL} prompt={prompt_version} "
          f"cap=${args.max_cost_usd}", flush=True)
    if args.dry_run:
        calls, tin, tout, usd = project_prose_cost(papers)
        print(f"PROJECTION prose_trial: {calls} calls, ~{tin} in / ~{tout} out, ~${usd:.4f} "
              f"(table price; worst case with one retry each ~${2 * usd:.4f})", flush=True)
        return 0

    spend = Spend(args.max_cost_usd)
    prose: dict[int, dict[str, Any]] = {}
    failures: dict[int, str] = {}
    lock = threading.Lock()

    def one(p: dict[str, Any]) -> None:
        cid = int(p["content_item_id"])
        paper = {"content_item_id": cid, "title": p["title"], "abstract": p["abstract"]}
        user, index_to_id = build_prose_user_prompt([paper], {cid: scores_of(p)})
        error = "skipped: spend cap"
        for _ in range(PROSE_MAX_ATTEMPTS):
            if not spend.may_start():
                break
            try:
                with connect() as conn:
                    resp = call_llm_logged(
                        conn, model=PROSE_MODEL, system_prompt=system_prompt, user_prompt=user,
                        prompt_version=prompt_version, stage_name="quality_prose_trial",
                        temperature=0.1, max_tokens=PROSE_MAX_TOKENS,
                        response_format=PROSE_RESPONSE_FORMAT, extra_body=PROSE_EXTRA_BODY,
                        entity=f"quality_prose_trial_{cid}", timeout=120.0,
                    )
            except Exception as exc:  # noqa: BLE001
                error = f"call_failed: {exc}"[:300]
                continue
            spend.add(float(resp["actual_cost_usd"] if resp["actual_cost_usd"] is not None
                            else resp["estimated_cost_usd"]))
            parsed, problems = parse_prose_response(resp["content"], index_to_id)
            cell = parsed.get(cid)
            if cell and cell.get("so_what") and cell.get("reason_not_higher"):
                with lock:
                    prose[cid] = cell
                return
            error = "; ".join(problems)[:300] or "prose_incomplete"
        with lock:
            failures[cid] = error

    with ThreadPoolExecutor(max_workers=CONCURRENCY) as pool:
        list(pool.map(one, papers))

    by_id = {int(p["content_item_id"]): p for p in papers}
    payload = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "prompt_version": prompt_version,
        "model": PROSE_MODEL,
        "papers_from": str(args.papers_from),
        "n_population": len(papers),
        "n_ok": len(prose),
        "failures": {str(k): v for k, v in sorted(failures.items())},
        "spend": {"usage_cost_usd": round(spend.total, 6), "calls": spend.calls, "cap_usd": args.max_cost_usd},
        "results": {
            str(cid): {
                "so_what": cell["so_what"],
                "reason_not_higher": cell["reason_not_higher"],
                "baseline_so_what": by_id[cid]["result_json"].get("so_what"),
            }
            for cid, cell in sorted(prose.items())
        },
    }
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(payload, indent=2, default=str), encoding="utf-8")
    print(f"prose_trial: done ok={len(prose)}/{len(papers)} failed={len(failures)} "
          f"calls={spend.calls} usage.cost=${spend.total:.4f} -> {out_path}", flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
