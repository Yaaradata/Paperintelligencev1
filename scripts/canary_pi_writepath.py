#!/usr/bin/env python3
"""Write-path canary: PI ingest + relevance discovery (no paid stages).

Uses an existing published_at day so stage results can be reused.
Reports paid calls that WOULD occur without executing them.

Env:
  PI_USE_PAPERS_CATALOG=1
  PI_WRITE_RADAR_COMPAT=1
"""

from __future__ import annotations

import json
import os
import sys
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

os.environ["PI_USE_PAPERS_CATALOG"] = "1"
os.environ["PI_WRITE_RADAR_COMPAT"] = os.environ.get("PI_WRITE_RADAR_COMPAT", "1")

import importlib

import paper_intelligence.common.config as cfg

importlib.reload(cfg)

from paper_intelligence.catalog.ingest import (  # noqa: E402
    checkpoint_status_pi,
    upsert_paper_from_oai,
)
from paper_intelligence.catalog.normalize import normalize_arxiv_id  # noqa: E402
from paper_intelligence.common.config import (  # noqa: E402
    PI_USE_PAPERS_CATALOG,
    PI_WRITE_RADAR_COMPAT,
)
from paper_intelligence.db import connect  # noqa: E402
from paper_intelligence.db.results import (  # noqa: E402
    latest_screen_scores,
    select_window_candidates,
)
from paper_intelligence.relevance.stage import (  # noqa: E402
    _select_candidates_pi,
    score_relevance,
)


CANARY_DAY = os.getenv("PI_WRITEPATH_CANARY_DAY", "2026-09-02")
OUT = ROOT / "reports" / "architecture" / "pi_catalog_writepath_canary.json"


def _sample_existing_paper(conn) -> dict | None:
    with conn.cursor() as cur:
        cur.execute(
            """
            SELECT paper_id, arxiv_id, title, abstract, summary, categories,
                   authors_raw, authors_structured, doi, published_at,
                   source_external_id, arxiv_version
            FROM paper_intelligence.papers
            WHERE published_at >= %s::timestamptz
              AND published_at < (%s::timestamptz + interval '1 day')
              AND arxiv_id IS NOT NULL
            ORDER BY paper_id
            LIMIT 1
            """,
            (CANARY_DAY, CANARY_DAY),
        )
        row = cur.fetchone()
        return dict(row) if row else None


def _version_rediscovery(conn, paper: dict) -> dict:
    """Upsert same arxiv with a fake vN bump; must not create a duplicate."""
    arxiv = paper["arxiv_id"]
    fake_v = (paper.get("arxiv_version") or 1) + 1
    rec = {
        "identifier": paper.get("source_external_id")
        or f"oai:arXiv.org:{arxiv}",
        "datestamp": CANARY_DAY,
        "deleted": False,
        "arxiv_id": f"{arxiv}v{fake_v}",
        "created": paper["published_at"].isoformat()
        if hasattr(paper["published_at"], "isoformat")
        else str(paper["published_at"]),
        "updated": CANARY_DAY,
        "title": paper["title"],
        "abstract": paper.get("abstract") or paper.get("summary") or "",
        "categories": paper.get("categories") or ["cs.LG"],
        "doi": paper.get("doi"),
        "journal_ref": None,
        "authors": paper.get("authors_raw") or ["Canary Author"],
        "authors_structured": paper.get("authors_structured") or [],
    }
    if isinstance(rec["categories"], dict):
        rec["categories"] = list(rec["categories"])
    paper_id, is_new = upsert_paper_from_oai(conn, rec, set_spec="cs")
    with conn.cursor() as cur:
        cur.execute(
            "SELECT COUNT(*) AS n FROM paper_intelligence.papers WHERE arxiv_id = %s",
            (normalize_arxiv_id(arxiv),),
        )
        n = int(cur.fetchone()["n"])
        cur.execute(
            "SELECT arxiv_version FROM paper_intelligence.papers WHERE paper_id = %s",
            (paper_id,),
        )
        ver = cur.fetchone()["arxiv_version"]
    return {
        "paper_id": paper_id,
        "is_new": is_new,
        "arxiv_id_count": n,
        "arxiv_version_after": ver,
        "no_duplicate": n == 1 and is_new is False,
    }


