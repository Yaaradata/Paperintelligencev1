"""Free deterministic relevance stage (ported from Research Radar).

Scores title/summary/categories; keeps RELEVANT, rejects low scores.
Rejected papers are archived to S3 (jsonl.gz) before status → REJECTED.
"""

from __future__ import annotations

import logging
import os
import re
from typing import Any

from paper_intelligence.cache.s3_archive import archive_rejected, build_rejected_record
from paper_intelligence.catalog.relevance import insert_relevance_result
from paper_intelligence.common.config import PI_USE_PAPERS_CATALOG, PI_WRITE_RADAR_COMPAT
from paper_intelligence.db import connect

log = logging.getLogger("paper_intelligence.relevance")

STAGE_NAME = "relevance"
STAGE_VERSION = "v001"
RELEVANCE_VERSION = os.getenv("RELEVANCE_VERSION", "pi-relevance-v1")
MIN_AI_RELEVANCE = float(os.getenv("MIN_AI_RELEVANCE_FOR_ENRICHMENT", "5.0"))

AI_ARXIV = {"cs.AI", "cs.CL", "cs.CV", "cs.LG", "cs.MA", "cs.RO", "stat.ML"}

TOPIC_RULES = {
    "AI agents": [
        r"\bagent(ic|s)?\b",
        r"\bmulti[- ]agent\b",
        r"\btool use\b",
        r"\bcomputer use\b",
    ],
    "LLMs / foundation models": [
        r"\bllm(s)?\b",
        r"\blarge language model",
        r"\bfoundation model",
        r"\btransformer(s)?\b",
    ],
    "Machine learning": [
        r"\bmachine learning\b",
        r"\bdeep learning\b",
        r"\bneural network",
    ],
    "Data science": [r"\bdata science\b", r"\bstatistical learning\b"],
    "Multimodal AI": [r"\bmultimodal\b", r"\bvision[- ]language\b", r"\bvlm(s)?\b"],
    "AI engineering / ML systems": [
        r"\bmlops\b",
        r"\bllmops\b",
        r"\binference serving\b",
        r"\bmodel serving\b",
        r"\bai engineering\b",
    ],
    "AI evaluation": [r"\beval(s|uation)?\b", r"\bbenchmark(s|ing)?\b", r"\bgrader(s)?\b"],
    "AI safety and security": [
        r"\balignment\b",
        r"\bai safety\b",
        r"\bmodel safety\b",
        r"\bjailbreak",
        r"\bprompt injection\b",
        r"\bai security\b",
    ],
    "Retrieval / RAG": [
        r"\brag\b",
        r"\bretrieval[- ]augmented\b",
        r"\bvector search\b",
        r"\bretrieval\b",
    ],
    "Model training, inference and efficiency": [
        r"\btraining\b",
        r"\binference\b",
        r"\bquantization\b",
        r"\bdistillation\b",
        r"\bmixture of experts\b",
        r"\bmoe\b",
    ],
    "Applied AI": [r"\bapplied ai\b", r"\bai application", r"\bgenerative ai\b"],
    "Human-AI interaction": [
        r"\bhuman[- ]ai\b",
        r"\bhuman computer interaction\b",
        r"\bhci\b",
    ],
    "AI product and experimentation": [
        r"\ba/b test",
        r"\bexperimentation\b",
        r"\bai product\b",
        r"\bproduct management\b",
    ],
}


def score_relevance(
    title: str | None,
    summary: str | None,
    categories: list[str] | None,
    source_type: str | None,
) -> tuple[float, str | None, list[str], str]:
    text = f"{title or ''}\n{summary or ''}".lower()
    hits: dict[str, int] = {}
    for topic, patterns in TOPIC_RULES.items():
        n = sum(1 for p in patterns if re.search(p, text, re.I))
        if n:
            hits[topic] = n
    score = min(6.5, 3.0 + sum(hits.values()) * 0.7) if hits else 0.0
    if any(c in AI_ARXIV for c in (categories or [])):
        score += 2.0
    if source_type in {"arxiv", "research_paper", "company_research"}:
        score += 0.8
    score = min(10.0, round(score, 2))
    ordered = sorted(hits.items(), key=lambda x: (-x[1], x[0]))
    primary = ordered[0][0] if ordered else None
    secondary = [name for name, _ in ordered[1:4]]
    reasons: list[str] = []
    if primary:
        reasons.append(f"matched topic '{primary}'")
    if any(c in AI_ARXIV for c in (categories or [])):
        reasons.append("AI/ML arXiv category")
    if source_type in {"arxiv", "research_paper", "company_research"}:
        reasons.append(f"source prior={source_type}")
    return score, primary, secondary, "; ".join(reasons) or "no strong deterministic AI signal"


