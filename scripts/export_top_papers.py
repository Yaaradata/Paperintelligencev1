#!/usr/bin/env python3
"""Export top-N tech and product papers over a date range (CSV + markdown).

Pools and base ranking are those of generate_audience_tops.py (quality_score
DESC, final_score DESC); nothing here changes the pipeline's defaults.

Tech selection adds an outcome tier (editorial brief, 22/09/2026): papers that
give a *measured* way to cut engineering / inference / training cost or to
improve inference performance come first.

  A  measured efficiency outcome: in one sentence of the abstract or so_what,
     a number (2.3x, 40%, 3-fold, by 25%) within 70 characters of both an
     improvement word (reduce, lower, faster, speedup, cut, ...) and an
     efficiency term (latency, throughput, memory usage, cost, FLOPs, energy,
     KV cache, TTFT, ...).
  B  efficiency outcome stated without a number (reduce/lower/cut + cost,
     latency, memory, ...; faster inference; higher throughput).
  C  everything else in the tech pool.

The tier is a keyword heuristic, not a model judgment; it has not been checked
against hand labels, so the matched phrase is exported for review.

  PYTHONPATH=src python scripts/export_top_papers.py --from 2026-07-01 --until 2026-09-28 --top 400
"""

from __future__ import annotations

import argparse
import csv
import importlib.util
import re
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from paper_intelligence.db import connect  # noqa: E402

_spec = importlib.util.spec_from_file_location("generate_audience_tops", ROOT / "scripts" / "generate_audience_tops.py")
tops = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(tops)

EFFICIENCY = (
    r"latenc\w*|throughput|speed-?ups?|faster|memory (?:usage|footprint|consumption|cost|overhead|traffic)"
    r"|(?:less|lower|peak) (?:gpu )?memory|flops|gpu[- ]hours?|compute|costs?|cheaper|energy|tokens?/s"
    r"|tokens? per second|kv[- ]?cache|inference time|training time|wall[- ]?clock|time[- ]to[- ]first[- ]token"
    r"|ttft|tpot|runtime|overhead"
)
EFFICIENCY_RE = re.compile(rf"\b({EFFICIENCY})\b", re.I)
DIRECTION_RE = re.compile(
    r"\b(reduc\w*|lower\w*|less|fewer|faster|speed-?ups?|cut\w*|sav\w*|decreas\w*|shrink\w*|cheaper|smaller"
    r"|compress\w*|accelerat\w*|throughput|improv\w* (?:ttft|latency|throughput))\b",
    re.I,
)
MEASURED_RE = re.compile(
    r"(\d+(?:\.\d+)?\s?(?:x|×|\$\\times\$|times|%|\\%|-fold|fold)(?![a-z])|\bby (?:up to |over |more than )?\d+(?:\.\d+)?)",
    re.I,
)
SENTENCE_RE = re.compile(r"(?<=[.;])\s+(?=[A-Z(])")
UNMEASURED_RE = re.compile(
    rf"\b(reduc\w*|lower\w*|cut\w*|sav\w*|decreas\w*|minimi[sz]\w*|shrink\w*|halv\w*)\b[^.]{{0,50}}\b({EFFICIENCY})\b"
    r"|\b(faster|efficient|accelerat\w*|speed(?:s|ing)? up)\b[^.]{0,30}\b(inference|serving|decoding|generation|training)\b"
    r"|\b(higher|improv\w*|increas\w*|boost\w*)\b[^.]{0,30}\b(throughput|inference (?:speed|performance|efficiency))\b",
    re.I,
)
CATEGORY_RES = (
    ("inference", re.compile(r"inference|serving|decod\w*|deploy\w*|ttft|time[- ]to[- ]first|kv[- ]?cache|tokens?/s|tokens? per second|latenc\w*|edge device|on-device", re.I)),
    ("training", re.compile(r"training|fine-?tun\w*|pre-?train\w*|gpu[- ]hours?", re.I)),
    ("engineering_cost", re.compile(r"engineering|operational|maintenance|developer|annotation|labell?ing|human effort|manual", re.I)),
)


def outcome(abstract: str | None, so_what: str | None) -> dict[str, str]:
    for source, text in (("abstract", abstract or ""), ("so_what", so_what or "")):
        for sentence in SENTENCE_RE.split(text):
            for m in MEASURED_RE.finditer(sentence):
                window = sentence[max(0, m.start() - 70): m.end() + 70]
                if EFFICIENCY_RE.search(window) and DIRECTION_RE.search(window):
                    return {"tier": "A", "evidence": f"{source}: …{window.strip()}…",
                            "category": _category(window, text)}
    for source, text in (("so_what", so_what or ""), ("abstract", abstract or "")):
        m = UNMEASURED_RE.search(text)
        if m:
            window = text[max(0, m.start() - 40): m.end() + 40]
            return {"tier": "B", "evidence": f"{source}: …{window.strip()}…", "category": _category(window, text)}
    return {"tier": "C", "evidence": "", "category": ""}


def _category(window: str, text: str) -> str:
    for scope in (window, text):
        found = [name for name, rx in CATEGORY_RES if rx.search(scope)]
        if found:
            return "+".join(found)
    return "compute_cost"


