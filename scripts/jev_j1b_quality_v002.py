#!/usr/bin/env python3
"""Re-run J1b quality comparison with System One quality_v002 (cap $2).

Same paper set as J1b: Sol Sep1–15 + Terra Sep16–21 LLM quality rows.
Reuses LLM scores; only Jev is re-scored under quality_v002.

  PYTHONPATH=src python3 scripts/jev_j1b_quality_v002.py --allow-paid --max-cost-usd 2

Writes:
  reports/review_fixes/jev_j1b_quality_v002.md
  reports/review_fixes/jev_j1b_quality_v002.json
  reports/review_fixes/jev_j1b_quality_scores.json  (per-paper, for CSV reuse)
"""

from __future__ import annotations

import argparse
import json
import math
import statistics
import sys
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from paper_intelligence.common.budget import BudgetCap  # noqa: E402
from paper_intelligence.common.config import require_model_priced  # noqa: E402
from paper_intelligence.db import connect  # noqa: E402
from paper_intelligence.systemone.client import (  # noqa: E402
    JEV_MODEL_PINNED,
    SystemOneRequest,
    system_one,
)
from paper_intelligence.systemone.policy import (  # noqa: E402
    build_questions,
    load_systemone_policy,
    parse_answers,
    state_from_paper,
)

REPORT = ROOT / "reports" / "review_fixes" / "jev_j1b_quality_v002.md"
JSON_OUT = ROOT / "reports" / "review_fixes" / "jev_j1b_quality_v002.json"
PER_PAPER = ROOT / "reports" / "review_fixes" / "jev_j1b_quality_scores.json"
V001_JSON = ROOT / "reports" / "review_fixes" / "jev_j1b.json"

QUALITY_DIMS = (
    "technical_significance",
    "apparent_novelty",
    "practical_applicability",
    "professional_value",
    "learning_value",
    "evidence_strength",
)
Q_WEIGHTS = {
    "technical_significance": 0.28,
    "apparent_novelty": 0.24,
    "practical_applicability": 0.20,
    "professional_value": 0.16,
    "learning_value": 0.12,
}
# v002 asks these two; combined → professional_value for LLM comparison.
PV_PARTS = ("decision_relevance_eng", "decision_relevance_product")


def _args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--allow-paid", action="store_true")
    p.add_argument("--max-cost-usd", type=float, default=2.0)
    p.add_argument("--concurrency", type=int, default=8)
    p.add_argument("--dry-run", action="store_true")
    return p.parse_args()


def _spearman(xs: list[float], ys: list[float]) -> float | None:
    if len(xs) < 3 or len(xs) != len(ys):
        return None

    def ranks(vals: list[float]) -> list[float]:
        order = sorted(range(len(vals)), key=lambda i: vals[i])
        r = [0.0] * len(vals)
        i = 0
        while i < len(order):
            j = i
            while j + 1 < len(order) and vals[order[j + 1]] == vals[order[i]]:
                j += 1
            avg = (i + j) / 2.0 + 1.0
            for k in range(i, j + 1):
                r[order[k]] = avg
            i = j + 1
        return r

    rx, ry = ranks(xs), ranks(ys)
    mx, my = statistics.mean(rx), statistics.mean(ry)
    num = sum((a - mx) * (b - my) for a, b in zip(rx, ry))
    denx = math.sqrt(sum((a - mx) ** 2 for a in rx))
    deny = math.sqrt(sum((b - my) ** 2 for b in ry))
    if denx == 0 or deny == 0:
        return None
    return num / (denx * deny)


def _composite(scores: dict[str, float]) -> float:
    q = sum(Q_WEIGHTS[d] * float(scores[d]) for d in Q_WEIGHTS)
    ef = 0.70 + 0.03 * float(scores["evidence_strength"])
    return min(10.0, q * ef)


