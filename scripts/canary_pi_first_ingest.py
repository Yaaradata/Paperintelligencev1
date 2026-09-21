#!/usr/bin/env python3
"""Real PI-first ingest path canary (transactional where possible).

Validates:
- PI papers write first
- PI ingest checkpoint controls resume
- Radar checkpoint does NOT control PI resume
- Radar compat failure does not roll back PI paper
- arXiv version rediscovery does not duplicate

Does not execute paid stages. Uses synthetic OAI records with cleanup.
"""

from __future__ import annotations

import json
import os
import sys
import uuid
from datetime import date
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

os.environ["PI_USE_PAPERS_CATALOG"] = "1"
os.environ["PI_WRITE_RADAR_COMPAT"] = "1"

import importlib

import paper_intelligence.common.config as cfg
import paper_intelligence.ingest.arxiv_oai as oai

importlib.reload(cfg)
importlib.reload(oai)

from paper_intelligence.catalog.ingest import (  # noqa: E402
    checkpoint_status_pi,
    finish_checkpoint_pi,
    start_checkpoint_pi,
    upsert_paper_from_oai,
)
from paper_intelligence.catalog.normalize import normalize_arxiv_id  # noqa: E402
from paper_intelligence.db import connect  # noqa: E402
from paper_intelligence.relevance.stage import _select_candidates_pi  # noqa: E402

OUT = ROOT / "reports" / "architecture" / "pi_first_ingest_canary.json"
FAKE = f"8888.{os.getpid() % 100000:05d}"
DAY = date(2026, 9, 2)


def _rec(arxiv: str, version: str | None = None) -> dict:
    aid = f"{arxiv}{version}" if version else arxiv
    return {
        "identifier": f"oai:arXiv.org:{arxiv}",
        "datestamp": DAY.isoformat(),
        "deleted": False,
        "arxiv_id": aid,
        "created": "2026-09-02T12:00:00+00:00",
        "updated": "2026-09-02T18:00:00+00:00",
        "title": "PI-first ingest canary on large language models and agents",
        "abstract": "Synthetic canary abstract about LLMs, agents, and machine learning.",
        "categories": ["cs.AI", "cs.LG"],
        "doi": None,
        "journal_ref": None,
        "authors": ["Canary Author"],
        "authors_structured": [{"position": 1, "name": "Canary Author", "affiliations": []}],
    }


def main() -> int:
    report: dict = {"fake_arxiv": FAKE, "checks": {}}
    with connect() as conn:
        # --- A. PI-first upsert + Radar failure injection ---
        conn.execute("BEGIN")
        try:
            paper_id, is_new = upsert_paper_from_oai(conn, _rec(FAKE), set_spec="cs")
            report["paper_id"] = paper_id
            report["checks"]["pi_write_first_new"] = is_new

            # Inject Radar failure after PI success
            with patch.object(oai, "upsert_item", side_effect=RuntimeError("radar down")):
                ok = oai._radar_compat_write(conn, _rec(FAKE), paper_id)
            report["checks"]["radar_compat_failure_swallowed"] = ok is False

            still = conn.execute(
                "SELECT paper_id, arxiv_id FROM paper_intelligence.papers WHERE paper_id=%s",
                (paper_id,),
            ).fetchone()
            report["checks"]["pi_retained_after_radar_failure"] = (
                still is not None and still["arxiv_id"] == normalize_arxiv_id(FAKE)
            )

            # Version rediscovery
            pid2, is_new2 = upsert_paper_from_oai(conn, _rec(FAKE, "v2"), set_spec="cs")
            n = conn.execute(
                "SELECT count(*) n FROM paper_intelligence.papers WHERE arxiv_id=%s",
                (normalize_arxiv_id(FAKE),),
            ).fetchone()["n"]
            report["checks"]["version_rediscovery_same_id"] = pid2 == paper_id and not is_new2
            report["checks"]["no_duplicate_arxiv"] = int(n) == 1

            # Relevance candidate visibility (no prior relevance)
            cands = _select_candidates_pi(
                conn, DAY.isoformat(), DAY.isoformat(), limit=100000, reprocess=False
            )
            report["checks"]["visible_to_relevance_selector"] = paper_id in {
                int(r["id"]) for r in cands
            }
        finally:
            conn.rollback()

        # --- B. Checkpoint resume: PI COMPLETE vs Radar COMPLETE mismatch ---
        conn.execute("BEGIN")
        try:
            # Ensure clean slate for fake window markers
            src = "arxiv_oai_canary_test"
            wf, wu = date(2099, 1, 1), date(2099, 1, 7)
            # Mark Radar COMPLETE (would skip legacy path)
            try:
                oai.start_checkpoint(conn, src, "cs", wf, wu)
                oai.finish_checkpoint(
                    conn,
                    src,
                    "cs",
                    wf,
                    wu,
                    status="COMPLETE",
                    stats=oai.WindowStats(),
                )
            except Exception as exc:  # noqa: BLE001
                report["checks"]["radar_checkpoint_setup_error"] = str(exc)

            # PI has NO complete checkpoint → should NOT skip when catalog mode
            pi_status = checkpoint_status_pi(conn, src, "cs", wf, wu)
            radar_status = oai.checkpoint_status(conn, src, "cs", wf, wu)
            report["checks"]["radar_complete_pi_absent"] = (
                radar_status == "COMPLETE" and pi_status != "COMPLETE"
            )

            # Start + finish PI checkpoint; now PI should skip
            ck = start_checkpoint_pi(conn, src, "cs", wf, wu)
            finish_checkpoint_pi(conn, ck, status="COMPLETE", records_kept=1)
            pi_status2 = checkpoint_status_pi(conn, src, "cs", wf, wu)
            report["checks"]["pi_checkpoint_controls_resume"] = pi_status2 == "COMPLETE"
            report["checks"]["radar_does_not_control_pi_resume"] = (
                report["checks"]["radar_complete_pi_absent"]
                and report["checks"]["pi_checkpoint_controls_resume"]
            )
        finally:
            conn.rollback()

    report["passed"] = all(
        [
            report["checks"].get("pi_write_first_new"),
            report["checks"].get("radar_compat_failure_swallowed"),
            report["checks"].get("pi_retained_after_radar_failure"),
            report["checks"].get("version_rediscovery_same_id"),
            report["checks"].get("no_duplicate_arxiv"),
            report["checks"].get("visible_to_relevance_selector"),
            report["checks"].get("radar_does_not_control_pi_resume"),
        ]
    )
    report["paid_calls_executed"] = 0
    OUT.write_text(json.dumps(report, indent=2, default=str) + "\n")
    print(json.dumps(report, indent=2, default=str))
    return 0 if report["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
