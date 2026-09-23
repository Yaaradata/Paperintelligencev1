"""Closed vocabularies loaded from the versioned classification policy."""

from __future__ import annotations

from functools import lru_cache
from typing import Any

import yaml

from paper_intelligence.common.config import AUDIENCE_POLICY, POLICIES_DIR

# Default follows AUDIENCE_POLICY (v001 until Phase 7c cutover).
POLICY_VERSION = "v002" if AUDIENCE_POLICY == "v002" else "v001"


@lru_cache(maxsize=8)
def load_policy(version: str = POLICY_VERSION) -> dict[str, Any]:
    path = POLICIES_DIR / "classification" / f"{version}.yaml"
    return yaml.safe_load(path.read_text(encoding="utf-8")) or {}


def audiences(version: str = POLICY_VERSION) -> list[str]:
    """Audience labels for v001. For v002, returns [] (seat scores replace labels)."""
    if version == "v002":
        return list(load_policy(version).get("audience_relevance") or [])
    return list(load_policy(version).get("audience_relevance") or [])


def seat_score_fields(version: str = POLICY_VERSION) -> dict[str, Any]:
    """Seat scoring field docs from v002 (empty for v001)."""
    return dict(load_policy(version).get("seat_scores") or {})


def domains(version: str = POLICY_VERSION) -> list[str]:
    return list(load_policy(version).get("domain") or [])


def subdomains_by_domain(version: str = POLICY_VERSION) -> dict[str, list[str]]:
    return {k: list(v or []) for k, v in (load_policy(version).get("subdomains") or {}).items()}


def all_subdomains(version: str = POLICY_VERSION) -> set[str]:
    return {s for values in subdomains_by_domain(version).values() for s in values}


def application_domains(version: str = POLICY_VERSION) -> list[str]:
    return list(load_policy(version).get("application_domain") or [])


def vocabulary_block(version: str = POLICY_VERSION) -> str:
    """Inline vocabulary text for the prompt.

    Omitting these previously let a model invent values that a CHECK constraint
    silently dropped, so they are always supplied with the request.
    """
    sub_lines = "\n".join(
        f"  {domain}: {' | '.join(values)}"
        for domain, values in subdomains_by_domain(version).items()
    )
    if version == "v002":
        seats = seat_score_fields(version)
        seat_lines = []
        for name, meta in seats.items():
            rng = meta.get("range") or [0.0, 10.0]
            inc = meta.get("increment", 0.5)
            reason = meta.get("reason_field", f"{name}_reason")
            seat_lines.append(
                f"  {name}: {rng[0]}–{rng[1]} in {inc} increments; "
                f"{reason}: one short sentence"
            )
        seat_block = (
            "seat scores (independent; both high / one high / both low all valid):\n"
            + "\n".join(seat_lines)
            if seat_lines
            else "seat scores: tech_relevance, product_relevance (0.0–10.0, 0.5 steps)"
        )
        return (
            seat_block
            + "\n\ndomain (choose exactly one):\n  "
            + " | ".join(domains(version))
            + "\n\nsubdomains (choose zero or more, only from the chosen domain):\n"
            + sub_lines
            + "\n\napplication_domain (choose one or more; general_method is exclusive; "
            "does NOT decide pool membership):\n  "
            + " | ".join(application_domains(version))
        )
    return (
        "audience_relevance (choose one or more):\n  "
        + " | ".join(audiences(version))
        + "\n\ndomain (choose exactly one):\n  "
        + " | ".join(domains(version))
        + "\n\nsubdomains (choose zero or more, only from the chosen domain):\n"
        + sub_lines
        + "\n\napplication_domain (choose one or more; general_method is exclusive):\n  "
        + " | ".join(application_domains(version))
    )
