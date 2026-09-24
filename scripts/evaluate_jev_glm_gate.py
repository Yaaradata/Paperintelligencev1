#!/usr/bin/env python3
"""Evaluate jev_glm golden scores against baseline_v1.md (arithmetic gate).

  PYTHONPATH=src python3 scripts/evaluate_jev_glm_gate.py

Writes reports/golden/jev_glm_gate.json
"""

from __future__ import annotations

import json
import math
import statistics
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from paper_intelligence.db import connect  # noqa: E402
from paper_intelligence.quality.stage import RUBRIC_DIMENSIONS, WEIGHTS  # noqa: E402

REPORT_DIR = ROOT / "reports" / "golden"
GOLDEN_RUN = REPORT_DIR / "jev_glm_golden_run.json"
GATE_JSON = REPORT_DIR / "jev_glm_gate.json"
BASELINE_MD = REPORT_DIR / "baseline_v1.md"

# Intersection baseline (G3a) — Jev v001 column (same scoring family as jev_glm)
BASELINE_JEV_V001 = {
    "technical_significance": 0.248,
    "apparent_novelty": 0.321,
    "practical_applicability": 0.539,
    "professional_value": 0.615,
    "learning_value": 0.187,
    "evidence_strength": 0.394,
    "composite": 0.367,
    "recall_at_50": 0.591,
}


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


def _g3c_score(dims: dict[str, float]) -> float:
    intercept = 2.7158
    coefs = {
        "technical_significance": -0.9491,
        "apparent_novelty": 0.0406,
        "practical_applicability": 0.7221,
        "professional_value": 1.2236,
        "learning_value": -0.2747,
        "evidence_strength": -0.2047,
    }
    return intercept + sum(coefs[d] * float(dims[d]) for d in coefs)


