#!/usr/bin/env python3
"""Luna's so_what "unsupported" flag vs human labels on the hand-labelling sheet.

  python scripts/score_prose_handlabels.py \
      [--sheet reports/golden/prose_overclaim_handlabel_sep21_23.csv] \
      [--key reports/golden/prose_overclaim_handlabel_sep21_23_key.json] \
      [--audit reports/golden/prose_audit_luna_2026-09-21_2026-09-23_v002.json]

The sheet is stratified (40 Luna-flagged, 20 not), so recall and agreement are
also reported re-weighted to the audited population. Exit 2 when Luna
disagrees with the human on more than 25% of the sheet: the judge must be
fixed before any prose prompt is compared with it.
"""
from __future__ import annotations

import argparse
import csv
import json
import sys
from pathlib import Path

LABEL_COL = "human_so_what_unsupported (yes/no)"
DISAGREEMENT_LIMIT = 0.25


def score(labels: dict[str, str], judge: dict[str, str], pop_flagged: int, pop_clean: int) -> dict:
    tp = sum(judge[p] == "yes" and labels[p] == "yes" for p in labels)
    fp = sum(judge[p] == "yes" and labels[p] == "no" for p in labels)
    fn = sum(judge[p] == "no" and labels[p] == "yes" for p in labels)
    tn = sum(judge[p] == "no" and labels[p] == "no" for p in labels)
    n_flag, n_clean = tp + fp, fn + tn
    w_flag = pop_flagged / n_flag if n_flag else 0.0
    w_clean = pop_clean / n_clean if n_clean else 0.0
    tp_w, fp_w, fn_w, tn_w = tp * w_flag, fp * w_flag, fn * w_clean, tn * w_clean
    pop = pop_flagged + pop_clean

    def ratio(a: float, b: float) -> float | None:
        return round(a / b, 3) if b else None

    return {
        "n": len(labels),
        "confusion": {"tp": tp, "fp": fp, "fn": fn, "tn": tn},
        "disagreement_sample": ratio(fp + fn, len(labels)),
        "precision": ratio(tp, tp + fp),
        "recall_sample": ratio(tp, tp + fn),
        "recall_weighted": ratio(tp_w, tp_w + fn_w),
        "disagreement_weighted": ratio(fp_w + fn_w, pop),
        "human_unsupported_rate_weighted": ratio(tp_w + fn_w, pop),
        "luna_unsupported_rate": ratio(pop_flagged, pop),
    }


def main() -> int:
    base = Path("reports/golden")
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--sheet", type=Path, default=base / "prose_overclaim_handlabel_sep21_23.csv")
    ap.add_argument("--key", type=Path, default=base / "prose_overclaim_handlabel_sep21_23_key.json")
    ap.add_argument("--audit", type=Path, default=base / "prose_audit_luna_2026-09-21_2026-09-23_v002.json")
    args = ap.parse_args()

    judge = json.loads(args.key.read_text())["judge_so_what_unsupported"]
    labels: dict[str, str] = {}
    bad: list[str] = []
    for row in csv.DictReader(args.sheet.open(newline="", encoding="utf-8")):
        value = (row.get(LABEL_COL) or "").strip().lower()
        if value not in {"yes", "no"}:
            bad.append(f"row {row['row']} (paper {row['paper_id']}): {value!r}")
        else:
            labels[row["paper_id"]] = value
    if bad or set(labels) != set(judge):
        print(f"sheet incomplete: {len(bad)} rows without yes/no label; "
              f"{len(set(judge) - set(labels))} key papers missing", file=sys.stderr)
        for b in bad[:20]:
            print(f"  {b}", file=sys.stderr)
        return 1

    audit = json.loads(args.audit.read_text())["results"]
    pop_flagged = sum(r["so_what_unsupported"] == "yes" for r in audit.values())
    result = score(labels, judge, pop_flagged, len(audit) - pop_flagged)
    print(json.dumps(result, indent=2))
    if result["disagreement_sample"] > DISAGREEMENT_LIMIT:
        print(f"JUDGE NOT VALID: Luna disagrees with the human on {result['disagreement_sample']:.0%} "
              f"of the sheet (limit {DISAGREEMENT_LIMIT:.0%}). Fix the audit judge before comparing prompts.")
        return 2
    print(f"Judge usable: disagreement {result['disagreement_sample']:.0%} <= {DISAGREEMENT_LIMIT:.0%}.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
