#!/usr/bin/env python3
"""Verifier Part B: typed prose audit with openai/gpt-6-luna (paid, hard spend cap).

For every paper in the window whose current quality row has non-empty prose,
sends title, abstract, the six scores, so_what and reason_not_higher, and asks
for four typed judgements (see prompts/prose_audit/v001.md). No rewriting,
scoring or ranking. Results go to a JSON file; nothing is written to scoring tables.

  PYTHONPATH=src python scripts/audit_prose_luna.py --from 2026-09-21 --until 2026-09-23 \
      --max-cost-usd 0.50 [--limit N] [--out reports/golden/prose_audit_luna_<from>_<until>.json]

Spend is tracked from provider ``usage.cost``; no new batch starts once
spend + the largest single-batch cost seen so far would exceed the cap.
"""
from __future__ import annotations

import argparse
import gzip
import json
import sys
import threading
from concurrent.futures import ThreadPoolExecutor
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any

from paper_intelligence.common.config import estimate_cost_usd, read_prompt, require_model_priced
from paper_intelligence.common.llm_stage import call_llm_logged, parse_json_object
from paper_intelligence.db import connect

MODEL = "openai/gpt-6-luna"
PROMPT_VERSION = "prose_audit_v001"
PROMPT_VERSIONS = ("v001", "v002", "v003")
BATCH_SIZE = 8
CONCURRENCY = 4
MAX_TOKENS = 1500
# Luna's reasoning counts against max_tokens; at 1500 most 8-paper v001 batches
# came back empty and fell through to per-paper retries (708 calls for 727 papers).
MAX_TOKENS_BY_VERSION = {"v001": MAX_TOKENS, "v002": 4000, "v003": 4000}
DIMS = (
    "technical_significance",
    "apparent_novelty",
    "practical_applicability",
    "professional_value",
    "learning_value",
    "evidence_strength",
)
YES_NO = {"yes", "no"}
REAL_HEDGE = {"real", "hedge"}

POPULATION_SQL = """
WITH q AS (
    SELECT DISTINCT ON (r.content_item_id) r.content_item_id, r.model, r.run_id, r.result_json
    FROM paper_intelligence.paper_classification_results r
    JOIN paper_intelligence.papers p ON p.paper_id = r.content_item_id
    WHERE r.task_type = 'quality' AND p.published_at::date BETWEEN %(from)s AND %(until)s
    ORDER BY r.content_item_id, r.created_at DESC
)
SELECT q.content_item_id, q.model, q.run_id::text AS run_id, q.result_json,
       p.title, p.abstract, c.quality_status
FROM q
JOIN paper_intelligence.papers p ON p.paper_id = q.content_item_id
LEFT JOIN paper_intelligence.paper_intelligence_current c ON c.content_item_id = q.content_item_id
WHERE NULLIF(btrim(q.result_json->>'so_what'), '') IS NOT NULL
ORDER BY q.content_item_id
"""


def user_prompt(batch: list[dict[str, Any]], version: str = "v001") -> str:
    blocks = []
    for i, p in enumerate(batch, 1):
        rj = p["result_json"]
        lines = [f"### Paper {i}", f"Title: {p['title']}", f"Abstract: {p['abstract']}"]
        if version == "v001":
            lines.append("Scores: " + ", ".join(f"{d}={rj.get(d)}" for d in DIMS))
        lines += [f"so_what: {rj.get('so_what')}", f"reason_not_higher: {rj.get('reason_not_higher')}"]
        blocks.append("\n".join(lines))
    return "\n\n".join(blocks)


def _parse_v001(item: dict[str, Any]) -> dict[str, str] | None:
    rec = {k: str(item.get(k, "")).strip().lower() for k in
           ("so_what_specific", "unsupported_claim", "contradicts_scores", "reason_not_higher")}
    if (rec["so_what_specific"] in YES_NO and rec["unsupported_claim"] in YES_NO
            and rec["contradicts_scores"] in YES_NO and rec["reason_not_higher"] in REAL_HEDGE):
        return rec
    return None


def _parse_v002(item: dict[str, Any]) -> dict[str, str] | None:
    rec = {k: str(item.get(k, "")).strip().lower() for k in
           ("so_what_unsupported", "reason_not_higher_unsupported")}
    if not (rec["so_what_unsupported"] in YES_NO and rec["reason_not_higher_unsupported"] in YES_NO):
        return None
    phrase = str(item.get("so_what_unsupported_phrase") or "").strip()
    rec["so_what_unsupported_phrase"] = phrase if rec["so_what_unsupported"] == "yes" else ""
    return rec