def _load_quality(conn) -> list[dict[str, Any]]:
    rows = conn.execute(
        """
        SELECT DISTINCT ON (q.content_item_id)
          q.content_item_id,
          p.title,
          p.abstract,
          p.arxiv_id,
          p.published_at::date AS published_date,
          q.model,
          q.result_json,
          q.created_at
        FROM paper_intelligence.paper_classification_results q
        JOIN paper_intelligence.papers p ON p.paper_id = q.content_item_id
        WHERE q.task_type = 'quality'
          AND p.published_at >= '2026-09-01'
          AND p.published_at < '2026-09-22'
        ORDER BY q.content_item_id, q.created_at DESC
        """
    ).fetchall()
    out = []
    for r in rows:
        rj = r["result_json"] or {}
        if isinstance(rj, str):
            rj = json.loads(rj)
        try:
            scores = {d: float(rj[d]) for d in QUALITY_DIMS}
        except (KeyError, TypeError, ValueError):
            continue
        model = str(r["model"] or "")
        pub = str(r["published_date"])
        if "terra" in model.lower() and pub >= "2026-09-16":
            family = "terra"
        elif "sol" in model.lower() and pub < "2026-09-16":
            family = "sol"
        else:
            continue
        comp = rj.get("composite") or {}
        out.append(
            {
                "content_item_id": int(r["content_item_id"]),
                "title": r["title"] or "",
                "abstract": r["abstract"] or "",
                "arxiv_id": r["arxiv_id"],
                "published_date": pub,
                "model": model,
                "family": family,
                "llm_scores": scores,
                "llm_composite_quality": float(comp["quality"])
                if isinstance(comp, dict) and comp.get("quality") is not None
                else _composite(scores),
            }
        )
    return out


def _jev_dims_from_parsed(parsed: dict[str, Any]) -> tuple[dict[str, float], float | None]:
    """Build six comparable dims; professional_value = mean of eng+product parts."""
    dims: dict[str, float] = {}
    confs: list[float] = []
    for d in QUALITY_DIMS:
        if d == "professional_value":
            continue
        cell = parsed.get(d) or {}
        if isinstance(cell, dict) and cell.get("score_0_10") is not None:
            dims[d] = float(cell["score_0_10"])
            if cell.get("confidence") is not None:
                confs.append(float(cell["confidence"]))
    parts = []
    for key in PV_PARTS:
        cell = parsed.get(key) or {}
        if isinstance(cell, dict) and cell.get("score_0_10") is not None:
            parts.append(float(cell["score_0_10"]))
            if cell.get("confidence") is not None:
                confs.append(float(cell["confidence"]))
    if len(parts) == len(PV_PARTS):
        dims["professional_value"] = sum(parts) / len(parts)
    conf = statistics.mean(confs) if confs else None
    return dims, conf


def _call(paper: dict[str, Any], policy: dict[str, Any], questions: dict[str, Any], budget: BudgetCap) -> dict[str, Any]:
    if not budget.allow_new_batch():
        return {"ok": False, "error": "budget_cap", "content_item_id": paper["content_item_id"]}
    t0 = time.perf_counter()
    resp = system_one(
        SystemOneRequest(
            model=JEV_MODEL_PINNED,
            state=state_from_paper(paper),
            questions=questions,
        )
    )
    elapsed = time.perf_counter() - t0
    billable = float(resp.billable_cost or 0.0)
    if not resp.error:
        budget.add_actual(billable)
    parsed = parse_answers(resp.answers or {}, policy) if not resp.error else {}
    return {
        "ok": resp.error is None,
        "error": resp.error,
        "content_item_id": paper["content_item_id"],
        "elapsed_s": elapsed,
        "billable_cost_usd": billable,
        "parsed": parsed,
        "answers": resp.answers,
    }


def _run_pool(papers, policy, questions, budget, concurrency: int) -> dict[int, dict]:
    sink: dict[int, dict] = {}
    print(f"=== quality_v002 n={len(papers)} ===", flush=True)
    with ThreadPoolExecutor(max_workers=concurrency) as ex:
        futs = [ex.submit(_call, p, policy, questions, budget) for p in papers]
        done = 0
        for fut in as_completed(futs):
            rec = fut.result()
            sink[int(rec["content_item_id"])] = rec
            done += 1
            if done % 50 == 0 or done == len(futs):
                print(f"  quality {done}/{len(futs)} spent=${budget.actual_usd:.4f}", flush=True)
    return sink


