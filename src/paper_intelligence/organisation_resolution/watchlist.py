"""Seed watchlist loading from config/organisations.yaml.

The watchlist only decides `is_org_of_interest` / `priority`. An organisation
that appears on no watchlist is still resolved and stored normally.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml

from paper_intelligence.common.config import REPO_ROOT

DEFAULT_WATCHLIST_PATH = REPO_ROOT / "config" / "organisations.yaml"

_WS = re.compile(r"\s+")
_PUNCT = re.compile(r"[^\w\s&-]", re.UNICODE)


def normalise_key(name: str) -> str:
    """Casefolded, punctuation-stripped key used for name-equality comparisons."""
    lowered = _PUNCT.sub(" ", (name or "").casefold())
    return _WS.sub(" ", lowered).strip()


@dataclass(frozen=True)
class WatchlistEntry:
    canonical_name: str
    ror_id: str | None = None
    openalex_id: str | None = None
    country_code: str | None = None
    organisation_type: str | None = None
    priority: int = 0
    is_org_of_interest: bool = True
    domains: list[str] = field(default_factory=list)
    aliases: list[str] = field(default_factory=list)


@dataclass(frozen=True)
class Watchlist:
    entries: list[WatchlistEntry] = field(default_factory=list)

    def match(
        self,
        canonical_name: str,
        *,
        ror_id: str | None = None,
        openalex_id: str | None = None,
        domain: str | None = None,
    ) -> WatchlistEntry | None:
        key = normalise_key(canonical_name)
        domain_key = (domain or "").strip().lower().lstrip(".")
        for entry in self.entries:
            if ror_id and entry.ror_id and entry.ror_id == ror_id:
                return entry
            if openalex_id and entry.openalex_id and entry.openalex_id == openalex_id:
                return entry
            if key and key == normalise_key(entry.canonical_name):
                return entry
            if key and any(key == normalise_key(alias) for alias in entry.aliases):
                return entry
            if domain_key and any(domain_key == d.lower().lstrip(".") for d in entry.domains):
                return entry
        return None


def _as_list(value: Any) -> list[str]:
    if value is None:
        return []
    if isinstance(value, str):
        return [value] if value.strip() else []
    if isinstance(value, list):
        return [str(v).strip() for v in value if str(v).strip()]
    return []


def load_watchlist(path: str | Path | None = None) -> Watchlist:
    """Read the seed watchlist. A missing file or empty list yields an empty watchlist."""
    target = Path(path) if path is not None else DEFAULT_WATCHLIST_PATH
    if not target.exists():
        return Watchlist(entries=[])
    try:
        document = yaml.safe_load(target.read_text(encoding="utf-8")) or {}
    except yaml.YAMLError:
        return Watchlist(entries=[])

    raw_entries = document.get("watchlist") if isinstance(document, dict) else document
    if not isinstance(raw_entries, list):
        return Watchlist(entries=[])

    entries: list[WatchlistEntry] = []
    for raw in raw_entries:
        if not isinstance(raw, dict):
            continue
        name = str(raw.get("canonical_name") or "").strip()
        if not name:
            continue
        entries.append(
            WatchlistEntry(
                canonical_name=name,
                ror_id=(str(raw["ror_id"]).strip() or None) if raw.get("ror_id") else None,
                openalex_id=(
                    (str(raw["openalex_id"]).strip() or None) if raw.get("openalex_id") else None
                ),
                country_code=(
                    (str(raw["country_code"]).strip() or None) if raw.get("country_code") else None
                ),
                organisation_type=(
                    (str(raw["organisation_type"]).strip() or None)
                    if raw.get("organisation_type")
                    else None
                ),
                priority=int(raw.get("priority") or 0),
                is_org_of_interest=bool(raw.get("is_org_of_interest", True)),
                domains=_as_list(raw.get("domains")),
                aliases=_as_list(raw.get("aliases")),
            )
        )
    return Watchlist(entries=entries)
