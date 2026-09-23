"""OpenRouter System One API client (TypeSafe Jev).

Calls ``POST {OPENROUTER_API_BASE}/systemone``. Pin ``typesafe/jev-1.13`` —
never use ``jev-latest`` in a run. Provider ``usage.cost`` is preferred as
actual cost (Phase 2b path); table estimate uses the verified price entry.
"""

from __future__ import annotations

import os
import time
from dataclasses import dataclass, field
from typing import Any

import requests

from paper_intelligence.common.config import OPENROUTER_API_BASE, estimate_cost_usd
from paper_intelligence.openrouter.client import (
    OpenRouterError,
    billable_cost_usd,
    provider_reported_cost_usd,
)

# Pinned OpenRouter model id. Do not substitute jev-latest in pipeline/shadow runs.
JEV_MODEL_PINNED = "typesafe/jev-1.13"
_FORBIDDEN_MODELS = frozenset({"~typesafe/jev-latest", "typesafe/jev-latest", "jev-latest"})


class SystemOneError(OpenRouterError):
    """System One request failed."""


@dataclass
class SystemOneRequest:
    model: str
    state: str
    questions: dict[str, Any]
    timeout: float = 60.0
    max_retries: int = 3
    extra: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class SystemOneResponse:
    model: str
    answers: dict[str, Any]
    input_tokens: int | None = None
    output_tokens: int | None = None
    estimated_cost: float | None = None
    actual_cost: float | None = None
    billable_cost: float | None = None
    provider: str | None = None
    response_id: str | None = None
    raw: dict[str, Any] | None = None
    error: str | None = None


def _api_key() -> str:
    key = os.getenv("OPENROUTER_API_KEY", "").strip()
    if not key:
        raise SystemOneError("OPENROUTER_API_KEY is not configured")
    return key


def assert_pinned_model(model: str) -> str:
    """Reject jev-latest aliases; normalise bare ``jev-1.13`` to the pinned id."""
    mid = (model or "").strip()
    if mid in _FORBIDDEN_MODELS or mid.endswith("/jev-latest") or mid.endswith("jev-latest"):
        raise SystemOneError(
            f"Refusing unpinned System One model {model!r}; use {JEV_MODEL_PINNED!r}"
        )
    if mid in {"jev-1.13", "typesafe/jev-1.13"}:
        return JEV_MODEL_PINNED
    if mid.startswith("typesafe/jev-1.13"):
        # Allow dated response ids like typesafe/jev-1.13-20260917 only as
        # request models when explicitly the 1.13 line — still pin requests.
        return JEV_MODEL_PINNED
    raise SystemOneError(
        f"Unsupported System One model {model!r}; pin {JEV_MODEL_PINNED!r}"
    )


def system_one(request: SystemOneRequest) -> SystemOneResponse:
    """Execute one System One evaluation with retry/backoff on 429 and 5xx."""
    model = assert_pinned_model(request.model)
    url = f"{OPENROUTER_API_BASE.rstrip('/')}/systemone"
    headers = {
        "Authorization": f"Bearer {_api_key()}",
        "Content-Type": "application/json",
    }
    payload: dict[str, Any] = {
        "model": model,
        "state": request.state,
        "questions": request.questions,
    }
    payload.update(request.extra)

    last_error: Exception | None = None
    for attempt in range(1, request.max_retries + 1):
        try:
            response = requests.post(
                url, headers=headers, json=payload, timeout=request.timeout
            )
            if response.status_code == 429 or response.status_code >= 500:
                raise SystemOneError(
                    f"HTTP {response.status_code}: {response.text[:300]}",
                    status=response.status_code,
                    retryable=True,
                )
            if response.status_code >= 400:
                raise SystemOneError(
                    f"HTTP {response.status_code}: {response.text[:500]}",
                    status=response.status_code,
                    retryable=False,
                )
            body = response.json()
            usage = body.get("usage") if isinstance(body, dict) else None
            usage = usage if isinstance(usage, dict) else {}
            inp = usage.get("input_tokens")
            out = usage.get("output_tokens")
            try:
                inp_i = int(inp) if inp is not None else None
            except (TypeError, ValueError):
                inp_i = None
            try:
                out_i = int(out) if out is not None else None
            except (TypeError, ValueError):
                out_i = None
            estimated = estimate_cost_usd(model, inp_i, out_i)
            actual = provider_reported_cost_usd(usage)
            billable = billable_cost_usd(actual_cost=actual, estimated_cost=estimated)
            answers = body.get("answers") if isinstance(body, dict) else None
            if not isinstance(answers, dict):
                raise SystemOneError("System One response missing answers object")
            return SystemOneResponse(
                model=str(body.get("model") or model),
                answers=answers,
                input_tokens=inp_i,
                output_tokens=out_i,
                estimated_cost=float(estimated or 0.0),
                actual_cost=float(actual) if actual is not None else None,
                billable_cost=float(billable),
                provider=(body.get("provider") if isinstance(body, dict) else None),
                response_id=(body.get("id") if isinstance(body, dict) else None),
                raw=body if isinstance(body, dict) else None,
            )
        except SystemOneError as exc:
            last_error = exc
            if not exc.retryable or attempt >= request.max_retries:
                return SystemOneResponse(
                    model=model,
                    answers={},
                    error=str(exc),
                )
            time.sleep(min(20.0, 2 ** (attempt - 1)))
        except requests.RequestException as exc:
            last_error = exc
            if attempt >= request.max_retries:
                return SystemOneResponse(model=model, answers={}, error=str(exc))
            time.sleep(min(20.0, 2 ** (attempt - 1)))

    return SystemOneResponse(
        model=model,
        answers={},
        error=str(last_error) if last_error else "system_one_failed",
    )
