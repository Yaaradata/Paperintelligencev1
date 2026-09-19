"""HF Daily Papers enrichment — join curation signals onto existing arXiv papers.

Does not create new content_items. Pulls Daily Papers by date, matches on
arxiv_id, optionally refreshes Paper Page detail (models/datasets/spaces/GitHub).
"""

from __future__ import annotations

import logging
from datetime import date, datetime, timedelta, timezone
from typing import Any

from paper_intelligence.db import connect
from paper_intelligence.external import huggingface as hf_client

log = logging.getLogger("paper_intelligence.hf_signals")

STAGE_NAME = "hf_signals"
STAGE_VERSION = "v001"

# HF allows Daily Papers submission within ~14 days of arXiv publish.
FEATURE_LAG_DAYS = 14

UPSERT_SQL = """
INSERT INTO paper_intelligence.paper_hf_signals (
    content_item_id, arxiv_id, hf_featured, hf_featured_date, hf_upvotes,
    hf_daily_upvote_rank, hf_num_comments, hf_submitter,
    linked_models_count, linked_datasets_count, linked_spaces_count,
    github_url, github_stars, project_url, hf_title,
    pulled_at, raw_response_path, stage_version, run_id, metadata
) VALUES (
    %s, %s, %s, %s, %s,
    %s, %s, %s,
    %s, %s, %s,
    %s, %s, %s, %s,
    NOW(), %s, %s, %s, %s::jsonb
)
ON CONFLICT (content_item_id) DO UPDATE SET
    arxiv_id = EXCLUDED.arxiv_id,
    hf_featured = EXCLUDED.hf_featured,
    hf_featured_date = COALESCE(EXCLUDED.hf_featured_date, paper_intelligence.paper_hf_signals.hf_featured_date),
    hf_upvotes = COALESCE(EXCLUDED.hf_upvotes, paper_intelligence.paper_hf_signals.hf_upvotes),
    hf_daily_upvote_rank = COALESCE(EXCLUDED.hf_daily_upvote_rank, paper_intelligence.paper_hf_signals.hf_daily_upvote_rank),
    hf_num_comments = COALESCE(EXCLUDED.hf_num_comments, paper_intelligence.paper_hf_signals.hf_num_comments),
    hf_submitter = COALESCE(EXCLUDED.hf_submitter, paper_intelligence.paper_hf_signals.hf_submitter),
    linked_models_count = COALESCE(EXCLUDED.linked_models_count, paper_intelligence.paper_hf_signals.linked_models_count),
    linked_datasets_count = COALESCE(EXCLUDED.linked_datasets_count, paper_intelligence.paper_hf_signals.linked_datasets_count),
    linked_spaces_count = COALESCE(EXCLUDED.linked_spaces_count, paper_intelligence.paper_hf_signals.linked_spaces_count),
    github_url = COALESCE(EXCLUDED.github_url, paper_intelligence.paper_hf_signals.github_url),
    github_stars = COALESCE(EXCLUDED.github_stars, paper_intelligence.paper_hf_signals.github_stars),
    project_url = COALESCE(EXCLUDED.project_url, paper_intelligence.paper_hf_signals.project_url),
    hf_title = COALESCE(EXCLUDED.hf_title, paper_intelligence.paper_hf_signals.hf_title),
    pulled_at = NOW(),
    raw_response_path = COALESCE(EXCLUDED.raw_response_path, paper_intelligence.paper_hf_signals.raw_response_path),
    stage_version = EXCLUDED.stage_version,
    run_id = EXCLUDED.run_id,
    metadata = paper_intelligence.paper_hf_signals.metadata || EXCLUDED.metadata
"""

UPDATE_CURRENT_SQL = """
UPDATE paper_intelligence.paper_intelligence_current c
SET hf_featured = s.hf_featured,
    hf_upvotes = s.hf_upvotes,
    hf_featured_date = s.hf_featured_date,
    updated_at = NOW()
FROM paper_intelligence.paper_hf_signals s
WHERE c.content_item_id = s.content_item_id
  AND s.content_item_id = ANY(%s)
"""


def _parse_day(value: str | date) -> date:
    if isinstance(value, date):
        return value
    return date.fromisoformat(str(value)[:10])


def _submitter_name(obj: Any) -> str | None:
    if not isinstance(obj, dict):
        return None
    return obj.get("name") or obj.get("fullname") or obj.get("user")


def _parse_featured_date(value: Any) -> date | None:
    if not value:
        return None
    text = str(value)
    try:
        return date.fromisoformat(text[:10])
    except ValueError:
        return None