def _store_relevance(
    conn: Any,
    content_id: int,
    score: float,
    primary: str | None,
    secondary: list[str],
    reason: str,
) -> None:
    """Best-effort Radar score/topic dual-write. Must not gate PI success."""
    if not PI_WRITE_RADAR_COMPAT:
        return
    import json

    try:
        with conn.cursor() as cur:
            for idx, name in enumerate([x for x in [primary, *secondary] if x]):
                cur.execute(
                    """
                    INSERT INTO research_radar.content_topics(
                        content_id, topic_id, is_primary, confidence, reason
                    )
                    SELECT %s, topic_id, %s, %s, %s
                    FROM research_radar.topics WHERE canonical_name = %s
                    ON CONFLICT (content_id, topic_id) DO UPDATE SET
                        is_primary = EXCLUDED.is_primary,
                        confidence = EXCLUDED.confidence,
                        reason = EXCLUDED.reason
                    """,
                    (content_id, idx == 0, min(1.0, score / 10), reason, name),
                )
            cur.execute(
                """
                INSERT INTO research_radar.content_scores(content_id, ai_relevance, scoring_reason)
                VALUES (%s, %s, %s::jsonb)
                ON CONFLICT (content_id) DO UPDATE SET
                    ai_relevance = EXCLUDED.ai_relevance,
                    scoring_reason = research_radar.content_scores.scoring_reason
                        || EXCLUDED.scoring_reason,
                    scored_at = NOW()
                """,
                (
                    content_id,
                    score,
                    json.dumps(
                        {"relevance_reason": reason, "via": "paper_intelligence"}
                    ),
                ),
            )
    except Exception:  # noqa: BLE001
        log.exception(
            "Radar compat content_scores write failed id=%s (PI relevance retained)",
            content_id,
        )


def _set_status(conn: Any, content_id: int, status: str) -> None:
    """Best-effort Radar compatibility write. Must not gate PI success."""
    if not PI_WRITE_RADAR_COMPAT:
        return
    try:
        conn.execute(
            "UPDATE research_radar.content_items SET status=%s, modified_at=NOW() WHERE id=%s",
            (status, content_id),
        )
    except Exception:  # noqa: BLE001
        log.exception("Radar compat status write failed id=%s status=%s", content_id, status)


def _set_relevance_version(conn: Any, content_id: int, version: str) -> None:
    if not PI_WRITE_RADAR_COMPAT:
        return
    try:
        conn.execute(
            """
            UPDATE research_radar.content_items
            SET relevance_version=%s, modified_at=NOW()
            WHERE id=%s
            """,
            (version, content_id),
        )
    except Exception:  # noqa: BLE001
        log.exception("Radar compat relevance_version write failed id=%s", content_id)


def _write_pi_relevance(
    conn: Any,
    *,
    paper_id: int,
    decision: str,
    score: float,
    reason: str,
    run_id: str | None,
) -> None:
    """Authoritative PI relevance append. Raises on failure."""
    insert_relevance_result(
        conn,
        paper_id=paper_id,
        decision=decision,
        score=score,
        reason=reason,
        method="deterministic",
        stage_version=STAGE_VERSION,
        policy_version="v001",
        run_id=run_id,
    )


