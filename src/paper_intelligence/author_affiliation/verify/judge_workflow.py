"""HTML + OpenAlex compare → optional LLM judge → persist accepted affiliations."""

from __future__ import annotations

import json
from typing import Any

from paper_intelligence.author_affiliation.verify.judge_compare import (
    COMPARE_DISAGREEMENT,
    COMPARE_EXACT_MATCH,
    COMPARE_HTML_ONLY,
    collect_claims,
    compare_claims,
)
from paper_intelligence.author_affiliation.verify.judge_effective import (
    RESOLVED_JUDGE_DECISIONS,
    build_name_to_id_from_compare,
    compute_rejected_organisation_ids,
)
from paper_intelligence.author_affiliation.verify.judge_llm import run_judge
from paper_intelligence.author_affiliation.verify.judge_persist import (
    JUDGE_VERSION_DEFAULT,
    auto_decision_for_compare,
    get_existing_judgment,
    persist_accepted_affiliations,
    upsert_judgment,
)


def _rejected_payload(
    compare: dict[str, Any],
    accepted_ids: list[int],
    unsupported_claims: list[Any] | None = None,
    decision: str | None = None,
) -> tuple[list[int], list[dict[str, Any]]]:
    rejected_ids = compute_rejected_organisation_ids(
        compare=compare,
        accepted_organisation_ids=accepted_ids,
        unsupported_claims=unsupported_claims,
        name_to_id=build_name_to_id_from_compare(compare),
        decision=decision,
    )
    name_map = {v: k for k, v in build_name_to_id_from_compare(compare).items()}
    rejected_claims = [
        {
            "organisation_id": oid,
            "organisation_name": name_map.get(oid) or str(oid),
            "reason": "evaluated_claim_not_accepted_by_judge",
        }
        for oid in rejected_ids
    ]
    return rejected_ids, rejected_claims


def _ensure_rejected_on_existing(
    conn: Any,
    existing: dict[str, Any],
    *,
    judge_version: str,
) -> dict[str, Any]:
    """Backfill rejected_organisation_ids on prior judgments when missing."""
    decision = str(existing.get("decision") or "").upper()
    if not existing.get("judge_called") or decision not in RESOLVED_JUDGE_DECISIONS:
        return existing
    accepted = list(existing.get("accepted_organisation_ids") or [])
    # Always recompute rejected from compare+accepted so empty-accept fail-open
    # clears prior accidental wipeouts.
    result = existing.get("result_json") or {}
    if isinstance(result, str):
        try:
            result = json.loads(result)
        except Exception:  # noqa: BLE001
            result = {}
    compare = result.get("compare") or {}
    unsupported = (result.get("judge") or {}).get("unsupported_claims") or []
    rejected_ids, rejected_claims = _rejected_payload(
        compare, accepted, unsupported, decision=decision
    )
    have = list(existing.get("rejected_organisation_ids") or [])
    if have == rejected_ids:
        return existing
    jid = upsert_judgment(
        conn,
        paper_id=int(existing["paper_id"]),
        compare_status=str(existing.get("compare_status") or "disagreement"),
        decision=existing.get("decision"),
        judge_called=True,
        result_json={**result, "rejected_organisations": rejected_claims},
        reason=existing.get("reason"),
        accepted_organisation_ids=accepted,
        rejected_organisation_ids=rejected_ids,
        model=existing.get("model"),
        prompt_version=existing.get("prompt_version"),
        estimated_cost_usd=float(existing["estimated_cost_usd"])
        if existing.get("estimated_cost_usd") is not None
        else None,
        input_tokens=existing.get("input_tokens"),
        output_tokens=existing.get("output_tokens"),
        judge_version=judge_version,
    )
    refreshed = get_existing_judgment(
        conn, int(existing["paper_id"]), judge_version=judge_version
    )
    if refreshed:
        refreshed["judgment_id"] = jid
        return refreshed
    return existing


