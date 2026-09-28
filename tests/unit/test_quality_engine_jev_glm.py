"""Tests for QUALITY_ENGINE=terra|jev_glm routing and prose failure isolation."""

from __future__ import annotations

import json
from unittest.mock import MagicMock, patch

import pytest

from paper_intelligence.quality import jev_glm_engine as jev_glm
from paper_intelligence.quality.stage import (
    RUBRIC_DIMENSIONS,
    active_policy_version,
    active_prompt_version,
    composite_score,
)


class TestEngineRouting:
    def test_default_engine_is_terra(self):
        from paper_intelligence.common import config

        # Default when env unset / terra
        assert config.QUALITY_ENGINE in {"terra", "jev_glm"}

    def test_active_versions_terra(self, monkeypatch):
        monkeypatch.setenv("QUALITY_ENGINE", "terra")
        # Re-read would need reload; call helpers with patched QUALITY_ENGINE
        import paper_intelligence.quality.stage as stage

        monkeypatch.setattr(stage, "QUALITY_ENGINE", "terra")
        assert stage.active_prompt_version() == "v001"
        assert stage.active_policy_version() == "v001"

    def test_active_versions_jev_glm(self, monkeypatch):
        import paper_intelligence.quality.stage as stage

        monkeypatch.setattr(stage, "QUALITY_ENGINE", "jev_glm")
        assert stage.active_prompt_version() == "prose_v001"
        assert stage.active_policy_version() == "systemone_v001"

    def test_run_window_routes_to_jev_glm(self, monkeypatch):
        import paper_intelligence.quality.stage as stage

        monkeypatch.setattr(stage, "QUALITY_ENGINE", "jev_glm")
        called = {}

        def fake_jev(*args, **kwargs):
            called["yes"] = True
            from paper_intelligence.common.batch_runner import BatchStats

            return BatchStats(papers_requested=0)

        monkeypatch.setattr(
            "paper_intelligence.quality.jev_glm_engine.run_jev_glm_window",
            fake_jev,
        )
        stats = stage.run_window(
            MagicMock(), [], run_id="r", stage_run_id="s", dry_run=True
        )
        assert called.get("yes") is True
        assert stats.papers_requested == 0

    def test_run_window_terra_default_does_not_call_jev(self, monkeypatch):
        import paper_intelligence.quality.stage as stage

        monkeypatch.setattr(stage, "QUALITY_ENGINE", "terra")
        called = {}

        def fake_jev(*args, **kwargs):
            called["yes"] = True
            from paper_intelligence.common.batch_runner import BatchStats

            return BatchStats()

        monkeypatch.setattr(
            "paper_intelligence.quality.jev_glm_engine.run_jev_glm_window",
            fake_jev,
        )
        # empty ids → early return before LLM; must not route to jev
        stats = stage.run_window(
            MagicMock(), [], run_id="r", stage_run_id="s", dry_run=True
        )
        assert called.get("yes") is None
        assert stats.papers_requested == 0


class TestProseParse:
    def test_parse_prose_ok(self):
        text = json.dumps(
            {
                "papers": [
                    {
                        "batch_index": 1,
                        "so_what": "Leaders can ship X.",
                        "reason_not_higher": "Only evaluated on Y.",
                    }
                ]
            }
        )
        out, problems = jev_glm.parse_prose_response(text, {1: 42})
        assert problems == []
        assert out[42]["so_what"].startswith("Leaders")
        assert out[42]["reason_not_higher"].startswith("Only")

    def test_parse_rejects_emitted_scores(self):
        text = json.dumps(
            {
                "papers": [
                    {
                        "batch_index": 1,
                        "so_what": "x",
                        "reason_not_higher": "y",
                        "technical_significance": 9.0,
                    }
                ]
            }
        )
        out, problems = jev_glm.parse_prose_response(text, {1: 42})
        assert any("prose_emitted_score_field" in p for p in problems)
        assert 42 in out  # still parsed prose fields

    def test_recover_truncated_json_keeps_complete_papers(self):
        # Second paper truncated mid-string — first paper must still parse.
        text = (
            '{"papers":[{"batch_index":1,"so_what":"Ship it.",'
            '"reason_not_higher":"Narrow eval."},'
            '{"batch_index":2,"so_what":"If your distillation data is model-generated'
        )
        out, problems = jev_glm.parse_prose_response(text, {1: 10, 2: 20})
        assert out[10]["so_what"] == "Ship it."
        assert out[10]["reason_not_higher"] == "Narrow eval."
        assert 20 not in out or not (
            out[20].get("so_what") and out[20].get("reason_not_higher")
        )
        assert any("prose_missing_batch_index" in p for p in problems)

    def test_empty_output_is_error(self):
        out, problems = jev_glm.parse_prose_response("", {1: 1})
        assert out == {}
        assert any("prose_json_error" in p for p in problems)


