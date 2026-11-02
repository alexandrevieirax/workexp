"""Pure formulas of methodology v0 (§5, §8). Inputs and outputs are in [0, 1].

Editing this module changes the methodology fingerprint (tests/test_about_consistency.py).
"""

from __future__ import annotations

from dataclasses import dataclass

TASK_CLASSES = {
    "low_applicability": "Baixa aplicabilidade atual da IA",
    "point_support": "Apoio pontual",
    "augmentation": "Aumento de capacidade humana",
    "partial_automation": "Automação parcial",
    "supervised_automation": "Automação elevada sob supervisão",
    "structured_automation": "Potencialmente automatizável em contexto estruturado",
    "significant_transformation": "Transformação significativa da forma de execução",
    "insufficient_evidence": "Evidência insuficiente",
}


def clip01(x: float) -> float:
    return 0.0 if x < 0 else 1.0 if x > 1 else float(x)


def weighted_mean_with_missing(values: dict[str, float | None], weights: dict[str, float]) -> tuple[float, list[str]]:
    """Weights of missing terms are redistributed proportionally; the missing keys are returned."""
    present = {k: w for k, w in weights.items() if values.get(k) is not None}
    missing = [k for k in weights if values.get(k) is None]
    if not present:
        return 0.0, missing
    total = sum(present.values())
    return sum(values[k] * w / total for k, w in present.items()), missing  # type: ignore[operator]


@dataclass
class TaskOutputs:
    technical_exposure: float
    automation_potential: float
    augmentation_potential: float
    transformation_potential: float
    process_redesign: float
    missing_terms: list[str]


def task_outputs(d: dict[str, float | None], cfg: dict) -> TaskOutputs:
    """d holds E1..E13 plus 'standardization' (process standardization) and 'complementarity'."""
    te, missing = weighted_mean_with_missing(
        {
            "semantic_match": d["E1"],
            "technical_capability": d["E2"],
            "observed_usage": d["E3"],
            "technology_maturity": d["E11"],
        },
        cfg["technical_exposure"]["weights"],
    )
    automation = te * (1 - d["E8"]) * (1 - d["E7"]) * (1 - d["E9"]) * d["standardization"]  # type: ignore[operator]
    augmentation = te * d["E6"] * d["complementarity"]  # type: ignore[operator]
    redesign, _ = weighted_mean_with_missing(
        {"data_infrastructure": d["E12"], "technology_maturity": d["E11"]}, cfg["process_redesign"]["weights"]
    )
    transformation = max(automation, augmentation) * redesign
    return TaskOutputs(
        clip01(te), clip01(automation), clip01(augmentation), clip01(transformation), clip01(redesign), missing
    )


def classify_task(out: TaskOutputs, standardization: float, uncertainty: float, cfg: dict) -> str:
    c = cfg["classification"]
    if uncertainty >= c["insufficient_evidence_uncertainty"]:
        return "insufficient_evidence"
    if out.technical_exposure < c["low_applicability_exposure"]:
        return "low_applicability"
    if (
        out.automation_potential >= c["structured_automation"]["automation"]
        and standardization >= c["structured_automation"]["standardization"]
    ):
        return "structured_automation"
    if out.automation_potential >= c["supervised_automation"]:
        return "supervised_automation"
    if out.automation_potential >= c["partial_automation"]:
        return "partial_automation"
    if (
        out.augmentation_potential >= c["transformation"]["augmentation"]
        and out.transformation_potential >= c["transformation"]["transformation"]
    ):
        return "significant_transformation"
    if out.augmentation_potential >= c["augmentation"]:
        return "augmentation"
    # Exposure above the low-applicability floor but no strong automation/augmentation signal.
    return "point_support"


def uncertainty_score(flags: dict[str, float], cfg: dict) -> float:
    """flags: each source of fragility in [0, 1]; combined with the configured weights."""
    w = cfg["uncertainty"]["weights"]
    total = sum(w.values())
    return clip01(sum(w[k] * flags.get(k, 0.0) for k in w) / total)


def occupational_indices(weights: list[float], outputs: list[TaskOutputs]) -> dict[str, float]:
    return {
        "OAE": sum(w * o.technical_exposure for w, o in zip(weights, outputs, strict=True)),
        "OAP": sum(w * o.automation_potential for w, o in zip(weights, outputs, strict=True)),
        "OAuP": sum(w * o.augmentation_potential for w, o in zip(weights, outputs, strict=True)),
        "OTP": sum(w * o.transformation_potential for w, o in zip(weights, outputs, strict=True)),
    }
