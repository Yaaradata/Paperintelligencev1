#!/usr/bin/env python3
"""Newsletter TECH/PRODUCT selection via OpenRouter LLM for any date window.

Editorial/evaluation only. Does not change scoring, affiliation, or adjudication.

Example:
  PYTHONPATH=src python3 scripts/select_newsletter.py \\
    --from 2026-08-01 --until 2026-08-31 \\
    --model anthropic/claude-opus-5 \\
    --reasoning-effort medium \\
    --output-dir reports/editorial

Requires OPENROUTER_API_KEY. Candidate pool is loaded from DB (or --pool-json).
"""

from __future__ import annotations

import argparse
import csv
import json
import sys
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from paper_intelligence.common.llm_stage import parse_json_object, strip_json_fences
from paper_intelligence.common.config import PI_USE_PAPERS_CATALOG
from paper_intelligence.db import connect
from paper_intelligence.editorial.seats import newsletter_rubric_body
from paper_intelligence.openrouter import LLMRequest, complete

DEFAULT_MODEL = "anthropic/claude-opus-5"
DEFAULT_REASONING = "medium"
PROMPT_VERSION = "newsletter_select_v002"
SEATS_POLICY_VERSION = "v001"

SYSTEM_PROMPT = """\
You are the paper-selection editor for a weekly AI newsletter for senior \
technology and product professionals.

Your job is selection, not summarisation.

Choose exactly TWO papers for publication from the supplied shortlist:
- one TECH pick
- one PRODUCT pick

Also identify one runner-up for each seat.

The four selected content_item_id values must be different.

Return ONLY a single JSON object matching the schema in the user message. \
No markdown fences, no preamble.
"""

USER_RUBRIC_TAIL = """\
<candidate_provenance>
Interpret candidate fields as follows:

quality_score:
Generated blind to authors and organisations. It measures the underlying
contribution.

final_score:
Adds a small capped organisation signal. Treat differences below ~0.3 as noise.

organisations:
Resolved using verified evidence. Organisation prestige must NOT be used
to choose between papers at this stage.

audiences, domain, subdomains, application_domain:
Cheap classifier outputs over a closed vocabulary. Treat them as hints.
If they conflict with the title, abstract, or stronger evidence, trust the
stronger evidence.

so_what:
Interpretation from the quality stage.

reason_not_higher:
Known limitations. Give this substantial weight before selecting a paper.
</candidate_provenance>

<evaluation>
Evaluate every candidate against:
1. Decision impact
2. Evidence strength
3. Enterprise transferability
4. Actionability
5. Explainability to the intended reader

Use these as qualitative reasoning dimensions only.
Do NOT calculate a composite numerical score.
Internally think of each dimension as strong / medium / weak.
Do not output those internal ratings.

quality_score and final_score are supporting signals only.
They may be used as tie-breakers but must not determine the winner.

Prefer a narrower, well-supported result over a sweeping claim with weaker evidence.
Do not turn correlation, simulation, benchmarks, or laboratory evidence into
production recommendations unless the supplied evidence supports that translation.
Do not select TECH and PRODUCT winners that deliver substantially the same
editorial lesson.
</evaluation>

<output_guidance>
why_this_paper:
State the decision the paper should cause the reader to reconsider.
Do not merely summarise the abstract.

action_for_reader:
Give one concrete test, review, question, or measurement the reader could
trigger with an existing team. Keep the action proportionate to the evidence.

talking_point:
One accurate, repeatable sentence capturing the practical insight.

caveat:
State the most decision-relevant limitation supported by reason_not_higher or
other supplied evidence.

why_not_runner_up:
State the decisive reason the winner is stronger for THIS seat.

editor_warning:
Use an empty string when both winners genuinely clear the application gate.
Otherwise state which seat was weak and why.
</output_guidance>
"""


def build_user_rubric(*, seats_version: str = SEATS_POLICY_VERSION) -> str:
    """Assemble USER_RUBRIC with seats from the shared policy file."""
    return newsletter_rubric_body(seats_version) + "\n\n" + USER_RUBRIC_TAIL


# Backward-compatible name for importers / dry-run inspection.
USER_RUBRIC = build_user_rubric()