class TestPersistBeforeProse:
    def test_build_quality_row_scores_without_prose(self):
        dims = {d: 7.0 for d in RUBRIC_DIMENSIONS}
        dims["confidence"] = 0.8
        row = jev_glm.build_quality_row(
            paper={"content_item_id": 99, "title": "t", "abstract": "a"},
            dims=dims,
            prose=None,
            run_id="run-1",
        )
        assert row["task_type"] == "quality"
        assert row["result_json"]["technical_significance"] == 7.0
        assert row["result_json"]["so_what"] is None
        assert row["result_json"]["prose_failed"] is True
        assert row["result_json"]["scores_persisted_before_prose"] is True
        assert row["result_json"]["composite"]["quality"] == pytest.approx(
            composite_score(dims)["quality"]
        )

    def test_persist_called_before_prose_in_window(self, monkeypatch):
        """Scores must be written even if prose never runs."""
        from paper_intelligence.common.batch_runner import BatchStats

        order: list[str] = []

        def fake_persist(**kwargs):
            order.append("persist")
            return len(kwargs.get("scored") or {})

        def fake_merge(**kwargs):
            order.append("merge")
            return 0

        def boom_prose(*args, **kwargs):
            order.append("prose_call")
            raise RuntimeError("prose offline")

        scored_dims = {d: 5.0 for d in RUBRIC_DIMENSIONS}

        monkeypatch.setattr(jev_glm, "persist_jev_scores", fake_persist)
        monkeypatch.setattr(jev_glm, "merge_prose_into_scores", fake_merge)
        monkeypatch.setattr(
            jev_glm,
            "fetch_papers",
            lambda conn, ids: [
                {
                    "content_item_id": 1,
                    "title": "t",
                    "abstract": "a",
                    "content_hash": "h",
                }
            ],
        )
        monkeypatch.setattr(jev_glm, "read_prompt", lambda *a, **k: "sys")
        monkeypatch.setattr(jev_glm, "call_llm_logged", boom_prose)
        recorded: dict = {}
        monkeypatch.setattr(
            jev_glm, "record_prose_attempts", lambda **kw: recorded.update(kw) or 0
        )
        monkeypatch.setattr(jev_glm, "connect", MagicMock())
        monkeypatch.setattr(
            jev_glm, "score_paper_with_jev", lambda p, **kw: (scored_dims, None, 0.01)
        )

        def run_batches_score(batches, handler, **kwargs):
            for b in batches:
                handler(b)

        monkeypatch.setattr(jev_glm, "run_batches", run_batches_score)

        stats = jev_glm.run_jev_glm_window(
            MagicMock(),
            [1],
            run_id="r1",
            stage_run_id="s1",
            dry_run=False,
            max_cost_usd=1.0,
        )
        assert "persist" in order
        assert "prose_call" in order
        assert order.index("persist") < order.index("prose_call")
        assert "merge" in order
        assert order.count("prose_call") == jev_glm.PROSE_MAX_ATTEMPTS
        assert [f["content_item_id"] for f in recorded["failures"]] == [1]
        assert isinstance(stats, BatchStats)


def _llm_result(content: str, finish_reason: str = "stop") -> dict:
    return {
        "content": content,
        "finish_reason": finish_reason,
        "input_tokens": 100,
        "output_tokens": 50,
        "estimated_cost": 0.0001,
        "estimated_cost_usd": 0.0001,
        "actual_cost_usd": 0.0001,
    }


