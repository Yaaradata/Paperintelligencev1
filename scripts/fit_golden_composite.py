#!/usr/bin/env python3
"""Phase G3c — refit composite weights on human labels (proposal only).

Read-only. Does NOT change config/policies/settings.yaml.

  PYTHONPATH=src python3 scripts/fit_golden_composite.py

Writes reports/golden/g3c_weight_fit.{json,md}
"""

from __future__ import annotations

import json
import math
import statistics
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import numpy as np
from sklearn.linear_model import LogisticRegression, Ridge
from sklearn.model_selection import KFold

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from paper_intelligence.db import connect  # noqa: E402

REPORT_DIR = ROOT / "reports" / "golden"
JSON_OUT = REPORT_DIR / "g3c_weight_fit.json"
MD_OUT = REPORT_DIR / "g3c_weight_fit.md"
JEV_V001 = ROOT / "reports" / "review_fixes" / "jev_j1b_quality_scores.json"
G3B_RUN_META = REPORT_DIR / "g3b_run.json"

TERRA_DIMS = (
    "technical_significance",
    "apparent_novelty",
    "practical_applicability",
    "professional_value",
    "learning_value",
    "evidence_strength",
)
CURRENT_WEIGHTS = {
    "technical_significance": 0.28,
    "apparent_novelty": 0.24,
    "practical_applicability": 0.20,
    "professional_value": 0.16,
    "learning_value": 0.12,
}
G2_BASELINE = {"spearman": 0.278, "recall_at_20": 0.152, "recall_at_50": 0.394}


def _spearman(xs: np.ndarray, ys: np.ndarray) -> float | None:
    xs = np.asarray(xs, dtype=float)
    ys = np.asarray(ys, dtype=float)
    if len(xs) < 3:
        return None

    def ranks(vals: np.ndarray) -> np.ndarray:
        order = np.argsort(vals, kind="mergesort")
        r = np.empty(len(vals), dtype=float)
        i = 0
        while i < len(order):
            j = i
            while j + 1 < len(order) and vals[order[j + 1]] == vals[order[i]]:
                j += 1
            avg = (i + j) / 2.0 + 1.0
            r[order[i : j + 1]] = avg
            i = j + 1
        return r

    rx, ry = ranks(xs), ranks(ys)
    if np.std(rx) == 0 or np.std(ry) == 0:
        return None
    return float(np.corrcoef(rx, ry)[0, 1])


def _current_quality(dims: dict[str, float]) -> float:
    """G2-matched: weighted sum only (stored quality), no evidence multiplier."""
    return sum(CURRENT_WEIGHTS[d] * float(dims[d]) for d in CURRENT_WEIGHTS)


def _recall_at_k(scores: np.ndarray, is_winner: np.ndarray, k: int) -> float | None:
    winners = int(is_winner.sum())
    if winners == 0:
        return None
    order = np.argsort(-scores, kind="mergesort")
    hits = int(is_winner[order[:k]].sum())
    return hits / winners


def _excluded_run() -> str | None:
    if not G3B_RUN_META.exists():
        return None
    try:
        return json.loads(G3B_RUN_META.read_text(encoding="utf-8")).get("run_id")
    except (OSError, json.JSONDecodeError):
        return None


def _load_rows() -> list[dict[str, Any]]:
    with connect() as conn:
        humans = conn.execute(
            """
            SELECT paper_id, h_final_score, h_newsletter_verdict
            FROM paper_intelligence.golden_human_scores
            WHERE labeller = 'subha' AND label_round = 'v1'
            ORDER BY paper_id
            """
        ).fetchall()
        ids = [int(r["paper_id"]) for r in humans]
        excl = _excluded_run()
        if excl:
            terra_rows = conn.execute(
                """
                SELECT DISTINCT ON (q.content_item_id)
                  q.content_item_id, q.result_json
                FROM paper_intelligence.paper_classification_results q
                WHERE q.task_type = 'quality'
                  AND q.model LIKE %s
                  AND q.content_item_id = ANY(%s)
                  AND (q.run_id IS NULL OR q.run_id <> %s::uuid)
                ORDER BY q.content_item_id, q.created_at DESC
                """,
                ("%terra%", ids, excl),
            ).fetchall()
        else:
            terra_rows = conn.execute(
                """
                SELECT DISTINCT ON (q.content_item_id)
                  q.content_item_id, q.result_json
                FROM paper_intelligence.paper_classification_results q
                WHERE q.task_type = 'quality'
                  AND q.model LIKE %s
                  AND q.content_item_id = ANY(%s)
                ORDER BY q.content_item_id, q.created_at DESC
                """,
                ("%terra%", ids),
            ).fetchall()

    terra: dict[int, dict[str, float]] = {}
    for r in terra_rows:
        rj = r["result_json"] or {}
        if isinstance(rj, str):
            rj = json.loads(rj)
        if all(rj.get(d) is not None for d in TERRA_DIMS):
            terra[int(r["content_item_id"])] = {d: float(rj[d]) for d in TERRA_DIMS}

    jev_raw = json.loads(JEV_V001.read_text(encoding="utf-8")) if JEV_V001.exists() else {}
    jev: dict[int, dict[str, float]] = {}
    for k, v in (jev_raw.get("papers") or {}).items():
        dims = v.get("dims") or {}
        if dims.get("professional_value") is None or dims.get("practical_applicability") is None:
            continue
        jev[int(k)] = {
            "professional_value": float(dims["professional_value"]),
            "practical_applicability": float(dims["practical_applicability"]),
        }

    rows = []
    for h in humans:
        cid = int(h["paper_id"])
        if cid not in terra or h.get("h_final_score") is None:
            continue
        rows.append(
            {
                "paper_id": cid,
                "h_final": float(h["h_final_score"]),
                "winner": 1 if h.get("h_newsletter_verdict") == "winner_material" else 0,
                "terra": terra[cid],
                "jev": jev.get(cid),
            }
        )
    return rows


