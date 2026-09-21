"""Load the affiliation_resolution policy document."""

from __future__ import annotations

from functools import lru_cache
from typing import Any

import yaml

from paper_intelligence.common.config import POLICIES_DIR

POLICY_NAME = "affiliation_resolution"
DEFAULT_POLICY_VERSION = "v001"

PRECEDENCE: tuple[str, ...] = (
    "llm_affiliation_judge",
    "explicit_paper_affiliation",
    "strong_deterministic",
    "ror_canonical_match",
    "openalex_paper_specific",
    "author_profile_secondary",
)


@lru_cache(maxsize=8)
def load_policy(version: str = DEFAULT_POLICY_VERSION) -> dict[str, Any]:
    """Read policies/affiliation_resolution/<version>.yaml. Missing file → defaults."""
    path = POLICIES_DIR / POLICY_NAME / f"{version}.yaml"
    if not path.exists():
        return {"policy_version": version, "precedence": list(PRECEDENCE)}
    document = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    if not isinstance(document, dict):
        return {"policy_version": version, "precedence": list(PRECEDENCE)}
    document.setdefault("policy_version", version)
    return document


def policy_version(version: str = DEFAULT_POLICY_VERSION) -> str:
    return str(load_policy(version).get("policy_version") or version)


def requires_literal_org_name(version: str = DEFAULT_POLICY_VERSION) -> bool:
    grounding = load_policy(version).get("grounding") or {}
    return bool(grounding.get("require_literal_org_name_in_evidence", True))
