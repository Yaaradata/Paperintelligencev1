#!/usr/bin/env python3
"""Export blind golden labelling workbook (Phase G1). NO paid calls.

  PYTHONPATH=src python3 scripts/export_golden_template.py

Writes:
  golden/golden_labelling_200.xlsx   — human labelling (no model scores)
  golden/model_scores_hidden.csv     — Terra/Jev for the same 200 ids
"""

from __future__ import annotations

import csv
import json
import sys
from collections import defaultdict
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

import yaml  # noqa: E402
from openpyxl import Workbook  # noqa: E402
from openpyxl.styles import Alignment, Font, PatternFill  # noqa: E402
from openpyxl.utils import get_column_letter  # noqa: E402
from openpyxl.worksheet.datavalidation import DataValidation  # noqa: E402

from paper_intelligence.db import connect  # noqa: E402

GOLDEN_DIR = ROOT / "golden"
XLSX_OUT = GOLDEN_DIR / "golden_labelling_200.xlsx"
HIDDEN_CSV = GOLDEN_DIR / "model_scores_hidden.csv"
TERRA_JEV = ROOT / "reports" / "review_fixes" / "terra_vs_jev_1000.csv"
JEV_CACHE = ROOT / "reports" / "review_fixes" / "jev_j1b_quality_scores.json"
JEV_V002 = ROOT / "reports" / "review_fixes" / "jev_j1b_quality_scores_v002.json"
SEAT_VAL = ROOT / "reports" / "review_fixes" / "seat_validation_set.json"
CLASS_POL = ROOT / "policies" / "classification" / "v002.yaml"
SEATS_POL = ROOT / "policies" / "editorial_seats" / "v001.yaml"
QUALITY_PROMPT = ROOT / "prompts" / "quality" / "v002.md"

TARGET_N = 200
FLAGGED_ARXIV = ("2609.20519", "2609.15779", "2609.03181", "2609.15983")
STRATUM_ORDER = (
    "editorial_pick",
    "flagged",
    "max_disagreement",
    "score_strata",
    "screen_failed",
)

SCORE_COLS = (
    "h_ai_relevance",
    "h_technical_significance",
    "h_apparent_novelty",
    "h_practical_applicability",
    "h_professional_value",
    "h_learning_value",
    "h_evidence_strength",
    "h_tech_relevance",
    "h_product_relevance",
    "h_final_score",
)

LABEL_HEADERS = (
    "row_no",
    "paper_id",
    "arxiv_id",
    "arxiv_url",
    "title",
    "abstract",
    "published_at",
    "organisations",
    "sample_stratum",
    *SCORE_COLS,
    "h_domain",
    "h_application_domain",
    "h_newsletter_verdict",
    "h_reject_reason",
    "h_notes",
)

VERDICTS = ("winner_material", "shortlist", "maybe", "reject")


def _half_steps() -> list[str]:
    return [f"{i / 2:.1f}" for i in range(0, 21)]


def _load_vocab() -> tuple[list[str], list[str]]:
    data = yaml.safe_load(CLASS_POL.read_text(encoding="utf-8")) or {}
    domains = [str(x) for x in (data.get("domain") or [])]
    apps = [str(x) for x in (data.get("application_domain") or [])]
    if not domains or not apps:
        raise RuntimeError(f"empty domain vocab in {CLASS_POL}")
    return domains, apps


