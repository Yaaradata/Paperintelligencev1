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
from paper_intelligence.common.config import PI_WRITE_RADAR_COMPAT
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
    import json

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
            (content_id, score, json.dumps({"relevance_reason": reason, "via": "paper_intelligence"})),
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
    """Score relevance for ingested papers in [date_from, date_until]."""
    owns = conn is None
    conn = conn or connect()
    try:
        statuses = ("INGESTED", "RELEVANCE_CHECKED", "ERROR")
        if reprocess:
            statuses = ("INGESTED", "RELEVANCE_CHECKED", "ERROR", "REJECTED")

        with conn.cursor() as cur:
            cur.execute(
                f"""
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

        kept = rejected = errors = 0
        reject_records: list[dict[str, Any]] = []
        reject_ids: list[int] = []

        if dry_run:
            for row in rows:
                cats = row.get("categories_raw") or []
                if isinstance(cats, str):
                    cats = [cats]
                score, _, _, _ = score_relevance(
                    row["title"], row.get("summary") or "", cats, row["source_type"]
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
            }

        for row in rows:
            try:
                cats = row.get("categories_raw") or []
                if isinstance(cats, str):
                    cats = [cats]
                score, primary, secondary, reason = score_relevance(
                    row["title"], row.get("summary") or "", cats, row["source_type"]
                )
                _store_relevance(conn, row["id"], score, primary, secondary, reason)
                if score < MIN_AI_RELEVANCE:
                    _write_pi_relevance(
                        conn,
                        paper_id=int(row["id"]),
                        decision="reject",
                        score=score,
                        reason=reason or "low_ai_relevance",
                        run_id=run_id,
                    )
                    _set_status(conn, row["id"], "RELEVANCE_CHECKED")
                    _set_relevance_version(conn, row["id"], RELEVANCE_VERSION)
                    reject_records.append(
                        build_rejected_record(
                            content_id=row["id"],
                            canonical_url=row.get("canonical_url") or "",
                            title=row["title"] or "",
                            abstract=row.get("abstract") or row.get("summary") or "",
                            categories=cats,
                            relevance_score=score,
                            primary_topic=primary,
                            rejection_reason="low_ai_relevance",
                            relevance_version=RELEVANCE_VERSION,
                            arxiv_id=row.get("arxiv_id"),
                        )
                    )
                    reject_ids.append(int(row["id"]))
                    rejected += 1
                else:
                    _write_pi_relevance(
                        conn,
                        paper_id=int(row["id"]),
                        decision="keep",
                        score=score,
                        reason=reason or "deterministic_keep",
                        run_id=run_id,
                    )
                    _set_status(conn, row["id"], "RELEVANCE_CHECKED")
                    _set_relevance_version(conn, row["id"], RELEVANCE_VERSION)
                    _set_status(conn, row["id"], "RELEVANT")
                    kept += 1
            except Exception as exc:  # noqa: BLE001
                log.exception("relevance failed id=%s", row["id"])
                _set_status(conn, row["id"], "ERROR")
                errors += 1
                conn.commit()

        archive_info = None
        if reject_records:
            archive_info = archive_rejected(
                conn,
                run_id or "00000000-0000-0000-0000-000000000000",
                STAGE_NAME,
                reject_records,
            )
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
        }
    finally:
        if owns:
            conn.close()
