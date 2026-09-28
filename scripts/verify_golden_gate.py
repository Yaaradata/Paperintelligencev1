#!/usr/bin/env python3
"""Verifier Part A: arithmetic golden gate for a jev_glm golden re-score (no model, $0).

Every figure is recomputed from raw rows:
  * human labels   — golden_human_scores (labeller/round from args)
  * baseline cols  — golden/model_scores_hidden.csv (Terra / Jev v001 / Jev v002 per-paper scores)
  * candidate      — paper_classification_results rows for --run-id (task_type='quality')

The 3-engine intersection is rebuilt with the rule used for baseline_v1.md
(all six dims + composite present for Terra, Jev v001, Jev v002 and the human row),
then the baseline figures are re-derived on it and checked against baseline_v1.md.

  PYTHONPATH=src python scripts/verify_golden_gate.py --run-id 750f86d6-... \
      [--json reports/golden/verifier_golden_gate.json]
"""
from __future__ import annotations

import argparse
import csv
import json
import math
import statistics
import sys
from pathlib import Path
from typing import Any

from paper_intelligence.db import connect

ROOT = Path(__file__).resolve().parents[1]
HIDDEN_CSV = ROOT / "golden" / "model_scores_hidden.csv"
G3C_JSON = ROOT / "reports" / "golden" / "g3c_weight_fit.json"

