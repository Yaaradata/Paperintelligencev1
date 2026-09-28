"""Backlog chain gates: weeks run in order, stop on projection, credit, spend, state, audit."""

from __future__ import annotations

import importlib.util
import json
from pathlib import Path
from unittest.mock import MagicMock

import pytest

SCRIPT = Path(__file__).resolve().parents[2] / "scripts" / "launch_backlog_chain.py"
WEEKS = [["2026-08-01", "2026-08-07"], ["2026-08-08", "2026-08-14"], ["2026-08-15", "2026-08-21"]]


@pytest.fixture()
def chain(monkeypatch, tmp_path):
    spec = importlib.util.spec_from_file_location("launch_backlog_chain", SCRIPT)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    monkeypatch.setattr(mod, "STATUS_DIR", tmp_path)
    cfg = {"weeks": WEEKS, "per_week_cap": 3.0, "max_week_projection": 2.5, "cumulative_stop": 7.0,
           "min_key_credit": 2.0, "extra_env": {}}
    (tmp_path / "backlog_chain1.json").write_text(json.dumps({"run_id": "chain1", "config": cfg}))
    finished: dict = {}
    monkeypatch.setattr(mod, "connect", MagicMock())
    monkeypatch.setattr(mod, "finish_pipeline_run", lambda conn, rid, **k: finished.update(k))
    monkeypatch.setattr(mod, "completeness", lambda w: {"complete": True})
    monkeypatch.setattr(mod, "reuse_counts", lambda w: {"scored_jev_glm": 0})
    monkeypatch.setattr(mod, "key_credit", lambda: 19.0)
    monkeypatch.setattr(mod, "dry_run", lambda w, env, cap: {"exit_code": 0, "stages": {}, "total_usd": 1.0})
    ran: list = []

    def run_week(cid, week, env, cap):
        ran.append((week, round(cap, 4)))
        return {"run_id": f"r{len(ran)}", "state": "succeeded", "exit_code": 0,
                "pipeline_actual_usd": 1.0, "db_llm_cost_usd": 1.1}

    monkeypatch.setattr(mod, "run_week", run_week)
    monkeypatch.setattr(mod, "audit", lambda cid, w, env: {"yes": True, "exit_code": 0, "report": "r.md"})
    mod._test = {"ran": ran, "finished": finished, "status": tmp_path / "backlog_chain1.json"}
    return mod


def _status(mod):
    return json.loads(mod._test["status"].read_text())


def test_all_weeks_in_order_and_spend_is_the_larger_cost_source(chain):
    assert chain.supervise("chain1") == 0
    assert [w for w, _ in chain._test["ran"]] == [tuple(w) for w in WEEKS]
    s = _status(chain)
    assert s["state"] == "succeeded" and s["weeks_completed"] == 3
    assert s["spent_usd"] == pytest.approx(3.3)
    assert chain._test["finished"]["status"] == "succeeded"


def test_projection_over_limit_stops_before_running(chain, monkeypatch):
    monkeypatch.setattr(chain, "dry_run", lambda w, env, cap: {"exit_code": 0, "stages": {}, "total_usd": 2.6})
    assert chain.supervise("chain1") == 1
    assert chain._test["ran"] == []
    assert "exceeds $2.5" in _status(chain)["stop_reason"]


def test_failed_audit_stops_the_chain(chain, monkeypatch):
    monkeypatch.setattr(chain, "audit", lambda cid, w, env: {"yes": False, "exit_code": 2, "report": "r.md"})
    chain.supervise("chain1")
    assert len(chain._test["ran"]) == 1
    assert "did not print YES" in _status(chain)["stop_reason"]


def test_week_not_succeeded_stops_without_audit(chain, monkeypatch):
    audited = []
    monkeypatch.setattr(chain, "run_week", lambda cid, w, env, cap: {
        "run_id": "r", "state": "cancelled", "exit_code": 3, "pipeline_actual_usd": 0.2, "db_llm_cost_usd": 0.2})
    monkeypatch.setattr(chain, "audit", lambda *a: audited.append(1))
    chain.supervise("chain1")
    assert audited == []
    assert "closed cancelled" in _status(chain)["stop_reason"]


