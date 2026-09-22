"""Phase 2b: provider-reported cost vs table estimate."""

from __future__ import annotations

import pytest

from paper_intelligence.common.batch_runner import BatchStats
from paper_intelligence.common.budget import cost_divergence_warning
from paper_intelligence.common.config import model_prices
from paper_intelligence.openrouter.client import (
    billable_cost_usd,
    provider_reported_cost_usd,
)


def test_updated_list_prices():
    assert model_prices("z-ai/glm-4.6") == (0.43, 1.75)
    assert model_prices("openai/gpt-5.6-sol") == (5.00, 30.00)
    assert model_prices("z-ai/glm-5.3-flash") == (0.15, 0.50)


def test_provider_cost_extracted():
    assert provider_reported_cost_usd({"cost": 0.0123}) == pytest.approx(0.0123)
    assert provider_reported_cost_usd({"prompt_tokens": 10}) is None
    assert provider_reported_cost_usd(None) is None


def test_billable_prefers_provider_actual():
    assert billable_cost_usd(actual_cost=0.5, estimated_cost=0.1) == 0.5
    assert billable_cost_usd(actual_cost=None, estimated_cost=0.1) == pytest.approx(0.1)
    assert billable_cost_usd(actual_cost=None, estimated_cost=None) == 0.0


def test_batch_stats_budget_uses_billable_cost():
    from paper_intelligence.common.budget import BudgetCap

    budget = BudgetCap(1.0)
    stats = BatchStats(budget=budget)
    # Table says 0.2 but provider says 0.6 — budget must use 0.6.
    stats.add_call(
        succeeded=1,
        failed=0,
        input_tokens=10,
        output_tokens=10,
        cost=0.6,
        estimated_cost=0.2,
        actual_cost=0.6,
    )
    assert stats.cost_usd == pytest.approx(0.6)
    assert stats.estimated_cost_usd == pytest.approx(0.2)
    assert stats.actual_cost_usd == pytest.approx(0.6)
    assert budget.actual_usd == pytest.approx(0.6)
    assert budget.allow_new_batch()  # 0.6 < 1.0
    stats.add_call(
        succeeded=1,
        failed=0,
        input_tokens=1,
        output_tokens=1,
        cost=0.5,
        estimated_cost=0.1,
        actual_cost=0.5,
    )
    assert budget.actual_usd == pytest.approx(1.1)
    assert not budget.allow_new_batch()


def test_fallback_when_actual_absent():
    stats = BatchStats()
    stats.add_call(
        succeeded=1,
        failed=0,
        input_tokens=1,
        output_tokens=1,
        cost=0.25,
        estimated_cost=0.25,
        actual_cost=None,
    )
    assert stats.calls_with_actual_cost == 0
    assert stats.cost_usd == pytest.approx(0.25)
    assert stats.cost_divergence_ratio() is None


def test_divergence_warning_over_20_percent():
    warn = cost_divergence_warning(estimated_usd=1.0, actual_usd=1.5)
    assert warn is not None
    assert "1.5000" in warn
    assert cost_divergence_warning(estimated_usd=1.0, actual_usd=1.1) is None


def test_complete_captures_usage_cost(monkeypatch):
    from paper_intelligence.openrouter import client as or_client

    class _Resp:
        status_code = 200

        def json(self):
            return {
                "choices": [{"message": {"content": "{}"}}],
                "usage": {
                    "prompt_tokens": 1000,
                    "completion_tokens": 500,
                    "cost": 0.042,
                },
            }

    monkeypatch.setenv("OPENROUTER_API_KEY", "test-key")
    monkeypatch.setattr(or_client.requests, "post", lambda *a, **k: _Resp())
    result = or_client.complete(
        or_client.LLMRequest(model="z-ai/glm-5.3-flash", messages=[{"role": "user", "content": "x"}])
    )
    assert result.actual_cost == pytest.approx(0.042)
    # table: 1000*0.15/1e6 + 500*0.50/1e6 = 0.00015 + 0.00025 = 0.0004
    assert result.estimated_cost == pytest.approx(0.0004)
