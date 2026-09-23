"""Load versioned editorial seat definitions (TECH / PRODUCT)."""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path
from typing import Any

import yaml

from paper_intelligence.common.config import REPO_ROOT

SEATS_DIR = REPO_ROOT / "policies" / "editorial_seats"
DEFAULT_VERSION = "v001"


@lru_cache(maxsize=8)
def load_editorial_seats(version: str = DEFAULT_VERSION) -> dict[str, Any]:
    path = SEATS_DIR / f"{version}.yaml"
    if not path.is_file():
        raise FileNotFoundError(f"editorial seats policy not found: {path}")
    data = yaml.safe_load(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict) or "seats" not in data:
        raise ValueError(f"invalid editorial seats file: {path}")
    return data


def format_seat_block(name: str, seat: dict[str, Any]) -> str:
    """Render one seat as the XML-ish block used in selector prompts."""
    lines: list[str] = [f'<seat name="{name}">', "Reader:"]
    reader = (seat.get("reader") or "").strip()
    for line in reader.splitlines():
        lines.append(line.rstrip())
    lines.append("")
    lines.append("Strong candidates affect decisions involving:")
    for item in seat.get("decision_areas") or []:
        lines.append(f"- {item}")
    lines.append("")
    lines.append("Prefer:")
    for item in seat.get("prefer") or []:
        lines.append(f"- {item}")
    frontier = (seat.get("frontier_clause") or "").strip()
    if frontier:
        lines.append("")
        lines.extend(frontier.splitlines())
    lines.append("")
    lines.append("Anchor test:")
    intro = (seat.get("anchor_test_intro") or "").strip()
    if intro:
        lines.extend(intro.splitlines())
    for item in seat.get("anchor_tests") or []:
        text = str(item).strip()
        if not (text.startswith('"') and text.endswith('"')):
            text = f'"{text}"'
        lines.append(f"- {text}")
    reject = (seat.get("reject") or "").strip()
    if reject:
        lines.append("")
        lines.extend(reject.splitlines())
    do_not = (seat.get("do_not_select") or "").strip()
    if do_not:
        lines.append("")
        lines.extend(do_not.splitlines())
    lines.append("</seat>")
    return "\n".join(lines)


def format_seats_xml(version: str = DEFAULT_VERSION) -> str:
    data = load_editorial_seats(version)
    seats = data["seats"]
    blocks = []
    for name in ("TECH", "PRODUCT"):
        if name not in seats:
            raise KeyError(f"seat {name!r} missing from editorial seats {version}")
        blocks.append(format_seat_block(name, seats[name]))
    return "\n\n".join(blocks)


def newsletter_rubric_body(version: str = DEFAULT_VERSION) -> str:
    """Full newsletter USER_RUBRIC body with seats loaded from the shared policy."""
    data = load_editorial_seats(version)
    parts = [
        "<newsletter_context>",
        (data.get("newsletter_context") or "").rstrip(),
        "</newsletter_context>",
        "",
        "<selection_principle>",
        (data.get("selection_principle") or "").rstrip(),
        "</selection_principle>",
        "",
        format_seats_xml(version),
        "",
        "<application_gate>",
        (data.get("application_gate") or "").rstrip(),
        "</application_gate>",
    ]
    return "\n".join(parts)


def linkedin_seats_section(version: str = DEFAULT_VERSION) -> str:
    """Seat definition blocks for LinkedIn (same TECH/PRODUCT text as newsletter)."""
    return format_seats_xml(version)