def _select_candidates_radar(
    conn: Any,
    date_from: str,
    date_until: str,
    *,
    limit: int | None,
    reprocess: bool,
) -> list[dict[str, Any]]:
    """Legacy Radar-status candidate pool (rollback path only)."""
    statuses = ("INGESTED", "RELEVANCE_CHECKED", "ERROR")
    if reprocess:
        statuses = ("INGESTED", "RELEVANCE_CHECKED", "ERROR", "REJECTED")

    with conn.cursor() as cur:
        cur.execute(
            """
            SELECT ci.id, ci.title, ci.summary, ci.categories_raw, ci.source_type,
                   ci.canonical_url, ci.status, ci.relevance_version,
                   pm.arxiv_id,
                   COALESCE(pm.abstract, ci.summary, '') AS abstract
            FROM research_radar.content_items ci
            LEFT JOIN research_radar.paper_metadata pm ON pm.content_id = ci.id
            WHERE ci.status = ANY(%s)
              AND ci.published_at >= %s::timestamptz
              AND ci.published_at < (%s::timestamptz + interval '1 day')
            ORDER BY ci.published_at DESC NULLS LAST, ci.id DESC
            LIMIT %s
            """,
            (list(statuses), date_from, date_until, limit or 100_000),
        )
        rows = [dict(r) for r in cur.fetchall()]

    if reprocess:
        rows = [
            r
            for r in rows
            if r.get("relevance_version") is None
            or r["relevance_version"] != RELEVANCE_VERSION
            or r.get("status") == "REJECTED"
        ][: limit or 100_000]
    return rows


def _select_candidates_pi(
    conn: Any,
    date_from: str,
    date_until: str,
    *,
    limit: int | None,
    reprocess: bool,
) -> list[dict[str, Any]]:
    """PI-native candidates: papers lacking a current valid relevance result.

    Does NOT consult research_radar.content_items.status.
    """
    with conn.cursor() as cur:
        if reprocess:
            cur.execute(
                """
                WITH windowed AS (
                  SELECT p.paper_id AS id, p.title, p.summary, p.abstract,
                         p.categories AS categories_raw, p.source_type,
                         p.canonical_url, p.arxiv_id,
                         COALESCE(p.abstract, p.summary, '') AS abstract_text
                  FROM paper_intelligence.papers p
                  WHERE p.published_at >= %s::timestamptz
                    AND p.published_at < (%s::timestamptz + interval '1 day')
                ),
                latest AS (
                  SELECT DISTINCT ON (r.paper_id)
                         r.paper_id, r.stage_version, r.policy_version, r.method
                  FROM paper_intelligence.paper_relevance_results r
                  JOIN windowed w ON w.id = r.paper_id
                  ORDER BY r.paper_id, r.created_at DESC, r.relevance_id DESC
                )
                SELECT w.id, w.title, w.summary, w.categories_raw, w.source_type,
                       w.canonical_url, w.arxiv_id, w.abstract_text AS abstract
                FROM windowed w
                LEFT JOIN latest l ON l.paper_id = w.id
                WHERE l.paper_id IS NULL
                   OR COALESCE(l.stage_version, '') <> %s
                   OR COALESCE(l.policy_version, '') <> 'v001'
                   OR l.method = 'migrated_legacy_state'
                ORDER BY w.id DESC
                LIMIT %s
                """,
                (date_from, date_until, STAGE_VERSION, limit or 100_000),
            )
        else:
            cur.execute(
                """
                SELECT p.paper_id AS id, p.title, p.summary, p.categories AS categories_raw,
                       p.source_type, p.canonical_url, p.arxiv_id,
                       COALESCE(p.abstract, p.summary, '') AS abstract
                FROM paper_intelligence.papers p
                WHERE p.published_at >= %s::timestamptz
                  AND p.published_at < (%s::timestamptz + interval '1 day')
                  AND NOT EXISTS (
                    SELECT 1 FROM paper_intelligence.paper_relevance_results r
                    WHERE r.paper_id = p.paper_id
                  )
                ORDER BY p.published_at DESC NULLS LAST, p.paper_id DESC
                LIMIT %s
                """,
                (date_from, date_until, limit or 100_000),
            )
        return [dict(r) for r in cur.fetchall()]


