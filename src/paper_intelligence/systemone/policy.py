"""Load versioned System One question policies and build API payloads."""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path
from typing import Any

import yaml

from paper_intelligence.common.config import POLICIES_DIR

SCORE_LEVEL_COUNT = 10  # System One max; levels 0..9 → map to screen 0..10 via *10/9


@lru_cache(maxsize=16)
def load_systemone_policy(name: str, version: str) -> dict[str, Any]:
    """Load ``policies/systemone/{name}_{version}.yaml``."""
    path = POLICIES_DIR / "systemone" / f"{name}_{version}.yaml"
    if not path.is_file():
        raise FileNotFoundError(f"System One policy not found: {path}")
    data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    if not isinstance(data, dict):
        raise ValueError(f"System One policy must be a mapping: {path}")
    return data


def state_from_paper(paper: dict[str, Any]) -> str:
    """State for Jev: title + abstract only (no categories, orgs, or ids)."""
    title = " ".join(str(paper.get("title") or "").split()).strip()
    abstract = " ".join(str(paper.get("abstract") or "").split()).strip()
    return f"Title: {title}\nAbstract: {abstract}"


def build_questions(policy: dict[str, Any]) -> dict[str, Any]:
    """Convert policy ``questions`` block into the System One request shape."""
    raw = policy.get("questions") or {}
    if not isinstance(raw, dict) or not raw:
        raise ValueError("policy.questions must be a non-empty mapping")
    out: dict[str, Any] = {}
    for key, spec in raw.items():
        if not isinstance(spec, dict):
            raise ValueError(f"question {key!r} must be a mapping")
        qtype = str(spec.get("type") or "").strip()
        instructions = str(spec.get("instructions") or "").strip()
        if not qtype or not instructions:
            raise ValueError(f"question {key!r} requires type and instructions")
        entry: dict[str, Any] = {"type": qtype, "instructions": instructions}
        if qtype == "score":
            criteria = spec.get("criteria")
            if not isinstance(criteria, list) or len(criteria) < 2:
                raise ValueError(f"score question {key!r} needs criteria list (2–10)")
            if len(criteria) > SCORE_LEVEL_COUNT:
                raise ValueError(
                    f"score question {key!r} has {len(criteria)} levels; "
                    f"System One allows at most {SCORE_LEVEL_COUNT}"
                )
            entry["criteria"] = [str(c) for c in criteria]
        elif qtype == "choice":
            criteria = spec.get("criteria")
            if not isinstance(criteria, dict) or not criteria:
                raise ValueError(f"choice question {key!r} needs criteria mapping")
            if len(criteria) > 255:
                raise ValueError(f"choice question {key!r} exceeds 255 options")
            entry["criteria"] = {str(k): str(v) for k, v in criteria.items()}
        elif qtype == "noul":
            pass
        else:
            raise ValueError(f"unsupported question type {qtype!r} for {key!r}")
        out[str(key)] = entry
    return out


def score_to_screen_scale(raw_score: float | None, *, n_levels: int = SCORE_LEVEL_COUNT) -> float | None:
    """Map System One score on levels 0..n_levels-1 onto the screen 0–10 scale."""
    if raw_score is None:
        return None
    top = max(1, int(n_levels) - 1)
    return round(float(raw_score) * (10.0 / top) * 2) / 2.0


def parse_answers(answers: dict[str, Any], policy: dict[str, Any]) -> dict[str, Any]:
    """Normalise System One answers using the policy question types."""
    questions = policy.get("questions") or {}
    parsed: dict[str, Any] = {}
    confidences: list[float] = []
    for key, spec in questions.items():
        ans = answers.get(key) if isinstance(answers, dict) else None
        if not isinstance(ans, dict):
            parsed[key] = None
            continue
        qtype = str(spec.get("type") or ans.get("type") or "")
        if qtype == "noul":
            try:
                noul = float(ans.get("noul"))
            except (TypeError, ValueError):
                noul = None
            parsed[key] = {"type": "noul", "noul": noul}
            if noul is not None:
                # Distance from 0.5 as a crude confidence proxy for noul.
                confidences.append(abs(noul - 0.5) * 2.0)
        elif qtype == "score":
            try:
                score = float(ans.get("score"))
            except (TypeError, ValueError):
                score = None
            try:
                confidence = float(ans.get("confidence"))
            except (TypeError, ValueError):
                confidence = None
            n_levels = len(spec.get("criteria") or [])
            parsed[key] = {
                "type": "score",
                "score": score,
                "score_0_10": score_to_screen_scale(score, n_levels=n_levels or SCORE_LEVEL_COUNT),
                "confidence": confidence,
                "probabilities": ans.get("probabilities"),
            }
            if confidence is not None:
                confidences.append(confidence)
        elif qtype == "choice":
            try:
                confidence = float(ans.get("confidence"))
            except (TypeError, ValueError):
                confidence = None
            parsed[key] = {
                "type": "choice",
                "choice": ans.get("choice"),
                "confidence": confidence,
                "probabilities": ans.get("probabilities"),
            }
            if confidence is not None:
                confidences.append(confidence)
        else:
            parsed[key] = ans
    parsed["_mean_confidence"] = (
        sum(confidences) / len(confidences) if confidences else None
    )
    return parsed


def policy_path(name: str, version: str) -> Path:
    return POLICIES_DIR / "systemone" / f"{name}_{version}.yaml"
