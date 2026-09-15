"""Shared stage contracts for PaperIntelligenceV1."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Literal, Protocol


@dataclass(frozen=True)
class Evidence:
    """One append-only evidence fact. Stages emit these; storage preserves them."""

    evidence_type: str
    evidence_source: str
    evidence_value: str | None = None
    confidence: float | None = None
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class RunContext:
    """Per-run context passed into every stage.process call."""

    run_id: str
    stage_run_id: str
    code_commit_sha: str | None = None
    prompt_version: str | None = None
    policy_version: str | None = None
    dry_run: bool = False
    allow_paid: bool = False
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class StageResult:
    status: Literal["success", "skipped", "failed", "unresolved"]
    data: dict[str, Any] = field(default_factory=dict)
    evidence: list[Evidence] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)


class Stage(Protocol):
    stage_name: str
    stage_version: str

    def process(self, content_item_id: int, run_context: RunContext) -> StageResult:
        """Process one content item. Must be idempotent and independently rerunnable."""
        ...
