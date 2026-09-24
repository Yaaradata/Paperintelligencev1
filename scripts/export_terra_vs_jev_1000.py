#!/usr/bin/env python3
"""Export Terra vs Jev comparison CSV for human judgement.

Reuses persisted J1b per-paper Jev scores when present
(``reports/review_fixes/jev_j1b_quality_scores.json``). Does **not** call
System One unless ``--allow-paid`` is passed after a dry-run cost print.

  PYTHONPATH=src python3 scripts/export_terra_vs_jev_1000.py
  PYTHONPATH=src python3 scripts/export_terra_vs_jev_1000.py --allow-paid --max-cost-usd 1
"""

from __future__ import annotations

import argparse
import csv
import json
import math
import random
import statistics
import sys
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from paper_intelligence.common.budget import BudgetCap  # noqa: E402
from paper_intelligence.db import connect  # noqa: E402
from paper_intelligence.systemone.client import (  # noqa: E402
    JEV_MODEL_PINNED,
    SystemOneRequest,
    system_one,
)
from paper_intelligence.systemone.policy import (  # noqa: E402
    build_questions,
    load_systemone_policy,
    parse_answers,
    state_from_paper,
)

OUT_CSV = ROOT / "reports" / "review_fixes" / "terra_vs_jev_1000.csv"
OUT_MD = ROOT / "reports" / "review_fixes" / "terra_vs_jev_1000.md"
JEV_CACHE = ROOT / "reports" / "review_fixes" / "jev_j1b_quality_scores.json"
JEV_CACHE_NOTE = "policy version recorded inside the cache JSON"
CALIB = ROOT / "reports" / "review_fixes" / "sol_terra_calibration.json"
SEAT_VAL = ROOT / "reports" / "review_fixes" / "seat_validation_set.json"

QUALITY_DIMS = (
    "technical_significance",
    "apparent_novelty",
    "practical_applicability",
    "professional_value",
    "learning_value",
    "evidence_strength",
)
Q_WEIGHTS = {
    "technical_significance": 0.28,
    "apparent_novelty": 0.24,
    "practical_applicability": 0.20,
    "professional_value": 0.16,
    "learning_value": 0.12,
}

# J1b measured ~$0.0574 / 1000 papers for 6-dim quality.
JEV_COST_PER_PAPER = 0.0574 / 1000.0


def _args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--allow-paid", action="store_true")
    p.add_argument("--max-cost-usd", type=float, default=1.0)
    p.add_argument("--concurrency", type=int, default=8)
    p.add_argument("--seed", type=int, default=42)
    p.add_argument("--n", type=int, default=1000)
    return p.parse_args()


def _composite(scores: dict[str, float]) -> float:
    q = sum(Q_WEIGHTS[d] * float(scores[d]) for d in Q_WEIGHTS)
    ef = 0.70 + 0.03 * float(scores["evidence_strength"])
    return min(10.0, q * ef)


def _terra_composite(rj: dict[str, Any]) -> float | None:
    comp = rj.get("composite") or {}
    if isinstance(comp, dict) and comp.get("quality") is not None:
        try:
            return float(comp["quality"])
        except (TypeError, ValueError):
            pass
    try:
        dims = {d: float(rj[d]) for d in QUALITY_DIMS}
    except (KeyError, TypeError, ValueError):
        return None
    return _composite(dims)


def _load_golden() -> set[int]:
    if not CALIB.exists():
        return set()
    data = json.loads(CALIB.read_text(encoding="utf-8"))
    return {int(x) for x in data.get("sample_ids") or []}


def _load_editorial() -> dict[int, str]:
    """content_item_id → winner | runner_up | linkedin_winner (best role)."""
    if not SEAT_VAL.exists():
        return {}
    data = json.loads(SEAT_VAL.read_text(encoding="utf-8"))
    rank = {"winner": 3, "linkedin_winner": 2, "runner_up": 1}
    out: dict[int, str] = {}
    for p in data.get("past_editorial_picks") or []:
        cid = int(p["content_item_id"])
        role = str(p.get("role") or "winner")
        if cid not in out or rank.get(role, 0) > rank.get(out[cid], 0):
            out[cid] = role if role in rank else "winner"
    return out


def _load_jev_cache() -> dict[int, dict[str, Any]]:
    if not JEV_CACHE.exists():
        return {}
    data = json.loads(JEV_CACHE.read_text(encoding="utf-8"))
    rows = data.get("papers") or data
    out: dict[int, dict[str, Any]] = {}
    if isinstance(rows, dict):
        for k, v in rows.items():
            out[int(k)] = v
    else:
        for row in rows:
            out[int(row["content_item_id"])] = row
    return out


