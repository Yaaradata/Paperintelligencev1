"""Runtime configuration. Values come from the environment, never literals in stage code."""

from __future__ import annotations

import os
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[3]
PROMPTS_DIR = REPO_ROOT / "prompts"
POLICIES_DIR = REPO_ROOT / "policies"

RAW_CACHE_DIR = Path(
    os.getenv("PI_RAW_CACHE_DIR", str(REPO_ROOT.parent.parent / "shared_data" / "raw"))
)

OPENROUTER_API_BASE = os.getenv("OPENROUTER_API_BASE", "https://openrouter.ai/api/v1")

SCREEN_MODEL = os.getenv("SCREEN_MODEL", "z-ai/glm-5.3-flash")
CLASSIFY_MODEL = os.getenv("CLASSIFY_MODEL", SCREEN_MODEL)
QUALITY_MODEL = os.getenv("QUALITY_MODEL", "openai/gpt-5.6-sol")

SCREEN_BATCH_SIZE = int(os.getenv("SCREEN_BATCH_SIZE", "15"))
CLASSIFY_BATCH_SIZE = int(os.getenv("CLASSIFY_BATCH_SIZE", "15"))
QUALITY_BATCH_SIZE = int(os.getenv("QUALITY_BATCH_SIZE", "5"))

SCREEN_MIN_AI_RELEVANCE = float(os.getenv("SCREEN_MIN_AI_RELEVANCE", "5.0"))
GATE_PERCENTILE = float(os.getenv("GATE_PERCENTILE", "15"))

STAGE_CONCURRENCY = int(os.getenv("PI_STAGE_CONCURRENCY", "6"))

QUALITY_REASONING_EFFORT = os.getenv("QUALITY_REASONING_EFFORT", "medium")

# Catalog cutover flags (default OFF until canary approved).
def _env_flag(name: str, default: str = "0") -> bool:
    return os.getenv(name, default).strip().lower() in {"1", "true", "yes", "on"}


# Final cutover: PI catalog is permanently authoritative.
# Radar dual-write is OFF by default after soak; re-enable only for
# optional one-way PI→Radar projection (never as a rollback source of truth).
PI_USE_PAPERS_CATALOG = _env_flag("PI_USE_PAPERS_CATALOG", "1")
PI_WRITE_RADAR_COMPAT = _env_flag("PI_WRITE_RADAR_COMPAT", "0")

# Per-model OpenRouter prices, USD per million tokens. Override per model with
# PI_PRICE_<SLUG>_IN / _OUT where SLUG upper-cases the model id and replaces
# non-alphanumerics with underscores.
_DEFAULT_PRICES: dict[str, tuple[float, float]] = {
    "z-ai/glm-5.3-flash": (0.15, 0.50),
    "openai/gpt-5.6-sol": (1.25, 10.00),
}


def _slug(model: str) -> str:
    return "".join(ch if ch.isalnum() else "_" for ch in model).upper()


def model_prices(model: str) -> tuple[float, float]:
    """(input, output) USD per million tokens for a model."""
    slug = _slug(model)
    default_in, default_out = _DEFAULT_PRICES.get(model, (0.0, 0.0))
    price_in = float(os.getenv(f"PI_PRICE_{slug}_IN", default_in))
    price_out = float(os.getenv(f"PI_PRICE_{slug}_OUT", default_out))
    return price_in, price_out


def estimate_cost_usd(model: str, input_tokens: int | None, output_tokens: int | None) -> float:
    price_in, price_out = model_prices(model)
    inp = int(input_tokens or 0)
    out = int(output_tokens or 0)
    return round((inp / 1_000_000.0) * price_in + (out / 1_000_000.0) * price_out, 6)


def read_prompt(stage: str, version: str) -> str:
    return (PROMPTS_DIR / stage / f"{version}.md").read_text(encoding="utf-8")
