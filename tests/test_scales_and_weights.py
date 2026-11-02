from __future__ import annotations

import pytest

from observatory.exposure.weights import TaskWeightInput, compute_task_weights, uniform_weights
from observatory.normalization.scales import Scale, ScaleMismatchError, ScaleRegistry, expected_frequency

REG = ScaleRegistry(
    {
        "IM": Scale("IM", "Importance", 1, 5),
        "RT": Scale("RT", "Relevance", 0, 100),
        "CX": Scale("CX", "Context", 1, 5),
        "CT": Scale("CT", "Context", 1, 3),
    }
)


def test_each_scale_normalized_by_its_own_range():
    assert REG.normalize("IM", 3) == 0.5
    assert REG.normalize("RT", 50) == 0.5
    assert REG.normalize("CT", 2) == 0.5
    assert REG.normalize("CX", 2) == 0.25


def test_mixing_unknown_or_wrong_scale_is_refused():
    with pytest.raises(ScaleMismatchError):
        REG.normalize("FT", 3)
    with pytest.raises(ValueError):
        REG.normalize("CT", 5)  # a CX value passed as CT is out of range → refused, not silently mixed


def test_expected_frequency():
    assert expected_frequency({"1": 100}) == 0.0
    assert expected_frequency({"7": 100}) == 1.0
    assert expected_frequency({"3": 50, "5": 50}) == pytest.approx(0.5)


def _w(**kw):
    return TaskWeightInput(key=kw.pop("key", "t"), **kw)


def test_weights_sum_to_one_and_follow_formula():
    tasks = [
        _w(key="a", importance=5, relevance=100, frequency_distribution={"7": 100}),
        _w(key="b", importance=3, relevance=50, frequency_distribution={"4": 100}),
    ]
    ws = compute_task_weights(tasks, REG, 0.5, 0.3, 0.2)
    assert sum(w.weight for w in ws) == pytest.approx(1.0)
    assert ws[0].weight_raw == pytest.approx(1.0)
    assert ws[1].weight_raw == pytest.approx(0.5**0.5 * 0.5**0.3 * 0.5**0.2)


def test_missing_frequency_redistributes_exponents_and_is_flagged():
    ws = compute_task_weights([_w(importance=3, relevance=50)], REG, 0.5, 0.3, 0.2)
    w = ws[0]
    assert "frequency_missing" in w.missing and w.method == "onet_redistributed"
    assert w.exponents == {"importance": pytest.approx(0.5 / 0.8), "relevance": pytest.approx(0.3 / 0.8)}
    assert w.weight_raw == pytest.approx(0.5 ** (0.5 / 0.8) * 0.5 ** (0.3 / 0.8))


def test_suppressed_values_are_treated_as_missing():
    ws = compute_task_weights(
        [_w(importance=3, relevance=50, frequency_distribution={"4": 100}, frequency_suppressed=True)],
        REG,
        0.5,
        0.3,
        0.2,
    )
    assert "frequency_suppressed" in ws[0].missing and ws[0].frequency_norm is None


def test_all_missing_uses_uniform_and_mixed_uses_rated_mean():
    ws = compute_task_weights([_w(key="a"), _w(key="b")], REG, 0.5, 0.3, 0.2)
    assert [w.weight for w in ws] == [0.5, 0.5] and ws[0].method == "uniform_fallback"
    mixed = compute_task_weights([_w(key="a", importance=5, relevance=100), _w(key="b")], REG, 0.5, 0.3, 0.2)
    assert mixed[1].weight_raw == pytest.approx(mixed[0].weight_raw)
    assert "weight_set_to_rated_mean" in mixed[1].missing


def test_uniform_weights_for_unrated_sources():
    ws = uniform_weights(["a", "b", "c", "d"])
    assert all(w.weight == 0.25 and w.method == "uniform_unweighted_source" for w in ws)