def _save_jev_cache(cache: dict[int, dict[str, Any]], *, policy: str = "quality_v001") -> None:
    existing_policy = policy
    if JEV_CACHE.exists():
        try:
            existing_policy = json.loads(JEV_CACHE.read_text(encoding="utf-8")).get("policy") or policy
        except (json.JSONDecodeError, OSError):
            pass
    payload = {
        "model": JEV_MODEL_PINNED,
        "policy": existing_policy,
        "source": "jev_j1b_reuse_or_fill",
        "papers": {str(k): v for k, v in sorted(cache.items())},
    }
    JEV_CACHE.write_text(json.dumps(payload, indent=2), encoding="utf-8")


def _load_terra_pool(conn) -> list[dict[str, Any]]:
    rows = conn.execute(
        """
        SELECT DISTINCT ON (q.content_item_id)
          q.content_item_id AS paper_id,
          p.arxiv_id,
          p.title,
          p.abstract,
          p.published_at,
          q.result_json,
          q.model
        FROM paper_intelligence.paper_classification_results q
        JOIN paper_intelligence.papers p ON p.paper_id = q.content_item_id
        WHERE q.task_type = 'quality'
          AND q.model LIKE '%%terra%%'
          AND p.published_at >= '2026-09-01'
          AND p.published_at < '2026-09-22'
        ORDER BY q.content_item_id, q.created_at DESC
        """
    ).fetchall()
    out = []
    for r in rows:
        rj = r["result_json"] or {}
        if isinstance(rj, str):
            rj = json.loads(rj)
        dims = {}
        ok = True
        for d in QUALITY_DIMS:
            if rj.get(d) is None:
                ok = False
                break
            dims[d] = float(rj[d])
        if not ok:
            continue
        comp = _terra_composite(rj)
        if comp is None:
            continue
        aid = r["arxiv_id"]
        out.append(
            {
                "paper_id": int(r["paper_id"]),
                "arxiv_id": aid,
                "arxiv_url": f"https://arxiv.org/abs/{aid}" if aid else "",
                "title": r["title"] or "",
                "abstract": r["abstract"] or "",
                "published_at": str(r["published_at"]),
                "terra_composite": comp,
                "terra_dims": dims,
            }
        )
    return out


def _orgs_by_id(conn, ids: list[int]) -> dict[int, str]:
    if not ids:
        return {}
    rows = conn.execute(
        """
        SELECT a.content_item_id, o.canonical_name AS display_name
        FROM paper_intelligence.paper_author_affiliations a
        JOIN paper_intelligence.organisations o ON o.id = a.organisation_id
        WHERE a.content_item_id = ANY(%s)
          AND o.canonical_name IS NOT NULL
        ORDER BY a.content_item_id, o.canonical_name
        """,
        (ids,),
    ).fetchall()
    buckets: dict[int, list[str]] = {}
    for r in rows:
        buckets.setdefault(int(r["content_item_id"]), []).append(str(r["display_name"]))
    return {k: "; ".join(dict.fromkeys(v)) for k, v in buckets.items()}


