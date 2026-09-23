#!/usr/bin/env python3
"""Phase J1 — TypeSafe Jev shadow evaluation (no writes to current).

Samples papers with existing screen / quality evidence, runs pinned
``typesafe/jev-1.13`` via OpenRouter System One, and writes
``reports/review_fixes/jev_shadow_eval.md``.

  PYTHONPATH=src python3 scripts/jev_shadow_eval.py --allow-paid --max-cost-usd 2

Defaults are unchanged: this script never patches screen/audience engines.
"""

from __future__ import annotations

import argparse
import csv
import gzip
import json
import math
import random
import re
import statistics
import time
import xml.etree.ElementTree as ET
from collections import defaultdict
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import requests
import yaml

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
import sys

if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from paper_intelligence.common.budget import BudgetCap  # noqa: E402
from paper_intelligence.common.config import (  # noqa: E402
    GATE_PERCENTILE,
    SCREEN_MIN_AI_RELEVANCE,
    estimate_cost_usd,
    require_model_priced,
)
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

REPORT_PATH = ROOT / "reports" / "review_fixes" / "jev_shadow_eval.md"
JSON_PATH = ROOT / "reports" / "review_fixes" / "jev_shadow_eval.json"
CACHE_ROOT = ROOT.parent.parent / "shared_data" / "raw" / "openrouter"
ATOM_NS = {"a": "http://www.w3.org/2005/Atom"}
RANK_DIMS = ("technical_significance", "apparent_novelty", "evidence_strength")
SCREEN_DIMS = ("ai_relevance",) + RANK_DIMS


def _args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--allow-paid", action="store_true")
    p.add_argument("--max-cost-usd", type=float, default=2.0)
    p.add_argument("--screen-n", type=int, default=300)
    p.add_argument("--quality-n", type=int, default=300)
    p.add_argument("--seed", type=int, default=42)
    p.add_argument("--concurrency", type=int, default=6)
    p.add_argument("--dry-run", action="store_true", help="Build sample only; no API calls")
    return p.parse_args()


def _db_available() -> bool:
    try:
        from paper_intelligence.db import connect

        with connect() as conn:
            conn.execute("SELECT 1 FROM paper_intelligence.papers LIMIT 1").fetchone()
        return True
    except Exception:
        return False


def _load_cid_arxiv_map() -> dict[int, str]:
    ids: dict[int, str] = {}
    for path in (ROOT / "reports").rglob("*"):
        if path.suffix == ".csv":
            try:
                with path.open(newline="", encoding="utf-8") as fh:
                    rows = list(csv.DictReader(fh))
            except Exception:
                continue
            for row in rows:
                cid = row.get("content_item_id") or row.get("paper_id")
                aid = (row.get("arxiv_id") or "").strip()
                url = row.get("canonical_url") or row.get("url") or ""
                m = re.search(r"arxiv\.org/abs/([\w.\-]+)", url)
                if m:
                    aid = m.group(1)
                if cid and aid:
                    try:
                        ids[int(cid)] = aid.split("v")[0]
                    except ValueError:
                        pass
        elif path.suffix == ".json":
            try:
                data = json.loads(path.read_text(encoding="utf-8"))
            except Exception:
                continue

            def walk(obj: Any) -> None:
                if isinstance(obj, dict):
                    cid = obj.get("content_item_id") or obj.get("paper_id")
                    aid = obj.get("arxiv_id")
                    if cid is not None and aid:
                        try:
                            ids[int(cid)] = str(aid).split("v")[0]
                        except ValueError:
                            pass
                    for v in obj.values():
                        walk(v)
                elif isinstance(obj, list):
                    for v in obj:
                        walk(v)

            walk(data)
    return ids


def _parse_llm_json(content: str) -> dict[str, Any] | None:
    m = re.search(r"\{.*\}", content or "", re.S)
    if not m:
        return None
    try:
        data = json.loads(m.group(0))
    except json.JSONDecodeError:
        return None
    return data if isinstance(data, dict) else None


def _load_screen_from_cache() -> dict[int, dict[str, float]]:
    out: dict[int, dict[str, float]] = {}
    if not CACHE_ROOT.exists():
        return out
    for path in CACHE_ROOT.rglob("*screen*.json.gz"):
        try:
            obj = json.loads(gzip.open(path, "rt", encoding="utf-8").read())
        except Exception:
            continue
        content = (
            ((obj.get("choices") or [{}])[0].get("message") or {}).get("content") or ""
        )
        data = _parse_llm_json(content)
        if not data:
            continue
        for paper in data.get("papers") or []:
            if not isinstance(paper, dict):
                continue
            cid = paper.get("content_item_id")
            if cid is None:
                continue
            try:
                cid_i = int(cid)
            except (TypeError, ValueError):
                continue
            scores = {}
            ok = True
            for dim in SCREEN_DIMS:
                try:
                    scores[dim] = float(paper[dim])
                except (KeyError, TypeError, ValueError):
                    ok = False
                    break
            if ok:
                out[cid_i] = scores
    return out


