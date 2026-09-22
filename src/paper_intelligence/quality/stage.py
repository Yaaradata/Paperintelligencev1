"""Stage: quality (Pass 2) — PAID, reasoning on, top slice of screen survivors.

The model never sees authors, affiliations or organisations: the payload is
title, categories and abstract only. Institutional standing enters later as a
capped additive boost, after scoring.

Quality *routing* eligibility is based on PI screen results (gate.passed), not
on research_radar.content_items.status. A screen pass enters the router; it does
not automatically imply a paid quality score.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any, Sequence

from psycopg import Connection

from paper_intelligence.common.batch_runner import BatchStats, run_batches
from paper_intelligence.common.budget import BudgetCap
from paper_intelligence.common.config import (
    GATE_PERCENTILE,
    QUALITY_BATCH_SIZE,
    QUALITY_MODEL,
    QUALITY_REASONING_EFFORT,
    ROUTER_PERCENTILE_SCOPE,
    estimate_cost_usd,
    read_prompt,
)
from paper_intelligence.common.llm_stage import (
    call_llm_logged,
    paper_block,
    parse_json_object,
    random_batches,
)
from paper_intelligence.common.content_hash import compute_content_hash
from paper_intelligence.db import (
    connect,
    fetch_papers,
    insert_classification_results,
    latest_screen_scores,
)
from paper_intelligence.quality.attempts import (
    record_quality_failures,
    record_quality_successes,
)
from paper_intelligence.author_affiliation.verify.judge_effective import (
    filter_affiliation_rows,
    load_judgment_exclusions,
    should_exclude_rejected,
)
from paper_intelligence.author_affiliation.verify.judge_persist import (
    JUDGE_VERSION_DEFAULT,
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


def _utc_published_date(value: Any) -> str | None:
    """UTC calendar date YYYY-MM-DD from a published_at value."""
    if value is None:
        return None
    if hasattr(value, "date"):
        # datetime → date in its timezone if aware; treat naive as UTC date.
        dt = value
        if getattr(dt, "tzinfo", None) is not None:
            from datetime import timezone

            return dt.astimezone(timezone.utc).date().isoformat()
        return dt.date().isoformat() if hasattr(dt, "hour") else dt.isoformat()
    text = str(value).strip()
    return text[:10] if text else None


def _rank_screen_survivors(
    screens: Sequence[dict[str, Any]],
    *,
    threshold_key: str = "gate",
) -> tuple[
    list[tuple[float, int]],
    dict[int, float],
    dict[int, bool],
    set[int],
    dict[int, str | None],
]:
    """Return (ranked, rank_means, gate_by_id, missing_dims, pub_day_by_id)."""
    ranked: list[tuple[float, int]] = []
    rank_means: dict[int, float] = {}
    gate_by_id: dict[int, bool] = {}
    missing_dims: set[int] = set()
    pub_day_by_id: dict[int, str | None] = {}
    for row in screens:
        cid = int(row["content_item_id"])
        pub_day_by_id[cid] = _utc_published_date(row.get("published_at"))
        result = row["result_json"] or {}
        gate = result.get(threshold_key) or {}
        passed = bool(gate.get("passed"))
        gate_by_id[cid] = passed
        if not passed:
            continue
        try:
            mean = sum(float(result[dim]) for dim in RANK_DIMENSIONS) / len(RANK_DIMENSIONS)
        except (KeyError, TypeError, ValueError):
            missing_dims.add(cid)
            continue
        ranked.append((mean, cid))
        rank_means[cid] = mean
    ranked.sort(key=lambda pair: (-pair[0], pair[1]))
    return ranked, rank_means, gate_by_id, missing_dims, pub_day_by_id


def _top_slice_ids(
    ranked: list[tuple[float, int]],
    *,
    gate_percentile: float,
    percentile_scope: str,
    pub_day_by_id: dict[int, str | None],
) -> tuple[set[int], dict[int, int], dict[int, int], dict[int, int]]:
    """Return (top_ids, position_by_id, survivors_n_by_id, keep_n_by_id).

    Position / survivor / keep counts are scoped to the ranking pool that
    selected the paper (whole window, or that paper's UTC day).
    """
    position_by_id: dict[int, int] = {}
    survivors_n_by_id: dict[int, int] = {}
    keep_n_by_id: dict[int, int] = {}
    top_ids: set[int] = set()

    if percentile_scope == "day":
        by_day: dict[str, list[tuple[float, int]]] = {}
        for mean, cid in ranked:
            day = pub_day_by_id.get(cid) or "_unknown"
            by_day.setdefault(day, []).append((mean, cid))
        for day, day_ranked in by_day.items():
            day_ranked.sort(key=lambda pair: (-pair[0], pair[1]))
            survivors_n = len(day_ranked)
            keep_n = (
                max(1, int(round(survivors_n * (gate_percentile / 100.0))))
                if survivors_n
                else 0
            )
            for i, (_, cid) in enumerate(day_ranked):
                position_by_id[cid] = i + 1
                survivors_n_by_id[cid] = survivors_n
                keep_n_by_id[cid] = keep_n
            top_ids.update(cid for _, cid in day_ranked[:keep_n])
    else:
        survivors_n = len(ranked)
        keep_n = (
            max(1, int(round(survivors_n * (gate_percentile / 100.0))))
            if survivors_n
            else 0
        )
        for i, (_, cid) in enumerate(ranked):
            position_by_id[cid] = i + 1
            survivors_n_by_id[cid] = survivors_n
            keep_n_by_id[cid] = keep_n
        top_ids = {cid for _, cid in ranked[:keep_n]}
    return top_ids, position_by_id, survivors_n_by_id, keep_n_by_id


def select_top_slice(
    conn: Connection,
    *,
    date_from: str,
    date_until: str,
    gate_percentile: float = GATE_PERCENTILE,
    threshold_key: str = "gate",
    percentile_scope: str = ROUTER_PERCENTILE_SCOPE,
) -> list[int]:
    """Screen survivors ranked on mean(tech, novelty, evidence); keep the top slice.

    ``percentile_scope="window"`` (default): one ranking over the whole date
    window. ``"day"``: top-N% computed separately per UTC ``published_at`` date.
    """
    scope = percentile_scope if percentile_scope in {"window", "day"} else "window"
    screens = latest_screen_scores(conn, date_from=date_from, date_until=date_until)
    ranked, _, _, _, pub_day_by_id = _rank_screen_survivors(
        screens, threshold_key=threshold_key
    )
    if not ranked:
        return []
    top_ids, _, _, _ = _top_slice_ids(
        ranked,
        gate_percentile=gate_percentile,
        percentile_scope=scope,
        pub_day_by_id=pub_day_by_id,
    )
    # Stable order: overall rank then id.
    return [cid for _, cid in ranked if cid in top_ids]


def select_notable_org_survivors(
    conn: Connection,
    *,
    date_from: str,
    date_until: str,
    apply_judge_effective: bool = True,
    judge_version: str = JUDGE_VERSION_DEFAULT,
) -> list[int]:
    """Screen-passed papers with at least one Org-of-Interest affiliation.

    When ``apply_judge_effective`` is True (default), affiliations rejected by a
    resolved HTML/OA judge decision are excluded at read time — matching
    adjudication — without mutating stored evidence.
    """
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
            SELECT a.content_item_id, a.organisation_id, a.confidence,
                   o.is_org_of_interest
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
        aff_rows = [dict(r) for r in cur.fetchall()]

    if not apply_judge_effective:
        return sorted({int(r["content_item_id"]) for r in aff_rows})

    by_paper: dict[int, list[dict[str, Any]]] = {}
    for row in aff_rows:
        by_paper.setdefault(int(row["content_item_id"]), []).append(row)

    exclusions = load_judgment_exclusions(
        conn, list(by_paper.keys()), judge_version=judge_version
    )
    selected: list[int] = []
    for cid, rows in by_paper.items():
        excl = exclusions.get(cid) or {}
        decision = excl.get("decision")
        judge_called = bool(excl.get("judge_called"))
        rejected = excl.get("rejected_organisation_ids") or []
        if should_exclude_rejected(decision, judge_called=judge_called):
            effective = filter_affiliation_rows(
                rows,
                rejected_organisation_ids=rejected,
                decision=decision,
                judge_called=judge_called,
            )
        else:
            effective = list(rows)
        if any(r.get("organisation_id") is not None for r in effective):
            selected.append(cid)
    return sorted(selected)


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
    percentile_scope: str = ROUTER_PERCENTILE_SCOPE,
    apply_judge_effective: bool = True,
) -> list[int]:
    """Quality router: top screen slice ∪ notable org ∪ notable person."""
    selected = set(
        select_top_slice(
            conn,
            date_from=date_from,
            date_until=date_until,
            gate_percentile=gate_percentile,
            percentile_scope=percentile_scope,
        )
    )
    selected.update(
        select_notable_org_survivors(
            conn,
            date_from=date_from,
            date_until=date_until,
            apply_judge_effective=apply_judge_effective,
        )
    )
    selected.update(
        select_notable_person_survivors(conn, date_from=date_from, date_until=date_until)
    )
    return sorted(selected)


@dataclass(frozen=True)
class QualityRoutingDecision:
    """Explicit router outcome for one latest PI screen row."""

    content_item_id: int
    decision: str  # selected | not_selected | blocked
    reason: str
    rank_mean: float | None = None
    rank_position: int | None = None
    survivors_in_window: int | None = None
    top_slice_keep: int | None = None
    gate_percentile: float | None = None
    percentile_scope: str | None = None

    def as_dict(self) -> dict[str, Any]:
        return asdict(self)


def explain_quality_routing(
    conn: Connection,
    *,
    date_from: str,
    date_until: str,
    gate_percentile: float = GATE_PERCENTILE,
    percentile_scope: str = ROUTER_PERCENTILE_SCOPE,
    apply_judge_effective: bool = True,
) -> list[QualityRoutingDecision]:
    """Record a routing decision for every latest PI screen result in the window.

    Decisions:
    - selected / selected_top_slice | selected_notable_org | selected_notable_person
    - not_selected / not_selected_below_gate_percentile
    - blocked / blocked_screen_gate_failed | blocked_missing_rank_dimensions

    Does not call the LLM. Does not mutate scores.
    """
    scope = percentile_scope if percentile_scope in {"window", "day"} else "window"
    screens = latest_screen_scores(conn, date_from=date_from, date_until=date_until)
    ranked, rank_means, gate_by_id, missing_dims, pub_day_by_id = _rank_screen_survivors(
        screens
    )
    top_ids, position, survivors_n_by_id, keep_n_by_id = _top_slice_ids(
        ranked,
        gate_percentile=gate_percentile,
        percentile_scope=scope,
        pub_day_by_id=pub_day_by_id,
    )

    notable_org = set(
        select_notable_org_survivors(
            conn,
            date_from=date_from,
            date_until=date_until,
            apply_judge_effective=apply_judge_effective,
        )
    )
    notable_person = set(
        select_notable_person_survivors(conn, date_from=date_from, date_until=date_until)
    )

    decisions: list[QualityRoutingDecision] = []
    for row in screens:
        cid = int(row["content_item_id"])
        if not gate_by_id.get(cid):
            decisions.append(
                QualityRoutingDecision(
                    content_item_id=cid,
                    decision="blocked",
                    reason="blocked_screen_gate_failed",
                    gate_percentile=gate_percentile,
                    percentile_scope=scope,
                )
            )
            continue
        if cid in missing_dims:
            decisions.append(
                QualityRoutingDecision(
                    content_item_id=cid,
                    decision="blocked",
                    reason="blocked_missing_rank_dimensions",
                    gate_percentile=gate_percentile,
                    percentile_scope=scope,
                )
            )
            continue

        mean = rank_means.get(cid)
        pos = position.get(cid)
        survivors_n = survivors_n_by_id.get(cid)
        keep_n = keep_n_by_id.get(cid)
        if cid in top_ids:
            reason = "selected_top_slice"
            if cid in notable_org:
                reason = "selected_top_slice_and_notable_org"
            elif cid in notable_person:
                reason = "selected_top_slice_and_notable_person"
            decisions.append(
                QualityRoutingDecision(
                    content_item_id=cid,
                    decision="selected",
                    reason=reason,
                    rank_mean=round(mean, 4) if mean is not None else None,
                    rank_position=pos,
                    survivors_in_window=survivors_n,
                    top_slice_keep=keep_n,
                    gate_percentile=gate_percentile,
                    percentile_scope=scope,
                )
            )
        elif cid in notable_org:
            decisions.append(
                QualityRoutingDecision(
                    content_item_id=cid,
                    decision="selected",
                    reason="selected_notable_org",
                    rank_mean=round(mean, 4) if mean is not None else None,
                    rank_position=pos,
                    survivors_in_window=survivors_n,
                    top_slice_keep=keep_n,
                    gate_percentile=gate_percentile,
                    percentile_scope=scope,
                )
            )
        elif cid in notable_person:
            decisions.append(
                QualityRoutingDecision(
                    content_item_id=cid,
                    decision="selected",
                    reason="selected_notable_person",
                    rank_mean=round(mean, 4) if mean is not None else None,
                    rank_position=pos,
                    survivors_in_window=survivors_n,
                    top_slice_keep=keep_n,
                    gate_percentile=gate_percentile,
                    percentile_scope=scope,
                )
            )
        else:
            decisions.append(
                QualityRoutingDecision(
                    content_item_id=cid,
                    decision="not_selected",
                    reason="not_selected_below_gate_percentile",
                    rank_mean=round(mean, 4) if mean is not None else None,
                    rank_position=pos,
                    survivors_in_window=survivors_n,
                    top_slice_keep=keep_n,
                    gate_percentile=gate_percentile,
                    percentile_scope=scope,
                )
            )
    return decisions


def quality_selection_reason_map(
    conn: Connection,
    *,
    date_from: str,
    date_until: str,
    gate_percentile: float = GATE_PERCENTILE,
    percentile_scope: str = ROUTER_PERCENTILE_SCOPE,
    apply_judge_effective: bool = True,
) -> dict[int, QualityRoutingDecision]:
    return {
        d.content_item_id: d
        for d in explain_quality_routing(
            conn,
            date_from=date_from,
            date_until=date_until,
            gate_percentile=gate_percentile,
            percentile_scope=percentile_scope,
            apply_judge_effective=apply_judge_effective,
        )
    }


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
    max_cost_usd: float | None = None,
) -> BatchStats:
    budget = BudgetCap(max_cost_usd) if max_cost_usd is not None else None
    stats = BatchStats(papers_requested=len(content_item_ids), budget=budget)
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
                by_id = {p["content_item_id"]: p for p in batch}
                for content_id, scores in parsed.items():
                    paper = by_id[content_id]
                    input_hash = paper.get("content_hash") or compute_content_hash(
                        paper.get("title"), paper.get("abstract")
                    )
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
                            "input_content_hash": input_hash,
                        }
                    )
                insert_classification_results(batch_conn, rows)
                if parsed:
                    record_quality_successes(
                        batch_conn,
                        list(parsed.keys()),
                        run_id=run_id,
                        stage_run_id=stage_run_id,
                        model=model,
                        stage_version=STAGE_VERSION,
                        prompt_version=PROMPT_VERSION,
                        policy_version=POLICY_VERSION,
                    )
                missing = sorted(expected - parsed.keys())
                if missing:
                    err = "parse_missing_or_invalid"
                    if problems:
                        err = f"parse_missing_or_invalid: {'; '.join(problems)}"[:2000]
                    record_quality_failures(
                        batch_conn,
                        missing,
                        run_id=run_id,
                        stage_run_id=stage_run_id,
                        model=model,
                        error_summary=err,
                        stage_version=STAGE_VERSION,
                        prompt_version=PROMPT_VERSION,
                        policy_version=POLICY_VERSION,
                        metadata={"problems": problems},
                    )
                batch_conn.commit()
            if problems:
                stats.add_warning("; ".join(problems))
            stats.add_call(
                succeeded=len(parsed),
                failed=len(expected) - len(parsed),
                input_tokens=result["input_tokens"],
                output_tokens=result["output_tokens"],
                cost=result["estimated_cost"],
                estimated_cost=result.get("estimated_cost_usd"),
                actual_cost=result.get("actual_cost_usd"),
            )
        except Exception as exc:  # noqa: BLE001
            err = f"{type(exc).__name__}: {exc}"
            stats.add_error(err, failed=len(expected))
            try:
                with connect() as err_conn:
                    record_quality_failures(
                        err_conn,
                        sorted(expected),
                        run_id=run_id,
                        stage_run_id=stage_run_id,
                        model=model,
                        error_summary=err[:2000],
                        stage_version=STAGE_VERSION,
                        prompt_version=PROMPT_VERSION,
                        policy_version=POLICY_VERSION,
                        metadata={"kind": "batch_exception"},
                    )
                    err_conn.commit()
            except Exception as persist_exc:  # noqa: BLE001
                stats.add_warning(
                    f"quality_attempt_persist_failed: {type(persist_exc).__name__}: {persist_exc}"
                )

    run_batches(batches, handle, label="quality", budget=budget, stats=stats)
    return stats
