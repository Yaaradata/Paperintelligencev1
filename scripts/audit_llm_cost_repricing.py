#!/usr/bin/env python3
"""Read-only audit: reprice historical LLM call logs under OLD vs NEW table prices.

No LLM calls. Uses paper_intelligence.llm_requests (+ external_requests for
stage/run/date). Optionally scans raw OpenRouter cache for usage.cost when
present on disk.

Example:
  PYTHONPATH=src python3 scripts/audit_llm_cost_repricing.py \\
    --out reports/review_fixes/llm_cost_repricing_audit.json
"""

from __future__ import annotations

import argparse
import json
import sys
from collections import defaultdict
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

# Prices before Phase 2b correction (for comparison).
OLD_PRICES: dict[str, tuple[float, float]] = {
    "z-ai/glm-5.3-flash": (0.15, 0.50),
    "z-ai/glm-4.6": (0.15, 0.50),
    "openai/gpt-5.6-sol": (1.25, 10.00),
}


def _est(model: str, inp: int, out: int, table: dict[str, tuple[float, float]]) -> float | None:
    if model not in table:
        return None
    pin, pout = table[model]
    return round((inp / 1_000_000.0) * pin + (out / 1_000_000.0) * pout, 6)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--out",
        default=str(ROOT / "reports/review_fixes/llm_cost_repricing_audit.json"),
    )
    parser.add_argument(
        "--scan-raw",
        action="store_true",
        help="also scan PI raw OpenRouter cache for usage.cost (slow)",
    )
    args = parser.parse_args(argv)

    from paper_intelligence.common.config import _DEFAULT_PRICES
    from paper_intelligence.db import connect

    new_prices = dict(_DEFAULT_PRICES)

    rows_out: list[dict[str, Any]] = []
    by_stage_month: dict[str, dict[str, Any]] = {}
    run_index: dict[str, dict[str, Any]] = {}

    sql = """
        SELECT
            l.llm_request_id,
            l.model,
            l.input_tokens,
            l.output_tokens,
            l.estimated_cost AS logged_estimated_cost,
            e.run_id,
            e.stage_run_id,
            e.endpoint,
            e.started_at,
            e.response_path,
            pr.pipeline_name,
            pr.started_at AS run_started_at
        FROM paper_intelligence.llm_requests l
        JOIN paper_intelligence.external_requests e ON e.request_id = l.request_id
        LEFT JOIN paper_intelligence.pipeline_runs pr ON pr.run_id = e.run_id
        WHERE e.provider = 'openrouter'
          AND e.success IS TRUE
        ORDER BY e.started_at NULLS LAST, l.created_at
    """

    with connect() as conn:
        with conn.cursor() as cur:
            cur.execute(sql)
            db_rows = [dict(r) for r in cur.fetchall()]

    for r in db_rows:
        model = r["model"] or ""
        inp = int(r["input_tokens"] or 0)
        out = int(r["output_tokens"] or 0)
        old_c = _est(model, inp, out, OLD_PRICES)
        new_c = _est(model, inp, out, new_prices)
        endpoint = r.get("endpoint") or ""
        stage = endpoint.split(":")[-1] if ":" in endpoint else endpoint
        month = None
        if r.get("started_at"):
            month = r["started_at"].strftime("%Y-%m")
        key = f"{month or 'unknown'}|{stage or 'unknown'}|{model}"
        agg = by_stage_month.setdefault(
            key,
            {
                "month": month,
                "stage": stage,
                "model": model,
                "calls": 0,
                "input_tokens": 0,
                "output_tokens": 0,
                "old_table_usd": 0.0,
                "new_table_usd": 0.0,
                "logged_estimated_usd": 0.0,
                "run_ids": set(),
            },
        )
        agg["calls"] += 1
        agg["input_tokens"] += inp
        agg["output_tokens"] += out
        if old_c is not None:
            agg["old_table_usd"] += old_c
        if new_c is not None:
            agg["new_table_usd"] += new_c
        if r.get("logged_estimated_cost") is not None:
            agg["logged_estimated_usd"] += float(r["logged_estimated_cost"])
        if r.get("run_id"):
            agg["run_ids"].add(str(r["run_id"]))
            run_index.setdefault(
                str(r["run_id"]),
                {
                    "run_id": str(r["run_id"]),
                    "pipeline_name": r.get("pipeline_name"),
                    "run_started_at": r["run_started_at"].isoformat()
                    if r.get("run_started_at")
                    else None,
                    "models": set(),
                    "stages": set(),
                    "calls": 0,
                },
            )
            run_index[str(r["run_id"])]["models"].add(model)
            run_index[str(r["run_id"])]["stages"].add(stage)
            run_index[str(r["run_id"])]["calls"] += 1

        rows_out.append(
            {
                "started_at": r["started_at"].isoformat() if r.get("started_at") else None,
                "run_id": r.get("run_id"),
                "stage": stage,
                "model": model,
                "input_tokens": inp,
                "output_tokens": out,
                "old_table_usd": old_c,
                "new_table_usd": new_c,
                "logged_estimated_usd": float(r["logged_estimated_cost"])
                if r.get("logged_estimated_cost") is not None
                else None,
                "response_path": r.get("response_path"),
            }
        )

    raw_cost_hits = 0
    if args.scan_raw:
        from paper_intelligence.common.config import RAW_CACHE_DIR

        or_dir = Path(RAW_CACHE_DIR) / "openrouter"
        if or_dir.is_dir():
            for path in or_dir.rglob("*.json"):
                try:
                    data = json.loads(path.read_text(encoding="utf-8"))
                except Exception:
                    continue
                usage = data.get("usage") if isinstance(data, dict) else None
                if isinstance(usage, dict) and usage.get("cost") is not None:
                    raw_cost_hits += 1

    summary_rows = []
    for key, agg in sorted(by_stage_month.items()):
        summary_rows.append(
            {
                **{k: v for k, v in agg.items() if k != "run_ids"},
                "run_ids": sorted(agg["run_ids"]),
                "old_table_usd": round(agg["old_table_usd"], 4),
                "new_table_usd": round(agg["new_table_usd"], 4),
                "logged_estimated_usd": round(agg["logged_estimated_usd"], 4),
                "ratio_new_over_old": (
                    round(agg["new_table_usd"] / agg["old_table_usd"], 3)
                    if agg["old_table_usd"]
                    else None
                ),
            }
        )

    runs = []
    for rid, info in sorted(run_index.items(), key=lambda x: x[1].get("run_started_at") or ""):
        runs.append(
            {
                "run_id": rid,
                "pipeline_name": info["pipeline_name"],
                "run_started_at": info["run_started_at"],
                "calls": info["calls"],
                "models": sorted(info["models"]),
                "stages": sorted(info["stages"]),
            }
        )

    report = {
        "prices_old": OLD_PRICES,
        "prices_new": {k: list(v) for k, v in new_prices.items()},
        "verification_note": "OpenRouter model pages, 2026-09-22",
        "by_stage_month": summary_rows,
        "runs": runs,
        "call_count": len(rows_out),
        "raw_cache_usage_cost_files": raw_cost_hits if args.scan_raw else None,
        "totals": {
            "old_table_usd": round(sum(r["old_table_usd"] for r in summary_rows), 4),
            "new_table_usd": round(sum(r["new_table_usd"] for r in summary_rows), 4),
            "logged_estimated_usd": round(
                sum(r["logged_estimated_usd"] for r in summary_rows), 4
            ),
        },
    }

    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(report, indent=2, default=str) + "\n", encoding="utf-8")

    md = out.with_suffix(".md")
    lines = [
        "# LLM cost repricing audit (read-only)",
        "",
        f"Calls: **{report['call_count']}**",
        f"Old table total: **${report['totals']['old_table_usd']:.4f}**",
        f"New table total: **${report['totals']['new_table_usd']:.4f}**",
        f"Logged estimated total: **${report['totals']['logged_estimated_usd']:.4f}**",
        "",
        "## By month / stage / model",
        "",
        "| month | stage | model | calls | in tok | out tok | old $ | new $ | ratio |",
        "|---|---|---|---:|---:|---:|---:|---:|---:|",
    ]
    for r in summary_rows:
        lines.append(
            f"| {r['month']} | {r['stage']} | `{r['model']}` | {r['calls']} | "
            f"{r['input_tokens']} | {r['output_tokens']} | {r['old_table_usd']:.4f} | "
            f"{r['new_table_usd']:.4f} | {r['ratio_new_over_old']} |"
        )
    lines += ["", "## Runs (match to OpenRouter activity)", ""]
    for r in runs[:80]:
        lines.append(
            f"- `{r['run_id']}` · {r['run_started_at']} · {r['pipeline_name']} · "
            f"calls={r['calls']} · stages={','.join(r['stages'])} · "
            f"models={','.join(r['models'])}"
        )
    if len(runs) > 80:
        lines.append(f"- … and {len(runs) - 80} more (see JSON)")
    md.write_text("\n".join(lines) + "\n", encoding="utf-8")

    print(f"wrote {out}")
    print(f"wrote {md}")
    print(
        f"totals old=${report['totals']['old_table_usd']:.4f} "
        f"new=${report['totals']['new_table_usd']:.4f}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
