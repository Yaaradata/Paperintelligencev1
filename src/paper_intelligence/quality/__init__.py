"""quality stage package."""

from paper_intelligence.quality.stage import (
    MAX_ORG_BOOST,
    MAX_PERSON_BOOST,
    POLICY_VERSION,
    PROMPT_VERSION,
    STAGE_NAME,
    STAGE_VERSION,
    build_user_prompt,
    composite_score,
    parse_response,
    run_window,
    select_notable_org_survivors,
    select_notable_person_survivors,
    select_quality_candidates,
    select_top_slice,
)

__all__ = [
    "MAX_ORG_BOOST",
    "MAX_PERSON_BOOST",
    "POLICY_VERSION",
    "PROMPT_VERSION",
    "STAGE_NAME",
    "STAGE_VERSION",
    "build_user_prompt",
    "composite_score",
    "parse_response",
    "run_window",
    "select_notable_org_survivors",
    "select_notable_person_survivors",
    "select_quality_candidates",
    "select_top_slice",
]
