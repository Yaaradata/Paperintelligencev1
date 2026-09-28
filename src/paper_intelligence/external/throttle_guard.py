"""Process-wide guard over provider throttling for free external APIs.

Every live request attempt to arXiv HTML, ROR and OpenAlex is one outcome:
429, 503 and timeouts/connection errors are failures, anything else (including
404) is ok. Cache hits are not requests and are not recorded. When the guard
trips, clients stop retrying and the affiliation stage stops, so the pipeline
halts instead of pushing harder against a provider that is throttling us.
"""

from __future__ import annotations

import threading
from collections import Counter

from paper_intelligence.common.runguard import RunGuard

THROTTLE_STATUSES = frozenset({429, 503})

_lock = threading.Lock()
_guard = RunGuard()
_counts: Counter[str] = Counter()


def record(provider: str, *, status: int | None = None, exception: BaseException | None = None) -> bool:
    """Record one request attempt. Returns True if the guard is (now) tripped."""
    throttled = exception is not None or (status in THROTTLE_STATUSES)
    with _lock:
        _counts[f"{provider}:requests"] += 1
        if throttled:
            kind = type(exception).__name__ if exception is not None else f"http_{status}"
            _counts[f"{provider}:{kind}"] += 1
        return _guard.record(not throttled)


def tripped() -> bool:
    return _guard.tripped


def reason() -> str | None:
    return _guard.reason


def counts() -> dict[str, int]:
    with _lock:
        return dict(_counts)


def reset(**guard_kwargs: int | float) -> None:
    """Fresh guard (per affiliation stage run, and in tests)."""
    global _guard
    with _lock:
        _guard = RunGuard(**guard_kwargs)
        _counts.clear()