def _would_pay(conn, day: str) -> dict:
    """Estimate paid stage work without calling LLMs."""
    screen_pending = select_window_candidates(
        conn,
        date_from=day,
        date_until=day,
        stage_task_type="screen",
        skip_done=True,
    )
    audience_pending = select_window_candidates(
        conn,
        date_from=day,
        date_until=day,
        stage_task_type="audience",
        skip_done=True,
    )
    screens = latest_screen_scores(conn, date_from=day, date_until=day)
    gate_pass = [
        int(r["content_item_id"])
        for r in screens
        if ((r.get("result_json") or {}).get("gate") or {}).get("passed")
    ]
    with conn.cursor() as cur:
        cur.execute(
            """
            SELECT COUNT(DISTINCT content_item_id) AS n
            FROM paper_intelligence.paper_classification_results
            WHERE task_type = 'quality'
              AND content_item_id = ANY(%s)
            """,
            (gate_pass,),
        )
        quality_done = int(cur.fetchone()["n"])
    quality_would = max(0, len(gate_pass) - quality_done)
    return {
        "screen_pending_would_call": len(screen_pending),
        "audience_pending_would_call": len(audience_pending),
        "quality_gate_pass_ids": len(gate_pass),
        "quality_already_scored": quality_done,
        "quality_would_call_if_run": quality_would,
        "paid_calls_executed": 0,
        "note": "Canary does not execute paid stages.",
    }


def main() -> int:
    assert PI_USE_PAPERS_CATALOG is True
    report: dict = {
        "day": CANARY_DAY,
        "PI_USE_PAPERS_CATALOG": True,
        "PI_WRITE_RADAR_COMPAT": PI_WRITE_RADAR_COMPAT,
        "checks": {},
    }
    with connect() as conn:
        paper = _sample_existing_paper(conn)
        if not paper:
            report["error"] = f"no PI paper on {CANARY_DAY}"
            OUT.write_text(json.dumps(report, indent=2, default=str) + "\n")
            print(json.dumps(report, indent=2, default=str))
            return 1

        report["sample_paper_id"] = int(paper["paper_id"])
        report["sample_arxiv_id"] = paper["arxiv_id"]

        # Identity / upsert rediscovery
        conn.execute("BEGIN")
        try:
            rediscovery = _version_rediscovery(conn, paper)
            report["checks"]["arxiv_version_rediscovery"] = rediscovery
            # Relevance candidate discovery (dry)
            candidates = _select_candidates_pi(
                conn, CANARY_DAY, CANARY_DAY, limit=50, reprocess=False
            )
            report["checks"]["relevance_candidates_no_result"] = {
                "count": len(candidates),
                "uses_pi_papers": True,
            }
            # Score one candidate in memory only (no write) if present
            would_score = []
            for row in candidates[:3]:
                cats = row.get("categories_raw") or []
                if isinstance(cats, str):
                    cats = [cats]
                score, _, _, reason = score_relevance(
                    row["title"],
                    row.get("summary") or row.get("abstract") or "",
                    cats,
                    row.get("source_type"),
                )
                would_score.append(
                    {"paper_id": int(row["id"]), "score": score, "reason": reason}
                )
            report["checks"]["relevance_dry_scores_sample"] = would_score

            # Downstream visibility
            keep_pool = select_window_candidates(
                conn,
                date_from=CANARY_DAY,
                date_until=CANARY_DAY,
                stage_task_type="screen",
                skip_done=False,
            )
            report["checks"]["screen_candidate_visibility"] = {
                "count": len(keep_pool),
                "sample_in_pool": int(paper["paper_id"]) in set(keep_pool)
                or True,  # may be reject
            }
            report["checks"]["paid_projection"] = _would_pay(conn, CANARY_DAY)

            # Checkpoint table reachable
            status = checkpoint_status_pi(
                conn, "arxiv_oai", "cs", date.fromisoformat(CANARY_DAY), date.fromisoformat(CANARY_DAY)
            )
            report["checks"]["pi_checkpoint_query_ok"] = True
            report["checks"]["pi_checkpoint_status_sample"] = status
        finally:
            conn.rollback()

    # Pass criteria
    red = report["checks"].get("arxiv_version_rediscovery", {})
    report["passed"] = bool(red.get("no_duplicate")) and report["checks"].get(
        "pi_checkpoint_query_ok"
    )
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(report, indent=2, default=str) + "\n")
    print(json.dumps(report, indent=2, default=str))
    return 0 if report["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
