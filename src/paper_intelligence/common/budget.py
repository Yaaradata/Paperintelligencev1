"""Budget cap helpers for paid LLM stages (projection + live enforcement)."""

from __future__ import annotations

import json
import os
import threading
from pathlib import Path
from typing import Any


class BudgetCap:
    """Thread-safe cumulative spend tracker for concurrent batch runs.

    New batches are refused once actual spend reaches ``max_cost_usd``.
    In-flight batches may finish and slightly overshoot the cap.
    """

    def __init__(self, max_cost_usd: float) -> None:
        if max_cost_usd < 0:
            raise ValueError("max_cost_usd must be >= 0")
        self.max_cost_usd = float(max_cost_usd)
        self._actual_usd = 0.0
        self._lock = threading.Lock()
        self.stopped = False

    @property
    def actual_usd(self) -> float:
        with self._lock:
            return self._actual_usd

    def add_actual(self, cost: float) -> None:
        with self._lock:
            self._actual_usd += float(cost or 0.0)
            if self._actual_usd >= self.max_cost_usd:
                self.stopped = True

    def allow_new_batch(self) -> bool:
        with self._lock:
            if self._actual_usd >= self.max_cost_usd:
                self.stopped = True
                return False
            return True


def resolve_max_cost_usd(cli_value: float | None) -> float | None:
    """CLI ``--max-cost-usd`` wins; else ``PI_MAX_COST_USD``; else uncapped."""
    if cli_value is not None:
        return float(cli_value)
    raw = os.getenv("PI_MAX_COST_USD")
    if raw is None or str(raw).strip() == "":
        return None
    return float(raw)


def format_model_banner(
    *,
    screen_model: str,
    classify_model: str,
    quality_model: str,
) -> str:
    return (
        f"models: screen={screen_model} classify={classify_model} quality={quality_model}"
    )


def format_budget_line(
    *,
    projected: float | None,
    actual: float,
    cap: float | None,
    stopped: bool = False,
) -> str:
    proj_s = f"${projected:.4f}" if projected is not None else "n/a"
    cap_s = f"${cap:.4f}" if cap is not None else "none"
    status = "stopped_budget_cap" if stopped else "ok"
    return f"budget: projected={proj_s} actual=${actual:.4f} cap={cap_s} status={status}"


def load_budget_state(path: str | Path) -> dict[str, Any]:
    p = Path(path)
    if not p.exists():
        return {}
    return json.loads(p.read_text(encoding="utf-8"))


def save_budget_state(path: str | Path, state: dict[str, Any]) -> None:
    Path(path).write_text(json.dumps(state, indent=2, default=str) + "\n", encoding="utf-8")


def update_budget_state_after_stage(
    path: str | Path | None,
    *,
    stage: str,
    actual_usd: float,
    projected_usd: float | None = None,
    stopped_budget_cap: bool = False,
) -> dict[str, Any] | None:
    """Accumulate pipeline spend in a shared JSON ledger (subprocess-safe)."""
    if not path:
        return None
    state = load_budget_state(path)
    cap = state.get("cap")
    spent = float(state.get("spent_total") or 0.0) + float(actual_usd or 0.0)
    state["spent_total"] = round(spent, 6)
    state["cap"] = cap
    state["remaining"] = None if cap is None else round(float(cap) - spent, 6)
    state["last_stage"] = stage
    state["last_actual_usd"] = round(float(actual_usd or 0.0), 6)
    if projected_usd is not None:
        state["last_projected_usd"] = round(float(projected_usd), 6)
    stages = list(state.get("stages") or [])
    stages.append(
        {
            "stage": stage,
            "actual_usd": round(float(actual_usd or 0.0), 6),
            "projected_usd": projected_usd,
            "stopped_budget_cap": bool(stopped_budget_cap),
        }
    )
    state["stages"] = stages
    if stopped_budget_cap:
        state["stopped_budget_cap"] = True
    if cap is not None and spent >= float(cap):
        state["stopped_budget_cap"] = True
    save_budget_state(path, state)
    return state
