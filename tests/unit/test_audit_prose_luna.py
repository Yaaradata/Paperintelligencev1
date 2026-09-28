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


def test_apply_trial_prose_swaps_prose_and_filters_to_trial_papers():
    mod = _load()
    rows = [{"content_item_id": 1, **PAPER}, {"content_item_id": 2, **PAPER}]
    out = mod.apply_trial_prose(rows, {"2": {"so_what": "new", "reason_not_higher": "lim"}})
    assert [r["content_item_id"] for r in out] == [2]
    assert out[0]["result_json"]["so_what"] == "new"
    assert out[0]["result_json"]["technical_significance"] == 6
    assert rows[1]["result_json"]["so_what"] == "S"


def _load_scorer():
    path = SCRIPT.parent / "score_prose_handlabels.py"
    spec = importlib.util.spec_from_file_location("score_prose_handlabels", path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def test_handlabel_scoring_precision_recall_and_weighting():
    mod = _load_scorer()
    judge = {str(i): "yes" for i in range(4)} | {str(i): "no" for i in range(4, 6)}
    human = {"0": "yes", "1": "yes", "2": "yes", "3": "no", "4": "yes", "5": "no"}
    r = mod.score(human, judge, pop_flagged=40, pop_clean=20)
    assert r["confusion"] == {"tp": 3, "fp": 1, "fn": 1, "tn": 1}
    assert r["precision"] == 0.75
    assert r["recall_sample"] == 0.75
    # weighted: tp 3*10=30, fn 1*10=10
    assert r["recall_weighted"] == 0.75
    assert r["disagreement_sample"] == round(2 / 6, 3)
    assert r["luna_unsupported_rate"] == round(40 / 60, 3)


def test_v002_gets_room_for_reasoning():
    mod = _load()
    assert mod.MAX_TOKENS_BY_VERSION["v002"] > mod.MAX_TOKENS_BY_VERSION["v001"]
