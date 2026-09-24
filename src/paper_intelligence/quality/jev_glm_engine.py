"""QUALITY_ENGINE=jev_glm — Jev scores + GLM prose.

Scoring: typesafe/jev-1.13 via System One with policies/systemone/quality_v001.yaml.
Composite: CURRENT quality.stage.WEIGHTS (not G3c refit).
Prose: z-ai/glm-5.3-flash via prompts/quality_prose/v001.md — so_what /
reason_not_higher only. Prose failure keeps scores; prose fields stay NULL.
"""

from __future__ import annotations

import json
import threading
from typing import Any, Sequence

from psycopg import Connection

from paper_intelligence.common.batch_runner import BatchStats, run_batches
from paper_intelligence.common.budget import BudgetCap
from paper_intelligence.common.config import (
    estimate_cost_usd,
    read_prompt,
    QUALITY_PROSE_MODEL,
)
from paper_intelligence.common.llm_stage import (
    call_llm_logged,
    indexed_paper_blocks,
    parse_json_object,
    random_batches,
    strip_json_fences,
)
from paper_intelligence.common.content_hash import compute_content_hash
from paper_intelligence.db import (
    connect,
    fetch_papers,
    insert_classification_results,
)
from paper_intelligence.quality.attempts import (
    record_quality_failures,
    record_quality_successes,
)
from paper_intelligence.quality.stage import (
    RUBRIC_DIMENSIONS,
    STAGE_NAME,
    STAGE_VERSION,
    WEIGHTS,
    composite_score,
)
from paper_intelligence.systemone.client import (
    JEV_MODEL_PINNED,
    SystemOneRequest,
    system_one,
)
from paper_intelligence.systemone.policy import (
    build_questions,
    load_systemone_policy,
    parse_answers,
    state_from_paper,
)

JEV_GLM_ENGINE = "jev_glm"
SCORING_ENGINE = "jev"
SCORING_MODEL = JEV_MODEL_PINNED
PROSE_MODEL = QUALITY_PROSE_MODEL
SYSTEMONE_POLICY_NAME = "quality"
SYSTEMONE_POLICY_VERSION = "v001"
# Distinct from Terra's prompt/policy versions so skip-done / currentness
# do not collide with Terra rows.
JEV_GLM_PROMPT_VERSION = "prose_v001"
JEV_GLM_POLICY_VERSION = "systemone_v001"
PROSE_PROMPT_STAGE = "quality_prose"
PROSE_PROMPT_VERSION = "v001"
PROSE_BATCH_SIZE = 5


def _dims_from_parsed(parsed: dict[str, Any]) -> dict[str, float] | None:
    dims: dict[str, float] = {}
    for d in RUBRIC_DIMENSIONS:
        entry = parsed.get(d)
        if not isinstance(entry, dict) or entry.get("score_0_10") is None:
            return None
        dims[d] = float(entry["score_0_10"])
    return dims


def _mean_confidence(parsed: dict[str, Any]) -> float | None:
    vals = []
    for d in RUBRIC_DIMENSIONS:
        entry = parsed.get(d)
        if isinstance(entry, dict) and entry.get("confidence") is not None:
            try:
                vals.append(float(entry["confidence"]))
            except (TypeError, ValueError):
                pass
    if not vals:
        return None
    # System One confidence is typically 0..1; store as 0..1 like Terra path
    # (Terra stores confidence/10). Keep raw mean if already 0..1.
    mean = sum(vals) / len(vals)
    return mean if mean <= 1.0 else mean / 10.0


def score_paper_with_jev(paper: dict[str, Any]) -> tuple[dict[str, Any] | None, str | None, float]:
    """Return (scores_dict, error, billable_cost). scores include dims only."""
    policy = load_systemone_policy(SYSTEMONE_POLICY_NAME, SYSTEMONE_POLICY_VERSION)
    questions = build_questions(policy)
    resp = system_one(
        SystemOneRequest(
            model=SCORING_MODEL,
            state=state_from_paper(paper),
            questions=questions,
            timeout=90.0,
        )
    )
    cost = float(resp.billable_cost or resp.estimated_cost or 0.0)
    if resp.error:
        return None, resp.error, cost
    parsed = parse_answers(resp.answers, policy)
    dims = _dims_from_parsed(parsed)
    if dims is None:
        return None, "jev_missing_or_invalid_dims", cost
    out = dict(dims)
    out["confidence"] = _mean_confidence(parsed)
    out["scoring_engine"] = SCORING_ENGINE
    out["scoring_model"] = SCORING_MODEL
    out["scoring_policy"] = f"{SYSTEMONE_POLICY_NAME}_{SYSTEMONE_POLICY_VERSION}"
    out["quality_engine"] = JEV_GLM_ENGINE
    return out, None, cost