def _select_1000(
    pool: list[dict[str, Any]],
    *,
    golden: set[int],
    editorial: dict[int, str],
    n: int,
    seed: int,
) -> list[dict[str, Any]]:
    by_id = {p["paper_id"]: p for p in pool}
    selected: list[dict[str, Any]] = []
    seen: set[int] = set()

    def add(cid: int) -> None:
        if cid in seen or cid not in by_id:
            return
        seen.add(cid)
        selected.append(by_id[cid])

    for cid in sorted(golden):
        add(cid)
    for cid in sorted(editorial):
        add(cid)

    # Oversample top-200 Terra (among full Terra pool).
    by_terra = sorted(pool, key=lambda p: -p["terra_composite"])
    for p in by_terra[:200]:
        add(p["paper_id"])

    # Stratify remaining across Terra score range.
    remaining = [p for p in pool if p["paper_id"] not in seen]
    remaining.sort(key=lambda p: p["terra_composite"])
    rng = random.Random(seed)
    if remaining and len(selected) < n:
        n_bins = 10
        bins: list[list[dict[str, Any]]] = [[] for _ in range(n_bins)]
        for i, p in enumerate(remaining):
            bins[min(n_bins - 1, int(i * n_bins / len(remaining)))].append(p)
        need = n - len(selected)
        per = max(1, need // n_bins)
        for b in bins:
            rng.shuffle(b)
            for p in b[:per]:
                if len(selected) >= n:
                    break
                add(p["paper_id"])
        # fill leftover
        leftover = [p for p in remaining if p["paper_id"] not in seen]
        rng.shuffle(leftover)
        for p in leftover:
            if len(selected) >= n:
                break
            add(p["paper_id"])

    selected = selected[:n]

    # After we have Jev, we also oversample top-200 by Jev — handled later once
    # scores exist (may replace stratified filler).
    return selected


def _oversample_jev_top(
    selected: list[dict[str, Any]],
    pool: list[dict[str, Any]],
    jev: dict[int, dict[str, Any]],
    *,
    n: int,
    seed: int,
) -> list[dict[str, Any]]:
    """Ensure top-200 by Jev (among Terra∩Jev pool) are in the final 1000."""
    by_id = {p["paper_id"]: p for p in pool}
    scored = []
    for p in pool:
        j = jev.get(p["paper_id"])
        if not j or j.get("composite") is None:
            continue
        scored.append((float(j["composite"]), p["paper_id"]))
    scored.sort(reverse=True)
    top_jev_ids = [cid for _, cid in scored[:200]]

    seen = {p["paper_id"] for p in selected}
    out = list(selected)
    for cid in top_jev_ids:
        if cid in seen or cid not in by_id:
            continue
        out.append(by_id[cid])
        seen.add(cid)

    if len(out) > n:
        # Keep must-include: golden/editorial already in selected head; keep
        # first n preferring original selected then new jev tops already appended.
        # Drop from the middle stratified region.
        must = set(p["paper_id"] for p in selected[: min(len(selected), 300)])
        must.update(top_jev_ids)
        must.update(p["paper_id"] for p in selected if p["paper_id"] in top_jev_ids)
        keep = []
        seen2: set[int] = set()
        for p in out:
            if p["paper_id"] in must and p["paper_id"] not in seen2:
                keep.append(p)
                seen2.add(p["paper_id"])
        for p in out:
            if len(keep) >= n:
                break
            if p["paper_id"] not in seen2:
                keep.append(p)
                seen2.add(p["paper_id"])
        out = keep[:n]
    elif len(out) < n:
        rng = random.Random(seed)
        filler = [p for p in pool if p["paper_id"] not in seen]
        rng.shuffle(filler)
        out.extend(filler[: n - len(out)])
    return out[:n]


def _score_jev(
    papers: list[dict[str, Any]],
    *,
    cache: dict[int, dict[str, Any]],
    max_cost: float,
    concurrency: int,
) -> tuple[dict[int, dict[str, Any]], float]:
    need = [p for p in papers if p["paper_id"] not in cache]
    if not need:
        return cache, 0.0
    policy = load_systemone_policy("quality", "v001")
    questions = build_questions(policy)
    budget = BudgetCap(max_cost)
    spent0 = budget.actual_usd

    def one(p: dict[str, Any]) -> tuple[int, dict[str, Any] | None, float]:
        if not budget.allow_new_batch():
            return p["paper_id"], None, 0.0
        state = state_from_paper({"title": p["title"], "abstract": p["abstract"]})
        resp = system_one(
            SystemOneRequest(
                model=JEV_MODEL_PINNED,
                state=state,
                questions=questions,
            )
        )
        billable = float(resp.billable_cost or 0.0)
        budget.add_actual(billable)
        if resp.error:
            return p["paper_id"], None, billable
        parsed = parse_answers(resp.answers or {}, policy)
        dims = {}
        confs = []
        for d in QUALITY_DIMS:
            cell = parsed.get(d) or {}
            if cell.get("score_0_10") is None:
                return p["paper_id"], None, billable
            dims[d] = float(cell["score_0_10"])
            if cell.get("confidence") is not None:
                confs.append(float(cell["confidence"]))
        return (
            p["paper_id"],
            {
                "content_item_id": p["paper_id"],
                "dims": dims,
                "composite": _composite(dims),
                "confidence": statistics.mean(confs) if confs else None,
            },
            billable,
        )

    done = 0
    with ThreadPoolExecutor(max_workers=concurrency) as ex:
        futs = [ex.submit(one, p) for p in need]
        for fut in as_completed(futs):
            cid, row, _ = fut.result()
            done += 1
            if row is not None:
                cache[cid] = row
            if done % 50 == 0 or done == len(futs):
                print(
                    f"  jev fill {done}/{len(futs)} spent=${budget.actual_usd:.4f}",
                    flush=True,
                )
    return cache, budget.actual_usd - spent0


def _ranks(values: dict[int, float]) -> dict[int, int]:
    ordered = sorted(values.items(), key=lambda kv: (-kv[1], kv[0]))
    return {cid: i + 1 for i, (cid, _) in enumerate(ordered)}


def main() -> int:
    args = _args()
    golden = _load_golden()
    editorial = _load_editorial()
    jev_cache = _load_jev_cache()
    jev_policy = "unknown"
    if JEV_CACHE.exists():
        try:
            jev_policy = str(
                json.loads(JEV_CACHE.read_text(encoding="utf-8")).get("policy") or "unknown"
            )
        except (json.JSONDecodeError, OSError):
            pass

    with connect() as conn:
        pool = _load_terra_pool(conn)
    print(f"terra_pool={len(pool)} jev_cache={len(jev_cache)}", flush=True)

    selected = _select_1000(
        pool, golden=golden, editorial=editorial, n=args.n, seed=args.seed
    )
    # Prefer papers that already have Jev when filling; still include must-haves.
    have_both_ids = {p["paper_id"] for p in pool if p["paper_id"] in jev_cache}
    print(
        f"selected_pre_jev_oversample={len(selected)} "
        f"terra_and_jev_available={len(have_both_ids)}",
        flush=True,
    )

    missing = [p for p in selected if p["paper_id"] not in jev_cache]
    # Also need Jev for top-200 Terra oversample already in selected; if cache
    # empty, all selected are missing.
    est = len(missing) * JEV_COST_PER_PAPER
    print(
        f"missing_jev={len(missing)} est_cost_usd=${est:.4f} "
        f"(J1b rate ${JEV_COST_PER_PAPER*1000:.4f}/1k)",
        flush=True,
    )

    if missing:
        if not args.allow_paid:
            OUT_MD.write_text(
                "\n".join(
                    [
                        "# Terra vs Jev 1000 — blocked (no paid Jev fill)",
                        "",
                        f"J1b per-paper Jev scores were **not persisted** "
                        f"(only aggregates in `jev_j1b.json`).",
                        "",
                        f"- Terra pool (Sep 1–21, latest Terra quality): **{len(pool)}**",
                        f"- Target sample: **{args.n}**",
                        f"- Missing Jev for selected sample: **{len(missing)}**",
                        f"- Estimated fill cost: **${est:.4f}** "
                        f"(cap would be `--max-cost-usd {args.max_cost_usd}`)",
                        "",
                        "Re-run with `--allow-paid` to score missing papers via "
                        f"`{JEV_MODEL_PINNED}` and write the CSV. No new calls made.",
                        "",
                    ]
                ),
                encoding="utf-8",
            )
            print(f"wrote {OUT_MD} (blocked — pass --allow-paid to fill)", flush=True)
            print(
                json.dumps(
                    {
                        "status": "need_paid_jev_fill",
                        "missing": len(missing),
                        "est_cost_usd": round(est, 4),
                        "max_cost_usd": args.max_cost_usd,
                    },
                    indent=2,
                )
            )
            return 2

        print(f"=== scoring missing Jev n={len(missing)} ===", flush=True)
        t0 = time.time()
        jev_cache, spent = _score_jev(
            missing,
            cache=jev_cache,
            max_cost=args.max_cost_usd,
            concurrency=args.concurrency,
        )
        _save_jev_cache(jev_cache)
        print(f"jev_fill_spent=${spent:.4f} wall_s={time.time()-t0:.1f}", flush=True)

    selected = _oversample_jev_top(
        selected, pool, jev_cache, n=args.n, seed=args.seed
    )
    # Drop any still missing Jev
    selected = [p for p in selected if p["paper_id"] in jev_cache]
    if len(selected) < args.n:
        # top up from terra∩jev
        have = {p["paper_id"] for p in selected}
        extra = [
            p
            for p in sorted(pool, key=lambda x: -x["terra_composite"])
            if p["paper_id"] in jev_cache and p["paper_id"] not in have
        ]
        selected.extend(extra[: args.n - len(selected)])

    if len(selected) < args.n:
        print(
            f"ERROR: only {len(selected)} papers have both Terra and Jev "
            f"(need {args.n})",
            file=sys.stderr,
        )
        return 1

    selected = selected[: args.n]
    ids = [p["paper_id"] for p in selected]
    with connect() as conn:
        orgs = _orgs_by_id(conn, ids)

    terra_scores = {p["paper_id"]: p["terra_composite"] for p in selected}
    jev_scores = {p["paper_id"]: float(jev_cache[p["paper_id"]]["composite"]) for p in selected}
    # Ranks within this 1000-sample (human-judgement set).
    terra_rank = _ranks(terra_scores)
    jev_rank = _ranks(jev_scores)

    rows_out = []
    for p in selected:
        cid = p["paper_id"]
        j = jev_cache[cid]
        jdims = j.get("dims") or {}
        tr = terra_rank[cid]
        jr = jev_rank[cid]
        role = editorial.get(cid)
        rows_out.append(
            {
                "paper_id": cid,
                "arxiv_id": p["arxiv_id"] or "",
                "arxiv_url": p["arxiv_url"],
                "title": p["title"],
                "published_at": p["published_at"],
                "terra_composite": round(p["terra_composite"], 4),
                "jev_composite": round(float(j["composite"]), 4),
                "terra_rank": tr,
                "jev_rank": jr,
                "rank_gap": tr - jr,
                **{f"terra_{d}": p["terra_dims"][d] for d in QUALITY_DIMS},
                **{f"jev_{d}": jdims.get(d) for d in QUALITY_DIMS},
                "jev_confidence": j.get("confidence"),
                "organisations": orgs.get(cid, ""),
                "is_golden": cid in golden,
                "was_editorial_pick": role if role else "none",
            }
        )

    rows_out.sort(key=lambda r: (-abs(int(r["rank_gap"])), int(r["paper_id"])))

    fieldnames = [
        "paper_id",
        "arxiv_id",
        "arxiv_url",
        "title",
        "published_at",
        "terra_composite",
        "jev_composite",
        "terra_rank",
        "jev_rank",
        "rank_gap",
        *[f"terra_{d}" for d in QUALITY_DIMS],
        *[f"jev_{d}" for d in QUALITY_DIMS],
        "jev_confidence",
        "organisations",
        "is_golden",
        "was_editorial_pick",
    ]
    OUT_CSV.parent.mkdir(parents=True, exist_ok=True)
    with OUT_CSV.open("w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=fieldnames)
        w.writeheader()
        w.writerows(rows_out)

    # Markdown summary
    pick_rows = [r for r in rows_out if r["was_editorial_pick"] != "none"]
    lines = [
        "# Terra vs Jev — 1000-paper human judgement set",
        "",
        f"**N:** {len(rows_out)}  ",
        f"**Jev model:** `{JEV_MODEL_PINNED}`  ",
        f"**Jev policy:** `{jev_policy}` "
        "(chosen because it beat quality_v002 on Terra/Sol Spearman; "
        "v002 raised confidence≥0.9 but lowered rank agreement)  ",
        f"**Jev source:** `{JEV_CACHE.relative_to(ROOT)}`  ",
        f"**CSV:** `{OUT_CSV.relative_to(ROOT)}`",
        "",
        "## Editorial picks — ranks in this set",
        "",
        "| paper_id | role | title | terra_rank | jev_rank | terra_pct | jev_pct |",
        "|---:|---|---|---:|---:|---:|---:|",
    ]
    n = len(rows_out)
    for r in sorted(pick_rows, key=lambda x: x["terra_rank"]):
        lines.append(
            f"| {r['paper_id']} | {r['was_editorial_pick']} | {r['title'][:60]} | "
            f"{r['terra_rank']} | {r['jev_rank']} | "
            f"{100*(1 - (r['terra_rank']-1)/n):.1f}% | "
            f"{100*(1 - (r['jev_rank']-1)/n):.1f}% |"
        )
    if pick_rows:
        lines += [
            "",
            f"- Mean Terra rank: **{statistics.mean(r['terra_rank'] for r in pick_rows):.1f}** "
            f"(mean pctile {statistics.mean(100*(1-(r['terra_rank']-1)/n) for r in pick_rows):.1f}%)",
            f"- Mean Jev rank: **{statistics.mean(r['jev_rank'] for r in pick_rows):.1f}** "
            f"(mean pctile {statistics.mean(100*(1-(r['jev_rank']-1)/n) for r in pick_rows):.1f}%)",
        ]
    else:
        lines += ["", "No editorial picks present in the Terra∩Jev sample."]

    lines += [
        "",
        "## 20 largest |rank_gap| disagreements",
        "",
        "| |rank_gap| | terra_rank | jev_rank | terra_Q | jev_Q | title |",
        "|---:|---:|---:|---:|---:|---|",
    ]
    for r in rows_out[:20]:
        lines.append(
            f"| {abs(int(r['rank_gap']))} | {r['terra_rank']} | {r['jev_rank']} | "
            f"{r['terra_composite']:.2f} | {r['jev_composite']:.2f} | {r['title'][:70]} |"
        )
    lines.append("")
    OUT_MD.write_text("\n".join(lines), encoding="utf-8")
    print(f"wrote {OUT_CSV}", flush=True)
    print(f"wrote {OUT_MD}", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
