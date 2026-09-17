"""Organisation canonicalisation.

Resolved organisations are always stored. The watchlist in
`config/organisations.yaml` only decides `is_org_of_interest` / `priority`;
an unlisted organisation is never discarded.
"""

from paper_intelligence.organisation_resolution.repository import (
    add_alias,
    add_domain_aliases,
    apply_watchlist,
    domain_candidates,
    domain_of,
    find_or_create_organisation,
    find_organisation_by_alias,
    find_organisation_by_email_domain,
    find_organisation_by_name,
    find_organisation_by_openalex,
    find_organisation_by_ror,
    get_organisation,
    is_public_email_domain,
    seed_watchlist_organisations,
)
from paper_intelligence.organisation_resolution.watchlist import (
    Watchlist,
    WatchlistEntry,
    load_watchlist,
    normalise_key,
)

__all__ = [
    "Watchlist",
    "WatchlistEntry",
    "add_alias",
    "add_domain_aliases",
    "apply_watchlist",
    "domain_candidates",
    "domain_of",
    "find_or_create_organisation",
    "find_organisation_by_alias",
    "find_organisation_by_email_domain",
    "find_organisation_by_name",
    "find_organisation_by_openalex",
    "find_organisation_by_ror",
    "get_organisation",
    "is_public_email_domain",
    "load_watchlist",
    "normalise_key",
    "seed_watchlist_organisations",
]