def _parse_v003(item: dict[str, Any]) -> dict[str, str] | None:
    rec = _parse_v002(item)
    specific = str(item.get("so_what_specific", "")).strip().lower()
    if rec is None or specific not in YES_NO:
        return None
    return {**rec, "so_what_specific": specific}


_PARSERS = {"v001": _parse_v001, "v002": _parse_v002, "v003": _parse_v003}


def parse_results(content: str, n: int, version: str = "v001") -> dict[int, dict[str, str]]:
    data = parse_json_object(content)
    parse_item = _PARSERS[version]
    out: dict[int, dict[str, str]] = {}
    for item in data.get("results") or []:
        if not isinstance(item, dict):
            continue
        try:
            i = int(item.get("i"))
        except (TypeError, ValueError):
            continue
        rec = parse_item(item)
        if 1 <= i <= n and rec is not None:
            out[i] = rec
    return out


def apply_trial_prose(rows: list[dict[str, Any]], trial: dict[str, dict[str, Any]]) -> list[dict[str, Any]]:
    """Keep only papers in the trial file, with their prose swapped for the trial prose."""
    out = []
    for r in rows:
        cell = trial.get(str(r["content_item_id"]))
        if not cell:
            continue
        rj = {**r["result_json"], "so_what": cell["so_what"], "reason_not_higher": cell["reason_not_higher"]}
        out.append({**r, "result_json": rj})
    return out