def build_prose_user_prompt(
    papers: Sequence[dict[str, Any]],
    scores_by_id: dict[int, dict[str, Any]],
) -> tuple[str, dict[int, int]]:
    """Blinded prose prompt: title, abstract, six scores. No authors."""
    index_to_id: dict[int, int] = {}
    parts: list[str] = []
    for i, paper in enumerate(papers, start=1):
        cid = int(paper["content_item_id"])
        index_to_id[i] = cid
        sc = scores_by_id[cid]
        dim_lines = "\n".join(f"  {d}: {sc[d]}" for d in RUBRIC_DIMENSIONS)
        title = " ".join(str(paper.get("title") or "").split())
        abstract = " ".join(str(paper.get("abstract") or "").split())[:3000]
        parts.append(
            f"batch_index: {i}\n"
            f"title: {title}\n"
            f"abstract: {abstract}\n"
            f"scores:\n{dim_lines}\n"
        )
    return "\n---\n".join(parts), index_to_id


def parse_prose_response(
    text: str, index_to_id: dict[int, int]
) -> tuple[dict[int, dict[str, str | None]], list[str]]:
    """Parse prose-only JSON. Never accepts score fields as authoritative."""
    problems: list[str] = []
    try:
        payload = parse_json_object(strip_json_fences(text))
    except (ValueError, json.JSONDecodeError) as exc:
        return {}, [f"prose_json_error: {exc}"]
    papers = payload.get("papers")
    if not isinstance(papers, list):
        return {}, ["prose_missing_papers_array"]
    out: dict[int, dict[str, str | None]] = {}
    seen: set[int] = set()
    for entry in papers:
        if not isinstance(entry, dict):
            problems.append("prose_non_object_entry")
            continue
        try:
            batch_index = int(entry.get("batch_index"))
        except (TypeError, ValueError):
            problems.append("prose_unparseable_batch_index")
            continue
        if batch_index not in index_to_id:
            problems.append(f"prose_unexpected_batch_index {batch_index}")
            continue
        if batch_index in seen:
            problems.append(f"prose_duplicate_batch_index {batch_index}")
            continue
        seen.add(batch_index)
        # Reject if model tried to emit scores
        for d in RUBRIC_DIMENSIONS:
            if d in entry:
                problems.append(f"prose_emitted_score_field:{d}")
        so_what = entry.get("so_what")
        reason = entry.get("reason_not_higher")
        so_what_s = (str(so_what).strip() if so_what is not None else "") or None
        reason_s = (str(reason).strip() if reason is not None else "") or None
        if not so_what_s:
            problems.append(f"batch_index={batch_index}: missing so_what")
        if not reason_s:
            problems.append(f"batch_index={batch_index}: missing reason_not_higher")
        out[index_to_id[batch_index]] = {
            "so_what": so_what_s,
            "reason_not_higher": reason_s,
        }
    missing = sorted(set(index_to_id) - seen)
    if missing:
        problems.append(f"prose_missing_batch_index: {missing}")
    return out, problems


