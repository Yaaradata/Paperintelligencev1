"""Hugging Face Daily Papers enrichment stage."""

from paper_intelligence.hf_signals.stage import (
    STAGE_NAME,
    STAGE_VERSION,
    collect_daily_index,
    run_window,
)

__all__ = [
    "STAGE_NAME",
    "STAGE_VERSION",
    "collect_daily_index",
    "run_window",
]
