#!/usr/bin/env python3
"""Render reports/golden/verifier_golden_gate.md from the three verifier JSON outputs ($0).

Inputs (produced by, in order):
  scripts/audit_window_completeness.py --json   -> Part 0
  scripts/verify_golden_gate.py --json          -> Part A
  scripts/audit_prose_luna.py --out             -> Part B
"""
from __future__ import annotations

import argparse
import json
import random
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
DIMS = (
    "technical_significance",
    "apparent_novelty",
    "practical_applicability",
    "professional_value",
    "learning_value",
    "evidence_strength",
)
FLAGS = {
    "so_what not specific (could describe any paper)": lambda r: r["so_what_specific"] == "no",
    "claims something the abstract does not support": lambda r: r["unsupported_claim"] == "yes",
    "contradicts the scores it was given": lambda r: r["contradicts_scores"] == "yes",
    "reason_not_higher is a hedge": lambda r: r["reason_not_higher"] == "hedge",
}
N_EXAMPLES = 10


def f3(x: float | None) -> str:
    return "n/a" if x is None else f"{x:.3f}"


def part0(a: dict[str, Any]) -> list[str]:
    t = a["totals"]
    out = [
        "## Part 0 — Window completeness audit (SQL only, $0)",
        "",
        f"Window {a['from']} .. {a['until']} (`papers.published_at`). Script: "
        f"`scripts/audit_window_completeness.py --from {a['from']} --until {a['until']}`.",
        "",
        f"Window papers **{t['window_papers']}** · passed screen **{t['screen_passed']}** · papers with a "
        f"quality row **{t['papers_with_quality']}** · quality rows across all engines/runs "
        f"**{t['quality_rows_total']}**.",
        "",
        "| defect | count | % of window | example ids (up to 10) |",
        "|---|---:|---:|---|",
    ]
    for r in a["defects"]:
        ex = "<br>".join(r["examples"]) if r["examples"] else "—"
        out.append(f"| {r['defect']} | {r['count']} | {r['pct_window']:.1f}% | {ex} |")
    out += [
        "",
        f"Prose missing on **{a['prose_missing']} of {t['papers_with_quality']}** scored papers "
        f"(**{a['prose_missing_rate']:.1%}**); publish threshold is 10%.",
        "",
        f"**Complete enough to publish from: {'YES' if a['publishable'] else 'NO'}.**",
    ]
    out += [f"- {reason}" for reason in a["blocking_reasons"]]
    return out


