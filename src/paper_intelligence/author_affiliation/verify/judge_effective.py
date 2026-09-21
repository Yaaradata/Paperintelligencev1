"""Judge accept/reject → effective affiliation set for downstream adjudication.

Preserves original HTML/OpenAlex evidence rows. Exclusion is applied at read
time for resolved judge decisions (HTML | OPENALEX | BOTH) only.
"""

from __future__ import annotations

from typing import Any, Iterable, Sequence

# Decisions that establish an explicit accept/reject set over evaluated claims.
RESOLVED_JUDGE_DECISIONS = frozenset({"HTML", "OPENALEX", "BOTH"})


def evaluated_organisation_ids(compare: dict[str, Any] | None) -> set[int]:
    """Organisation IDs the judge was asked to choose among (HTML ∪ OpenAlex)."""
    if not compare:
        return set()
    out: set[int] = set()
    for key in ("html_org_ids", "oa_org_ids"):
        for raw in compare.get(key) or []:
            try:
                out.add(int(raw))
            except (TypeError, ValueError):
                continue
    return out


def compute_rejected_organisation_ids(
    *,
    compare: dict[str, Any] | None,
    accepted_organisation_ids: Iterable[int],
    unsupported_claims: Sequence[Any] | None = None,
    name_to_id: dict[str, int] | None = None,
    decision: str | None = None,
) -> list[int]:
    """Rejected = evaluated claims not accepted.

    Only organisations that were part of the HTML/OA comparison (or named in
    unsupported_claims and mapped into that evaluated set) are rejected.
    Affiliations the judge never saw are left alone.

    If a resolved decision has an empty accepted set, apply no exclusions
    (fail open — do not wipe the paper's affiliations).
    """
    decision_u = str(decision or "").strip().upper()
    accepted = {int(x) for x in accepted_organisation_ids}
    if decision_u in RESOLVED_JUDGE_DECISIONS and not accepted:
        return []

    evaluated = evaluated_organisation_ids(compare)
    rejected = set(evaluated) - accepted

    # Map unsupported claim strings onto evaluated IDs when possible.
    lookup = {k.casefold(): v for k, v in (name_to_id or {}).items()}
    for claim in unsupported_claims or []:
        text = ""
        if isinstance(claim, dict):
            text = str(claim.get("organisation_name") or claim.get("name") or "")
            raw_id = claim.get("organisation_id") or claim.get("existing_organisation_id")
            if raw_id is not None:
                try:
                    oid = int(raw_id)
                except (TypeError, ValueError):
                    oid = None
                if oid is not None and oid in evaluated and oid not in accepted:
                    rejected.add(oid)
                    continue
        else:
            text = str(claim or "")
        key = text.strip().casefold()
        if not key:
            continue
        oid = lookup.get(key)
        if oid is not None and oid in evaluated and oid not in accepted:
            rejected.add(oid)

    return sorted(rejected)


def build_name_to_id_from_compare(compare: dict[str, Any] | None) -> dict[str, int]:
    """Best-effort name→id map from compare claim lists (parallel arrays)."""
    if not compare:
        return {}
    mapping: dict[str, int] = {}
    for names_key, ids_key in (
        ("html_org_names", "html_org_ids"),
        ("oa_org_names", "oa_org_ids"),
    ):
        names = list(compare.get(names_key) or [])
        ids = list(compare.get(ids_key) or [])
        for i, name in enumerate(names):
            if i >= len(ids):
                break
            try:
                oid = int(ids[i])
            except (TypeError, ValueError):
                continue
            key = str(name or "").strip().casefold()
            if key:
                mapping[key] = oid
    return mapping


def should_exclude_rejected(decision: str | None, *, judge_called: bool) -> bool:
    return bool(judge_called) and str(decision or "").strip().upper() in RESOLVED_JUDGE_DECISIONS


def filter_affiliation_rows(
    rows: Sequence[dict[str, Any]],
    *,
    rejected_organisation_ids: Iterable[int] | None,
    decision: str | None = None,
    judge_called: bool = False,
) -> list[dict[str, Any]]:
    """Drop explicitly rejected org IDs from the effective evidence set.

    Does not mutate or delete stored rows. Non-resolved / uncertain judgments
    apply no exclusion. Orgs not in the rejected set are kept even if the judge
    never mentioned them.
    """
    if not should_exclude_rejected(decision, judge_called=judge_called):
        return list(rows)
    rejected = {int(x) for x in (rejected_organisation_ids or [])}
    if not rejected:
        return list(rows)
    out: list[dict[str, Any]] = []
    for row in rows:
        oid = row.get("organisation_id")
        if oid is None:
            out.append(row)
            continue
        try:
            if int(oid) in rejected:
                continue
        except (TypeError, ValueError):
            out.append(row)
            continue
        out.append(row)
    return out


def effective_organisation_ids(
    rows: Sequence[dict[str, Any]],
    *,
    rejected_organisation_ids: Iterable[int] | None = None,
    decision: str | None = None,
    judge_called: bool = False,
    min_confidence: float = 0.6,
) -> list[int]:
    """Distinct organisation IDs that survive confidence + reject filters."""
    filtered = filter_affiliation_rows(
        rows,
        rejected_organisation_ids=rejected_organisation_ids,
        decision=decision,
        judge_called=judge_called,
    )
    ids: set[int] = set()
    for row in filtered:
        oid = row.get("organisation_id")
        if oid is None:
            continue
        conf = row.get("confidence")
        conf_f = float(conf) if conf is not None else 1.0
        if conf_f < min_confidence:
            continue
        try:
            ids.add(int(oid))
        except (TypeError, ValueError):
            continue
    return sorted(ids)


def load_judgment_exclusions(
    conn: Any,
    paper_ids: Sequence[int],
    *,
    judge_version: str,
) -> dict[int, dict[str, Any]]:
    """paper_id → {decision, judge_called, rejected_organisation_ids, accepted_organisation_ids}."""
    if not paper_ids:
        return {}
    sql = """
        SELECT paper_id, decision, judge_called,
               COALESCE(accepted_organisation_ids, '{}') AS accepted_organisation_ids,
               COALESCE(rejected_organisation_ids, '{}') AS rejected_organisation_ids
        FROM paper_intelligence.affiliation_judgments
        WHERE judge_version = %s AND paper_id = ANY(%s)
    """
    params = (judge_version, list(paper_ids))
    if hasattr(conn, "cursor"):
        with conn.cursor() as cur:
            cur.execute(sql, params)
            rows = cur.fetchall()
    else:
        rows = conn.execute(sql, params).fetchall()
    out: dict[int, dict[str, Any]] = {}
    for row in rows:
        # Support both dict_row and tuple access.
        if isinstance(row, dict):
            pid = int(row["paper_id"])
            decision = row.get("decision")
            judge_called = bool(row.get("judge_called"))
            accepted = list(row.get("accepted_organisation_ids") or [])
            rejected = list(row.get("rejected_organisation_ids") or [])
        else:
            pid = int(row[0])
            decision = row[1]
            judge_called = bool(row[2])
            accepted = list(row[3] or [])
            rejected = list(row[4] or [])
        out[pid] = {
            "decision": decision,
            "judge_called": judge_called,
            "accepted_organisation_ids": accepted,
            "rejected_organisation_ids": rejected,
        }
    return out
