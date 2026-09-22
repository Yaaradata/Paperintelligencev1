"""Stage: audience_domain — PAID, cheap, screen survivors, reasoning off.

ONE call returns audience + domain + subdomain + application_domain; the result
persists as separate append-only rows sharing run_id / prompt_version /
stage_version. Out-of-vocabulary values are logged and counted, never silently
dropped.
"""

from __future__ import annotations

from typing import Any, Sequence

from psycopg import Connection

from paper_intelligence.audience_domain import vocabulary
from paper_intelligence.common.batch_runner import BatchStats, run_batches
from paper_intelligence.common.budget import BudgetCap
from paper_intelligence.common.config import (
    CLASSIFY_BATCH_SIZE,
    CLASSIFY_MODEL,
    estimate_cost_usd,
    read_prompt,
)
from paper_intelligence.common.llm_stage import (
    call_llm_logged,
    paper_block,
    parse_json_object,
    random_batches,
)
from paper_intelligence.db import connect, fetch_papers, insert_classification_results

STAGE_NAME = "audience_domain"
STAGE_VERSION = "v001"
PROMPT_VERSION = "v002"
POLICY_VERSION = vocabulary.POLICY_VERSION

GENERAL_METHOD = "general_method"


def build_user_prompt(papers: Sequence[dict[str, Any]]) -> str:
    blocks = "\n---\n".join(paper_block(p) for p in papers)
    ids = [p["content_item_id"] for p in papers]
    return (
        "CLOSED VOCABULARIES — use only these values:\n"
        f"{vocabulary.vocabulary_block()}\n\n"
        f"Classify these {len(papers)} papers. Return one object per paper, for "
        f"exactly these content_item_id values: {ids}.\n\n{blocks}"
    )


def _clean_list(values: Any) -> list[str]:
    if values is None:
        return []
    if isinstance(values, str):
        values = [values]
    if not isinstance(values, list):
        return []
    return [str(v).strip().lower() for v in values if str(v).strip()]


def validate_entry(entry: dict[str, Any]) -> tuple[dict[str, Any], list[str]]:
    """Split a model answer into in-vocabulary values and out-of-vocabulary reports."""
    oov: list[str] = []

    valid_audiences = set(vocabulary.audiences())
    valid_domains = set(vocabulary.domains())
    valid_apps = set(vocabulary.application_domains())
    sub_by_domain = vocabulary.subdomains_by_domain()

    audience = []
    for value in _clean_list(entry.get("audience_relevance")):
        if value in valid_audiences:
            audience.append(value)
        else:
            oov.append(f"audience:{value}")

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

    confidence = entry.get("confidence")
    try:
        confidence = float(confidence) if confidence is not None else None
    except (TypeError, ValueError):
        confidence = None

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
    text: str, expected_ids: set[int]
) -> tuple[dict[int, dict[str, Any]], list[str]]:
    payload = parse_json_object(text)
    parsed: dict[int, dict[str, Any]] = {}
    problems: list[str] = []
    for entry in payload.get("papers") or []:
        try:
            content_id = int(entry.get("content_item_id"))
        except (TypeError, ValueError):
            problems.append("unparseable content_item_id")
            continue
        if content_id not in expected_ids:
            problems.append(f"unexpected content_item_id {content_id}")
            continue
        values, oov = validate_entry(entry)
        if oov:
            problems.append(f"{content_id} out-of-vocabulary: {', '.join(oov)}")
        parsed[content_id] = values
    missing = expected_ids - parsed.keys()
    if missing:
        problems.append(f"missing ids: {sorted(missing)}")
    return parsed, problems


def _rows_for(content_id: int, values: dict[str, Any], *, model: str, run_id: str) -> list[dict]:
    base = {
        "content_item_id": content_id,
        "method": "llm",
        "provider": "openrouter",
        "model": model,
        "prompt_version": PROMPT_VERSION,
        "policy_version": POLICY_VERSION,
        "stage_version": STAGE_VERSION,
        "confidence": (values["confidence"] / 10.0) if values["confidence"] is not None else None,
        "run_id": run_id,
    }
    return [
        {**base, "task_type": "audience", "result_json": {"audiences": values["audience_relevance"]}},
        {**base, "task_type": "domain", "result_json": {"domain": values["domain"]}},
        {**base, "task_type": "subdomain", "result_json": {"subdomains": values["subdomains"]}},
        {
            **base,
            "task_type": "application_domain",
            "result_json": {"application_domains": values["application_domain"]},
        },
    ]


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
) -> BatchStats:
    budget = BudgetCap(max_cost_usd) if max_cost_usd is not None else None
    stats = BatchStats(papers_requested=len(content_item_ids), budget=budget)
    if not content_item_ids:
        return stats

    papers = fetch_papers(conn, content_item_ids)
    system_prompt = read_prompt("audience_domain", PROMPT_VERSION)

    if dry_run:
        calls = -(-len(papers) // max(1, batch_size))
        chars = sum(len(paper_block(p)) for p in papers)
        overhead = (len(system_prompt) + len(vocabulary.vocabulary_block())) * calls
        stats.calls = calls
        stats.input_tokens = (chars + overhead) // 4
        stats.output_tokens = len(papers) * 90
        stats.cost_usd = estimate_cost_usd(model, stats.input_tokens, stats.output_tokens)
        return stats

    batches = random_batches(papers, batch_size)

    def handle(batch: Sequence[dict[str, Any]]) -> None:
        expected = {p["content_item_id"] for p in batch}
        try:
            with connect() as batch_conn:
                result = call_llm_logged(
                    batch_conn,
                    model=model,
                    system_prompt=system_prompt,
                    user_prompt=build_user_prompt(batch),
                    prompt_version=PROMPT_VERSION,
                    stage_name=STAGE_NAME,
                    reasoning_effort=None,  # closed-enum mapping, never deliberation
                    run_id=run_id,
                    stage_run_id=stage_run_id,
                    entity=f"audience_domain_{min(expected)}",
                )
                parsed, problems = parse_response(result["content"], expected)
                rows: list[dict[str, Any]] = []
                for content_id, values in parsed.items():
                    rows.extend(_rows_for(content_id, values, model=model, run_id=run_id))
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
            )
        except Exception as exc:  # noqa: BLE001
            stats.add_error(f"{type(exc).__name__}: {exc}", failed=len(expected))

    run_batches(batches, handle, label="audience_domain", budget=budget, stats=stats)
    return stats
