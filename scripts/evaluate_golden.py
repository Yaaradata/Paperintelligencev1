#!/usr/bin/env python3
"""Evaluate pipeline output against golden datasets.

Phase 1 scaffold — Phase 4 implements scoring split by gold_label_source.
"""

from __future__ import annotations

import argparse
import sys


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Golden evaluation")
    parser.add_argument(
        "--task",
        required=True,
        choices=["audience_domain", "author_affiliation"],
    )
    parser.add_argument("--golden-version", default="v1")
    args = parser.parse_args(argv)
    print(
        f"evaluate_golden.py scaffold: task={args.task} "
        f"golden_version={args.golden_version}"
    )
    print("Implementation pending Phase 4.", file=sys.stderr)
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
