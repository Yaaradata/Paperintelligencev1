"""RunGuard: >10% failures over the last 100 items trips the guard."""

from __future__ import annotations

import pytest

from paper_intelligence.common.runguard import RunGuard


def _feed(guard: RunGuard, outcomes: list[bool]) -> int | None:
    for ok in outcomes:
        guard.record(ok)
    return guard.tripped_at


def test_replay_of_cancelled_backfill_trips_at_item_20():
    # Run 3558a3ee: 303 papers processed, every one failed (HTTP 404 routing).
    assert _feed(RunGuard(), [False] * 303) == 20


def test_ten_percent_exactly_does_not_trip():
    outcomes = ([True] * 9 + [False]) * 10  # 10/100 failed
    assert _feed(RunGuard(), outcomes) is None


def test_eleven_in_last_hundred_trips():
    outcomes = [True] * 89 + [False] * 11
    assert _feed(RunGuard(), outcomes) is not None


def test_old_failures_roll_out_of_window():
    guard = RunGuard(window=100, max_failure_rate=0.10, min_items=100)
    outcomes = [False] * 10 + [True] * 200  # at most 10/100 in any full window
    assert _feed(guard, outcomes) is None


def test_not_evaluated_before_min_items():
    guard = RunGuard(min_items=20)
    assert _feed(guard, [False] * 19) is None
    assert guard.record(False) is True


def test_invalid_config():
    with pytest.raises(ValueError):
        RunGuard(window=10, min_items=20)


def _run_stage_like(outcomes: list[bool], batch_size: int = 5):
    """Drive run_batches the way screen/audience_domain/quality handlers do."""
    from paper_intelligence.common.batch_runner import BatchStats, run_batches

    stats = BatchStats()
    handled = []
    batches = [outcomes[i : i + batch_size] for i in range(0, len(outcomes), batch_size)]

    def handle(batch):
        handled.append(len(batch))
        ok = sum(batch)
        stats.add_call(succeeded=ok, failed=len(batch) - ok,
                       input_tokens=0, output_tokens=0, cost=0.0)

    run_batches(batches, handle, concurrency=1, stats=stats, label="screen")
    return stats, sum(handled)


def test_batch_runner_guard_stops_failing_paid_stage():
    stats, handled = _run_stage_like([False] * 500)
    assert stats.stopped_runguard is True
    assert "runguard tripped" in stats.stop_reason
    assert handled == 20  # stops submitting once 20 papers have all failed


def test_batch_runner_guard_quiet_on_healthy_stage():
    stats, handled = _run_stage_like(([True] * 19 + [False]) * 25)
    assert stats.stopped_runguard is False
    assert handled == 500


def test_batch_runner_without_stats_has_no_guard():
    from paper_intelligence.common.batch_runner import run_batches

    seen = []
    run_batches([[1]] * 30, lambda b: seen.append(b), concurrency=1)
    assert len(seen) == 30