OUTPUT_SCHEMA = """\
Return JSON with this exact shape:
{
  "editor_warning": "",
  "tech": {
    "content_item_id": 0,
    "arxiv_id": "",
    "title": "",
    "canonical_url": "",
    "why_this_paper": "",
    "decision_it_changes": "",
    "action_for_reader": "",
    "talking_point": "",
    "caveat": "",
    "why_not_runner_up": ""
  },
  "tech_runner_up": {
    "content_item_id": 0,
    "arxiv_id": "",
    "title": "",
    "canonical_url": "",
    "why_this_paper": "",
    "decision_it_changes": "",
    "action_for_reader": "",
    "talking_point": "",
    "caveat": ""
  },
  "product": { ... same fields as tech ... },
  "product_runner_up": { ... same fields as tech_runner_up ... },
  "cross_check": {
    "tech_product_ids_differ": true,
    "four_ids_unique": true,
    "prestige_not_used_as_selector": true,
    "application_gate_cleared": true,
    "notes": ""
  }
}

Rules:
- All four content_item_id values must be distinct and must appear in the shortlist.
- Prefer papers that clear the application gate.
- Do not choose primarily for organisation prestige or Hugging Face status.
"""


CANDIDATE_SQL_RADAR = """
WITH window_papers AS (
  SELECT ci.id AS content_item_id, ci.title, ci.summary AS abstract, ci.status,
         ci.published_at, ci.canonical_url,
         pm.arxiv_id, pm.doi, pm.abstract AS pm_abstract
  FROM research_radar.content_items ci
  JOIN research_radar.paper_metadata pm ON pm.content_id = ci.id
  WHERE ci.published_at >= %s::timestamptz
    AND ci.published_at < (%s::timestamptz + interval '1 day')
),
quality AS (
  SELECT DISTINCT ON (r.content_item_id)
         r.content_item_id, r.result_json
  FROM paper_intelligence.paper_classification_results r
  JOIN window_papers w ON w.content_item_id = r.content_item_id
  WHERE r.task_type = 'quality'
  ORDER BY r.content_item_id, r.created_at DESC
),
orgs AS (
  SELECT a.content_item_id,
         jsonb_agg(DISTINCT jsonb_build_object(
           'canonical_name', o.canonical_name,
           'is_org_of_interest', o.is_org_of_interest,
           'confidence', a.confidence,
           'evidence_type', a.evidence_type
         )) FILTER (
           WHERE o.id IS NOT NULL AND coalesce(a.confidence, 1) >= 0.6
         ) AS organisations
  FROM paper_intelligence.paper_author_affiliations a
  JOIN paper_intelligence.organisations o ON o.id = a.organisation_id
  JOIN window_papers w ON w.content_item_id = a.content_item_id
  GROUP BY a.content_item_id
)
SELECT w.*,
       c.final_score, c.quality_score, c.screen_score, c.org_boost,
       c.audiences, c.domain, c.subdomains, c.application_domains,
       c.quality_status, c.hf_featured, c.hf_featured_date, c.hf_upvotes,
       c.affiliation_resolution_status, top.canonical_name AS top_organisation,
       q.result_json AS quality_json,
       o.organisations
FROM window_papers w
JOIN quality q ON q.content_item_id = w.content_item_id
LEFT JOIN paper_intelligence.paper_intelligence_current c
       ON c.content_item_id = w.content_item_id
LEFT JOIN paper_intelligence.organisations top ON top.id = c.top_organisation_id
LEFT JOIN orgs o ON o.content_item_id = w.content_item_id
WHERE c.final_score IS NOT NULL OR c.quality_status = 'scored'
ORDER BY c.final_score DESC NULLS LAST, c.quality_score DESC NULLS LAST
"""

