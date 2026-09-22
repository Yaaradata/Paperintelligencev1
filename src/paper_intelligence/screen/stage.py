"""Stage: screen (Pass 1) — PAID, cheap, every paper, reasoning off.

Four numeric dimensions, no prose. The gate lives in code, never in the model:
a paper that fails `ai_relevance` keeps its honest scores and its row.
"""

from __future__ import annotations

from typing import Any, Sequence

from psycopg import Connection

from paper_intelligence.common.batch_runner import BatchStats, run_batches
from paper_intelligence.common.budget import BudgetCap
from paper_intelligence.common.config import (
    SCREEN_BATCH_SIZE,
    SCREEN_MIN_AI_RELEVANCE,
    SCREEN_MODEL,
    read_prompt,
)
from paper_intelligence.common.llm_stage import (
    call_llm_logged,
    paper_block,
    parse_json_object,
    random_batches,
)
from paper_intelligence.common.content_hash import compute_content_hash
from paper_intelligence.db import connect, fetch_papers, insert_classification_results

STAGE_NAME = "screen"
STAGE_VERSION = "v001"
PROMPT_VERSION = "v001"
POLICY_VERSION = "v001"

DIMENSIONS = (
    "ai_relevance",
    "technical_significance",
    "apparent_novelty",
    "evidence_strength",
)

def build_user_prompt(papers: Sequence[dict[str, Any]]) -> str:
    blocks = "\n---\n".join(paper_block(p) for p in papers)
    ids = [p["content_item_id"] for p in papers]
    return (
        f"Score these {len(papers)} papers. Return one object per paper, "
        f"for exactly these content_item_id values: {ids}.\n\n{blocks}"
    )


def _valid_score(value: Any) -> float | None:
    try:
        score = float(value)
    except (TypeError, ValueError):
        return None
    if score < 0.0 or score > 10.0:
        return None
    # Scale is 0.0-10.0 in 0.5 increments; snap tiny float noise, reject the rest.
    doubled = score * 2
    if abs(doubled - round(doubled)) > 1e-6:
        return None
    return round(doubled) / 2


def parse_response(text: str, expected_ids: set[int]) -> tuple[dict[int, dict[str, float]], list[str]]:
    payload = parse_json_object(text)
    problems: list[str] = []
    parsed: dict[int, dict[str, float]] = {}
    for entry in payload.get("papers") or []:
        try:
            content_id = int(entry.get("content_item_id"))
        except (TypeError, ValueError):
            problems.append(f"unparseable content_item_id: {entry!r:.120}")
            continue
        if content_id not in expected_ids:
            problems.append(f"unexpected content_item_id {content_id}")
            continue
        scores: dict[str, float] = {}
        bad = False
        for dimension in DIMENSIONS:
            score = _valid_score(entry.get(dimension))
            if score is None:
                problems.append(f"{content_id}: invalid {dimension}={entry.get(dimension)!r}")
                bad = True
                break
            scores[dimension] = score
        if not bad:
            parsed[content_id] = scores
    missing = expected_ids - parsed.keys()
    if missing:
        problems.append(f"missing ids: {sorted(missing)}")
    return parsed, problems


def gate_decision(scores: dict[str, float], threshold: float) -> bool:
    return scores["ai_relevance"] >= threshold


def run_window(
    conn: Connection,
    content_item_ids: Sequence[int],
    *,
    run_id: str,
    stage_run_id: str,
    threshold: float = SCREEN_MIN_AI_RELEVANCE,
    model: str = SCREEN_MODEL,
    batch_size: int = SCREEN_BATCH_SIZE,
    dry_run: bool = False,
    max_cost_usd: float | None = None,
) -> BatchStats:
    budget = BudgetCap(max_cost_usd) if max_cost_usd is not None else None
    stats = BatchStats(papers_requested=len(content_item_ids), budget=budget)
    if not content_item_ids:
        return stats

    papers = fetch_papers(conn, content_item_ids)
    system_prompt = read_prompt("screen", PROMPT_VERSION)

    if dry_run:
        # Projection only: character count is a reasonable token proxy for a
        # title+abstract payload, and output is four numbers per paper.
        chars = sum(len(paper_block(p)) for p in papers) + len(system_prompt) * (
            max(1, len(papers) // max(1, batch_size))
        )
        stats.calls = -(-len(papers) // max(1, batch_size))
        stats.input_tokens = chars // 4
        stats.output_tokens = len(papers) * 40
        from paper_intelligence.common.config import estimate_cost_usd

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
                    reasoning_effort=None,  # screen never reasons
                    run_id=run_id,
                    stage_run_id=stage_run_id,
                    entity=f"screen_{min(expected)}",
                )
                parsed, problems = parse_response(result["content"], expected)
                rows = []
                for content_id, scores in parsed.items():
                    paper = next(p for p in batch if p["content_item_id"] == content_id)
                    input_hash = paper.get("content_hash") or compute_content_hash(
                        paper.get("title"), paper.get("abstract")
                    )
                    passed = gate_decision(scores, threshold)
                    rows.append(
                        {
                            "content_item_id": content_id,
                            "task_type": "screen",
                            "result_json": {
                                **scores,
                                "gate": {
                                    "dimension": "ai_relevance",
                                    "threshold": threshold,
                                    "passed": passed,
                                },
                            },
                            "method": "llm",
                            "provider": "openrouter",
                            "model": model,
                            "prompt_version": PROMPT_VERSION,
                            "policy_version": POLICY_VERSION,
                            "stage_version": STAGE_VERSION,
                            "confidence": None,
                            "run_id": run_id,
                            "input_content_hash": input_hash,
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
                estimated_cost=result.get("estimated_cost_usd"),
                actual_cost=result.get("actual_cost_usd"),
            )
        except Exception as exc:  # noqa: BLE001 — batch failure must not kill the run
            stats.add_error(f"{type(exc).__name__}: {exc}", failed=len(expected))

    run_batches(batches, handle, label="screen", budget=budget, stats=stats)
    return stats
