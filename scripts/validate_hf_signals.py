#!/usr/bin/env python3
"""HF Daily Papers validation — 30-day overlap + ranking comparison.

Observational only: does not change final_score / adjudication / classification.

Example:
  PYTHONPATH=src python3 scripts/validate_hf_signals.py
  PYTHONPATH=src python3 scripts/validate_hf_signals.py --from 2026-08-18 --until 2026-09-16
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import date, timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from paper_intelligence.common.config import PI_USE_PAPERS_CATALOG
from paper_intelligence.db import connect
from paper_intelligence.evaluation.hf_validation import (
    DEFAULT_WINDOW_END,
    DEFAULT_WINDOW_START,
    SCORE_FIELD,
    SELECTION_DETAIL,
    SELECTION_METHOD,
    STAGE_NAME,
    STAGE_VERSION,
    assign_cohort,
    build_report_payload,
    compute_overlap,
    console_summary,
    inclusive_days,
    summarize_cohort,
    top_n,
    write_csv,
)
from paper_intelligence.external import huggingface as hf_client
from paper_intelligence.observability import (
    code_commit_sha,
    finish_pipeline_run,
    finish_stage_run,
    start_pipeline_run,
    start_stage_run,
)


PAPER_SQL_RADAR = """
SELECT
    ci.id AS content_item_id,
    pm.arxiv_id,
    ci.title,
    ci.published_at::date AS published_at,
    c.domain,
    c.subdomains,
    c.audiences,
    c.application_domains,
    c.final_score,
    c.quality_score,
    c.screen_score,
    c.org_boost,
    c.organisation_score,
    s.hf_featured,
    s.hf_featured_date,
    s.hf_upvotes,
    s.hf_daily_upvote_rank,
    (
      SELECT o.canonical_name
      FROM paper_intelligence.paper_author_affiliations a
      JOIN paper_intelligence.organisations o ON o.id = a.organisation_id
      WHERE a.content_item_id = ci.id AND o.is_org_of_interest
      ORDER BY o.priority DESC NULLS LAST, o.canonical_name
      LIMIT 1
    ) AS notable_organisation,
    NULL::text AS notable_person
FROM research_radar.content_items ci
JOIN research_radar.paper_metadata pm ON pm.content_id = ci.id
LEFT JOIN paper_intelligence.paper_intelligence_current c
       ON c.content_item_id = ci.id
LEFT JOIN paper_intelligence.paper_hf_signals s
       ON s.content_item_id = ci.id
WHERE ci.published_at >= %s::timestamptz
  AND ci.published_at < (%s::timestamptz + interval '1 day')
  AND pm.arxiv_id IS NOT NULL
"""

PAPER_SQL_PI = """
SELECT
    p.paper_id AS content_item_id,
    p.arxiv_id,
    p.title,
    p.published_at::date AS published_at,
    c.domain,
    c.subdomains,
    c.audiences,
    c.application_domains,
    c.final_score,
    c.quality_score,
    c.screen_score,
    c.org_boost,
    c.organisation_score,
    s.hf_featured,
    s.hf_featured_date,
    s.hf_upvotes,
    s.hf_daily_upvote_rank,
    (
      SELECT o.canonical_name
      FROM paper_intelligence.paper_author_affiliations a
      JOIN paper_intelligence.organisations o ON o.id = a.organisation_id
      WHERE a.content_item_id = p.paper_id AND o.is_org_of_interest
      ORDER BY o.priority DESC NULLS LAST, o.canonical_name
      LIMIT 1
    ) AS notable_organisation,
    NULL::text AS notable_person
FROM paper_intelligence.papers p
LEFT JOIN paper_intelligence.paper_intelligence_current c
       ON c.content_item_id = p.paper_id
LEFT JOIN paper_intelligence.paper_hf_signals s
       ON s.content_item_id = p.paper_id
WHERE p.published_at >= %s::timestamptz
  AND p.published_at < (%s::timestamptz + interval '1 day')
  AND p.arxiv_id IS NOT NULL
