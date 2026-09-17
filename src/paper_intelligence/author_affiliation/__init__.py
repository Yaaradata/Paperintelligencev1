"""Affiliation stage: grounded author→organisation evidence, append-only."""

from paper_intelligence.author_affiliation.grounding import is_grounded
from paper_intelligence.author_affiliation.policy import (
    DEFAULT_POLICY_VERSION,
    PRECEDENCE,
    load_policy,
    policy_version,
)
from paper_intelligence.author_affiliation.runner import run_window, select_window
from paper_intelligence.author_affiliation.stage import (
    EVIDENCE_EMAIL,
    EVIDENCE_EXPLICIT,
    EVIDENCE_OPENALEX,
    EVIDENCE_PROFILE,
    EVIDENCE_ROR,
    OUTCOME_NO_EVIDENCE,
    OUTCOME_RESOLVED,
    OUTCOME_REVIEW,
    STAGE_NAME,
    STAGE_VERSION,
    AffiliationStage,
)

__all__ = [
    "AffiliationStage",
    "DEFAULT_POLICY_VERSION",
    "EVIDENCE_EMAIL",
    "EVIDENCE_EXPLICIT",
    "EVIDENCE_OPENALEX",
    "EVIDENCE_PROFILE",
    "EVIDENCE_ROR",
    "OUTCOME_NO_EVIDENCE",
    "OUTCOME_RESOLVED",
    "OUTCOME_REVIEW",
    "PRECEDENCE",
    "STAGE_NAME",
    "STAGE_VERSION",
    "is_grounded",
    "load_policy",
    "policy_version",
    "run_window",
    "select_window",
]
