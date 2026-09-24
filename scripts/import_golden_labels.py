#!/usr/bin/env python3
"""Import filled golden labelling xlsx into golden_human_scores.

Append-only: the same (paper_id, labeller, label_round) raises — never overwrite.

  PYTHONPATH=src python3 scripts/import_golden_labels.py \\
    --xlsx golden/quality_scoring_golden_v1.xlsx --labeller subha --label-round v1

Dry-run (validate only, no DB write):

  PYTHONPATH=src python3 scripts/import_golden_labels.py \\
    --xlsx golden/quality_scoring_golden_v1.xlsx --labeller subha --dry-run
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

import yaml  # noqa: E402
from openpyxl import load_workbook  # noqa: E402

from paper_intelligence.db import connect  # noqa: E402

CLASS_POL = ROOT / "policies" / "classification" / "v002.yaml"
VERDICTS = {"winner_material", "shortlist", "maybe", "reject"}
SCORE_FIELDS = (
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
# Six quality rubric dims (excludes screen ai_relevance and seat/final).
QUALITY_DIM_FIELDS = (
    "h_technical_significance",
    "h_apparent_novelty",
    "h_practical_applicability",
    "h_professional_value",
    "h_learning_value",
    "h_evidence_strength",
)
# At least one quality dim or final_score or verdict required to count as labelled.
REQUIRED_ANY = SCORE_FIELDS + ("h_newsletter_verdict",)


def _args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--xlsx", required=True, type=Path)
    p.add_argument("--labeller", required=True)
    p.add_argument("--label-round", default="v1")
    p.add_argument("--blind", action="store_true", default=True)
    p.add_argument("--not-blind", action="store_true", help="set blind=false")
    p.add_argument("--dry-run", action="store_true")
    return p.parse_args()


def _vocab() -> tuple[set[str], set[str]]:
    data = yaml.safe_load(CLASS_POL.read_text(encoding="utf-8")) or {}
    return set(data.get("domain") or []), set(data.get("application_domain") or [])


def _half_step(val: Any) -> float | None:
    if val is None or val == "":
        return None
    try:
        x = float(val)
    except (TypeError, ValueError):
        raise ValueError(f"not a number: {val!r}")
    if x < 0 or x > 10:
        raise ValueError(f"out of range 0–10: {x}")
    # 0.5 steps
    if abs(x * 2 - round(x * 2)) > 1e-6:
        raise ValueError(f"not a 0.5 step: {x}")
    return round(x * 2) / 2


def _row_dict(headers: list[str], values: list[Any]) -> dict[str, Any]:
    return {h: values[i] if i < len(values) else None for i, h in enumerate(headers)}


def _is_blank_row(row: dict[str, Any]) -> bool:
    for key in REQUIRED_ANY:
        v = row.get(key)
        if v is not None and str(v).strip() != "":
            return False
    return True


def _validate_row(
    row: dict[str, Any],
    *,
    domains: set[str],
    apps: set[str],
) -> tuple[dict[str, Any] | None, str | None]:
    """Return (cleaned_row, error). Skip blank with (None, None)."""
    if _is_blank_row(row):
        return None, None
    try:
        paper_id = int(row.get("paper_id"))
    except (TypeError, ValueError):
        return None, "paper_id missing or not an integer"

    cleaned: dict[str, Any] = {
        "paper_id": paper_id,
        "arxiv_id": (str(row.get("arxiv_id")).strip() if row.get("arxiv_id") else None),
        "sample_stratum": (
            str(row.get("sample_stratum")).strip() if row.get("sample_stratum") else None
        ),
    }
    for key in SCORE_FIELDS:
        try:
            cleaned[key] = _half_step(row.get(key))
        except ValueError as exc:
            return None, f"{key}: {exc}"

    domain = row.get("h_domain")
    if domain is not None and str(domain).strip() != "":
        domain = str(domain).strip()
        if domain not in domains:
            return None, f"h_domain {domain!r} not in closed vocabulary"
        cleaned["h_domain"] = domain
    else:
        cleaned["h_domain"] = None

    app = row.get("h_application_domain")
    if app is not None and str(app).strip() != "":
        app = str(app).strip()
        if app not in apps:
            return None, f"h_application_domain {app!r} not in closed vocabulary"
        cleaned["h_application_domain"] = app
    else:
        cleaned["h_application_domain"] = None

    verdict = row.get("h_newsletter_verdict")
    if verdict is not None and str(verdict).strip() != "":
        verdict = str(verdict).strip()
        if verdict not in VERDICTS:
            return None, f"h_newsletter_verdict {verdict!r} invalid"
        cleaned["h_newsletter_verdict"] = verdict
    else:
        cleaned["h_newsletter_verdict"] = None

    for key in ("h_reject_reason", "h_notes"):
        v = row.get(key)
        cleaned[key] = str(v).strip() if v is not None and str(v).strip() != "" else None

    # Require at least the six quality dims OR final_score OR verdict
    has_dims = all(cleaned.get(k) is not None for k in QUALITY_DIM_FIELDS)
    has_final = cleaned.get("h_final_score") is not None
    has_verdict = cleaned.get("h_newsletter_verdict") is not None
    if not (has_dims or has_final or has_verdict):
        return None, "need six quality dims, or h_final_score, or h_newsletter_verdict"

    return cleaned, None


def main() -> int:
    args = _args()
    if not args.xlsx.exists():
        print(f"missing xlsx: {args.xlsx}", file=sys.stderr)
        return 2
    domains, apps = _vocab()
    wb = load_workbook(args.xlsx, data_only=True)
    if "labelling" not in wb.sheetnames:
        print("sheet 'labelling' not found", file=sys.stderr)
        return 2
    ws = wb["labelling"]
    headers = [str(c.value).strip() if c.value is not None else "" for c in ws[1]]
    if "paper_id" not in headers:
        print("labelling sheet missing paper_id header", file=sys.stderr)
        return 2

    accepted: list[dict[str, Any]] = []
    rejected: list[tuple[int, str]] = []
    skipped_blank = 0
    for excel_row, values in enumerate(ws.iter_rows(min_row=2, values_only=True), start=2):
        row = _row_dict(headers, list(values))
        cleaned, err = _validate_row(row, domains=domains, apps=apps)
        if err is None and cleaned is None:
            skipped_blank += 1
            continue
        if err:
            rejected.append((excel_row, err))
            continue
        assert cleaned is not None
        accepted.append(cleaned)

    print(
        f"validated accepted={len(accepted)} rejected={len(rejected)} "
        f"blank_skipped={skipped_blank}",
        flush=True,
    )
    for excel_row, err in rejected:
        print(f"  REJECT row {excel_row}: {err}", flush=True)

    if rejected and not args.dry_run:
        print("refusing insert while any row is rejected (fix and re-run)", file=sys.stderr)
        return 3
    if args.dry_run:
        print("dry-run: no DB write", flush=True)
        return 0 if not rejected else 3
    if not accepted:
        print("nothing to insert", flush=True)
        return 0

    blind = not args.not_blind
    sql = """
        INSERT INTO paper_intelligence.golden_human_scores (
          paper_id, arxiv_id, labeller, label_round, blind, sample_stratum,
          h_ai_relevance,
          h_technical_significance, h_apparent_novelty, h_practical_applicability,
          h_professional_value, h_learning_value, h_evidence_strength,
          h_tech_relevance, h_product_relevance, h_final_score,
          h_domain, h_application_domain, h_newsletter_verdict,
          h_reject_reason, h_notes
        ) VALUES (
          %(paper_id)s, %(arxiv_id)s, %(labeller)s, %(label_round)s, %(blind)s,
          %(sample_stratum)s,
          %(h_ai_relevance)s,
          %(h_technical_significance)s, %(h_apparent_novelty)s,
          %(h_practical_applicability)s, %(h_professional_value)s,
          %(h_learning_value)s, %(h_evidence_strength)s,
          %(h_tech_relevance)s, %(h_product_relevance)s, %(h_final_score)s,
          %(h_domain)s, %(h_application_domain)s, %(h_newsletter_verdict)s,
          %(h_reject_reason)s, %(h_notes)s
        )
    """
    inserted = 0
    with connect() as conn:
        for row in accepted:
            payload = {
                **row,
                "labeller": args.labeller,
                "label_round": args.label_round,
                "blind": blind,
            }
            try:
                conn.execute(sql, payload)
                inserted += 1
            except Exception as exc:  # noqa: BLE001 — surface unique violations clearly
                print(
                    f"INSERT FAILED paper_id={row['paper_id']}: {exc}",
                    file=sys.stderr,
                )
                conn.rollback()
                return 4
        conn.commit()
    print(f"inserted={inserted} labeller={args.labeller} round={args.label_round}", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
