"""Stage: audience_domain — PAID, cheap, screen survivors, reasoning off.

ONE call returns domain + subdomain + application_domain plus either:
  - v001: audience_relevance labels (legacy)
  - v002: tech_relevance / product_relevance seat scores

Results persist as separate append-only rows sharing run_id / prompt_version /
stage_version. Out-of-vocabulary values are logged and counted, never silently
dropped. Missing seat scores under v002 are parse failures.
"""

from __future__ import annotations

from typing import Any, Sequence

from psycopg import Connection

from paper_intelligence.audience_domain import vocabulary
from paper_intelligence.common.batch_runner import BatchStats, run_batches
from paper_intelligence.common.budget import BudgetCap
from paper_intelligence.common.config import (
    AUDIENCE_POLICY,
    CLASSIFY_BATCH_SIZE,
    CLASSIFY_MODEL,
    estimate_cost_usd,
    read_prompt,
)
from paper_intelligence.common.content_hash import compute_content_hash
from paper_intelligence.common.llm_stage import (
    call_llm_logged,
    indexed_paper_blocks,
    paper_block,
    parse_json_object,
    random_batches,
)
from paper_intelligence.db import connect, fetch_papers, insert_classification_results
from paper_intelligence.editorial.seats import format_seats_xml

STAGE_NAME = "audience_domain"

# Dual path: AUDIENCE_POLICY selects versions. Default v001 until Phase 7c.
if AUDIENCE_POLICY == "v002":
    POLICY_VERSION = "v002"
    PROMPT_VERSION = "v003"
    STAGE_VERSION = "v002"
else:
    POLICY_VERSION = "v001"
    PROMPT_VERSION = "v002"
    STAGE_VERSION = "v001"

GENERAL_METHOD = "general_method"
SEATS_VERSION = "v001"


def _valid_half_score(value: Any) -> float | None:
    """0.0–10.0 in 0.5 increments; None if missing/invalid."""
    if value is None:
        return None
    try:
        score = float(value)
    except (TypeError, ValueError):
        return None
    if score < 0.0 or score > 10.0:
        return None
    doubled = score * 2
    if abs(doubled - round(doubled)) > 1e-6:
        return None
    return round(doubled) / 2


def render_system_prompt(prompt_version: str = PROMPT_VERSION) -> str:
    """Load prompt and substitute {{EDITORIAL_SEATS}} from shared seat policy."""
    text = read_prompt("audience_domain", prompt_version)
    if "{{EDITORIAL_SEATS}}" in text:
        text = text.replace("{{EDITORIAL_SEATS}}", format_seats_xml(SEATS_VERSION))
    return text


def build_user_prompt(
    papers: Sequence[dict[str, Any]],
    *,
    policy_version: str = POLICY_VERSION,
) -> tuple[str, dict[int, int]]:
    blocks, index_to_id = indexed_paper_blocks(papers)
    indices = sorted(index_to_id)
    if policy_version == "v002":
        prompt = (
            "CLOSED VOCABULARIES — use only these values:\n"
            f"{vocabulary.vocabulary_block(policy_version)}\n\n"
            f"Score seat relevance and classify these {len(papers)} papers. "
            f"Return one object per paper, for exactly these batch_index values: "
            f"{indices}.\n\n{blocks}"
        )
    else:
        prompt = (
            "CLOSED VOCABULARIES — use only these values:\n"
            f"{vocabulary.vocabulary_block(policy_version)}\n\n"
            f"Classify these {len(papers)} papers. Return one object per paper, for "
            f"exactly these batch_index values: {indices}.\n\n{blocks}"
        )
    return prompt, index_to_id


def _clean_list(values: Any) -> list[str]:
    if values is None:
        return []
    if isinstance(values, str):
        values = [values]
    if not isinstance(values, list):
        return []
    return [str(v).strip().lower() for v in values if str(v).strip()]


