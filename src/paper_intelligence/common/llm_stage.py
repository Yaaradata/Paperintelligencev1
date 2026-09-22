"""Shared plumbing for batched LLM stages: batching, JSON parsing, logged calls."""

from __future__ import annotations

import json
import random
from datetime import datetime, timezone
from typing import Any, Sequence

from psycopg import Connection

from paper_intelligence.cache.raw_store import request_hash, write_raw
from paper_intelligence.common.config import estimate_cost_usd
from paper_intelligence.observability.runs import record_external_request
from paper_intelligence.openrouter import (
    LLMRequest,
    OpenRouterError,
    billable_cost_usd,
    complete,
)


MAX_ABSTRACT_CHARS = 2000


def paper_block(paper: dict[str, Any], *, max_abstract_chars: int = MAX_ABSTRACT_CHARS) -> str:
    """Blinded paper payload: title, categories, abstract. No authors or affiliations."""
    categories = paper.get("categories") or []
    if isinstance(categories, str):
        try:
            categories = json.loads(categories)
        except ValueError:
            categories = [categories]
    abstract = (paper.get("abstract") or "")[:max_abstract_chars]
    return (
        f"content_item_id: {paper['content_item_id']}\n"
        f"title: {paper.get('title') or ''}\n"
        f"categories: {', '.join(str(c) for c in categories)}\n"
        f"abstract: {abstract}\n"
    )


def random_batches(items: Sequence[Any], batch_size: int) -> list[list[Any]]:
    """Shuffle then chunk.

    Never group by date, category or prior score — the model would calibrate to
    the batch instead of the absolute scale.
    """
    shuffled = list(items)
    random.shuffle(shuffled)
    size = max(1, batch_size)
    return [shuffled[i : i + size] for i in range(0, len(shuffled), size)]


def strip_json_fences(text: str) -> str:
    body = (text or "").strip()
    if body.startswith("```"):
        lines = body.splitlines()
        if lines and lines[0].startswith("```"):
            lines = lines[1:]
        if lines and lines[-1].strip() == "```":
            lines = lines[:-1]
        body = "\n".join(lines).strip()
    return body


def parse_json_object(text: str) -> dict[str, Any]:
    body = strip_json_fences(text)
    start = body.find("{")
    end = body.rfind("}")
    if start == -1 or end == -1:
        raise ValueError(f"no JSON object in model output: {body[:200]!r}")
    return json.loads(body[start : end + 1])


def call_llm_logged(
    conn: Connection | None,
    *,
    model: str,
    system_prompt: str,
    user_prompt: str,
    prompt_version: str,
    stage_name: str,
    reasoning_effort: str | None = None,
    temperature: float | None = 0.2,
    max_tokens: int | None = None,
    run_id: str | None = None,
    stage_run_id: str | None = None,
    entity: str = "batch",
    timeout: float = 180.0,
) -> dict[str, Any]:
    """One OpenRouter call with raw persistence and external_requests logging.

    Returns content, tokens, estimated_cost_usd (table), actual_cost_usd
    (provider, may be None), and billable ``estimated_cost`` (actual preferred)
    for backward-compatible stage accounting.
    """
    started = datetime.now(timezone.utc)
    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": user_prompt},
    ]
    req_hash = request_hash(
        "openrouter",
        "chat/completions",
        {"model": model, "messages": messages, "reasoning": reasoning_effort},
    )

    try:
        response = complete(
            LLMRequest(
                model=model,
                messages=messages,
                prompt_version=prompt_version,
                temperature=temperature,
                max_tokens=max_tokens,
                reasoning_effort=reasoning_effort,
                timeout=timeout,
            )
        )
    except OpenRouterError as exc:
        if conn is not None:
            record_external_request(
                conn,
                run_id=run_id,
                stage_run_id=stage_run_id,
                content_item_id=None,
                provider="openrouter",
                endpoint=f"chat/completions:{stage_name}",
                request_hash=req_hash,
                started_at=started,
                http_status=getattr(exc, "status", None),
                success=False,
                error_type=type(exc).__name__,
                error_message=str(exc)[:1000],
            )
            conn.commit()
        raise

    raw_path, raw_sha = write_raw("openrouter", req_hash, entity, response.raw or {})
    estimated = response.estimated_cost
    if estimated is None:
        estimated = estimate_cost_usd(model, response.input_tokens, response.output_tokens)
    actual = response.actual_cost
    billable = billable_cost_usd(actual_cost=actual, estimated_cost=estimated)

    if conn is not None:
        record_external_request(
            conn,
            run_id=run_id,
            stage_run_id=stage_run_id,
            content_item_id=None,
            provider="openrouter",
            endpoint=f"chat/completions:{stage_name}",
            request_hash=req_hash,
            started_at=started,
            http_status=200,
            success=True,
            response_path=raw_path,
            response_sha256=raw_sha,
            llm={
                "model": model,
                "prompt_version": prompt_version,
                "input_tokens": response.input_tokens,
                "output_tokens": response.output_tokens,
                "estimated_cost": float(estimated or 0.0),
                "actual_cost": float(actual) if actual is not None else None,
            },
        )
        conn.commit()

    return {
        "content": response.content,
        "input_tokens": response.input_tokens or 0,
        "output_tokens": response.output_tokens or 0,
        "estimated_cost": billable,  # preferred billable for legacy callers
        "estimated_cost_usd": float(estimated or 0.0),
        "actual_cost_usd": float(actual) if actual is not None else None,
        "raw_path": raw_path,
    }