def _abstracts(conn, ids: list[int]) -> dict[int, str]:
    rows = conn.execute(
        "SELECT paper_id, abstract, arxiv_id FROM paper_intelligence.papers WHERE paper_id = ANY(%s)", (ids,)
    ).fetchall()
    return {int(r["paper_id"]): (r["abstract"], r["arxiv_id"]) for r in rows}


def _rank_key(r: dict[str, Any]) -> tuple:
    return (-(r["quality_score"] or 0), -(r["final_score"] or 0), r["content_item_id"])


def build(conn, date_from: str, date_until: str, top: int) -> dict[str, list[dict[str, Any]]]:
    tech_pool = tops.fetch_pool(conn, date_from=date_from, date_until=date_until, pool="tech", limit=10**6)
    product_name = "product" if tops._policy() == "v002" else "business"
    product = tops.fetch_pool(conn, date_from=date_from, date_until=date_until, pool=product_name, limit=top)
    meta = _abstracts(conn, [r["content_item_id"] for r in tech_pool + product])
    for r in tech_pool + product:
        r["abstract"], r["arxiv_id"] = meta.get(r["content_item_id"], (None, None))
    for r in tech_pool:
        r.update(outcome(r["abstract"], r["so_what"]))
    tech_pool.sort(key=lambda r: ("ABC".index(r["tier"]), *_rank_key(r)))
    return {"tech": tech_pool[:top], "product": product, "tech_pool_tiers": {
        t: sum(1 for r in tech_pool if r["tier"] == t) for t in "ABC"}, "tech_pool_size": len(tech_pool)}


COLUMNS = ["rank", "tier", "outcome_category", "quality_score", "final_score", "published", "arxiv_url", "title",
           "organisation", "domain", "so_what", "outcome_evidence"]


def _row(i: int, r: dict[str, Any]) -> dict[str, Any]:
    return {
        "rank": i, "tier": r.get("tier", ""), "outcome_category": r.get("category", ""),
        "quality_score": r["quality_score"], "final_score": r["final_score"],
        "published": tops._fmt_date(r["published_at"]),
        "arxiv_url": f"https://arxiv.org/abs/{r['arxiv_id']}" if r.get("arxiv_id") else "",
        "title": (r["title"] or "").strip(), "organisation": r.get("organisation") or r.get("all_organisations") or "",
        "domain": r.get("domain") or "", "so_what": (r.get("so_what") or "").strip(),
        "outcome_evidence": r.get("evidence", ""),
    }


def write(kind: str, rows: list[dict[str, Any]], out_dir: Path, stem: str, header: list[str]) -> tuple[Path, Path]:
    csv_path = out_dir / f"{stem}.csv"
    md_path = out_dir / f"{stem}.md"
    cols = COLUMNS if kind == "tech" else [c for c in COLUMNS if c not in ("tier", "outcome_category", "outcome_evidence")]
    with open(csv_path, "w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=cols, extrasaction="ignore")
        w.writeheader()
        for i, r in enumerate(rows, 1):
            w.writerow(_row(i, r))
    md_cols = ["rank", *(["tier", "outcome_category"] if kind == "tech" else []), "quality_score", "published", "title", "organisation"]
    lines = [*header, "", "| " + " | ".join(md_cols) + " |", "|" + "|".join("---" for _ in md_cols) + "|"]
    for i, r in enumerate(rows, 1):
        d = _row(i, r)
        d["title"] = f"[{tops._title(d['title'])}]({d['arxiv_url']})" if d["arxiv_url"] else tops._title(d["title"])
        d["organisation"] = tops._title(d["organisation"])
        lines.append("| " + " | ".join(str(d[c]) for c in md_cols) + " |")
    md_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return csv_path, md_path


def main(argv: list[str]) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--from", dest="date_from", required=True)
    ap.add_argument("--until", dest="date_until", required=True)
    ap.add_argument("--top", type=int, default=400)
    ap.add_argument("--out-dir", default=str(ROOT / "reports" / "exports"))
    args = ap.parse_args(argv)
    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    with connect() as conn:
        res = build(conn, args.date_from, args.date_until, args.top)
    window = f"{args.date_from}_to_{args.date_until}"
    tiers = res["tech_pool_tiers"]
    shown = {t: sum(1 for r in res["tech"] if r["tier"] == t) for t in "ABC"}
    tech_header = [
        f"# Tech top {args.top} — {args.date_from} to {args.date_until}",
        "",
        f"Tech pool: {res['tech_pool_size']} quality-scored papers. Outcome tiers in pool: "
        f"A (measured cost/efficiency outcome) {tiers['A']}, B (stated, not measured) {tiers['B']}, C {tiers['C']}.",
        f"This list: A {shown['A']}, B {shown['B']}, C {shown['C']}. Order: tier, then quality_score, then final_score.",
        "Tier is a keyword heuristic (not validated against hand labels); see outcome_evidence in the CSV.",
    ]
    product_header = [
        f"# Product top {args.top} — {args.date_from} to {args.date_until}",
        "",
        "Product pool as in the weekly reports; order: quality_score, then final_score.",
    ]
    for kind, header in (("tech", tech_header), ("product", product_header)):
        csv_path, md_path = write(kind, res[kind], out_dir, f"{kind}_top_{args.top}_{window}", header)
        print(f"{kind}: {len(res[kind])} rows -> {csv_path} , {md_path}")
    print(f"tech pool tiers: {tiers}; in top {args.top}: {shown}")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