def quality_stats(subset: list[dict[str, Any]], label: str) -> dict[str, Any]:
    ok = [p for p in subset if p.get("jev_ok")]
    per_dim = {}
    for d in QUALITY_DIMS:
        xs, ys, absd = [], [], []
        for p in ok:
            xs.append(float(p["llm_scores"][d]))
            ys.append(float(p["jev_scores"][d]))
            absd.append(abs(xs[-1] - ys[-1]))
        per_dim[d] = {
            "spearman": _spearman(xs, ys),
            "mae": statistics.mean(absd) if absd else None,
            "n": len(xs),
        }
    llm_ranked = sorted(ok, key=lambda p: (-float(p["llm_composite_quality"]), p["content_item_id"]))
    jev_ranked = sorted(ok, key=lambda p: (-float(p["jev_composite"]), p["content_item_id"]))
    overlaps = {}
    for k in (20, 50):
        a = {p["content_item_id"] for p in llm_ranked[:k]}
        b = {p["content_item_id"] for p in jev_ranked[:k]}
        overlaps[f"top_{k}"] = {"overlap": len(a & b), "of": k}
    bands = []
    max_conf = max((float(p["jev_confidence"]) for p in ok if p.get("jev_confidence") is not None), default=None)
    for lo, hi in ((0.0, 0.6), (0.6, 0.7), (0.7, 0.8), (0.8, 0.9), (0.9, 1.01)):
        sub = [
            p
            for p in ok
            if p.get("jev_confidence") is not None and lo <= float(p["jev_confidence"]) < hi
        ]
        if not sub:
            bands.append({"lo": lo, "hi": hi, "n": 0, "composite_mae": None})
            continue
        mae = statistics.mean(
            [abs(float(p["llm_composite_quality"]) - float(p["jev_composite"])) for p in sub]
        )
        bands.append({"lo": lo, "hi": hi, "n": len(sub), "composite_mae": mae})
    return {
        "label": label,
        "n_eligible": len(subset),
        "n_ok": len(ok),
        "per_dim": per_dim,
        "composite_spearman": _spearman(
            [float(p["llm_composite_quality"]) for p in ok],
            [float(p["jev_composite"]) for p in ok],
        ),
        "composite_mae": statistics.mean(
            [abs(float(p["llm_composite_quality"]) - float(p["jev_composite"])) for p in ok]
        )
        if ok
        else None,
        "overlaps": overlaps,
        "confidence_bands": bands,
        "max_confidence": max_conf,
        "any_confidence_ge_0_9": bool(max_conf is not None and max_conf >= 0.9),
    }


def _fmt(x, nd=3):
    return "n/a" if x is None else f"{x:.{nd}f}"


