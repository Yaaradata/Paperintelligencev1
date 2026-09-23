#!/usr/bin/env python3
"""Refresh the Sep 1–21 top-500 export with current affiliation evidence."""

from __future__ import annotations

import argparse
import csv
import json
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path

from paper_intelligence.db import connect
from paper_intelligence.organisation_resolution.repository import (
    is_member_society_email_domain,
)

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_CSV = ROOT / "reports" / "top_500_2026-09-01_to_2026-09-21.csv"
DEFAULT_MD = ROOT / "reports" / "top_500_2026-09-01_to_2026-09-21.md"
DEFAULT_PDF_ORGS = ROOT / "reports" / "top_500_2026-09-01_to_2026-09-21_pdf_orgs.json"


def _args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--csv", type=Path, default=DEFAULT_CSV)
    parser.add_argument("--markdown", type=Path, default=DEFAULT_MD)
    parser.add_argument("--pdf-orgs", type=Path, default=DEFAULT_PDF_ORGS)
    return parser.parse_args()


def _is_disallowed_society_email(row: dict) -> bool:
    if row.get("evidence_type") != "email_domain":
        return False
    value = str(row.get("evidence_value") or "")
    domain = value.rsplit("@", 1)[-1].lower().strip().strip(".")
    return is_member_society_email_domain(domain)


def _database_orgs(ids: list[int]) -> tuple[dict[int, list[str]], dict[int, list[str]]]:
    all_orgs: dict[int, dict[int, list[dict]]] = defaultdict(lambda: defaultdict(list))
    with connect() as conn:
        rows = conn.execute(
            """
            SELECT a.content_item_id, a.organisation_id, a.evidence_type,
                   a.evidence_value, o.canonical_name, o.is_org_of_interest
            FROM paper_intelligence.paper_author_affiliations a
            JOIN paper_intelligence.organisations o ON o.id = a.organisation_id
            WHERE a.content_item_id = ANY(%s)
              AND a.organisation_id IS NOT NULL
            """,
            (ids,),
        ).fetchall()
    for row in rows:
        all_orgs[int(row["content_item_id"])][int(row["organisation_id"])].append(dict(row))

    resolved: dict[int, list[str]] = defaultdict(list)
    notable: dict[int, list[str]] = defaultdict(list)
    for paper_id, grouped in all_orgs.items():
        for evidence_rows in grouped.values():
            allowed = [r for r in evidence_rows if not _is_disallowed_society_email(r)]
            if not allowed:
                continue
            name = str(allowed[0]["canonical_name"])
            resolved[paper_id].append(name)
            if any(bool(r["is_org_of_interest"]) for r in allowed):
                notable[paper_id].append(name)
    return (
        {k: sorted(set(v), key=str.casefold) for k, v in resolved.items()},
        {k: sorted(set(v), key=str.casefold) for k, v in notable.items()},
    )


def _load_pdf_orgs(path: Path) -> dict[int, list[str]]:
    if not path.exists():
        return {}
    raw = json.loads(path.read_text(encoding="utf-8"))
    return {
        int(paper_id): sorted(
            {str(name).strip() for name in names if str(name).strip()},
            key=str.casefold,
        )
        for paper_id, names in raw.items()
    }


def _join(values: list[str]) -> str:
    return "; ".join(values)


def main() -> int:
    args = _args()
    with args.csv.open(newline="", encoding="utf-8") as handle:
        rows = list(csv.DictReader(handle))
    ids = [int(row["content_item_id"]) for row in rows]
    resolved, notable = _database_orgs(ids)
    pdf_orgs = _load_pdf_orgs(args.pdf_orgs)

    output_rows: list[dict[str, str]] = []
    with_any = 0
    with_resolved = 0
    with_notable = 0
    for row in rows:
        paper_id = int(row["content_item_id"])
        db_names = resolved.get(paper_id, [])
        pdf_names = pdf_orgs.get(paper_id, [])
        names = sorted(set(db_names) | set(pdf_names), key=str.casefold)
        status = (
            "database_and_pdf"
            if db_names and pdf_names
            else "database_resolved"
            if db_names
            else "paper_pdf"
            if pdf_names
            else "not_disclosed_or_unresolved"
        )
        organisation_display = _join(names) or "Not disclosed / unresolved"
        with_any += bool(names)
        with_resolved += bool(db_names)
        with_notable += bool(notable.get(paper_id))
        output_rows.append(
            {
                **row,
                "notable_organisations": _join(notable.get(paper_id, [])),
                "all_resolved_organisations": _join(db_names),
                "pdf_organisations": _join(pdf_names),
                "organisations": organisation_display,
                "organisation_status": status,
            }
        )

    fieldnames = list(output_rows[0])
    with args.csv.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(output_rows)

    generated = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    lines = [
        "# Top 500 papers — Sep 1–21, 2026",
        "",
        f"**Refreshed:** {generated} · **Rank:** quality_score → final_score · **Rows:** 500",
        "",
        f"Organisation evidence is present on **{with_any}/500** papers "
        f"({with_resolved} database-resolved; PDF evidence fills additional papers). "
        f"Notable organisations occur on **{with_notable}/500** papers.",
        "",
        "Professional-society email-domain-only evidence is excluded. "
        "“Not disclosed / unresolved” means the paper did not disclose a reliable "
        "affiliation in the sources checked; no affiliation was guessed from author history.",
        "",
        "| # | ID | Date | Quality | Organisations / status | Title |",
        "|---:|---:|---|---:|---|---|",
    ]
    for row in output_rows:
        title = row["title"].replace("|", r"\|")
        organisations = row["organisations"].replace("|", r"\|")
        lines.append(
            f"| {row['rank']} | {row['content_item_id']} | {row['published_date']} | "
            f"{row['quality_score']} | {organisations} | "
            f"[{title}]({row['canonical_url']}) |"
        )
    args.markdown.write_text("\n".join(lines) + "\n", encoding="utf-8")

    print(
        json.dumps(
            {
                "rows": len(output_rows),
                "with_any_organisation": with_any,
                "database_resolved": with_resolved,
                "with_notable_organisation": with_notable,
                "without_reliable_organisation": len(output_rows) - with_any,
                "csv": str(args.csv),
                "markdown": str(args.markdown),
            },
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
