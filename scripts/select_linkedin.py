#!/usr/bin/env python3
"""LinkedIn TECH/PRODUCT selection via OpenRouter LLM for any date window.

Editorial/evaluation only. Does not change scoring, affiliation, or adjudication.

Hard rule: LinkedIn winners must differ from newsletter TECH and PRODUCT winners.

Example (after newsletter selection exists):
  PYTHONPATH=src python3 scripts/select_linkedin.py \\
    --from 2026-08-01 --until 2026-08-31 \\
    --newsletter-json reports/editorial/2026-08-01_to_2026-08-31_newsletter_selection.json \\
    --model anthropic/claude-opus-5 \\
    --reasoning-effort medium \\
    --output-dir reports/editorial

Requires OPENROUTER_API_KEY.
"""

from __future__ import annotations

import argparse
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
from paper_intelligence.db import connect
from paper_intelligence.editorial.seats import linkedin_seats_section
from paper_intelligence.openrouter import LLMRequest, complete

# Reuse pool loaders from the newsletter script without importing as a package.
import importlib.util

_spec = importlib.util.spec_from_file_location(
    "select_newsletter", ROOT / "scripts" / "select_newsletter.py"
)
assert _spec and _spec.loader
_newsletter = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_newsletter)

load_candidates_from_db = _newsletter.load_candidates_from_db
load_candidates_from_pool_json = _newsletter.load_candidates_from_pool_json
shortlist_for_prompt = _newsletter.shortlist_for_prompt
window_label = _newsletter.window_label

DEFAULT_MODEL = "anthropic/claude-opus-5"
DEFAULT_REASONING = "medium"
PROMPT_VERSION = "linkedin_select_v002"
SEATS_POLICY_VERSION = "v001"

SYSTEM_PROMPT = """\
You are an editorial selector for LinkedIn posts aimed at senior technology and \
product professionals.

Select exactly TWO ADDITIONAL papers from the shortlist:
- one LinkedIn TECH paper
- one LinkedIn PRODUCT paper

Also identify one runner-up for each seat.

Hard rule: LinkedIn winners MUST NOT be the same papers as the newsletter \
TECH winner or PRODUCT winner supplied in the user message.

Return ONLY a single JSON object matching the schema in the user message. \
No markdown fences, no preamble.
"""

USER_RUBRIC_LENS = """\
Use the SAME decision-value philosophy and seat definitions as the newsletter
selection. Seat definitions are loaded from the shared editorial seats policy
and appear below.

Governing question:
"What does this paper change for me, my team, my product, or my organisation?"

Select for DECISION VALUE, not prestige, novelty alone, or leaderboard gains.
Organisation prestige must NOT decide the winner.

Additionally apply a LinkedIn publishing lens.

A LinkedIn paper should have:
- one clear practical insight that can be explained without oversimplifying
- a decision or assumption professionals can debate
- enough evidence to support the claim
- a useful takeaway within the first few lines of a post
- relevance beyond a very narrow research niche
- a credible connection to day-to-day technical or product leadership

Avoid:
- papers requiring excessive academic background before the insight becomes useful
- papers whose main value is only benchmark improvement
- hype-driven results
- papers where the LinkedIn headline would require overstating the evidence

For TECH LinkedIn, prioritise topics such as:
- engineering practice
- architecture
- agents
- LLM evaluation
- reliability
- inference/cost/performance
- security
- deployment
- AI infrastructure

For PRODUCT LinkedIn, prioritise topics such as:
- human-AI interaction
- AI adoption
- workflow design
- trust
- governance
- user behaviour
- product operating model
- risk
- commercial/product decisions

Application gate:
There must be a credible 3–6 month decision, experiment, review, or operating
change for the intended reader. A test/review is enough; production rollout is not required.

Prefer also avoiding newsletter runner-ups when equally strong alternatives exist,
but that is not a hard rule.

For each LinkedIn seat also identify ONE runner-up.
Winner IDs must differ from BOTH newsletter winners.
"""


