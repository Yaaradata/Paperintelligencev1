#!/usr/bin/env python3
"""Orchestrate multi-stage PaperIntelligence runs.

Phase 1 scaffold — implementation lands with vertical-slice stages (Phase 3).
"""

from __future__ import annotations

import sys


def main(argv: list[str] | None = None) -> int:
    _ = argv
    print(
        "run_pipeline.py: not implemented yet (Phase 3+). "
        "Use run_stage.py per stage once stages exist.",
        file=sys.stderr,
    )
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
