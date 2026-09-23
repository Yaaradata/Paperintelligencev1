#!/usr/bin/env python3
"""Phase J1b — DB-backed Jev re-measure (no cascade; cap $2).

  PYTHONPATH=src python3 scripts/jev_j1b_eval.py --allow-paid --max-cost-usd 2

Writes reports/review_fixes/jev_j1b.md (+ .json). Does not change pipeline defaults.
"""

from __future__ import annotations

import argparse
import json
import math
import random
import statistics
import sys
import time
from collections import Counter, defaultdict
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from paper_intelligence.common.budget import BudgetCap  # noqa: E402
from paper_intelligence.common.config import GATE_PERCENTILE, require_model_priced  # noqa: E402
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

REPORT = ROOT / "reports" / "review_fixes" / "jev_j1b.md"
JSON_OUT = ROOT / "reports" / "review_fixes" / "jev_j1b.json"
SEAT_VAL = ROOT / "reports" / "review_fixes" / "seat_validation_set.json"

RANK_DIMS = ("technical_significance", "apparent_novelty", "evidence_strength")
SCREEN_DIMS = ("ai_relevance",) + RANK_DIMS
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


def _args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--allow-paid", action="store_true")
    p.add_argument("--max-cost-usd", type=float, default=2.0)
    p.add_argument("--concurrency", type=int, default=8)
    p.add_argument("--seed", type=int, default=42)
    p.add_argument("--screen-target", type=int, default=450)
    p.add_argument("--quality-cap", type=int, default=0, help="0 = all eligible")
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


def _keep_n(n: int, pct: float) -> int:
    if n <= 0:
        return 0
    return max(1, int(round(n * (pct / 100.0))))


def _rank_mean(scores: dict[str, float]) -> float:
    return sum(float(scores[d]) for d in RANK_DIMS) / len(RANK_DIMS)


def _composite(scores: dict[str, float]) -> float:
    q = sum(Q_WEIGHTS[d] * float(scores[d]) for d in Q_WEIGHTS)
    ef = 0.70 + 0.03 * float(scores["evidence_strength"])
    return min(10.0, q * ef)


def _confirm_grants(conn) -> dict[str, Any]:
    who = conn.execute("SELECT current_user AS u").fetchone()["u"]
    usage = conn.execute(
        "SELECT has_schema_privilege(current_user,'paper_intelligence','USAGE') ok"
    ).fetchone()["ok"]
    sel = conn.execute(
        "SELECT has_table_privilege(current_user,'paper_intelligence.papers','SELECT') ok"
    ).fetchone()["ok"]
    n = conn.execute("SELECT count(*) n FROM paper_intelligence.papers").fetchone()["n"]
    return {"user": who, "pi_usage": bool(usage), "papers_select": bool(sel), "papers": int(n)}


