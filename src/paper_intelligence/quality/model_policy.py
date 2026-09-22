"""Resolve which quality LLM model is current for a paper's published_at date."""

from __future__ import annotations

import os
import warnings
from datetime import date, datetime, timezone
from functools import lru_cache
from pathlib import Path
from typing import Any

import yaml

from paper_intelligence.common.config import POLICIES_DIR

POLICY_VERSION = "v001"
_POLICY_PATH = POLICIES_DIR / "quality_models" / f"{POLICY_VERSION}.yaml"


@lru_cache(maxsize=1)
def load_quality_model_policy(path: str | None = None) -> dict[str, Any]:
    policy_path = Path(path) if path else _POLICY_PATH
    data = yaml.safe_load(policy_path.read_text(encoding="utf-8")) or {}
    cutover = data.get("cutover_date")
    if not cutover:
        raise ValueError(f"quality_models policy missing cutover_date: {policy_path}")
    return {
        "policy_version": str(data.get("policy_version") or POLICY_VERSION),
        "cutover_date": date.fromisoformat(str(cutover)),
        "pre_cutover_model": str(data["pre_cutover_model"]),
        "post_cutover_model": str(data["post_cutover_model"]),
        "path": str(policy_path),
    }


def quality_model_env_override() -> str | None:
    """Explicit QUALITY_MODEL when set in the environment; else None."""
    raw = os.environ.get("QUALITY_MODEL")
    if raw is None or str(raw).strip() == "":
        return None
    return str(raw).strip()


def _as_utc_date(value: date | datetime | str | None) -> date | None:
    if value is None:
        return None
    if isinstance(value, datetime):
        dt = value if value.tzinfo else value.replace(tzinfo=timezone.utc)
        return dt.astimezone(timezone.utc).date()
    if isinstance(value, date):
        return value
    text = str(value).strip()
    if not text:
        return None
    if "T" in text or " " in text:
        try:
            if text.endswith("Z"):
                text = text[:-1] + "+00:00"
            dt = datetime.fromisoformat(text)
            if dt.tzinfo is None:
                dt = dt.replace(tzinfo=timezone.utc)
            return dt.astimezone(timezone.utc).date()
        except ValueError:
            text = text[:10]
    return date.fromisoformat(text[:10])


def mapped_quality_model(
    published_at: date | datetime | str | None,
    *,
    policy: dict[str, Any] | None = None,
) -> str:
    """Model required for a paper given its published_at (UTC date)."""
    pol = policy or load_quality_model_policy()
    pub = _as_utc_date(published_at)
    if pub is None:
        # Unknown date → post-cutover model (safer for new ingest).
        return str(pol["post_cutover_model"])
    if pub < pol["cutover_date"]:
        return str(pol["pre_cutover_model"])
    return str(pol["post_cutover_model"])


def resolve_quality_model(
    published_at: date | datetime | str | None,
    *,
    policy: dict[str, Any] | None = None,
    allow_env_override: bool = True,
) -> tuple[str, bool]:
    """Return (model, override_active).

    When QUALITY_MODEL is set in the environment and differs from the mapping,
    the env value wins (one-off runs) and override_active is True.
    """
    mapped = mapped_quality_model(published_at, policy=policy)
    if not allow_env_override:
        return mapped, False
    override = quality_model_env_override()
    if override is None or override == mapped:
        return mapped, False
    return override, True


def warn_quality_model_override(
    published_dates: list[date | datetime | str | None],
    *,
    policy: dict[str, Any] | None = None,
) -> list[str]:
    """Loud warnings when env QUALITY_MODEL disagrees with the date mapping."""
    override = quality_model_env_override()
    if override is None:
        return []
    pol = policy or load_quality_model_policy()
    msgs: list[str] = []
    disagreed = 0
    for pub in published_dates:
        mapped = mapped_quality_model(pub, policy=pol)
        if mapped != override:
            disagreed += 1
    if disagreed:
        msg = (
            f"WARNING: QUALITY_MODEL env override={override!r} disagrees with "
            f"quality_models/{pol['policy_version']} mapping for {disagreed}/"
            f"{len(published_dates)} paper date(s) "
            f"(cutover={pol['cutover_date']}; "
            f"pre={pol['pre_cutover_model']}; post={pol['post_cutover_model']}). "
            f"Override is for one-off runs only."
        )
        msgs.append(msg)
        warnings.warn(msg, stacklevel=2)
        print(msg, flush=True)
    return msgs


def group_ids_by_quality_model(
    papers: list[dict[str, Any]],
    *,
    id_key: str = "content_item_id",
    date_key: str = "published_at",
    policy: dict[str, Any] | None = None,
    honor_env_override: bool = True,
) -> dict[str, list[int]]:
    """Partition paper ids by resolved quality model."""
    groups: dict[str, list[int]] = {}
    dates = [p.get(date_key) for p in papers]
    if honor_env_override:
        warn_quality_model_override(dates, policy=policy)
    for paper in papers:
        model, _ = resolve_quality_model(
            paper.get(date_key),
            policy=policy,
            allow_env_override=honor_env_override,
        )
        groups.setdefault(model, []).append(int(paper[id_key]))
    return groups


def summarize_quality_models_for_window(
    conn: Any,
    *,
    date_from: str,
    date_until: str,
) -> dict[str, Any]:
    """Models that produced scored quality in the window + mix / stale flags."""
    sql = """
        SELECT
            COALESCE(
                c.adjudication_json->>'result_quality_model',
                (
                    SELECT r.model
                    FROM paper_intelligence.paper_classification_results r
                    WHERE r.content_item_id = c.content_item_id
                      AND r.task_type = 'quality'
                    ORDER BY r.created_at DESC
                    LIMIT 1
                )
            ) AS quality_model,
            COUNT(*) AS papers
        FROM paper_intelligence.paper_intelligence_current c
        JOIN paper_intelligence.papers p ON p.paper_id = c.content_item_id
        WHERE p.published_at >= %s::timestamptz
          AND p.published_at < (%s::timestamptz + interval '1 day')
          AND (c.final_score IS NOT NULL OR c.quality_status = 'scored')
        GROUP BY 1
        ORDER BY papers DESC
    """
    with conn.cursor() as cur:
        cur.execute(sql, (date_from, date_until))
        rows = [dict(r) for r in cur.fetchall()]
        cur.execute(
            """
            SELECT
                COUNT(*) FILTER (WHERE c.quality_status = 'stale_content') AS stale_content,
                COUNT(*) FILTER (WHERE c.quality_status = 'scored') AS scored,
                COUNT(*) FILTER (WHERE c.quality_status = 'pending') AS pending,
                COUNT(*) FILTER (WHERE c.quality_status = 'failed') AS failed
            FROM paper_intelligence.paper_intelligence_current c
            JOIN paper_intelligence.papers p ON p.paper_id = c.content_item_id
            WHERE p.published_at >= %s::timestamptz
              AND p.published_at < (%s::timestamptz + interval '1 day')
            """,
            (date_from, date_until),
        )
        status = dict(cur.fetchone() or {})
    models = {str(r["quality_model"] or "unknown"): int(r["papers"]) for r in rows}
    return {
        "quality_models": models,
        "mixed_models": len([m for m in models if m != "unknown"]) > 1,
        "status_counts": status,
    }