CANDIDATE_SQL_PI = """
WITH window_papers AS (
  SELECT p.paper_id AS content_item_id, p.title,
         COALESCE(p.abstract, p.summary) AS abstract,
         lr.decision AS status,
         p.published_at, p.canonical_url,
         p.arxiv_id, p.doi, p.abstract AS pm_abstract
  FROM paper_intelligence.papers p
  LEFT JOIN LATERAL (
    SELECT decision FROM paper_intelligence.paper_relevance_results r
    WHERE r.paper_id = p.paper_id
    ORDER BY r.created_at DESC, r.relevance_id DESC
    LIMIT 1
  ) lr ON TRUE
  WHERE p.published_at >= %s::timestamptz
    AND p.published_at < (%s::timestamptz + interval '1 day')
),
quality AS (
  SELECT DISTINCT ON (r.content_item_id)
         r.content_item_id, r.result_json
  FROM paper_intelligence.paper_classification_results r
  JOIN window_papers w ON w.content_item_id = r.content_item_id
  WHERE r.task_type = 'quality'
  ORDER BY r.content_item_id, r.created_at DESC
),
orgs AS (
  SELECT a.content_item_id,
         jsonb_agg(DISTINCT jsonb_build_object(
           'canonical_name', o.canonical_name,
           'is_org_of_interest', o.is_org_of_interest,
           'confidence', a.confidence,
           'evidence_type', a.evidence_type
         )) FILTER (
           WHERE o.id IS NOT NULL AND coalesce(a.confidence, 1) >= 0.6
         ) AS organisations
  FROM paper_intelligence.paper_author_affiliations a
  JOIN paper_intelligence.organisations o ON o.id = a.organisation_id
  JOIN window_papers w ON w.content_item_id = a.content_item_id
  GROUP BY a.content_item_id
)
SELECT w.*,
       c.final_score, c.quality_score, c.screen_score, c.org_boost,
       c.audiences, c.domain, c.subdomains, c.application_domains,
       c.quality_status, c.hf_featured, c.hf_featured_date, c.hf_upvotes,
       c.affiliation_resolution_status, top.canonical_name AS top_organisation,
       q.result_json AS quality_json,
       o.organisations
FROM window_papers w
JOIN quality q ON q.content_item_id = w.content_item_id
LEFT JOIN paper_intelligence.paper_intelligence_current c
       ON c.content_item_id = w.content_item_id
LEFT JOIN paper_intelligence.organisations top ON top.id = c.top_organisation_id
LEFT JOIN orgs o ON o.content_item_id = w.content_item_id
WHERE c.final_score IS NOT NULL OR c.quality_status = 'scored'
ORDER BY c.final_score DESC NULLS LAST, c.quality_score DESC NULLS LAST
"""

CANDIDATE_SQL = CANDIDATE_SQL_RADAR


def window_label(date_from: date, date_until: date) -> str:
    """Stable filename stem for a date window, e.g. 2026-08-01_to_2026-08-31."""
    return f"{date_from.isoformat()}_to_{date_until.isoformat()}"


def _parse_day(value: str) -> date:
    return date.fromisoformat(value[:10])


def _quality_fields(qj: Any) -> dict[str, Any]:
    if not qj:
        return {}
    if isinstance(qj, str):
        qj = json.loads(qj)
    out: dict[str, Any] = {}
    if not isinstance(qj, dict):
        return out
    for key in ("so_what", "reason_not_higher", "summary"):
        if key in qj:
            out[key] = qj[key]
    return out


def _dedupe_orgs(raw: Any) -> list[dict[str, Any]]:
    if not raw:
        return []
    if isinstance(raw, str):
        raw = json.loads(raw)
    seen: set[str] = set()
    out: list[dict[str, Any]] = []
    for row in raw:
        name = (row or {}).get("canonical_name")
        if not name or name in seen:
            continue
        seen.add(name)
        out.append(row)
    return out