def _load_quality_ids_from_cache() -> set[int]:
    ids: set[int] = set()
    if not CACHE_ROOT.exists():
        return ids
    for path in CACHE_ROOT.rglob("*quality*.json.gz"):
        try:
            obj = json.loads(gzip.open(path, "rt", encoding="utf-8").read())
        except Exception:
            continue
        content = (
            ((obj.get("choices") or [{}])[0].get("message") or {}).get("content") or ""
        )
        data = _parse_llm_json(content)
        if not data:
            continue
        for paper in data.get("papers") or []:
            if not isinstance(paper, dict):
                continue
            cid = paper.get("content_item_id")
            if cid is None:
                continue
            try:
                ids.add(int(cid))
            except (TypeError, ValueError):
                pass
    return ids


def _load_classify_from_cache() -> dict[int, dict[str, Any]]:
    """Best-effort domain / application_domain labels from classify caches."""
    out: dict[int, dict[str, Any]] = {}
    if not CACHE_ROOT.exists():
        return out
    for path in list(CACHE_ROOT.rglob("*classify*.json.gz")) + list(
        CACHE_ROOT.rglob("*audience*.json.gz")
    ):
        try:
            obj = json.loads(gzip.open(path, "rt", encoding="utf-8").read())
        except Exception:
            continue
        content = (
            ((obj.get("choices") or [{}])[0].get("message") or {}).get("content") or ""
        )
        data = _parse_llm_json(content)
        if not data:
            continue
        for paper in data.get("papers") or []:
            if not isinstance(paper, dict):
                continue
            cid = paper.get("content_item_id")
            if cid is None:
                continue
            try:
                cid_i = int(cid)
            except (TypeError, ValueError):
                continue
            rec = out.setdefault(cid_i, {})
            if paper.get("domain"):
                rec["domain"] = paper.get("domain")
            apps = paper.get("application_domains") or paper.get("application_domain")
            if isinstance(apps, list) and apps:
                rec["application_domain"] = apps[0]
            elif isinstance(apps, str):
                rec["application_domain"] = apps
            if paper.get("tech_relevance") is not None:
                try:
                    rec["tech_relevance"] = float(paper["tech_relevance"])
                except (TypeError, ValueError):
                    pass
            if paper.get("product_relevance") is not None:
                try:
                    rec["product_relevance"] = float(paper["product_relevance"])
                except (TypeError, ValueError):
                    pass
    return out


def _fetch_arxiv_meta(arxiv_ids: list[str]) -> dict[str, dict[str, str]]:
    """Batch-fetch title/abstract/published from arXiv API."""
    out: dict[str, dict[str, str]] = {}
    headers = {"User-Agent": "paper-intelligence/1.0 (jev-shadow-eval)"}
    for i in range(0, len(arxiv_ids), 40):
        chunk = arxiv_ids[i : i + 40]
        for attempt in range(3):
            try:
                resp = requests.get(
                    "http://export.arxiv.org/api/query",
                    params={"id_list": ",".join(chunk), "max_results": len(chunk)},
                    headers=headers,
                    timeout=60,
                )
                resp.raise_for_status()
                root = ET.fromstring(resp.text)
                for entry in root.findall("a:entry", ATOM_NS):
                    eid = (entry.findtext("a:id", default="", namespaces=ATOM_NS) or "")
                    m = re.search(r"arxiv\.org/abs/([\w.\-]+)", eid)
                    if not m:
                        continue
                    aid = m.group(1).split("v")[0]
                    title = " ".join(
                        (entry.findtext("a:title", default="", namespaces=ATOM_NS) or "").split()
                    )
                    abstract = " ".join(
                        (
                            entry.findtext("a:summary", default="", namespaces=ATOM_NS) or ""
                        ).split()
                    )
                    published = (
                        entry.findtext("a:published", default="", namespaces=ATOM_NS) or ""
                    )[:10]
                    out[aid] = {
                        "title": title,
                        "abstract": abstract,
                        "published_date": published,
                    }
                break
            except Exception:
                if attempt == 2:
                    raise
                time.sleep(2 ** attempt)
        time.sleep(0.4)
    return out


def _calibration_ids() -> list[int]:
    path = ROOT / "reports" / "review_fixes" / "sol_terra_calibration.json"
    if not path.exists():
        return []
    data = json.loads(path.read_text(encoding="utf-8"))
    return [int(x) for x in data.get("sample_ids") or []]


def _rank_mean(scores: dict[str, float]) -> float:
    return sum(float(scores[d]) for d in RANK_DIMS) / len(RANK_DIMS)