def _normalize_daily_entry(entry: dict[str, Any], *, day: str, rank: int | None) -> dict[str, Any]:
    paper = entry.get("paper") if isinstance(entry.get("paper"), dict) else {}
    arxiv_id = (paper.get("id") or "").strip()
    submitter = _submitter_name(entry.get("submittedBy")) or _submitter_name(
        paper.get("submittedOnDailyBy")
    )
    featured_date = _parse_featured_date(
        paper.get("submittedOnDailyAt") or entry.get("publishedAt") or day
    )
    return {
        "arxiv_id": arxiv_id,
        "hf_featured": True,
        "hf_featured_date": featured_date,
        "hf_upvotes": paper.get("upvotes"),
        "hf_daily_upvote_rank": rank,
        "hf_num_comments": entry.get("numComments"),
        "hf_submitter": submitter,
        "github_url": paper.get("githubRepo"),
        "github_stars": paper.get("githubStars"),
        "project_url": paper.get("projectPage"),
        "hf_title": paper.get("title") or entry.get("title"),
        "daily_day": day,
    }


def _merge_detail(base: dict[str, Any], detail: dict[str, Any]) -> dict[str, Any]:
    out = dict(base)
    if not detail:
        return out
    if detail.get("upvotes") is not None:
        out["hf_upvotes"] = detail.get("upvotes")
    if detail.get("submittedOnDailyAt"):
        out["hf_featured"] = True
        out["hf_featured_date"] = _parse_featured_date(detail.get("submittedOnDailyAt"))
    if not out.get("hf_submitter"):
        out["hf_submitter"] = _submitter_name(detail.get("submittedOnDailyBy"))
    out["linked_models_count"] = detail.get("numTotalModels")
    out["linked_datasets_count"] = detail.get("numTotalDatasets")
    out["linked_spaces_count"] = detail.get("numTotalSpaces")
    out["github_url"] = detail.get("githubRepo") or out.get("github_url")
    out["github_stars"] = detail.get("githubStars") if detail.get("githubStars") is not None else out.get("github_stars")
    out["project_url"] = detail.get("projectPage") or out.get("project_url")
    out["hf_title"] = detail.get("title") or out.get("hf_title")
    return out


def collect_daily_index(
    date_from: date,
    date_until: date,
    *,
    conn: Any | None = None,
    run_id: str | None = None,
    stage_run_id: str | None = None,
) -> dict[str, dict[str, Any]]:
    """arxiv_id → best daily-paper signal across the date range (+ lag buffer)."""
    today = datetime.now(timezone.utc).date()
    end = min(date_until + timedelta(days=FEATURE_LAG_DAYS), today)
    if end < date_from:
        end = date_from
    index: dict[str, dict[str, Any]] = {}
    day = date_from
    days_fetched = 0
    while day <= end:
        page = hf_client.list_daily_papers(
            day, conn=conn, run_id=run_id, stage_run_id=stage_run_id
        )
        days_fetched += 1
        if page.error:
            log.warning("hf daily_papers failed day=%s err=%s", day, page.error)
            day += timedelta(days=1)
            continue
        # Rank within the day by upvotes (HF date+trending ignores the date).
        ranked_entries: list[tuple[int, dict[str, Any]]] = []
        for entry in page.papers or []:
            if not isinstance(entry, dict):
                continue
            paper = entry.get("paper") if isinstance(entry.get("paper"), dict) else {}
            upvotes = paper.get("upvotes")
            try:
                score = int(upvotes) if upvotes is not None else -1
            except (TypeError, ValueError):
                score = -1
            ranked_entries.append((score, entry))
        ranked_entries.sort(key=lambda pair: (-pair[0], (pair[1].get("paper") or {}).get("id") or ""))
        for rank, (_score, entry) in enumerate(ranked_entries, start=1):
            norm = _normalize_daily_entry(entry, day=page.day, rank=rank)
            aid = norm["arxiv_id"]
            if not aid:
                continue
            prev = index.get(aid)
            if prev is None:
                index[aid] = norm
                continue
            # Prefer higher upvotes; then better (lower) day-rank.
            prev_up = prev.get("hf_upvotes") or -1
            new_up = norm.get("hf_upvotes") or -1
            if new_up > prev_up:
                index[aid] = norm
            elif new_up == prev_up:
                prev_rank = prev.get("hf_daily_upvote_rank") or 10_000
                new_rank = norm.get("hf_daily_upvote_rank") or 10_000
                if new_rank < prev_rank:
                    index[aid] = norm
        day += timedelta(days=1)
    log.info(
        "hf daily index days=%d unique_arxiv=%d range=%s..%s",
        days_fetched,
        len(index),
        date_from,
        end,
    )
    return index


