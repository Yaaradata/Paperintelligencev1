#!/usr/bin/env python3
"""PI-only paper independence test (transactional; rolls back).

Creates a paper in paper_intelligence.papers with NO Radar row, then verifies
catalog-mode orchestration can see it for relevance and downstream readers.
Does not execute paid stages.
"""

from __future__ import annotations

import json
import os
import sys
import uuid
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

os.environ["PI_USE_PAPERS_CATALOG"] = "1"
os.environ["PI_WRITE_RADAR_COMPAT"] = "0"  # force no Radar writes for this test

import importlib

import paper_intelligence.common.config as cfg
import paper_intelligence.db.results as results_mod
import paper_intelligence.relevance.stage as relevance_stage

importlib.reload(cfg)
importlib.reload(results_mod)
importlib.reload(relevance_stage)

from paper_intelligence.catalog.ingest import upsert_paper_from_oai  # noqa: E402
from paper_intelligence.catalog.relevance import (  # noqa: E402
    current_relevance,
    insert_relevance_result,
)
from paper_intelligence.db import connect  # noqa: E402
from paper_intelligence.db.results import select_window_candidates  # noqa: E402
from paper_intelligence.relevance.stage import _select_candidates_pi  # noqa: E402

OUT = ROOT / "reports" / "architecture" / "pi_only_paper_independence.json"
FAKE_ARXIV = f"9999.{os.getpid() % 100000:05d}"


def main() -> int:
    report: dict = {"fake_arxiv_id": FAKE_ARXIV, "checks": {}}
    with connect() as conn:
        conn.execute("BEGIN")
        try:
            rec = {
                "identifier": f"oai:arXiv.org:{FAKE_ARXIV}",
                "datestamp": "2026-09-02",
                "deleted": False,
                "arxiv_id": FAKE_ARXIV,
                "created": "2026-09-02T00:00:00+00:00",
                "updated": None,
                "title": "PI-only independence canary paper on large language models",
                "abstract": (
                    "A synthetic paper about LLMs, agents, and machine learning "
                    "used only for catalog independence testing."
                ),
                "categories": ["cs.AI", "cs.LG"],
                "doi": None,
                "journal_ref": None,
                "authors": ["Independence Tester"],
                "authors_structured": [
                    {
                        "position": 1,
                        "name": "Independence Tester",
                        "affiliations": [],
                    }
                ],
            }
            paper_id, is_new = upsert_paper_from_oai(conn, rec, set_spec="cs")
            report["paper_id"] = paper_id
            report["checks"]["created_new"] = is_new

            # No Radar row
            with conn.cursor() as cur:
                cur.execute(
                    "SELECT 1 FROM research_radar.content_items WHERE id = %s",
                    (paper_id,),
                )
                radar_by_id = cur.fetchone()
                cur.execute(
                    """
                    SELECT 1 FROM research_radar.content_items
                    WHERE canonical_url = %s
                    """,
                    (f"https://arxiv.org/abs/{FAKE_ARXIV}",),
                )
                radar_by_url = cur.fetchone()
            report["checks"]["no_radar_row"] = radar_by_id is None and radar_by_url is None

            # Relevance candidate discovery includes it
            cands = _select_candidates_pi(
                conn, "2026-09-02", "2026-09-02", limit=100_000, reprocess=False
            )
            cand_ids = {int(r["id"]) for r in cands}
            report["checks"]["selected_for_relevance"] = paper_id in cand_ids

            # Write PI relevance keep (native, free)
            insert_relevance_result(
                conn,
                paper_id=paper_id,
                decision="keep",
                score=8.5,
                reason="pi_only_independence_test",
                method="deterministic",
                stage_version="v001",
                policy_version="v001",
            )
            cur_rel = current_relevance(conn, paper_id)
            report["checks"]["has_pi_relevance_keep"] = (
                cur_rel is not None and cur_rel["decision"] == "keep"
            )

            # No longer a relevance candidate
            cands2 = _select_candidates_pi(
                conn, "2026-09-02", "2026-09-02", limit=100_000, reprocess=False
            )
            report["checks"]["not_repeated_after_result"] = paper_id not in {
                int(r["id"]) for r in cands2
            }

            # Screen eligibility via PI keep
            screen_ids = select_window_candidates(
                conn,
                date_from="2026-09-02",
                date_until="2026-09-02",
                stage_task_type="screen",
                skip_done=False,
            )
            report["checks"]["eligible_for_screen"] = paper_id in set(screen_ids)

            # Report/editorial reader can see metadata
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT paper_id, title, arxiv_id FROM paper_intelligence.papers
                    WHERE paper_id = %s
                    """,
                    (paper_id,),
                )
                meta = dict(cur.fetchone())
            report["checks"]["reader_finds_paper"] = meta.get("arxiv_id") == FAKE_ARXIV

            report["passed"] = all(
                [
                    report["checks"]["created_new"],
                    report["checks"]["no_radar_row"],
                    report["checks"]["selected_for_relevance"],
                    report["checks"]["has_pi_relevance_keep"],
                    report["checks"]["not_repeated_after_result"],
                    report["checks"]["eligible_for_screen"],
                    report["checks"]["reader_finds_paper"],
                ]
            )
            report["note"] = (
                "Stopped before paid stages. Fixture rolled back; no permanent writes."
            )
        finally:
            conn.rollback()

    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(report, indent=2, default=str) + "\n")
    print(json.dumps(report, indent=2, default=str))
    return 0 if report.get("passed") else 1


if __name__ == "__main__":
    raise SystemExit(main())
