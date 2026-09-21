"""LLM judge for HTML vs OpenAlex affiliation disagreements."""

from __future__ import annotations

import json
import os
from typing import Any

from paper_intelligence.author_affiliation.verify.html_resolve import resolve_local_organisation
from paper_intelligence.common.config import (
    CLASSIFY_MODEL,
    estimate_cost_usd,
    read_prompt,
)
from paper_intelligence.common.llm_stage import call_llm_logged, parse_json_object

JUDGE_MODEL = os.getenv("MODEL_JUDGE_GLM") or os.getenv("AFFILIATION_JUDGE_MODEL") or CLASSIFY_MODEL
PROMPT_VERSION = os.getenv("AFFILIATION_JUDGE_PROMPT_VERSION", "v001")
STAGE_NAME = "affiliation_judge"
VALID_DECISIONS = frozenset({"HTML", "OPENALEX", "BOTH", "UNCERTAIN"})


def build_judge_payload(claims: dict[str, Any], compare: dict[str, Any]) -> dict[str, Any]:
    """Structured evidence packet for the judge (and dry-run inspection)."""
    return {
        "paper_id": claims["paper_id"],
        "arxiv_id": claims.get("arxiv_id"),
        "title": claims.get("title"),
        "authors": [a.get("name") for a in claims.get("authors") or []],
        "html_affiliation_text": (claims.get("html") or {}).get("raw_sample") or [],
        "html_organisation_claims": {
            "org_names": compare.get("html_org_names") or [],
            "org_ids": compare.get("html_org_ids") or [],
        },
        "openalex": {
            "work_id": (claims.get("openalex") or {}).get("work_id"),
            "work_title": (claims.get("openalex") or {}).get("work_title"),
            "identity_ok": (claims.get("openalex") or {}).get("identity_ok"),
            "identity_reason": (claims.get("openalex") or {}).get("identity_reason"),
            "organisation_claims": {
                "org_names": compare.get("oa_org_names") or [],
                "org_ids": compare.get("oa_org_ids") or [],
            },
            "author_institution_pairs": [
                {
                    "author_name": p.get("author_name"),
                    "institution_name": p.get("institution_name"),
                }
                for p in ((claims.get("openalex") or {}).get("pairs") or [])[:40]
            ],
        },
        "compare_summary": {
            "overlap_ids": compare.get("overlap_ids"),
            "html_only_ids": compare.get("html_only_ids"),
            "oa_only_ids": compare.get("oa_only_ids"),
        },
    }