def validate_entry(
    entry: dict[str, Any],
    *,
    policy_version: str = POLICY_VERSION,
) -> tuple[dict[str, Any] | None, list[str]]:
    """Split a model answer into in-vocabulary values and out-of-vocabulary reports.

    Under v002, missing/invalid tech_relevance or product_relevance returns
    ``(None, problems)`` so the caller treats the paper as a parse failure.
    """
    oov: list[str] = []

    valid_domains = set(vocabulary.domains(policy_version))
    valid_apps = set(vocabulary.application_domains(policy_version))
    sub_by_domain = vocabulary.subdomains_by_domain(policy_version)

    domain_raw = (entry.get("domain") or "").strip().lower() if entry.get("domain") else ""
    domain = domain_raw if domain_raw in valid_domains else None
    if domain_raw and domain is None:
        oov.append(f"domain:{domain_raw}")

    allowed_subs = set(sub_by_domain.get(domain, [])) if domain else set()
    subdomains = []
    for value in _clean_list(entry.get("subdomains")):
        if value in allowed_subs:
            subdomains.append(value)
        else:
            oov.append(f"subdomain:{value}")

    applications = []
    for value in _clean_list(entry.get("application_domain")):
        if value in valid_apps:
            applications.append(value)
        else:
            oov.append(f"application_domain:{value}")

    # general_method is mutually exclusive with every sector label.
    if GENERAL_METHOD in applications and len(applications) > 1:
        applications = [GENERAL_METHOD]

    confidence = _valid_half_score(entry.get("confidence"))

    if policy_version == "v002":
        tech = _valid_half_score(entry.get("tech_relevance"))
        product = _valid_half_score(entry.get("product_relevance"))
        problems: list[str] = []
        if tech is None:
            problems.append("missing_or_invalid:tech_relevance")
        if product is None:
            problems.append("missing_or_invalid:product_relevance")
        if problems:
            return None, problems + oov
        tech_reason = str(entry.get("tech_reason") or "").strip() or None
        product_reason = str(entry.get("product_reason") or "").strip() or None
        return (
            {
                "tech_relevance": tech,
                "product_relevance": product,
                "tech_reason": tech_reason,
                "product_reason": product_reason,
                "domain": domain,
                "subdomains": subdomains,
                "application_domain": applications,
                "confidence": confidence,
            },
            oov,
        )

    valid_audiences = set(vocabulary.audiences(policy_version))
    audience = []
    for value in _clean_list(entry.get("audience_relevance")):
        if value in valid_audiences:
            audience.append(value)
        else:
            oov.append(f"audience:{value}")

    return (
        {
            "audience_relevance": audience,
            "domain": domain,
            "subdomains": subdomains,
            "application_domain": applications,
            "confidence": confidence,
        },
        oov,
    )


def parse_response(
    text: str,
    index_to_id: dict[int, int],
    *,
    policy_version: str = POLICY_VERSION,
) -> tuple[dict[int, dict[str, Any]], list[str]]:
    payload = parse_json_object(text)
    parsed: dict[int, dict[str, Any]] = {}
    problems: list[str] = []
    expected_indices = set(index_to_id)
    seen_indices: set[int] = set()
    for entry in payload.get("papers") or []:
        try:
            batch_index = int(entry.get("batch_index"))
        except (TypeError, ValueError):
            problems.append("unparseable batch_index")
            continue
        if batch_index not in expected_indices:
            problems.append(f"unexpected batch_index {batch_index}")
            continue
        if batch_index in seen_indices:
            problems.append(f"duplicate batch_index {batch_index}")
            continue
        seen_indices.add(batch_index)
        content_id = index_to_id[batch_index]
        values, oov = validate_entry(entry, policy_version=policy_version)
        if values is None:
            problems.append(
                f"batch_index={batch_index} parse_failure: {', '.join(oov)}"
            )
            continue
        if oov:
            problems.append(f"batch_index={batch_index} out-of-vocabulary: {', '.join(oov)}")
        parsed[content_id] = values
    missing = expected_indices - seen_indices
    if missing:
        problems.append(f"missing batch_index: {sorted(missing)}")
    return parsed, problems


def _rows_for(
    content_id: int,
    values: dict[str, Any],
    *,
    model: str,
    run_id: str,
    input_content_hash: str | None = None,
    policy_version: str = POLICY_VERSION,
    prompt_version: str = PROMPT_VERSION,
    stage_version: str = STAGE_VERSION,
) -> list[dict]:
    base = {
        "content_item_id": content_id,
        "method": "llm",
        "provider": "openrouter",
        "model": model,
        "prompt_version": prompt_version,
        "policy_version": policy_version,
        "stage_version": stage_version,
        "confidence": (values["confidence"] / 10.0) if values["confidence"] is not None else None,
        "run_id": run_id,
        "input_content_hash": input_content_hash,
    }
    rows = [
        {**base, "task_type": "domain", "result_json": {"domain": values["domain"]}},
        {**base, "task_type": "subdomain", "result_json": {"subdomains": values["subdomains"]}},
        {
            **base,
            "task_type": "application_domain",
            "result_json": {"application_domains": values["application_domain"]},
        },
    ]
    if policy_version == "v002":
        rows.extend(
            [
                {
                    **base,
                    "task_type": "tech_relevance",
                    "result_json": {
                        "tech_relevance": values["tech_relevance"],
                        "tech_reason": values.get("tech_reason"),
                    },
                },
                {
                    **base,
                    "task_type": "product_relevance",
                    "result_json": {
                        "product_relevance": values["product_relevance"],
                        "product_reason": values.get("product_reason"),
                    },
                },
            ]
        )
    else:
        rows.insert(
            0,
            {
                **base,
                "task_type": "audience",
                "result_json": {"audiences": values["audience_relevance"]},
            },
        )
    return rows


