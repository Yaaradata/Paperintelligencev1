"""QUALITY_ENGINE=jev_glm — Jev scores + GLM prose.

Scoring: typesafe/jev-1.13 via System One with policies/systemone/quality_v001.yaml.
Composite: CURRENT quality.stage.WEIGHTS (not G3c refit).
Prose: z-ai/glm-5.3-flash via prompts/quality_prose/v001.md — so_what /
reason_not_higher only.

Scores are persisted to DB immediately after Jev scoring (prose fields NULL).
Prose is best-effort and merged into those rows afterward; a prose hang/kill
does not lose scores.
"""

from __future__ import annotations

import json
import re
import threading
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from typing import Any, Sequence

from psycopg import Connection

from paper_intelligence.cache.raw_store import request_hash, write_raw
from paper_intelligence.common.batch_runner import BatchStats, run_batches
from paper_intelligence.common.budget import BudgetCap
from paper_intelligence.common.runguard import RunGuard, RunGuardTripped
from paper_intelligence.common.config import (
    estimate_cost_usd,
    read_prompt,
    QUALITY_PROSE_MODEL,
)
from paper_intelligence.common.llm_stage import (
    call_llm_logged,
    parse_json_object,
    strip_json_fences,
)
from paper_intelligence.common.content_hash import compute_content_hash
from paper_intelligence.db import (
    connect,
    fetch_papers,
    insert_classification_results,
)
from paper_intelligence.quality.attempts import (
    insert_quality_attempts,
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
from paper_intelligence.observability.runs import record_external_request
from paper_intelligence.systemone.client import (
    JEV_MODEL_PINNED,
    SystemOneRequest,
    SystemOneResponse,
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
JEV_ENDPOINT = "systemone:quality_jev"
# Distinct from Terra's prompt/policy versions so skip-done / currentness
# do not collide with Terra rows.
JEV_GLM_PROMPT_VERSION = "prose_v001"
JEV_GLM_POLICY_VERSION = "systemone_v001"
PROSE_PROMPT_STAGE = "quality_prose"
PROSE_PROMPT_VERSION = "v001"
# One paper per prose call: a failed call loses one paper, not a batch.
# max_tokens counts GLM reasoning tokens as well as the answer (two-sentence
# so_what + one-sentence reason_not_higher, ~150-250 tokens).
PROSE_MAX_TOKENS = 800
PROSE_MAX_ATTEMPTS = 2  # first call + one retry of the same paper
PROSE_CONCURRENCY = 8
PROSE_RAW_OUTPUT_CHARS = 500
# Prose failures are recorded in quality_attempts under this stage_version so
# adjudication (which filters on the quality stage_version) never sees them.
PROSE_ATTEMPT_STAGE_VERSION = f"{PROSE_PROMPT_STAGE}_{PROSE_PROMPT_VERSION}"
# No JSON schema: the account's allowed providers for GLM flash do not support
# structured outputs, so JSON is requested loosely and validated in code
# (parse_prose_response) with one retry per paper.
PROSE_RESPONSE_FORMAT = {"type": "json_object"}
# GLM reasoning cannot be disabled on the Z.AI endpoint (HTTP 400, 2026-09-25);
# at default effort it used median ~510 tokens and sometimes the whole
# max_tokens budget, leaving empty output. Low effort keeps room for the answer.
PROSE_EXTRA_BODY = {"reasoning": {"effort": "low"}}


def _confidence_fields(conf: Any) -> tuple[Any, float | None]:
    """Return (result_json confidence 0-10 scale, row confidence 0-1)."""
    if not isinstance(conf, (int, float)):
        return None, None
    if conf <= 1.0:
        return conf * 10.0, float(conf)
    return conf, float(conf) / 10.0


def build_quality_row(
    *,
    paper: dict[str, Any],
    dims: dict[str, Any],
    prose: dict[str, str | None] | None,
    run_id: str,
) -> dict[str, Any]:
    """One paper_classification_results row for jev_glm (scores required; prose optional)."""
    prose = prose or {"so_what": None, "reason_not_higher": None}
    has_prose = bool(prose.get("so_what") and prose.get("reason_not_higher"))
    conf = dims.get("confidence")
    conf_json, conf_row = _confidence_fields(conf)
    input_hash = paper.get("content_hash") or compute_content_hash(
        paper.get("title"), paper.get("abstract")
    )
    result_json: dict[str, Any] = {
        **{d: dims[d] for d in RUBRIC_DIMENSIONS},
        "so_what": prose.get("so_what"),
        "reason_not_higher": prose.get("reason_not_higher"),
        "confidence": conf_json,
        "composite": composite_score(dims),  # CURRENT WEIGHTS
        "quality_engine": JEV_GLM_ENGINE,
        "scoring_engine": SCORING_ENGINE,
        "scoring_model": SCORING_MODEL,
        "prose_model": PROSE_MODEL if has_prose else None,
        "prose_prompt_version": PROSE_PROMPT_VERSION,
        "scoring_policy": f"{SYSTEMONE_POLICY_NAME}_{SYSTEMONE_POLICY_VERSION}",
        "prose_failed": not has_prose,
        "scores_persisted_before_prose": True,
    }
    return {
        "content_item_id": int(paper["content_item_id"]),
        "task_type": "quality",
        "result_json": result_json,
        "method": "llm",
        "provider": "openrouter",
        "model": SCORING_MODEL,
        "prompt_version": JEV_GLM_PROMPT_VERSION,
        "policy_version": JEV_GLM_POLICY_VERSION,
        "stage_version": STAGE_VERSION,
        "confidence": conf_row,
        "run_id": run_id,
        "input_content_hash": input_hash,
    }


def persist_jev_scores(
    *,
    papers: Sequence[dict[str, Any]],
    scored: dict[int, dict[str, Any]],
    run_id: str,
    stage_run_id: str | None,
) -> int:
    """Write Jev scores to DB immediately — before GLM prose.

    Prose fields are NULL / prose_failed=true. Later ``merge_prose_into_scores``
    patches the same run's rows when prose succeeds.
    """
    by_id = {int(p["content_item_id"]): p for p in papers}
    rows = [
        build_quality_row(
            paper=by_id[cid],
            dims=dims,
            prose=None,
            run_id=run_id,
        )
        for cid, dims in scored.items()
        if cid in by_id
    ]
    if not rows:
        return 0
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
    return len(rows)


def merge_prose_into_scores(
    *,
    run_id: str | None = None,
    prose_by_id: dict[int, dict[str, str | None]],
    score_run_ids: dict[int, str] | None = None,
) -> int:
    """Patch prose fields onto score rows already stored.

    Each paper's row is located by its scoring run: ``score_run_ids[cid]`` when
    given (prose backfill), else ``run_id``.
    """
    updated = 0
    with connect() as conn:
        with conn.cursor() as cur:
            for cid, prose in prose_by_id.items():
                target_run = (score_run_ids or {}).get(cid) or run_id
                if not target_run:
                    continue
                has_prose = bool(prose.get("so_what") and prose.get("reason_not_higher"))
                if not has_prose:
                    continue
                patch = {
                    "so_what": prose.get("so_what"),
                    "reason_not_higher": prose.get("reason_not_higher"),
                    "prose_model": PROSE_MODEL,
                    "prose_prompt_version": PROSE_PROMPT_VERSION,
                    "prose_failed": False,
                }
                cur.execute(
                    """
                    UPDATE paper_intelligence.paper_classification_results
                    SET result_json = result_json || %s::jsonb
                    WHERE id = (
                        SELECT id
                        FROM paper_intelligence.paper_classification_results
                        WHERE content_item_id = %s
                          AND run_id = %s
                          AND task_type = 'quality'
                          AND model = %s
                          AND prompt_version = %s
                        ORDER BY created_at DESC
                        LIMIT 1
                    )
                    """,
                    (
                        json.dumps(patch, default=str),
                        cid,
                        target_run,
                        SCORING_MODEL,
                        JEV_GLM_PROMPT_VERSION,
                    ),
                )
                updated += cur.rowcount
        conn.commit()
    return updated


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


def log_jev_request(
    *,
    paper: dict[str, Any],
    resp: SystemOneResponse,
    req_hash: str,
    started_at: datetime,
    run_id: str | None,
    stage_run_id: str | None,
) -> str:
    """external_requests + llm_requests row for one System One call.

    actual_cost is provider ``usage.cost`` so DB run-cost totals include Jev.
    """
    cid = int(paper["content_item_id"])
    raw_path = raw_sha = None
    if resp.raw:
        raw_path, raw_sha = write_raw("openrouter", req_hash, f"quality_jev_{cid}", resp.raw)
    with connect() as conn:
        request_id = record_external_request(
            conn,
            run_id=run_id,
            stage_run_id=stage_run_id,
            content_item_id=cid,
            provider="openrouter",
            endpoint=JEV_ENDPOINT,
            request_hash=req_hash,
            started_at=started_at,
            http_status=None if resp.error else 200,
            success=resp.error is None,
            response_path=raw_path,
            response_sha256=raw_sha,
            error_type="SystemOneError" if resp.error else None,
            error_message=(resp.error or "")[:1000] or None,
            llm={
                "model": SCORING_MODEL,
                "prompt_version": JEV_GLM_POLICY_VERSION,
                "input_tokens": resp.input_tokens,
                "output_tokens": resp.output_tokens,
                "estimated_cost": float(resp.estimated_cost or 0.0),
                "actual_cost": resp.actual_cost,
            },
        )
        conn.commit()
    return request_id


def score_paper_with_jev(
    paper: dict[str, Any],
    *,
    run_id: str | None = None,
    stage_run_id: str | None = None,
    stats: BatchStats | None = None,
) -> tuple[dict[str, Any] | None, str | None, float]:
    """Return (scores_dict, error, billable_cost). scores include dims only."""
    policy = load_systemone_policy(SYSTEMONE_POLICY_NAME, SYSTEMONE_POLICY_VERSION)
    questions = build_questions(policy)
    state = state_from_paper(paper)
    req_hash = request_hash(
        "openrouter",
        JEV_ENDPOINT,
        {"model": SCORING_MODEL, "state": state, "questions": questions},
    )
    started = datetime.now(timezone.utc)
    resp = system_one(
        SystemOneRequest(
            model=SCORING_MODEL,
            state=state,
            questions=questions,
            timeout=90.0,
        )
    )
    try:
        log_jev_request(
            paper=paper,
            resp=resp,
            req_hash=req_hash,
            started_at=started,
            run_id=run_id,
            stage_run_id=stage_run_id,
        )
    except Exception as exc:  # noqa: BLE001
        msg = (
            f"jev_cost_log_failed content_item_id={paper.get('content_item_id')} "
            f"cost={resp.billable_cost} error={exc}"
        )
        print(f"  WARN {msg[:300]}", flush=True)
        if stats is not None:
            stats.add_warning(msg[:300])
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
        payload = _loads_prose_payload(text)
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


def _loads_prose_payload(text: str) -> dict[str, Any]:
    """Parse prose JSON; recover complete paper objects from truncated output."""
    body = strip_json_fences(text or "")
    if not body.strip():
        raise ValueError("no JSON object in model output: ''")
    try:
        return parse_json_object(body)
    except (ValueError, json.JSONDecodeError):
        recovered = _recover_papers_from_truncated(body)
        if recovered:
            return {"papers": recovered}
        raise


def _recover_papers_from_truncated(body: str) -> list[dict[str, Any]]:
    """Extract complete paper objects when the model truncates the JSON array."""
    papers: list[dict[str, Any]] = []
    # Match objects that look like a finished prose entry (both required fields).
    pattern = re.compile(
        r'\{\s*"batch_index"\s*:\s*(\d+)\s*,\s*'
        r'"so_what"\s*:\s*("(?:\\.|[^"\\])*")\s*,\s*'
        r'"reason_not_higher"\s*:\s*("(?:\\.|[^"\\])*")\s*'
        r'\}',
        re.DOTALL,
    )
    # Also allow field order so_what / reason swapped
    pattern_alt = re.compile(
        r'\{\s*"batch_index"\s*:\s*(\d+)\s*,\s*'
        r'"reason_not_higher"\s*:\s*("(?:\\.|[^"\\])*")\s*,\s*'
        r'"so_what"\s*:\s*("(?:\\.|[^"\\])*")\s*'
        r'\}',
        re.DOTALL,
    )
    for match in pattern.finditer(body):
        try:
            papers.append(
                {
                    "batch_index": int(match.group(1)),
                    "so_what": json.loads(match.group(2)),
                    "reason_not_higher": json.loads(match.group(3)),
                }
            )
        except (TypeError, ValueError, json.JSONDecodeError):
            continue
    if not papers:
        for match in pattern_alt.finditer(body):
            try:
                papers.append(
                    {
                        "batch_index": int(match.group(1)),
                        "reason_not_higher": json.loads(match.group(2)),
                        "so_what": json.loads(match.group(3)),
                    }
                )
            except (TypeError, ValueError, json.JSONDecodeError):
                continue
    return papers


def _call_prose_llm(
    conn: Connection,
    *,
    paper: dict[str, Any],
    scored: dict[int, dict[str, Any]],
    prose_system: str,
    run_id: str,
    stage_run_id: str,
    stats: BatchStats,
) -> tuple[dict[str, str | None] | None, list[str], str]:
    """One prose call for one paper. Raises on transport errors.

    Returns (prose cell or None, problems, raw model output).
    """
    cid = int(paper["content_item_id"])
    user_prompt, index_to_id = build_prose_user_prompt([paper], scored)
    result = call_llm_logged(
        conn,
        model=PROSE_MODEL,
        system_prompt=prose_system,
        user_prompt=user_prompt,
        prompt_version=PROSE_PROMPT_VERSION,
        stage_name="quality_prose",
        reasoning_effort=None,
        temperature=0.1,
        max_tokens=PROSE_MAX_TOKENS,
        response_format=PROSE_RESPONSE_FORMAT,
        extra_body=PROSE_EXTRA_BODY,
        run_id=run_id,
        stage_run_id=stage_run_id,
        entity=f"quality_prose_{cid}",
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
    content = result.get("content") or ""
    parsed, problems = parse_prose_response(content, index_to_id)
    if result.get("finish_reason") == "length":
        problems.append(f"finish_reason=length max_tokens={PROSE_MAX_TOKENS}")
    cell = parsed.get(cid)
    if cell and cell.get("so_what") and cell.get("reason_not_higher"):
        return cell, problems, content
    return None, problems, content


class ProseConfigError(RuntimeError):
    """Request rejected before any model ran (routing/auth/params). Retrying cannot help."""


# 4xx other than 429 means the request itself is unroutable or unauthorised.
_CONFIG_ERROR_STATUSES = {400, 401, 402, 403, 404}


def run_prose_for_paper(
    *,
    paper: dict[str, Any],
    scored: dict[int, dict[str, Any]],
    prose_system: str,
    run_id: str,
    stage_run_id: str,
    stats: BatchStats,
) -> tuple[dict[str, str | None] | None, dict[str, Any] | None]:
    """Prose for one paper: one call, one retry on failure.

    Returns (prose cell, None) on success or (None, failure record) where the
    failure record carries the paper id, last error and raw output (truncated).
    """
    cid = int(paper["content_item_id"])
    last_error = "unknown"
    last_raw = ""
    for attempt in range(1, PROSE_MAX_ATTEMPTS + 1):
        try:
            with connect() as conn:
                cell, problems, raw = _call_prose_llm(
                    conn,
                    paper=paper,
                    scored=scored,
                    prose_system=prose_system,
                    run_id=run_id,
                    stage_run_id=stage_run_id,
                    stats=stats,
                )
                conn.commit()
        except Exception as exc:  # noqa: BLE001
            if getattr(exc, "status", None) in _CONFIG_ERROR_STATUSES:
                raise ProseConfigError(str(exc)) from exc
            cell, problems, raw = None, [f"prose_call_failed: {exc}"], ""
        if cell is not None:
            return cell, None
        last_error = "; ".join(problems) or "prose_incomplete"
        last_raw = raw
        stats.add_warning(
            f"prose_failed content_item_id={cid} attempt={attempt}/{PROSE_MAX_ATTEMPTS} "
            f"error={last_error[:200]}"
        )
    return None, {
        "content_item_id": cid,
        "error": last_error[:2000],
        "raw_output": (last_raw or "")[:PROSE_RAW_OUTPUT_CHARS],
        "attempts": PROSE_MAX_ATTEMPTS,
    }


def record_prose_attempts(
    *,
    succeeded_ids: Sequence[int],
    failures: Sequence[dict[str, Any]],
    run_id: str,
    stage_run_id: str | None,
    score_run_ids: dict[int, str] | None = None,
) -> int:
    """Durable per-paper prose outcome in quality_attempts (not a WARN line).

    Uses PROSE_ATTEMPT_STAGE_VERSION so adjudication's quality-attempt lookup
    ignores these rows.
    """
    common = {
        "run_id": run_id,
        "stage_run_id": stage_run_id,
        "stage_version": PROSE_ATTEMPT_STAGE_VERSION,
        "prompt_version": PROSE_PROMPT_VERSION,
        "policy_version": JEV_GLM_POLICY_VERSION,
        "model": PROSE_MODEL,
    }
    runs = score_run_ids or {}
    rows = [
        {
            **common,
            "content_item_id": cid,
            "status": "succeeded",
            "metadata": {"score_run_id": runs.get(cid, run_id)},
        }
        for cid in succeeded_ids
    ] + [
        {
            **common,
            "content_item_id": f["content_item_id"],
            "status": "failed",
            "error_summary": f"prose_failed: {f['error']}"[:2000],
            "metadata": {
                "score_run_id": runs.get(f["content_item_id"], run_id),
                "raw_output": f["raw_output"],
                "attempts": f["attempts"],
            },
        }
        for f in failures
    ]
    if not rows:
        return 0
    with connect() as conn:
        n = insert_quality_attempts(conn, rows)
        conn.commit()
    return n


def run_prose_for_papers(
    *,
    papers: Sequence[dict[str, Any]],
    scored: dict[int, dict[str, Any]],
    run_id: str,
    stage_run_id: str,
    stats: BatchStats,
    budget: BudgetCap | None,
    score_run_ids: dict[int, str] | None = None,
    concurrency: int = PROSE_CONCURRENCY,
    guard: RunGuard | None = None,
) -> tuple[dict[int, dict[str, str | None]], list[dict[str, Any]]]:
    """Per-paper prose for ``papers``; merges successes and records every outcome.

    Returns (prose_by_id for successes, failure records).
    """
    prose_system = read_prompt(PROSE_PROMPT_STAGE, PROSE_PROMPT_VERSION)
    prose_by_id: dict[int, dict[str, str | None]] = {}
    failures: list[dict[str, Any]] = []
    lock = threading.Lock()
    done = [0]
    total = len(papers)
    print(f"  glm_prose: starting papers={total} (1 paper/call, concurrency={concurrency})", flush=True)

    abort = threading.Event()
    config_error: list[str] = []

    def one(paper: dict[str, Any]) -> None:
        cid = int(paper["content_item_id"])
        if abort.is_set():
            return
        if budget is not None and not budget.allow_new_batch():
            with lock:
                stats.papers_skipped_budget += 1
            return
        try:
            cell, failure = run_prose_for_paper(
                paper=paper,
                scored=scored,
                prose_system=prose_system,
                run_id=run_id,
                stage_run_id=stage_run_id,
                stats=stats,
            )
        except ProseConfigError as exc:
            with lock:
                failures.append(
                    {
                        "content_item_id": cid,
                        "error": f"prose_config_error: {exc}"[:2000],
                        "raw_output": "",
                        "attempts": 1,
                    }
                )
                if not config_error:
                    config_error.append(f"content_item_id={cid}: {exc}")
            abort.set()
            return
        with lock:
            if cell is not None:
                prose_by_id[cid] = cell
            elif failure is not None:
                failures.append(failure)
            done[0] += 1
            if guard is not None and guard.record(cell is not None) and not abort.is_set():
                print(f"  {guard.reason} — stopping new prose calls", flush=True)
                abort.set()
            if done[0] % 50 == 0 or done[0] == total:
                print(
                    f"  glm_prose: {done[0]}/{total} ok={len(prose_by_id)} "
                    f"failed={len(failures)} cost=${stats.cost_usd:.4f}",
                    flush=True,
                )

    pool = ThreadPoolExecutor(max_workers=max(1, concurrency))
    try:
        list(pool.map(one, papers))
    except BaseException:
        abort.set()
        raise
    finally:
        # Persist whatever finished, even on Ctrl-C or a config abort.
        pool.shutdown(wait=True, cancel_futures=True)
        n_merged = merge_prose_into_scores(
            run_id=run_id, prose_by_id=prose_by_id, score_run_ids=score_run_ids
        )
        record_prose_attempts(
            succeeded_ids=sorted(prose_by_id),
            failures=failures,
            run_id=run_id,
            stage_run_id=stage_run_id,
            score_run_ids=score_run_ids,
        )
    if guard is not None and guard.tripped:
        raise RunGuardTripped(
            f"{guard.reason}; processed {done[0]}/{total}, ok={len(prose_by_id)} "
            f"failed={len(failures)}"
        )
    if config_error:
        raise ProseConfigError(
            f"prose aborted after {done[0]} papers — request rejected before any model ran: "
            f"{config_error[0][:600]}"
        )
    print(
        f"  glm_prose: finished ok={len(prose_by_id)} failed={len(failures)} "
        f"skipped_budget={stats.papers_skipped_budget} merged={n_merged}",
        flush=True,
    )
    for f in failures:
        print(f"  prose_failed content_item_id={f['content_item_id']} error={f['error'][:160]}", flush=True)
    return prose_by_id, failures


# Output per prose call includes GLM reasoning. 20-paper test 2026-09-25 (all
# served by Z.AI): median 681 completion tokens on successful calls, of which
# ~510 reasoning.
PROSE_EXPECTED_OUT_TOKENS = 700


def project_prose_cost(
    papers: Sequence[dict[str, Any]],
    *,
    out_tokens_per_call: int = PROSE_EXPECTED_OUT_TOKENS,
    calls_per_paper: float = 1.0,
) -> tuple[int, int, int, float]:
    """(calls, input_tokens, output_tokens, usd) for per-paper prose at table price."""
    prose_prompt = read_prompt(PROSE_PROMPT_STAGE, PROSE_PROMPT_VERSION)
    per_call_in = [
        (len(prose_prompt) + len(p.get("title") or "") + len((p.get("abstract") or "")[:3000]) + 400) // 4
        for p in papers
    ]
    calls = int(round(len(papers) * calls_per_paper))
    tin = int(sum(per_call_in) * calls_per_paper)
    tout = int(calls * out_tokens_per_call)
    return calls, tin, tout, estimate_cost_usd(PROSE_MODEL, tin, tout)


def project_jev_glm_cost(papers: Sequence[dict[str, Any]]) -> BatchStats:
    """Dry-run cost: Jev scoring (per paper) + GLM prose (per paper)."""
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

    prose_calls, prose_in, prose_out, prose_cost = project_prose_cost(papers)

    stats.calls = jev_calls + prose_calls
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

    # Score concurrently per paper (System One is per-paper); then prose per paper.
    scored: dict[int, dict[str, Any]] = {}
    score_errors: dict[int, str] = {}
    lock = threading.Lock()

    def score_one(paper: dict[str, Any]) -> None:
        if budget is not None and not budget.allow_new_batch():
            with lock:
                stats.papers_skipped_budget += 1
            return
        dims, err, cost = score_paper_with_jev(
            paper, run_id=run_id, stage_run_id=stage_run_id, stats=stats
        )
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
    print(
        f"  jev_score: starting n={len(papers)} (1 paper/call)",
        flush=True,
    )
    run_batches(
        [[p] for p in papers],
        handler=lambda batch: score_one(batch[0]),
        stats=stats,
        budget=budget,
        label="jev_score",
    )
    print(
        f"  jev_score: finished ok={len(scored)} failed={len(score_errors)} "
        f"skipped_budget={stats.papers_skipped_budget}",
        flush=True,
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

    # Persist Jev scores NOW — before prose — so a prose hang/kill keeps scores.
    print(
        f"  jev_glm: persisting scores before prose n={len(scored)}",
        flush=True,
    )
    n_persisted = persist_jev_scores(
        papers=papers,
        scored=scored,
        run_id=run_id,
        stage_run_id=stage_run_id,
    )
    print(f"  jev_glm: scores persisted rows={n_persisted}", flush=True)
    if stats.stopped_runguard:
        return stats

    # Prose for successfully scored papers (best-effort; scores already durable)
    scored_papers = [p for p in papers if int(p["content_item_id"]) in scored]
    try:
        run_prose_for_papers(
            papers=scored_papers,
            scored=scored,
            run_id=run_id,
            stage_run_id=stage_run_id,
            stats=stats,
            budget=budget,
            guard=RunGuard(),
        )
    except (RunGuardTripped, ProseConfigError) as exc:
        reason = f"glm_prose: {exc}"
        print(f"  STOP {reason}", flush=True)
        stats.stopped_runguard = True
        stats.stop_reason = reason
        stats.errors.append(reason[:300])
    return stats
