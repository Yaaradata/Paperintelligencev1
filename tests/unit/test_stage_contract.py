"""Unit tests for Stage contract dataclasses and Protocol shape."""

from __future__ import annotations

from paper_intelligence.common import Evidence, RunContext, StageResult


def test_stage_result_statuses_and_defaults() -> None:
    result = StageResult(status="success")
    assert result.status == "success"
    assert result.data == {}
    assert result.evidence == []
    assert result.metadata == {}


def test_evidence_frozen_fields() -> None:
    ev = Evidence(
        evidence_type="oai_affiliation",
        evidence_source="paper_metadata.affiliation_text",
        evidence_value="MIT CSAIL",
        confidence=0.9,
    )
    assert ev.evidence_type == "oai_affiliation"
    assert ev.metadata == {}


def test_run_context_paid_defaults_safe() -> None:
    ctx = RunContext(run_id="r1", stage_run_id="s1")
    assert ctx.dry_run is False
    assert ctx.allow_paid is False


def test_stage_protocol_structural() -> None:
    class Dummy:
        stage_name = "normalize_authors"
        stage_version = "v001"

        def process(self, content_item_id: int, run_context: RunContext) -> StageResult:
            return StageResult(status="skipped", data={"content_item_id": content_item_id})

    stage = Dummy()
    out = stage.process(42, RunContext(run_id="r", stage_run_id="s"))
    assert out.status == "skipped"
    assert out.data["content_item_id"] == 42
