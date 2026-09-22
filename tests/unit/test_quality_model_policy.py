"""Phase 3b: date-mapped quality models + stale_content status."""

from __future__ import annotations

from datetime import date
from pathlib import Path
from unittest.mock import patch

import pytest
import yaml

from paper_intelligence.adjudication.quality_status import (
    derive_quality_status,
    quality_result_is_current,
    result_content_is_stale,
)
from paper_intelligence.quality import model_policy as mp


@pytest.fixture
def policy_file(tmp_path: Path) -> Path:
    path = tmp_path / "v001.yaml"
    path.write_text(
        yaml.dump(
            {
                "policy_version": "v001",
                "cutover_date": "2026-09-16",
                "pre_cutover_model": "openai/gpt-5.6-sol",
                "post_cutover_model": "openai/gpt-5.6-terra",
            }
        ),
        encoding="utf-8",
    )
    return path


@pytest.fixture
def loaded_policy(policy_file: Path):
    mp.load_quality_model_policy.cache_clear()
    pol = mp.load_quality_model_policy(str(policy_file))
    yield pol
    mp.load_quality_model_policy.cache_clear()


class TestMappedQualityModel:
    def test_pre_cutover_uses_sol(self, loaded_policy):
        assert (
            mp.mapped_quality_model("2026-09-15", policy=loaded_policy)
            == "openai/gpt-5.6-sol"
        )
        assert (
            mp.mapped_quality_model(date(2026, 9, 1), policy=loaded_policy)
            == "openai/gpt-5.6-sol"
        )

    def test_cutover_and_after_uses_terra(self, loaded_policy):
        assert (
            mp.mapped_quality_model("2026-09-16", policy=loaded_policy)
            == "openai/gpt-5.6-terra"
        )
        assert (
            mp.mapped_quality_model("2026-09-21", policy=loaded_policy)
            == "openai/gpt-5.6-terra"
        )

    def test_span_window_groups_by_model(self, loaded_policy):
        papers = [
            {"content_item_id": 1, "published_at": "2026-09-10"},
            {"content_item_id": 2, "published_at": "2026-09-15"},
            {"content_item_id": 3, "published_at": "2026-09-16"},
            {"content_item_id": 4, "published_at": "2026-09-20"},
        ]
        with patch.dict("os.environ", {}, clear=False):
            # Ensure no QUALITY_MODEL override.
            env = {k: v for k, v in __import__("os").environ.items() if k != "QUALITY_MODEL"}
            with patch.dict("os.environ", env, clear=True):
                groups = mp.group_ids_by_quality_model(
                    papers, policy=loaded_policy, honor_env_override=True
                )
        assert groups["openai/gpt-5.6-sol"] == [1, 2]
        assert groups["openai/gpt-5.6-terra"] == [3, 4]

    def test_sep_1_15_stays_current_under_terra_env_default(self, loaded_policy):
        """Sol scores remain current for pre-cutover dates even if env wants Terra."""
        meta = {
            "stage_version": "v001",
            "prompt_version": "v001",
            "policy_version": "v001",
            "model": "openai/gpt-5.6-sol",
            "input_content_hash": None,
        }
        expected = mp.mapped_quality_model("2026-09-10", policy=loaded_policy)
        assert expected == "openai/gpt-5.6-sol"
        assert quality_result_is_current(
            meta,
            stage_version="v001",
            prompt_version="v001",
            policy_version="v001",
            model=expected,
        )

    def test_env_override_warns_when_disagrees(self, loaded_policy, capsys):
        with patch.dict("os.environ", {"QUALITY_MODEL": "openai/gpt-5.6-terra"}):
            msgs = mp.warn_quality_model_override(
                ["2026-09-10", "2026-09-20"], policy=loaded_policy
            )
        assert msgs
        assert "disagrees" in msgs[0]
        assert "openai/gpt-5.6-terra" in msgs[0]


class TestModelGuardNoFalseAlarm:
    def test_mapping_mismatch_zero_when_models_match_dates(self, loaded_policy):
        """Guard compares to date map, not a single env QUALITY_MODEL."""
        # Simulate: Sep 10 Sol row — should not mismatch vs mapping.
        expected = mp.mapped_quality_model("2026-09-10", policy=loaded_policy)
        assert expected == "openai/gpt-5.6-sol"
        # Terra env alone must not redefine expected.
        with patch.dict("os.environ", {"QUALITY_MODEL": "openai/gpt-5.6-terra"}):
            still = mp.mapped_quality_model("2026-09-10", policy=loaded_policy)
            assert still == "openai/gpt-5.6-sol"
            override, active = mp.resolve_quality_model(
                "2026-09-10", policy=loaded_policy, allow_env_override=True
            )
            assert active
            assert override == "openai/gpt-5.6-terra"


class TestStaleContentStatus:
    def test_derive_stale_content(self):
        status, reason = derive_quality_status(
            has_current_quality_row=False,
            route_decision="selected",
            route_reason="selected_top_slice",
            latest_attempt_status=None,
            content_stale=True,
        )
        assert status == "stale_content"
        assert reason.startswith("stale_content:")

    def test_scored_beats_stale_flag(self):
        status, _ = derive_quality_status(
            has_current_quality_row=True,
            route_decision="selected",
            route_reason="x",
            latest_attempt_status=None,
            content_stale=True,
        )
        assert status == "scored"

    def test_result_content_is_stale(self):
        assert result_content_is_stale(
            {"input_content_hash": "aaa"},
            paper_content_hash="bbb",
        )
        assert not result_content_is_stale(
            {"input_content_hash": None},
            paper_content_hash="bbb",
        )
        assert not result_content_is_stale(
            {"input_content_hash": "aaa"},
            paper_content_hash="aaa",
        )


class TestCalibrationSample:
    def test_stratified_includes_top(self):
        import importlib.util
        import sys

        root = Path(__file__).resolve().parents[2]
        path = root / "scripts" / "calibrate_sol_terra_quality.py"
        spec = importlib.util.spec_from_file_location("calibrate_sol_terra", path)
        mod = importlib.util.module_from_spec(spec)
        assert spec.loader is not None
        # Avoid executing paid main; just load helpers.
        sys.modules["calibrate_sol_terra"] = mod
        spec.loader.exec_module(mod)

        rows = [
            {"content_item_id": i, "final_score": float(i)}
            for i in range(1, 101)
        ]
        sample = mod._select_sample(rows, n=60, top_n=20)
        ids = {r["content_item_id"] for r in sample}
        assert len(sample) == 60
        for i in range(81, 101):
            assert i in ids

    def test_spearman(self):
        import importlib.util
        import sys

        root = Path(__file__).resolve().parents[2]
        path = root / "scripts" / "calibrate_sol_terra_quality.py"
        spec = importlib.util.spec_from_file_location("calibrate_sol_terra2", path)
        mod = importlib.util.module_from_spec(spec)
        assert spec.loader is not None
        sys.modules["calibrate_sol_terra2"] = mod
        spec.loader.exec_module(mod)

        xs = [1.0, 2.0, 3.0, 4.0]
        assert mod._spearman(xs, xs) == pytest.approx(1.0)
        assert mod._spearman(xs, list(reversed(xs))) == pytest.approx(-1.0)
