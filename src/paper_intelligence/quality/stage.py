"""Stage: quality (Pass 2) — PAID, reasoning on, top slice of screen survivors.

The model never sees authors, affiliations or organisations: the payload is
title, categories and abstract only. Institutional standing enters later as a
capped additive boost, after scoring.
"""

from __future__ import annotations

from typing import Any, Sequence

from psycopg import Connection

from paper_intelligence.common.batch_runner import BatchStats, run_batches
from paper_intelligence.common.config import (
    GATE_PERCENTILE,
    QUALITY_BATCH_SIZE,
    QUALITY_MODEL,
    QUALITY_REASONING_EFFORT,
    estimate_cost_usd,
    read_prompt,
)
from paper_intelligence.common.llm_stage import (
    call_llm_logged,
    paper_block,
    parse_json_object,
    random_batches,
)
from paper_intelligence.db import (
    connect,
    fetch_papers,
    insert_classification_results,
    latest_screen_scores,
)

STAGE_NAME = "quality"
STAGE_VERSION = "v001"
PROMPT_VERSION = "v001"
POLICY_VERSION = "v001"

RUBRIC_DIMENSIONS = (
    "technical_significance",
    "apparent_novelty",
    "practical_applicability",
    "professional_value",
    "learning_value",
    "evidence_strength",
)

WEIGHTS = {
    "technical_significance": 0.28,
    "apparent_novelty": 0.24,
    "practical_applicability": 0.20,
    "professional_value": 0.16,
    "learning_value": 0.12,
}

# ai_relevance is excluded: it is near-constant post-gate and only compresses
# the ranking scale.
RANK_DIMENSIONS = ("technical_significance", "apparent_novelty", "evidence_strength")

MAX_ORG_BOOST = 0.5
MAX_PERSON_BOOST = 0.3


def composite_score(
    scores: dict[str, float], *, org_boost: float = 0.0, person_boost: float = 0.0
) -> dict[str, float]:
    """Rubric composite with the evidence multiplier applied exactly once."""
    quality = sum(WEIGHTS[dim] * float(scores[dim]) for dim in WEIGHTS)
    evidence_factor = 0.70 + 0.03 * float(scores["evidence_strength"])
    org = min(max(org_boost, 0.0), MAX_ORG_BOOST)
    person = min(max(person_boost, 0.0), MAX_PERSON_BOOST)
    final = min(10.0, quality * evidence_factor + org + person)
    return {
        "quality": round(quality, 4),
        "evidence_factor": round(evidence_factor, 4),
        "org_boost": round(org, 4),
        "person_boost": round(person, 4),
        "final": round(final, 4),
    }


def select_top_slice(
    conn: Connection,
    *,
    date_from: str,
    date_until: str,
    gate_percentile: float = GATE_PERCENTILE,
    threshold_key: str = "gate",
) -> list[int]:
    """Screen survivors ranked on mean(tech, novelty, evidence); keep the top slice."""
    ranked: list[tuple[float, int]] = []
    for row in latest_screen_scores(conn, date_from=date_from, date_until=date_until):
        result = row["result_json"] or {}
        gate = result.get(threshold_key) or {}
        if not gate.get("passed"):
            continue
        try:
            mean = sum(float(result[dim]) for dim in RANK_DIMENSIONS) / len(RANK_DIMENSIONS)
        except (KeyError, TypeError, ValueError):
            continue
        ranked.append((mean, int(row["content_item_id"])))

    if not ranked:
        return []
    ranked.sort(key=lambda pair: (-pair[0], pair[1]))
    keep = max(1, int(round(len(ranked) * (gate_percentile / 100.0))))
    return [content_id for _, content_id in ranked[:keep]]


def select_notable_org_survivors(
    conn: Connection,
    *,
    date_from: str,
    date_until: str,
) -> list[int]:
    """Screen-passed papers with at least one Org-of-Interest affiliation."""
    survivors = {
        int(row["content_item_id"])
        for row in latest_screen_scores(conn, date_from=date_from, date_until=date_until)
        if ((row["result_json"] or {}).get("gate") or {}).get("passed")
    }
    if not survivors:
        return []
    with conn.cursor() as cur:
        cur.execute(
            """
            SELECT DISTINCT a.content_item_id
            FROM paper_intelligence.paper_author_affiliations a
            JOIN paper_intelligence.organisations o ON o.id = a.organisation_id
            WHERE a.content_item_id = ANY(%s)
              AND o.is_org_of_interest IS TRUE
              AND o.active IS TRUE
              AND a.organisation_id IS NOT NULL
            ORDER BY a.content_item_id
            """,
            (list(survivors),),
        )
        return [int(row["content_item_id"]) for row in cur.fetchall()]


def select_notable_person_survivors(
    conn: Connection,
    *,
    date_from: str,
    date_until: str,
) -> list[int]:
    """Screen-passed papers linked to a Person-of-Interest (empty until people stage)."""
    survivors = {
        int(row["content_item_id"])
        for row in latest_screen_scores(conn, date_from=date_from, date_until=date_until)
        if ((row["result_json"] or {}).get("gate") or {}).get("passed")
    }
    if not survivors:
        return []
    with conn.cursor() as cur:
        cur.execute(
            """
            SELECT DISTINCT pp.content_item_id
            FROM paper_intelligence.papers_people pp
            JOIN paper_intelligence.people p ON p.id = pp.person_id
            WHERE pp.content_item_id = ANY(%s)
              AND p.is_person_of_interest IS TRUE
              AND p.active IS TRUE
            ORDER BY pp.content_item_id
            """,
            (list(survivors),),
        )
        return [int(row["content_item_id"]) for row in cur.fetchall()]


