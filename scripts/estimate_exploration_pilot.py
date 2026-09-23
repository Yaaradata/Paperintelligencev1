#!/usr/bin/env python3
"""Dry-run cost estimate for the exploration-sample quality pilot.

Does not call the LLM. Does not score historical windows unless --allow-paid
is added later (not implemented here on purpose).

Example:
  PYTHONPATH=src python3 scripts/estimate_exploration_pilot.py \\
    --day 2026-09-02 --per-day 12
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from paper_intelligence.db import connect
from paper_intelligence.quality.nomination import estimate_exploration_pilot


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Exploration pilot cost estimate")
    parser.add_argument("--day", required=True, help="YYYY-MM-DD")
    parser.add_argument("--per-day", type=int, default=12)
    parser.add_argument("--seed", default="exploration-pilot-v1")
    parser.add_argument(
        "--output",
        default=None,
        help="Optional JSON path for the estimate",
    )
    args = parser.parse_args(argv)

    with connect() as conn:
        estimate = estimate_exploration_pilot(
            conn, day=args.day, per_day=args.per_day, seed=args.seed
        )

    # Drop full sample from stdout; keep summary.
    summary = {k: v for k, v in estimate.items() if k != "sample"}
    print(json.dumps(summary, indent=2))
    if args.output:
        path = Path(args.output)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(estimate, indent=2, default=str) + "\n", encoding="utf-8")
        print(f"wrote {path}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
