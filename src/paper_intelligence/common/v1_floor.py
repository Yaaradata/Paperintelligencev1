"""Default exclusion of papers first submitted before the v1 floor.

Window reports and scoring clamp the window start to ``V1_DATE_FLOOR``
(arXiv v1 date, stored in ``published_at``) unless ``--include-pre-v1-floor``
is passed. Rows are never deleted; ingest is not clamped.
"""

from __future__ import annotations

import argparse
import sys
from datetime import date
from os import getenv

V1_DATE_FLOOR = date.fromisoformat(getenv("PI_V1_DATE_FLOOR", "2026-07-01"))


def add_v1_floor_argument(parser: argparse.ArgumentParser) -> None:
    parser.add_argument(
        "--include-pre-v1-floor",
        action="store_true",
        help=f"include papers with arXiv v1 date before {V1_DATE_FLOOR} "
        "(excluded from reports and scoring by default)",
    )


def _as_date(value: str | date) -> date:
    return value if isinstance(value, date) else date.fromisoformat(value[:10])


def clamp_window(
    date_from: str | date | None,
    date_until: str | date | None,
    *,
    include_pre_floor: bool = False,
    floor: date = V1_DATE_FLOOR,
) -> tuple[str | date | None, str | date | None, bool]:
    """Return ``(date_from, date_until, in_scope)`` with the start clamped.

    The clamped start keeps the input's type (``str`` or ``date``).
    ``in_scope`` is False when the whole window ends before the floor.
    """
    if include_pre_floor or not date_from:
        return date_from, date_until, True
    if date_until and _as_date(date_until) < floor:
        return date_from, date_until, False
    if _as_date(date_from) < floor:
        clamped = floor if isinstance(date_from, date) else floor.isoformat()
        return clamped, date_until, True
    return date_from, date_until, True


def apply_v1_floor(args: argparse.Namespace) -> bool:
    """Clamp ``args.date_from`` in place; print what changed. False = out of scope."""
    before = args.date_from
    args.date_from, args.date_until, in_scope = clamp_window(
        args.date_from,
        args.date_until,
        include_pre_floor=bool(getattr(args, "include_pre_v1_floor", False)),
    )
    if not in_scope:
        print(
            f"window {before}..{args.date_until} is entirely before the v1 floor "
            f"{V1_DATE_FLOOR}; nothing to do (pass --include-pre-v1-floor to override)",
            file=sys.stderr,
        )
    elif args.date_from != before:
        print(
            f"v1 floor: window start {before} clamped to {args.date_from} "
            "(pass --include-pre-v1-floor to override)",
            file=sys.stderr,
        )
    return in_scope
