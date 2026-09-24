#!/usr/bin/env python3
"""Build reports/golden/jev_glm_run_sep21_23.md from golden gate + Sep window.

  PYTHONPATH=src QUALITY_ENGINE=jev_glm python3 scripts/write_jev_glm_report.py
"""

from __future__ import annotations

import json
import math
import statistics
import sys
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from paper_intelligence.db import connect  # noqa: E402
from paper_intelligence.quality.stage import RUBRIC_DIMENSIONS, WEIGHTS  # noqa: E402

REPORT_DIR = ROOT / "reports" / "golden"
OUT = REPORT_DIR / "jev_glm_run_sep21_23.md"
GATE_JSON = REPORT_DIR / "jev_glm_gate.json"
GOLDEN_RUN = REPORT_DIR / "jev_glm_golden_run.json"
PIPE_RUN = REPORT_DIR / "jev_glm_sep21_23_run.json"
BASELINE = REPORT_DIR / "baseline_v1.md"
G3C = REPORT_DIR / "g3c_weight_fit.json"

DATE_FROM = "2026-09-21"
DATE_UNTIL = "2026-09-23"


def _spearman(xs: list[float], ys: list[float]) -> float | None:
    if len(xs) < 3:
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


def _g3c_line(scores: dict[str, float]) -> float:
    """Reported-only G3c option (a) Ridge weights — NOT stored."""
    # From g3c_weight_fit.md full-data signed coefs + intercept
    intercept = 2.7158
    coefs = {
        "technical_significance": -0.9491,
        "apparent_novelty": 0.0406,
        "practical_applicability": 0.7221,
        "professional_value": 1.2236,
        "learning_value": -0.2747,
        "evidence_strength": -0.2047,
    }
    return intercept + sum(coefs[d] * float(scores[d]) for d in coefs)


def _load_gate() -> dict[str, Any] | None:
    if GATE_JSON.exists():
        return json.loads(GATE_JSON.read_text(encoding="utf-8"))
    return None