"""

PAPER_SQL = PAPER_SQL_RADAR


def _parse_day(value: str) -> date:
    return date.fromisoformat(value[:10])


def collect_hf_daily_ids(
    start: date,
    end: date,
    *,
    conn,
    run_id: str | None,
    stage_run_id: str | None,
) -> set[str]:
    """Unique arXiv ids appearing on HF Daily Papers in [start, end] (inclusive)."""
    ids: set[str] = set()
    day = start
    while day <= end:
        page = hf_client.list_daily_papers(
            day, conn=conn, run_id=run_id, stage_run_id=stage_run_id
        )
        if page.error:
            print(f"  WARN hf daily {day}: {page.error}", flush=True)
        for entry in page.papers or []:
            paper = entry.get("paper") if isinstance(entry, dict) else None
            aid = (paper or {}).get("id") if isinstance(paper, dict) else None
            if aid:
                ids.add(str(aid))
        day += timedelta(days=1)
    return ids


def ensure_hf_signals_for_window(start: date, end: date) -> dict:
    """Fill paper_hf_signals for the window if sparse (uses stage; cached HTTP)."""
    from paper_intelligence.hf_signals import run_window

    return run_window(start.isoformat(), end.isoformat(), fetch_paper_detail=True)


def load_papers(conn, start: date, end: date) -> list[dict]:
    sql = PAPER_SQL_PI if PI_USE_PAPERS_CATALOG else PAPER_SQL_RADAR
    with conn.cursor() as cur:
        cur.execute(sql, (start.isoformat(), end.isoformat()))
        return [dict(r) for r in cur.fetchall()]


def write_markdown(
    path: Path,
    *,
    start: date,
    end: date,
    overlap,
    metrics: dict,
    ranking_note: str,
    recommendation: str,
    findings: list[str],
    run_meta: dict,
) -> None:
    both = metrics["BOTH"]
    ours = metrics["OURS_ONLY"]
    hf_only = metrics["HF_ONLY"]
    lines = [
        "# Hugging Face Daily Papers — validation",
        "",
        "## Purpose",
        "",
        "Determine whether HF Daily Papers adds **incremental editorial/relevance signal**",
        "beyond PaperIntelligence ranking. A finding that HF adds little value is valid.",
        "",
        "This analysis does **not** change `final_score`, adjudication, classification,",
        "or affiliation.",
        "",
        "## Methodology",
        "",
        f"- **Window (inclusive):** `{start.isoformat()}` → `{end.isoformat()}`",
        f"  ({inclusive_days(start, end)} days).",
        "- **Our corpus:** `research_radar.content_items` with `paper_metadata.arxiv_id`",
        "  and `published_at` in the window.",
        "- **HF set:** unique arXiv ids from HF Daily Papers API for each day in the",
        "  window (day-local list; not `sort=trending`).",
        "- **Overlap** joins those id sets.",
        f"- **Score field:** `{SCORE_FIELD}` on `paper_intelligence_current`.",
        f"- **High-quality selection:** `{SELECTION_METHOD}`.",
        f"  {SELECTION_DETAIL}",
        "",
        "### Cohorts (mutually exclusive on comparison universe)",
        "",
        "- **BOTH** — HF Daily Papers ∩ high-quality (`final_score` present)",
        "- **OURS_ONLY** — high-quality \\ HF",
        "- **HF_ONLY** — HF ∩ our corpus, but no `final_score`",
        "",
        "Comparison universe = high-quality ∪ (HF ∩ our corpus).",
        "",
        "## Overlap calculations",
        "",
        f"| Metric | Value |",
        f"|---|---:|",
        f"| HF unique (Daily Papers in window) | {overlap.hf_unique} |",
        f"| Our unique (arxiv papers in window) | {overlap.our_unique} |",
        f"| Intersection | {overlap.intersection} |",
        f"| HF → ours % | {overlap.hf_to_ours_pct} |",
        f"| Ours → HF % | {overlap.ours_to_hf_pct} |",
        f"| HF-only (not in our window corpus) | {overlap.hf_only} |",
        f"| Ours-only (not on HF Daily in window) | {overlap.ours_only} |",
        "",
        "## Ranking comparison",
        "",
        ranking_note,
        "",
        "| Cohort | N | Avg final_score | Median | % notable org | % tech/product aud | Mean HF upvotes |",
        "|---|---:|---:|---:|---:|---:|---:|",
        f"| BOTH | {both.count} | {both.avg_score} | {both.median_score} | {both.pct_notable_org} | {both.pct_tech_product_audience} | {both.mean_hf_upvotes} |",
        f"| OURS_ONLY | {ours.count} | {ours.avg_score} | {ours.median_score} | {ours.pct_notable_org} | {ours.pct_tech_product_audience} | {ours.mean_hf_upvotes} |",
        f"| HF_ONLY | {hf_only.count} | {hf_only.avg_score} | {hf_only.median_score} | {hf_only.pct_notable_org} | {hf_only.pct_tech_product_audience} | {hf_only.mean_hf_upvotes} |",
        "",
        "### Domain distribution (BOTH)",
        "",
        "```",
        json.dumps(both.domain_distribution, indent=2),
        "```",
        "",
        "## Caveats",
        "",
        "- Quality/`final_score` coverage may be concentrated in part of the window",
        "  (pipeline paid stages not necessarily run for every day).",
        "- HF-only cohort average score is expected to be null when those papers never",
        "  entered the quality slice.",
        "- `hf_daily_upvote_rank` is same-day upvote rank, not HF global trending.",
        "- HF→ours < 100% can mean paper not in our category filter / not yet ingested",
        "  for that publish date, not that HF has non-arXiv papers.",
        "",
        "## Findings",
        "",
    ]
    for finding in findings:
        lines.append(f"- {finding}")
    lines += [
        "",
        "## Recommendation",
        "",
        recommendation,
        "",
        "## Run provenance",
        "",
        "```json",
        json.dumps(run_meta, indent=2, default=str),
        "```",
        "",
    ]
    path.write_text("\n".join(lines), encoding="utf-8")


def derive_findings(overlap, metrics: dict) -> tuple[list[str], str]:
    findings: list[str] = []
    findings.append(
        f"HF → our corpus overlap is {overlap.hf_to_ours_pct}% "
        f"({overlap.intersection}/{overlap.hf_unique})."
    )
    findings.append(
        f"Our corpus → HF overlap is {overlap.ours_to_hf_pct}% "
        f"({overlap.intersection}/{overlap.our_unique}) — HF is a thin curated slice."
    )
    both = metrics["BOTH"]
    ours = metrics["OURS_ONLY"]
    hf_only = metrics["HF_ONLY"]
    findings.append(
        f"Cohorts: BOTH={both.count}, OURS_ONLY={ours.count}, HF_ONLY={hf_only.count}."
    )

    recommendation = "weak signal"
    if both.count and ours.avg_score is not None and both.avg_score is not None:
        delta = both.avg_score - ours.avg_score
        findings.append(
            f"Avg final_score BOTH ({both.avg_score}) vs OURS_ONLY ({ours.avg_score}); "
            f"delta={round(delta, 3)}."
        )
        # Incremental signal if BOTH is materially higher than OURS_ONLY, or HF
        # recovers many high-upvote papers we already score highly.
        if abs(delta) < 0.3 and both.count < max(20, int(0.15 * (both.count + ours.count))):
            recommendation = "no incremental signal"
            findings.append(
                "BOTH is not materially higher-scoring than OURS_ONLY and is a small "
                "share of our high-quality set — HF adds little ranking lift on this window."
            )
        elif delta >= 0.3:
            recommendation = "HF adds useful signal"
            findings.append(
                "BOTH scores materially above OURS_ONLY — HF co-selection correlates "
                "with higher final_score on this window."
            )
        else:
            recommendation = "weak signal"
            findings.append(
                "BOTH vs OURS_ONLY score gap is small; treat HF as optional prior, "
                "not primary ranker."
            )
    else:
        findings.append(
            "Insufficient BOTH/OURS_ONLY score coverage to claim ranking lift."
        )
        recommendation = "weak signal"

    if hf_only.count:
        findings.append(
            f"HF_ONLY={hf_only.count} papers are featured on HF but lack final_score "
            f"(mean upvotes={hf_only.mean_hf_upvotes}) — candidates we may be missing "
            "if gate/quality coverage is incomplete, not proof HF should boost score."
        )

    text = {
        "HF adds useful signal": (
            "**Recommendation: HF adds useful signal** — measured co-selection aligns "
            "with higher `final_score`. Still do not change production weights until "
            "replicated on another window."
        ),
        "weak signal": (
            "**Recommendation: weak signal** — HF is a valid curation layer but does "
            "not yet justify changing `final_score` on this evidence."
        ),
        "no incremental signal": (
            "**Recommendation: no incremental signal** — on this window HF does not "
            "improve on our high-quality set enough to warrant a ranking change."
        ),
    }[recommendation]
    return findings, text


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="HF Daily Papers 30-day validation")
    parser.add_argument("--from", dest="date_from", default=DEFAULT_WINDOW_START.isoformat())
    parser.add_argument("--until", dest="date_until", default=DEFAULT_WINDOW_END.isoformat())
    parser.add_argument(
        "--skip-hf-enrich",
        action="store_true",
        help="do not call hf_signals stage; use existing paper_hf_signals only",
    )
    parser.add_argument("--reports-dir", type=Path, default=ROOT / "reports")
    args = parser.parse_args(argv)

    start = _parse_day(args.date_from)
    end = _parse_day(args.date_until)
    if inclusive_days(start, end) != 30:
        print(
            f"WARNING: window is {inclusive_days(start, end)} days (expected 30). "
            "Proceeding with documented boundaries.",
            flush=True,
        )

    reports_dir = args.reports_dir
    reports_dir.mkdir(parents=True, exist_ok=True)

    with connect() as conn:
        run_id = start_pipeline_run(
            conn,
            pipeline_name="paper_intelligence.hf_validation",
            trigger_type="manual",
            metadata={"date_from": start.isoformat(), "date_until": end.isoformat()},
        )
        stage_run_id = start_stage_run(
            conn, run_id, stage_name=STAGE_NAME, stage_version=STAGE_VERSION
        )
        try:
            if not args.skip_hf_enrich:
                print("=== ensuring HF signals for window ===", flush=True)
                enrich = ensure_hf_signals_for_window(start, end)
                print(f"hf_signals: {enrich}", flush=True)

            print("=== collecting HF Daily Papers id set (cache-friendly) ===", flush=True)
            hf_ids = collect_hf_daily_ids(
                start, end, conn=conn, run_id=run_id, stage_run_id=stage_run_id
            )
            print(f"HF unique ids: {len(hf_ids)}", flush=True)

            papers = load_papers(conn, start, end)
            our_ids = {p["arxiv_id"] for p in papers if p.get("arxiv_id")}
            overlap = compute_overlap(hf_ids, our_ids)

            # Attach global our-rank among scored papers
            scored = sorted(
                [p for p in papers if p.get("final_score") is not None],
                key=lambda r: (
                    -float(r["final_score"]),
                    -float(r["quality_score"] or 0),
                    str(r.get("arxiv_id") or ""),
                ),
            )
            our_rank = {
                p["content_item_id"]: i for i, p in enumerate(scored, start=1)
            }

            cohorts: dict[str, list[dict]] = {
                "BOTH": [],
                "OURS_ONLY": [],
                "HF_ONLY": [],
            }
            for p in papers:
                aid = p.get("arxiv_id")
                in_hf = bool(aid and aid in hf_ids)
                in_hq = p.get("final_score") is not None
                cohort = assign_cohort(in_hf=in_hf, in_high_quality=in_hq)
                if cohort is None:
                    continue
                row = dict(p)
                row["our_rank"] = our_rank.get(p["content_item_id"])
                row["hf_featured"] = in_hf
                cohorts[cohort].append(row)

            metrics = {name: summarize_cohort(rows) for name, rows in cohorts.items()}
            samples = {
                "BOTH": top_n(cohorts["BOTH"], 20, cohort="BOTH"),
                "OURS_ONLY": top_n(cohorts["OURS_ONLY"], 20, cohort="OURS_ONLY"),
                "HF_ONLY": top_n(cohorts["HF_ONLY"], 20, cohort="HF_ONLY"),
            }

            findings, recommendation = derive_findings(overlap, metrics)
            run_meta = {
                "run_id": run_id,
                "stage_name": STAGE_NAME,
                "stage_version": STAGE_VERSION,
                "code_commit_sha": code_commit_sha(),
                "papers_evaluated": len(papers),
                "hf_unique": overlap.hf_unique,
                "high_quality_count": len(scored),
            }
            payload = build_report_payload(
                window_start=start,
                window_end=end,
                overlap=overlap,
                cohorts=cohorts,
                metrics=metrics,
                run_meta=run_meta,
            )
            payload["findings"] = findings
            payload["recommendation"] = recommendation
            payload["samples"] = {
                k: [
                    {
                        "arxiv_id": r.get("arxiv_id"),
                        "title": r.get("title"),
                        "final_score": r.get("final_score"),
                        "hf_upvotes": r.get("hf_upvotes"),
                    }
                    for r in v
                ]
                for k, v in samples.items()
            }

            json_path = reports_dir / "hf_validation_30d.json"
            json_path.write_text(json.dumps(payload, indent=2, default=str), encoding="utf-8")
            write_csv(reports_dir / "hf_both_top20.csv", samples["BOTH"])
            write_csv(reports_dir / "hf_ours_only_top20.csv", samples["OURS_ONLY"])
            write_csv(reports_dir / "hf_only_top20.csv", samples["HF_ONLY"])

            ranking_note = (
                f"Score field `{SCORE_FIELD}`; selection `{SELECTION_METHOD}`. "
                f"{SELECTION_DETAIL}"
            )
            write_markdown(
                ROOT / "docs" / "hf_validation.md",
                start=start,
                end=end,
                overlap=overlap,
                metrics=metrics,
                ranking_note=ranking_note,
                recommendation=recommendation,
                findings=findings,
                run_meta=run_meta,
            )

            print(console_summary(overlap, metrics), flush=True)
            print(f"\nwrote {json_path}", flush=True)
            print(f"wrote {ROOT / 'docs' / 'hf_validation.md'}", flush=True)

            finish_stage_run(
                conn,
                stage_run_id,
                status="succeeded",
                items_success=len(papers),
            )
            finish_pipeline_run(
                conn,
                run_id,
                status="succeeded",
                items_input=len(papers),
                items_succeeded=len(papers),
                metadata=payload["overlap"],
            )
            return 0
        except Exception as exc:  # noqa: BLE001
            finish_stage_run(
                conn, stage_run_id, status="failed", error_summary=str(exc)[:500]
            )
            finish_pipeline_run(conn, run_id, status="failed")
            print(f"hf_validation failed: {exc}", file=sys.stderr)
            raise


if __name__ == "__main__":
    raise SystemExit(main())