DIMS = (
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
BASELINE_ENGINES = ("terra", "jev_v001", "jev_v002")
# Transcribed from reports/golden/baseline_v1.md; re-derived below and compared.
BASELINE_V1 = {
    "terra": {"technical_significance": 0.432, "apparent_novelty": 0.426, "practical_applicability": 0.588,
              "professional_value": 0.302, "learning_value": 0.232, "evidence_strength": 0.517,
              "composite": 0.219, "recall_at_50": 0.500},
    "jev_v001": {"technical_significance": 0.248, "apparent_novelty": 0.321, "practical_applicability": 0.539,
                 "professional_value": 0.615, "learning_value": 0.187, "evidence_strength": 0.394,
                 "composite": 0.367, "recall_at_50": 0.591},
    "jev_v002": {"technical_significance": 0.289, "apparent_novelty": 0.280, "practical_applicability": 0.413,
                 "professional_value": 0.696, "learning_value": 0.309, "evidence_strength": 0.370,
                 "composite": 0.427, "recall_at_50": 0.773},
}
SPEARMAN_TOLERANCE = 0.05
MIN_INTERSECTION = 150
MIN_CELL_N = 25


def ranks(vals: list[float]) -> list[float]:
    order = sorted(range(len(vals)), key=lambda i: vals[i])
    out = [0.0] * len(vals)
    i = 0
    while i < len(order):
        j = i
        while j + 1 < len(order) and vals[order[j + 1]] == vals[order[i]]:
            j += 1
        for k in range(i, j + 1):
            out[order[k]] = (i + j) / 2.0 + 1.0
        i = j + 1
    return out


def spearman(xs: list[float], ys: list[float]) -> float | None:
    if len(xs) < MIN_CELL_N:
        return None
    rx, ry = ranks(xs), ranks(ys)
    mx, my = statistics.mean(rx), statistics.mean(ry)
    num = sum((a - mx) * (b - my) for a, b in zip(rx, ry))
    den = math.sqrt(sum((a - mx) ** 2 for a in rx) * sum((b - my) ** 2 for b in ry))
    return num / den if den else None


def mae(xs: list[float], ys: list[float]) -> float | None:
    return statistics.mean(abs(a - b) for a, b in zip(xs, ys)) if len(xs) >= MIN_CELL_N else None


def local_composite(scores: dict[str, float]) -> float:
    q = sum(w * scores[d] for d, w in Q_WEIGHTS.items())
    return min(10.0, q * (0.70 + 0.03 * scores["evidence_strength"]))


def _f(v: Any) -> float | None:
    if v is None or v == "":
        return None
    try:
        return float(v)
    except (TypeError, ValueError):
        return None


def load_humans(labeller: str, label_round: str) -> dict[int, dict[str, Any]]:
    with connect() as conn:
        rows = conn.execute(
            "SELECT * FROM paper_intelligence.golden_human_scores WHERE labeller=%s AND label_round=%s",
            (labeller, label_round),
        ).fetchall()
    out = {}
    for r in rows:
        scores = {d: _f(r[f"h_{d}"]) for d in DIMS}
        scores = {k: v for k, v in scores.items() if v is not None}
        final = _f(r["h_final_score"])
        composite = final if final is not None else (
            local_composite(scores) if len(scores) == len(DIMS) else None
        )
        out[int(r["paper_id"])] = {
            "scores": scores,
            "h_final_score": final,
            "composite": composite,
            "verdict": r["h_newsletter_verdict"],
        }
    return out


def load_hidden_engines() -> dict[str, dict[int, dict[str, Any]]]:
    engines: dict[str, dict[int, dict[str, Any]]] = {e: {} for e in BASELINE_ENGINES}
    with HIDDEN_CSV.open(newline="", encoding="utf-8") as fh:
        for row in csv.DictReader(fh):
            pid = int(row["paper_id"])
            for e in BASELINE_ENGINES:
                scores = {d: _f(row.get(f"{e}_{d}")) for d in DIMS}
                if any(v is None for v in scores.values()):
                    continue
                comp = _f(row.get(f"{e}_composite"))
                engines[e][pid] = {"scores": scores, "composite": comp}
    return engines


def load_candidate(run_id: str) -> dict[int, dict[str, Any]]:
    with connect() as conn:
        rows = conn.execute(
            """
            SELECT content_item_id, model, prompt_version, policy_version, result_json
            FROM paper_intelligence.paper_classification_results
            WHERE task_type='quality' AND run_id=%s::uuid
            """,
            (run_id,),
        ).fetchall()
    out = {}
    for r in rows:
        rj = r["result_json"] or {}
        if isinstance(rj, str):
            rj = json.loads(rj)
        scores = {d: _f(rj.get(d)) for d in DIMS}
        if any(v is None for v in scores.values()):
            continue
        comp = rj.get("composite")
        quality = _f(comp.get("quality")) if isinstance(comp, dict) else _f(comp)
        out[int(r["content_item_id"])] = {
            "scores": scores,
            "composite": quality,
            "composite_final": _f(comp.get("final")) if isinstance(comp, dict) else None,
            "model": r["model"],
            "prompt_version": r["prompt_version"],
            "policy_version": r["policy_version"],
            "scoring_engine": rj.get("scoring_engine"),
        }
    return out


def g3c_scorer() -> tuple[dict[str, float], float, Any]:
    fit = json.loads(G3C_JSON.read_text(encoding="utf-8"))["options"]["a_ridge_terra6_h_final"]
    coefs = {d: float(fit["full_fit_signed_coefs"][d]) for d in DIMS}
    intercept = float(fit["full_fit_intercept"])

    def score(scores: dict[str, float]) -> float:
        return intercept + sum(coefs[d] * scores[d] for d in DIMS)

    return coefs, intercept, score


def evaluate(
    humans: dict[int, dict[str, Any]], engine: dict[int, dict[str, Any]], ids: list[int],
    composite_key: str = "composite",
) -> dict[str, Any]:
    out: dict[str, Any] = {"n_papers": len(ids), "dims": {}}
    for d in DIMS:
        xs, ys = [], []
        for pid in ids:
            h, e = humans[pid], engine.get(pid)
            if e is None or d not in h["scores"]:
                continue
            xs.append(h["scores"][d])
            ys.append(e["scores"][d])
        out["dims"][d] = {"n": len(xs), "spearman": spearman(xs, ys), "mae": mae(xs, ys)}

    # Composite vs human composite (h_final_score, or local composite where h_final_score is NULL)
    xs, ys, xs_f, ys_f = [], [], [], []
    for pid in ids:
        h, e = humans[pid], engine.get(pid)
        if e is None or e.get(composite_key) is None:
            continue
        if h["composite"] is not None:
            xs.append(h["composite"])
            ys.append(e[composite_key])
        if h["h_final_score"] is not None:
            xs_f.append(h["h_final_score"])
            ys_f.append(e[composite_key])
    out["composite_vs_human_composite"] = {"n": len(xs), "spearman": spearman(xs, ys), "mae": mae(xs, ys)}
    out["composite_vs_h_final_score"] = {"n": len(xs_f), "spearman": spearman(xs_f, ys_f), "mae": mae(xs_f, ys_f)}

    winners = {pid for pid in ids if humans[pid]["verdict"] == "winner_material"}
    ranked = sorted(
        ((engine[pid][composite_key], pid) for pid in ids if pid in engine and engine[pid].get(composite_key) is not None),
        key=lambda t: (-t[0], t[1]),
    )
    out["n_winners"] = len(winners)
    for k in (20, 50):
        top = {pid for _, pid in ranked[:k]}
        hits = len(winners & top)
        out[f"recall_at_{k}"] = {"hits": hits, "recall": hits / len(winners) if winners else None}
    return out


def gate(candidate: dict[str, Any], baseline: dict[str, Any]) -> dict[str, Any]:
    """Compare against the re-derived (unrounded) baseline figures, not the 3-dp transcription."""
    dims = {}
    ok = True
    for d in DIMS:
        sp = candidate["dims"][d]["spearman"]
        base = baseline["dims"][d]["spearman"]
        floor = base - SPEARMAN_TOLERANCE
        passed = sp is not None and sp >= floor
        ok &= passed
        dims[d] = {"candidate": sp, "baseline": base, "floor": floor, "pass": passed}
    r50, b50 = candidate["recall_at_50"], baseline["recall_at_50"]
    r_ok = r50["hits"] >= b50["hits"] and candidate["n_winners"] == baseline["n_winners"]
    return {
        "dims": dims,
        "recall_at_50": {"candidate": r50["recall"], "candidate_hits": r50["hits"],
                         "baseline": b50["recall"], "baseline_hits": b50["hits"],
                         "n_winners": baseline["n_winners"], "pass": r_ok},
        "verdict": "Holds" if ok and r_ok else "Does not hold",
    }


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--run-id", required=True)
    ap.add_argument("--labeller", default="subha")
    ap.add_argument("--label-round", default="v1")
    ap.add_argument("--json", type=Path, default=ROOT / "reports" / "golden" / "verifier_golden_gate.json")
    args = ap.parse_args()

    humans = load_humans(args.labeller, args.label_round)
    hidden = load_hidden_engines()
    cand = load_candidate(args.run_id)

    inter = sorted(
        pid for pid, h in humans.items()
        if len(h["scores"]) == len(DIMS) and h["composite"] is not None
        and all(pid in hidden[e] and hidden[e][pid]["composite"] is not None for e in BASELINE_ENGINES)
    )
    missing_cand = [pid for pid in inter if pid not in cand]

    baseline_rederived = {e: evaluate(humans, hidden[e], inter) for e in BASELINE_ENGINES}
    baseline_check = {}
    for e in BASELINE_ENGINES:
        rd = baseline_rederived[e]
        figures = {d: rd["dims"][d]["spearman"] for d in DIMS}
        figures["composite"] = rd["composite_vs_human_composite"]["spearman"]
        figures["recall_at_50"] = rd["recall_at_50"]["recall"]
        baseline_check[e] = {
            k: {"baseline_v1_md": BASELINE_V1[e][k], "rederived": v,
                "match": v is not None and abs(round(v, 3) - BASELINE_V1[e][k]) < 0.0015}
            for k, v in figures.items()
        }

    cand_inter = evaluate(humans, cand, inter)
    cand_full = evaluate(humans, cand, sorted(humans))
    determinable = len(inter) >= MIN_INTERSECTION and not missing_cand
    gates = {e: gate(cand_inter, baseline_rederived[e]) for e in BASELINE_ENGINES} if determinable else {}

    coefs, intercept, g3c = g3c_scorer()
    g3c_engine = {pid: {**v, "g3c": g3c(v["scores"])} for pid, v in cand.items()}
    g3c_inter = evaluate(humans, g3c_engine, inter, composite_key="g3c")

    stamps = sorted({(v["model"], v["prompt_version"], v["policy_version"], v["scoring_engine"]) for v in cand.values()})
    report = {
        "run_id": args.run_id,
        "labeller": args.labeller,
        "label_round": args.label_round,
        "n_humans": len(humans),
        "n_candidate_rows_scored": len(cand),
        "candidate_stamps": stamps,
        "n_intersection": len(inter),
        "intersection_missing_candidate": missing_cand,
        "determinable": determinable,
        "baseline_rederived": baseline_rederived,
        "baseline_check": baseline_check,
        "candidate_intersection": cand_inter,
        "candidate_full_200": cand_full,
        "gates": gates,
        "g3c": {"coefs": coefs, "intercept": intercept, "intersection": g3c_inter,
                "note": "G3c option (a) ridge, fitted on Terra dims; applied to jev_glm dims. Reported, not stored."},
    }
    args.json.parent.mkdir(parents=True, exist_ok=True)
    args.json.write_text(json.dumps(report, indent=2, default=str), encoding="utf-8")
    print(json.dumps({
        "n_intersection": len(inter),
        "missing": missing_cand,
        "baseline_all_match": all(c["match"] for e in baseline_check.values() for c in e.values()),
        "verdicts": {e: g["verdict"] for e, g in gates.items()},
    }, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