def _lookup_content_items(conn: Any, arxiv_ids: list[str]) -> dict[str, int]:
    if not arxiv_ids:
        return {}
    from paper_intelligence.catalog.normalize import normalize_arxiv_id
    from paper_intelligence.common.config import PI_USE_PAPERS_CATALOG

    with conn.cursor() as cur:
        if PI_USE_PAPERS_CATALOG:
            norms = [normalize_arxiv_id(a) for a in arxiv_ids]
            norms = [a for a in norms if a]
            cur.execute(
                """
                SELECT arxiv_id, paper_id AS content_id
                FROM paper_intelligence.papers
                WHERE arxiv_id = ANY(%s)
                """,
                (norms,),
            )
            # Map both normalized and original request ids when possible
            by_norm = {str(r["arxiv_id"]): int(r["content_id"]) for r in cur.fetchall()}
            out: dict[str, int] = {}
            for raw in arxiv_ids:
                n = normalize_arxiv_id(raw)
                if n and n in by_norm:
                    out[str(raw)] = by_norm[n]
                    out[n] = by_norm[n]
            return out
        cur.execute(
            """
            SELECT pm.arxiv_id, pm.content_id
            FROM research_radar.paper_metadata pm
            WHERE pm.arxiv_id = ANY(%s)
            """,
            (arxiv_ids,),
        )
        return {str(r["arxiv_id"]): int(r["content_id"]) for r in cur.fetchall() if r["arxiv_id"]}


def run_window(
    date_from: str | date,
    date_until: str | date,
    *,
    conn: Any | None = None,
    dry_run: bool = False,
    fetch_paper_detail: bool = True,
    run_id: str | None = None,
    stage_run_id: str | None = None,
    limit: int | None = None,
) -> dict[str, Any]:
    """Enrich papers published in [date_from, date_until] with HF Daily Papers signals."""
    import json

    d0 = _parse_day(date_from)
    d1 = _parse_day(date_until)
    owns = conn is None
    conn = conn or connect()
    try:
        index = collect_daily_index(
            d0, d1, conn=conn, run_id=run_id, stage_run_id=stage_run_id
        )
        # Restrict to papers whose arXiv publish date is in the requested window
        # (still allow featured_date later via lag fetch above).
        with conn.cursor() as cur:
            from paper_intelligence.common.config import PI_USE_PAPERS_CATALOG

            if PI_USE_PAPERS_CATALOG:
                cur.execute(
                    """
                    SELECT arxiv_id, paper_id AS content_id
                    FROM paper_intelligence.papers
                    WHERE arxiv_id IS NOT NULL
                      AND published_at >= %s::timestamptz
                      AND published_at < (%s::timestamptz + interval '1 day')
                    """,
                    (d0.isoformat(), d1.isoformat()),
                )
            else:
                cur.execute(
                    """
                    SELECT pm.arxiv_id, pm.content_id
                    FROM research_radar.paper_metadata pm
                    JOIN research_radar.content_items ci ON ci.id = pm.content_id
                    WHERE pm.arxiv_id IS NOT NULL
                      AND ci.published_at >= %s::timestamptz
                      AND ci.published_at < (%s::timestamptz + interval '1 day')
                    """,
                    (d0.isoformat(), d1.isoformat()),
                )
            window_papers = {
                str(r["arxiv_id"]): int(r["content_id"])
                for r in cur.fetchall()
                if r["arxiv_id"]
            }

        matched_ids = sorted(set(index) & set(window_papers))
        if limit is not None:
            matched_ids = matched_ids[: int(limit)]

        summary = {
            "hf_daily_unique": len(index),
            "window_arxiv_papers": len(window_papers),
            "matched": len(matched_ids),
            "overlap_pct_of_window": round(
                100.0 * len(matched_ids) / len(window_papers), 1
            )
            if window_papers
            else 0.0,
            "wrote": 0,
            "detail_fetches": 0,
            "detail_errors": 0,
            "dry_run": dry_run,
        }

        if dry_run:
            return summary

        written_ids: list[int] = []
        for aid in matched_ids:
            content_id = window_papers[aid]
            signal = dict(index[aid])
            raw_ref = None
            if fetch_paper_detail:
                detail = hf_client.get_paper(
                    aid,
                    conn=conn,
                    run_id=run_id,
                    stage_run_id=stage_run_id,
                    content_item_id=content_id,
                )
                summary["detail_fetches"] += 1
                if detail.error:
                    summary["detail_errors"] += 1
                else:
                    signal = _merge_detail(signal, detail.paper)
                    raw_ref = detail.raw_ref

            meta = {
                "daily_day": signal.get("daily_day"),
                "source": "hf_daily_papers",
            }
            conn.execute(
                UPSERT_SQL,
                (
                    content_id,
                    aid,
                    bool(signal.get("hf_featured")),
                    signal.get("hf_featured_date"),
                    signal.get("hf_upvotes"),
                    signal.get("hf_daily_upvote_rank"),
                    signal.get("hf_num_comments"),
                    signal.get("hf_submitter"),
                    signal.get("linked_models_count"),
                    signal.get("linked_datasets_count"),
                    signal.get("linked_spaces_count"),
                    signal.get("github_url"),
                    signal.get("github_stars"),
                    signal.get("project_url"),
                    signal.get("hf_title"),
                    raw_ref,
                    STAGE_VERSION,
                    run_id,
                    json.dumps(meta, default=str),
                ),
            )
            written_ids.append(content_id)

        if written_ids:
            conn.execute(UPDATE_CURRENT_SQL, (written_ids,))
        conn.commit()
        summary["wrote"] = len(written_ids)
        return summary
    finally:
        if owns:
            conn.close()