def _load_screens(conn) -> list[dict[str, Any]]:
    rows = conn.execute(
        """
        SELECT DISTINCT ON (q.content_item_id)
          q.content_item_id,
          p.title,
          p.abstract,
          p.arxiv_id,
          p.published_at::date AS published_date,
          q.result_json,
          q.model AS screen_model,
          q.created_at
        FROM paper_intelligence.paper_classification_results q
        JOIN paper_intelligence.papers p ON p.paper_id = q.content_item_id
        WHERE q.task_type = 'screen'
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
        scores = {d: rj.get(d) for d in SCREEN_DIMS}
        if any(scores[d] is None for d in SCREEN_DIMS):
            continue
        gate = (rj.get("gate") or {})
        passed = gate.get("passed")
        if passed is None:
            passed = float(scores["ai_relevance"]) >= 5.0
        try:
            scores_f = {d: float(scores[d]) for d in SCREEN_DIMS}
        except (TypeError, ValueError):
            continue
        out.append(
            {
                "content_item_id": int(r["content_item_id"]),
                "title": r["title"] or "",
                "abstract": r["abstract"] or "",
                "arxiv_id": r["arxiv_id"],
                "published_date": str(r["published_date"]),
                "llm_scores": scores_f,
                "llm_gate_passed": bool(passed),
                "llm_rank_mean": _rank_mean(scores_f),
            }
        )
    return out


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
        model = r["model"] or ""
        pub = str(r["published_date"])
        family = None
        if "sol" in model and pub < "2026-09-16":
            family = "sol"
        elif "terra" in model and pub >= "2026-09-16":
            family = "terra"
        elif "sol" in model:
            family = "sol"
        elif "terra" in model:
            family = "terra"
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
                "llm_final": float(comp["final"])
                if isinstance(comp, dict) and comp.get("final") is not None
                else None,
            }
        )
    return out


def _build_screen_sample(screens: list[dict[str, Any]], *, target: int, seed: int) -> list[dict[str, Any]]:
    rng = random.Random(seed)
    by_id = {p["content_item_id"]: p for p in screens}
    selected: dict[int, str] = {}

    def add(cid: int, reason: str) -> None:
        if cid in by_id and cid not in selected:
            selected[cid] = reason

    # All Sep16-21 gate failures (~100)
    for p in screens:
        if p["published_date"] >= "2026-09-16" and not p["llm_gate_passed"]:
            add(p["content_item_id"], "gate_failure_sep16_21")

    survivors = [p for p in screens if p["llm_gate_passed"]]
    # Stratify by rank_mean quintiles
    survivors_sorted = sorted(survivors, key=lambda p: p["llm_rank_mean"])
    if survivors_sorted:
        qn = 5
        per = max(20, target // 10)
        for qi in range(qn):
            lo = int(qi * len(survivors_sorted) / qn)
            hi = int((qi + 1) * len(survivors_sorted) / qn)
            bucket = survivors_sorted[lo:hi]
            rng.shuffle(bucket)
            for p in bucket[:per]:
                add(p["content_item_id"], f"stratum_q{qi+1}")

    # Near percentile boundaries per day for 15/50/75
    by_day: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for p in survivors:
        by_day[p["published_date"]].append(p)
    for day, rows in by_day.items():
        rows = sorted(rows, key=lambda p: (-p["llm_rank_mean"], p["content_item_id"]))
        n = len(rows)
        for pct in (15, 50, 75):
            k = _keep_n(n, pct)
            # take ±3 around the cut
            for idx in range(max(0, k - 3), min(n, k + 3)):
                add(rows[idx]["content_item_id"], f"boundary_{pct}_{day}")

    # Fill to target with random survivors
    remain = [p for p in survivors if p["content_item_id"] not in selected]
    rng.shuffle(remain)
    for p in remain:
        if len(selected) >= target:
            break
        add(p["content_item_id"], "fill")

    out = []
    for cid, reason in selected.items():
        rec = dict(by_id[cid])
        rec["sample_reason"] = reason
        out.append(rec)
    return out


def _top_slice_ids(papers: list[dict[str, Any]], *, score_key: str, pct: float) -> set[int]:
    by_day: dict[str, list[tuple[float, int]]] = defaultdict(list)
    for p in papers:
        if not p.get("llm_gate_passed"):
            continue
        if score_key == "llm":
            mean = p["llm_rank_mean"]
        else:
            mean = p.get("jev_rank_mean")
            if mean is None:
                continue
            # For Jev top-slice, also require Jev gate pass when available
            if p.get("jev_gate_passed") is False:
                continue
        by_day[p["published_date"]].append((float(mean), int(p["content_item_id"])))
    selected: set[int] = set()
    for rows in by_day.values():
        rows.sort(key=lambda t: (-t[0], t[1]))
        keep = _keep_n(len(rows), pct)
        selected.update(cid for _, cid in rows[:keep])
    return selected


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
        "actual_cost_usd": resp.actual_cost,
        "estimated_cost_usd": resp.estimated_cost,
        "input_tokens": resp.input_tokens,
        "output_tokens": resp.output_tokens,
        "model": resp.model,
        "parsed": parsed,
        "answers": resp.answers,
    }


def _run_pool(papers: list[dict[str, Any]], policy, questions, budget, concurrency: int, label: str) -> dict[int, dict]:
    sink: dict[int, dict] = {}
    print(f"=== {label} n={len(papers)} ===", flush=True)
    with ThreadPoolExecutor(max_workers=concurrency) as ex:
        futs = [ex.submit(_call, p, policy, questions, budget) for p in papers]
        done = 0
        for fut in as_completed(futs):
            rec = fut.result()
            sink[int(rec["content_item_id"])] = rec
            done += 1
            if done % 50 == 0 or done == len(futs):
                print(f"  {label} {done}/{len(futs)} spent=${budget.actual_usd:.4f}", flush=True)
    return sink


def main() -> int:
    args = _args()
    if not args.dry_run and not args.allow_paid:
        print("Need --allow-paid", file=sys.stderr)
        return 2
    require_model_priced(JEV_MODEL_PINNED)

    with connect() as conn:
        grants = _confirm_grants(conn)
        print("grants:", grants, flush=True)
        if not (grants["pi_usage"] and grants["papers_select"]):
            print("STOP: neural_rw lacks paper_intelligence access", file=sys.stderr)
            return 3
        screens = _load_screens(conn)
        qualities = _load_quality(conn)

    print(f"screens={len(screens)} qualities={len(qualities)}", flush=True)
    screen_sample = _build_screen_sample(screens, target=args.screen_target, seed=args.seed)
    print(
        f"screen_sample={len(screen_sample)} reasons={Counter(p['sample_reason'].split('_')[0] for p in screen_sample)}",
        flush=True,
    )

    # Quality set: prefer Sol on sep1-15 + Terra on sep16-21 (canonical windows)
    sol_q = [p for p in qualities if p["family"] == "sol" and p["published_date"] < "2026-09-16"]
    terra_q = [p for p in qualities if p["family"] == "terra" and p["published_date"] >= "2026-09-16"]
    quality_run = list({p["content_item_id"]: p for p in sol_q + terra_q}.values())
    if args.quality_cap and args.quality_cap > 0:
        rng = random.Random(args.seed)
        rng.shuffle(quality_run)
        quality_run = quality_run[: args.quality_cap]
    print(f"quality_run={len(quality_run)} sol={len(sol_q)} terra={len(terra_q)}", flush=True)

    seat_val = json.loads(SEAT_VAL.read_text(encoding="utf-8"))
    audience_ids = list(seat_val.get("all_content_item_ids") or [])
    past_picks = seat_val.get("past_editorial_picks") or []
    # Enrich audience papers from DB
    with connect() as conn:
        aud_rows = conn.execute(
            """
            SELECT paper_id AS content_item_id, title, abstract, arxiv_id,
                   published_at::date AS published_date
            FROM paper_intelligence.papers
            WHERE paper_id = ANY(%s)
            """,
            (audience_ids,),
        ).fetchall()
    aud_by_id = {int(r["content_item_id"]): dict(r) for r in aud_rows}
    for r in aud_by_id.values():
        r["published_date"] = str(r["published_date"])
        r["title"] = r.get("title") or ""
        r["abstract"] = r.get("abstract") or ""
    audience_papers = [aud_by_id[i] for i in audience_ids if i in aud_by_id]
    print(f"audience_papers={len(audience_papers)} past_picks={len(past_picks)}", flush=True)

    if args.dry_run:
        JSON_OUT.write_text(
            json.dumps(
                {
                    "dry_run": True,
                    "grants": grants,
                    "screen_sample": len(screen_sample),
                    "quality_run": len(quality_run),
                    "sol": len(sol_q),
                    "terra": len(terra_q),
                    "audience": len(audience_papers),
                },
                indent=2,
            ),
            encoding="utf-8",
        )
        return 0

    screen_pol = load_systemone_policy("screen", "v001")
    quality_pol = load_systemone_policy("quality", "v001")
    audience_pol = load_systemone_policy("audience", "v001")
    screen_q = build_questions(screen_pol)
    quality_q = build_questions(quality_pol)
    audience_q = build_questions(audience_pol)

    budget = BudgetCap(args.max_cost_usd)
    t0 = time.perf_counter()
    screen_res = _run_pool(screen_sample, screen_pol, screen_q, budget, args.concurrency, "screen")
    t_screen = time.perf_counter() - t0
    spend_after_screen = budget.actual_usd

    t1 = time.perf_counter()
    quality_res = _run_pool(quality_run, quality_pol, quality_q, budget, args.concurrency, "quality")
    t_quality = time.perf_counter() - t1
    spend_after_quality = budget.actual_usd

    t2 = time.perf_counter()
    audience_res = _run_pool(audience_papers, audience_pol, audience_q, budget, args.concurrency, "audience")
    t_audience = time.perf_counter() - t2
    total_spend = budget.actual_usd

    # ---- Screen analysis ----
    for p in screen_sample:
        rec = screen_res.get(p["content_item_id"]) or {}
        parsed = rec.get("parsed") or {}
        jev = {}
        for d in SCREEN_DIMS:
            cell = parsed.get(d) or {}
            if isinstance(cell, dict) and cell.get("score_0_10") is not None:
                jev[d] = float(cell["score_0_10"])
        noul = (parsed.get("gate_ai_relevance") or {}).get("noul")
        p["jev_scores"] = jev
        p["jev_noul"] = noul
        p["jev_gate_passed"] = (
            float(noul) >= 0.5
            if noul is not None
            else (float(jev["ai_relevance"]) >= 5.0 if "ai_relevance" in jev else None)
        )
        p["jev_rank_mean"] = _rank_mean(jev) if all(d in jev for d in RANK_DIMS) else None
        p["jev_ok"] = bool(rec.get("ok"))
        p["jev_confidence"] = parsed.get("_mean_confidence")

    screen_corr = {}
    for d in SCREEN_DIMS + ("rank_mean",):
        xs, ys = [], []
        for p in screen_sample:
            if d == "rank_mean":
                if p.get("llm_rank_mean") is not None and p.get("jev_rank_mean") is not None:
                    xs.append(float(p["llm_rank_mean"]))
                    ys.append(float(p["jev_rank_mean"]))
            elif d in p["llm_scores"] and d in p.get("jev_scores", {}):
                xs.append(float(p["llm_scores"][d]))
                ys.append(float(p["jev_scores"][d]))
        screen_corr[d] = {"spearman": _spearman(xs, ys), "n": len(xs)}

    # quality lookup for flipped-in papers
    q_by_id = {p["content_item_id"]: p for p in qualities}
    slice_tables = {}
    for pct in (15, 50, 75):
        llm_ids = _top_slice_ids(screen_sample, score_key="llm", pct=pct)
        # For fair comparison use same gate-pass set; Jev ranking among LLM gate-passers
        # also compute Jev-native (Jev gate)
        jev_ids = _top_slice_ids(screen_sample, score_key="jev", pct=pct)
        flip_in = sorted(jev_ids - llm_ids)
        flip_out = sorted(llm_ids - jev_ids)
        flip_in_with_q = []
        for cid in flip_in:
            if cid in q_by_id:
                qq = q_by_id[cid]
                flip_in_with_q.append(
                    {
                        "content_item_id": cid,
                        "quality_score": qq.get("llm_composite_quality"),
                        "final": qq.get("llm_final"),
                        "model": qq.get("model"),
                        "title": (qq.get("title") or "")[:80],
                    }
                )
        slice_tables[str(pct)] = {
            "llm_selected": len(llm_ids),
            "jev_selected": len(jev_ids),
            "flip_in": len(flip_in),
            "flip_out": len(flip_out),
            "flip_in_pct_of_selected": (len(flip_in) / len(llm_ids) * 100) if llm_ids else None,
            "flip_out_pct_of_selected": (len(flip_out) / len(llm_ids) * 100) if llm_ids else None,
            "jaccard": (len(llm_ids & jev_ids) / len(llm_ids | jev_ids)) if (llm_ids or jev_ids) else None,
            "flip_in_with_quality_n": len(flip_in_with_q),
            "flip_in_with_quality": flip_in_with_q[:40],
            "flip_in_quality_mean": statistics.mean([x["quality_score"] for x in flip_in_with_q])
            if flip_in_with_q
            else None,
        }

    # ---- Quality analysis ----
    def attach_jev_quality(papers: list[dict[str, Any]], results: dict[int, dict]) -> None:
        for p in papers:
            rec = results.get(p["content_item_id"]) or {}
            parsed = rec.get("parsed") or {}
            jev = {}
            confs = []
            for d in QUALITY_DIMS:
                cell = parsed.get(d) or {}
                if isinstance(cell, dict) and cell.get("score_0_10") is not None:
                    jev[d] = float(cell["score_0_10"])
                    if cell.get("confidence") is not None:
                        confs.append(float(cell["confidence"]))
            p["jev_scores"] = jev
            p["jev_ok"] = bool(rec.get("ok")) and len(jev) == len(QUALITY_DIMS)
            p["jev_composite"] = _composite(jev) if p["jev_ok"] else None
            p["jev_confidence"] = statistics.mean(confs) if confs else None

    attach_jev_quality(quality_run, quality_res)

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
        # composite overlap
        llm_ranked = sorted(ok, key=lambda p: (-float(p["llm_composite_quality"]), p["content_item_id"]))
        jev_ranked = sorted(ok, key=lambda p: (-float(p["jev_composite"]), p["content_item_id"]))
        overlaps = {}
        for k in (20, 50):
            a = {p["content_item_id"] for p in llm_ranked[:k]}
            b = {p["content_item_id"] for p in jev_ranked[:k]}
            overlaps[f"top_{k}"] = {
                "overlap": len(a & b),
                "of": k,
                "pct": len(a & b) / k if k else None,
            }
        # confidence bands vs mean |delta| composite
        bands = []
        for lo, hi in ((0.0, 0.6), (0.6, 0.7), (0.7, 0.8), (0.8, 0.9), (0.9, 1.01)):
            sub = [
                p
                for p in ok
                if p.get("jev_confidence") is not None and lo <= float(p["jev_confidence"]) < hi
            ]
            if not sub:
                bands.append({"lo": lo, "hi": hi, "n": 0, "composite_mae": None, "mean_dim_spearman": None})
                continue
            mae = statistics.mean(
                [
                    abs(float(p["llm_composite_quality"]) - float(p["jev_composite"]))
                    for p in sub
                ]
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
        }

    sol_subset = [p for p in quality_run if p["family"] == "sol" and p["published_date"] < "2026-09-16"]
    terra_subset = [
        p for p in quality_run if p["family"] == "terra" and p["published_date"] >= "2026-09-16"
    ]
    q_sol = quality_stats(sol_subset, "sol_sep1_15")
    q_terra = quality_stats(terra_subset, "terra_sep16_21")
    q_all = quality_stats(quality_run, "all_run")

    # cost/time per 1000 for quality
    q_ok_costs = [
        float((quality_res.get(p["content_item_id"]) or {}).get("billable_cost_usd") or 0)
        for p in quality_run
        if (quality_res.get(p["content_item_id"]) or {}).get("ok")
    ]
    q_pp = statistics.mean(q_ok_costs) if q_ok_costs else None
    q_wall_pp = t_quality / max(1, len(quality_run))

    # ---- Audience seats ----
    pick_by_id = {int(p["content_item_id"]): p for p in past_picks}
    aud_scores = []
    for p in audience_papers:
        rec = audience_res.get(p["content_item_id"]) or {}
        parsed = rec.get("parsed") or {}
        tech = (parsed.get("tech_relevance") or {}).get("score_0_10")
        prod = (parsed.get("product_relevance") or {}).get("score_0_10")
        conf = parsed.get("_mean_confidence")
        pick = pick_by_id.get(p["content_item_id"])
        aud_scores.append(
            {
                "content_item_id": p["content_item_id"],
                "tech_relevance": float(tech) if tech is not None else None,
                "product_relevance": float(prod) if prod is not None else None,
                "confidence": conf,
                "ok": bool(rec.get("ok")),
                "pick_seat": (pick or {}).get("seat"),
                "pick_role": (pick or {}).get("role"),
                "is_past_pick": pick is not None,
            }
        )
    tech_picks = [a for a in aud_scores if a.get("pick_seat") == "TECH" and a.get("tech_relevance") is not None]
    prod_picks = [
        a for a in aud_scores if a.get("pick_seat") == "PRODUCT" and a.get("product_relevance") is not None
    ]
    stratified_only = [a for a in aud_scores if not a["is_past_pick"] and a.get("tech_relevance") is not None]

    def both_one_neither(rows: list[dict[str, Any]], thr: float) -> dict[str, int]:
        both = one = neither = 0
        for a in rows:
            t = a.get("tech_relevance")
            p = a.get("product_relevance")
            if t is None or p is None:
                continue
            th = t >= thr
            ph = p >= thr
            if th and ph:
                both += 1
            elif th or ph:
                one += 1
            else:
                neither += 1
        return {"both": both, "one": one, "neither": neither, "n": both + one + neither}

    thr_table = {str(t): both_one_neither(aud_scores, t) for t in (5.0, 6.0, 7.0, 8.0)}

    # propose thresholds from past picks: p25 of pick seat scores
    def propose(rows: list[dict[str, Any]], key: str) -> float | None:
        vals = sorted(float(a[key]) for a in rows if a.get(key) is not None)
        if len(vals) < 2:
            return statistics.mean(vals) if vals else None
        # slightly below min of winners if few; else ~p25
        idx = max(0, int(0.25 * (len(vals) - 1)))
        return vals[idx]

    proposed_tech = propose(tech_picks, "tech_relevance")
    proposed_prod = propose(prod_picks, "product_relevance")

    # ---- Architecture proposal ----
    # Hold condition: Spearman >= 0.75 per dim AND top-50 overlap >= 35/50
    # Evaluate on combined ok set preferring terra+sol separately; use all_run for proposal gate
    dims_ok = all(
        (q_all["per_dim"][d]["spearman"] or 0) >= 0.75 for d in QUALITY_DIMS
    )
    top50 = q_all["overlaps"]["top_50"]["overlap"]
    hold = bool(dims_ok and top50 >= 35)

    # Cost per window Sep16-21 style: ~2535 screen survivors, today quality ~380 at 15% historically
    # but current GATE=75 → more quality. Use Sep16-21 actual: 2535 pass, 380 quality at then-15%.
    # For GATE=75: keep ~75% of ~2535 ≈ 1900 quality LLM calls.
    survivors = 2535
    today_75_quality_n = _keep_n(survivors, 75)
    # Terra unit from Sep16-21: $1.2344/380 ≈ $0.00325
    terra_pp = 1.2344 / 380.0
    llm_screen_pp = 0.2504 / 2638.0
    today_cost = {
        "screen_llm": survivors * llm_screen_pp,  # approx survivors≈screened keep
        "quality_llm_75": today_75_quality_n * terra_pp,
    }
    today_cost["total"] = today_cost["screen_llm"] + today_cost["quality_llm_75"]
    # Proposed: Jev quality on ALL survivors + LLM prose on top ~150
    # Use measured Jev quality $/paper; prose ≈ current Terra full call (conservative)
    # or slightly less — use Terra unit as prose proxy
    proposed_cost = {
        "jev_quality_all_survivors": survivors * (q_pp or 0),
        "llm_prose_top_150": 150 * terra_pp,
    }
    proposed_cost["total"] = proposed_cost["jev_quality_all_survivors"] + proposed_cost["llm_prose_top_150"]

    summary = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "grants": grants,
        "model": JEV_MODEL_PINNED,
        "budget": {"cap": args.max_cost_usd, "spent": total_spend, "stopped": budget.stopped},
        "timing": {
            "screen_wall_s": t_screen,
            "quality_wall_s": t_quality,
            "audience_wall_s": t_audience,
        },
        "spend_breakdown": {
            "screen": spend_after_screen,
            "quality": spend_after_quality - spend_after_screen,
            "audience": total_spend - spend_after_quality,
        },
        "screen": {
            "sample_n": len(screen_sample),
            "sample_reasons": dict(Counter(p["sample_reason"] for p in screen_sample)),
            "gate_failures_in_sample": sum(
                1 for p in screen_sample if p["sample_reason"] == "gate_failure_sep16_21"
            ),
            "spearman": screen_corr,
            "top_slice": slice_tables,
            "ok": sum(1 for r in screen_res.values() if r.get("ok")),
        },
        "quality": {
            "note": "Used Sol for Sep1–15 pubs and Terra for Sep16–21 pubs (canonical windows). "
            "Requested ~1887; actual eligible Sol+Terra window set reported below.",
            "n_sol_sep1_15": len(sol_q),
            "n_terra_sep16_21": len(terra_q),
            "n_run": len(quality_run),
            "sol": q_sol,
            "terra": q_terra,
            "all": q_all,
            "per_1000": {
                "cost_usd": (1000 * q_pp) if q_pp is not None else None,
                "wall_s": 1000 * q_wall_pp,
                "per_paper_cost_usd": q_pp,
            },
            "hold_condition": {
                "spearman_ge_0_75_all_dims": dims_ok,
                "top50_overlap_ge_35": top50 >= 35,
                "top50_overlap": top50,
                "holds": hold,
            },
        },
        "audience": {
            "n": len(aud_scores),
            "ok": sum(1 for a in aud_scores if a["ok"]),
            "tech_picks": {
                "n": len(tech_picks),
                "tech_relevance_mean": statistics.mean([a["tech_relevance"] for a in tech_picks])
                if tech_picks
                else None,
                "tech_relevance_min": min((a["tech_relevance"] for a in tech_picks), default=None),
                "scores": [
                    {
                        "id": a["content_item_id"],
                        "role": a["pick_role"],
                        "tech": a["tech_relevance"],
                        "product": a["product_relevance"],
                    }
                    for a in tech_picks
                ],
            },
            "product_picks": {
                "n": len(prod_picks),
                "product_relevance_mean": statistics.mean(
                    [a["product_relevance"] for a in prod_picks]
                )
                if prod_picks
                else None,
                "product_relevance_min": min(
                    (a["product_relevance"] for a in prod_picks), default=None
                ),
                "scores": [
                    {
                        "id": a["content_item_id"],
                        "role": a["pick_role"],
                        "tech": a["tech_relevance"],
                        "product": a["product_relevance"],
                    }
                    for a in prod_picks
                ],
            },
            "stratified_n": len(stratified_only),
            "both_one_neither_by_threshold": thr_table,
            "proposed_tech_pool_min": proposed_tech,
            "proposed_product_pool_min": proposed_prod,
        },
        "architecture_proposal": {
            "condition_holds": hold,
            "design": (
                "Jev scores ALL screen survivors on the six rubric dimensions; "
                "drop cost-driven quality router; LLM writes so_what + reason_not_higher "
                "only for top ~150 editorial candidates."
                if hold
                else "Hold condition not met — do not adopt Jev-for-all-survivors design yet."
            ),
            "today_gate75_window_cost_usd": today_cost,
            "proposed_window_cost_usd": proposed_cost if hold else None,
            "savings_usd": (today_cost["total"] - proposed_cost["total"]) if hold else None,
        },
    }

    JSON_OUT.write_text(json.dumps(summary, indent=2, default=str), encoding="utf-8")

    # Markdown
    def pct(x):
        return "n/a" if x is None else f"{100*x:.1f}%"

    def fmt(x, nd=3):
        return "n/a" if x is None else f"{x:.{nd}f}"

    lines = [
        "# Jev J1b — STOP",
        "",
        f"**Generated:** {summary['generated_at']}  ",
        f"**Model:** `{JEV_MODEL_PINNED}`  ",
        f"**Spend:** ${total_spend:.4f} / ${args.max_cost_usd:.2f}  ",
        "**Cascade:** not started  ",
        f"**DB grants:** user=`{grants['user']}` pi_usage={grants['pi_usage']} "
        f"papers_select={grants['papers_select']} papers={grants['papers']}",
        "",
        "## 0. Grant confirmation",
        "",
        "`GRANT USAGE ON SCHEMA paper_intelligence TO neural_rw` (+ table SELECT) is in effect. "
        "This evaluation ran against the live DB (title/abstract + classification rows), not caches.",
        "",
        "## 1. Screen — top-slice is the decision",
        "",
        f"Sample **{len(screen_sample)}** papers stratified across screen rank_mean, "
        f"percentile boundaries (15/50/75), plus **{summary['screen']['gate_failures_in_sample']}** "
        "Sep 16–21 gate failures.",
        "",
        "### Spearman (LLM vs Jev)",
        "",
        "| Dimension | Spearman | N |",
        "|---|---:|---:|",
    ]
    for d, st in screen_corr.items():
        lines.append(f"| {d} | {fmt(st['spearman'])} | {st['n']} |")

    lines += [
        "",
        "### Top-slice agreement at GATE_PERCENTILE 15 / 50 / 75",
        "",
        "| Pct | LLM sel | Jev sel | Flip in | Flip out | In % of LLM sel | Out % | Jaccard | Flip-in with quality | Mean Q of flip-in |",
        "|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for pct_k in ("15", "50", "75"):
        t = slice_tables[pct_k]
        lines.append(
            f"| {pct_k} | {t['llm_selected']} | {t['jev_selected']} | {t['flip_in']} | {t['flip_out']} | "
            f"{fmt(t['flip_in_pct_of_selected'],1)}% | {fmt(t['flip_out_pct_of_selected'],1)}% | "
            f"{fmt(t['jaccard'])} | {t['flip_in_with_quality_n']} | {fmt(t['flip_in_quality_mean'],2)} |"
        )

    lines += [
        "",
        "### Flip-in papers that already have quality (sample)",
        "",
    ]
    for pct_k in ("15", "75"):
        rows = slice_tables[pct_k]["flip_in_with_quality"][:15]
        lines.append(f"**At {pct_k}%:**")
        if not rows:
            lines.append("- (none with quality scores)")
        else:
            for r in rows:
                lines.append(
                    f"- `{r['content_item_id']}` Q={fmt(r['quality_score'],2)} "
                    f"final={fmt(r['final'],2)} ({r['model']}): {r['title']}"
                )
        lines.append("")

    lines += [
        "## 2. Quality rubric via Jev",
        "",
        f"Eligible: **Sol Sep1–15 = {len(sol_q)}**, **Terra Sep16–21 = {len(terra_q)}**, "
        f"run N = **{len(quality_run)}** (spec cited ~1887; this is the current DB window set).",
        f"Cost/1k: **${fmt((1000*q_pp) if q_pp else None, 4)}** · wall/1k ≈ **{fmt(1000*q_wall_pp,1)} s** "
        f"(${fmt(q_pp, 6)}/paper).",
        "",
    ]

    for block, title in ((q_sol, "vs Sol (Sep 1–15)"), (q_terra, "vs Terra (Sep 16–21)")):
        lines += [
            f"### {title} — n_ok={block['n_ok']}/{block['n_eligible']}",
            "",
            "| Dimension | Spearman | mean \\|Δ\\| | N |",
            "|---|---:|---:|---:|",
        ]
        for d in QUALITY_DIMS:
            st = block["per_dim"][d]
            lines.append(f"| {d} | {fmt(st['spearman'])} | {fmt(st['mae'],2)} | {st['n']} |")
        lines += [
            "",
            f"- Composite Spearman: **{fmt(block['composite_spearman'])}** · MAE: **{fmt(block['composite_mae'],2)}**",
            f"- Top-20 overlap: **{block['overlaps']['top_20']['overlap']}/20** · "
            f"Top-50: **{block['overlaps']['top_50']['overlap']}/50**",
            "",
            "Confidence bands (composite MAE):",
            "",
            "| Band | N | composite MAE |",
            "|---|---:|---:|",
        ]
        for b in block["confidence_bands"]:
            lines.append(f"| [{b['lo']:.1f},{b['hi']:.1f}) | {b['n']} | {fmt(b['composite_mae'],2)} |")
        lines.append("")

    lines += [
        "## 3. Audience seats vs editorial ground truth",
        "",
        f"Past TECH picks (n={len(tech_picks)}): mean tech_relevance="
        f"**{fmt(summary['audience']['tech_picks']['tech_relevance_mean'],2)}** "
        f"min={fmt(summary['audience']['tech_picks']['tech_relevance_min'],2)}",
        f"Past PRODUCT picks (n={len(prod_picks)}): mean product_relevance="
        f"**{fmt(summary['audience']['product_picks']['product_relevance_mean'],2)}** "
        f"min={fmt(summary['audience']['product_picks']['product_relevance_min'],2)}",
        "",
        "Pick-level scores:",
        "",
    ]
    for a in summary["audience"]["tech_picks"]["scores"]:
        lines.append(
            f"- TECH `{a['id']}` ({a['role']}): tech={fmt(a['tech'],1)} product={fmt(a['product'],1)}"
        )
    for a in summary["audience"]["product_picks"]["scores"]:
        lines.append(
            f"- PRODUCT `{a['id']}` ({a['role']}): tech={fmt(a['tech'],1)} product={fmt(a['product'],1)}"
        )

    lines += [
        "",
        "### Both / one / neither by threshold (full validation set)",
        "",
        "| Threshold | both | one | neither | N |",
        "|---:|---:|---:|---:|---:|",
    ]
    for thr, row in thr_table.items():
        lines.append(
            f"| {thr} | {row['both']} | {row['one']} | {row['neither']} | {row['n']} |"
        )
    lines += [
        "",
        f"**Proposed pool mins:** `TECH_POOL_MIN≈{fmt(proposed_tech,1)}` · "
        f"`PRODUCT_POOL_MIN≈{fmt(proposed_prod,1)}` (p25 of past picks on their seat score).",
        "",
        "## Architecture proposal (not implemented)",
        "",
        f"Hold condition (Spearman≥0.75 all dims **and** top-50 overlap≥35/50 on combined run): "
        f"**{'HOLDS' if hold else 'DOES NOT HOLD'}** "
        f"(top-50 overlap={top50}/50; all-dim≥0.75={dims_ok}).",
        "",
        summary["architecture_proposal"]["design"],
        "",
    ]
    if hold:
        lines += [
            "### Cost per Sep16–21-scale window (~2535 survivors)",
            "",
            f"| Design | Screen | Quality / prose | Total |",
            f"|---|---:|---:|---:|",
            f"| Today: LLM screen + GATE=75% full Terra quality (~{today_75_quality_n} papers) | "
            f"${today_cost['screen_llm']:.2f} | ${today_cost['quality_llm_75']:.2f} | "
            f"**${today_cost['total']:.2f}** |",
            f"| Proposed: Jev 6-dim on all survivors + LLM prose top 150 | "
            f"(screen unchanged/optional) | "
            f"${proposed_cost['jev_quality_all_survivors']:.2f} + "
            f"${proposed_cost['llm_prose_top_150']:.2f} | "
            f"**${proposed_cost['total']:.2f}** |",
            f"",
            f"Estimated savings vs today GATE=75 quality path: "
            f"**${summary['architecture_proposal']['savings_usd']:.2f}** / window "
            f"(screen LLM cost kept separate; main cut is dropping ~{today_75_quality_n - 150} full Terra calls).",
            "",
        ]
    else:
        lines += [
            "No adopt-now cost redesign — improve quality agreement first.",
            "",
        ]

    lines += [
        "## STOP",
        "",
        "- No `SCREEN_ENGINE` / `AUDIENCE_ENGINE` cascade.",
        "- No pipeline default changes.",
        f"- Artifacts: `{REPORT.relative_to(ROOT)}`, `{JSON_OUT.relative_to(ROOT)}`",
        "",
    ]
    REPORT.write_text("\n".join(lines), encoding="utf-8")
    print(f"wrote {REPORT}", flush=True)
    print(
        json.dumps(
            {
                "spent": total_spend,
                "hold": hold,
                "top50": top50,
                "sol_n": q_sol["n_ok"],
                "terra_n": q_terra["n_ok"],
            },
            indent=2,
        ),
        flush=True,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