def estimate_judge_tokens(payload: dict[str, Any], system_prompt: str) -> dict[str, Any]:
    """Rough token estimate without calling the model (~4 chars/token)."""
    user = json.dumps(payload, ensure_ascii=False, default=str)
    chars = len(system_prompt) + len(user) + 200
    input_tokens = max(1, chars // 4)
    # Structured decisions are short
    output_tokens = 350
    cost = estimate_cost_usd(JUDGE_MODEL, input_tokens, output_tokens)
    return {
        "model": JUDGE_MODEL,
        "prompt_version": PROMPT_VERSION,
        "estimated_input_tokens": input_tokens,
        "estimated_output_tokens": output_tokens,
        "estimated_cost_usd": cost,
    }


def validate_judge_output(raw: dict[str, Any]) -> tuple[bool, str, dict[str, Any]]:
    """Validate structured judge JSON. Returns (ok, error, cleaned)."""
    if not isinstance(raw, dict):
        return False, "not_an_object", {}
    decision = str(raw.get("decision") or "").strip().upper()
    if decision not in VALID_DECISIONS:
        return False, f"invalid_decision:{decision!r}", {}
    accepted = raw.get("accepted_organisations")
    if accepted is None:
        accepted = []
    if not isinstance(accepted, list):
        return False, "accepted_organisations_not_list", {}
    cleaned_orgs: list[dict[str, Any]] = []
    for item in accepted:
        if not isinstance(item, dict):
            return False, "accepted_org_not_object", {}
        name = (item.get("organisation_name") or "").strip()
        if not name and decision != "UNCERTAIN":
            return False, "accepted_org_missing_name", {}
        if not name:
            continue
        supporting = (item.get("supporting_evidence") or "").strip()
        if decision != "UNCERTAIN" and len(supporting) < 3:
            return False, "accepted_org_missing_supporting_evidence", {}
        cleaned_orgs.append(
            {
                "organisation_name": name,
                "existing_organisation_id": item.get("existing_organisation_id"),
                "author_names": list(item.get("author_names") or []),
                "supporting_evidence": supporting,
            }
        )
    if decision in {"HTML", "OPENALEX", "BOTH"} and not cleaned_orgs:
        return False, "decision_requires_accepted_organisations", {}
    if decision == "UNCERTAIN" and cleaned_orgs:
        # Prefer empty accepted on UNCERTAIN; drop invented lists
        cleaned_orgs = []
    return True, "", {
        "decision": decision,
        "accepted_organisations": cleaned_orgs,
        "reason": str(raw.get("reason") or "").strip(),
        "unsupported_claims": list(raw.get("unsupported_claims") or []),
    }


def _literal_supported(name: str, supporting: str, payload: dict[str, Any]) -> bool:
    """True when the accepted name/evidence is anchored in supplied paper text/claims."""
    needle = (name or "").strip().casefold()
    support = (supporting or "").strip().casefold()
    if not needle or len(support) < 3:
        return False
    html_bits = [
        str(t).casefold()
        for t in (payload.get("html_affiliation_text") or [])
        if t
    ]
    claim_names = [
        str(n).casefold()
        for n in (
            ((payload.get("html_organisation_claims") or {}).get("org_names") or [])
            + ((payload.get("openalex") or {}).get("organisation_claims") or {}).get("org_names")
            or []
        )
        if n
    ]
    # Supporting quote must appear in HTML text, or the org name must appear in
    # HTML text / known claim names (not prestige, not free invention).
    if any(support in bit or bit in support for bit in html_bits if len(bit) >= 3):
        return True
    if any(needle in bit or bit in needle for bit in html_bits if len(bit) >= 3):
        return True
    if any(needle == c or needle in c or c in needle for c in claim_names if c):
        return True
    return False


def resolve_accepted_organisations(
    conn: Any,
    accepted: list[dict[str, Any]],
    *,
    payload: dict[str, Any] | None = None,
    compare: dict[str, Any] | None = None,
) -> list[dict[str, Any]]:
    """Map judge names to canonical IDs; drop claims not grounded in supplied evidence."""
    payload = payload or {}
    compare = compare or {}
    evaluated_ids = {
        int(x)
        for key in ("html_org_ids", "oa_org_ids")
        for x in (compare.get(key) or [])
        if x is not None
    }
    out: list[dict[str, Any]] = []
    for item in accepted:
        name = item["organisation_name"]
        supporting = item.get("supporting_evidence") or ""
        if not _literal_supported(name, supporting, payload):
            continue
        existing = item.get("existing_organisation_id")
        oid: int | None = None
        if existing is not None:
            try:
                oid = int(existing)
            except (TypeError, ValueError):
                oid = None
        if oid is None:
            res = resolve_local_organisation(conn, name)
            if res.get("organisation_id") is not None:
                oid = int(res["organisation_id"])
        # Prefer IDs that were part of the evaluated claim set when present.
        if oid is not None and evaluated_ids and oid not in evaluated_ids:
            # Allow only when the name is literally present in HTML evidence.
            html_bits = " ".join(str(t) for t in (payload.get("html_affiliation_text") or []))
            if name.casefold() not in html_bits.casefold() and supporting.casefold() not in html_bits.casefold():
                oid = None
        out.append({**item, "resolved_organisation_id": oid})
    return out


def run_judge(
    conn: Any,
    claims: dict[str, Any],
    compare: dict[str, Any],
    *,
    dry_run: bool = True,
    run_id: str | None = None,
    stage_run_id: str | None = None,
) -> dict[str, Any]:
    """Call LLM judge (or dry-run estimate). Never invents affiliations on failure."""
    system_prompt = read_prompt(STAGE_NAME, PROMPT_VERSION)
    payload = build_judge_payload(claims, compare)
    estimate = estimate_judge_tokens(payload, system_prompt)
    user_prompt = (
        "Paper affiliation disagreement. Decide using only the supplied evidence.\n\n"
        + json.dumps(payload, indent=2, ensure_ascii=False, default=str)
    )

    if dry_run:
        return {
            "ok": True,
            "dry_run": True,
            "judge_called": False,
            "payload": payload,
            "estimate": estimate,
            "decision": None,
            "accepted_organisations": [],
            "reason": "dry_run_no_llm_call",
        }

    llm = call_llm_logged(
        conn,
        model=JUDGE_MODEL,
        system_prompt=system_prompt,
        user_prompt=user_prompt,
        prompt_version=PROMPT_VERSION,
        stage_name=STAGE_NAME,
        temperature=0.0,
        max_tokens=1200,
        run_id=run_id,
        stage_run_id=stage_run_id,
        entity=f"paper:{claims['paper_id']}",
    )
    try:
        parsed = parse_json_object(llm.get("content") or "")
    except Exception as exc:  # noqa: BLE001
        return {
            "ok": False,
            "dry_run": False,
            "judge_called": True,
            "payload": payload,
            "estimate": estimate,
            "error": f"parse_failed:{exc}",
            "decision": "UNCERTAIN",
            "accepted_organisations": [],
            "reason": "invalid_model_output",
            "llm": {k: llm.get(k) for k in ("input_tokens", "output_tokens", "estimated_cost", "raw_path")},
        }

    ok, err, cleaned = validate_judge_output(parsed)
    if not ok:
        return {
            "ok": False,
            "dry_run": False,
            "judge_called": True,
            "payload": payload,
            "estimate": estimate,
            "error": err,
            "decision": "UNCERTAIN",
            "accepted_organisations": [],
            "reason": f"validation_failed:{err}",
            "raw_parsed": parsed,
            "llm": {k: llm.get(k) for k in ("input_tokens", "output_tokens", "estimated_cost", "raw_path")},
        }

    resolved = resolve_accepted_organisations(
        conn,
        cleaned["accepted_organisations"],
        payload=payload,
        compare=compare,
    )
    # Keep only evidence-grounded claims (supporting_evidence already required).
    grounded = [r for r in resolved if r.get("supporting_evidence")]
    decision = cleaned["decision"]
    if decision in {"HTML", "OPENALEX", "BOTH"} and not any(
        r.get("resolved_organisation_id") is not None for r in grounded
    ):
        # Decision without any grounded org → treat as uncertain; do not invent.
        decision = "UNCERTAIN"
        grounded = []
        reason = "no_grounded_accepted_organisations"
    else:
        reason = cleaned["reason"]
    return {
        "ok": True,
        "dry_run": False,
        "judge_called": True,
        "payload": payload,
        "estimate": estimate,
        "decision": decision,
        "accepted_organisations": grounded,
        "reason": reason,
        "unsupported_claims": cleaned["unsupported_claims"],
        "llm": {
            "model": JUDGE_MODEL,
            "prompt_version": PROMPT_VERSION,
            "input_tokens": llm.get("input_tokens"),
            "output_tokens": llm.get("output_tokens"),
            "estimated_cost": llm.get("estimated_cost"),
            "raw_path": llm.get("raw_path"),
        },
    }