def run_window(
    date_from: str,
    date_until: str,
    *,
    conn: Any | None = None,
    limit: int | None = None,
    dry_run: bool = False,
    reprocess: bool = False,
    run_id: str | None = None,
) -> dict[str, Any]:
    """Score relevance for papers in [date_from, date_until].

    Catalog mode: candidates from ``paper_intelligence.papers`` with no current
    valid PI relevance result. Radar status is never an eligibility gate.
    """
    owns = conn is None
    conn = conn or connect()
    try:
        if PI_USE_PAPERS_CATALOG:
            rows = _select_candidates_pi(
                conn, date_from, date_until, limit=limit, reprocess=reprocess
            )
        else:
            rows = _select_candidates_radar(
                conn, date_from, date_until, limit=limit, reprocess=reprocess
            )

        kept = rejected = errors = 0
        reject_records: list[dict[str, Any]] = []
        reject_ids: list[int] = []

        if dry_run:
            for row in rows:
                cats = row.get("categories_raw") or []
                if isinstance(cats, str):
                    cats = [cats]
                score, _, _, _ = score_relevance(
                    row["title"], row.get("summary") or "", cats, row.get("source_type")
                )
                if score < MIN_AI_RELEVANCE:
                    rejected += 1
                else:
                    kept += 1
            return {
                "dry_run": True,
                "candidates": len(rows),
                "would_keep": kept,
                "would_reject": rejected,
                "min_ai_relevance": MIN_AI_RELEVANCE,
                "relevance_version": RELEVANCE_VERSION,
                "catalog_mode": PI_USE_PAPERS_CATALOG,
            }

        for row in rows:
            paper_id = int(row["id"])
            try:
                cats = row.get("categories_raw") or []
                if isinstance(cats, str):
                    cats = [cats]
                elif isinstance(cats, dict):
                    cats = list(cats.values()) if cats else []
                score, primary, secondary, reason = score_relevance(
                    row["title"],
                    row.get("summary") or row.get("abstract") or "",
                    cats,
                    row.get("source_type"),
                )
                # Authoritative PI write first.
                if score < MIN_AI_RELEVANCE:
                    _write_pi_relevance(
                        conn,
                        paper_id=paper_id,
                        decision="reject",
                        score=score,
                        reason=reason or "low_ai_relevance",
                        run_id=run_id,
                    )
                    reject_records.append(
                        build_rejected_record(
                            content_id=paper_id,
                            canonical_url=row.get("canonical_url") or "",
                            title=row["title"] or "",
                            abstract=row.get("abstract") or row.get("summary") or "",
                            categories=cats if isinstance(cats, list) else [],
                            relevance_score=score,
                            primary_topic=primary,
                            rejection_reason="low_ai_relevance",
                            relevance_version=RELEVANCE_VERSION,
                            arxiv_id=row.get("arxiv_id"),
                        )
                    )
                    reject_ids.append(paper_id)
                    rejected += 1
                else:
                    _write_pi_relevance(
                        conn,
                        paper_id=paper_id,
                        decision="keep",
                        score=score,
                        reason=reason or "deterministic_keep",
                        run_id=run_id,
                    )
                    kept += 1
                # Best-effort Radar dual-write (may no-op for PI-only papers).
                _store_relevance(conn, paper_id, score, primary, secondary, reason)
                _set_status(conn, paper_id, "RELEVANCE_CHECKED")
                _set_relevance_version(conn, paper_id, RELEVANCE_VERSION)
                if score >= MIN_AI_RELEVANCE:
                    _set_status(conn, paper_id, "RELEVANT")
                conn.commit()
            except Exception:  # noqa: BLE001
                log.exception("relevance failed id=%s", paper_id)
                try:
                    conn.rollback()
                except Exception:  # noqa: BLE001
                    pass
                _set_status(conn, paper_id, "ERROR")
                errors += 1
                try:
                    conn.commit()
                except Exception:  # noqa: BLE001
                    pass

        archive_info = None
        if reject_records:
            try:
                archive_info = archive_rejected(
                    conn,
                    run_id or "00000000-0000-0000-0000-000000000000",
                    STAGE_NAME,
                    reject_records,
                )
            except Exception:  # noqa: BLE001
                log.exception("S3 reject archive failed (PI relevance retained)")
        for cid in reject_ids:
            _set_status(conn, cid, "REJECTED")
        conn.commit()

        return {
            "candidates": len(rows),
            "kept": kept,
            "rejected": rejected,
            "errors": errors,
            "min_ai_relevance": MIN_AI_RELEVANCE,
            "relevance_version": RELEVANCE_VERSION,
            "s3_archive": archive_info,
            "catalog_mode": PI_USE_PAPERS_CATALOG,
        }
    finally:
        if owns:
            conn.close()