def select_quality_candidates(
    conn: Connection,
    *,
    date_from: str,
    date_until: str,
    gate_percentile: float = GATE_PERCENTILE,
) -> list[int]:
    """Quality router: top screen slice ∪ notable org ∪ notable person."""
    selected = set(
        select_top_slice(
            conn,
            date_from=date_from,
            date_until=date_until,
            gate_percentile=gate_percentile,
        )
    )
    selected.update(
        select_notable_org_survivors(conn, date_from=date_from, date_until=date_until)
    )
    selected.update(
        select_notable_person_survivors(conn, date_from=date_from, date_until=date_until)
    )
    return sorted(selected)


def build_user_prompt(papers: Sequence[dict[str, Any]]) -> str:
    blocks = "\n---\n".join(paper_block(p, max_abstract_chars=3000) for p in papers)
    ids = [p["content_item_id"] for p in papers]
    return (
        f"Score these {len(papers)} papers against the full rubric. Return one object "
        f"per paper, for exactly these content_item_id values: {ids}.\n\n{blocks}"
    )


def _score(value: Any) -> float | None:
    try:
        score = float(value)
    except (TypeError, ValueError):
        return None
    if score < 0.0 or score > 10.0:
        return None
    return round(score * 2) / 2


def parse_response(
    text: str, expected_ids: set[int]
) -> tuple[dict[int, dict[str, Any]], list[str]]:
    payload = parse_json_object(text)
    parsed: dict[int, dict[str, Any]] = {}
    problems: list[str] = []
    for entry in payload.get("papers") or []:
        try:
            content_id = int(entry.get("content_item_id"))
        except (TypeError, ValueError):
            problems.append("unparseable content_item_id")
            continue
        if content_id not in expected_ids:
            problems.append(f"unexpected content_item_id {content_id}")
            continue
        scores: dict[str, Any] = {}
        bad = False
        for dimension in RUBRIC_DIMENSIONS:
            value = _score(entry.get(dimension))
            if value is None:
                problems.append(f"{content_id}: invalid {dimension}={entry.get(dimension)!r}")
                bad = True
                break
            scores[dimension] = value
        if bad:
            continue
        reason_not_higher = (entry.get("reason_not_higher") or "").strip()
        if not reason_not_higher:
            problems.append(f"{content_id}: missing reason_not_higher")
        scores["so_what"] = (entry.get("so_what") or "").strip()
        scores["reason_not_higher"] = reason_not_higher
        confidence = _score(entry.get("confidence"))
        scores["confidence"] = confidence
        parsed[content_id] = scores
    missing = expected_ids - parsed.keys()
    if missing:
        problems.append(f"missing ids: {sorted(missing)}")
    return parsed, problems


def run_window(
    conn: Connection,
    content_item_ids: Sequence[int],
    *,
    run_id: str,
    stage_run_id: str,
    model: str = QUALITY_MODEL,
    batch_size: int = QUALITY_BATCH_SIZE,
    dry_run: bool = False,
) -> BatchStats:
    stats = BatchStats(papers_requested=len(content_item_ids))
    if not content_item_ids:
        return stats

    papers = fetch_papers(conn, content_item_ids)
    system_prompt = read_prompt("quality", PROMPT_VERSION)

    if dry_run:
        calls = -(-len(papers) // max(1, batch_size))
        chars = sum(len(paper_block(p, max_abstract_chars=3000)) for p in papers)
        stats.calls = calls
        stats.input_tokens = (chars + len(system_prompt) * calls) // 4
        # Reasoning models bill thinking tokens as output; budget generously.
        stats.output_tokens = len(papers) * 700
        stats.cost_usd = estimate_cost_usd(model, stats.input_tokens, stats.output_tokens)
        return stats

    batches = random_batches(papers, batch_size)

    def handle(batch: Sequence[dict[str, Any]]) -> None:
        expected = {p["content_item_id"] for p in batch}
        try:
            with connect() as batch_conn:
                result = call_llm_logged(
                    batch_conn,
                    model=model,
                    system_prompt=system_prompt,
                    user_prompt=build_user_prompt(batch),
                    prompt_version=PROMPT_VERSION,
                    stage_name=STAGE_NAME,
                    reasoning_effort=QUALITY_REASONING_EFFORT,
                    temperature=None,
                    max_tokens=6000,
                    run_id=run_id,
                    stage_run_id=stage_run_id,
                    entity=f"quality_{min(expected)}",
                    timeout=600.0,
                )
                parsed, problems = parse_response(result["content"], expected)
                rows = []
                for content_id, scores in parsed.items():
                    composite = composite_score(scores)
                    rows.append(
                        {
                            "content_item_id": content_id,
                            "task_type": "quality",
                            "result_json": {**scores, "composite": composite},
                            "method": "llm",
                            "provider": "openrouter",
                            "model": model,
                            "prompt_version": PROMPT_VERSION,
                            "policy_version": POLICY_VERSION,
                            "stage_version": STAGE_VERSION,
                            "confidence": (scores["confidence"] / 10.0)
                            if scores.get("confidence") is not None
                            else None,
                            "run_id": run_id,
                        }
                    )
                insert_classification_results(batch_conn, rows)
                batch_conn.commit()
            if problems:
                stats.add_warning("; ".join(problems))
            stats.add_call(
                succeeded=len(parsed),
                failed=len(expected) - len(parsed),
                input_tokens=result["input_tokens"],
                output_tokens=result["output_tokens"],
                cost=result["estimated_cost"],
            )
        except Exception as exc:  # noqa: BLE001
            stats.add_error(f"{type(exc).__name__}: {exc}", failed=len(expected))

    run_batches(batches, handle, label="quality")
    return stats
