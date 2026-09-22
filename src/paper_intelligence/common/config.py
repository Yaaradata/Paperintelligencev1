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
# Note: QUALITY_MODEL env is a one-off override. Prefer
# policies/quality_models/v001.yaml (mapped_quality_model) for currentness.
# quality_model_env_override() is True only when the var is actually set.

SCREEN_BATCH_SIZE = int(os.getenv("SCREEN_BATCH_SIZE", "15"))
CLASSIFY_BATCH_SIZE = int(os.getenv("CLASSIFY_BATCH_SIZE", "15"))
QUALITY_BATCH_SIZE = int(os.getenv("QUALITY_BATCH_SIZE", "5"))

SCREEN_MIN_AI_RELEVANCE = float(os.getenv("SCREEN_MIN_AI_RELEVANCE", "5.0"))
GATE_PERCENTILE = float(os.getenv("GATE_PERCENTILE", "15"))
# Quality top-slice scope: "window" (legacy / default) or "day" (per UTC published_at date).
_ROUTER_SCOPE_RAW = os.getenv("ROUTER_PERCENTILE_SCOPE", "window").strip().lower()
ROUTER_PERCENTILE_SCOPE = (
    _ROUTER_SCOPE_RAW if _ROUTER_SCOPE_RAW in {"window", "day"} else "window"
)

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
#
# Unknown models must NOT default to $0 — model_prices() raises instead.
# Verified against OpenRouter model pages on 2026-09-22.
_DEFAULT_PRICES: dict[str, tuple[float, float]] = {
    # https://openrouter.ai/z-ai/glm-5.3-flash — list $0.15 / $0.50.
    # Note: a 50% promo ran until 2026-09-09 16:00 UTC; earlier billed spend
    # may be ~half of table estimates.
    "z-ai/glm-5.3-flash": (0.15, 0.50),
    # https://openrouter.ai/z-ai/glm-4.6 — list $0.43 / $1.75 (was wrongly 0.15/0.50).
    "z-ai/glm-4.6": (0.43, 1.75),
    # https://openrouter.ai/openai/gpt-5.6-sol — list $5 / $30 (was wrongly 1.25/10).
    "openai/gpt-5.6-sol": (5.00, 30.00),
    # https://openrouter.ai/openai/gpt-5.6-terra — list $2 / $12 (post-cutover
    # quality model per policies/quality_models/v001.yaml).
    "openai/gpt-5.6-terra": (2.00, 12.00),
}


class UnknownModelPriceError(ValueError):
    """Raised when a model has no default price and no PI_PRICE_* env override."""


def _slug(model: str) -> str:
    return "".join(ch if ch.isalnum() else "_" for ch in model).upper()


def model_prices(model: str) -> tuple[float, float]:
    """(input, output) USD per million tokens for a model.

    Raises ``UnknownModelPriceError`` when the model has no default entry and
    both ``PI_PRICE_<SLUG>_IN`` and ``_OUT`` are not set. Never returns a silent
    $0/$0 default for unknown models.
    """
    slug = _slug(model)
    env_in = os.getenv(f"PI_PRICE_{slug}_IN")
    env_out = os.getenv(f"PI_PRICE_{slug}_OUT")
    if model in _DEFAULT_PRICES:
        default_in, default_out = _DEFAULT_PRICES[model]
        price_in = float(env_in) if env_in is not None else default_in
        price_out = float(env_out) if env_out is not None else default_out
        return price_in, price_out
    if env_in is None or env_out is None:
        raise UnknownModelPriceError(
            f"No price configured for model {model!r}. "
            f"Set PI_PRICE_{slug}_IN and PI_PRICE_{slug}_OUT "
            f"(USD per million tokens), or add a verified entry to _DEFAULT_PRICES."
        )
    return float(env_in), float(env_out)


def require_model_priced(model: str) -> tuple[float, float]:
    """Fail fast at paid-stage startup if ``model`` cannot be costed."""
    return model_prices(model)


def estimate_cost_usd(model: str, input_tokens: int | None, output_tokens: int | None) -> float:
    price_in, price_out = model_prices(model)
    inp = int(input_tokens or 0)
    out = int(output_tokens or 0)
    return round((inp / 1_000_000.0) * price_in + (out / 1_000_000.0) * price_out, 6)


def read_prompt(stage: str, version: str) -> str:
    return (PROMPTS_DIR / stage / f"{version}.md").read_text(encoding="utf-8")
