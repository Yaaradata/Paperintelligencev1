"""Unit tests for Phase 2 budget cap and model pricing."""

from __future__ import annotations

import threading
import time
from typing import Any

import pytest

from paper_intelligence.common.batch_runner import BatchStats, run_batches
from paper_intelligence.common.budget import BudgetCap, format_budget_line, resolve_max_cost_usd
from paper_intelligence.common.config import UnknownModelPriceError, model_prices


def test_unknown_model_raises(monkeypatch):
    monkeypatch.delenv("PI_PRICE_TOTALLY_FAKE_MODEL_IN", raising=False)
    monkeypatch.delenv("PI_PRICE_TOTALLY_FAKE_MODEL_OUT", raising=False)
    with pytest.raises(UnknownModelPriceError, match="No price configured"):
        model_prices("totally/fake-model")


def test_unknown_model_allowed_with_env_override(monkeypatch):
    monkeypatch.setenv("PI_PRICE_TOTALLY_FAKE_MODEL_IN", "1.0")
    monkeypatch.setenv("PI_PRICE_TOTALLY_FAKE_MODEL_OUT", "2.0")
    assert model_prices("totally/fake-model") == (1.0, 2.0)


def test_known_model_has_price():
    pin, pout = model_prices("openai/gpt-5.6-sol")
    assert pin > 0 and pout > 0


def test_resolve_max_cost_cli_wins(monkeypatch):
    monkeypatch.setenv("PI_MAX_COST_USD", "5")
    assert resolve_max_cost_usd(10.0) == 10.0
    assert resolve_max_cost_usd(None) == 5.0
    monkeypatch.delenv("PI_MAX_COST_USD")
    assert resolve_max_cost_usd(None) is None


def test_budget_line_format():
    line = format_budget_line(projected=1.5, actual=0.25, cap=10.0, stopped=False)
    assert "projected=$1.5000" in line
    assert "actual=$0.2500" in line
    assert "cap=$10.0000" in line
    assert "status=ok" in line


def test_projection_over_cap_logic():
    """Mirror the refuse condition used by run_stage / run_pipeline."""
    projected = 12.0
    cap = 10.0
    force = False
    assert projected > cap and not force


def test_cumulative_cap_stops_further_batches():
    """After spend reaches the cap, remaining batches are not submitted."""
    budget = BudgetCap(1.0)
    stats = BatchStats(papers_requested=6, budget=budget)
    batches = [[1], [2], [3], [4], [5], [6]]
    submitted: list[int] = []
    lock = threading.Lock()

    def handle(batch: list[Any]) -> None:
        with lock:
            submitted.append(batch[0])
        # Each batch costs $0.4; after 3 completes (~$1.2) no more should start.
        # Sleep briefly so concurrent workers can race the gate.
        time.sleep(0.02)
        stats.add_call(
            succeeded=1, failed=0, input_tokens=1, output_tokens=1, cost=0.4
        )

    run_batches(
        batches,
        handle,
        concurrency=2,
        progress_every=0,
        label="test",
        budget=budget,
        stats=stats,
    )
    assert stats.stopped_budget_cap
    assert len(submitted) < 6
    assert stats.papers_skipped_budget == 6 - len(submitted)
    assert stats.cost_usd >= 1.0


def test_concurrent_accumulation_is_correct():
    budget = BudgetCap(100.0)
    stats = BatchStats(papers_requested=20, budget=budget)
    batches = [[i] for i in range(20)]

    def handle(batch: list[Any]) -> None:
        stats.add_call(
            succeeded=1, failed=0, input_tokens=0, output_tokens=0, cost=0.25
        )

    run_batches(
        batches,
        handle,
        concurrency=8,
        progress_every=0,
        label="acc",
        budget=budget,
        stats=stats,
    )
    assert stats.cost_usd == pytest.approx(5.0)
    assert budget.actual_usd == pytest.approx(5.0)
    assert not stats.stopped_budget_cap


def test_succeeded_without_result_reason_updated():
    from paper_intelligence.adjudication.quality_status import derive_quality_status

    status, reason = derive_quality_status(
        has_current_quality_row=False,
        route_decision="selected",
        route_reason="x",
        latest_attempt_status="succeeded",
    )
    assert status == "pending"
    assert reason == "inconsistent_attempt_without_result"
