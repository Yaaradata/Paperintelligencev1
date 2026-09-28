"""Concurrent batch executor shared by the paid LLM stages."""

from __future__ import annotations

import threading
from concurrent.futures import FIRST_COMPLETED, ThreadPoolExecutor, wait
from dataclasses import dataclass, field
from typing import Any, Callable, Sequence

from paper_intelligence.common.budget import BudgetCap
from paper_intelligence.common.config import STAGE_CONCURRENCY
from paper_intelligence.common.runguard import RunGuard


@dataclass
class BatchStats:
    papers_requested: int = 0
    papers_succeeded: int = 0
    papers_failed: int = 0
    calls: int = 0
    input_tokens: int = 0
    output_tokens: int = 0
    cost_usd: float = 0.0  # billable: actual preferred, else table estimate
    estimated_cost_usd: float = 0.0
    actual_cost_usd: float = 0.0
    calls_with_actual_cost: int = 0
    errors: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    stopped_budget_cap: bool = False
    papers_skipped_budget: int = 0
    stopped_runguard: bool = False
    stop_reason: str | None = None
    budget: BudgetCap | None = field(default=None, repr=False)
    _lock: threading.Lock = field(default_factory=threading.Lock, repr=False)

    def add_call(
        self,
        *,
        succeeded: int,
        failed: int,
        input_tokens: int,
        output_tokens: int,
        cost: float,
        estimated_cost: float | None = None,
        actual_cost: float | None = None,
    ) -> None:
        """Record one LLM call.

        ``cost`` is the billable amount (actual if known, else estimate).
        Optional ``estimated_cost`` / ``actual_cost`` feed divergence reporting.
        """
        with self._lock:
            self.calls += 1
            self.papers_succeeded += succeeded
            self.papers_failed += failed
            self.input_tokens += input_tokens
            self.output_tokens += output_tokens
            self.cost_usd += cost
            est = float(estimated_cost) if estimated_cost is not None else float(cost)
            self.estimated_cost_usd += est
            if actual_cost is not None:
                self.actual_cost_usd += float(actual_cost)
                self.calls_with_actual_cost += 1
            if self.budget is not None:
                self.budget.add_actual(cost)

    def cost_divergence_ratio(self) -> float | None:
        """(|actual−estimated| / estimated) when both sides are available."""
        if self.calls_with_actual_cost <= 0 or self.estimated_cost_usd <= 0:
            return None
        # Compare actual total only over the same run's estimated total.
        return abs(self.actual_cost_usd - self.estimated_cost_usd) / self.estimated_cost_usd

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
        base = (
            f"{label}: {self.papers_succeeded} papers ok, {self.papers_failed} failed, "
            f"{self.calls} calls, {self.input_tokens} in / {self.output_tokens} out tokens, "
            f"${self.cost_usd:.4f} total (${avg:.6f}/paper)"
        )
        if self.calls_with_actual_cost:
            base += (
                f", estimated=${self.estimated_cost_usd:.4f} "
                f"actual=${self.actual_cost_usd:.4f}"
            )
        if self.stopped_budget_cap:
            base += f", stopped_budget_cap skipped={self.papers_skipped_budget}"
        return base


def run_batches(
    batches: Sequence[Sequence[Any]],
    handler: Callable[[Sequence[Any]], None],
    *,
    concurrency: int | None = None,
    progress_every: int = 10,
    label: str = "batch",
    budget: BudgetCap | None = None,
    stats: BatchStats | None = None,
    guard: RunGuard | None = None,
) -> None:
    """Run `handler` over batches concurrently; handler owns its own error capture.

    When ``budget`` is set, new batches are only submitted while
    ``budget.allow_new_batch()`` is true. In-flight work may finish after the
    cap is reached. Unsubmitted batches are counted on ``stats`` when provided.

    With ``stats``, a ``RunGuard`` (default: >10% of the last 100 papers
    failed, evaluated from paper 20) is fed the per-paper outcomes after each
    batch. Once tripped, no new batches are submitted and, after in-flight
    batches finish, ``stats.stopped_runguard`` / ``stats.stop_reason`` are set.
    """
    workers = max(1, concurrency or STAGE_CONCURRENCY)
    batch_list = list(batches)
    total = len(batch_list)
    if total == 0:
        return
    if guard is None and stats is not None:
        guard = RunGuard()
    seen_ok = stats.papers_succeeded if stats is not None else 0
    seen_failed = stats.papers_failed if stats is not None else 0

    def _feed_guard() -> None:
        nonlocal seen_ok, seen_failed
        if guard is None or stats is None:
            return
        with stats._lock:
            ok, failed = stats.papers_succeeded, stats.papers_failed
        for _ in range(ok - seen_ok):
            guard.record(True)
        for _ in range(failed - seen_failed):
            guard.record(False)
        seen_ok, seen_failed = ok, failed

    done = 0
    next_i = 0

    with ThreadPoolExecutor(max_workers=workers) as pool:
        futures: set[Any] = set()

        def _try_submit() -> bool:
            nonlocal next_i
            if next_i >= total:
                return False
            if budget is not None and not budget.allow_new_batch():
                return False
            if guard is not None and guard.tripped:
                return False
            batch = batch_list[next_i]
            next_i += 1
            futures.add(pool.submit(handler, batch))
            return True

        for _ in range(workers):
            if not _try_submit():
                break

        while futures:
            completed, futures = wait(futures, return_when=FIRST_COMPLETED)
            for future in completed:
                future.result()
                done += 1
                _feed_guard()
                if progress_every and done % progress_every == 0:
                    print(f"  {label}: {done}/{total} batches", flush=True)
            while len(futures) < workers:
                if not _try_submit():
                    break

        unsubmitted = batch_list[next_i:] if next_i < total else []

    # Always emit a final line — progress_every skips e.g. 1033 when total % 10 != 0.
    submitted = done
    if total:
        if unsubmitted:
            print(
                f"  {label}: {submitted}/{total} batches done "
                f"({len(unsubmitted)} unsubmitted — budget/stop)",
                flush=True,
            )
        else:
            print(f"  {label}: {submitted}/{total} batches complete", flush=True)

    if guard is not None and guard.tripped:
        reason = (
            f"{label}: {guard.reason}; {submitted}/{total} batches done, "
            f"{len(unsubmitted)} not submitted"
        )
        print(f"  STOP {reason}", flush=True)
        if stats is not None:
            stats.stopped_runguard = True
            stats.stop_reason = reason
            stats.errors.append(reason[:300])
        return
    if unsubmitted and stats is not None:
        skipped = sum(len(b) for b in unsubmitted)
        stats.stopped_budget_cap = True
        stats.papers_skipped_budget = skipped
    elif budget is not None and budget.stopped and stats is not None:
        stats.stopped_budget_cap = True
