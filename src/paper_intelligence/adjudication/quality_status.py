"""Derive paper_intelligence_current.quality_status from quality rows + attempts."""

from __future__ import annotations

from typing import Any


def quality_result_is_current(
    result_meta: dict[str, Any] | None,
    *,
    stage_version: str,
    prompt_version: str,
    policy_version: str,
    model: str,
) -> bool:
    """True when a classification result matches the live quality versions + model."""
    if not result_meta:
        return False
    return (
        str(result_meta.get("stage_version") or "") == stage_version
        and str(result_meta.get("prompt_version") or "") == prompt_version
        and str(result_meta.get("policy_version") or "") == policy_version
        and str(result_meta.get("model") or "") == model
    )


def derive_quality_status(
    *,
    has_current_quality_row: bool,
    route_decision: str | None,
    route_reason: str | None,
    latest_attempt_status: str | None,
    latest_attempt_error: str | None = None,
    gate_passed: bool = False,
    has_screen: bool = False,
) -> tuple[str, str]:
    """Return (quality_status, selection_reason).

    Vocabulary: scored | failed | pending | not_selected | skipped.
    """
    if has_current_quality_row:
        return "scored", "scored_quality_result_current_versions"

    if route_decision == "selected":
        if latest_attempt_status == "failed":
            err = (latest_attempt_error or "quality_attempt_failed").strip()
            return "failed", f"quality_attempt_failed:{err[:200]}"
        if latest_attempt_status == "succeeded":
            # Succeeded attempt but no current classification row — data inconsistency.
            return "pending", "inconsistent_attempt_without_result"
        return "pending", f"pending_quality_score:{route_reason or 'selected'}"

    if route_decision == "not_selected":
        return "not_selected", route_reason or "not_selected"

    if route_decision is not None:
        # blocked / other
        return "skipped", route_reason or str(route_decision)

    if gate_passed:
        return "not_selected", "screen_gate_passed_router_decision_unavailable"
    if has_screen:
        return "skipped", "blocked_or_no_screen_gate_pass"
    return "skipped", "no_screen_result"
