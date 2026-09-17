#!/usr/bin/env python3
"""Evaluate pipeline output against golden datasets.

Splits metrics by gold_label_source (manual vs llm_adjudicated).
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from paper_intelligence.db import connect
from paper_intelligence.evaluation.golden import (
    evaluate_audience_domain,
    evaluate_author_affiliation,
)
from paper_intelligence.observability.runs import code_commit_sha


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Golden evaluation")
    parser.add_argument(
        "--task",
        required=True,
        choices=["audience_domain", "author_affiliation"],
    )
    parser.add_argument("--golden-version", default="v1")
    parser.add_argument(
        "--json-out",
        default=None,
        help="optional path to write machine-readable metrics",
    )
    args = parser.parse_args(argv)

    with connect() as conn:
        if args.task == "audience_domain":
            summary = evaluate_audience_domain(conn, golden_version=args.golden_version)
        else:
            summary = evaluate_author_affiliation(
                conn, golden_version=args.golden_version
            )

    summary["task"] = args.task
    summary["golden_version"] = args.golden_version
    summary["code_commit_sha"] = code_commit_sha()
    print(json.dumps(summary, indent=2, default=str))
    if args.json_out:
        Path(args.json_out).write_text(json.dumps(summary, indent=2, default=str))
        print(f"wrote {args.json_out}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
