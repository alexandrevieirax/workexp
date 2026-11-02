"""Task weights within an occupation (methodology §6). Scales are normalized separately; never summed raw."""

from __future__ import annotations

from dataclasses import dataclass, field

from observatory.normalization.scales import ScaleRegistry, expected_frequency


@dataclass
class TaskWeightInput:
    key: int | str
    importance: float | None = None
    importance_suppressed: bool = False
    importance_n: int | None = None
    relevance: float | None = None
    relevance_suppressed: bool = False
    frequency_distribution: dict[str, float] | None = None
    frequency_suppressed: bool = False


@dataclass
class TaskWeight:
    key: int | str
    importance_norm: float | None
    relevance_norm: float | None
    frequency_norm: float | None
    exponents: dict[str, float]
    weight_raw: float
    weight: float = 0.0
    method: str = "onet_alpha_beta_gamma"
    missing: list[str] = field(default_factory=list)


def compute_task_weights(
    tasks: list[TaskWeightInput],
    scales: ScaleRegistry,
    alpha: float,
    beta: float,
    gamma: float,
    importance_scale: str = "IM",
    relevance_scale: str = "RT",
    frequency_categories: int = 7,
    treat_suppressed_as_missing: bool = True,
) -> list[TaskWeight]:
    out: list[TaskWeight] = []
    for t in tasks:
        missing: list[str] = []
        imp = rel = freq = None
        if t.importance is not None and not (treat_suppressed_as_missing and t.importance_suppressed):
            imp = scales.normalize(importance_scale, t.importance)
        else:
            missing.append("importance_suppressed" if t.importance_suppressed else "importance_missing")
        if t.relevance is not None and not (treat_suppressed_as_missing and t.relevance_suppressed):
            rel = scales.normalize(relevance_scale, t.relevance)
        else:
            missing.append("relevance_suppressed" if t.relevance_suppressed else "relevance_missing")
        if t.frequency_distribution and not (treat_suppressed_as_missing and t.frequency_suppressed):
            freq = expected_frequency(t.frequency_distribution, frequency_categories)
        else:
            missing.append("frequency_suppressed" if t.frequency_suppressed else "frequency_missing")

        terms = {"importance": (imp, alpha), "relevance": (rel, beta), "frequency": (freq, gamma)}
        present = {k: e for k, (v, e) in terms.items() if v is not None}
        if not present:
            out.append(TaskWeight(t.key, None, None, None, {}, 1.0, method="uniform_fallback", missing=missing))
            continue
        total = sum(present.values())
        exps = {k: e / total for k, e in present.items()}  # proportional redistribution of missing exponents
        raw = 1.0
        for k, e in exps.items():
            raw *= terms[k][0] ** e
        out.append(
            TaskWeight(
                t.key,
                imp,
                rel,
                freq,
                exps,
                raw,
                method="onet_alpha_beta_gamma" if not missing else "onet_redistributed",
                missing=missing,
            )
        )

    if any(w.method == "uniform_fallback" for w in out) and not all(w.method == "uniform_fallback" for w in out):
        # Mixing a uniform fallback with rated tasks would give unrated tasks the maximum weight.
        rated_mean = sum(w.weight_raw for w in out if w.method != "uniform_fallback") / max(
            1, sum(1 for w in out if w.method != "uniform_fallback")
        )
        for w in out:
            if w.method == "uniform_fallback":
                w.weight_raw = rated_mean
                w.missing.append("weight_set_to_rated_mean")
    total = sum(w.weight_raw for w in out)
    for w in out:
        w.weight = w.weight_raw / total if total > 0 else 1.0 / len(out)
    return out


def uniform_weights(keys: list[int | str], method: str = "uniform_unweighted_source") -> list[TaskWeight]:
    n = len(keys)
    return [
        TaskWeight(k, None, None, None, {}, 1.0, 1.0 / n, method=method, missing=["no_ratings_in_source"]) for k in keys
    ]
