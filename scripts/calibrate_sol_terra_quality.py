#!/usr/bin/env python3
"""Sol vs Terra quality calibration (PAID — ask before --allow-paid).

Samples ~60 Sep 1–15 papers that already have Sol quality scores (stratified
across final_score, including the top 20), scores them with Terra under a
separate calibration run_id that is NOT treated as current quality.

Default is dry-run cost only. Do not pass --allow-paid without explicit approval.

  PYTHONPATH=src python3 scripts/calibrate_sol_terra_quality.py \\
    --from 2026-09-01 --until 2026-09-15

  # After explicit go-ahead:
  PYTHONPATH=src python3 scripts/calibrate_sol_terra_quality.py \\
    --from 2026-09-01 --until 2026-09-15 --allow-paid --max-cost-usd 5
"""

from __future__ import annotations

import argparse
import json
import math
import sys
import uuid
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

SOL_MODEL = "openai/gpt-5.6-sol"
TERRA_MODEL = "openai/gpt-5.6-terra"
CALIBRATION_RUN_PREFIX = "quality-calibration-sol-terra"


def _spearman(xs: list[float], ys: list[float]) -> float | None:
    if len(xs) != len(ys) or len(xs) < 2:
        return None
    n = len(xs)

    def ranks(vals: list[float]) -> list[float]:
        order = sorted(range(n), key=lambda i: vals[i])
        r = [0.0] * n
        i = 0
        while i < n:
            j = i
            while j + 1 < n and vals[order[j + 1]] == vals[order[i]]:
                j += 1
            avg = (i + j) / 2.0 + 1.0
            for k in range(i, j + 1):
                r[order[k]] = avg
            i = j + 1
        return r

    rx, ry = ranks(xs), ranks(ys)
    mean_x = sum(rx) / n
    mean_y = sum(ry) / n
    num = sum((a - mean_x) * (b - mean_y) for a, b in zip(rx, ry))
    den_x = math.sqrt(sum((a - mean_x) ** 2 for a in rx))
    den_y = math.sqrt(sum((b - mean_y) ** 2 for b in ry))
    if den_x == 0 or den_y == 0:
        return None
    return num / (den_x * den_y)