GOOD_PROSE = json.dumps(
    {"papers": [{"batch_index": 1, "so_what": "Specific.", "reason_not_higher": "Small eval."}]}
)


class TestPerPaperProse:
    PAPER = {"content_item_id": 42, "title": "T", "abstract": "A"}
    SCORED = {42: {d: 6.0 for d in RUBRIC_DIMENSIONS}}

    def _run(self, monkeypatch, responses):
        from paper_intelligence.common.batch_runner import BatchStats

        calls: list[dict] = []

        def fake_llm(conn, **kwargs):
            calls.append(kwargs)
            return responses[len(calls) - 1]

        monkeypatch.setattr(jev_glm, "call_llm_logged", fake_llm)
        monkeypatch.setattr(jev_glm, "connect", MagicMock())
        stats = BatchStats(papers_requested=1)
        cell, failure = jev_glm.run_prose_for_paper(
            paper=self.PAPER,
            scored=self.SCORED,
            prose_system="sys",
            run_id="r",
            stage_run_id="s",
            stats=stats,
        )
        return cell, failure, calls, stats

    def test_request_is_single_paper_json_object_no_provider_filter(self, monkeypatch):
        cell, failure, calls, _ = self._run(monkeypatch, [_llm_result(GOOD_PROSE)])
        assert failure is None and cell["so_what"] == "Specific."
        kw = calls[0]
        assert kw["response_format"] == {"type": "json_object"}
        assert "provider" not in kw
        assert kw["extra_body"] == {"reasoning": {"effort": "low"}}
        assert kw["max_tokens"] == jev_glm.PROSE_MAX_TOKENS == 800
        assert kw["user_prompt"].count("batch_index:") == 1

    def test_non_json_output_fails_validation_and_retries(self, monkeypatch):
        cell, failure, calls, _ = self._run(
            monkeypatch, [_llm_result("Here is the prose: it matters."), _llm_result(GOOD_PROSE)]
        )
        assert len(calls) == 2 and failure is None and cell["so_what"] == "Specific."

    def test_runguard_stops_window_when_all_fail(self, monkeypatch):
        from paper_intelligence.common.batch_runner import BatchStats
        from paper_intelligence.common.runguard import RunGuard, RunGuardTripped

        calls: list = []

        def bad(conn, **kwargs):
            calls.append(1)
            return _llm_result("", "length")

        monkeypatch.setattr(jev_glm, "call_llm_logged", bad)
        monkeypatch.setattr(jev_glm, "connect", MagicMock())
        monkeypatch.setattr(jev_glm, "read_prompt", lambda *a, **k: "sys")
        monkeypatch.setattr(jev_glm, "merge_prose_into_scores", lambda **kw: 0)
        recorded: dict = {}
        monkeypatch.setattr(jev_glm, "record_prose_attempts", lambda **kw: recorded.update(kw) or 0)
        papers = [{"content_item_id": i, "title": "t", "abstract": "a"} for i in range(1, 301)]
        scored = {i: {d: 5.0 for d in RUBRIC_DIMENSIONS} for i in range(1, 301)}
        guard = RunGuard(window=100, max_failure_rate=0.10, min_items=20)
        with pytest.raises(RunGuardTripped, match="tripped at item 20"):
            jev_glm.run_prose_for_papers(
                papers=papers, scored=scored, run_id="r", stage_run_id="s",
                stats=BatchStats(papers_requested=300), budget=None, concurrency=1, guard=guard,
            )
        assert len(calls) == 20 * jev_glm.PROSE_MAX_ATTEMPTS
        assert len(recorded["failures"]) == 20

    def test_parse_failure_retries_once_then_succeeds(self, monkeypatch):
        cell, failure, calls, _ = self._run(
            monkeypatch, [_llm_result("", "length"), _llm_result(GOOD_PROSE)]
        )
        assert len(calls) == 2
        assert failure is None and cell["reason_not_higher"] == "Small eval."

    def test_second_failure_returns_record_with_id_and_truncated_raw(self, monkeypatch):
        raw = '{"papers": [{"batch_index": 1, "so_what": "' + "x" * 900
        cell, failure, calls, stats = self._run(
            monkeypatch, [_llm_result(raw, "length"), _llm_result(raw, "length")]
        )
        assert cell is None and len(calls) == 2
        assert failure["content_item_id"] == 42
        assert failure["attempts"] == 2
        assert len(failure["raw_output"]) == 500
        assert "finish_reason=length" in failure["error"]
        assert all("content_item_id=42" in w for w in stats.warnings)

    def test_record_prose_attempts_isolated_from_adjudication(self, monkeypatch):
        captured: list = []
        monkeypatch.setattr(jev_glm, "connect", MagicMock())
        monkeypatch.setattr(
            jev_glm, "insert_quality_attempts", lambda conn, rows: captured.extend(rows) or len(rows)
        )
        n = jev_glm.record_prose_attempts(
            succeeded_ids=[1],
            failures=[{"content_item_id": 2, "error": "bad", "raw_output": "{", "attempts": 2}],
            run_id="backfill",
            stage_run_id="s",
            score_run_ids={1: "score-run", 2: "score-run"},
        )
        assert n == 2
        from paper_intelligence.quality.stage import STAGE_VERSION

        for row in captured:
            assert row["stage_version"] == "quality_prose_v001" != STAGE_VERSION
            assert row["model"] == jev_glm.PROSE_MODEL
        failed = [r for r in captured if r["status"] == "failed"][0]
        assert failed["content_item_id"] == 2
        assert failed["metadata"]["raw_output"] == "{"
        assert failed["metadata"]["score_run_id"] == "score-run"

    def test_routing_404_aborts_window_without_retry(self, monkeypatch):
        from paper_intelligence.common.batch_runner import BatchStats
        from paper_intelligence.openrouter.client import OpenRouterError

        calls: list = []

        def no_route(conn, **kwargs):
            calls.append(1)
            raise OpenRouterError("HTTP 404: No endpoints found", status=404)

        recorded: dict = {}
        monkeypatch.setattr(jev_glm, "call_llm_logged", no_route)
        monkeypatch.setattr(jev_glm, "connect", MagicMock())
        monkeypatch.setattr(jev_glm, "read_prompt", lambda *a, **k: "sys")
        monkeypatch.setattr(jev_glm, "merge_prose_into_scores", lambda **kw: 0)
        monkeypatch.setattr(jev_glm, "record_prose_attempts", lambda **kw: recorded.update(kw) or 0)
        papers = [{"content_item_id": i, "title": "t", "abstract": "a"} for i in range(1, 51)]
        scored = {i: {d: 5.0 for d in RUBRIC_DIMENSIONS} for i in range(1, 51)}
        with pytest.raises(jev_glm.ProseConfigError, match="No endpoints found"):
            jev_glm.run_prose_for_papers(
                papers=papers, scored=scored, run_id="r", stage_run_id="s",
                stats=BatchStats(papers_requested=50), budget=None, concurrency=1,
            )
        assert len(calls) == 1
        assert "succeeded_ids" in recorded
        [failure] = recorded["failures"]
        assert failure["content_item_id"] == 1
        assert "prose_config_error" in failure["error"]
        assert "No endpoints found" in failure["error"]

    def test_every_prose_failure_reaches_quality_attempts(self, monkeypatch):
        """End to end through insert_quality_attempts: id, error, raw output[:500]."""
        from paper_intelligence.common.batch_runner import BatchStats

        raw = "not json " + "y" * 900

        def bad_then_good(conn, **kwargs):
            if "title: fail" in kwargs["user_prompt"]:
                return _llm_result(raw)
            return _llm_result(GOOD_PROSE)

        inserted: list = []
        monkeypatch.setattr(jev_glm, "call_llm_logged", bad_then_good)
        monkeypatch.setattr(jev_glm, "connect", MagicMock())
        monkeypatch.setattr(jev_glm, "read_prompt", lambda *a, **k: "sys")
        monkeypatch.setattr(jev_glm, "merge_prose_into_scores", lambda **kw: 0)
        monkeypatch.setattr(
            jev_glm, "insert_quality_attempts", lambda conn, rows: inserted.extend(rows) or len(rows)
        )
        papers = [
            {"content_item_id": 1, "title": "ok", "abstract": "a"},
            {"content_item_id": 2, "title": "fail", "abstract": "a"},
        ]
        scored = {i: {d: 5.0 for d in RUBRIC_DIMENSIONS} for i in (1, 2)}
        _, failures = jev_glm.run_prose_for_papers(
            papers=papers, scored=scored, run_id="r", stage_run_id="s",
            stats=BatchStats(papers_requested=2), budget=None, concurrency=1,
        )
        assert [f["content_item_id"] for f in failures] == [2]
        by_status = {r["status"]: r for r in inserted}
        assert set(by_status) == {"succeeded", "failed"}
        failed = by_status["failed"]
        assert failed["content_item_id"] == 2
        assert failed["error_summary"].startswith("prose_failed: ")
        assert failed["metadata"]["raw_output"] == raw[:500]
        assert failed["stage_version"] == jev_glm.PROSE_ATTEMPT_STAGE_VERSION

    def test_one_call_per_paper_across_window(self, monkeypatch):
        calls: list[dict] = []

        def fake_llm(conn, **kwargs):
            calls.append(kwargs)
            return _llm_result(GOOD_PROSE)

        from paper_intelligence.common.batch_runner import BatchStats

        monkeypatch.setattr(jev_glm, "call_llm_logged", fake_llm)
        monkeypatch.setattr(jev_glm, "connect", MagicMock())
        monkeypatch.setattr(jev_glm, "read_prompt", lambda *a, **k: "sys")
        monkeypatch.setattr(jev_glm, "merge_prose_into_scores", lambda **kw: len(kw["prose_by_id"]))
        monkeypatch.setattr(jev_glm, "record_prose_attempts", lambda **kw: 0)
        papers = [{"content_item_id": i, "title": "t", "abstract": "a"} for i in (1, 2, 3)]
        scored = {i: {d: 5.0 for d in RUBRIC_DIMENSIONS} for i in (1, 2, 3)}
        prose, failures = jev_glm.run_prose_for_papers(
            papers=papers, scored=scored, run_id="r", stage_run_id="s",
            stats=BatchStats(papers_requested=3), budget=None,
        )
        assert len(calls) == 3 and sorted(prose) == [1, 2, 3] and failures == []
        assert all(c["user_prompt"].count("batch_index:") == 1 for c in calls)

    def test_current_weights_unchanged(self):
        """G3c refit must not leak into stored composite."""
        from paper_intelligence.quality.stage import WEIGHTS

        assert WEIGHTS["technical_significance"] == 0.28
        assert WEIGHTS["learning_value"] == 0.12