def project_jev_glm_cost(papers: Sequence[dict[str, Any]]) -> BatchStats:
    """Dry-run cost: Jev scoring (per paper) + GLM prose (batched)."""
    stats = BatchStats(papers_requested=len(papers))
    if not papers:
        return stats
    policy = load_systemone_policy(SYSTEMONE_POLICY_NAME, SYSTEMONE_POLICY_VERSION)
    questions = build_questions(policy)
    # Rough Jev input size: state + serialised questions once amortized.
    q_chars = len(json.dumps(questions))
    jev_in = 0
    for p in papers:
        jev_in += (len(state_from_paper(p)) + q_chars) // 4
    jev_calls = len(papers)
    jev_cost = estimate_cost_usd(SCORING_MODEL, jev_in, 0)

    prose_prompt = read_prompt(PROSE_PROMPT_STAGE, PROSE_PROMPT_VERSION)
    prose_batches = -(-len(papers) // PROSE_BATCH_SIZE)
    prose_chars = sum(
        len((p.get("title") or "")) + len((p.get("abstract") or "")[:3000]) + 120
        for p in papers
    )
    prose_in = (prose_chars + len(prose_prompt) * prose_batches) // 4
    prose_out = len(papers) * 120
    prose_cost = estimate_cost_usd(PROSE_MODEL, prose_in, prose_out)

    stats.calls = jev_calls + prose_batches
    stats.input_tokens = jev_in + prose_in
    stats.output_tokens = prose_out
    stats.cost_usd = round(jev_cost + prose_cost, 6)
    # Stash breakdown on warnings for dry-run reporters
    stats.warnings.append(f"jev_scoring_est_usd={jev_cost:.6f}")
    stats.warnings.append(f"glm_prose_est_usd={prose_cost:.6f}")
    return stats


def run_jev_glm_window(
    conn: Connection,
    content_item_ids: Sequence[int],
    *,
    run_id: str,
    stage_run_id: str,
    dry_run: bool = False,
    max_cost_usd: float | None = None,
    prose_batch_size: int = PROSE_BATCH_SIZE,
) -> BatchStats:
    budget = BudgetCap(max_cost_usd) if max_cost_usd is not None else None
    stats = BatchStats(papers_requested=len(content_item_ids), budget=budget)
    if not content_item_ids:
        return stats

    papers = fetch_papers(conn, content_item_ids)
    if dry_run:
        projected = project_jev_glm_cost(papers)
        stats.calls = projected.calls
        stats.input_tokens = projected.input_tokens
        stats.output_tokens = projected.output_tokens
        stats.cost_usd = projected.cost_usd
        stats.warnings.extend(projected.warnings)
        return stats

    prose_system = read_prompt(PROSE_PROMPT_STAGE, PROSE_PROMPT_VERSION)
    # Score concurrently per paper (System One is per-paper); then prose in batches.
    scored: dict[int, dict[str, Any]] = {}
    score_errors: dict[int, str] = {}
    lock = threading.Lock()

    def score_one(paper: dict[str, Any]) -> None:
        if budget is not None and not budget.allow_new_batch():
            with lock:
                stats.papers_skipped_budget += 1
            return
        dims, err, cost = score_paper_with_jev(paper)
        stats.add_call(
            succeeded=1 if dims else 0,
            failed=0 if dims else 1,
            input_tokens=0,
            output_tokens=0,
            cost=cost,
            estimated_cost=cost,
            actual_cost=cost,
        )
        cid = int(paper["content_item_id"])
        with lock:
            if dims is None:
                score_errors[cid] = err or "jev_score_failed"
            else:
                scored[cid] = dims

    # Use run_batches with batch_size=1 for Jev scoring concurrency control
    run_batches(
        [[p] for p in papers],
        handler=lambda batch: score_one(batch[0]),
        stats=stats,
        budget=budget,
        label="jev_score",
    )

    # Persist scoring failures
    if score_errors:
        with connect() as fail_conn:
            record_quality_failures(
                fail_conn,
                sorted(score_errors.keys()),
                run_id=run_id,
                stage_run_id=stage_run_id,
                model=SCORING_MODEL,
                error_summary="jev_scoring_failed",
                stage_version=STAGE_VERSION,
                prompt_version=JEV_GLM_PROMPT_VERSION,
                policy_version=JEV_GLM_POLICY_VERSION,
                metadata={"errors": score_errors},
            )
            fail_conn.commit()

    # Prose for successfully scored papers
    scored_papers = [p for p in papers if int(p["content_item_id"]) in scored]
    prose_by_id: dict[int, dict[str, str | None]] = {}
    prose_problems: list[str] = []

    for batch in random_batches(scored_papers, prose_batch_size):
        if budget is not None and not budget.allow_new_batch():
            stats.papers_skipped_budget += len(batch)
            # Leave prose NULL for remaining — still insert scores below
            break
        try:
            with connect() as batch_conn:
                user_prompt, index_to_id = build_prose_user_prompt(batch, scored)
                result = call_llm_logged(
                    batch_conn,
                    model=PROSE_MODEL,
                    system_prompt=prose_system,
                    user_prompt=user_prompt,
                    prompt_version=PROSE_PROMPT_VERSION,
                    stage_name="quality_prose",
                    reasoning_effort=None,
                    temperature=0.2,
                    max_tokens=1500,
                    run_id=run_id,
                    stage_run_id=stage_run_id,
                    entity=f"quality_prose_{min(index_to_id.values())}",
                    timeout=120.0,
                )
                stats.add_call(
                    succeeded=0,
                    failed=0,
                    input_tokens=int(result.get("input_tokens") or 0),
                    output_tokens=int(result.get("output_tokens") or 0),
                    cost=float(result.get("estimated_cost") or 0.0),
                    estimated_cost=float(
                        result.get("estimated_cost_usd")
                        or result.get("estimated_cost")
                        or 0.0
                    ),
                    actual_cost=result.get("actual_cost_usd"),
                )
                parsed, problems = parse_prose_response(result["content"], index_to_id)
                prose_problems.extend(problems)
                for cid, prose in parsed.items():
                    # Only accept if both fields present; else NULL prose
                    if prose.get("so_what") and prose.get("reason_not_higher"):
                        prose_by_id[cid] = prose
                    else:
                        prose_by_id[cid] = {"so_what": None, "reason_not_higher": None}
                        stats.add_warning(
                            f"prose_incomplete content_item_id={cid}"
                        )
                for cid in (int(p["content_item_id"]) for p in batch):
                    if cid not in prose_by_id:
                        prose_by_id[cid] = {"so_what": None, "reason_not_higher": None}
                batch_conn.commit()
        except Exception as exc:  # noqa: BLE001 — prose must not fail the paper
            stats.add_warning(f"prose_batch_failed: {exc}")
            for p in batch:
                prose_by_id[int(p["content_item_id"])] = {
                    "so_what": None,
                    "reason_not_higher": None,
                }

    if prose_problems:
        for p in prose_problems[:20]:
            stats.add_warning(p)

    # Insert classification rows for scored papers (prose may be NULL)
    rows = []
    by_id = {int(p["content_item_id"]): p for p in papers}
    for cid, dims in scored.items():
        paper = by_id[cid]
        prose = prose_by_id.get(cid) or {"so_what": None, "reason_not_higher": None}
        composite = composite_score(dims)  # CURRENT WEIGHTS
        input_hash = paper.get("content_hash") or compute_content_hash(
            paper.get("title"), paper.get("abstract")
        )
        conf = dims.get("confidence")
        result_json: dict[str, Any] = {
            **{d: dims[d] for d in RUBRIC_DIMENSIONS},
            "so_what": prose.get("so_what"),
            "reason_not_higher": prose.get("reason_not_higher"),
            "confidence": (conf * 10.0) if isinstance(conf, (int, float)) and conf <= 1.0 else conf,
            "composite": composite,
            "quality_engine": JEV_GLM_ENGINE,
            "scoring_engine": SCORING_ENGINE,
            "scoring_model": SCORING_MODEL,
            "prose_model": PROSE_MODEL if prose.get("so_what") else None,
            "prose_prompt_version": PROSE_PROMPT_VERSION,
            "scoring_policy": f"{SYSTEMONE_POLICY_NAME}_{SYSTEMONE_POLICY_VERSION}",
            "prose_failed": prose.get("so_what") is None or prose.get("reason_not_higher") is None,
        }
        rows.append(
            {
                "content_item_id": cid,
                "task_type": "quality",
                "result_json": result_json,
                "method": "llm",
                "provider": "openrouter",
                "model": SCORING_MODEL,
                "prompt_version": JEV_GLM_PROMPT_VERSION,
                "policy_version": JEV_GLM_POLICY_VERSION,
                "stage_version": STAGE_VERSION,
                "confidence": (
                    float(conf)
                    if isinstance(conf, (int, float)) and conf <= 1.0
                    else (float(conf) / 10.0 if conf is not None else None)
                ),
                "run_id": run_id,
                "input_content_hash": input_hash,
            }
        )

    if rows:
        with connect() as write_conn:
            insert_classification_results(write_conn, rows)
            record_quality_successes(
                write_conn,
                [r["content_item_id"] for r in rows],
                run_id=run_id,
                stage_run_id=stage_run_id,
                model=SCORING_MODEL,
                stage_version=STAGE_VERSION,
                prompt_version=JEV_GLM_PROMPT_VERSION,
                policy_version=JEV_GLM_POLICY_VERSION,
            )
            write_conn.commit()

    return stats