def load_candidates_from_db(
    conn: Any, date_from: date, date_until: date, *, limit: int | None = None
) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    with conn.cursor() as cur:
        if PI_USE_PAPERS_CATALOG:
            cur.execute(
                """
                SELECT count(*) AS total,
                       count(*) FILTER (WHERE lr.decision = 'keep') AS relevant
                FROM paper_intelligence.papers p
                LEFT JOIN LATERAL (
                  SELECT decision FROM paper_intelligence.paper_relevance_results r
                  WHERE r.paper_id = p.paper_id
                  ORDER BY r.created_at DESC, r.relevance_id DESC
                  LIMIT 1
                ) lr ON TRUE
                WHERE p.published_at >= %s::timestamptz
                  AND p.published_at < (%s::timestamptz + interval '1 day')
                """,
                (date_from.isoformat(), date_until.isoformat()),
            )
            base = dict(cur.fetchone())
            sql = CANDIDATE_SQL_PI + (" LIMIT %s" if limit else "")
        else:
            cur.execute(
                """
                SELECT count(*) total,
                       count(*) FILTER (WHERE status = 'RELEVANT') relevant
                FROM research_radar.content_items
                WHERE published_at >= %s::timestamptz
                  AND published_at < (%s::timestamptz + interval '1 day')
                """,
                (date_from.isoformat(), date_until.isoformat()),
            )
            base = dict(cur.fetchone())
            sql = CANDIDATE_SQL_RADAR + (" LIMIT %s" if limit else "")
        params: tuple[Any, ...] = (date_from.isoformat(), date_until.isoformat())
        if limit:
            params = (*params, int(limit))
        cur.execute(sql, params)
        rows = [dict(r) for r in cur.fetchall()]

    candidates: list[dict[str, Any]] = []
    for row in rows:
        qf = _quality_fields(row.get("quality_json"))
        abstract = row.get("pm_abstract") or row.get("abstract") or ""
        item = {
            "content_item_id": int(row["content_item_id"]),
            "arxiv_id": row.get("arxiv_id"),
            "doi": row.get("doi"),
            "canonical_url": row.get("canonical_url")
            or (
                f"https://arxiv.org/abs/{row['arxiv_id']}" if row.get("arxiv_id") else None
            ),
            "title": row.get("title"),
            "abstract": (abstract or "")[:2500],
            "published_at": row["published_at"].isoformat() if row.get("published_at") else None,
            "status": row.get("status"),
            "quality_status": row.get("quality_status"),
            "quality_score": float(row["quality_score"]) if row.get("quality_score") is not None else None,
            "final_score": float(row["final_score"]) if row.get("final_score") is not None else None,
            "screen_score": float(row["screen_score"]) if row.get("screen_score") is not None else None,
            "org_boost": float(row["org_boost"]) if row.get("org_boost") is not None else None,
            "audiences": row.get("audiences"),
            "domain": row.get("domain"),
            "subdomains": row.get("subdomains"),
            "application_domains": row.get("application_domains"),
            "so_what": qf.get("so_what"),
            "reason_not_higher": qf.get("reason_not_higher"),
            "organisations": _dedupe_orgs(row.get("organisations")),
            "top_organisation": row.get("top_organisation"),
            "hf_featured": bool(row.get("hf_featured")) if row.get("hf_featured") is not None else False,
            "hf_featured_date": str(row["hf_featured_date"]) if row.get("hf_featured_date") else None,
            "hf_upvotes": row.get("hf_upvotes"),
            "eligible": True,
        }
        candidates.append(item)

    stats = {
        "total_window_papers": base["total"],
        "relevant_papers": base["relevant"],
        "papers_with_quality_result": len(candidates),
        "papers_eligible_for_editorial_selection": len(candidates),
        "date_from": date_from.isoformat(),
        "date_until": date_until.isoformat(),
    }
    return stats, candidates


def load_candidates_from_pool_json(path: Path) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    stats = payload.get("stats") or {}
    candidates = [
        c
        for c in (payload.get("candidates") or [])
        if c.get("eligible") or c.get("final_score") is not None
    ]
    return stats, candidates