def _weight_table(names: list[str], coef: np.ndarray) -> dict[str, Any]:
    abs_w = np.abs(coef)
    s = float(abs_w.sum()) or 1.0
    return {
        "signed_coefs": {names[i]: float(coef[i]) for i in range(len(names))},
        "l1_share": {names[i]: float(abs_w[i] / s) for i in range(len(names))},
    }


def _cv_eval(
    rows: list[dict[str, Any]],
    *,
    feature_fn,
    fit_fn,
    score_fn,
    n_splits: int = 5,
    seed: int = 42,
) -> dict[str, Any]:
    n = len(rows)
    idx = np.arange(n)
    kf = KFold(n_splits=n_splits, shuffle=True, random_state=seed)
    fold_metrics = []
    fold_coefs = []

    X_all, names = feature_fn(rows)
    y_final = np.array([r["h_final"] for r in rows], dtype=float)
    y_win = np.array([r["winner"] for r in rows], dtype=int)

    oof = np.zeros(n, dtype=float)
    for fold_i, (tr, te) in enumerate(kf.split(idx)):
        train = [rows[i] for i in tr]
        test = [rows[i] for i in te]
        X_tr, _ = feature_fn(train)
        fit_out = fit_fn(
            X_tr,
            np.array([r["h_final"] for r in train], dtype=float),
            np.array([r["winner"] for r in train], dtype=int),
        )
        fold_coefs.append(fit_out["coef"].tolist())
        X_te, _ = feature_fn(test)
        scores = score_fn(X_te, fit_out)
        oof[te] = scores
        y_te_final = np.array([r["h_final"] for r in test], dtype=float)
        y_te_win = np.array([r["winner"] for r in test], dtype=int)
        fold_metrics.append(
            {
                "fold": fold_i,
                "n_test": len(test),
                "spearman": _spearman(y_te_final, scores),
                "recall_at_20": _recall_at_k(scores, y_te_win, min(20, len(test))),
                "recall_at_50": _recall_at_k(scores, y_te_win, min(50, len(test))),
            }
        )

    full = fit_fn(X_all, y_final, y_win)
    scores_all = score_fn(X_all, full)
    wt = _weight_table(names, full["coef"])

    return {
        "feature_names": names,
        "n": n,
        "n_winners": int(y_win.sum()),
        "oof_spearman": _spearman(y_final, oof),
        "oof_recall_at_20": _recall_at_k(oof, y_win, 20),
        "oof_recall_at_50": _recall_at_k(oof, y_win, 50),
        "in_sample_spearman": _spearman(y_final, scores_all),
        "full_fit_signed_coefs": wt["signed_coefs"],
        "full_fit_l1_share": wt["l1_share"],
        "full_fit_intercept": full.get("intercept"),
        "fold_coef_mean_signed": {
            names[i]: float(np.mean([c[i] for c in fold_coefs]))
            for i in range(len(names))
        },
        "fold_metrics": fold_metrics,
    }


