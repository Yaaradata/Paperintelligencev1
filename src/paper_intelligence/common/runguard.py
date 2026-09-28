"""Rolling failure-rate guard for paid per-item runs.

Trips when more than ``max_failure_rate`` of the last ``window`` item outcomes
failed. The rate is evaluated once ``min_items`` outcomes have been seen, so a
run that is failing wholesale stops after ``min_items`` items instead of after
the full window.
"""

from __future__ import annotations

import threading
from collections import deque


class RunGuardTripped(RuntimeError):
    """Raised by callers after the guard trips; carries the guard's reason."""


class RunGuard:
    def __init__(
        self,
        *,
        window: int = 100,
        max_failure_rate: float = 0.10,
        min_items: int = 20,
    ) -> None:
        if window <= 0 or min_items <= 0 or min_items > window:
            raise ValueError("need 0 < min_items <= window")
        self.window = window
        self.max_failure_rate = max_failure_rate
        self.min_items = min_items
        self._outcomes: deque[bool] = deque(maxlen=window)
        self._seen = 0
        self._lock = threading.Lock()
        self.tripped_at: int | None = None
        self.reason: str | None = None

    def record(self, ok: bool) -> bool:
        """Record one item outcome. Returns True if the guard is (now) tripped."""
        with self._lock:
            self._seen += 1
            self._outcomes.append(bool(ok))
            if self.tripped_at is None and len(self._outcomes) >= self.min_items:
                failed = sum(1 for o in self._outcomes if not o)
                rate = failed / len(self._outcomes)
                if rate > self.max_failure_rate:
                    self.tripped_at = self._seen
                    self.reason = (
                        f"runguard tripped at item {self._seen}: {failed}/{len(self._outcomes)} "
                        f"failed in last {len(self._outcomes)} ({rate:.0%} > "
                        f"{self.max_failure_rate:.0%})"
                    )
            return self.tripped_at is not None

    @property
    def tripped(self) -> bool:
        return self.tripped_at is not None

    def status(self) -> str:
        with self._lock:
            failed = sum(1 for o in self._outcomes if not o)
            n = len(self._outcomes)
        state = self.reason or "not tripped"
        return f"runguard: last {n} items, {failed} failed; {state}"