def part_a(g: dict[str, Any]) -> list[str]:
    ci, cf = g["candidate_intersection"], g["candidate_full_200"]
    base = g["baseline_rederived"]
    gates = g["gates"]
    verdicts = {e: v["verdict"] for e, v in gates.items()}
    headline = "Holds" if verdicts and all(v == "Holds" for v in verdicts.values()) else (
        "Cannot be determined" if not g["determinable"] else "Does not hold"
    )
    all_match = all(c["match"] for e in g["baseline_check"].values() for c in e.values())
    out = [
        "## Part A — Golden gate (arithmetic only, no model, $0)",
        "",
        f"Candidate: jev_glm golden re-score, run `{g['run_id']}` "
        f"({g['n_candidate_rows_scored']} rows, stamps {g['candidate_stamps']}). "
        f"Labels: `golden_human_scores` labeller `{g['labeller']}`, round `{g['label_round']}`, "
        f"n={g['n_humans']}. No LLM judges anything in this part.",
        "",
        "Script: `scripts/verify_golden_gate.py --run-id " + g["run_id"] + "`.",
        "",
        f"### Verdict: **{headline}**",
        "",
        "| Baseline column | Verdict | Failing checks |",
        "|---|---|---|",
    ]
    for e, gv in gates.items():
        fails = [d for d, v in gv["dims"].items() if not v["pass"]]
        if not gv["recall_at_50"]["pass"]:
            fails.append("recall@50")
        out.append(f"| {e} | {gv['verdict']} | {', '.join(fails) or '—'} |")
    out += [
        "",
        "`baseline_v1.md` lists three columns and does not say which one a scoring change is gated "
        "against. The candidate holds only against Jev v001, the same System One policy family, and "
        "only with zero margin on recall@50 (13/22 vs 13/22). It does not hold against Terra, the "
        "production default (`QUALITY_ENGINE=terra`): three dimensions drop more than 0.05. It does "
        "not hold against Jev v002 either. Because it fails the production column, the headline is "
        "**Does not hold**. Which column governs is an open decision; nothing was adjusted.",
        "",
        f"### Intersection (n={g['n_intersection']}, rebuilt with the baseline rule; candidate missing on "
        f"{len(g['intersection_missing_candidate'])} papers)",
        "",
        "Spearman vs human (MAE in brackets). Floor = baseline − 0.05.",
        "",
        "| Dimension | jev_glm | Terra | Jev v001 | Jev v002 | vs Terra floor | vs v001 floor | vs v002 floor |",
        "|---|---:|---:|---:|---:|---|---|---|",
    ]
    for d in DIMS:
        c = ci["dims"][d]
        row = [f"{f3(c['spearman'])} ({c['mae']:.2f})"]
        for e in ("terra", "jev_v001", "jev_v002"):
            b = base[e]["dims"][d]
            row.append(f"{f3(b['spearman'])} ({b['mae']:.2f})")
        marks = []
        for e in ("terra", "jev_v001", "jev_v002"):
            gv = gates[e]["dims"][d]
            marks.append(f"{'pass' if gv['pass'] else '**FAIL**'} ({gv['floor']:.3f})")
        out.append(f"| {d} | " + " | ".join(row + marks) + " |")
    cc = ci["composite_vs_h_final_score"]
    out.append(
        f"| composite vs h_final_score | {f3(cc['spearman'])} ({cc['mae']:.2f}) | "
        + " | ".join(
            f"{f3(base[e]['composite_vs_h_final_score']['spearman'])} "
            f"({base[e]['composite_vs_h_final_score']['mae']:.2f})"
            for e in ("terra", "jev_v001", "jev_v002")
        )
        + " | not a gate input | | |"
    )
    out += ["", "Verdict recall (`winner_material`, ranked by composite; "
            f"{ci['n_winners']} winners in the intersection):", "",
            "| | jev_glm | Terra | Jev v001 | Jev v002 |", "|---|---:|---:|---:|---:|"]
    for k in (20, 50):
        cells = [f"{ci[f'recall_at_{k}']['recall']:.3f} ({ci[f'recall_at_{k}']['hits']}/{ci['n_winners']})"]
        for e in ("terra", "jev_v001", "jev_v002"):
            r = base[e][f"recall_at_{k}"]
            cells.append(f"{r['recall']:.3f} ({r['hits']}/{base[e]['n_winners']})")
        out.append(f"| recall@{k} | " + " | ".join(cells) + " |")
    out += [
        "",
        "Composite here is `composite.quality` (Σ weight·dim, weights unchanged). "
        "h_final_score is present on all intersection rows, so composite-vs-human-composite equals "
        "composite-vs-h_final_score.",
        "",
        f"Full 200 (informational only, not comparable to the baseline): composite vs h_final_score "
        f"Spearman {f3(cf['composite_vs_h_final_score']['spearman'])}, MAE "
        f"{cf['composite_vs_h_final_score']['mae']:.2f}; recall@20 {cf['recall_at_20']['recall']:.3f} "
        f"({cf['recall_at_20']['hits']}/{cf['n_winners']}), recall@50 {cf['recall_at_50']['recall']:.3f} "
        f"({cf['recall_at_50']['hits']}/{cf['n_winners']}).",
        "",
        "### Provenance of every figure",
        "",
        "| Figure | Status |",
        "|---|---|",
        f"| jev_glm per-dimension Spearman / MAE, composite, recall@20/@50 | **Re-derived** from run "
        f"`{g['run_id']}` rows and `golden_human_scores` |",
        f"| Intersection membership (n={g['n_intersection']}) | **Re-derived** from "
        "`golden/model_scores_hidden.csv` + human rows, using the baseline rule |",
        f"| Baseline Spearman ×18, composite ×3, recall@50 ×3 (Terra / v001 / v002) | **Re-derived** "
        f"from `model_scores_hidden.csv`; {'all 24 match' if all_match else 'MISMATCH against'} "
        "`baseline_v1.md` to 3 dp |",
        "| Baseline MAE, recall@20, composite vs h_final_score MAE | **Re-derived** (not in `baseline_v1.md`) |",
        "| Gate thresholds (0.05, recall@50 not lower, n ≥ 150, cells n ≥ 25) | Carried from "
        "`baseline_v1.md` (rules, not figures) |",
        "",
        "Gate comparisons use the unrounded re-derived baseline values (e.g. v001 recall@50 = 13/22, "
        "not the rounded 0.591).",
        "",
        "### G3c refitted weights — reported, not stored",
    ]
    g3 = g["g3c"]
    gi = g3["intersection"]
    coefs = " · ".join(f"{d} {v:+.3f}" for d, v in g3["coefs"].items())
    out += [
        "",
        f"Option (a) ridge from `reports/golden/g3c_weight_fit.json`: intercept {g3['intercept']:.3f}; {coefs}.",
        "",
        f"Applied to this run's jev_glm dimensions on the same intersection (n={gi['n_papers']}): "
        f"composite vs h_final_score Spearman **{f3(gi['composite_vs_h_final_score']['spearman'])}**, "
        f"recall@20 **{gi['recall_at_20']['recall']:.3f}** ({gi['recall_at_20']['hits']}/{gi['n_winners']}), "
        f"recall@50 **{gi['recall_at_50']['recall']:.3f}** ({gi['recall_at_50']['hits']}/{gi['n_winners']}).",
        "",
        "Reported, not stored. The weights were fitted on **Terra** dimensions against these same "
        "human labels, so this line is in-sample for the labels and out-of-distribution for jev_glm "
        "dimensions. It is not a gate input and no weights were applied anywhere.",
    ]
    return out


