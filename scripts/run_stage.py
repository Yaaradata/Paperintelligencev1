#!/usr/bin/env python3
"""Run a single PaperIntelligence stage with mandatory date window for paid work.

Phase 1 scaffold — flags reserved; no API calls.
"""

from __future__ import annotations

import argparse
import sys


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Run one pipeline stage")
    parser.add_argument("--stage", required=True)
    parser.add_argument("--from", dest="date_from", default=None, help="published_at lower bound")
    parser.add_argument("--until", dest="date_until", default=None, help="published_at upper bound")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--allow-paid", action="store_true")
    parser.add_argument("--limit", type=int, default=None)
    args = parser.parse_args(argv)

    print(
        f"run_stage.py scaffold: stage={args.stage} from={args.date_from} "
        f"until={args.date_until} dry_run={args.dry_run} "
        f"allow_paid={args.allow_paid} limit={args.limit}"
    )
    print("Implementation pending Phase 3/4.", file=sys.stderr)
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