def _editorial_pick_ids() -> list[int]:
    """Every past newsletter + LinkedIn winner / runner-up (deduped, stable)."""
    ids: list[int] = []
    seen: set[int] = set()

    def add(cid: int | None) -> None:
        if cid is None:
            return
        cid = int(cid)
        if cid in seen:
            return
        seen.add(cid)
        ids.append(cid)

    if SEAT_VAL.exists():
        seat = json.loads(SEAT_VAL.read_text(encoding="utf-8"))
        for p in seat.get("past_editorial_picks") or []:
            add(p.get("content_item_id"))

    # Explicit newsletter / LinkedIn selection files (winners + runners-up).
    paths = [
        ROOT / "reports" / "newsletter_picks_2026-09-01_to_2026-09-15.json",
        ROOT / "reports" / "editorial" / "august_newsletter_selection.json",
        ROOT / "reports" / "editorial" / "august_linkedin_selection.json",
    ]
    for path in paths:
        if not path.exists():
            continue
        data = json.loads(path.read_text(encoding="utf-8"))
        if "tech_pick" in data:  # sep newsletter shape
            for key in ("tech_pick", "product_pick"):
                block = data.get(key) or {}
                add(block.get("content_item_id"))
                add(block.get("runner_up_id"))
            continue
        for key, block in data.items():
            if not isinstance(block, dict):
                continue
            role = str(block.get("role") or "")
            if role in {"winner", "runner_up", "linkedin_winner"} or key.endswith(
                ("runner_up", "pick", "tech", "product")
            ):
                if "content_item_id" in block:
                    add(block.get("content_item_id"))
            # nested runner keys
            if key.endswith("runner_up") or "runner_up" in key:
                add(block.get("content_item_id"))
        # also walk known seat keys
        for key in (
            "tech",
            "product",
            "tech_runner_up",
            "product_runner_up",
            "tech_linkedin",
            "product_linkedin",
        ):
            block = data.get(key)
            if isinstance(block, dict):
                add(block.get("content_item_id"))
    return ids


def _load_terra_jev_csv() -> list[dict[str, Any]]:
    if not TERRA_JEV.exists():
        return []
    with TERRA_JEV.open(encoding="utf-8", newline="") as f:
        return list(csv.DictReader(f))