def build_user_rubric(*, seats_version: str = SEATS_POLICY_VERSION) -> str:
    return (
        USER_RUBRIC_LENS.strip()
        + "\n\n"
        + linkedin_seats_section(seats_version)
        + "\n"
    )


USER_RUBRIC = build_user_rubric()

OUTPUT_SCHEMA = """\
Return JSON with this exact shape:
{
  "tech": {
    "content_item_id": 0,
    "arxiv_id": "",
    "title": "",
    "canonical_url": "",
    "target_audience": "TECH",
    "why_this_paper": "",
    "decision_it_changes": "",
    "action_for_reader": "",
    "talking_point": "",
    "caveat": "",
    "why_it_works_for_linkedin": "",
    "why_not_runner_up": ""
  },
  "tech_runner_up": {
    "content_item_id": 0,
    "arxiv_id": "",
    "title": "",
    "canonical_url": "",
    "target_audience": "TECH",
    "why_this_paper": "",
    "decision_it_changes": "",
    "action_for_reader": "",
    "talking_point": "",
    "caveat": "",
    "why_it_works_for_linkedin": ""
  },
  "product": {
    "content_item_id": 0,
    "arxiv_id": "",
    "title": "",
    "canonical_url": "",
    "target_audience": "PRODUCT",
    "why_this_paper": "",
    "decision_it_changes": "",
    "action_for_reader": "",
    "talking_point": "",
    "caveat": "",
    "why_it_works_for_linkedin": "",
    "why_not_runner_up": ""
  },
  "product_runner_up": {
    "content_item_id": 0,
    "arxiv_id": "",
    "title": "",
    "canonical_url": "",
    "target_audience": "PRODUCT",
    "why_this_paper": "",
    "decision_it_changes": "",
    "action_for_reader": "",
    "talking_point": "",
    "caveat": "",
    "why_it_works_for_linkedin": ""
  },
  "posting_order": {
    "friday": "TECH",
    "tuesday": "PRODUCT",
    "rationale": "Which seat has the stronger immediate timeliness/editorial hook for Friday."
  },
  "post_briefs": {
    "friday": {
      "seat": "TECH",
      "content_item_id": 0,
      "hook": "",
      "core_insight": "",
      "why_it_matters": "",
      "practical_action": "",
      "caveat": "",
      "suggested_closing_question": ""
    },
    "tuesday": {
      "seat": "PRODUCT",
      "content_item_id": 0,
      "hook": "",
      "core_insight": "",
      "why_it_matters": "",
      "practical_action": "",
      "caveat": "",
      "suggested_closing_question": ""
    }
  },
  "cross_check": {
    "linkedin_winners_differ_from_newsletter_winners": true,
    "distinct_editorial_lessons": true,
    "notes": ""
  }
}

Post briefs:
- Hook: 1–2 sentences on the professional problem/question
- Core insight: 2–3 sentences grounded strictly in paper evidence
- Why it matters / Practical action / Caveat / Suggested closing question
- Do NOT invent claims beyond supplied evidence
- Do NOT write a fully promotional post
"""


def _parse_day(value: str) -> date:
    return date.fromisoformat(value[:10])


def load_newsletter_exclusions(path: Path) -> dict[str, Any]:
    data = json.loads(path.read_text(encoding="utf-8"))
    tech = (data.get("tech") or {}).get("content_item_id")
    product = (data.get("product") or {}).get("content_item_id")
    tech_ru = (data.get("tech_runner_up") or {}).get("content_item_id")
    product_ru = (data.get("product_runner_up") or {}).get("content_item_id")
    if tech is None or product is None:
        raise SystemExit(f"{path}: newsletter JSON missing tech/product winners")
    return {
        "tech_winner_id": int(tech),
        "product_winner_id": int(product),
        "tech_runner_up_id": int(tech_ru) if tech_ru is not None else None,
        "product_runner_up_id": int(product_ru) if product_ru is not None else None,
        "tech_winner": data.get("tech"),
        "product_winner": data.get("product"),
        "tech_runner_up": data.get("tech_runner_up"),
        "product_runner_up": data.get("product_runner_up"),
    }