def test_cumulative_cap_limits_week_cap_and_stops(chain, monkeypatch):
    def run_week(cid, week, env, cap):
        chain._test["ran"].append((week, round(cap, 4)))
        spend = min(3.0, cap)
        return {"run_id": "r", "state": "succeeded", "exit_code": 0,
                "pipeline_actual_usd": spend, "db_llm_cost_usd": spend}

    monkeypatch.setattr(chain, "run_week", run_week)
    chain.supervise("chain1")
    assert [c for _, c in chain._test["ran"]] == [3.0, 3.0, 1.0]
    assert _status(chain)["spent_usd"] == pytest.approx(7.0)


def test_spend_reaching_cumulative_stop_blocks_next_week(chain, monkeypatch):
    monkeypatch.setattr(chain, "run_week", lambda cid, w, env, cap: (
        chain._test["ran"].append(w) or {"run_id": "r", "state": "succeeded", "exit_code": 0,
                                         "pipeline_actual_usd": cap, "db_llm_cost_usd": cap}))
    monkeypatch.setattr(chain, "dry_run", lambda w, env, cap: {"exit_code": 0, "stages": {}, "total_usd": 0.5})
    cfg_path = chain._test["status"]
    data = json.loads(cfg_path.read_text())
    data["config"]["weeks"] = WEEKS + [["2026-08-22", "2026-08-24"]]
    cfg_path.write_text(json.dumps(data))
    chain.supervise("chain1")
    assert len(chain._test["ran"]) == 3
    assert "reached $7" in _status(chain)["stop_reason"]


def test_low_key_credit_stops(chain, monkeypatch):
    monkeypatch.setattr(chain, "key_credit", lambda: 1.5)
    chain.supervise("chain1")
    assert chain._test["ran"] == []
    assert "below $2.0" in _status(chain)["stop_reason"]


def test_credit_below_projection_plus_one_stops(chain, monkeypatch):
    monkeypatch.setattr(chain, "key_credit", lambda: 2.9)
    monkeypatch.setattr(chain, "dry_run", lambda w, env, cap: {"exit_code": 0, "stages": {}, "total_usd": 2.0})
    chain.supervise("chain1")
    assert chain._test["ran"] == []
    assert "+ $1" in _status(chain)["stop_reason"]


def test_incomplete_week_stops(chain, monkeypatch):
    monkeypatch.setattr(chain, "completeness", lambda w: {"complete": False, "missing_from_db": 4})
    chain.supervise("chain1")
    assert chain._test["ran"] == []
    assert "completeness not met" in _status(chain)["stop_reason"]


def test_parse_projection_reads_top_level_lines_and_last_budget():
    spec = importlib.util.spec_from_file_location("lbc", SCRIPT)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    out = "\n".join([
        "PROJECTION screen: 205 papers, ~14 calls, ~86459 in / ~8200 out tokens, ~$0.02",
        "budget: projected=$0.0171 actual=$0.0000 cap=$25.0000 status=ok",
        "  PROJECTION quality model=typesafe/jev-1.13: 183 papers, ~366 calls, ~$0.0962",
        "PROJECTION quality: 183 papers, ~366 calls, ~369086 in / ~128100 out tokens, ~$0.10",
        "budget: projected=$0.2600 actual=$0.0000 cap=$3.0000 status=ok",
        "",
        "=== pipeline stage: screen ===",
        "PROJECTION screen: 205 papers, ~14 calls, ~86459 in / ~8200 out tokens, ~$0.02",
        "budget: projected=$0.0171 actual=$0.0000 cap=$3.0000 status=ok",
        "=== pipeline stage: quality ===",
        "budget: projected=$0.0962 actual=$0.0000 cap=$3.0000 status=ok",
    ])
    p = mod.parse_projection(out)
    assert p["stages"] == {"screen": {"papers": 205, "usd": 0.02}, "quality": {"papers": 183, "usd": 0.10}}
    assert p["total_usd"] == 0.26