def _gate_passed(scores: dict[str, float], threshold: float = SCREEN_MIN_AI_RELEVANCE) -> bool:
    return float(scores.get("ai_relevance", 0.0)) >= threshold


def _spearman(xs: list[float], ys: list[float]) -> float | None:
    if len(xs) < 3 or len(xs) != len(ys):
        return None

    def ranks(vals: list[float]) -> list[float]:
        order = sorted(range(len(vals)), key=lambda i: vals[i])
        r = [0.0] * len(vals)
        i = 0
        while i < len(order):
            j = i
            while j + 1 < len(order) and vals[order[j + 1]] == vals[order[i]]:
                j += 1
            avg = (i + j) / 2.0 + 1.0
            for k in range(i, j + 1):
                r[order[k]] = avg
            i = j + 1
        return r

    rx, ry = ranks(xs), ranks(ys)
    mx, my = statistics.mean(rx), statistics.mean(ry)
    num = sum((a - mx) * (b - my) for a, b in zip(rx, ry))
    denx = math.sqrt(sum((a - mx) ** 2 for a in rx))
    deny = math.sqrt(sum((b - my) ** 2 for b in ry))
    if denx == 0 or deny == 0:
        return None
    return num / (denx * deny)


def _top_slice_keep(n: int, percentile: float = GATE_PERCENTILE) -> int:
    """Match quality._top_slice_ids: keep round(n * GATE_PERCENTILE/100)."""
    if n <= 0:
        return 0
    return max(1, int(round(n * (float(percentile) / 100.0))))


def _simulate_top_slice(
    papers: list[dict[str, Any]], score_key: str
) -> set[int]:
    """Per published_date, keep top slice by rank mean under score_key ('llm'|'jev')."""
    by_day: dict[str, list[tuple[float, int]]] = defaultdict(list)
    for p in papers:
        if not p.get("llm_gate_passed"):
            continue
        day = p.get("published_date") or "unknown"
        if score_key == "llm":
            mean = p["llm_rank_mean"]
        else:
            mean = p.get("jev_rank_mean")
            if mean is None:
                continue
        by_day[day].append((float(mean), int(p["content_item_id"])))
    selected: set[int] = set()
    for day, rows in by_day.items():
        rows.sort(key=lambda t: (-t[0], t[1]))
        keep = _top_slice_keep(len(rows))
        for _, cid in rows[:keep]:
            selected.add(cid)
    return selected


def _call_policy(
    *,
    paper: dict[str, Any],
    policy: dict[str, Any],
    questions: dict[str, Any],
    budget: BudgetCap | None,
) -> dict[str, Any]:
    if budget is not None and not budget.allow_new_batch():
        return {"ok": False, "error": "budget_cap", "content_item_id": paper["content_item_id"]}
    t0 = time.perf_counter()
    resp = system_one(
        SystemOneRequest(
            model=JEV_MODEL_PINNED,
            state=state_from_paper(paper),
            questions=questions,
        )
    )
    elapsed = time.perf_counter() - t0
    billable = float(resp.billable_cost or 0.0)
    if budget is not None and not resp.error:
        budget.add_actual(billable)
    parsed = parse_answers(resp.answers or {}, policy) if not resp.error else {}
    return {
        "ok": resp.error is None,
        "error": resp.error,
        "content_item_id": paper["content_item_id"],
        "elapsed_s": elapsed,
        "input_tokens": resp.input_tokens,
        "output_tokens": resp.output_tokens,
        "estimated_cost_usd": resp.estimated_cost,
        "actual_cost_usd": resp.actual_cost,
        "billable_cost_usd": billable,
        "model": resp.model,
        "answers": resp.answers,
        "parsed": parsed,
    }


