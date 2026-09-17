"""Closed vocabularies loaded from the versioned classification policy."""

from __future__ import annotations

from functools import lru_cache
from typing import Any

import yaml

from paper_intelligence.common.config import POLICIES_DIR

POLICY_VERSION = "v001"


@lru_cache(maxsize=4)
def load_policy(version: str = POLICY_VERSION) -> dict[str, Any]:
    path = POLICIES_DIR / "classification" / f"{version}.yaml"
    return yaml.safe_load(path.read_text(encoding="utf-8")) or {}


def audiences(version: str = POLICY_VERSION) -> list[str]:
    return list(load_policy(version).get("audience_relevance") or [])


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
