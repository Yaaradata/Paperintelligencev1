from __future__ import annotations

import importlib.util
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
spec = importlib.util.spec_from_file_location("daily_health_report", ROOT / "scripts" / "daily_health_report.py")
dhr = importlib.util.module_from_spec(spec)
sys.modules["daily_health_report"] = dhr
spec.loader.exec_module(dhr)

NOW = datetime(2026, 9, 30, 0, 30, tzinfo=timezone.utc)  # 06:00 IST, Wednesday


def _stage(name, *, n_in=100, ok=100, failed=0, skipped=0, status="succeeded", **meta):
    return {"pipeline_name": f"paper_intelligence.{name}", "status": status, "items_input": n_in,
            "items_succeeded": ok, "items_failed": failed, "items_skipped": skipped, "metadata": meta}


def _facts(**over):
    facts = {
        "now": NOW, "local": NOW.astimezone(dhr.IST),
        "run": {"run_id": "r", "status": "succeeded", "started_at": NOW - timedelta(hours=3),
                "ended_at": NOW - timedelta(hours=2), "metadata": {}, "date_from": "2026-09-29",
                "date_until": "2026-09-29"},
        "stages": [_stage("ingest", records_seen=500, records_new=412, records_dupe=88),
                   _stage("relevance", candidates=412, kept=300, rejected=112),
                   _stage("audience_domain", n_in=300, ok=300, oov_papers=3, cost_usd=0.05)],
        "newest_paper": NOW - timedelta(days=1),
        "spend_today": 0.4, "spend_month": 12.0, "stuck": [], "missing_tables": [],
        "audit": None, "tests": {"exit_code": 0, "passed": 367, "failed": 0, "tail": ""},
    }
    facts.update(over)
    return facts


def _by_name(checks, prefix):
    return next(c for c in checks if c.name.startswith(prefix))


def test_healthy_day_is_ok_with_counts_in_subject():
    subject, body = dhr.render(_facts(), dhr.build_checks(_facts()))
    assert subject.startswith("[OK] PaperIntelligence — 30 Sep — 412 new papers, 0 failures")
    assert "NEEDS ATTENTION" not in body
    assert "300 in" not in body and "412 in → 300 relevant, 112 rejected" in body
    assert "No email by 08:00 IST" in body


def test_stage_over_failure_threshold_flags_attention():
    stages = [_stage("quality", n_in=100, ok=90, failed=10, status="partial", stop_reason="runguard")]
    f = _facts(stages=stages)
    checks = dhr.build_checks(f)
    c = _by_name(checks, "no stage failure")
    assert not c.ok and "quality: 10 of 100 failed" in c.attention and "runguard" in c.attention
    subject, body = dhr.render(f, checks)
    assert subject.startswith("[ATTENTION]") and body.startswith("NEEDS ATTENTION")


def test_no_recent_run_and_stale_papers():
    run = {**_facts()["run"], "started_at": NOW - timedelta(hours=30)}
    checks = dhr.build_checks(_facts(run=run, newest_paper=NOW - timedelta(days=6)))
    assert not _by_name(checks, "pipeline ran").ok
    assert not _by_name(checks, "newest paper").ok


def test_freshness_allows_extra_day_on_monday():
    monday = datetime(2026, 9, 28, 0, 30, tzinfo=timezone.utc)
    f = _facts(now=monday, local=monday.astimezone(dhr.IST), newest_paper=monday - timedelta(days=4),
               run={**_facts()["run"], "started_at": monday - timedelta(hours=3)})
    assert _by_name(dhr.build_checks(f), "newest paper").ok


def test_spend_caps_and_oov():
    checks = dhr.build_checks(_facts(spend_today=dhr.DAILY_SPEND_CAP + 1, spend_month=dhr.MONTHLY_SPEND_CAP + 1))
    assert not _by_name(checks, "daily spend").ok and not _by_name(checks, "month-to-date").ok
    oov_bad = [_stage("audience_domain", n_in=100, ok=100, oov_papers=10)]
    assert not _by_name(dhr.build_checks(_facts(stages=oov_bad)), "classify out-of-vocabulary").ok
    unrecorded = [_stage("audience_domain", n_in=100, ok=100)]
    c = _by_name(dhr.build_checks(_facts(stages=unrecorded)), "classify out-of-vocabulary")
    assert not c.ok and "not recorded" in c.detail


def test_stuck_runs_summarised():
    stuck = [{"run_id": str(i), "pipeline_name": f"paper_intelligence.s{i}", "started_at": NOW - timedelta(days=9 - i)}
             for i in range(8)]
    c = _by_name(dhr.build_checks(_facts(stuck=stuck)), "no runs stuck")
    assert not c.ok and c.attention.startswith("8 run(s) stuck") and "+3 more" in c.attention


def test_runs_under_a_live_pipeline_are_not_stuck():
    started = NOW - timedelta(hours=3)
    live = {"w1": started}
    wrapper = {"run_id": "w1", "pipeline_name": "paper_intelligence.pipeline_detached", "started_at": started}
    stage = {"run_id": "s1", "pipeline_name": "affiliation_fast", "started_at": started + timedelta(minutes=30)}
    old = {"run_id": "s0", "pipeline_name": "affiliation_fast", "started_at": started - timedelta(days=5)}
    dead_chain = {"run_id": "c1", "pipeline_name": "paper_intelligence.backlog_chain",
                  "started_at": started + timedelta(minutes=5)}
    assert dhr._belongs_to_live_run(wrapper, live)
    assert dhr._belongs_to_live_run(stage, live)
    assert not dhr._belongs_to_live_run(old, live)
    assert not dhr._belongs_to_live_run(dead_chain, live)
    assert not dhr._belongs_to_live_run(stage, {})


def test_a_check_that_throws_is_reported_not_raised():
    f = _facts(newest_paper="not a datetime")
    c = next(c for c in dhr.build_checks(f) if "errored" in c.name)
    assert not c.ok and "freshness" in c.attention


def test_report_crash_still_produces_error_email(monkeypatch):
    def boom(*a, **k):
        raise RuntimeError("db down")
    monkeypatch.setattr(dhr, "gather", boom)
    import paper_intelligence.db as db
    monkeypatch.setattr(db, "connect", lambda: _NullConn())
    subject, body = dhr.build_report(with_tests=False, with_audit=False, now=NOW)
    assert subject.startswith("[ERROR] PaperIntelligence — 30 Sep — health check crashed")
    assert "db down" in body and "UNKNOWN" in body


class _NullConn:
    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False
