#!/usr/bin/env python3
"""Compare quality router modes (read-only; no LLM).

For a date window, report selection under window vs day percentile scope,
with and without judge-effective notable-org filtering. Shows added/removed
ids vs the current default (window + judge-effective), how many new ids
already have reusable quality, and dry-run cost for the rest.

  PYTHONPATH=src python3 scripts/compare_router_modes.py \\
    --from 2026-09-01 --until 2026-09-15 \\
    --out reports/review_fixes/router_mode_comparison.json
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))


def _set_stats(
    label: str,
    ids: list[int],
    *,
    baseline: set[int],
    done: set[int],
) -> dict[str, Any]:
    s = set(ids)
    added = sorted(s - baseline)
    removed = sorted(baseline - s)
    added_have_quality = [i for i in added if i in done]
    added_need_quality = [i for i in added if i not in done]
    return {
        "label": label,
        "selected_n": len(s),
        "added_vs_baseline_n": len(added),
        "removed_vs_baseline_n": len(removed),
        "added_ids": added,
        "removed_ids": removed,
        "added_already_quality_n": len(added_have_quality),
        "added_need_quality_n": len(added_need_quality),
        "added_need_quality_ids": added_need_quality,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--from", dest="date_from", default="2026-09-01")
    parser.add_argument("--until", dest="date_until", default="2026-09-15")
    parser.add_argument(
        "--out",
        default=str(ROOT / "reports/review_fixes/router_mode_comparison.json"),
    )
    parser.add_argument("--gate-percentile", type=float, default=None)
    args = parser.parse_args(argv)

    from paper_intelligence.common.config import GATE_PERCENTILE
    from paper_intelligence.db import connect, ids_with_result
    from paper_intelligence.quality.model_policy import group_ids_by_quality_model
    from paper_intelligence.db import fetch_papers
    from paper_intelligence.quality import stage as quality_stage
    from paper_intelligence.quality.stage import (
        POLICY_VERSION,
        PROMPT_VERSION,
        STAGE_VERSION,
        select_quality_candidates,
    )

    gate = args.gate_percentile if args.gate_percentile is not None else GATE_PERCENTILE
    modes = [
        ("window+judge", "window", True),
        ("window+raw_ooi", "window", False),
        ("day+judge", "day", True),
        ("day+raw_ooi", "day", False),
    ]

    with connect() as conn:
        selections: dict[str, list[int]] = {}
        for label, scope, judge in modes:
            selections[label] = select_quality_candidates(
                conn,
                date_from=args.date_from,
                date_until=args.date_until,
                gate_percentile=gate,
                percentile_scope=scope,
                apply_judge_effective=judge,
            )

        baseline_label = "window+judge"
        baseline = set(selections[baseline_label])

        # Reusable quality under date-mapped model.
        all_ids = sorted({i for ids in selections.values() for i in ids})
        papers = fetch_papers(conn, all_ids) if all_ids else []
        done: set[int] = set()
        for model, group_ids in group_ids_by_quality_model(
            papers, honor_env_override=False
        ).items():
            done |= ids_with_result(
                conn,
                group_ids,
                "quality",
                stage_version=STAGE_VERSION,
                prompt_version=PROMPT_VERSION,
                policy_version=POLICY_VERSION,
                model=model,
            )

        # Per-day breakdown for day+judge
        from datetime import date as date_cls, timedelta

        d0 = date_cls.fromisoformat(args.date_from)
        d1 = date_cls.fromisoformat(args.date_until)
        per_day: dict[str, dict[str, int]] = {}
        day = d0
        while day <= d1:
            day_s = day.isoformat()
            w = select_quality_candidates(
                conn,
                date_from=day_s,
                date_until=day_s,
                gate_percentile=gate,
                percentile_scope="window",
                apply_judge_effective=True,
            )
            d = select_quality_candidates(
                conn,
                date_from=day_s,
                date_until=day_s,
                gate_percentile=gate,
                percentile_scope="day",
                apply_judge_effective=True,
            )
            # For a single day, window == day; still record counts.
            per_day[day_s] = {"window_or_day_n": len(w), "day_scope_n": len(d)}
            day += timedelta(days=1)

        mode_stats = []
        projections: dict[str, Any] = {}
        for label, _, _ in modes:
            st = _set_stats(
                label, selections[label], baseline=baseline, done=done
            )
            need = st["added_need_quality_ids"]
            if need:
                papers_need = fetch_papers(conn, need)
                groups = group_ids_by_quality_model(
                    papers_need, honor_env_override=False
                )
                cost = 0.0
                calls = 0
                for model, gids in groups.items():
                    stats = quality_stage.run_window(
                        conn,
                        gids,
                        run_id="dry-run",
                        stage_run_id="dry-run",
                        dry_run=True,
                        model=model,
                    )
                    cost += stats.cost_usd
                    calls += stats.calls
                st["added_need_quality_projected_usd"] = round(cost, 4)
                st["added_need_quality_projected_calls"] = calls
            else:
                st["added_need_quality_projected_usd"] = 0.0
                st["added_need_quality_projected_calls"] = 0
            mode_stats.append(st)
            projections[label] = st

        # Also: full set dry-run for day+judge new-only vs baseline
        report = {
            "date_from": args.date_from,
            "date_until": args.date_until,
            "gate_percentile": gate,
            "baseline": baseline_label,
            "baseline_selected_n": len(baseline),
            "modes": mode_stats,
            "per_day_counts": per_day,
            "note": (
                "Default production scope remains window. "
                "Judge-effective notable-org is ON by default. "
                "No LLM calls executed."
            ),
        }

    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(report, indent=2, default=str) + "\n", encoding="utf-8")

    md = out.with_suffix(".md")
    lines = [
        f"# Router mode comparison {args.date_from} → {args.date_until}",
        "",
        f"Baseline: **{baseline_label}** (n={len(baseline)}, gate={gate}%).",
        "Default production scope is unchanged (`window`).",
        "",
        "## Modes",
        "",
        "| Mode | Selected | + vs baseline | − vs baseline | + already quality | + need quality | + dry-run $ |",
        "|---|---:|---:|---:|---:|---:|---:|",
    ]
    for st in mode_stats:
        lines.append(
            f"| `{st['label']}` | {st['selected_n']} | {st['added_vs_baseline_n']} | "
            f"{st['removed_vs_baseline_n']} | {st['added_already_quality_n']} | "
            f"{st['added_need_quality_n']} | ${st['added_need_quality_projected_usd']:.4f} |"
        )
    lines += ["", "## Per-day counts (single-day windows)", ""]
    for day_s, counts in sorted(per_day.items()):
        lines.append(
            f"- {day_s}: selected={counts['window_or_day_n']}"
        )
    lines += ["", "No LLM calls. No default scope change.", ""]
    md.write_text("\n".join(lines) + "\n", encoding="utf-8")

    print(f"wrote {out}")
    print(f"wrote {md}")
    for st in mode_stats:
        print(
            f"  {st['label']}: n={st['selected_n']} "
            f"+{st['added_vs_baseline_n']}/-{st['removed_vs_baseline_n']} "
            f"need_quality={st['added_need_quality_n']} "
            f"~${st['added_need_quality_projected_usd']:.4f}"
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