def run_window(
    conn: Connection,
    content_item_ids: Sequence[int],
    *,
    run_id: str,
    stage_run_id: str,
    model: str = CLASSIFY_MODEL,
    batch_size: int = CLASSIFY_BATCH_SIZE,
    dry_run: bool = False,
    max_cost_usd: float | None = None,
    policy_version: str | None = None,
    prompt_version: str | None = None,
    stage_version: str | None = None,
) -> BatchStats:
    policy = policy_version or POLICY_VERSION
    prompt_ver = prompt_version or PROMPT_VERSION
    stage_ver = stage_version or STAGE_VERSION
    # Keep prompt/stage aligned when caller overrides only policy.
    if policy_version == "v002" and prompt_version is None:
        prompt_ver = "v003"
        stage_ver = stage_version or "v002"
    elif policy_version == "v001" and prompt_version is None:
        prompt_ver = "v002"
        stage_ver = stage_version or "v001"

    budget = BudgetCap(max_cost_usd) if max_cost_usd is not None else None
    stats = BatchStats(papers_requested=len(content_item_ids), budget=budget)
    if not content_item_ids:
        return stats

    papers = fetch_papers(conn, content_item_ids)
    system_prompt = render_system_prompt(prompt_ver)

    if dry_run:
        calls = -(-len(papers) // max(1, batch_size))
        chars = sum(len(paper_block(p)) for p in papers)
        overhead = (len(system_prompt) + len(vocabulary.vocabulary_block(policy))) * calls
        stats.calls = calls
        stats.input_tokens = (chars + overhead) // 4
        stats.output_tokens = len(papers) * (110 if policy == "v002" else 90)
        stats.cost_usd = estimate_cost_usd(model, stats.input_tokens, stats.output_tokens)
        return stats

    batches = random_batches(papers, batch_size)

    def handle(batch: Sequence[dict[str, Any]]) -> None:
        expected = {p["content_item_id"] for p in batch}
        try:
            with connect() as batch_conn:
                user_prompt, index_to_id = build_user_prompt(batch, policy_version=policy)
                result = call_llm_logged(
                    batch_conn,
                    model=model,
                    system_prompt=system_prompt,
                    user_prompt=user_prompt,
                    prompt_version=prompt_ver,
                    stage_name=STAGE_NAME,
                    reasoning_effort=None,  # closed-enum mapping, never deliberation
                    run_id=run_id,
                    stage_run_id=stage_run_id,
                    entity=f"audience_domain_{min(expected)}",
                )
                parsed, problems = parse_response(
                    result["content"], index_to_id, policy_version=policy
                )
                rows: list[dict[str, Any]] = []
                by_id = {p["content_item_id"]: p for p in batch}
                for content_id, values in parsed.items():
                    paper = by_id[content_id]
                    input_hash = paper.get("content_hash") or compute_content_hash(
                        paper.get("title"), paper.get("abstract")
                    )
                    rows.extend(
                        _rows_for(
                            content_id,
                            values,
                            model=model,
                            run_id=run_id,
                            input_content_hash=input_hash,
                            policy_version=policy,
                            prompt_version=prompt_ver,
                            stage_version=stage_ver,
                        )
                    )
                insert_classification_results(batch_conn, rows)
                batch_conn.commit()
            if problems:
                stats.add_warning("; ".join(problems))
            stats.add_call(
                succeeded=len(parsed),
                failed=len(expected) - len(parsed),
                input_tokens=result["input_tokens"],
                output_tokens=result["output_tokens"],
                cost=result["estimated_cost"],
                estimated_cost=result.get("estimated_cost_usd"),
                actual_cost=result.get("actual_cost_usd"),
            )
        except Exception as exc:  # noqa: BLE001
            stats.add_error(f"{type(exc).__name__}: {exc}", failed=len(expected))

    run_batches(batches, handle, label="audience_domain", budget=budget, stats=stats)
    return stats
