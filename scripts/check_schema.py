#!/usr/bin/env python3
"""Read-only probe: report whether key paper_intelligence objects exist.

Does not apply migrations. Run before diagnosing pipeline/DB issues.
Phase 1 scaffold — Phase 2/4 wires real DB checks.
"""

from __future__ import annotations

import sys
from pathlib import Path

MIGRATIONS = Path(__file__).resolve().parents[1] / "sql" / "migrations"


def main(argv: list[str] | None = None) -> int:
    _ = argv
    files = sorted(MIGRATIONS.glob("*.sql"))
    print(f"Migrations on disk ({len(files)}):")
    for path in files:
        print(f"  - {path.name}")
    print(
        "DB probe not wired yet (Phase 2/4). "
        "Agents must not apply DDL; human runs migrations."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