def main() -> int:
    rows = _load_rows()
    rows_terra = rows
    rows_mixed = [r for r in rows if r.get("jev")]

    def feat_terra6(rs):
        names = list(TERRA_DIMS)
        X = np.array([[r["terra"][d] for d in TERRA_DIMS] for r in rs], dtype=float)
        return X, names

    def feat_mixed(rs):
        names = [
            "terra_technical_significance",
            "terra_apparent_novelty",
            "terra_evidence_strength",
            "jev_professional_value",
            "jev_practical_applicability",
        ]
        X = np.array(
            [
                [
                    r["terra"]["technical_significance"],
                    r["terra"]["apparent_novelty"],
                    r["terra"]["evidence_strength"],
                    r["jev"]["professional_value"],
                    r["jev"]["practical_applicability"],
                ]
                for r in rs
            ],
            dtype=float,
        )
        return X, names

    def fit_ridge_h_final(X, y_final, y_win):
        model = Ridge(alpha=1.0, fit_intercept=True)
        model.fit(X, y_final)
        return {
            "coef": model.coef_.astype(float),
            "intercept": float(model.intercept_),
            "model": model,
        }

    def score_ridge(X, fit_out):
        return fit_out["model"].predict(X)

    def fit_logistic_winner(X, y_final, y_win):
        model = LogisticRegression(
            C=1.0, class_weight="balanced", max_iter=2000, solver="lbfgs"
        )
        model.fit(X, y_win)
        return {
            "coef": model.coef_.ravel().astype(float),
            "intercept": float(model.intercept_[0]),
            "model": model,
        }

    def score_logistic(X, fit_out):
        return fit_out["model"].predict_proba(X)[:, 1]

    y_final = np.array([r["h_final"] for r in rows_terra], dtype=float)
    y_win = np.array([r["winner"] for r in rows_terra], dtype=int)
    cur = np.array([_current_quality(r["terra"]) for r in rows_terra], dtype=float)
    baseline_same_n = {
        "n": len(rows_terra),
        "n_winners": int(y_win.sum()),
        "spearman": _spearman(y_final, cur),
        "recall_at_20": _recall_at_k(cur, y_win, 20),
        "recall_at_50": _recall_at_k(cur, y_win, 50),
        "note": "current weights, quality=Σw·dim (G2-matched; no evidence multiplier)",
    }

    results = {
        "a_ridge_terra6_h_final": _cv_eval(
            rows_terra,
            feature_fn=feat_terra6,
            fit_fn=fit_ridge_h_final,
            score_fn=score_ridge,
        ),
        "b_logistic_terra6_winner": _cv_eval(
            rows_terra,
            feature_fn=feat_terra6,
            fit_fn=fit_logistic_winner,
            score_fn=score_logistic,
        ),
        "c_mixed_terra_jev": _cv_eval(
            rows_mixed,
            feature_fn=feat_mixed,
            fit_fn=fit_ridge_h_final,
            score_fn=score_ridge,
        ),
    }

    n = len(rows_terra)
    spearman_se = 1.0 / math.sqrt(max(n - 1, 1))

    def _gain(opt_key: str) -> dict[str, Any]:
        r = results[opt_key]
        # Primary comparison vs G2-cited baseline (user brief)
        d_sp_g2 = (r["oof_spearman"] or 0) - G2_BASELINE["spearman"]
        d20_g2 = (r["oof_recall_at_20"] or 0) - G2_BASELINE["recall_at_20"]
        d50_g2 = (r["oof_recall_at_50"] or 0) - G2_BASELINE["recall_at_50"]
        # Also vs recomputed same-n current weights
        d_sp = (r["oof_spearman"] or 0) - (baseline_same_n["spearman"] or 0)
        within_noise = abs(d_sp_g2) < spearman_se
        marginal = (not within_noise) and abs(d_sp_g2) < 1.5 * spearman_se
        return {
            "delta_spearman_vs_g2_cited": d_sp_g2,
            "delta_recall_at_20_vs_g2_cited": d20_g2,
            "delta_recall_at_50_vs_g2_cited": d50_g2,
            "delta_spearman_vs_same_n_current": d_sp,
            "within_noise": within_noise,
            "marginal": marginal,
            "noise_se_spearman": spearman_se,
        }

    gains = {k: _gain(k) for k in results}

    report = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "phase": "G3c",
        "n_terra_rows": len(rows_terra),
        "n_mixed_rows": len(rows_mixed),
        "g2_cited_baseline": G2_BASELINE,
        "baseline_current_weights_same_n": baseline_same_n,
        "noise": {
            "spearman_se_approx": spearman_se,
            "rule": "|Δ Spearman| vs G2 cited < 1/√(n−1) → WITHIN NOISE; "
            "< 1.5×SE → MARGINAL",
        },
        "options": results,
        "gains_vs_current": gains,
        "proposal_only": True,
        "settings_yaml_unchanged": True,
    }

    REPORT_DIR.mkdir(parents=True, exist_ok=True)

    def _scrub(obj):
        if isinstance(obj, dict):
            return {k: _scrub(v) for k, v in obj.items() if k != "model"}
        if isinstance(obj, list):
            return [_scrub(x) for x in obj]
        if isinstance(obj, (np.floating, np.integer)):
            return float(obj)
        return obj

    JSON_OUT.write_text(json.dumps(_scrub(report), indent=2, default=str), encoding="utf-8")

    def _fmt(x, nd=3):
        return "n/a" if x is None else f"{x:.{nd}f}"

    lines = [
        "# G3c — composite weight refit (proposal only)",
        "",
        f"**Generated:** {report['generated_at']}  ",
        f"**n (Terra rows):** {len(rows_terra)} · **n (mixed Terra+Jev):** {len(rows_mixed)}  ",
        "**config/policies/settings.yaml: UNCHANGED** — numbers below are proposals only.",
        "",
        "## Baseline (current weights)",
        "",
        f"- G2 cited (full Terra coverage): Spearman **{G2_BASELINE['spearman']}** / "
        f"recall@20 **{G2_BASELINE['recall_at_20']}** / recall@50 **{G2_BASELINE['recall_at_50']}**",
        f"- Recomputed same-n quality=Σw·dim (n={baseline_same_n['n']}, "
        f"winners={baseline_same_n['n_winners']}): "
        f"Spearman **{_fmt(baseline_same_n['spearman'])}** / "
        f"recall@20 **{_fmt(baseline_same_n['recall_at_20'])}** / "
        f"recall@50 **{_fmt(baseline_same_n['recall_at_50'])}**",
        f"- Noise floor (Spearman SE ≈ 1/√(n−1)): **{_fmt(spearman_se)}**",
        "",
        "## Held-out metrics (5-fold OOF)",
        "",
        "| Option | OOF Spearman | recall@20 | recall@50 | Δρ vs G2 cited | Noise flag |",
        "|---|---:|---:|---:|---:|---|",
    ]
    labels = {
        "a_ridge_terra6_h_final": "(a) Ridge Terra-6 → h_final",
        "b_logistic_terra6_winner": "(b) logistic Terra-6 → winner_material",
        "c_mixed_terra_jev": "(c) mixed Terra tech/novelty/evidence + Jev prof/practical",
    }
    for key, label in labels.items():
        r = results[key]
        g = gains[key]
        flag = (
            "WITHIN NOISE"
            if g["within_noise"]
            else ("MARGINAL" if g["marginal"] else "above noise")
        )
        lines.append(
            f"| {label} | {_fmt(r['oof_spearman'])} | {_fmt(r['oof_recall_at_20'])} | "
            f"{_fmt(r['oof_recall_at_50'])} | {_fmt(g['delta_spearman_vs_g2_cited'])} | "
            f"**{flag}** |"
        )

    lines += ["", "## Fitted weights (full-data proposal)", ""]
    for key, label in labels.items():
        r = results[key]
        lines += [
            f"### {label}",
            "",
            f"Intercept: `{_fmt(r.get('full_fit_intercept'), 4)}`",
            "",
            "| Feature | Signed coef | L1 share |",
            "|---|---:|---:|",
        ]
        for name in r["feature_names"]:
            lines.append(
                f"| `{name}` | {r['full_fit_signed_coefs'][name]:.4f} | "
                f"{r['full_fit_l1_share'][name]:.4f} |"
            )
        lines.append("")

    lines += [
        "## Interpretation",
        "",
        "- Do **not** ship weights from this run. Propose only.",
        "- Option (b) ranks by P(winner_material); Spearman vs h_final is secondary.",
        "- Option (c) requires both Terra and Jev at inference — operational cost.",
        "- L1 share is |coef| / Σ|coef| for readability; scoring uses signed coefs + intercept.",
        "- Compare human–human ceiling (double_label_30) before treating Spearman ~0.6 as a win.",
        "",
    ]
    MD_OUT.write_text("\n".join(lines), encoding="utf-8")
    print(f"wrote {JSON_OUT}", flush=True)
    print(f"wrote {MD_OUT}", flush=True)
    print(
        json.dumps(
            {
                "baseline_same_n": baseline_same_n,
                "oof": {
                    k: {
                        "spearman": results[k]["oof_spearman"],
                        "r20": results[k]["oof_recall_at_20"],
                        "r50": results[k]["oof_recall_at_50"],
                        "noise": gains[k]["within_noise"],
                        "delta_sp_g2": gains[k]["delta_spearman_vs_g2_cited"],
                    }
                    for k in results
                },
            },
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
