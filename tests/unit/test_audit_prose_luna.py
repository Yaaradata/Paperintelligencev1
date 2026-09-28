"""audit_prose_luna.py: v002 judges so_what and reason_not_higher separately."""

from __future__ import annotations

import importlib.util
import json
from pathlib import Path

SCRIPT = Path(__file__).resolve().parents[2] / "scripts" / "audit_prose_luna.py"


def _load():
    spec = importlib.util.spec_from_file_location("audit_prose_luna", SCRIPT)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


PAPER = {
    "title": "T",
    "abstract": "A",
    "result_json": {"so_what": "S", "reason_not_higher": "R", "technical_significance": 6},
}


def test_v002_prompt_omits_scores_v001_keeps_them():
    mod = _load()
    assert "Scores:" not in mod.user_prompt([PAPER], "v002")
    assert "so_what: S" in mod.user_prompt([PAPER], "v002")
    assert "Scores: technical_significance=6" in mod.user_prompt([PAPER], "v001")


def test_v002_parse_splits_fields_and_keeps_phrase_only_when_flagged():
    mod = _load()
    content = json.dumps({"results": [
        {"i": 1, "so_what_unsupported": "Yes", "so_what_unsupported_phrase": "cuts cost",
         "reason_not_higher_unsupported": "no"},
        {"i": 2, "so_what_unsupported": "no", "so_what_unsupported_phrase": "stray",
         "reason_not_higher_unsupported": "yes"},
        {"i": 3, "so_what_unsupported": "maybe", "reason_not_higher_unsupported": "no"},
    ]})
    out = mod.parse_results(content, 3, "v002")
    assert out[1] == {"so_what_unsupported": "yes", "reason_not_higher_unsupported": "no",
                      "so_what_unsupported_phrase": "cuts cost"}
    assert out[2]["so_what_unsupported_phrase"] == ""
    assert out[2]["reason_not_higher_unsupported"] == "yes"
    assert 3 not in out


def test_v001_parse_unchanged():
    mod = _load()
    content = json.dumps({"results": [{"i": 1, "so_what_specific": "yes", "unsupported_claim": "no",
                                       "contradicts_scores": "no", "reason_not_higher": "real"}]})
    assert mod.parse_results(content, 1)[1]["unsupported_claim"] == "no"
    assert mod.parse_results(content, 1, "v002") == {}


def test_v002_gets_room_for_reasoning():
    mod = _load()
    assert mod.MAX_TOKENS_BY_VERSION["v002"] > mod.MAX_TOKENS_BY_VERSION["v001"]
