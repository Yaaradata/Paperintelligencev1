"""OpenRouter client boundary — only LLM provider allowed.

No vendor SDKs. Calling stages decide prompts, parsing, and policy.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class LLMRequest:
    model: str
    messages: list[dict[str, Any]]
    prompt_version: str | None = None
    temperature: float | None = None
    max_tokens: int | None = None
    extra: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class LLMResponse:
    model: str
    content: str
    input_tokens: int | None = None
    output_tokens: int | None = None
    estimated_cost: float | None = None
    raw_ref: str | None = None
    error: str | None = None


def complete(request: LLMRequest) -> LLMResponse:
    """Execute one OpenRouter completion.

    Returns structured response. Stages validate enums, persist append-only
    rows, and apply gates — this client must not.
    """
    raise NotImplementedError(
        "openrouter.complete is a typed stub; Urmila implements behind this contract"
    )