def part_b(p: dict[str, Any]) -> list[str]:
    res = p["results"]
    n = len(res)
    flagged = {pid: r for pid, r in res.items() if any(f(r) for f in FLAGS.values())}
    sp = p["spend"]
    out = [
        "## Part B — Prose audit (paid, `openai/gpt-6-luna`, cap $0.50)",
        "",
        f"Model pinned `openai/gpt-6-luna` (OpenRouter served: {', '.join(p['served_models'])}); price "
        "$0.10/M in, $0.50/M out, verified 2026-09-25 from openrouter.ai/openai/gpt-6-luna. Prompt "
        f"`prompts/prose_audit/v001.md` (`{p['prompt_version']}`). Four typed judgements only; no "
        "rewriting, scoring or ranking. Script: `scripts/audit_prose_luna.py`.",
        "",
        f"Population: every window paper whose current quality row has non-null `so_what`: **{p['n_population']}**; "
        f"judged **{p['n_judged']}**.",
        "",
        "| Flag | count | rate |",
        "|---|---:|---:|",
    ]
    for label, f in FLAGS.items():
        c = sum(f(r) for r in res.values())
        out.append(f"| {label} | {c} | {c / n:.1%} |")
    out.append(f"| **any flag (overall flag rate)** | **{len(flagged)}** | **{len(flagged) / n:.1%}** |")
    skipped = [pid for pid, r in res.items() if r["quality_status"] != "scored"]
    out += [
        "",
        f"Of these, {n - len(skipped)} rows are jev_glm prose for currently scored papers. {len(skipped)} "
        f"({', '.join(skipped) or '—'}) are older Terra prose on papers now `skipped` (screen failed), "
        "included because they still hold non-null prose.",
        "",
        "**Scope note.** The prompt asks whether `so_what` *or* `reason_not_higher` makes a claim the "
        "abstract does not support. The specification asked about `so_what` only. The unsupported-claim "
        "count may therefore include limitations stated in `reason_not_higher` that the abstract does "
        "not mention. In the 4 flagged examples read by hand, the unsupported part was in `so_what` "
        "(downstream product or audience claims), but the split was not measured.",
        "",
        "### Spend",
        "",
        f"- `usage.cost` summed over {sp['calls']} calls: **${sp['actual_usage_cost_usd']:.4f}** "
        f"(table estimate ${sp['table_estimate_usd']:.4f}; calls without `usage.cost`: "
        f"{sp['calls_without_usage_cost']}).",
        "- Two failed smoke runs before this (8 papers each, no judgements kept): $0.0033 + $0.0026.",
        f"- **Actual Part B spend: ${sp['actual_usage_cost_usd'] + 0.0033 + 0.0026:.4f}** of the $0.50 cap.",
        f"- {len(p['errors'])} call errors, mostly empty output on 8-paper batches. Every affected paper "
        "was retried as a single-paper call, so all papers were judged; the retries account for the "
        "high call count.",
        "",
        f"### {N_EXAMPLES} flagged examples (full prose)",
        "",
    ]
    rng = random.Random(20260925)
    contra = sorted(pid for pid, r in flagged.items() if r["contradicts_scores"] == "yes")
    rest = sorted(pid for pid in flagged if pid not in contra)
    picks = contra + sorted(rng.sample(rest, max(0, min(len(rest), N_EXAMPLES - len(contra)))))
    for pid in picks[:N_EXAMPLES]:
        r = res[pid]
        names = [label for label, f in FLAGS.items() if f(r)]
        scores = ", ".join(f"{d.split('_')[0]}={r['scores'][d]}" for d in DIMS)
        out += [
            f"**{pid} — {r['title']}**  ",
            f"Flags: {'; '.join(names)}  ",
            f"Scores: {scores}",
            "",
            f"> **so_what:** {r['so_what']}",
            ">",
            f"> **reason_not_higher:** {r['reason_not_higher']}",
            "",
        ]
    return out


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--audit", type=Path, default=ROOT / "reports/golden/audit_window_2026-09-21_23.json")
    ap.add_argument("--gate", type=Path, default=ROOT / "reports/golden/verifier_golden_gate.json")
    ap.add_argument("--prose", type=Path,
                    default=ROOT / "reports/golden/prose_audit_luna_2026-09-21_2026-09-23.json")
    ap.add_argument("--out", type=Path, default=ROOT / "reports/golden/verifier_golden_gate.md")
    args = ap.parse_args()
    audit = json.loads(args.audit.read_text())
    gate = json.loads(args.gate.read_text())
    prose = json.loads(args.prose.read_text())
    lines = [
        "# Verifier — golden gate, window completeness, prose audit",
        "",
        "Three separate checks, reported separately. No default changes, no weights applied, "
        "no policy edits, no DDL.",
        "",
        *part0(audit), "", "---", "", *part_a(gate), "", "---", "", *part_b(prose),
    ]
    args.out.write_text("\n".join(lines).rstrip() + "\n", encoding="utf-8")
    print(f"wrote {args.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
