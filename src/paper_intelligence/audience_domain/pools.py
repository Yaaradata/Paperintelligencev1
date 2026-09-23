"""Tech / product pool membership helpers (AUDIENCE_POLICY aware)."""

from __future__ import annotations

from typing import Any

from paper_intelligence.common.config import (
    AUDIENCE_POLICY,
    PRODUCT_POOL_MIN,
    TECH_POOL_MIN,
)

METHOD_APPLICATIONS = frozenset({"general_method", "scientific_research"})
TECH_AUDIENCES = frozenset({"practitioner", "technical_leadership", "student"})
BUSINESS_AUDIENCE = "enterprise_adoption"


def in_tech_pool_v002(
    row: dict[str, Any],
    *,
    tech_min: float = TECH_POOL_MIN,
) -> bool:
    """v002 tech pool: tech_relevance >= threshold (v001 rows ignored)."""
    if str(row.get("audience_policy_version") or "") != "v002":
        return False
    score = row.get("tech_relevance")
    if score is None:
        return False
    try:
        return float(score) >= float(tech_min)
    except (TypeError, ValueError):
        return False


def in_product_pool_v002(
    row: dict[str, Any],
    *,
    product_min: float = PRODUCT_POOL_MIN,
) -> bool:
    """v002 product pool: product_relevance >= threshold (v001 rows ignored).

    Sector application_domain alone never qualifies — only the seat score.
    """
    if str(row.get("audience_policy_version") or "") != "v002":
        return False
    score = row.get("product_relevance")
    if score is None:
        return False
    try:
        return float(score) >= float(product_min)
    except (TypeError, ValueError):
        return False


def in_tech_pool_v001(row: dict[str, Any]) -> bool:
    audiences = {str(a).lower() for a in (row.get("audiences") or [])}
    apps = {str(a).lower() for a in (row.get("application_domains") or [])}
    if not audiences & TECH_AUDIENCES:
        return False
    if BUSINESS_AUDIENCE in audiences:
        return False
    if apps - METHOD_APPLICATIONS:
        return False
    return True


def in_business_pool_v001(row: dict[str, Any]) -> bool:
    audiences = {str(a).lower() for a in (row.get("audiences") or [])}
    apps = {str(a).lower() for a in (row.get("application_domains") or [])}
    if BUSINESS_AUDIENCE in audiences:
        return True
    if apps - METHOD_APPLICATIONS:
        return True
    return False


def pool_membership(
    row: dict[str, Any],
    *,
    policy: str | None = None,
    tech_min: float = TECH_POOL_MIN,
    product_min: float = PRODUCT_POOL_MIN,
) -> dict[str, bool]:
    """Return {tech, product} membership flags for a current-state row."""
    pol = (policy or AUDIENCE_POLICY).strip().lower()
    if pol == "v002":
        return {
            "tech": in_tech_pool_v002(row, tech_min=tech_min),
            "product": in_product_pool_v002(row, product_min=product_min),
        }
    return {
        "tech": in_tech_pool_v001(row),
        "product": in_business_pool_v001(row),
    }