def main() -> int:
    args = _args()
    if not args.dry_run and not args.allow_paid:
        print("Refusing paid System One calls without --allow-paid", file=sys.stderr)
        return 2
    require_model_priced(JEV_MODEL_PINNED)

    db_ok = _db_available()
    print(f"db_available={db_ok}", flush=True)

    cid_arxiv = _load_cid_arxiv_map()
    screen_scores = _load_screen_from_cache()
    quality_ids = _load_quality_ids_from_cache()
    classify = _load_classify_from_cache()
    golden60 = set(_calibration_ids())

    # Prefer Sep 1–21 via arxiv YYMM=2609 and mapped published dates later.
    screen_pool = [
        cid
        for cid, scores in screen_scores.items()
        if cid in cid_arxiv and cid_arxiv[cid].startswith("2609.")
    ]
    quality_pool = [
        cid
        for cid in quality_ids
        if cid in cid_arxiv and cid_arxiv[cid].startswith("2609.") and cid in screen_scores
    ]
    rng = random.Random(args.seed)
    rng.shuffle(screen_pool)
    rng.shuffle(quality_pool)

    # Ensure golden-60 papers with screen are included in screen sample when possible.
    screen_selected: list[int] = []
    for cid in golden60:
        if cid in screen_pool and cid not in screen_selected:
            screen_selected.append(cid)
    for cid in screen_pool:
        if len(screen_selected) >= args.screen_n:
            break
        if cid not in screen_selected:
            screen_selected.append(cid)
    screen_selected = screen_selected[: args.screen_n]

    quality_selected: list[int] = []
    for cid in golden60:
        if cid in quality_pool and cid not in quality_selected:
            quality_selected.append(cid)
    for cid in quality_pool:
        if len(quality_selected) >= args.quality_n:
            break
        if cid not in quality_selected:
            quality_selected.append(cid)
    quality_selected = quality_selected[: args.quality_n]

    # Audience sample = quality sample (has richer labels when present) ∪ screen sample head
    audience_ids = list(dict.fromkeys(quality_selected + screen_selected))[: args.quality_n]

    all_ids = sorted(set(screen_selected) | set(quality_selected) | set(audience_ids))
    arxiv_list = sorted({cid_arxiv[i] for i in all_ids if i in cid_arxiv})
    print(
        f"sample screen={len(screen_selected)} quality={len(quality_selected)} "
        f"audience={len(audience_ids)} unique={len(all_ids)} arxiv_fetch={len(arxiv_list)}",
        flush=True,
    )
    meta = _fetch_arxiv_meta(arxiv_list)

    def paper_rec(cid: int) -> dict[str, Any] | None:
        aid = cid_arxiv.get(cid)
        if not aid or aid not in meta:
            return None
        m = meta[aid]
        llm = screen_scores.get(cid) or {}
        return {
            "content_item_id": cid,
            "arxiv_id": aid,
            "title": m["title"],
            "abstract": m["abstract"],
            "published_date": m["published_date"],
            "llm_scores": llm,
            "llm_gate_passed": _gate_passed(llm) if llm else None,
            "llm_rank_mean": _rank_mean(llm) if llm and all(d in llm for d in RANK_DIMS) else None,
            "classify": classify.get(cid) or {},
        }

    screen_papers = [p for cid in screen_selected if (p := paper_rec(cid))]
    audience_papers = [p for cid in audience_ids if (p := paper_rec(cid))]
    print(f"with abstracts screen={len(screen_papers)} audience={len(audience_papers)}", flush=True)

    screen_policy = load_systemone_policy("screen", "v001")
    audience_policy = load_systemone_policy("audience", "v001")
    screen_questions = build_questions(screen_policy)
    audience_questions = build_questions(audience_policy)

    if args.dry_run:
        print("dry-run: skipping System One calls", flush=True)
        payload = {
            "dry_run": True,
            "screen_n": len(screen_papers),
            "audience_n": len(audience_papers),
            "db_available": db_ok,
        }
        JSON_PATH.write_text(json.dumps(payload, indent=2), encoding="utf-8")
        return 0

    budget = BudgetCap(args.max_cost_usd)
    screen_results: dict[int, dict[str, Any]] = {}
    audience_results: dict[int, dict[str, Any]] = {}

    def run_batch(papers: list[dict[str, Any]], policy, questions, sink: dict) -> None:
        with ThreadPoolExecutor(max_workers=args.concurrency) as ex:
            futs = [
                ex.submit(
                    _call_policy,
                    paper=p,
                    policy=policy,
                    questions=questions,
                    budget=budget,
                )
                for p in papers
            ]
            done = 0
            for fut in as_completed(futs):
                rec = fut.result()
                sink[int(rec["content_item_id"])] = rec
                done += 1
                if done % 25 == 0 or done == len(futs):
                    print(
                        f"  progress {done}/{len(futs)} spent=${budget.actual_usd:.4f}",
                        flush=True,
                    )

    t_screen0 = time.perf_counter()
    print("=== Jev screen shadow ===", flush=True)
    run_batch(screen_papers, screen_policy, screen_questions, screen_results)
    t_screen = time.perf_counter() - t_screen0
    screen_spend = budget.actual_usd

    t_aud0 = time.perf_counter()
    print("=== Jev audience shadow ===", flush=True)
    # Fresh budget remaining for audience within same cap.
    run_batch(audience_papers, audience_policy, audience_questions, audience_results)
    t_audience = time.perf_counter() - t_aud0
    total_spend = budget.actual_usd
    audience_spend = max(0.0, total_spend - screen_spend)

    # Attach Jev scores onto screen papers
    for p in screen_papers:
        rec = screen_results.get(p["content_item_id"]) or {}
        parsed = rec.get("parsed") or {}
        jev_scores = {}
        for dim in SCREEN_DIMS:
            cell = parsed.get(dim) or {}
            if isinstance(cell, dict) and cell.get("score_0_10") is not None:
                jev_scores[dim] = float(cell["score_0_10"])
        gate_cell = parsed.get("gate_ai_relevance") or {}
        noul = gate_cell.get("noul") if isinstance(gate_cell, dict) else None
        p["jev_scores"] = jev_scores
        p["jev_noul"] = noul
        p["jev_gate_passed"] = (
            (float(noul) >= float(screen_policy.get("gate", {}).get("noul_threshold", 0.5)))
            if noul is not None
            else (
                _gate_passed(jev_scores)
                if "ai_relevance" in jev_scores
                else None
            )
        )
        p["jev_rank_mean"] = (
            _rank_mean(jev_scores) if all(d in jev_scores for d in RANK_DIMS) else None
        )
        p["jev_confidence"] = parsed.get("_mean_confidence")
        p["jev_ok"] = bool(rec.get("ok"))

    # Gate agreement
    both = [p for p in screen_papers if p.get("llm_gate_passed") is not None and p.get("jev_gate_passed") is not None]
    tp = sum(1 for p in both if p["llm_gate_passed"] and p["jev_gate_passed"])
    fp = sum(1 for p in both if (not p["llm_gate_passed"]) and p["jev_gate_passed"])
    fn = sum(1 for p in both if p["llm_gate_passed"] and (not p["jev_gate_passed"]))
    tn = sum(1 for p in both if (not p["llm_gate_passed"]) and (not p["jev_gate_passed"]))
    precision = tp / (tp + fp) if (tp + fp) else None
    recall = tp / (tp + fn) if (tp + fn) else None
    accuracy = (tp + tn) / len(both) if both else None

    llm_slice = _simulate_top_slice(screen_papers, "llm")
    jev_slice = _simulate_top_slice(screen_papers, "jev")
    flip_in = sorted(jev_slice - llm_slice)
    flip_out = sorted(llm_slice - jev_slice)

    # Rank correlations
    corr: dict[str, float | None] = {}
    for dim in SCREEN_DIMS:
        xs, ys = [], []
        for p in screen_papers:
            if dim in (p.get("llm_scores") or {}) and dim in (p.get("jev_scores") or {}):
                xs.append(float(p["llm_scores"][dim]))
                ys.append(float(p["jev_scores"][dim]))
        corr[dim] = _spearman(xs, ys)
        corr[f"{dim}_n"] = len(xs)  # type: ignore[assignment]
    # rank mean corr
    xs, ys = [], []
    for p in screen_papers:
        if p.get("llm_rank_mean") is not None and p.get("jev_rank_mean") is not None:
            xs.append(float(p["llm_rank_mean"]))
            ys.append(float(p["jev_rank_mean"]))
    corr["rank_mean"] = _spearman(xs, ys)
    corr["rank_mean_n"] = len(xs)  # type: ignore[assignment]

    # Golden-60 agreement
    g_papers = [p for p in screen_papers if p["content_item_id"] in golden60 and p.get("jev_ok")]
    g_gate = [
        p
        for p in g_papers
        if p.get("llm_gate_passed") is not None and p.get("jev_gate_passed") is not None
    ]
    g_agree = sum(1 for p in g_gate if p["llm_gate_passed"] == p["jev_gate_passed"])
    g_dim_mae = {}
    for dim in SCREEN_DIMS:
        diffs = [
            abs(float(p["llm_scores"][dim]) - float(p["jev_scores"][dim]))
            for p in g_papers
            if dim in (p.get("llm_scores") or {}) and dim in (p.get("jev_scores") or {})
        ]
        g_dim_mae[dim] = statistics.mean(diffs) if diffs else None

    # Confidence bands vs gate accuracy
    bands = [(0.0, 0.6), (0.6, 0.7), (0.7, 0.8), (0.8, 0.9), (0.9, 1.01)]
    band_stats = []
    for lo, hi in bands:
        subset = [
            p
            for p in both
            if p.get("jev_confidence") is not None and lo <= float(p["jev_confidence"]) < hi
        ]
        if not subset:
            band_stats.append({"lo": lo, "hi": hi, "n": 0, "gate_accuracy": None})
            continue
        acc = sum(1 for p in subset if p["llm_gate_passed"] == p["jev_gate_passed"]) / len(subset)
        band_stats.append({"lo": lo, "hi": hi, "n": len(subset), "gate_accuracy": acc})

    # Cascade projections per 1000 papers
    # LLM screen unit cost from Sep16-21: $0.2504 / 2638 ≈ $0.0000949/paper
    llm_screen_per_paper = 0.2504 / 2638.0
    llm_audience_per_paper = 0.3546 / 2535.0  # phase_7a projection
    jev_screen_costs = [
        float(r.get("billable_cost_usd") or 0.0)
        for r in screen_results.values()
        if r.get("ok")
    ]
    jev_aud_costs = [
        float(r.get("billable_cost_usd") or 0.0)
        for r in audience_results.values()
        if r.get("ok")
    ]
    jev_screen_pp = statistics.mean(jev_screen_costs) if jev_screen_costs else None
    jev_aud_pp = statistics.mean(jev_aud_costs) if jev_aud_costs else None
    jev_screen_time_pp = (
        statistics.mean([float(r["elapsed_s"]) for r in screen_results.values() if r.get("ok")])
        if any(r.get("ok") for r in screen_results.values())
        else None
    )
    # Wall-clock for concurrent run → effective per-paper wall = total_wall / n
    jev_screen_wall_pp = t_screen / max(1, len(screen_papers))
    jev_aud_wall_pp = t_audience / max(1, len(audience_papers))
    # Approximate current LLM screen wall unknown; use batch estimate ~0.05s/paper effective
    # from Sep16-21 ~2638 papers in ~few minutes — use observed if we can't; report Jev only + relative.
    llm_screen_wall_pp_est = 0.05  # conservative placeholder noted in report

    cascade_rows = []
    for thr in (0.6, 0.7, 0.8, 0.9):
        decidable = [
            p
            for p in both
            if p.get("jev_confidence") is not None and float(p["jev_confidence"]) >= thr
        ]
        frac = len(decidable) / len(both) if both else 0.0
        if decidable:
            acc = sum(1 for p in decidable if p["llm_gate_passed"] == p["jev_gate_passed"]) / len(
                decidable
            )
        else:
            acc = None
        # per 1000: frac on Jev, (1-frac) on LLM
        if jev_screen_pp is not None:
            cost_1000 = 1000 * (frac * jev_screen_pp + (1 - frac) * llm_screen_per_paper)
        else:
            cost_1000 = None
        time_1000 = 1000 * (
            frac * jev_screen_wall_pp + (1 - frac) * llm_screen_wall_pp_est
        )
        cascade_rows.append(
            {
                "threshold": thr,
                "jev_fraction": frac,
                "gate_accuracy_on_decidable": acc,
                "cost_per_1000_usd": cost_1000,
                "wall_sec_per_1000_est": time_1000,
            }
        )

    # Audience agreement (domain / app when baseline exists)
    aud_domain_n = aud_domain_agree = 0
    aud_app_n = aud_app_agree = 0
    for p in audience_papers:
        rec = audience_results.get(p["content_item_id"]) or {}
        if not rec.get("ok"):
            continue
        parsed = rec.get("parsed") or {}
        base = p.get("classify") or {}
        dom = (parsed.get("domain") or {}).get("choice")
        if base.get("domain") and dom:
            aud_domain_n += 1
            if base["domain"] == dom:
                aud_domain_agree += 1
        app = (parsed.get("application_domain") or {}).get("choice")
        if base.get("application_domain") and app:
            aud_app_n += 1
            if base["application_domain"] == app:
                aud_app_agree += 1

    # Quality-stage note: Jev cannot emit so_what / reason_not_higher
    quality_note = {
        "replace_quality": False,
        "reason": (
            "Jev returns typed noul/choice/score only; editorial selection depends on "
            "so_what and reason_not_higher prose from Sol/Terra. At most, Jev could "
            "shadow the six rubric scores while an LLM keeps the prose — not evaluated "
            "as a replacement in J1."
        ),
    }

    summary = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "model": JEV_MODEL_PINNED,
        "db_available": db_ok,
        "data_source": "openrouter_raw_cache + arxiv_api + reports (DB schema grants missing for neural_rw)",
        "gate_percentile_config": GATE_PERCENTILE,
        "top_slice_keep_pct": GATE_PERCENTILE,
        "screen": {
            "n": len(screen_papers),
            "ok": sum(1 for r in screen_results.values() if r.get("ok")),
            "gate": {
                "n": len(both),
                "tp": tp,
                "fp": fp,
                "fn": fn,
                "tn": tn,
                "precision": precision,
                "recall": recall,
                "accuracy": accuracy,
            },
            "top_slice": {
                "llm_selected": len(llm_slice),
                "jev_selected": len(jev_slice),
                "flip_in": len(flip_in),
                "flip_out": len(flip_out),
                "flip_in_ids": flip_in[:30],
                "flip_out_ids": flip_out[:30],
            },
            "spearman": corr,
            "golden60": {
                "n_in_sample": len(g_papers),
                "gate_n": len(g_gate),
                "gate_agree": g_agree,
                "gate_accuracy": (g_agree / len(g_gate)) if g_gate else None,
                "dim_mae": g_dim_mae,
            },
            "confidence_bands": band_stats,
            "cost_usd": screen_spend,
            "wall_s": t_screen,
            "per_paper_cost_usd": jev_screen_pp,
            "per_paper_wall_s": jev_screen_wall_pp,
        },
        "audience": {
            "n": len(audience_papers),
            "ok": sum(1 for r in audience_results.values() if r.get("ok")),
            "domain_agreement": {
                "n": aud_domain_n,
                "agree": aud_domain_agree,
                "accuracy": (aud_domain_agree / aud_domain_n) if aud_domain_n else None,
            },
            "application_domain_agreement": {
                "n": aud_app_n,
                "agree": aud_app_agree,
                "accuracy": (aud_app_agree / aud_app_n) if aud_app_n else None,
            },
            "seat_score_baseline": "mostly absent (AUDIENCE_POLICY still v001; no tech/product rows)",
            "cost_usd": audience_spend,
            "wall_s": t_audience,
            "per_paper_cost_usd": jev_aud_pp,
            "per_paper_wall_s": jev_aud_wall_pp,
        },
        "cascade_screen": cascade_rows,
        "cost_per_1000": {
            "screen_llm_usd": 1000 * llm_screen_per_paper,
            "screen_jev_usd": (1000 * jev_screen_pp) if jev_screen_pp is not None else None,
            "audience_llm_usd": 1000 * llm_audience_per_paper,
            "audience_jev_usd": (1000 * jev_aud_pp) if jev_aud_pp is not None else None,
        },
        "quality_stage": quality_note,
        "budget": {
            "cap_usd": args.max_cost_usd,
            "spent_usd": total_spend,
            "stopped": budget.stopped,
        },
        "proposed_threshold": None,
    }

    # Propose threshold: highest thr with decidable gate accuracy >= 0.9 and frac >= 0.3
    proposal = None
    for row in sorted(cascade_rows, key=lambda r: r["threshold"]):
        acc = row["gate_accuracy_on_decidable"]
        if acc is not None and acc >= 0.90 and row["jev_fraction"] >= 0.25:
            proposal = row
    if proposal is None:
        # fallback: best accuracy among thr with n-equivalent frac>0
        cand = [r for r in cascade_rows if r["gate_accuracy_on_decidable"] is not None]
        if cand:
            proposal = max(cand, key=lambda r: (r["gate_accuracy_on_decidable"], r["threshold"]))
    summary["proposed_threshold"] = proposal

    JSON_PATH.write_text(json.dumps(summary, indent=2, default=str), encoding="utf-8")

    # Markdown report
    def pct(x: float | None) -> str:
        return "n/a" if x is None else f"{100 * x:.1f}%"

    def money(x: float | None) -> str:
        return "n/a" if x is None else f"${x:.4f}"

    lines = [
        "# Jev shadow evaluation (Phase J1) — STOP",
        "",
        f"**Generated:** {summary['generated_at']}  ",
        f"**Model:** `{JEV_MODEL_PINNED}` (pinned; jev-latest forbidden)  ",
        f"**Spend:** ${total_spend:.4f} / cap ${args.max_cost_usd:.2f}  ",
        f"**Defaults changed:** none (screen/audience engines still LLM)  ",
        f"**DB:** `neural_rw` lacked `paper_intelligence` USAGE at run time; "
        "sample rebuilt from OpenRouter raw caches + arXiv API + report id maps.",
        "",
        "## Scope",
        "",
        f"- Screen shadow: **{len(screen_papers)}** Sep-2026 papers with existing LLM screen scores",
        f"- Audience shadow: **{len(audience_papers)}** papers (title+abstract → seat scores + domain/app)",
        f"- Golden-60 (Sol/Terra calibration ids) in screen sample: **{len(g_papers)}**",
        "- Quality stage: **not replaced** (no `so_what` / `reason_not_higher`)",
        "",
        "## Screen gate agreement (Jev vs current LLM gate)",
        "",
        f"| Metric | Value |",
        f"|---|---:|",
        f"| N (comparable) | {len(both)} |",
        f"| Accuracy | {pct(accuracy)} |",
        f"| Precision (Jev pass \\| LLM pass) | {pct(precision)} |",
        f"| Recall | {pct(recall)} |",
        f"| TP / FP / FN / TN | {tp} / {fp} / {fn} / {tn} |",
        "",
        "### Top-slice flips (day scope, interpreted keep % from `GATE_PERCENTILE`)",
        "",
        f"- Config `GATE_PERCENTILE={GATE_PERCENTILE}` → keep top "
        f"**{summary['top_slice_keep_pct']}%** per day among gate-passers in the sample.",
        f"- LLM selected: **{len(llm_slice)}** · Jev selected: **{len(jev_slice)}**",
        f"- Flip **in** (Jev only): **{len(flip_in)}** · Flip **out** (LLM only): **{len(flip_out)}**",
        "",
        "## Rank correlation (Spearman, LLM vs Jev 0–10 mapped scores)",
        "",
        "| Dimension | Spearman | N |",
        "|---|---:|---:|",
    ]
    for dim in SCREEN_DIMS + ("rank_mean",):
        lines.append(f"| {dim} | {corr.get(dim)} | {corr.get(dim + '_n')} |")

    lines += [
        "",
        "## Golden-60 agreement",
        "",
        f"- In sample with Jev ok: **{len(g_papers)}**",
        f"- Gate agreement: **{g_agree}/{len(g_gate)}** ({pct((g_agree/len(g_gate)) if g_gate else None)})",
        "- Mean |Δ| by dimension:",
    ]
    for dim, mae in g_dim_mae.items():
        lines.append(f"  - `{dim}`: {mae}")

    lines += [
        "",
        "## Jev confidence bands (screen mean confidence vs gate agreement)",
        "",
        "| Band | N | Gate accuracy |",
        "|---|---:|---:|",
    ]
    for b in band_stats:
        lines.append(
            f"| [{b['lo']:.1f}, {b['hi']:.1f}) | {b['n']} | {pct(b['gate_accuracy'])} |"
        )

    lines += [
        "",
        "## Cost and wall-clock",
        "",
        "| Stage | N ok | Provider/billable $ | Wall (s) | $/paper | wall s/paper |",
        "|---|---:|---:|---:|---:|---:|",
        f"| Jev screen | {summary['screen']['ok']} | {money(screen_spend)} | {t_screen:.1f} | {money(jev_screen_pp)} | {jev_screen_wall_pp:.3f} |",
        f"| Jev audience | {summary['audience']['ok']} | {money(audience_spend)} | {t_audience:.1f} | {money(jev_aud_pp)} | {jev_aud_wall_pp:.3f} |",
        f"| LLM screen (Sep16–21 actual) | 2638 | $0.2504 | — | {money(llm_screen_per_paper)} | ~{llm_screen_wall_pp_est:.2f} est |",
        f"| LLM audience (7a dry-run) | 2535 | $0.3546 | — | {money(llm_audience_per_paper)} | — |",
        "",
        "### Cost per 1,000 papers",
        "",
        f"| Stage | Before (LLM) | After (100% Jev) |",
        f"|---|---:|---:|",
        f"| Screen | {money(summary['cost_per_1000']['screen_llm_usd'])} | {money(summary['cost_per_1000']['screen_jev_usd'])} |",
        f"| Audience | {money(summary['cost_per_1000']['audience_llm_usd'])} | {money(summary['cost_per_1000']['audience_jev_usd'])} |",
        "",
        "## Cascade proposal (screen)",
        "",
        "| Threshold | Jev fraction | Gate accuracy on decidable | $/1k | wall s/1k (est) |",
        "|---:|---:|---:|---:|---:|",
    ]
    for row in cascade_rows:
        lines.append(
            f"| {row['threshold']:.1f} | {pct(row['jev_fraction'])} | "
            f"{pct(row['gate_accuracy_on_decidable'])} | {money(row['cost_per_1000_usd'])} | "
            f"{row['wall_sec_per_1000_est']:.0f} |"
        )
    if proposal:
        lines += [
            "",
            f"**Proposed threshold for J2 cascade:** `{proposal['threshold']}` "
            f"(Jev fraction {pct(proposal['jev_fraction'])}, "
            f"decidable gate accuracy {pct(proposal['gate_accuracy_on_decidable'])}, "
            f"{money(proposal['cost_per_1000_usd'])}/1k screen).",
        ]

    lines += [
        "",
        "## Audience shadow notes",
        "",
        f"- Domain agreement vs cached classify labels: "
        f"**{aud_domain_agree}/{aud_domain_n}** ({pct((aud_domain_agree/aud_domain_n) if aud_domain_n else None)})",
        f"- Application-domain agreement: "
        f"**{aud_app_agree}/{aud_app_n}** ({pct((aud_app_agree/aud_app_n) if aud_app_n else None)})",
        "- `tech_relevance` / `product_relevance` baselines are largely absent until audience v002 runs; "
        "Jev seat scores were collected for cost/latency but not accuracy-benchmarked against LLM seats.",
        "",
        "## Quality stage",
        "",
        quality_note["reason"],
        "",
        "## J2 (not started)",
        "",
        "Awaiting threshold approval. Then: `SCREEN_ENGINE` / `AUDIENCE_ENGINE` ∈ "
        "`{llm, jev, cascade}` defaulting to **`llm`**, with engine+version stamped on result rows.",
        "",
        "## STOP",
        "",
        "No pipeline defaults changed. Artifacts:",
        f"- `{REPORT_PATH.relative_to(ROOT)}`",
        f"- `{JSON_PATH.relative_to(ROOT)}`",
        "",
    ]
    REPORT_PATH.write_text("\n".join(lines), encoding="utf-8")
    print(f"wrote {REPORT_PATH}", flush=True)
    print(f"wrote {JSON_PATH}", flush=True)
    print(json.dumps({"spent": total_spend, "proposed": proposal}, default=str), flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