def _orgs_by_id(conn, ids: list[int]) -> dict[int, str]:
    if not ids:
        return {}
    rows = conn.execute(
        """
        SELECT a.content_item_id, o.canonical_name
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
        buckets.setdefault(int(r["content_item_id"]), []).append(str(r["canonical_name"]))
    return {k: "; ".join(dict.fromkeys(v)) for k, v in buckets.items()}


def _fetch_papers(conn, ids: list[int]) -> dict[int, dict[str, Any]]:
    if not ids:
        return {}
    rows = conn.execute(
        """
        SELECT paper_id, arxiv_id, title, abstract, published_at
        FROM paper_intelligence.papers
        WHERE paper_id = ANY(%s)
        """,
        (ids,),
    ).fetchall()
    out = {}
    for r in rows:
        aid = r["arxiv_id"]
        out[int(r["paper_id"])] = {
            "paper_id": int(r["paper_id"]),
            "arxiv_id": aid or "",
            "arxiv_url": f"https://arxiv.org/abs/{aid}" if aid else "",
            "title": r["title"] or "",
            "abstract": r["abstract"] or "",
            "published_at": str(r["published_at"]) if r["published_at"] is not None else "",
        }
    return out


def _papers_by_arxiv(conn, arxiv_ids: list[str]) -> dict[str, dict[str, Any]]:
    rows = conn.execute(
        """
        SELECT paper_id, arxiv_id, title, abstract, published_at
        FROM paper_intelligence.papers
        WHERE arxiv_id = ANY(%s)
        """,
        (list(arxiv_ids),),
    ).fetchall()
    out = {}
    for r in rows:
        aid = str(r["arxiv_id"] or "")
        out[aid] = {
            "paper_id": int(r["paper_id"]),
            "arxiv_id": aid,
            "arxiv_url": f"https://arxiv.org/abs/{aid}" if aid else "",
            "title": r["title"] or "",
            "abstract": r["abstract"] or "",
            "published_at": str(r["published_at"]) if r["published_at"] is not None else "",
        }
    return out


def _screen_failures_sep16_21(conn, limit: int = 20) -> list[int]:
    rows = conn.execute(
        """
        SELECT DISTINCT ON (q.content_item_id)
          q.content_item_id,
          q.result_json,
          q.created_at
        FROM paper_intelligence.paper_classification_results q
        JOIN paper_intelligence.papers p ON p.paper_id = q.content_item_id
        WHERE q.task_type = 'screen'
          AND p.published_at >= '2026-09-16'
          AND p.published_at < '2026-09-22'
        ORDER BY q.content_item_id, q.created_at DESC
        """
    ).fetchall()
    fails: list[int] = []
    for r in rows:
        rj = r["result_json"] or {}
        if isinstance(rj, str):
            rj = json.loads(rj)
        gate = rj.get("gate") or {}
        passed = gate.get("passed")
        if passed is None:
            try:
                passed = float(rj.get("ai_relevance") or 0) >= 5.0
            except (TypeError, ValueError):
                passed = False
        if not passed:
            fails.append(int(r["content_item_id"]))
        if len(fails) >= limit * 3:  # gather extra; trim later
            break
    return fails


def _terra_composites_sep(conn) -> list[tuple[int, float]]:
    rows = conn.execute(
        """
        SELECT DISTINCT ON (q.content_item_id)
          q.content_item_id,
          q.result_json
        FROM paper_intelligence.paper_classification_results q
        JOIN paper_intelligence.papers p ON p.paper_id = q.content_item_id
        WHERE q.task_type = 'quality'
          AND q.model LIKE '%%terra%%'
          AND p.published_at >= '2026-09-01'
          AND p.published_at < '2026-09-22'
        ORDER BY q.content_item_id, q.created_at DESC
        """
    ).fetchall()
    out: list[tuple[int, float]] = []
    for r in rows:
        rj = r["result_json"] or {}
        if isinstance(rj, str):
            rj = json.loads(rj)
        comp = rj.get("composite") or {}
        if isinstance(comp, dict) and comp.get("quality") is not None:
            out.append((int(r["content_item_id"]), float(comp["quality"])))
    out.sort(key=lambda t: t[1])
    return out


def _select_sample(conn) -> tuple[list[dict[str, Any]], dict[str, int]]:
    """Return ordered paper rows with sample_stratum; counts per stratum."""
    selected: dict[int, str] = {}  # paper_id -> stratum (first wins)

    def take(cid: int, stratum: str) -> bool:
        if cid in selected:
            return False
        selected[cid] = stratum
        return True

    # (a) editorial
    for cid in _editorial_pick_ids():
        take(cid, "editorial_pick")

    # (b) flagged by arxiv
    by_aid = _papers_by_arxiv(conn, list(FLAGGED_ARXIV))
    missing_flagged = [a for a in FLAGGED_ARXIV if a not in by_aid]
    if missing_flagged:
        print(f"WARNING: flagged arxiv not in DB: {missing_flagged}", flush=True)
    for aid in FLAGGED_ARXIV:
        if aid in by_aid:
            take(by_aid[aid]["paper_id"], "flagged")

    # (c) max disagreement 30+30
    tj = _load_terra_jev_csv()
    jev_higher = sorted(
        [r for r in tj if int(float(r["rank_gap"])) > 0],
        key=lambda r: -abs(int(float(r["rank_gap"]))),
    )
    terra_higher = sorted(
        [r for r in tj if int(float(r["rank_gap"])) < 0],
        key=lambda r: -abs(int(float(r["rank_gap"]))),
    )
    n_jh = n_th = 0
    for r in jev_higher:
        if n_jh >= 30:
            break
        if take(int(r["paper_id"]), "max_disagreement"):
            n_jh += 1
    for r in terra_higher:
        if n_th >= 30:
            break
        if take(int(r["paper_id"]), "max_disagreement"):
            n_th += 1

    # (e) screen failures early so score_strata can fill remainder
    fails = _screen_failures_sep16_21(conn, limit=20)
    n_fail = 0
    for cid in fails:
        if n_fail >= 20:
            break
        if take(cid, "screen_failed"):
            n_fail += 1

    # (d) score strata 12 per quintile + fill shortfall to 200
    terra_scores = _terra_composites_sep(conn)
    available = [t for t in terra_scores if t[0] not in selected]
    n_bins = 5
    per_bin = 12
    if available:
        bins: list[list[tuple[int, float]]] = [[] for _ in range(n_bins)]
        for i, item in enumerate(available):
            bins[min(n_bins - 1, int(i * n_bins / len(available)))].append(item)
        for b in bins:
            # take from middle of each bin for diversity
            mid = len(b) // 2
            ordered = b[mid:] + b[:mid]
            taken = 0
            for cid, _ in ordered:
                if taken >= per_bin:
                    break
                if take(cid, "score_strata"):
                    taken += 1

    # Fill remainder from score_strata pool
    if len(selected) < TARGET_N:
        for cid, _ in available:
            if len(selected) >= TARGET_N:
                break
            take(cid, "score_strata")

    # If still short, extend screen_failed or disagreement leftovers
    if len(selected) < TARGET_N:
        for cid in fails:
            if len(selected) >= TARGET_N:
                break
            take(cid, "screen_failed")
    if len(selected) < TARGET_N:
        for r in jev_higher + terra_higher:
            if len(selected) >= TARGET_N:
                break
            take(int(r["paper_id"]), "max_disagreement")

    # Fetch paper metadata in stratum order
    ids_by_stratum: dict[str, list[int]] = defaultdict(list)
    for cid, stratum in selected.items():
        ids_by_stratum[stratum].append(cid)

    ordered_ids: list[int] = []
    for stratum in STRATUM_ORDER:
        ordered_ids.extend(sorted(ids_by_stratum.get(stratum, [])))
    ordered_ids = ordered_ids[:TARGET_N]

    papers = _fetch_papers(conn, ordered_ids)
    orgs = _orgs_by_id(conn, ordered_ids)
    rows = []
    counts: dict[str, int] = defaultdict(int)
    for cid in ordered_ids:
        p = papers.get(cid)
        if not p:
            print(f"WARNING: missing paper_id={cid}", flush=True)
            continue
        stratum = selected[cid]
        counts[stratum] += 1
        rows.append({**p, "organisations": orgs.get(cid, ""), "sample_stratum": stratum})
    return rows, dict(counts)


def _build_hidden_csv(rows: list[dict[str, Any]]) -> None:
    tj = {int(r["paper_id"]): r for r in _load_terra_jev_csv()}
    jev_v001: dict[int, dict] = {}
    if JEV_CACHE.exists():
        raw = json.loads(JEV_CACHE.read_text(encoding="utf-8"))
        for k, v in (raw.get("papers") or {}).items():
            jev_v001[int(k)] = v
    jev_v002: dict[int, dict] = {}
    if JEV_V002.exists():
        raw = json.loads(JEV_V002.read_text(encoding="utf-8"))
        for k, v in (raw.get("papers") or {}).items():
            jev_v002[int(k)] = v

    # Terra dims from DB for ids missing from comparison CSV
    need_terra = [r["paper_id"] for r in rows if r["paper_id"] not in tj]
    terra_db: dict[int, dict[str, Any]] = {}
    if need_terra:
        with connect() as conn:
            db_rows = conn.execute(
                """
                SELECT DISTINCT ON (q.content_item_id)
                  q.content_item_id, q.result_json, q.model
                FROM paper_intelligence.paper_classification_results q
                WHERE q.task_type = 'quality'
                  AND q.content_item_id = ANY(%s)
                  AND q.model LIKE '%%terra%%'
                ORDER BY q.content_item_id, q.created_at DESC
                """,
                (need_terra,),
            ).fetchall()
            for r in db_rows:
                rj = r["result_json"] or {}
                if isinstance(rj, str):
                    rj = json.loads(rj)
                terra_db[int(r["content_item_id"])] = rj

    # Latest screen ai_relevance for all sample ids
    screen_ai: dict[int, float | None] = {}
    with connect() as conn:
        srows = conn.execute(
            """
            SELECT DISTINCT ON (q.content_item_id)
              q.content_item_id, q.result_json
            FROM paper_intelligence.paper_classification_results q
            WHERE q.task_type = 'screen'
              AND q.content_item_id = ANY(%s)
            ORDER BY q.content_item_id, q.created_at DESC
            """,
            ([r["paper_id"] for r in rows],),
        ).fetchall()
        for r in srows:
            rj = r["result_json"] or {}
            if isinstance(rj, str):
                rj = json.loads(rj)
            try:
                screen_ai[int(r["content_item_id"])] = float(rj["ai_relevance"])
            except (KeyError, TypeError, ValueError):
                screen_ai[int(r["content_item_id"])] = None

    fieldnames = [
        "paper_id",
        "arxiv_id",
        "sample_stratum",
        "screen_ai_relevance",
        "terra_composite",
        "terra_rank",
        "jev_v001_composite",
        "jev_v001_rank",
        "jev_v002_composite",
        "rank_gap_terra_minus_jev_v001",
        "terra_technical_significance",
        "terra_apparent_novelty",
        "terra_practical_applicability",
        "terra_professional_value",
        "terra_learning_value",
        "terra_evidence_strength",
        "jev_v001_technical_significance",
        "jev_v001_apparent_novelty",
        "jev_v001_practical_applicability",
        "jev_v001_professional_value",
        "jev_v001_learning_value",
        "jev_v001_evidence_strength",
        "jev_v002_technical_significance",
        "jev_v002_apparent_novelty",
        "jev_v002_practical_applicability",
        "jev_v002_professional_value",
        "jev_v002_learning_value",
        "jev_v002_evidence_strength",
    ]
    dims = (
        "technical_significance",
        "apparent_novelty",
        "practical_applicability",
        "professional_value",
        "learning_value",
        "evidence_strength",
    )
    HIDDEN_CSV.parent.mkdir(parents=True, exist_ok=True)
    with HIDDEN_CSV.open("w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=fieldnames)
        w.writeheader()
        for row in rows:
            cid = row["paper_id"]
            trow = tj.get(cid)
            out: dict[str, Any] = {
                "paper_id": cid,
                "arxiv_id": row["arxiv_id"],
                "sample_stratum": row["sample_stratum"],
                "screen_ai_relevance": screen_ai.get(cid),
            }
            if trow:
                out["terra_composite"] = trow.get("terra_composite")
                out["terra_rank"] = trow.get("terra_rank")
                out["jev_v001_composite"] = trow.get("jev_composite")
                out["jev_v001_rank"] = trow.get("jev_rank")
                out["rank_gap_terra_minus_jev_v001"] = trow.get("rank_gap")
                for d in dims:
                    out[f"terra_{d}"] = trow.get(f"terra_{d}")
                    out[f"jev_v001_{d}"] = trow.get(f"jev_{d}")
            else:
                rj = terra_db.get(cid) or {}
                comp = (rj.get("composite") or {}).get("quality") if isinstance(rj.get("composite"), dict) else None
                out["terra_composite"] = comp
                for d in dims:
                    out[f"terra_{d}"] = rj.get(d)
                j1 = jev_v001.get(cid)
                if j1:
                    out["jev_v001_composite"] = j1.get("composite")
                    for d in dims:
                        out[f"jev_v001_{d}"] = (j1.get("dims") or {}).get(d)
            j2 = jev_v002.get(cid)
            if j2:
                out["jev_v002_composite"] = j2.get("composite")
                # v002 professional_value already combined in dims when present
                for d in dims:
                    out[f"jev_v002_{d}"] = (j2.get("dims") or {}).get(d)
            elif cid in jev_v001 and not trow:
                pass
            w.writerow(out)


def _write_xlsx(rows: list[dict[str, Any]], domains: list[str], apps: list[str]) -> None:
    wb = Workbook()

    # ---- Sheet 1: labelling ----
    ws = wb.active
    ws.title = "labelling"
    header_font = Font(bold=True)
    header_fill = PatternFill("solid", fgColor="D9E2F3")
    for col, name in enumerate(LABEL_HEADERS, start=1):
        cell = ws.cell(1, col, name)
        cell.font = header_font
        cell.fill = header_fill
        cell.alignment = Alignment(wrap_text=True, vertical="center")

    for i, row in enumerate(rows, start=1):
        values = {
            "row_no": i,
            "paper_id": row["paper_id"],
            "arxiv_id": row["arxiv_id"],
            "arxiv_url": row["arxiv_url"],
            "title": row["title"],
            "abstract": row["abstract"],
            "published_at": row["published_at"],
            "organisations": row["organisations"],
            "sample_stratum": row["sample_stratum"],
        }
        for col, name in enumerate(LABEL_HEADERS, start=1):
            val = values.get(name, "")
            cell = ws.cell(i + 1, col, val if val is not None else "")
            if name in {"title", "abstract", "organisations"}:
                cell.alignment = Alignment(wrap_text=True, vertical="top")

    ws.freeze_panes = "D2"  # freeze header + first 3 cols (row_no, paper_id, arxiv_id)
    widths = {
        "A": 8,
        "B": 12,
        "C": 14,
        "D": 28,
        "E": 40,
        "F": 60,
        "G": 20,
        "H": 28,
        "I": 16,
    }
    for letter, width in widths.items():
        ws.column_dimensions[letter].width = width
    for col in range(10, len(LABEL_HEADERS) + 1):
        ws.column_dimensions[get_column_letter(col)].width = 14
    ws.row_dimensions[1].height = 30
    for r in range(2, len(rows) + 2):
        ws.row_dimensions[r].height = 60

    # Data validations (options live on hidden _lists sheet)
    ws_lists = wb.create_sheet("_lists")
    for i, d in enumerate(domains, start=1):
        ws_lists.cell(i, 1, d)
    for i, a in enumerate(apps, start=1):
        ws_lists.cell(i, 2, a)
    for i, v in enumerate(VERDICTS, start=1):
        ws_lists.cell(i, 3, v)
    for i, s in enumerate(_half_steps(), start=1):
        ws_lists.cell(i, 4, float(s))
    ws_lists.sheet_state = "hidden"

    score_start = LABEL_HEADERS.index("h_ai_relevance") + 1
    score_end = LABEL_HEADERS.index("h_final_score") + 1
    dv_score2 = DataValidation(
        type="list",
        formula1=f"=_lists!$D$1:$D${len(_half_steps())}",
        allow_blank=True,
        showErrorMessage=True,
        errorTitle="Invalid score",
        error="Enter 0.0–10.0 in 0.5 steps (use the dropdown).",
        showDropDown=False,
    )
    dv_score2.add(
        f"{get_column_letter(score_start)}2:{get_column_letter(score_end)}{len(rows)+1}"
    )
    ws.add_data_validation(dv_score2)

    dom_col = LABEL_HEADERS.index("h_domain") + 1
    app_col = LABEL_HEADERS.index("h_application_domain") + 1
    verd_col = LABEL_HEADERS.index("h_newsletter_verdict") + 1
    dv_dom = DataValidation(
        type="list",
        formula1=f"=_lists!$A$1:$A${len(domains)}",
        allow_blank=True,
        showErrorMessage=True,
        errorTitle="Invalid domain",
        error="Pick a value from the closed classification vocabulary.",
    )
    dv_dom.add(f"{get_column_letter(dom_col)}2:{get_column_letter(dom_col)}{len(rows)+1}")
    ws.add_data_validation(dv_dom)
    dv_app = DataValidation(
        type="list",
        formula1=f"=_lists!$B$1:$B${len(apps)}",
        allow_blank=True,
        showErrorMessage=True,
        errorTitle="Invalid application_domain",
        error="Pick a value from the closed classification vocabulary.",
    )
    dv_app.add(f"{get_column_letter(app_col)}2:{get_column_letter(app_col)}{len(rows)+1}")
    ws.add_data_validation(dv_app)
    dv_ver = DataValidation(
        type="list",
        formula1=f"=_lists!$C$1:$C${len(VERDICTS)}",
        allow_blank=True,
        showErrorMessage=True,
        errorTitle="Invalid verdict",
        error="Use winner_material / shortlist / maybe / reject.",
    )
    dv_ver.add(f"{get_column_letter(verd_col)}2:{get_column_letter(verd_col)}{len(rows)+1}")
    ws.add_data_validation(dv_ver)

    # ---- Sheet 2: rubric ----
    wr = wb.create_sheet("rubric", 1)
    seats = yaml.safe_load(SEATS_POL.read_text(encoding="utf-8")) or {}
    quality_text = QUALITY_PROMPT.read_text(encoding="utf-8")
    # Extract dimension section + composite from prompt
    wr["A1"] = "Quality rubric (six dimensions + composite)"
    wr["A1"].font = Font(bold=True, size=14)
    wr["A3"] = quality_text
    wr["A3"].alignment = Alignment(wrap_text=True, vertical="top")
    wr.merge_cells("A3:D40")
    wr["A42"] = "TECH and PRODUCT seat definitions (verbatim from policies/editorial_seats/v001.yaml)"
    wr["A42"].font = Font(bold=True, size=14)
    wr["A44"] = yaml.dump(seats.get("seats") or seats, sort_keys=False, allow_unicode=True)
    wr["A44"].alignment = Alignment(wrap_text=True, vertical="top")
    wr.merge_cells("A44:D80")
    wr.column_dimensions["A"].width = 100

    # ---- Sheet 3: instructions ----
    wi = wb.create_sheet("instructions", 2)
    instructions = [
        "Golden labelling instructions",
        "",
        "1. Label BLIND. Do not open model_scores_hidden.csv or any Terra/Jev report while labelling.",
        "2. Work in order (rows are already sorted: editorial_pick → flagged → max_disagreement → score_strata → screen_failed).",
        "3. Do about 25 papers per sitting. Stop when tired — fatigue invalidates scores.",
        "4. Leave a row entirely blank rather than guessing. Blank rows are skipped on import.",
        "5. Score the numeric columns on 0–10 in 0.5 steps using the dropdowns "
        "(including h_ai_relevance = AI/ML relevance, aligned with the screen gate).",
        "6. h_final_score is YOUR overall judgement for newsletter relevance — not a formula cell.",
        "   (The composite formula on the rubric sheet is guidance only; do not reverse-engineer it.)",
        "7. h_domain / h_application_domain: use the dropdown closed vocabulary only.",
        "8. h_newsletter_verdict: winner_material | shortlist | maybe | reject.",
        "9. If verdict is reject, optionally fill h_reject_reason.",
        "10. Save the file and return it for import via scripts/import_golden_labels.py.",
        "",
        "Import example:",
        "  PYTHONPATH=src python3 scripts/import_golden_labels.py \\",
        "    --xlsx golden/golden_labelling_200.xlsx --labeller subha --label-round v1",
    ]
    for i, line in enumerate(instructions, start=1):
        wi.cell(i, 1, line)
        if i == 1:
            wi.cell(i, 1).font = Font(bold=True, size=14)
    wi.column_dimensions["A"].width = 110

    # Ensure no accidental model-score columns on labelling sheet
    forbidden = ("terra", "jev", "rank_gap", "composite")
    for cell in ws[1]:
        name = str(cell.value or "").lower()
        if any(tok in name for tok in forbidden):
            raise RuntimeError(f"labelling sheet leaked model column: {cell.value}")

    GOLDEN_DIR.mkdir(parents=True, exist_ok=True)
    wb.save(XLSX_OUT)


def main() -> int:
    domains, apps = _load_vocab()
    with connect() as conn:
        rows, counts = _select_sample(conn)
    if len(rows) != TARGET_N:
        print(f"WARNING: got {len(rows)} rows (target {TARGET_N})", flush=True)
    _write_xlsx(rows, domains, apps)
    _build_hidden_csv(rows)
    print(f"wrote {XLSX_OUT} n={len(rows)}", flush=True)
    print(f"wrote {HIDDEN_CSV}", flush=True)
    print("stratum_counts:", json.dumps(counts, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