def main() -> int:
    args = _args()
    if not args.dry_run and not args.allow_paid:
        print("Need --allow-paid", file=sys.stderr)
        return 2
    require_model_priced(JEV_MODEL_PINNED)
    load_systemone_policy.cache_clear()
    policy = load_systemone_policy("quality", "v002")
    questions = build_questions(policy)
    print(
        f"policy=quality_v002 questions={list(questions)} "
        f"levels={[len(questions[k]['criteria']) for k in questions]}",
        flush=True,
    )

    with connect() as conn:
        qualities = _load_quality(conn)
    sol_q = [p for p in qualities if p["family"] == "sol"]
    terra_q = [p for p in qualities if p["family"] == "terra"]
    quality_run = list({p["content_item_id"]: p for p in sol_q + terra_q}.values())
    print(f"quality_run={len(quality_run)} sol={len(sol_q)} terra={len(terra_q)}", flush=True)

    if args.dry_run:
        print(json.dumps({"dry_run": True, "n": len(quality_run), "est_usd": round(len(quality_run) * 0.000057, 4)}))
        return 0

    budget = BudgetCap(args.max_cost_usd)
    t0 = time.perf_counter()
    results = _run_pool(quality_run, policy, questions, budget, args.concurrency)
    wall = time.perf_counter() - t0
    spent = budget.actual_usd

    per_paper: dict[str, Any] = {}
    for p in quality_run:
        rec = results.get(p["content_item_id"]) or {}
        parsed = rec.get("parsed") or {}
        dims, conf = _jev_dims_from_parsed(parsed)
        ok = bool(rec.get("ok")) and len(dims) == len(QUALITY_DIMS)
        p["jev_scores"] = dims
        p["jev_ok"] = ok
        p["jev_composite"] = _composite(dims) if ok else None
        p["jev_confidence"] = conf
        if ok:
            per_paper[str(p["content_item_id"])] = {
                "content_item_id": p["content_item_id"],
                "dims": dims,
                "composite": p["jev_composite"],
                "confidence": conf,
                "family": p["family"],
                "published_date": p["published_date"],
                "pv_parts": {
                    k: float((parsed.get(k) or {}).get("score_0_10"))
                    for k in PV_PARTS
                    if (parsed.get(k) or {}).get("score_0_10") is not None
                },
            }

    q_sol = quality_stats(sol_q, "sol_sep1_15")
    q_terra = quality_stats(terra_q, "terra_sep16_21")
    q_all = quality_stats(quality_run, "all_run")

    v001 = {}
    if V001_JSON.exists():
        prev = json.loads(V001_JSON.read_text(encoding="utf-8"))
        v001 = {
            "sol": prev.get("quality", {}).get("sol"),
            "terra": prev.get("quality", {}).get("terra"),
            "all": prev.get("quality", {}).get("all"),
            "spend_quality": (prev.get("spend_breakdown") or {}).get("quality"),
        }

    # Winner: higher mean per-dim Spearman on Terra window (decision target) + top-50
    def score_block(b: dict[str, Any] | None) -> float:
        if not b:
            return -1.0
        dims = [b["per_dim"][d]["spearman"] or 0 for d in QUALITY_DIMS]
        top50 = b.get("overlaps", {}).get("top_50", {}).get("overlap") or 0
        return statistics.mean(dims) + 0.01 * top50

    winner = "v002" if score_block(q_terra) >= score_block(v001.get("terra")) else "v001"

    summary = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "model": JEV_MODEL_PINNED,
        "policy": "quality_v002",
        "budget": {"cap": args.max_cost_usd, "spent": spent, "stopped": budget.stopped},
        "timing": {"quality_wall_s": wall, "n": len(quality_run)},
        "per_1000": {
            "cost_usd": (1000 * spent / len(quality_run)) if quality_run else None,
            "wall_s": (1000 * wall / len(quality_run)) if quality_run else None,
        },
        "v002": {"sol": q_sol, "terra": q_terra, "all": q_all},
        "v001_reference": v001,
        "winner_for_csv": winner,
        "n_ok": sum(1 for p in quality_run if p.get("jev_ok")),
    }

    PER_PAPER.write_text(
        json.dumps(
            {
                "model": JEV_MODEL_PINNED,
                "policy": "quality_v002",
                "source": "jev_j1b_quality_v002",
                "generated_at": summary["generated_at"],
                "papers": per_paper,
            },
            indent=2,
        ),
        encoding="utf-8",
    )
    JSON_OUT.write_text(json.dumps(summary, indent=2, default=str), encoding="utf-8")

    lines = [
        "# Jev quality v002 vs v001 — STOP",
        "",
        f"**Generated:** {summary['generated_at']}  ",
        f"**Model:** `{JEV_MODEL_PINNED}` · **Policy:** `quality_v002`  ",
        f"**Spend:** ${spent:.4f} / ${args.max_cost_usd:.2f}  ",
        f"**N:** {len(quality_run)} (sol={len(sol_q)}, terra={len(terra_q)}) · ok={summary['n_ok']}  ",
        f"**Winner for CSV:** **{winner}** (by Terra mean per-dim Spearman + top-50)",
        "",
        "## Design changes (v002)",
        "",
        "- 5–6 observable criteria levels (no adverb ladders)",
        "- No cross-question instructions",
        "- `professional_value` = mean(`decision_relevance_eng`, `decision_relevance_product`)",
        "- Dropped “ignore author prestige”",
        "- Composite weights unchanged; evidence still only via evidence_factor",
        "",
        "## (a) Per-dimension Spearman — side by side",
        "",
        "### vs Sol (Sep 1–15)",
        "",
        "| Dimension | v001 | v002 | Δ |",
        "|---|---:|---:|---:|",
    ]
    v001_sol = (v001.get("sol") or {}).get("per_dim") or {}
    for d in QUALITY_DIMS:
        a = (v001_sol.get(d) or {}).get("spearman")
        b = q_sol["per_dim"][d]["spearman"]
        delta = (b - a) if a is not None and b is not None else None
        lines.append(f"| {d} | {_fmt(a)} | {_fmt(b)} | {_fmt(delta)} |")
    lines += [
        "",
        f"Composite Spearman: v001 **{_fmt((v001.get('sol') or {}).get('composite_spearman'))}** · "
        f"v002 **{_fmt(q_sol['composite_spearman'])}**",
        f"Top-20 / Top-50: v001 "
        f"**{(v001.get('sol') or {}).get('overlaps', {}).get('top_20', {}).get('overlap', 'n/a')}/20** / "
        f"**{(v001.get('sol') or {}).get('overlaps', {}).get('top_50', {}).get('overlap', 'n/a')}/50** · "
        f"v002 **{q_sol['overlaps']['top_20']['overlap']}/20** / "
        f"**{q_sol['overlaps']['top_50']['overlap']}/50**",
        "",
        "### vs Terra (Sep 16–21)",
        "",
        "| Dimension | v001 | v002 | Δ |",
        "|---|---:|---:|---:|",
    ]
    v001_terra = (v001.get("terra") or {}).get("per_dim") or {}
    for d in QUALITY_DIMS:
        a = (v001_terra.get(d) or {}).get("spearman")
        b = q_terra["per_dim"][d]["spearman"]
        delta = (b - a) if a is not None and b is not None else None
        lines.append(f"| {d} | {_fmt(a)} | {_fmt(b)} | {_fmt(delta)} |")
    lines += [
        "",
        f"Composite Spearman: v001 **{_fmt((v001.get('terra') or {}).get('composite_spearman'))}** · "
        f"v002 **{_fmt(q_terra['composite_spearman'])}**",
        f"Top-20 / Top-50: v001 "
        f"**{(v001.get('terra') or {}).get('overlaps', {}).get('top_20', {}).get('overlap', 'n/a')}/20** / "
        f"**{(v001.get('terra') or {}).get('overlaps', {}).get('top_50', {}).get('overlap', 'n/a')}/50** · "
        f"v002 **{q_terra['overlaps']['top_20']['overlap']}/20** / "
        f"**{q_terra['overlaps']['top_50']['overlap']}/50**",
        "",
        "## Confidence bands (v002)",
        "",
        f"Max mean confidence: **{_fmt(q_all['max_confidence'], 3)}** · "
        f"Any ≥0.9: **{q_all['any_confidence_ge_0_9']}**",
        "",
        "### Sol",
        "",
        "| Band | N | composite MAE |",
        "|---|---:|---:|",
    ]
    for b in q_sol["confidence_bands"]:
        lines.append(f"| [{b['lo']:.1f},{b['hi']:.1f}) | {b['n']} | {_fmt(b['composite_mae'], 2)} |")
    lines += ["", "### Terra", "", "| Band | N | composite MAE |", "|---|---:|---:|"]
    for b in q_terra["confidence_bands"]:
        lines.append(f"| [{b['lo']:.1f},{b['hi']:.1f}) | {b['n']} | {_fmt(b['composite_mae'], 2)} |")
    if not q_all["any_confidence_ge_0_9"]:
        lines += [
            "",
            "**Confidence still never reaches 0.9** — rubric levels may still not be "
            "discriminating enough (or the abstract state is under-informative).",
        ]
    lines += [
        "",
        f"## Cost / wall (v002 quality)",
        "",
        f"${_fmt(summary['per_1000']['cost_usd'], 4)} / 1k · "
        f"{_fmt(summary['per_1000']['wall_s'], 1)} s / 1k · "
        f"total ${spent:.4f} in {wall:.0f}s",
        "",
        "## STOP",
        "",
        f"- Per-paper cache: `{PER_PAPER.relative_to(ROOT)}`",
        f"- Next: `export_terra_vs_jev_1000.py` using **{winner}**",
        "",
    ]
    REPORT.write_text("\n".join(lines), encoding="utf-8")
    print(f"wrote {REPORT}", flush=True)
    print(json.dumps({"spent": spent, "winner": winner, "n_ok": summary["n_ok"],
                      "terra_top50": q_terra["overlaps"]["top_50"]["overlap"],
                      "max_conf": q_all["max_confidence"]}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
