from __future__ import annotations

import json

import pytest

from observatory.about.render import references
from observatory.benchmark.metrics import average_precision, load_benchmark, ndcg_at_k, precision_at_k, recall_at_k
from observatory.capabilities.dictionary import find_leakage, load_dictionary
from observatory.config import get_settings


def test_ranking_metrics_known_values():
    ranked = ["a", "b", "c", "d"]
    assert precision_at_k(ranked, {"a", "c"}, 2) == 0.5
    assert recall_at_k(ranked, {"a", "c"}, 3) == 1.0
    assert average_precision(ranked, {"a", "c"}) == pytest.approx((1 + 2 / 3) / 2)
    assert ndcg_at_k(["a", "b"], {"a": 2, "b": 0}, 2) == 1.0
    assert ndcg_at_k(["b", "a"], {"a": 2}, 2) < 1.0


def test_benchmark_is_labeled_as_draft_not_gold():
    meta, items = load_benchmark(get_settings().validation_dir / "benchmark_v0.1.0.jsonl")
    assert meta["version"] == "0.1.0"
    assert items and all(i["annotator"] == "ai_draft" and i["is_gold"] is False for i in items)
    tags = {t for i in items for t in i.get("tags", [])}
    assert {"manual", "cognitive", "hybrid", "regulated", "physical_presence", "high_risk", "false_friend"} <= tags
    assert {i["language"] for i in items if i["item_type"] == "task_capability"} == {"en", "pt"}
    # the evaluated vertical-slice occupation must not be in the calibration set
    assert not any("15-1252" in i.get("source_ref", "") for i in items)


def test_capability_dictionary_structure():
    d = load_dictionary()
    assert set(d.families()) == set("ABCDEFGHIJ")
    refs = references()
    for c in d.capabilities:
        assert c.definition and c.examples and c.limitations and c.risks and c.modality and c.valid_until
        assert set(c.references) <= refs.keys()
    assert d.review_status == "unreviewed"


def test_leakage_detector():
    d = load_dictionary()
    assert find_leakage(d, ["Fix bugs reported by users."]) == [("B.02", "Fix bugs reported by users")]
    assert find_leakage(d, ["Some unrelated statement"]) == []


def test_references_flag_peer_review_and_verification():
    for r in json.loads((get_settings().docs_dir / "references" / "references.json").read_text(encoding="utf-8")):
        assert "peer_reviewed" in r and r.get("verification_status")


def test_curriculum_analysis_is_phase_8():
    pytest.skip("Curriculum analysis engine is scheduled for phase 8; only its schema exists in v0.")


def test_model_comparison_records_rule_and_choice(tmp_path):
    from observatory.benchmark.compare import compare
    from observatory.methodology import load_methodology

    m = load_methodology()
    report = compare(
        ["baseline"], load_dictionary(), get_settings().validation_dir / "benchmark_v0.1.0.jsonl", m.config, tmp_path
    )
    r = report["results"][0]
    assert report["chosen"] == "baseline" and r["eligible"] and r["reproducible"]
    assert 0 <= r["occupation_pairs"]["auc"] <= 1 and r["selection_score"] > 0
    assert "selection_rule" in report and (tmp_path / "comparison.md").exists()
