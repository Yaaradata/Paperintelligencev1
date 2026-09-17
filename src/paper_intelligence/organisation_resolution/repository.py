"""Canonical organisation storage: paper_intelligence.organisations + aliases."""

from __future__ import annotations

import json
from typing import Any, Iterable

from psycopg import Connection, errors

from paper_intelligence.organisation_resolution.watchlist import (
    Watchlist,
    WatchlistEntry,
    load_watchlist,
)

ALIAS_TYPES = ("name", "domain", "abbreviation", "historical_name")

_PUBLIC_EMAIL_DOMAINS = frozenset(
    {
        "gmail.com",
        "googlemail.com",
        "yahoo.com",
        "yahoo.co.uk",
        "hotmail.com",
        "outlook.com",
        "live.com",
        "icloud.com",
        "me.com",
        "aol.com",
        "protonmail.com",
        "proton.me",
        "qq.com",
        "163.com",
        "126.com",
        "foxmail.com",
        "mail.ru",
        "yandex.ru",
        "example.com",
    }
)


def is_public_email_domain(domain: str) -> bool:
    return (domain or "").strip().lower().lstrip(".") in _PUBLIC_EMAIL_DOMAINS


def domain_of(email: str) -> str | None:
    if not email or "@" not in email:
        return None
    domain = email.rsplit("@", 1)[1].strip().lower().strip(".")
    return domain or None


def domain_candidates(domain: str) -> list[str]:
    """`cs.ox.ac.uk` → itself plus progressively shorter parents (min two labels)."""
    parts = [p for p in (domain or "").lower().strip(".").split(".") if p]
    return [".".join(parts[i:]) for i in range(0, max(1, len(parts) - 1))]


# --------------------------------------------------------------------------
# Lookups
# --------------------------------------------------------------------------


def find_organisation_by_ror(conn: Connection, ror_id: str) -> int | None:
    with conn.cursor() as cur:
        cur.execute(
            "SELECT id FROM paper_intelligence.organisations WHERE ror_id = %s", (ror_id,)
        )
        row = cur.fetchone()
    return row["id"] if row else None


def find_organisation_by_openalex(conn: Connection, openalex_id: str) -> int | None:
    with conn.cursor() as cur:
        cur.execute(
            "SELECT id FROM paper_intelligence.organisations WHERE openalex_id = %s",
            (openalex_id,),
        )
        row = cur.fetchone()
    return row["id"] if row else None


def find_organisation_by_name(conn: Connection, canonical_name: str) -> int | None:
    with conn.cursor() as cur:
        cur.execute(
            """
            SELECT id FROM paper_intelligence.organisations
            WHERE lower(canonical_name) = lower(%s)
            ORDER BY id LIMIT 1
            """,
            (canonical_name,),
        )
        row = cur.fetchone()
    return row["id"] if row else None


def find_organisation_by_alias(
    conn: Connection, alias: str, *, alias_type: str | None = None
) -> int | None:
    with conn.cursor() as cur:
        cur.execute(
            """
            SELECT organisation_id FROM paper_intelligence.organisation_aliases
            WHERE lower(alias) = lower(%s)
              AND (%s::text IS NULL OR alias_type = %s)
            ORDER BY id LIMIT 1
            """,
            (alias, alias_type, alias_type),
        )
        row = cur.fetchone()
    return row["organisation_id"] if row else None


def find_organisation_by_email_domain(conn: Connection, email_or_domain: str) -> int | None:
    """Deterministic match of an email (or bare domain) against existing 'domain' aliases."""
    domain = domain_of(email_or_domain) or (email_or_domain or "").strip().lower().strip(".")
    if not domain or is_public_email_domain(domain):
        return None
    for candidate in domain_candidates(domain):
        organisation_id = find_organisation_by_alias(conn, candidate, alias_type="domain")
        if organisation_id is not None:
            return organisation_id
    return None


def get_organisation(conn: Connection, organisation_id: int) -> dict[str, Any] | None:
    with conn.cursor() as cur:
        cur.execute(
            "SELECT * FROM paper_intelligence.organisations WHERE id = %s", (organisation_id,)
        )
        return cur.fetchone()


# --------------------------------------------------------------------------
# Writes
# --------------------------------------------------------------------------


def add_alias(
    conn: Connection,
    organisation_id: int,
    alias: str,
    alias_type: str,
    *,
    confidence: float | None = None,
) -> None:
    """Record a name/domain/abbreviation/historical alias. Idempotent."""
    value = (alias or "").strip()
    if not value or alias_type not in ALIAS_TYPES:
        return
    if alias_type == "domain":
        value = value.lower().lstrip("@").strip(".")
        if not value:
            return
    with conn.cursor() as cur:
        cur.execute(
            """
            INSERT INTO paper_intelligence.organisation_aliases
                (organisation_id, alias, alias_type, confidence)
            VALUES (%s, %s, %s, %s)
            ON CONFLICT (organisation_id, alias, alias_type) DO NOTHING
            """,
            (organisation_id, value, alias_type, confidence),
        )


def add_domain_aliases(
    conn: Connection, organisation_id: int, domains: Iterable[str], *, confidence: float | None = None
) -> None:
    for domain in domains:
        add_alias(conn, organisation_id, domain, "domain", confidence=confidence)


