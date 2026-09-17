"""Concurrent batch executor shared by the paid LLM stages."""

from __future__ import annotations

import threading
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass, field
from typing import Any, Callable, Sequence

from paper_intelligence.common.config import STAGE_CONCURRENCY


@dataclass
class BatchStats:
    papers_requested: int = 0
    papers_succeeded: int = 0
    papers_failed: int = 0
    calls: int = 0
    input_tokens: int = 0
    output_tokens: int = 0
    cost_usd: float = 0.0
    errors: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    _lock: threading.Lock = field(default_factory=threading.Lock, repr=False)

    def add_call(
        self,
        *,
        succeeded: int,
        failed: int,
        input_tokens: int,
        output_tokens: int,
        cost: float,
    ) -> None:
        with self._lock:
            self.calls += 1
            self.papers_succeeded += succeeded
            self.papers_failed += failed
            self.input_tokens += input_tokens
            self.output_tokens += output_tokens
            self.cost_usd += cost

    def add_error(self, message: str, *, failed: int) -> None:
        with self._lock:
            self.calls += 1
            self.papers_failed += failed
            if len(self.errors) < 20:
                self.errors.append(message[:300])

    def add_warning(self, message: str) -> None:
        """Parse-level problem on an otherwise successful call (e.g. out-of-vocabulary value)."""
        with self._lock:
            self.warnings.append(message[:300])

    def summary_line(self, label: str) -> str:
        avg = (self.cost_usd / self.papers_succeeded) if self.papers_succeeded else 0.0
        return (
            f"{label}: {self.papers_succeeded} papers ok, {self.papers_failed} failed, "
            f"{self.calls} calls, {self.input_tokens} in / {self.output_tokens} out tokens, "
            f"${self.cost_usd:.4f} total (${avg:.6f}/paper)"
        )


def run_batches(
    batches: Sequence[Sequence[Any]],
    handler: Callable[[Sequence[Any]], None],
    *,
    concurrency: int | None = None,
    progress_every: int = 10,
    label: str = "batch",
) -> None:
    """Run `handler` over batches concurrently; handler owns its own error capture."""
    workers = max(1, concurrency or STAGE_CONCURRENCY)
    done = 0
    total = len(batches)
    with ThreadPoolExecutor(max_workers=workers) as pool:
        futures = {pool.submit(handler, batch): index for index, batch in enumerate(batches)}
        for future in as_completed(futures):
            done += 1
            future.result()
            if progress_every and done % progress_every == 0:
                print(f"  {label}: {done}/{total} batches", flush=True)