def _window_funnel() -> dict[str, Any]:
    with connect() as conn:
        papers = conn.execute(
            """
            SELECT paper_id, published_at::date AS d
            FROM paper_intelligence.papers
            WHERE published_at::date BETWEEN %s::date AND %s::date
            """,
            (DATE_FROM, DATE_UNTIL),
        ).fetchall()
        ids = [int(r["paper_id"]) for r in papers]
        by_day_papers: dict[str, int] = Counter(str(r["d"]) for r in papers)

        screen = conn.execute(
            """
            SELECT DISTINCT ON (content_item_id) content_item_id, result_json, created_at::date AS d
            FROM paper_intelligence.paper_classification_results
            WHERE task_type='screen' AND content_item_id = ANY(%s)
            ORDER BY content_item_id, created_at DESC
            """,
            (ids,),
        ).fetchall() if ids else []
        quality = conn.execute(
            """
            SELECT DISTINCT ON (content_item_id)
              content_item_id, result_json, model, method, created_at,
              (SELECT published_at::date FROM paper_intelligence.papers p
               WHERE p.paper_id = content_item_id) AS d
            FROM paper_intelligence.paper_classification_results
            WHERE task_type='quality'
              AND model = 'typesafe/jev-1.13'
              AND prompt_version = 'prose_v001'
              AND content_item_id = ANY(%s)
            ORDER BY content_item_id, created_at DESC
            """,
            (ids,),
        ).fetchall() if ids else []

        current = conn.execute(
            """
            SELECT c.paper_id, c.quality_status, c.adjudication_json,
                   p.published_at::date AS d, p.title, p.arxiv_id
            FROM paper_intelligence.paper_intelligence_current c
            JOIN paper_intelligence.papers p ON p.paper_id = c.paper_id
            WHERE p.published_at::date BETWEEN %s::date AND %s::date
            """,
            (DATE_FROM, DATE_UNTIL),
        ).fetchall()

    screen_pass = 0
    for r in screen:
        rj = r["result_json"] or {}
        if isinstance(rj, str):
            rj = json.loads(rj)
        gate = rj.get("gate") or {}
        if gate.get("passed") is True or (
            isinstance(rj.get("ai_relevance"), (int, float)) and float(rj["ai_relevance"]) >= 5.0
        ):
            screen_pass += 1

    q_by_day: dict[str, list[float]] = defaultdict(list)
    prose_ok = 0
    prose_null = 0
    top_rows = []
    for r in quality:
        rj = r["result_json"] or {}
        if isinstance(rj, str):
            rj = json.loads(rj)
        if (rj.get("quality_engine") or "") != "jev_glm" and (rj.get("scoring_engine") or "") != "jev":
            # still count systemone_v001 stamps
            pass
        comp = rj.get("composite") or {}
        q = None
        if isinstance(comp, dict) and comp.get("quality") is not None:
            q = float(comp["quality"])
        elif all(rj.get(d) is not None for d in RUBRIC_DIMENSIONS):
            q = sum(WEIGHTS[d] * float(rj[d]) for d in WEIGHTS)
        if q is None:
            continue
        day = str(r["d"]) if r.get("d") else "?"
        q_by_day[day].append(q)
        if rj.get("so_what"):
            prose_ok += 1
        else:
            prose_null += 1
        top_rows.append(
            {
                "paper_id": int(r["content_item_id"]),
                "quality": q,
                "so_what": rj.get("so_what"),
                "reason_not_higher": rj.get("reason_not_higher"),
                "dims": {d: rj.get(d) for d in RUBRIC_DIMENSIONS},
            }
        )

    # Enrich top with titles/orgs
    top_rows.sort(key=lambda x: (-x["quality"], x["paper_id"]))
    top20_ids = [t["paper_id"] for t in top_rows[:20]]
    meta: dict[int, dict[str, Any]] = {}
    if top20_ids:
        with connect() as conn:
            brows = conn.execute(
                """
                SELECT paper_id, title, arxiv_id FROM paper_intelligence.papers
                WHERE paper_id = ANY(%s)
                """,
                (top20_ids,),
            ).fetchall()
            for b in brows:
                meta[int(b["paper_id"])] = {
                    "title": b["title"],
                    "arxiv_id": b["arxiv_id"],
                    "arxiv_url": f"https://arxiv.org/abs/{b['arxiv_id']}" if b.get("arxiv_id") else "",
                    "organisations": "",
                }
            try:
                orows = conn.execute(
                    """
                    SELECT content_item_id AS paper_id,
                           string_agg(DISTINCT organisation_name, '; ') AS orgs
                    FROM paper_intelligence.paper_organisations
                    WHERE content_item_id = ANY(%s)
                    GROUP BY content_item_id
                    """,
                    (top20_ids,),
                ).fetchall()
                for o in orows:
                    if int(o["paper_id"]) in meta:
                        meta[int(o["paper_id"])]["organisations"] = o["orgs"] or ""
            except Exception:
                try:
                    conn.rollback()
                except Exception:
                    pass

    for t in top_rows[:20]:
        t.update(meta.get(t["paper_id"], {}))

    # Prose samples across score range
    samples = []
    if top_rows:
        n = len(top_rows)
        idxs = sorted({0, n // 7, 2 * n // 7, 3 * n // 7, 4 * n // 7, 5 * n // 7, 6 * n // 7, n - 1})
        # Prefer 15 spread
        step = max(1, n // 15)
        idxs = list(range(0, n, step))[:15]
        sample_ids = [top_rows[i]["paper_id"] for i in idxs]
        with connect() as conn:
            brows = conn.execute(
                "SELECT paper_id, title, arxiv_id FROM paper_intelligence.papers WHERE paper_id = ANY(%s)",
                (sample_ids,),
            ).fetchall()
            titles = {int(b["paper_id"]): b for b in brows}
        for i in idxs:
            t = top_rows[i]
            b = titles.get(t["paper_id"], {})
            samples.append(
                {
                    **t,
                    "title": b.get("title"),
                    "arxiv_id": b.get("arxiv_id"),
                }
            )

    scored_status = Counter(
        (r.get("quality_status") or "?") for r in current
    )

    return {
        "n_papers": len(ids),
        "by_day_papers": dict(by_day_papers),
        "n_screen_rows": len(screen),
        "n_screen_pass_est": screen_pass,
        "n_quality_jev_glm": len(top_rows),
        "prose_ok": prose_ok,
        "prose_null": prose_null,
        "q_by_day": {d: {"n": len(vs), "mean": statistics.mean(vs) if vs else None,
                         "p50": statistics.median(vs) if vs else None} for d, vs in sorted(q_by_day.items())},
        "quality_status_counts": dict(scored_status),
        "top20": top_rows[:20],
        "prose_samples": samples,
        "all_qualities": [t["quality"] for t in top_rows],
    }


def _cost_from_logs() -> dict[str, Any]:
    out: dict[str, Any] = {"projected": {"screen": 0.0396, "audience_domain": 0.1695,
                                          "quality_jev": 0.0226, "quality_glm_prose": 0.0606,
                                          "quality_total": 0.0832, "paid_total": 0.29}}
    # Try parse pipeline log for actuals
    log = REPORT_DIR / "jev_glm_sep21_23_pipeline.log"
    if log.exists():
        text = log.read_text(encoding="utf-8", errors="replace")
        out["log_tail"] = text[-2000:]
        # crude extract of budget lines
        actuals = []
        for line in text.splitlines():
            if "budget: projected=" in line and "actual=" in line:
                actuals.append(line.strip())
        out["budget_lines"] = actuals[-20:]
    if PIPE_RUN.exists():
        out["run_meta"] = json.loads(PIPE_RUN.read_text(encoding="utf-8"))
    if GOLDEN_RUN.exists():
        out["golden_run"] = json.loads(GOLDEN_RUN.read_text(encoding="utf-8"))
    return out


def main() -> int:
    gate = _load_gate()
    window = _window_funnel()
    costs = _cost_from_logs()
    g3c = json.loads(G3C.read_text(encoding="utf-8")) if G3C.exists() else {}

    lines = [
        "# Jev+GLM quality run — Sep 21–23 + golden gate",
        "",
        f"**Generated:** {datetime.now(timezone.utc).isoformat()}  ",
        f"**QUALITY_ENGINE:** `jev_glm` (Jev `typesafe/jev-1.13` + policy `quality_v001` scores; "
        f"GLM `z-ai/glm-5.3-flash` prose)  ",
        "**Weights:** CURRENT composite weights only (G3c refit reported separately, not stored).  ",
        "**Window:** 2026-09-21 … 2026-09-23 — **PARTIAL** (Sep 22–23 inside arXiv announcement lag).  ",
        "",
        "---",
        "",
        "## 1. Verifier gate (arithmetic vs golden labels — no LLM judge)",
        "",
    ]

    if not gate:
        lines += [
            "_Gate results not yet written (`reports/golden/jev_glm_gate.json` missing)._",
            "",
        ]
    else:
        verdict = gate.get("verdict", "Cannot be determined")
        lines += [
            f"**Verdict: {verdict}**  ",
            f"n_scored={gate.get('n_scored')} · compared to baseline_v1.md column "
            f"**`{gate.get('baseline_column')}`** (intersection baseline).",
            "",
            "| Dimension | jev_glm Spearman | baseline | Δ | floor (baseline−0.05) | Pass? |",
            "|---|---:|---:|---:|---:|---|",
        ]
        for dim, row in (gate.get("dims") or {}).items():
            lines.append(
                f"| {dim} | {row.get('spearman')} | {row.get('baseline')} | "
                f"{row.get('delta')} | {row.get('floor')} | "
                f"{'yes' if row.get('pass') else 'NO'} |"
            )
        lines += [
            "",
            f"Composite vs h_final Spearman: **{gate.get('composite_spearman')}** "
            f"(baseline {gate.get('composite_baseline')})",
            f"recall@20: **{gate.get('recall_at_20')}** · recall@50: **{gate.get('recall_at_50')}** "
            f"(baseline recall@50 {gate.get('recall_at_50_baseline')}) → "
            f"{'pass' if gate.get('recall_pass') else 'FAIL'}",
            "",
            f"### G3c refitted weights (reported only — NOT stored)",
            "",
            f"Option (a) Ridge OOF-style on these jev_glm rows: Spearman **{gate.get('g3c_spearman')}** / "
            f"recall@20 **{gate.get('g3c_recall_at_20')}** / recall@50 **{gate.get('g3c_recall_at_50')}**",
            "",
            f"Notes: {gate.get('notes')}",
            "",
        ]

    lines += [
        "---",
        "",
        "## 2. Sep 21–23 window (descriptive — no human labels)",
        "",
        f"Papers in window: **{window['n_papers']}** · "
        f"jev_glm quality rows: **{window['n_quality_jev_glm']}** · "
        f"prose OK / NULL: **{window['prose_ok']}** / **{window['prose_null']}**",
        "",
        "### Per-day funnel",
        "",
        "| Day | papers | quality n | mean quality | p50 |",
        "|---|---:|---:|---:|---:|",
    ]
    for day, n in sorted((window.get("by_day_papers") or {}).items()):
        qd = (window.get("q_by_day") or {}).get(day) or {}
        lines.append(
            f"| {day} | {n} | {qd.get('n', 0)} | "
            f"{qd.get('mean') if qd.get('mean') is None else round(qd['mean'], 3)} | "
            f"{qd.get('p50') if qd.get('p50') is None else round(qd['p50'], 3)} |"
        )

    lines += [
        "",
        f"Current quality_status counts: `{window.get('quality_status_counts')}`",
        "",
        "### Cost — projected vs actual",
        "",
        "| Stage | Projected USD |",
        "|---|---:|",
        f"| screen (flash) | {costs['projected']['screen']} |",
        f"| audience_domain | {costs['projected']['audience_domain']} |",
        f"| quality — Jev scoring | {costs['projected']['quality_jev']} |",
        f"| quality — GLM prose | {costs['projected']['quality_glm_prose']} |",
        f"| quality total | {costs['projected']['quality_total']} |",
        f"| **paid total (dry-run)** | **{costs['projected']['paid_total']}** |",
        "",
    ]
    if costs.get("budget_lines"):
        lines.append("Budget lines from pipeline log:")
        lines.append("```")
        lines.extend(costs["budget_lines"])
        lines.append("```")
        lines.append("")
    if costs.get("golden_run"):
        lines.append(
            f"Golden eval run cost: `${costs['golden_run'].get('cost_usd')}` "
            f"(run_id `{costs['golden_run'].get('run_id')}`)"
        )
        lines.append("")

    quals = window.get("all_qualities") or []
    if quals:
        lines += [
            "### Jev score distribution (quality = Σw·dim)",
            "",
            f"n={len(quals)} mean={statistics.mean(quals):.3f} "
            f"p50={statistics.median(quals):.3f} "
            f"min={min(quals):.2f} max={max(quals):.2f}",
            "",
        ]

    lines += [
        "### Top 20 by quality_score",
        "",
        "| rank | quality | paper_id | arxiv | title | organisations |",
        "|---:|---:|---:|---|---|---|",
    ]
    for i, t in enumerate(window.get("top20") or [], 1):
        title = (t.get("title") or "")[:80].replace("|", "/")
        orgs = (t.get("organisations") or "")[:40].replace("|", "/")
        aid = t.get("arxiv_id") or ""
        url = t.get("arxiv_url") or (f"https://arxiv.org/abs/{aid}" if aid else "")
        lines.append(
            f"| {i} | {t['quality']:.2f} | {t['paper_id']} | [{aid}]({url}) | {title} | {orgs} |"
        )

    lines += [
        "",
        "### GLM prose samples (15 across score range)",
        "",
    ]
    for t in window.get("prose_samples") or []:
        lines += [
            f"#### paper_id={t['paper_id']} · quality={t['quality']:.2f} · "
            f"{t.get('arxiv_id')}",
            "",
            f"**Title:** {t.get('title')}",
            "",
            f"**so_what:** {t.get('so_what') or '_NULL_'}",
            "",
            f"**reason_not_higher:** {t.get('reason_not_higher') or '_NULL_'}",
            "",
        ]

    if not window.get("prose_samples"):
        lines += [
            "_No jev_glm quality rows in window yet (pipeline still running or empty)._",
            "",
        ]

    lines += [
        "---",
        "",
        "## STOP",
        "",
        "- No weight / threshold / policy / default changes.",
        f"- Artifacts: `{OUT.relative_to(ROOT)}`, `{GATE_JSON.name}`, "
        f"`{GOLDEN_RUN.name}`, `{PIPE_RUN.name}`",
        "",
    ]
    REPORT_DIR.mkdir(parents=True, exist_ok=True)
    OUT.write_text("\n".join(lines), encoding="utf-8")
    print(f"wrote {OUT}", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
