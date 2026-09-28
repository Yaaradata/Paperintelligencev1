#!/usr/bin/env python3
"""Compare two prose versions audited with prose_audit v003 on the same papers.

  python scripts/compare_prose_audits.py \
      --baseline reports/golden/prose_audit_luna_2026-09-21_2026-09-23_v003.json \
      --trial    reports/golden/prose_audit_luna_2026-09-21_2026-09-23_v003_prose_trial_v002_....json \
      [--validated reports/golden/prose_audit_luna_2026-09-21_2026-09-23_v002.json] [--examples 5]

Reports, side by side: so_what unsupported, so_what not specific ("could
describe any paper"), reason_not_higher unsupported. The trial is only better
if unsupported drops without not-specific rising. --validated checks that the
v003 unsupported flag on the baseline agrees with the hand-validated v002 run.
"""
from __future__ import annotations

import argparse
import json
import random
import sys
from pathlib import Path

FLAGS = (
    ("so_what unsupported", "so_what_unsupported", "yes"),
    ("so_what could describe any paper", "so_what_specific", "no"),
    ("reason_not_higher unsupported", "reason_not_higher_unsupported", "yes"),
)


def rates(results: dict[str, dict], ids: list[str]) -> dict[str, tuple[int, float]]:
    out = {}
    for label, field, bad in FLAGS:
        k = sum(results[i][field] == bad for i in ids)
        out[label] = (k, k / len(ids) if ids else 0.0)
    return out


def verdict(base: dict, trial: dict) -> str:
    u0, u1 = base["so_what unsupported"][0], trial["so_what unsupported"][0]
    g0, g1 = base["so_what could describe any paper"][0], trial["so_what could describe any paper"][0]
    if u1 < u0 and g1 <= g0:
        return "TRIAL BETTER: unsupported dropped and not-specific did not rise"
    if u1 < u0:
        return "TRADE-OFF: unsupported dropped but not-specific rose; not better by the rule"
    return "TRIAL NOT BETTER: unsupported did not drop"


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--baseline", type=Path, required=True)
    ap.add_argument("--trial", type=Path, required=True)
    ap.add_argument("--validated", type=Path)
    ap.add_argument("--examples", type=int, default=5)
    ap.add_argument("--seed", type=int, default=20260928)
    args = ap.parse_args()

    base = json.loads(args.baseline.read_text())["results"]
    trial = json.loads(args.trial.read_text())["results"]
    ids = sorted(set(base) & set(trial), key=int)
    rb, rt = rates(base, ids), rates(trial, ids)
    print(f"papers judged under both: {len(ids)} (baseline {len(base)}, trial {len(trial)})\n")
    print(f"| flag | v001 prose | v002 prose |\n|---|---:|---:|")
    for label, _, _ in FLAGS:
        print(f"| {label} | {rb[label][0]} ({rb[label][1]:.1%}) | {rt[label][0]} ({rt[label][1]:.1%}) |")
    print(f"\n{verdict(rb, rt)}")

    if args.validated:
        val = json.loads(args.validated.read_text())["results"]
        common = [i for i in ids if i in val]
        agree = sum(val[i]["so_what_unsupported"] == base[i]["so_what_unsupported"] for i in common)
        print(f"\nv003 vs validated v002 unsupported flag on v001 prose: agree {agree}/{len(common)} "
              f"({agree / len(common):.1%})" if common else "\nno overlap with --validated")

    rng = random.Random(args.seed)
    print(f"\n## {args.examples} so_what pairs (random, seed {args.seed})")
    for i in rng.sample(ids, min(args.examples, len(ids))):
        print(f"\n### {i}: {base[i].get('title')}")
        print(f"- v001 [unsupported={base[i]['so_what_unsupported']}, specific={base[i]['so_what_specific']}]: "
              f"{base[i]['so_what']}")
        print(f"- v002 [unsupported={trial[i]['so_what_unsupported']}, specific={trial[i]['so_what_specific']}]: "
              f"{trial[i]['so_what']}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
