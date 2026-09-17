#!/usr/bin/env python3
"""Load a golden JSON file into paper_intelligence golden_* tables."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from paper_intelligence.db import connect
from paper_intelligence.evaluation.golden import load_golden_file, upsert_golden_set


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Load golden dataset JSON into RDS")
    parser.add_argument("--file", required=True, help="path to golden JSON")
    args = parser.parse_args(argv)

    payload = load_golden_file(args.file)
    with connect() as conn:
        stats = upsert_golden_set(conn, payload)
    print(
        f"loaded {payload['name']} version={payload['version']} "
        f"items={stats['items_written']} labels={stats['labels_written']} "
        f"missing_content={stats['missing_content']} set_id={stats['golden_set_id']}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