def validate_selection(
    selection: dict[str, Any],
    *,
    allowed_ids: set[int],
    excluded_winner_ids: set[int],
) -> list[str]:
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
    winners = []
    for key in ("tech", "product"):
        try:
            winners.append(int((selection.get(key) or {})["content_item_id"]))
        except Exception:  # noqa: BLE001
            pass
    if len(winners) == 2 and winners[0] == winners[1]:
        errors.append("LinkedIn TECH and PRODUCT winners must differ")
    for wid in winners:
        if wid in excluded_winner_ids:
            errors.append(f"LinkedIn winner {wid} collides with newsletter winner")
    if len(ids) == 4 and len(set(ids)) != 4:
        errors.append(f"four LinkedIn IDs are not unique: {ids}")
    return errors


def render_selection_markdown(
    selection: dict[str, Any],
    *,
    model: str,
    exclusions: dict[str, Any],
    stats: dict[str, Any],
) -> str:
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
            f"- **Why LinkedIn:** {node.get('why_it_works_for_linkedin')}\n"
            + (
                f"- **Why not runner-up:** {node.get('why_not_runner_up')}\n"
                if node.get("why_not_runner_up")
                else ""
            )
        )

    return (
        f"# LinkedIn selection (LLM)\n\n"
        f"- model: `{model}`\n"
        f"- prompt_version: `{PROMPT_VERSION}`\n"
        f"- window: {stats.get('date_from')} → {stats.get('date_until')}\n"
        f"- excluded newsletter winners: "
        f"`{exclusions['tech_winner_id']}`, `{exclusions['product_winner_id']}`\n\n"
        f"## LinkedIn TECH\n{block('Winner', selection['tech'])}\n"
        f"{block('Runner-up', selection['tech_runner_up'])}\n"
        f"## LinkedIn PRODUCT\n{block('Winner', selection['product'])}\n"
        f"{block('Runner-up', selection['product_runner_up'])}\n"
    )