def _select_sample(
    rows: list[dict[str, Any]],
    *,
    n: int = 60,
    top_n: int = 20,
) -> list[dict[str, Any]]:
    """Stratify across final_score; always include top_n by final_score."""
    scored = [r for r in rows if r.get("final_score") is not None]
    scored.sort(key=lambda r: (-float(r["final_score"]), int(r["content_item_id"])))
    if not scored:
        return []
    top = scored[: min(top_n, len(scored))]
    selected = {int(r["content_item_id"]): r for r in top}
    remaining = [r for r in scored if int(r["content_item_id"]) not in selected]
    need = max(0, n - len(selected))
    if need and remaining:
        # Equal-width bands on final_score.
        lo = float(remaining[-1]["final_score"])
        hi = float(remaining[0]["final_score"])
        bands = 5
        if hi <= lo:
            step = max(1, len(remaining) // need)
            for r in remaining[::step][:need]:
                selected[int(r["content_item_id"])] = r
        else:
            width = (hi - lo) / bands
            buckets: list[list[dict[str, Any]]] = [[] for _ in range(bands)]
            for r in remaining:
                idx = min(bands - 1, int((float(r["final_score"]) - lo) / width))
                # score high → band near end
                idx = bands - 1 - idx
                buckets[idx].append(r)
            per = max(1, need // bands)
            for bucket in buckets:
                for r in bucket[:per]:
                    if len(selected) >= n:
                        break
                    selected[int(r["content_item_id"])] = r
            # Fill remainder from overall remaining.
            for r in remaining:
                if len(selected) >= n:
                    break
                selected.setdefault(int(r["content_item_id"]), r)
    out = list(selected.values())
    out.sort(key=lambda r: (-float(r["final_score"]), int(r["content_item_id"])))
    return out[:n]


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--from", dest="date_from", default="2026-09-01")
    parser.add_argument("--until", dest="date_until", default="2026-09-15")
    parser.add_argument("--sample-size", type=int, default=60)
    parser.add_argument("--top-n", type=int, default=20)
    parser.add_argument("--max-cost-usd", type=float, default=None)
    parser.add_argument("--allow-paid", action="store_true")
    parser.add_argument(
        "--out",
        default=str(ROOT / "reports/review_fixes/sol_terra_calibration.json"),
    )
    args = parser.parse_args(argv)

    from paper_intelligence.common.budget import resolve_max_cost_usd
    from paper_intelligence.common.config import require_model_priced
    from paper_intelligence.db import connect
    from paper_intelligence.quality import stage as quality_stage
    from paper_intelligence.quality.stage import (
        POLICY_VERSION,
        PROMPT_VERSION,
        STAGE_VERSION,
    )

    max_cost = resolve_max_cost_usd(args.max_cost_usd)
    require_model_priced(TERRA_MODEL)
    require_model_priced(SOL_MODEL)

    sql = """
        SELECT DISTINCT ON (r.content_item_id)
            r.content_item_id,
            r.result_json,
            r.model,
            r.created_at,
            c.final_score,
            p.title,
            p.arxiv_id,
            p.published_at
        FROM paper_intelligence.paper_classification_results r
        JOIN paper_intelligence.papers p ON p.paper_id = r.content_item_id
        LEFT JOIN paper_intelligence.paper_intelligence_current c
          ON c.content_item_id = r.content_item_id
        WHERE r.task_type = 'quality'
          AND r.model = %s
          AND r.stage_version = %s
          AND r.prompt_version = %s
          AND r.policy_version = %s
          AND p.published_at >= %s::timestamptz
          AND p.published_at < (%s::timestamptz + interval '1 day')
        ORDER BY r.content_item_id, r.created_at DESC
    """

    with connect() as conn:
        with conn.cursor() as cur:
            cur.execute(
                sql,
                (
                    SOL_MODEL,
                    STAGE_VERSION,
                    PROMPT_VERSION,
                    POLICY_VERSION,
                    args.date_from,
                    args.date_until,
                ),
            )
            sol_rows = [dict(r) for r in cur.fetchall()]

        sample = _select_sample(sol_rows, n=args.sample_size, top_n=args.top_n)
        ids = [int(r["content_item_id"]) for r in sample]
        print(
            f"calibration sample: {len(ids)} papers with Sol quality "
            f"in {args.date_from}..{args.date_until} "
            f"(requested {args.sample_size}, top {args.top_n} forced)",
            flush=True,
        )
        if not ids:
            print("no Sol-scored papers in window", file=sys.stderr)
            return 2

        proj = quality_stage.run_window(
            conn,
            ids,
            run_id="dry-run",
            stage_run_id="dry-run",
            dry_run=True,
            model=TERRA_MODEL,
        )
        print(
            f"DRY-RUN Terra cost: {len(ids)} papers · ~{proj.calls} calls · "
            f"~${proj.cost_usd:.4f} (model={TERRA_MODEL})",
            flush=True,
        )
        print(
            "STOP: calibration is PAID. Re-run with --allow-paid only after "
            "explicit approval. Results use a calibration run_id and are not "
            "current quality (adjudication still expects Sol for pre-cutover).",
            flush=True,
        )

        report: dict[str, Any] = {
            "date_from": args.date_from,
            "date_until": args.date_until,
            "sol_model": SOL_MODEL,
            "terra_model": TERRA_MODEL,
            "sample_size": len(ids),
            "sample_ids": ids,
            "dry_run_projected_cost_usd": round(proj.cost_usd, 4),
            "executed": False,
            "note": (
                "Terra rows written under calibration run_id are append-only "
                "history; mapped quality model for these dates remains Sol, so "
                "adjudication will not treat Terra as current."
            ),
        }

        if not args.allow_paid:
            out = Path(args.out)
            out.parent.mkdir(parents=True, exist_ok=True)
            out.write_text(json.dumps(report, indent=2, default=str) + "\n", encoding="utf-8")
            print(f"wrote {out} (dry-run only)")
            return 0

        if max_cost is not None and proj.cost_usd > max_cost:
            print(
                f"refusing: projected ${proj.cost_usd:.4f} exceeds cap ${max_cost:.4f}",
                file=sys.stderr,
            )
            return 2

        run_id = f"{CALIBRATION_RUN_PREFIX}-{uuid.uuid4()}"
        stage_run_id = f"{run_id}-stage"
        print(f"PAID calibration run_id={run_id}", flush=True)
        stats = quality_stage.run_window(
            conn,
            ids,
            run_id=run_id,
            stage_run_id=stage_run_id,
            dry_run=False,
            model=TERRA_MODEL,
            max_cost_usd=max_cost,
        )
        print(stats.summary_line("quality-calibration"), flush=True)

        # Load Terra results for this run and compare to Sol sample.
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT content_item_id, result_json
                FROM paper_intelligence.paper_classification_results
                WHERE run_id = %s AND task_type = 'quality' AND model = %s
                """,
                (run_id, TERRA_MODEL),
            )
            terra_by_id = {
                int(r["content_item_id"]): (r["result_json"] or {}) for r in cur.fetchall()
            }

        rubrics = (
            "technical_significance",
            "apparent_novelty",
            "practical_applicability",
            "professional_value",
            "learning_value",
            "evidence_strength",
        )
        pairs: list[dict[str, Any]] = []
        sol_finals: list[float] = []
        terra_finals: list[float] = []
        dim_abs: dict[str, list[float]] = {d: [] for d in rubrics}

        sol_by_id = {int(r["content_item_id"]): r for r in sample}
        for cid in ids:
            sol_row = sol_by_id[cid]
            sol_rj = sol_row.get("result_json") or {}
            terra_rj = terra_by_id.get(cid) or {}
            sol_comp = (sol_rj.get("composite") or {}).get("final")
            terra_comp = (terra_rj.get("composite") or {}).get("final")
            # Fall back to stored current final for Sol ranking if composite missing.
            if sol_comp is None and sol_row.get("final_score") is not None:
                sol_comp = float(sol_row["final_score"])
            entry: dict[str, Any] = {
                "content_item_id": cid,
                "arxiv_id": sol_row.get("arxiv_id"),
                "title": sol_row.get("title"),
                "sol_final": sol_comp,
                "terra_final": terra_comp,
                "abs_diff": None,
                "sol_so_what": sol_rj.get("so_what"),
                "terra_so_what": terra_rj.get("so_what"),
                "sol_reason_not_higher": sol_rj.get("reason_not_higher"),
                "terra_reason_not_higher": terra_rj.get("reason_not_higher"),
            }
            if sol_comp is not None and terra_comp is not None:
                entry["abs_diff"] = abs(float(sol_comp) - float(terra_comp))
                sol_finals.append(float(sol_comp))
                terra_finals.append(float(terra_comp))
            for dim in rubrics:
                try:
                    sv = float(sol_rj.get(dim))
                    tv = float(terra_rj.get(dim))
                    dim_abs[dim].append(abs(sv - tv))
                except (TypeError, ValueError):
                    pass
            pairs.append(entry)

        # Top-15 overlap by each model's final.
        sol_rank = sorted(
            [p for p in pairs if p["sol_final"] is not None],
            key=lambda p: (-float(p["sol_final"]), p["content_item_id"]),
        )
        terra_rank = sorted(
            [p for p in pairs if p["terra_final"] is not None],
            key=lambda p: (-float(p["terra_final"]), p["content_item_id"]),
        )
        sol_top15 = {p["content_item_id"] for p in sol_rank[:15]}
        terra_top15 = {p["content_item_id"] for p in terra_rank[:15]}
        overlap = sol_top15 & terra_top15

        biggest = sorted(
            [p for p in pairs if p["abs_diff"] is not None],
            key=lambda p: -float(p["abs_diff"]),
        )[:10]

        report.update(
            {
                "executed": True,
                "run_id": run_id,
                "actual_cost_usd": round(stats.cost_usd, 4),
                "spearman_final_score": _spearman(sol_finals, terra_finals),
                "top15_overlap": len(overlap),
                "top15_overlap_ids": sorted(overlap),
                "mean_abs_diff_by_dimension": {
                    d: (round(sum(v) / len(v), 4) if v else None)
                    for d, v in dim_abs.items()
                },
                "mean_abs_diff_final": (
                    round(sum(p["abs_diff"] for p in pairs if p["abs_diff"] is not None)
                          / max(1, sum(1 for p in pairs if p["abs_diff"] is not None)), 4)
                ),
                "biggest_disagreements": biggest,
                "pairs": pairs,
            }
        )

    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(report, indent=2, default=str) + "\n", encoding="utf-8")
    md = out.with_suffix(".md")
    lines = [
        "# Sol vs Terra quality calibration",
        "",
        f"Window: {args.date_from} → {args.date_until}",
        f"Sample: {report['sample_size']} papers",
        f"Dry-run Terra cost: ~${report['dry_run_projected_cost_usd']:.4f}",
        "",
    ]
    if report.get("executed"):
        lines += [
            f"Run id: `{report['run_id']}`",
            f"Actual cost: ${report['actual_cost_usd']:.4f}",
            f"Spearman(final_score): {report['spearman_final_score']}",
            f"Top-15 overlap: {report['top15_overlap']}/15",
            f"Mean |Δ final|: {report['mean_abs_diff_final']}",
            "",
            "## Mean |Δ| by rubric dimension",
            "",
        ]
        for d, v in (report.get("mean_abs_diff_by_dimension") or {}).items():
            lines.append(f"- `{d}`: {v}")
        lines += ["", "## Biggest disagreements", ""]
        for p in report.get("biggest_disagreements") or []:
            lines.append(
                f"- id {p['content_item_id']} |Δ|={p['abs_diff']}: "
                f"Sol {p['sol_final']} vs Terra {p['terra_final']} — "
                f"{(p.get('title') or '')[:80]}"
            )
            lines.append(f"  - Sol so_what: {p.get('sol_so_what') or '—'}")
            lines.append(f"  - Terra so_what: {p.get('terra_so_what') or '—'}")
    else:
        lines.append("Not executed (dry-run only). Awaiting explicit --allow-paid.")
    md.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"wrote {out}")
    print(f"wrote {md}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
