"""Golden-set load and evaluation helpers."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from psycopg import Connection

REPO_ROOT = Path(__file__).resolve().parents[3]
GOLDEN_DIR = REPO_ROOT / "data" / "golden"


def load_golden_file(path: str | Path) -> dict[str, Any]:
    target = Path(path)
    payload = json.loads(target.read_text(encoding="utf-8"))
    required = {"name", "version", "task_type", "items"}
    missing = required - set(payload)
    if missing:
        raise ValueError(f"{target}: missing keys {sorted(missing)}")
    if not isinstance(payload["items"], list) or not payload["items"]:
        raise ValueError(f"{target}: items must be a non-empty list")
    return payload


def upsert_golden_set(conn: Connection, payload: dict[str, Any]) -> dict[str, int]:
    """Insert/replace a golden set + items + labels. Returns counts."""
    name = payload["name"]
    version = payload["version"]
    task_type = payload["task_type"]
    # Map package task names onto schema task_type values where needed.
    label_task = {
        "audience_domain": "domain",
        "author_affiliation": "author_affiliation",
    }.get(task_type, task_type)

    with conn.cursor() as cur:
        cur.execute(
            """
            INSERT INTO paper_intelligence.golden_sets (name, version, task_type)
            VALUES (%s, %s, %s)
            ON CONFLICT (name) DO UPDATE SET
                version = EXCLUDED.version,
                task_type = EXCLUDED.task_type
            RETURNING id
            """,
            (name, version, task_type),
        )
        golden_set_id = int(cur.fetchone()["id"])

        cur.execute(
            "DELETE FROM paper_intelligence.golden_labels WHERE golden_set_id = %s",
            (golden_set_id,),
        )
        cur.execute(
            "DELETE FROM paper_intelligence.golden_set_items WHERE golden_set_id = %s",
            (golden_set_id,),
        )

        items_written = 0
        labels_written = 0
        missing_content = 0
        for item in payload["items"]:
            content_item_id = int(item["content_item_id"])
            cur.execute(
                "SELECT 1 FROM research_radar.content_items WHERE id = %s",
                (content_item_id,),
            )
            if cur.fetchone() is None:
                missing_content += 1
                continue
            cur.execute(
                """
                INSERT INTO paper_intelligence.golden_set_items (golden_set_id, content_item_id)
                VALUES (%s, %s)
                ON CONFLICT DO NOTHING
                """,
                (golden_set_id, content_item_id),
            )
            items_written += 1
            source = item.get("gold_label_source") or "manual"
            if source not in {"manual", "llm_adjudicated"}:
                source = "manual"
            # Schema stores one label row per (set, content, task_type).
            # For audience_domain we store the combined label under task_type='domain'
            # and also under 'audience' when audiences are present.
            label_json = item.get("label_json") or {}
            tasks = [label_task]
            if task_type == "audience_domain" and label_json.get("audiences") is not None:
                tasks.append("audience")
            for task in tasks:
                cur.execute(
                    """
                    INSERT INTO paper_intelligence.golden_labels
                        (golden_set_id, content_item_id, task_type, label_json,
                         gold_label_source, labeller)
                    VALUES (%s, %s, %s, %s::jsonb, %s, %s)
                    ON CONFLICT (golden_set_id, content_item_id, task_type) DO UPDATE SET
                        label_json = EXCLUDED.label_json,
                        gold_label_source = EXCLUDED.gold_label_source,
                        labeller = EXCLUDED.labeller
                    """,
                    (
                        golden_set_id,
                        content_item_id,
                        task,
                        json.dumps(label_json, default=str),
                        source,
                        item.get("labeller"),
                    ),
                )
                labels_written += 1

    conn.commit()
    return {
        "golden_set_id": golden_set_id,
        "items_written": items_written,
        "labels_written": labels_written,
        "missing_content": missing_content,
    }


def _latest_pred(conn: Connection, content_item_id: int, task_type: str) -> dict[str, Any] | None:
    with conn.cursor() as cur:
        cur.execute(
            """
            SELECT result_json
            FROM paper_intelligence.paper_classification_results
            WHERE content_item_id = %s AND task_type = %s
            ORDER BY created_at DESC
            LIMIT 1
            """,
            (content_item_id, task_type),
        )
        row = cur.fetchone()
    return (row["result_json"] if row else None) or None


def _affiliation_orgs(conn: Connection, content_item_id: int) -> set[str]:
    with conn.cursor() as cur:
        cur.execute(
            """
            SELECT DISTINCT COALESCE(o.canonical_name, a.raw_affiliation) AS name
            FROM paper_intelligence.paper_author_affiliations a
            LEFT JOIN paper_intelligence.organisations o ON o.id = a.organisation_id
            WHERE a.content_item_id = %s
              AND COALESCE(o.canonical_name, a.raw_affiliation) IS NOT NULL
            """,
            (content_item_id,),
        )
        return {str(r["name"]).casefold() for r in cur.fetchall() if r["name"]}


def evaluate_audience_domain(
    conn: Connection, *, golden_version: str = "v1"
) -> dict[str, Any]:
    with conn.cursor() as cur:
        cur.execute(
            """
            SELECT gs.id, gs.name
            FROM paper_intelligence.golden_sets gs
            WHERE gs.task_type = 'audience_domain' AND gs.version = %s
            ORDER BY gs.id
            """,
            (golden_version,),
        )
        sets = list(cur.fetchall())
    if not sets:
        raise LookupError(f"no audience_domain golden set version={golden_version}")

    summary: dict[str, Any] = {"sets": [], "by_source": {}}
    for gs in sets:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT gl.content_item_id, gl.task_type, gl.label_json, gl.gold_label_source
                FROM paper_intelligence.golden_labels gl
                WHERE gl.golden_set_id = %s AND gl.task_type IN ('domain', 'audience')
                """,
                (gs["id"],),
            )
            labels = list(cur.fetchall())

        stats = {
            "name": gs["name"],
            "n": 0,
            "domain_compared": 0,
            "domain_match": 0,
            "audience_compared": 0,
            "audience_exact": 0,
            "missing_prediction": 0,
        }
        for row in labels:
            source = row["gold_label_source"] or "manual"
            bucket = summary["by_source"].setdefault(
                source, {"n": 0, "domain_match": 0, "domain_compared": 0}
            )
            label = row["label_json"] or {}
            pred = _latest_pred(conn, int(row["content_item_id"]), row["task_type"])
            stats["n"] += 1
            bucket["n"] += 1
            if pred is None:
                stats["missing_prediction"] += 1
                continue
            if row["task_type"] == "domain":
                gold_domain = (label.get("domain") or "").strip().casefold()
                pred_domain = (pred.get("domain") or "").strip().casefold()
                if gold_domain:
                    stats["domain_compared"] += 1
                    bucket["domain_compared"] += 1
                    if gold_domain == pred_domain:
                        stats["domain_match"] += 1
                        bucket["domain_match"] += 1
            elif row["task_type"] == "audience":
                gold_aud = sorted({a.casefold() for a in (label.get("audiences") or [])})
                pred_aud = sorted({a.casefold() for a in (pred.get("audiences") or [])})
                stats["audience_compared"] += 1
                if gold_aud == pred_aud:
                    stats["audience_exact"] += 1
        if stats["domain_compared"]:
            stats["domain_accuracy"] = round(
                stats["domain_match"] / stats["domain_compared"], 4
            )
        if stats["audience_compared"]:
            stats["audience_exact_accuracy"] = round(
                stats["audience_exact"] / stats["audience_compared"], 4
            )
        summary["sets"].append(stats)

    for source, bucket in summary["by_source"].items():
        if bucket["domain_compared"]:
            bucket["domain_accuracy"] = round(
                bucket["domain_match"] / bucket["domain_compared"], 4
            )
    return summary


