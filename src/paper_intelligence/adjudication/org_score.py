"""Institutional standing: verified affiliation evidence → organisation score.

Applied only AFTER blinded quality scoring, as a capped additive boost. The
score is never an input to the rubric, so a well-known lab cannot inflate the
quality judgement itself.

`organisation_score` is a property of the organisation (watchlist priority or
unlisted-resolved baseline). It does NOT vary by paper. What varies per paper
is evidence strength, which scales only the additive `org_boost`.
"""

from __future__ import annotations

from typing import Any, Sequence

from paper_intelligence.quality.stage import MAX_ORG_BOOST

# Paper-specific evidence carries full weight. Author-profile evidence says
# where a person usually works, not who backed THIS paper, so it is halved.
EVIDENCE_WEIGHTS = {
    "explicit_paper_affiliation": 1.0,
    "email_domain": 1.0,
    "ror_canonical_match": 0.9,
    "openalex_paper_specific": 0.9,
    "author_profile_secondary": 0.5,
    "paper_affiliation": 1.0,
    "ror_match": 0.9,
    "alias_match": 0.9,
    "openalex_authorship": 0.9,
    "author_profile": 0.5,
}

MIN_CONFIDENCE = 0.6

# Watchlist priority → organisation standing on the 0-10 display scale.
# Constant for a given organisation; never multiplied by per-paper confidence.
PRIORITY_SCORES = {3: 10.0, 2: 8.0, 1: 6.0}
UNLISTED_RESOLVED_SCORE = 3.0


def _evidence_weight(evidence_type: str | None) -> float:
    return EVIDENCE_WEIGHTS.get((evidence_type or "").strip().lower(), 0.5)


def _org_standing(row: dict[str, Any]) -> float:
    if row.get("is_org_of_interest"):
        return float(PRIORITY_SCORES.get(int(row.get("priority") or 0), 6.0))
    return float(UNLISTED_RESOLVED_SCORE)


def organisation_score(rows: Sequence[dict[str, Any]]) -> dict[str, Any]:
    """Score one paper's affiliation evidence.

    `rows` are paper_author_affiliations joined to organisations, each with
    organisation_id, canonical_name, priority, is_org_of_interest,
    evidence_type, confidence.

    Returns:
      organisation_score — constant standing for the chosen organisation
      org_boost          — capped additive boost, scaled by THIS paper's evidence
      evidence_*         — why that org was attributed to this paper
    """
    best: dict[str, Any] | None = None
    considered = 0

    for row in rows:
        confidence = row.get("confidence")
        confidence = float(confidence) if confidence is not None else 1.0
        if confidence < MIN_CONFIDENCE:
            continue
        if row.get("organisation_id") is None:
            continue
        considered += 1

        standing = _org_standing(row)
        weight = _evidence_weight(row.get("evidence_type"))
        evidence_strength = weight * min(1.0, confidence)
        # Prefer the strongest evidence; break ties toward higher standing.
        rank_key = (evidence_strength, standing)

        if best is None or rank_key > best["_rank"]:
            best = {
                "_rank": rank_key,
                "organisation_score": round(standing, 1),
                "organisation_id": int(row["organisation_id"]),
                "organisation_name": row.get("canonical_name"),
                "evidence_type": row.get("evidence_type"),
                "evidence_confidence": round(confidence, 3),
                "evidence_strength": round(evidence_strength, 3),
                "is_org_of_interest": bool(row.get("is_org_of_interest")),
            }

    if best is None:
        return {
            "organisation_score": 0.0,
            "org_boost": 0.0,
            "organisation_id": None,
            "organisation_name": None,
            "evidence_type": None,
            "evidence_considered": considered,
            "status": "unresolved" if rows else "no_evidence_supplied",
        }

    # Standing maps to the boost ceiling; evidence strength scales how much of
    # that ceiling this paper earns. Same org → same organisation_score always.
    boost = min(
        MAX_ORG_BOOST,
        (best["organisation_score"] / 10.0) * MAX_ORG_BOOST * best["evidence_strength"],
    )
    best.pop("_rank", None)
    return {
        **best,
        "org_boost": round(boost, 4),
        "evidence_considered": considered,
        "status": "resolved",
    }