def shortlist_for_prompt(candidates: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Compact payload for the model (drop bulky unused fields)."""
    out: list[dict[str, Any]] = []
    for c in candidates:
        out.append(
            {
                "content_item_id": c["content_item_id"],
                "arxiv_id": c.get("arxiv_id"),
                "canonical_url": c.get("canonical_url"),
                "title": c.get("title"),
                "abstract": c.get("abstract"),
                "published_at": c.get("published_at"),
                "quality_score": c.get("quality_score"),
                "final_score": c.get("final_score"),
                "audiences": c.get("audiences"),
                "domain": c.get("domain"),
                "subdomains": c.get("subdomains"),
                "application_domains": c.get("application_domains"),
                "so_what": c.get("so_what"),
                "reason_not_higher": c.get("reason_not_higher"),
                "organisations": [
                    {
                        "canonical_name": o.get("canonical_name"),
                        "is_org_of_interest": o.get("is_org_of_interest"),
                    }
                    for o in (c.get("organisations") or [])[:6]
                ],
                "top_organisation": c.get("top_organisation"),
                "hf_featured": c.get("hf_featured"),
            }
        )
    return out


def write_pool_files(
    output_dir: Path,
    stats: dict[str, Any],
    candidates: list[dict[str, Any]],
    *,
    label: str,
) -> tuple[Path, Path]:
    output_dir.mkdir(parents=True, exist_ok=True)
    payload = {"stats": stats, "candidates": candidates}
    json_path = output_dir / f"{label}_candidate_pool.json"
    csv_path = output_dir / f"{label}_candidate_pool.csv"
    json_path.write_text(json.dumps(payload, indent=2, default=str) + "\n", encoding="utf-8")
    fields = [
        "content_item_id",
        "arxiv_id",
        "title",
        "published_at",
        "quality_score",
        "final_score",
        "domain",
        "audiences",
        "application_domains",
        "top_organisation",
        "hf_featured",
        "canonical_url",
    ]
    with csv_path.open("w", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(fh, fieldnames=fields, extrasaction="ignore")
        writer.writeheader()
        for c in candidates:
            row = {k: c.get(k) for k in fields}
            row["audiences"] = json.dumps(c.get("audiences"), default=str)
            row["application_domains"] = json.dumps(c.get("application_domains"), default=str)
            writer.writerow(row)
    return json_path, csv_path


def render_markdown(selection: dict[str, Any], *, model: str, stats: dict[str, Any]) -> str:
    def block(label: str, node: dict[str, Any]) -> str:
        return (
            f"### {label}\n"
            f"- **{node.get('title')}**\n"
            f"- ID `{node.get('content_item_id')}` · arXiv `{node.get('arxiv_id')}` · "
            f"[link]({node.get('canonical_url')})\n"
            f"- **Why:** {node.get('why_this_paper')}\n"
            f"- **Decision:** {node.get('decision_it_changes')}\n"
            f"- **Action:** {node.get('action_for_reader')}\n"
            f"- **Talking point:** {node.get('talking_point')}\n"
            f"- **Caveat:** {node.get('caveat')}\n"
            + (
                f"- **Why not runner-up:** {node.get('why_not_runner_up')}\n"
                if node.get("why_not_runner_up")
                else ""
            )
        )

    return (
        f"# Newsletter selection (LLM)\n\n"
        f"- model: `{model}`\n"
        f"- prompt_version: `{PROMPT_VERSION}`\n"
        f"- eligible: {stats.get('papers_eligible_for_editorial_selection')}\n"
        f"- window: {stats.get('date_from')} → {stats.get('date_until')}\n"
        f"- editor_warning: `{selection.get('editor_warning') or '(none)'}`\n\n"
        f"## TECH\n{block('Winner', selection['tech'])}\n"
        f"{block('Runner-up', selection['tech_runner_up'])}\n"
        f"## PRODUCT\n{block('Winner', selection['product'])}\n"
        f"{block('Runner-up', selection['product_runner_up'])}\n"
    )


def validate_selection(selection: dict[str, Any], allowed_ids: set[int]) -> list[str]:
    errors: list[str] = []
    keys = ("tech", "tech_runner_up", "product", "product_runner_up")
    ids: list[int] = []
    for key in keys:
        node = selection.get(key) or {}
        try:
            cid = int(node["content_item_id"])
        except Exception:  # noqa: BLE001
            errors.append(f"{key}: missing content_item_id")
            continue
        if cid not in allowed_ids:
            errors.append(f"{key}: content_item_id {cid} not in shortlist")
        ids.append(cid)
    if len(ids) == 4 and len(set(ids)) != 4:
        errors.append(f"four IDs are not unique: {ids}")
    if selection.get("tech", {}).get("content_item_id") == selection.get("product", {}).get(
        "content_item_id"
    ):
        errors.append("TECH and PRODUCT winners must differ")
    return errors


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="LLM newsletter selection for any --from/--until date window"
    )
    parser.add_argument("--from", dest="date_from", required=True, help="Inclusive start date YYYY-MM-DD")
    parser.add_argument("--until", dest="date_until", required=True, help="Inclusive end date YYYY-MM-DD")
    parser.add_argument("--model", default=DEFAULT_MODEL)
    parser.add_argument("--reasoning-effort", default=DEFAULT_REASONING)
    parser.add_argument("--temperature", type=float, default=0.2)
    parser.add_argument("--max-tokens", type=int, default=8000)
    parser.add_argument("--limit", type=int, default=None, help="Optional cap on shortlist size")
    parser.add_argument(
        "--pool-json",
        default=None,
        help="Optional existing candidate pool JSON (skip DB rebuild)",
    )
    parser.add_argument("--output-dir", default=str(ROOT / "reports" / "editorial"))
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Build pool + prompt only; do not call OpenRouter",
    )
    args = parser.parse_args(argv)

    date_from = _parse_day(args.date_from)
    date_until = _parse_day(args.date_until)
    if date_until < date_from:
        print("--until must be on or after --from", file=sys.stderr)
        return 2

    label = window_label(date_from, date_until)
    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    if args.pool_json:
        stats, candidates = load_candidates_from_pool_json(Path(args.pool_json))
        stats = {
            **stats,
            "date_from": stats.get("date_from") or date_from.isoformat(),
            "date_until": stats.get("date_until") or date_until.isoformat(),
        }
        if args.limit:
            candidates = candidates[: args.limit]
            stats["papers_eligible_for_editorial_selection"] = len(candidates)
    else:
        with connect() as conn:
            stats, candidates = load_candidates_from_db(
                conn, date_from, date_until, limit=args.limit
            )

    pool_json, pool_csv = write_pool_files(output_dir, stats, candidates, label=label)

    print("=== CANDIDATE POOL ===", flush=True)
    print(f"window: {date_from.isoformat()} → {date_until.isoformat()}", flush=True)
    print(f"total window papers: {stats.get('total_window_papers')}", flush=True)
    print(f"relevant papers: {stats.get('relevant_papers')}", flush=True)
    print(f"papers with quality result: {stats.get('papers_with_quality_result')}", flush=True)
    print(
        f"papers eligible for editorial selection: "
        f"{stats.get('papers_eligible_for_editorial_selection')}",
        flush=True,
    )
    print(f"wrote {pool_json}", flush=True)
    print(f"wrote {pool_csv}", flush=True)

    if not candidates:
        print("No eligible candidates; aborting.", file=sys.stderr)
        return 2

    shortlist = shortlist_for_prompt(candidates)
    user_prompt = (
        f"<selection_window>\n"
        f"date_from: {date_from.isoformat()}\n"
        f"date_until: {date_until.isoformat()}\n"
        f"Select from papers published in this inclusive window only.\n"
        f"</selection_window>\n\n"
        + build_user_rubric()
        + "\n"
        + OUTPUT_SCHEMA
        + "\n\n<shortlist>\n"
        + json.dumps(shortlist, indent=2, default=str)
        + "\n</shortlist>\n"
    )
    prompt_path = output_dir / f"{label}_newsletter_prompt_user.txt"
    prompt_path.write_text(user_prompt, encoding="utf-8")

    if args.dry_run:
        print(f"dry-run: wrote pool + prompt under {output_dir}", flush=True)
        print(f"wrote {prompt_path}", flush=True)
        return 0

    print(f"calling OpenRouter model={args.model} reasoning={args.reasoning_effort}", flush=True)
    response = complete(
        LLMRequest(
            model=args.model,
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": user_prompt},
            ],
            prompt_version=PROMPT_VERSION,
            temperature=args.temperature,
            max_tokens=args.max_tokens,
            reasoning_effort=args.reasoning_effort or None,
            timeout=300.0,
        )
    )
    raw_path = output_dir / f"{label}_newsletter_raw_response.txt"
    raw_path.write_text(response.content or "", encoding="utf-8")

    selection = parse_json_object(strip_json_fences(response.content or ""))
    errors = validate_selection(selection, {int(c["content_item_id"]) for c in candidates})
    selection["_meta"] = {
        "model": response.model,
        "prompt_version": PROMPT_VERSION,
        "date_from": date_from.isoformat(),
        "date_until": date_until.isoformat(),
        "window_label": label,
        "input_tokens": response.input_tokens,
        "output_tokens": response.output_tokens,
        "estimated_cost": response.estimated_cost,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "validation_errors": errors,
        "stats": stats,
    }

    json_path = output_dir / f"{label}_newsletter_selection.json"
    json_path.write_text(json.dumps(selection, indent=2, default=str) + "\n", encoding="utf-8")
    md_path = output_dir / f"{label}_newsletter_selection.md"
    md_path.write_text(render_markdown(selection, model=args.model, stats=stats), encoding="utf-8")

    print(f"estimated_cost=${response.estimated_cost}", flush=True)
    print(f"wrote {json_path}", flush=True)
    print(f"wrote {md_path}", flush=True)
    if errors:
        print("validation_errors:", errors, flush=True)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