def find_or_create_organisation(
    conn: Connection,
    canonical_name: str,
    *,
    ror_id: str | None = None,
    openalex_id: str | None = None,
    country_code: str | None = None,
    organisation_type: str | None = None,
    metadata: dict[str, Any] | None = None,
    watchlist: Watchlist | None = None,
) -> int:
    """Idempotently resolve a canonical organisation row and return its id.

    Match order: ror_id, then openalex_id, then exact canonical name, then an
    existing alias. Organisations absent from every watchlist are stored the
    same way as watchlisted ones; the watchlist only drives interest/priority.
    """
    name = (canonical_name or "").strip()
    if not name:
        raise ValueError("canonical_name is required")

    ror_id = (ror_id or "").strip() or None
    openalex_id = (openalex_id or "").strip() or None

    organisation_id = None
    if ror_id:
        organisation_id = find_organisation_by_ror(conn, ror_id)
    if organisation_id is None and openalex_id:
        organisation_id = find_organisation_by_openalex(conn, openalex_id)
    if organisation_id is None:
        organisation_id = find_organisation_by_name(conn, name)
    if organisation_id is None:
        organisation_id = find_organisation_by_alias(conn, name)

    if organisation_id is None:
        organisation_id = _insert_organisation(
            conn,
            name,
            ror_id=ror_id,
            openalex_id=openalex_id,
            country_code=country_code,
            organisation_type=organisation_type,
            metadata=metadata,
        )
    else:
        _enrich_organisation(
            conn,
            organisation_id,
            ror_id=ror_id,
            openalex_id=openalex_id,
            country_code=country_code,
            organisation_type=organisation_type,
            metadata=metadata,
        )

    add_alias(conn, organisation_id, name, "name")
    apply_watchlist(conn, organisation_id, name, watchlist=watchlist, ror_id=ror_id,
                    openalex_id=openalex_id)
    return organisation_id


def _insert_organisation(
    conn: Connection,
    canonical_name: str,
    *,
    ror_id: str | None,
    openalex_id: str | None,
    country_code: str | None,
    organisation_type: str | None,
    metadata: dict[str, Any] | None,
) -> int:
    sql = """
        INSERT INTO paper_intelligence.organisations
            (canonical_name, organisation_type, country_code, ror_id, openalex_id, metadata)
        VALUES (%s, %s, %s, %s, %s, %s::jsonb)
        RETURNING id
    """
    params = (
        canonical_name,
        organisation_type,
        country_code,
        ror_id,
        openalex_id,
        json.dumps(metadata or {}, default=str),
    )
    try:
        with conn.cursor() as cur:
            cur.execute(sql, params)
            return cur.fetchone()["id"]
    except errors.UniqueViolation:
        # Another writer created the same ror_id/openalex_id between our lookup
        # and this insert; re-resolve rather than failing the item.
        conn.rollback()
        for finder, value in (
            (find_organisation_by_ror, ror_id),
            (find_organisation_by_openalex, openalex_id),
        ):
            if value:
                existing = finder(conn, value)
                if existing is not None:
                    return existing
        existing = find_organisation_by_name(conn, canonical_name)
        if existing is not None:
            return existing
        raise


def _enrich_organisation(
    conn: Connection,
    organisation_id: int,
    *,
    ror_id: str | None,
    openalex_id: str | None,
    country_code: str | None,
    organisation_type: str | None,
    metadata: dict[str, Any] | None,
) -> None:
    """Fill in identifiers we did not have before. Never overwrites existing values."""
    with conn.cursor() as cur:
        cur.execute(
            """
            UPDATE paper_intelligence.organisations
            SET ror_id = COALESCE(ror_id, %s),
                openalex_id = COALESCE(openalex_id, %s),
                country_code = COALESCE(country_code, %s),
                organisation_type = COALESCE(organisation_type, %s),
                metadata = metadata || %s::jsonb,
                updated_at = NOW()
            WHERE id = %s
            """,
            (
                ror_id,
                openalex_id,
                country_code,
                organisation_type,
                json.dumps(metadata or {}, default=str),
                organisation_id,
            ),
        )


def apply_watchlist(
    conn: Connection,
    organisation_id: int,
    canonical_name: str,
    *,
    watchlist: Watchlist | None = None,
    ror_id: str | None = None,
    openalex_id: str | None = None,
    domain: str | None = None,
) -> WatchlistEntry | None:
    """Set is_org_of_interest / priority when the org is seeded. Returns the entry, if any.

    A non-match is a no-op: the organisation stays stored with its defaults.
    """
    active = watchlist if watchlist is not None else load_watchlist()
    entry = active.match(
        canonical_name, ror_id=ror_id, openalex_id=openalex_id, domain=domain
    )
    if entry is None:
        return None
    with conn.cursor() as cur:
        cur.execute(
            """
            UPDATE paper_intelligence.organisations
            SET is_org_of_interest = %s,
                priority = GREATEST(priority, %s),
                updated_at = NOW()
            WHERE id = %s
            """,
            (entry.is_org_of_interest, entry.priority, organisation_id),
        )
    add_domain_aliases(conn, organisation_id, entry.domains, confidence=1.0)
    for alias in entry.aliases:
        add_alias(conn, organisation_id, alias, "name", confidence=1.0)
    return entry


def seed_watchlist_organisations(
    conn: Connection, *, watchlist: Watchlist | None = None
) -> list[int]:
    """Ensure every seeded organisation exists. Safe to call with an empty watchlist."""
    active = watchlist if watchlist is not None else load_watchlist()
    ids: list[int] = []
    for entry in active.entries:
        ids.append(
            find_or_create_organisation(
                conn,
                entry.canonical_name,
                ror_id=entry.ror_id,
                openalex_id=entry.openalex_id,
                country_code=entry.country_code,
                organisation_type=entry.organisation_type,
                metadata={"source": "watchlist_seed"},
                watchlist=active,
            )
        )
    return ids