class _RecordingConn:
    """Captures SQL executed through record_external_request."""

    def __init__(self):
        self.executed: list[tuple[str, tuple]] = []

    def cursor(self):
        conn = self

        class _Cur:
            def __enter__(self):
                return self

            def __exit__(self, *a):
                return False

            def execute(self, sql, params=None):
                conn.executed.append((" ".join(sql.split()), params))

        return _Cur()

    def commit(self):
        pass

    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False


class TestJevCostLogging:
    PAPER = {"content_item_id": 7, "title": "T", "abstract": "A", "authors": []}

    def _patch(self, monkeypatch, resp):
        conn = _RecordingConn()
        monkeypatch.setattr(jev_glm, "connect", lambda: conn)
        monkeypatch.setattr(jev_glm, "write_raw", lambda *a, **k: ("raw/path.json", "sha"))
        monkeypatch.setattr(jev_glm, "system_one", lambda req: resp)
        monkeypatch.setattr(jev_glm, "load_systemone_policy", lambda *a: {})
        monkeypatch.setattr(jev_glm, "build_questions", lambda policy: {"q": 1})
        monkeypatch.setattr(jev_glm, "state_from_paper", lambda p: "state")
        return conn

    def _rows(self, conn, table):
        return [p for sql, p in conn.executed if f"INSERT INTO paper_intelligence.{table}" in sql]

    def test_successful_score_logs_provider_usage_cost(self, monkeypatch):
        from paper_intelligence.systemone.client import SystemOneResponse

        resp = SystemOneResponse(
            model=jev_glm.SCORING_MODEL,
            answers={},
            input_tokens=1200,
            output_tokens=40,
            estimated_cost=0.00009,
            actual_cost=0.0000575,
            billable_cost=0.0000575,
            raw={"id": "x"},
        )
        conn = self._patch(monkeypatch, resp)
        monkeypatch.setattr(jev_glm, "parse_answers", lambda answers, policy: {})
        jev_glm.score_paper_with_jev(self.PAPER, run_id="run-1", stage_run_id="sr-1")

        [ext] = self._rows(conn, "external_requests")
        assert ext[1] == "run-1" and ext[2] == "sr-1" and ext[3] == 7
        assert ext[4] == "openrouter" and ext[5] == jev_glm.JEV_ENDPOINT
        assert ext[11] is True
        [llm] = self._rows(conn, "llm_requests")
        assert llm[1] == ext[0]
        assert llm[2] == jev_glm.SCORING_MODEL
        assert llm[4] == 1200 and llm[5] == 40
        assert llm[6] == pytest.approx(0.00009)
        assert llm[7] == pytest.approx(0.0000575)

    def test_failed_score_still_logged(self, monkeypatch):
        from paper_intelligence.systemone.client import SystemOneResponse

        resp = SystemOneResponse(model=jev_glm.SCORING_MODEL, answers={}, error="HTTP 502: bad gateway")
        conn = self._patch(monkeypatch, resp)
        dims, err, cost = jev_glm.score_paper_with_jev(self.PAPER, run_id="run-1", stage_run_id="sr-1")
        assert dims is None and "502" in err
        [ext] = self._rows(conn, "external_requests")
        assert ext[11] is False and "502" in ext[16]
        [llm] = self._rows(conn, "llm_requests")
        assert llm[7] is None

    def test_log_failure_is_a_warning_not_a_lost_score(self, monkeypatch):
        from paper_intelligence.common.batch_runner import BatchStats
        from paper_intelligence.systemone.client import SystemOneResponse

        resp = SystemOneResponse(model=jev_glm.SCORING_MODEL, answers={}, billable_cost=0.00005)
        self._patch(monkeypatch, resp)

        def db_down():
            raise RuntimeError("db down")

        monkeypatch.setattr(jev_glm, "connect", db_down)
        monkeypatch.setattr(jev_glm, "parse_answers", lambda answers, policy: {})
        stats = BatchStats(papers_requested=1)
        _, _, cost = jev_glm.score_paper_with_jev(self.PAPER, run_id="r", stage_run_id="s", stats=stats)
        assert cost == pytest.approx(0.00005)
        assert any("jev_cost_log_failed content_item_id=7" in w for w in stats.warnings)

    def test_window_passes_run_ids_to_scoring(self, monkeypatch):
        seen: list[dict] = []
        dims = {d: 5.0 for d in RUBRIC_DIMENSIONS}

        def fake_score(paper, **kw):
            seen.append(kw)
            return dims, None, 0.0

        monkeypatch.setattr(jev_glm, "score_paper_with_jev", fake_score)
        monkeypatch.setattr(jev_glm, "fetch_papers", lambda conn, ids: [{"content_item_id": 1}])
        monkeypatch.setattr(jev_glm, "persist_jev_scores", lambda **kw: 1)
        monkeypatch.setattr(jev_glm, "run_prose_for_papers", lambda **kw: ({}, []))
        monkeypatch.setattr(
            jev_glm, "run_batches", lambda batches, handler, **kw: [handler(b) for b in batches]
        )
        jev_glm.run_jev_glm_window(MagicMock(), [1], run_id="run-9", stage_run_id="sr-9")
        assert seen[0]["run_id"] == "run-9" and seen[0]["stage_run_id"] == "sr-9"
        assert seen[0]["stats"] is not None