def project_cost(rows: list[dict[str, Any]], system_prompt: str, version: str) -> tuple[int, int, int, float]:
    """(calls, input_tokens, output_tokens, usd) at table price, one call per batch."""
    batches = [rows[i : i + BATCH_SIZE] for i in range(0, len(rows), BATCH_SIZE)]
    out_per_paper = {"v001": 40, "v002": 45, "v003": 55}[version]
    tin = sum((len(system_prompt) + len(user_prompt(b, version))) // 4 for b in batches)
    tout = out_per_paper * len(rows)
    return len(batches), tin, tout, estimate_cost_usd(MODEL, tin, tout)


def _served_model(raw_path: str | None) -> str | None:
    """Model id OpenRouter reports it served; raw files may be gzip-compressed."""
    if not raw_path or not Path(raw_path).is_file():
        return None
    try:
        blob = Path(raw_path).read_bytes()
        if blob[:2] == b"\x1f\x8b":
            blob = gzip.decompress(blob)
        raw = json.loads(blob)
    except (OSError, ValueError):
        return None
    return raw.get("model") if isinstance(raw, dict) else None


class Spend:
    def __init__(self, cap: float) -> None:
        self.cap = cap
        self.total = 0.0
        self.estimated = 0.0
        self.max_call = 0.0
        self.calls = 0
        self.calls_without_actual = 0
        self.lock = threading.Lock()

    def may_start(self) -> bool:
        with self.lock:
            reserve = self.max_call * CONCURRENCY if self.max_call else 0.02
            return self.total + reserve <= self.cap

    def add(self, actual: float | None, estimated: float) -> None:
        with self.lock:
            cost = actual if actual is not None else estimated
            self.calls += 1
            self.calls_without_actual += actual is None
            self.total += cost
            self.estimated += estimated
            self.max_call = max(self.max_call, cost)


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--from", dest="date_from", required=True, type=date.fromisoformat)
    ap.add_argument("--until", dest="date_until", required=True, type=date.fromisoformat)
    ap.add_argument("--max-cost-usd", type=float, required=True)
    ap.add_argument("--limit", type=int)
    ap.add_argument("--out", type=Path)
    ap.add_argument("--prompt-version", choices=PROMPT_VERSIONS, default="v001",
                    help="v002 judges so_what and reason_not_higher separately")
    ap.add_argument("--dry-run", action="store_true", help="project cost only; no API calls")
    ap.add_argument("--prose-from", type=Path,
                    help="prose_prompt_trial.py output: audit that prose instead of the stored prose, "
                         "for the papers it contains")
    args = ap.parse_args()
    version = args.prompt_version
    prompt_version = f"prose_audit_{version}"
    suffix = "" if version == "v001" else f"_{version}"
    out_path = args.out or Path(
        f"reports/golden/prose_audit_luna_{args.date_from}_{args.date_until}{suffix}.json"
    )

    require_model_priced(MODEL)
    system_prompt = read_prompt("prose_audit", version)
    with connect() as conn:
        rows = [dict(r) for r in conn.execute(
            POPULATION_SQL, {"from": args.date_from, "until": args.date_until}
        ).fetchall()]
    for r in rows:
        if isinstance(r["result_json"], str):
            r["result_json"] = json.loads(r["result_json"])
    if args.prose_from:
        rows = apply_trial_prose(rows, json.loads(args.prose_from.read_text())["results"])
        if not args.out:
            out_path = out_path.with_name(f"{out_path.stem}_{args.prose_from.stem}.json")
    if args.limit:
        rows = rows[: args.limit]
    batches = [rows[i : i + BATCH_SIZE] for i in range(0, len(rows), BATCH_SIZE)]
    print(f"prose_audit: papers={len(rows)} batches={len(batches)} model={MODEL} prompt={prompt_version} "
          f"cap=${args.max_cost_usd}", flush=True)
    if args.dry_run:
        calls, tin, tout, usd = project_cost(rows, system_prompt, version)
        print(f"PROJECTION prose_audit: {calls} calls, ~{tin} in / ~{tout} out tokens, "
              f"~${usd:.4f} (table price, no retries)", flush=True)
        return 0

    spend = Spend(args.max_cost_usd)
    results: dict[int, dict[str, Any]] = {}
    errors: list[dict[str, Any]] = []
    served_models: set[str] = set()
    res_lock = threading.Lock()
    done = [0]

    def call(batch: list[dict[str, Any]]) -> dict[int, dict[str, str]]:
        with connect() as conn:
            resp = call_llm_logged(
                conn, model=MODEL, system_prompt=system_prompt, user_prompt=user_prompt(batch, version),
                prompt_version=prompt_version, stage_name="prose_audit", temperature=0.0,
                max_tokens=MAX_TOKENS_BY_VERSION[version], response_format={"type": "json_object"}, entity="prose_audit",
            )
        spend.add(resp["actual_cost_usd"], resp["estimated_cost_usd"])
        served = _served_model(resp.get("raw_path"))
        if served:
            with res_lock:
                served_models.add(served)
        return parse_results(resp["content"], len(batch), version)

    def run(batch: list[dict[str, Any]]) -> None:
        if not spend.may_start():
            with res_lock:
                errors.append({"ids": [p["content_item_id"] for p in batch], "error": "skipped: spend cap"})
            return
        try:
            parsed = call(batch)
        except Exception as exc:  # noqa: BLE001
            parsed = {}
            with res_lock:
                errors.append({"ids": [p["content_item_id"] for p in batch], "error": str(exc)[:300]})
        missing = [i for i in range(1, len(batch) + 1) if i not in parsed]
        for i in missing:
            if len(batch) == 1 or not spend.may_start():
                continue
            try:
                single = call([batch[i - 1]])
                if 1 in single:
                    parsed[i] = single[1]
            except Exception as exc:  # noqa: BLE001
                with res_lock:
                    errors.append({"ids": [batch[i - 1]["content_item_id"]], "error": str(exc)[:300]})
        with res_lock:
            for i, rec in parsed.items():
                p = batch[i - 1]
                results[p["content_item_id"]] = {**rec, "quality_model": p["model"], "run_id": p["run_id"]}
            done[0] += 1
            if done[0] % 10 == 0 or done[0] == len(batches):
                print(f"prose_audit: {done[0]}/{len(batches)} batches, judged={len(results)}, "
                      f"spend=${spend.total:.4f}", flush=True)

    with ThreadPoolExecutor(max_workers=CONCURRENCY) as pool:
        list(pool.map(run, batches))

    by_id = {r["content_item_id"]: r for r in rows}
    payload = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "window": [args.date_from.isoformat(), args.date_until.isoformat()],
        "model": MODEL,
        "served_models": sorted(served_models),
        "prompt_version": prompt_version,
        "n_population": len(rows),
        "n_judged": len(results),
        "spend": {
            "actual_usage_cost_usd": round(spend.total, 6),
            "table_estimate_usd": round(spend.estimated, 6),
            "calls": spend.calls,
            "calls_without_usage_cost": spend.calls_without_actual,
            "cap_usd": args.max_cost_usd,
        },
        "errors": errors,
        "results": {
            str(pid): {
                **rec,
                "title": by_id[pid]["title"],
                "quality_status": by_id[pid]["quality_status"],
                "scores": {d: by_id[pid]["result_json"].get(d) for d in DIMS},
                "so_what": by_id[pid]["result_json"].get("so_what"),
                "reason_not_higher": by_id[pid]["result_json"].get("reason_not_higher"),
            }
            for pid, rec in sorted(results.items())
        },
    }
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(payload, indent=2, default=str), encoding="utf-8")
    print(f"prose_audit: done judged={len(results)}/{len(rows)} errors={len(errors)} "
          f"usage.cost=${spend.total:.4f} (table est ${spend.estimated:.4f}) -> {out_path}", flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