def render_post_briefs_markdown(selection: dict[str, Any]) -> str:
    briefs = selection.get("post_briefs") or {}
    order = selection.get("posting_order") or {}
    lines = [
        "# LinkedIn post briefs (LLM)",
        "",
        "Do not publish/schedule from this file. Claims must stay within paper evidence.",
        "",
        f"Friday seat: **{order.get('friday')}** · Tuesday seat: **{order.get('tuesday')}**",
        f"Order rationale: {order.get('rationale') or ''}",
        "",
    ]
    for when in ("friday", "tuesday"):
        b = briefs.get(when) or {}
        lines.extend(
            [
                "---",
                "",
                f"## Post — {when.capitalize()} — {b.get('seat')}",
                "",
                f"content_item_id: `{b.get('content_item_id')}`",
                "",
                f"**Hook:**  \n{b.get('hook')}",
                "",
                f"**Core insight:**  \n{b.get('core_insight')}",
                "",
                f"**Why it matters:**  \n{b.get('why_it_matters')}",
                "",
                f"**Practical action:**  \n{b.get('practical_action')}",
                "",
                f"**Caveat:**  \n{b.get('caveat')}",
                "",
                f"**Suggested closing question:**  \n{b.get('suggested_closing_question')}",
                "",
            ]
        )
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="LLM LinkedIn selection for any --from/--until date window"
    )
    parser.add_argument("--from", dest="date_from", required=True, help="Inclusive start date YYYY-MM-DD")
    parser.add_argument("--until", dest="date_until", required=True, help="Inclusive end date YYYY-MM-DD")
    parser.add_argument(
        "--newsletter-json",
        required=True,
        help="Path to newsletter_selection.json for the same window (hard exclusions)",
    )
    parser.add_argument("--model", default=DEFAULT_MODEL)
    parser.add_argument("--reasoning-effort", default=DEFAULT_REASONING)
    parser.add_argument("--temperature", type=float, default=0.2)
    parser.add_argument("--max-tokens", type=int, default=9000)
    parser.add_argument("--limit", type=int, default=None)
    parser.add_argument("--pool-json", default=None)
    parser.add_argument("--output-dir", default=str(ROOT / "reports" / "editorial"))
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args(argv)

    date_from = _parse_day(args.date_from)
    date_until = _parse_day(args.date_until)
    if date_until < date_from:
        print("--until must be on or after --from", file=sys.stderr)
        return 2

    label = window_label(date_from, date_until)
    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    exclusions = load_newsletter_exclusions(Path(args.newsletter_json))
    excluded = {exclusions["tech_winner_id"], exclusions["product_winner_id"]}

    if args.pool_json:
        stats, candidates = load_candidates_from_pool_json(Path(args.pool_json))
        stats = {
            **stats,
            "date_from": stats.get("date_from") or date_from.isoformat(),
            "date_until": stats.get("date_until") or date_until.isoformat(),
        }
        if args.limit:
            candidates = candidates[: args.limit]
    else:
        with connect() as conn:
            stats, candidates = load_candidates_from_db(
                conn, date_from, date_until, limit=args.limit
            )

    print("=== LINKEDIN SELECTION INPUT ===", flush=True)
    print(f"window: {date_from.isoformat()} → {date_until.isoformat()}", flush=True)
    print(f"eligible candidates: {len(candidates)}", flush=True)
    print(
        f"excluded newsletter winners: {exclusions['tech_winner_id']}, "
        f"{exclusions['product_winner_id']}",
        flush=True,
    )

    if len(candidates) < 4:
        print("Need at least 4 eligible candidates.", file=sys.stderr)
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
        + "\n\n<newsletter_winners_hard_exclude>\n"
        + json.dumps(
            {
                "tech_winner": {
                    "content_item_id": exclusions["tech_winner_id"],
                    "title": (exclusions.get("tech_winner") or {}).get("title"),
                },
                "product_winner": {
                    "content_item_id": exclusions["product_winner_id"],
                    "title": (exclusions.get("product_winner") or {}).get("title"),
                },
                "tech_runner_up_soft_avoid": exclusions.get("tech_runner_up_id"),
                "product_runner_up_soft_avoid": exclusions.get("product_runner_up_id"),
            },
            indent=2,
        )
        + "\n</newsletter_winners_hard_exclude>\n\n<shortlist>\n"
        + json.dumps(shortlist, indent=2, default=str)
        + "\n</shortlist>\n"
    )
    prompt_path = output_dir / f"{label}_linkedin_prompt_user.txt"
    prompt_path.write_text(user_prompt, encoding="utf-8")

    if args.dry_run:
        print(f"dry-run: wrote prompt under {output_dir}", flush=True)
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
    (output_dir / f"{label}_linkedin_raw_response.txt").write_text(
        response.content or "", encoding="utf-8"
    )

    selection = parse_json_object(strip_json_fences(response.content or ""))
    errors = validate_selection(
        selection,
        allowed_ids={int(c["content_item_id"]) for c in candidates},
        excluded_winner_ids=excluded,
    )
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
        "excluded_newsletter_winners": sorted(excluded),
        "validation_errors": errors,
        "stats": stats,
    }

    json_path = output_dir / f"{label}_linkedin_selection.json"
    json_path.write_text(json.dumps(selection, indent=2, default=str) + "\n", encoding="utf-8")
    md_path = output_dir / f"{label}_linkedin_selection.md"
    md_path.write_text(
        render_selection_markdown(
            selection, model=args.model, exclusions=exclusions, stats=stats
        ),
        encoding="utf-8",
    )
    briefs_path = output_dir / f"{label}_linkedin_post_briefs.md"
    briefs_path.write_text(render_post_briefs_markdown(selection), encoding="utf-8")

    print(f"estimated_cost=${response.estimated_cost}", flush=True)
    print(f"wrote {json_path}", flush=True)
    print(f"wrote {md_path}", flush=True)
    print(f"wrote {briefs_path}", flush=True)
    if errors:
        print("validation_errors:", errors, flush=True)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