def process_paper_affiliation_judge(
    conn: Any,
    paper_id: int,
    *,
    dry_run: bool = True,
    allow_openalex_network: bool = False,
    judge_version: str = JUDGE_VERSION_DEFAULT,
    persist: bool = True,
    force: bool = False,
) -> dict[str, Any]:
    """Run compare (+ optional judge) for one paper.

    dry_run=True: never call the LLM; still compute whether a call would be needed.
    Reruns skip paid calls when a prior judgment with judge_called=True exists
    (unless force=True).
    """
    existing = get_existing_judgment(conn, paper_id, judge_version=judge_version)
    if existing and existing.get("judge_called") and not force and not dry_run:
        existing = _ensure_rejected_on_existing(
            conn, existing, judge_version=judge_version
        )
        return {
            "paper_id": int(paper_id),
            "skipped_duplicate": True,
            "compare_status": existing.get("compare_status"),
            "decision": existing.get("decision"),
            "judge_called": True,
            "reason": "existing_judgment",
            "judgment_id": existing.get("judgment_id"),
            "accepted_organisation_ids": list(
                existing.get("accepted_organisation_ids") or []
            ),
            "rejected_organisation_ids": list(
                existing.get("rejected_organisation_ids") or []
            ),
        }

    claims = collect_claims(
        conn, paper_id, allow_openalex_network=allow_openalex_network
    )
    compare = compare_claims(claims)
    status = compare["compare_status"]

    result: dict[str, Any] = {
        "paper_id": int(paper_id),
        "arxiv_id": claims.get("arxiv_id"),
        "title": claims.get("title"),
        "compare": compare,
        "claims_summary": {
            "html_org_ids": compare["html_org_ids"],
            "html_org_names": compare["html_org_names"],
            "oa_org_ids": compare["oa_org_ids"],
            "oa_org_names": compare["oa_org_names"],
            "oa_work_status": (claims.get("openalex") or {}).get("work_status"),
            "oa_identity_ok": (claims.get("openalex") or {}).get("identity_ok"),
        },
        "skipped_duplicate": False,
    }

    if status != COMPARE_DISAGREEMENT:
        decision = auto_decision_for_compare(status)
        accepted_ids = (
            compare["html_org_ids"]
            if status in (COMPARE_EXACT_MATCH, COMPARE_HTML_ONLY)
            else []
        )
        if status == COMPARE_EXACT_MATCH:
            accepted_ids = compare["html_org_ids"]
        result.update(
            {
                "needs_judge": False,
                "judge_called": False,
                "decision": decision,
                "accepted_organisation_ids": accepted_ids,
                "rejected_organisation_ids": [],
                "reason": f"auto:{status}",
                "estimate": None,
            }
        )
        if persist and not dry_run:
            jid = upsert_judgment(
                conn,
                paper_id=paper_id,
                compare_status=status,
                decision=decision,
                judge_called=False,
                result_json=result,
                reason=result["reason"],
                accepted_organisation_ids=accepted_ids,
                rejected_organisation_ids=[],
                judge_version=judge_version,
            )
            result["judgment_id"] = jid
        elif persist and dry_run:
            result["would_persist_judgment"] = True
        return result

    judge = run_judge(conn, claims, compare, dry_run=dry_run)
    result["needs_judge"] = True
    result["judge"] = {
        k: judge.get(k)
        for k in (
            "ok",
            "dry_run",
            "judge_called",
            "decision",
            "reason",
            "error",
            "estimate",
            "accepted_organisations",
            "unsupported_claims",
            "llm",
            "payload",
        )
        if k in judge
    }
    result["estimate"] = judge.get("estimate")
    result["judge_called"] = bool(judge.get("judge_called"))
    result["decision"] = judge.get("decision") or ("UNCERTAIN" if not dry_run else None)

    if dry_run:
        result["reason"] = "dry_run_disagreement_would_call_judge"
        result["rejected_organisation_ids"] = []
        if persist:
            jid = upsert_judgment(
                conn,
                paper_id=paper_id,
                compare_status=status,
                decision=None,
                judge_called=False,
                result_json={**result, "dry_run": True},
                reason=result["reason"],
                accepted_organisation_ids=[],
                rejected_organisation_ids=[],
                model=(judge.get("estimate") or {}).get("model"),
                prompt_version=(judge.get("estimate") or {}).get("prompt_version"),
                estimated_cost_usd=(judge.get("estimate") or {}).get("estimated_cost_usd"),
                input_tokens=(judge.get("estimate") or {}).get("estimated_input_tokens"),
                output_tokens=(judge.get("estimate") or {}).get("estimated_output_tokens"),
                judge_version=judge_version,
            )
            result["judgment_id"] = jid
        return result

    decision = judge.get("decision") or "UNCERTAIN"
    accepted = judge.get("accepted_organisations") or []
    accepted_ids = sorted(
        {
            int(a["resolved_organisation_id"])
            for a in accepted
            if a.get("resolved_organisation_id") is not None
        }
    )
    rejected_ids: list[int] = []
    rejected_claims: list[dict[str, Any]] = []
    if decision in RESOLVED_JUDGE_DECISIONS:
        rejected_ids, rejected_claims = _rejected_payload(
            compare, accepted_ids, judge.get("unsupported_claims") or [], decision=decision
        )
    result["accepted_organisation_ids"] = accepted_ids
    result["rejected_organisation_ids"] = rejected_ids
    result["rejected_organisations"] = rejected_claims
    result["reason"] = judge.get("reason") or judge.get("error")

    if persist:
        llm = judge.get("llm") or {}
        jid = upsert_judgment(
            conn,
            paper_id=paper_id,
            compare_status=status,
            decision=decision,
            judge_called=True,
            result_json=result,
            reason=result.get("reason"),
            accepted_organisation_ids=accepted_ids,
            rejected_organisation_ids=rejected_ids,
            model=llm.get("model") or (judge.get("estimate") or {}).get("model"),
            prompt_version=llm.get("prompt_version")
            or (judge.get("estimate") or {}).get("prompt_version"),
            estimated_cost_usd=llm.get("estimated_cost"),
            input_tokens=llm.get("input_tokens"),
            output_tokens=llm.get("output_tokens"),
            judge_version=judge_version,
        )
        result["judgment_id"] = jid
        if decision != "UNCERTAIN" and accepted_ids:
            inserted = persist_accepted_affiliations(
                conn,
                paper_id=paper_id,
                accepted=accepted,
                decision=decision,
                reason=result.get("reason"),
            )
            result["inserted_affiliation_row_ids"] = inserted
        else:
            result["inserted_affiliation_row_ids"] = []

    return result
