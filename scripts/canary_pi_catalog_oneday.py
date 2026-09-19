#!/usr/bin/env python3
"""One-day PI catalog canary with PI_USE_PAPERS_CATALOG=1 (no paid quality)."""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path

# Force canary flags before importing config-dependent modules
os.environ["PI_USE_PAPERS_CATALOG"] = "1"
os.environ["PI_WRITE_RADAR_COMPAT"] = "1"

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

# Reload config after env set
import importlib
import paper_intelligence.common.config as cfg

importlib.reload(cfg)
import paper_intelligence.db.results as results_mod

importlib.reload(results_mod)

from paper_intelligence.catalog.normalize import normalize_arxiv_id
from paper_intelligence.catalog.relevance import current_relevance
from paper_intelligence.db import connect, fetch_papers, latest_screen_scores, select_window_candidates
from paper_intelligence.quality.stage import explain_quality_routing, select_quality_candidates
from paper_intelligence.author_affiliation.repository import fetch_paper
from paper_intelligence.common.config import GATE_PERCENTILE, PI_USE_PAPERS_CATALOG, PI_WRITE_RADAR_COMPAT


def main() -> int:
    day = "2026-09-02"
    focus = 137619
    assert PI_USE_PAPERS_CATALOG is True
    assert PI_WRITE_RADAR_COMPAT is True

    with connect() as conn:
        papers = fetch_papers(conn, [focus])
        assert papers and papers[0]["content_item_id"] == focus

        rel = current_relevance(conn, focus)
        screens = latest_screen_scores(conn, date_from=day, date_until=day)
        screen_ids = {int(r["content_item_id"]) for r in screens}
        decisions = {
            d.content_item_id: d
            for d in explain_quality_routing(
                conn, date_from=day, date_until=day, gate_percentile=GATE_PERCENTILE
            )
        }
        selected = set(
            select_quality_candidates(
                conn, date_from=day, date_until=day, gate_percentile=GATE_PERCENTILE
            )
        )
        aff = fetch_paper(conn, focus)

        # HF identity via normalized arxiv
        with conn.cursor() as cur:
            cur.execute(
                "SELECT paper_id, arxiv_id FROM paper_intelligence.papers WHERE paper_id=%s",
                (focus,),
            )
            prow = dict(cur.fetchone())
            arxiv = prow["arxiv_id"]
            cur.execute(
                """
                SELECT COUNT(*) AS n FROM paper_intelligence.papers WHERE arxiv_id = %s
                """,
                (arxiv,),
            )
            arxiv_n = int(cur.fetchone()["n"])
            # orphan check for day results
            cur.execute(
                """
                SELECT COUNT(*) AS orphans
                FROM paper_intelligence.paper_classification_results r
                LEFT JOIN paper_intelligence.papers p ON p.paper_id = r.content_item_id
                JOIN paper_intelligence.papers pw ON pw.paper_id = r.content_item_id
                WHERE pw.published_at >= %s::timestamptz
                  AND pw.published_at < (%s::timestamptz + interval '1 day')
                  AND p.paper_id IS NULL
                """,
                (day, day),
            )
            # simpler: all screen content ids resolve
            orphans = 0
            for sid in screen_ids:
                cur.execute(
                    "SELECT 1 FROM paper_intelligence.papers WHERE paper_id=%s", (sid,)
                )
                if not cur.fetchone():
                    orphans += 1

            # Radar mutation independence (transactional)
            cur.execute(
                "SELECT status FROM research_radar.content_items WHERE id=%s FOR UPDATE",
                (focus,),
            )
            original_status = cur.fetchone()["status"]
            mutation_results = {}
            for status in ("RELEVANT", "ENTITY_RESOLVED", "SCORED"):
                cur.execute(
                    "UPDATE research_radar.content_items SET status=%s WHERE id=%s",
                    (status, focus),
                )
                # re-run eligibility under catalog flag
                keep_pool = select_window_candidates(
                    conn,
                    date_from=day,
                    date_until=day,
                    stage_task_type="screen",
                    skip_done=False,
                )
                focus_in_screen_pool = focus in keep_pool
                focus_decision = explain_quality_routing(
                    conn, date_from=day, date_until=day, gate_percentile=GATE_PERCENTILE
                )
                focus_d = next(d for d in focus_decision if d.content_item_id == focus)
                mutation_results[status] = {
                    "in_screen_relevance_pool": focus_in_screen_pool,
                    "quality_decision": focus_d.decision,
                    "quality_reason": focus_d.reason,
                }
            # rollback mutation
            cur.execute(
                "UPDATE research_radar.content_items SET status=%s WHERE id=%s",
                (original_status, focus),
            )
            conn.commit()

        focus_d = decisions[focus]
        report = {
            "day": day,
            "flags": {
                "PI_USE_PAPERS_CATALOG": PI_USE_PAPERS_CATALOG,
                "PI_WRITE_RADAR_COMPAT": PI_WRITE_RADAR_COMPAT,
            },
            "paid_quality_executed": False,
            "focus_137619": {
                "resolved_from_pi_catalog": bool(papers),
                "relevance": rel,
                "screen_present": focus in screen_ids,
                "routing": focus_d.as_dict(),
                "selected_for_quality": focus in selected,
                "affiliation_title": aff.get("title"),
                "affiliation_arxiv": aff.get("arxiv_id"),
                "arxiv_unique_count": arxiv_n,
                "normalize_arxiv_v2_same": normalize_arxiv_id(f"{arxiv}v2") == arxiv,
            },
            "checks": {
                "one_canonical_paper": arxiv_n == 1,
                "relevance_keep": (rel or {}).get("decision") == "keep",
                "enters_router": focus_d.decision in {"selected", "not_selected"},
                "below_gate": focus_d.reason == "not_selected_below_gate_percentile",
                "orphan_screen_rows": orphans,
                "radar_mutation_independent": all(
                    v["quality_reason"] == "not_selected_below_gate_percentile"
                    and v["in_screen_relevance_pool"]
                    for v in mutation_results.values()
                ),
            },
            "radar_mutation_results": mutation_results,
            "radar_status_restored": original_status,
        }

    out = Path("reports/architecture/pi_catalog_canary_2026-09-02.json")
    out.write_text(json.dumps(report, indent=2, default=str) + "\n")
    print(json.dumps(report, indent=2, default=str))
    print("wrote", out)
    ok = all(
        [
            report["checks"]["one_canonical_paper"],
            report["checks"]["relevance_keep"],
            report["checks"]["enters_router"],
            report["checks"]["below_gate"],
            report["checks"]["orphan_screen_rows"] == 0,
            report["checks"]["radar_mutation_independent"],
        ]
    )
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