def main() -> int:
    if not GOLDEN_RUN.exists():
        print(f"missing {GOLDEN_RUN}", file=sys.stderr)
        return 2
    meta = json.loads(GOLDEN_RUN.read_text(encoding="utf-8"))
    run_id = meta.get("run_id")
    if not run_id:
        print("golden run_id missing", file=sys.stderr)
        return 2

    with connect() as conn:
        humans = conn.execute(
            """
            SELECT paper_id, h_final_score, h_newsletter_verdict,
                   h_technical_significance, h_apparent_novelty,
                   h_practical_applicability, h_professional_value,
                   h_learning_value, h_evidence_strength
            FROM paper_intelligence.golden_human_scores
            WHERE labeller='subha' AND label_round='v1'
            """
        ).fetchall()
        eng = conn.execute(
            """
            SELECT content_item_id, result_json
            FROM paper_intelligence.paper_classification_results
            WHERE task_type='quality' AND run_id=%s::uuid
            """,
            (run_id,),
        ).fetchall()

    engine: dict[int, dict[str, Any]] = {}
    for r in eng:
        rj = r["result_json"] or {}
        if isinstance(rj, str):
            rj = json.loads(rj)
        if not all(rj.get(d) is not None for d in RUBRIC_DIMENSIONS):
            continue
        dims = {d: float(rj[d]) for d in RUBRIC_DIMENSIONS}
        comp = rj.get("composite") or {}
        quality = (
            float(comp["quality"])
            if isinstance(comp, dict) and comp.get("quality") is not None
            else sum(WEIGHTS[d] * dims[d] for d in WEIGHTS)
        )
        engine[int(r["content_item_id"])] = {
            "dims": dims,
            "composite": quality,
            "g3c": _g3c_score(dims),
        }

    if len(engine) < 150:
        verdict = "Cannot be determined"
        report = {
            "verdict": verdict,
            "n_scored": len(engine),
            "reason": f"n_scored={len(engine)} < 150",
            "run_id": run_id,
        }
        GATE_JSON.write_text(json.dumps(report, indent=2), encoding="utf-8")
        print(json.dumps(report, indent=2))
        return 0

    dims_out: dict[str, Any] = {}
    dim_pass = True
    for dim in RUBRIC_DIMENSIONS:
        xs, ys = [], []
        for h in humans:
            cid = int(h["paper_id"])
            if cid not in engine:
                continue
            hv = h.get(f"h_{dim}")
            if hv is None:
                continue
            xs.append(float(hv))
            ys.append(float(engine[cid]["dims"][dim]))
        sp = _spearman(xs, ys)
        base = BASELINE_JEV_V001[dim]
        floor = base - 0.05
        ok = sp is not None and sp >= floor
        if not ok:
            dim_pass = False
        dims_out[dim] = {
            "n": len(xs),
            "spearman": None if sp is None else round(sp, 3),
            "baseline": base,
            "delta": None if sp is None else round(sp - base, 3),
            "floor": round(floor, 3),
            "pass": ok,
        }

    # Composite + recall
    xs, ys, g3c_ys = [], [], []
    winners = []
    scored = []
    for h in humans:
        cid = int(h["paper_id"])
        if cid not in engine or h.get("h_final_score") is None:
            continue
        xs.append(float(h["h_final_score"]))
        ys.append(float(engine[cid]["composite"]))
        g3c_ys.append(float(engine[cid]["g3c"]))
        is_w = h.get("h_newsletter_verdict") == "winner_material"
        winners.append(is_w)
        scored.append((float(engine[cid]["composite"]), cid, is_w))
        # keep parallel for g3c recall
    scored.sort(key=lambda t: (-t[0], t[1]))
    n_w = sum(1 for w in winners if w)
    def recall_at(k: int, rows=scored) -> float | None:
        if n_w == 0:
            return None
        hits = sum(1 for _, _, w in rows[:k] if w)
        return hits / n_w

    # G3c ranking
    g3c_scored = []
    for h in humans:
        cid = int(h["paper_id"])
        if cid not in engine:
            continue
        g3c_scored.append(
            (
                float(engine[cid]["g3c"]),
                cid,
                h.get("h_newsletter_verdict") == "winner_material",
            )
        )
    g3c_scored.sort(key=lambda t: (-t[0], t[1]))
    n_w_g3c = sum(1 for *_, w in g3c_scored if w)

    def recall_g3c(k: int) -> float | None:
        if n_w_g3c == 0:
            return None
        return sum(1 for _, _, w in g3c_scored[:k] if w) / n_w_g3c

    comp_sp = _spearman(xs, ys)
    g3c_sp = _spearman(xs, g3c_ys)
    r20 = recall_at(20)
    r50 = recall_at(50)
    r50_base = BASELINE_JEV_V001["recall_at_50"]
    recall_pass = r50 is not None and r50 >= r50_base

    if dim_pass and recall_pass:
        verdict = "Holds"
    else:
        verdict = "Does not hold"

    report = {
        "verdict": verdict,
        "baseline_column": "jev_v001 (intersection baseline_v1.md)",
        "run_id": run_id,
        "n_scored": len(engine),
        "n_winners": n_w,
        "dims": dims_out,
        "composite_spearman": None if comp_sp is None else round(comp_sp, 3),
        "composite_baseline": BASELINE_JEV_V001["composite"],
        "recall_at_20": None if r20 is None else round(r20, 3),
        "recall_at_50": None if r50 is None else round(r50, 3),
        "recall_at_50_baseline": r50_base,
        "recall_pass": recall_pass,
        "dims_pass": dim_pass,
        "g3c_spearman": None if g3c_sp is None else round(g3c_sp, 3),
        "g3c_recall_at_20": None if recall_g3c(20) is None else round(recall_g3c(20), 3),
        "g3c_recall_at_50": None if recall_g3c(50) is None else round(recall_g3c(50), 3),
        "notes": (
            "Gate vs Jev v001 intersection baseline (same scoring policy family). "
            "G3c line uses option-(a) Ridge coefs on this run's dims — reported only."
        ),
        "baseline_source": str(BASELINE_MD.relative_to(ROOT)),
    }
    GATE_JSON.write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(json.dumps(report, indent=2))
    print(f"verdict={verdict}", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
