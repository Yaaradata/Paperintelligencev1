"""Persist affiliation judge outcomes without mutating original HTML/OA evidence."""

from __future__ import annotations

import json
from typing import Any

from paper_intelligence.author_affiliation.repository import insert_affiliation, list_paper_authors
from paper_intelligence.author_affiliation.verify.judge_llm import JUDGE_MODEL, PROMPT_VERSION

JUDGE_VERSION_DEFAULT = "html-oa-judge-v001"
EVIDENCE_TYPE = "llm_affiliation_judge"
EVIDENCE_SOURCE = "affiliation_judge.v001"
STAGE_VERSION = "judge-v001"
POLICY_VERSION = "v001"


def get_existing_judgment(
    conn: Any, paper_id: int, *, judge_version: str = JUDGE_VERSION_DEFAULT
) -> dict[str, Any] | None:
    row = conn.execute(
        """
        SELECT * FROM paper_intelligence.affiliation_judgments
        WHERE judge_version = %s AND paper_id = %s
        """,
        (judge_version, int(paper_id)),
    ).fetchone()
    return dict(row) if row else None


def upsert_judgment(
    conn: Any,
    *,
    paper_id: int,
    compare_status: str,
    decision: str | None,
    judge_called: bool,
    result_json: dict[str, Any],
    reason: str | None = None,
    accepted_organisation_ids: list[int] | None = None,
    rejected_organisation_ids: list[int] | None = None,
    model: str | None = None,
    prompt_version: str | None = None,
    estimated_cost_usd: float | None = None,
    input_tokens: int | None = None,
    output_tokens: int | None = None,
    judge_version: str = JUDGE_VERSION_DEFAULT,
) -> int:
    ids = accepted_organisation_ids or []
    rejected = rejected_organisation_ids or []
    row = conn.execute(
        """
        INSERT INTO paper_intelligence.affiliation_judgments
            (paper_id, judge_version, compare_status, decision, judge_called,
             model, prompt_version, accepted_organisation_ids, rejected_organisation_ids,
             result_json, reason,
             estimated_cost_usd, input_tokens, output_tokens)
        VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s::jsonb,%s,%s,%s,%s)
        ON CONFLICT (judge_version, paper_id) DO UPDATE SET
            compare_status = EXCLUDED.compare_status,
            decision = EXCLUDED.decision,
            judge_called = EXCLUDED.judge_called,
            model = EXCLUDED.model,
            prompt_version = EXCLUDED.prompt_version,
            accepted_organisation_ids = EXCLUDED.accepted_organisation_ids,
            rejected_organisation_ids = EXCLUDED.rejected_organisation_ids,
            result_json = EXCLUDED.result_json,
            reason = EXCLUDED.reason,
            estimated_cost_usd = EXCLUDED.estimated_cost_usd,
            input_tokens = EXCLUDED.input_tokens,
            output_tokens = EXCLUDED.output_tokens
        RETURNING judgment_id
        """,
        (
            int(paper_id),
            judge_version,
            compare_status,
            decision,
            bool(judge_called),
            model,
            prompt_version,
            ids,
            rejected,
            json.dumps(result_json, default=str),
            reason,
            estimated_cost_usd,
            input_tokens,
            output_tokens,
        ),
    ).fetchone()
    conn.commit()
    return int(row["judgment_id"])


def persist_accepted_affiliations(
    conn: Any,
    *,
    paper_id: int,
    accepted: list[dict[str, Any]],
    decision: str,
    reason: str | None,
    run_id: str | None = None,
) -> list[int]:
    """Append judge-accepted org evidence; does not delete HTML/OA rows.

    Fans out to all paper authors as paper-level attribution (existing pattern).
    Only writes rows with a resolved organisation_id.
    """
    authors = list_paper_authors(conn, paper_id)
    if not authors:
        return []
    inserted: list[int] = []
    for item in accepted:
        oid = item.get("resolved_organisation_id")
        if oid is None:
            continue
        name = item.get("organisation_name") or ""
        evidence_value = (item.get("supporting_evidence") or name)[:2000]
        raw = f"judge:{decision}:{name}"
        for author in authors:
            # If judge listed specific authors, prefer those; else all authors.
            wanted = [n.casefold() for n in (item.get("author_names") or []) if n]
            if wanted and (author.get("raw_name") or "").casefold() not in wanted:
                # still allow substring match
                an = (author.get("raw_name") or "").casefold()
                if not any(w in an or an in w for w in wanted):
                    continue
            new_id = insert_affiliation(
                conn,
                content_item_id=int(paper_id),
                paper_author_id=int(author["id"]),
                organisation_id=int(oid),
                raw_affiliation=raw,
                relationship_scope="author" if wanted else "paper",
                evidence_type=EVIDENCE_TYPE,
                evidence_source=EVIDENCE_SOURCE,
                evidence_value=evidence_value,
                confidence=0.88,
                run_id=run_id,
                stage_version=STAGE_VERSION,
                policy_version=POLICY_VERSION,
            )
            if new_id is not None:
                inserted.append(int(new_id))
    conn.commit()
    return inserted


def auto_decision_for_compare(compare_status: str) -> str:
    if compare_status == "exact_match":
        return "AUTO_AGREE"
    if compare_status == "html_only":
        return "AUTO_HTML"
    if compare_status in ("openalex_only", "neither", "oa_unavailable"):
        return "AUTO_SKIP"
    return "UNCERTAIN"