def evaluate_author_affiliation(
    conn: Connection, *, golden_version: str = "v1"
) -> dict[str, Any]:
    with conn.cursor() as cur:
        cur.execute(
            """
            SELECT gs.id, gs.name
            FROM paper_intelligence.golden_sets gs
            WHERE gs.task_type = 'author_affiliation' AND gs.version = %s
            ORDER BY gs.id
            LIMIT 1
            """,
            (golden_version,),
        )
        gs = cur.fetchone()
    if not gs:
        raise LookupError(f"no author_affiliation golden set version={golden_version}")

    with conn.cursor() as cur:
        cur.execute(
            """
            SELECT content_item_id, label_json, gold_label_source
            FROM paper_intelligence.golden_labels
            WHERE golden_set_id = %s
            """,
            (gs["id"],),
        )
        labels = list(cur.fetchall())

    stats = {
        "name": gs["name"],
        "n": len(labels),
        "compared": 0,
        "any_org_overlap": 0,
        "exact_org_set": 0,
        "missing_prediction": 0,
        "by_source": {},
    }
    for row in labels:
        source = row["gold_label_source"] or "llm_adjudicated"
        bucket = stats["by_source"].setdefault(
            source, {"n": 0, "compared": 0, "any_org_overlap": 0, "exact_org_set": 0}
        )
        bucket["n"] += 1
        gold_orgs = {
            str(o).casefold()
            for o in ((row["label_json"] or {}).get("organisations") or [])
            if o
        }
        pred_orgs = _affiliation_orgs(conn, int(row["content_item_id"]))
        if not pred_orgs:
            stats["missing_prediction"] += 1
            continue
        stats["compared"] += 1
        bucket["compared"] += 1
        if gold_orgs & pred_orgs:
            stats["any_org_overlap"] += 1
            bucket["any_org_overlap"] += 1
        if gold_orgs and gold_orgs == pred_orgs:
            stats["exact_org_set"] += 1
            bucket["exact_org_set"] += 1

    if stats["compared"]:
        stats["overlap_rate"] = round(stats["any_org_overlap"] / stats["compared"], 4)
        stats["exact_rate"] = round(stats["exact_org_set"] / stats["compared"], 4)
    return stats
