from __future__ import annotations

import pytest

from observatory.exposure import formulas as F
from observatory.methodology import load_methodology

CFG = load_methodology().config


def dims(**kw):
    base = {
        "E1": 0.8,
        "E2": 0.8,
        "E3": 0.8,
        "E6": 0.5,
        "E7": 0.2,
        "E8": 0.1,
        "E9": 0.2,
        "E10": 0.5,
        "E11": 0.8,
        "E12": 0.8,
        "E13": 0.5,
        "standardization": 0.6,
        "complementarity": 0.7,
    }
    return base | kw


def test_outputs_are_bounded():
    o = F.task_outputs(dims(), CFG)
    for v in (o.technical_exposure, o.automation_potential, o.augmentation_potential, o.transformation_potential):
        assert 0 <= v <= 1


def test_technical_exposure_formula():
    w = CFG["technical_exposure"]["weights"]
    o = F.task_outputs(dims(E1=1.0, E2=0.5, E3=0.0, E11=0.5), CFG)
    expected = w["semantic_match"] * 1 + w["technical_capability"] * 0.5 + w["technology_maturity"] * 0.5
    assert o.technical_exposure == pytest.approx(expected)


def test_physical_presence_blocks_automation_not_exposure():
    o = F.task_outputs(dims(E8=1.0), CFG)
    assert o.automation_potential == 0 and o.technical_exposure > 0


def test_missing_observed_usage_redistributes_weight_and_is_reported():
    o = F.task_outputs(dims(E3=None, E1=1, E2=1, E11=1), CFG)
    assert o.technical_exposure == pytest.approx(1.0)
    assert o.missing_terms == ["observed_usage"]


def test_augmentation_requires_judgment():
    assert F.task_outputs(dims(E6=0.0), CFG).augmentation_potential == 0


def test_classification_rules():
    c = CFG["classification"]
    hi_unc = F.task_outputs(dims(), CFG)
    assert F.classify_task(hi_unc, 0.6, c["insufficient_evidence_uncertainty"], CFG) == "insufficient_evidence"
    low = F.task_outputs(dims(E1=0, E2=0, E3=0, E11=0), CFG)
    assert F.classify_task(low, 0.6, 0.1, CFG) == "low_applicability"
    auto = F.task_outputs(dims(E1=1, E2=1, E3=1, E11=1, E7=0, E8=0, E9=0, standardization=1.0), CFG)
    assert F.classify_task(auto, 1.0, 0.1, CFG) == "structured_automation"
    assert set(F.TASK_CLASSES) >= {
        "augmentation",
        "partial_automation",
        "supervised_automation",
        "significant_transformation",
        "point_support",
    }


def test_beta_noise_is_mean_preserving_and_bounded():
    import numpy as np

    from observatory.exposure.engine import beta_noise

    rng = np.random.default_rng(0)
    for m in (0.0, 0.02, 0.5, 0.97, 1.0):
        xs = [beta_noise(rng, m, 0.2) for _ in range(4000)]
        assert all(0 <= x <= 1 for x in xs)
        assert abs(np.mean(xs) - m) < 0.02


def test_uncertainty_score_bounds():
    assert F.uncertainty_score({}, CFG) == 0
    full = {k: 1.0 for k in CFG["uncertainty"]["weights"]}
    assert F.uncertainty_score(full, CFG) == pytest.approx(1.0)


def test_occupational_indices_are_weighted_sums():
    outs = [F.task_outputs(dims(E1=1, E2=1, E3=1, E11=1), CFG), F.task_outputs(dims(E1=0, E2=0, E3=0, E11=0), CFG)]
    idx = F.occupational_indices([0.25, 0.75], outs)
    assert idx["OAE"] == pytest.approx(0.25 * outs[0].technical_exposure)


def test_engine_on_synthetic_slice_is_reproducible(slice_run):
    _, report = slice_run
    onet = report.occupations["ONET"]
    for occ in (report.occupations[t] for t in ("ONET", "ESCO", "CBO")):
        for k in ("OAE", "OAP", "OAuP", "OTP"):
            lo, hi = occ["intervals"][k]
            assert 0 <= lo <= hi <= 1
            # regression: clipped Gaussian noise pushed the point estimate outside its own interval
            assert lo - 1e-3 <= occ["scores"][k] <= hi + 1e-3, (k, occ["scores"][k], lo, hi)
    assert onet["quality"]["task_count"] == 4
    assert onet["quality"]["prior_source"] == "onet_direct"
    assert onet["max_abs_delta_OAE"] >= 0


def test_monte_carlo_is_seeded(synthetic_env):
    from fixtures.synthetic import build
    from observatory.pipeline.vertical_slice import SliceConfig, run

    kw = dict(
        onet_code=build.ONET_CODE,
        onet_version="99.0",
        esco_uri=build.ESCO_URI,
        cbo_code="999901",
        aei_release="release_synthetic",
        offline=True,
        provider="baseline",
    )
    a = run(SliceConfig(**kw))
    b = run(SliceConfig(**kw))
    assert a.occupations["ONET"]["intervals"] == b.occupations["ONET"]["intervals"]
    assert a.occupations["ONET"]["scores"] == b.occupations["ONET"]["scores"]
