"""OpenRouter client boundary — only LLM provider allowed.

Returns structured responses. Prompt construction, vocabulary validation,
gating and persistence belong to the calling stage, never here.
"""

from __future__ import annotations

import os
import time
from dataclasses import dataclass, field
from typing import Any

import requests

from paper_intelligence.common.config import OPENROUTER_API_BASE, estimate_cost_usd


class OpenRouterError(RuntimeError):
    def __init__(self, message: str, *, status: int | None = None, retryable: bool = False):
        super().__init__(message)
        self.status = status
        self.retryable = retryable


@dataclass
class LLMRequest:
    model: str
    messages: list[dict[str, Any]]
    prompt_version: str | None = None
    temperature: float | None = 0.2
    max_tokens: int | None = None
    reasoning_effort: str | None = None
    response_format: dict[str, Any] | None = None
    timeout: float = 180.0
    max_retries: int = 3
    extra: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class LLMResponse:
    model: str
    content: str
    input_tokens: int | None = None
    output_tokens: int | None = None
    estimated_cost: float | None = None
    actual_cost: float | None = None
    raw: dict[str, Any] | None = None
    raw_ref: str | None = None
    error: str | None = None


def _api_key() -> str:
    key = os.getenv("OPENROUTER_API_KEY", "").strip()
    if not key:
        raise OpenRouterError("OPENROUTER_API_KEY is not configured")
    return key


def provider_reported_cost_usd(usage: dict[str, Any] | None) -> float | None:
    """Extract OpenRouter ``usage.cost`` (USD credits) when present."""
    if not usage:
        return None
    raw = usage.get("cost")
    if raw is None:
        return None
    try:
        return float(raw)
    except (TypeError, ValueError):
        return None


def billable_cost_usd(
    *,
    actual_cost: float | None,
    estimated_cost: float | None,
) -> float:
    """Prefer provider-reported cost; fall back to table estimate."""
    if actual_cost is not None:
        return float(actual_cost)
    return float(estimated_cost or 0.0)


def _body(request: LLMRequest) -> dict[str, Any]:
    body: dict[str, Any] = {"model": request.model, "messages": request.messages}
    if request.temperature is not None:
        body["temperature"] = request.temperature
    if request.max_tokens is not None:
        body["max_tokens"] = request.max_tokens
    if request.reasoning_effort:
        body["reasoning"] = {"effort": request.reasoning_effort}
    if request.response_format is not None:
        body["response_format"] = request.response_format
    # OpenRouter now returns usage.cost by default; ``usage.include`` is a
    # no-op/deprecated but harmless if an older gateway still keys on it.
    body.setdefault("usage", {"include": True})
    body.update(request.extra)
    return body


def complete(request: LLMRequest) -> LLMResponse:
    """Execute one OpenRouter completion with retry/backoff on 429 and 5xx."""
    url = f"{OPENROUTER_API_BASE.rstrip('/')}/chat/completions"
    headers = {
        "Authorization": f"Bearer {_api_key()}",
        "Content-Type": "application/json",
    }
    payload = _body(request)

    last_error: Exception | None = None
    for attempt in range(1, request.max_retries + 1):
        try:
            response = requests.post(
                url, headers=headers, json=payload, timeout=request.timeout
            )
            if response.status_code == 429 or response.status_code >= 500:
                raise OpenRouterError(
                    f"HTTP {response.status_code}: {response.text[:300]}",
                    status=response.status_code,
                    retryable=True,
                )
            if response.status_code >= 400:
                raise OpenRouterError(
                    f"HTTP {response.status_code}: {response.text[:300]}",
                    status=response.status_code,
                )
            data = response.json()
            choices = data.get("choices") or []
            content = ""
            if choices:
                content = (choices[0].get("message", {}).get("content") or "").strip()
            usage = data.get("usage") or {}
            input_tokens = usage.get("prompt_tokens") or usage.get("input_tokens")
            output_tokens = usage.get("completion_tokens") or usage.get("output_tokens")
            estimated = estimate_cost_usd(request.model, input_tokens, output_tokens)
            actual = provider_reported_cost_usd(usage)
            return LLMResponse(
                model=request.model,
                content=content,
                input_tokens=input_tokens,
                output_tokens=output_tokens,
                estimated_cost=estimated,
                actual_cost=actual,
                raw=data,
            )
        except Exception as exc:  # noqa: BLE001 — client boundary normalises errors
            last_error = exc
            retryable = getattr(exc, "retryable", False) or isinstance(
                exc, (requests.Timeout, requests.ConnectionError)
            )
            if retryable and attempt < request.max_retries:
                time.sleep(min(30.0, 2 ** (attempt - 1)))
                continue
            break

    raise OpenRouterError(str(last_error or "OpenRouter call failed"))
