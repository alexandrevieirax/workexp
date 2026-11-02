"""Exposure engine: task dimensions -> task outputs -> occupational indices, with uncertainty and sensitivity.

The engine is pure (no DB access) so it can be tested in isolation; ``observatory.pipeline`` persists results.
"""

from __future__ import annotations

import copy
from dataclasses import dataclass, field
from typing import Any

import numpy as np

from observatory.capabilities.dictionary import CapabilityDictionary
from observatory.connectors.aei import AeiRelease
from observatory.exposure import formulas as F
from observatory.exposure.dimensions import (
    PRIOR_DIMENSIONS,
    Calibration,
    CapabilityIndex,
    capability_weighted,
    lexical_adjust,
)
from observatory.exposure.weights import TaskWeightInput, compute_task_weights, uniform_weights
from observatory.methodology import Methodology
from observatory.normalization.scales import ScaleRegistry

NOISY_DIMS = ["E1", "E2", "E3", "E6", "E7", "E8", "E9", "E11", "E12", "standardization", "complementarity"]


@dataclass
class TaskInput:
    key: int | str
    statement: str
    language: str
    unit_type: str
    weight_input: TaskWeightInput | None = None
    source_ref: str | None = None


@dataclass
class PriorContext:
    """Occupation-level priors and where they came from (direct O*NET, transferred via crosswalk, default)."""

    priors: dict[str, dict]
    source: str  # onet_direct | crosswalk_transfer | default
    mapping_confidence: float | None = None
    from_occupation: str | None = None


@dataclass
class TaskResult:
    key: int | str
    statement: str
    weight: float
    weight_detail: dict
    dimensions: dict[str, float | None]
    dimension_sources: dict[str, Any]
    outputs: F.TaskOutputs
    task_class: str
    uncertainty: float
    matched: list[dict]
    evidence: list[dict]
    barriers: list[dict]
    missing: list[str]
    justification: str = ""

    @property
    def confidence(self) -> float:
        return 1 - self.uncertainty


@dataclass
class AssessmentResult:
    scores: dict[str, float]
    intervals: dict[str, list[float]]
    quality: dict[str, Any]
    sensitivity: dict[str, Any]
    tasks: list[TaskResult]
    limitations: list[str] = field(default_factory=list)


class ExposureEngine:
    def __init__(
        self,
        methodology: Methodology,
        dictionary: CapabilityDictionary,
        index: CapabilityIndex,
        calibration: Calibration,
        scales: ScaleRegistry | None = None,
        aei: AeiRelease | None = None,
    ):
        self.m = methodology
        self.cfg = methodology.config
        self.dictionary = dictionary
        self.index = index
        self.calibration = calibration
        self.scales = scales
        self.aei = aei

    # ------------------------------------------------------------------ per task
    def _task_dimensions(self, tasks: list[TaskInput], prior_ctx: PriorContext) -> list[dict]:
        cfg = self.cfg
        sm = cfg["semantic_match"]
        rows: list[dict] = []
        by_lang: dict[str, list[int]] = {}
        for i, t in enumerate(tasks):
            by_lang.setdefault(t.language, []).append(i)
        calibrated = np.zeros((len(tasks), len(self.index.cap_ids)))
        raw = np.zeros_like(calibrated)
        neg = np.zeros_like(calibrated)
        for lang, idx in by_lang.items():
            sc = self.index.scores([tasks[i].statement for i in idx], lang, sm["negative_penalty"])
            calibrated[idx] = self.calibration.apply(sc["s"])
            raw[idx] = sc["s_pos"]
            neg[idx] = np.nan_to_num(sc["s_neg"], nan=-1)

        caps = self.dictionary.by_id()
        lex = self.m.lexicon
        delta = cfg["lexical_adjustment"]["delta"]
        default_prior = cfg["occupational_priors"]["default_prior"]
        for i, t in enumerate(tasks):
            order = np.argsort(-calibrated[i])
            top = [j for j in order[: sm["top_k"]] if calibrated[i, j] >= sm["min_calibrated_for_match"]]
            matches = [(self.index.cap_ids[j], float(calibrated[i, j])) for j in top]
            e1 = float(np.mean([calibrated[i, j] for j in order[: sm["top_k"]]]))
            margin = float(calibrated[i, order[0]] - calibrated[i, order[1]]) if len(order) > 1 else 1.0

            d: dict[str, float | None] = {"E1": e1}
            src: dict[str, Any] = {
                "E1": {"method": "embedding_topk_mean", "model": self.calibration.model_key, "top_k": sm["top_k"]}
            }
            for e, prop in (("E2", "technical_capability"), ("E11", "maturity"), ("E12", "data_infrastructure")):
                v = capability_weighted(self.dictionary, matches, prop)
                d[e] = v if v is not None else 0.0
                src[e] = {"method": "capability_prior_weighted", "property": prop, "no_match": v is None}
            comp = capability_weighted(self.dictionary, matches, "augmentation_affinity")
            d["complementarity"] = comp if comp is not None else 0.0
            sup = capability_weighted(self.dictionary, matches, "supervision_need")

            # E3 observed usage
            evidence: list[dict] = []
            usage_missing = 0.0
            if t.unit_type in ("onet_task", "onet_emerging_task") and self.aei is not None:
                ou = self.aei.lookup(t.statement)
                if ou is None:
                    d["E3"] = cfg["observed_usage"]["absent_from_sample_value"]
                    src["E3"] = {"method": "AEI", "status": "absent_from_sample", "release": self.aei.release}
                    usage_missing = cfg["observed_usage"]["absent_from_sample_uncertainty"]
                else:
                    d["E3"] = ou.percentile
                    src["E3"] = {
                        "method": "AEI percentile among observed tasks",
                        "release": self.aei.release,
                        "pct": ou.pct,
                        "match_method": ou.match_method,
                        "match_score": ou.match_score,
                        "matched_text": ou.matched_text,
                    }
                    usage_missing = min(1.0, 2 * (1 - ou.match_score))
                    evidence.append(
                        {
                            "type": "observed_usage",
                            "source": f"AEI {self.aei.release}",
                            "reference": "handa2025which",
                            "pct_of_conversations": round(ou.pct, 5),
                            "automation_pattern_share": _r(ou.automation_share),
                            "augmentation_pattern_share": _r(ou.augmentation_share),
                            "match_method": ou.match_method,
                            "match_score": ou.match_score,
                            "peer_reviewed": False,
                        }
                    )
            else:
                d["E3"] = None
                src["E3"] = {"method": "none", "status": "missing", "reason": "no observed-usage source for unit type"}
                usage_missing = 1.0

            # E6-E10 + standardization: occupational prior adjusted by task lexical cues
            for e, dim in PRIOR_DIMENSIONS.items():
                p = prior_ctx.priors.get(dim, {}).get("value")
                prior_src = prior_ctx.source if p is not None else "default"
                p = default_prior if p is None else p
                v, detail = lexical_adjust(p, t.statement, lex.get(dim, {}), delta)
                d[e] = v
                src[e] = {"method": "occupational_prior+lexical", "prior_source": prior_src, **detail}
            d["E13"] = max(sup if sup is not None else 0.0, d["E9"] or 0.0)
            src["E13"] = {"method": "max(capability.supervision_need, E9)"}

            prior_flag = {
                "onet_direct": 0.0,
                "crosswalk_transfer": 1 - (prior_ctx.mapping_confidence or 0.0),
                # pooled over tied candidates: extra fragility because the exact equivalent is undetermined
                "crosswalk_pooled": min(1.0, 1 - (prior_ctx.mapping_confidence or 0.0) + 0.25),
                "default": 1.0,
            }[prior_ctx.source]
            flags = {
                "observed_usage_missing": usage_missing,
                "prior_not_direct": prior_flag,
                "match_ambiguity": 1.0 if margin < cfg["uncertainty"]["ambiguity_margin"] else 0.0,
                "baseline_embedding_model": 0.0 if self.index.embedder.provider.is_semantic else 1.0,
                "capability_priors_unreviewed": 1.0 if self.dictionary.review_status == "unreviewed" else 0.0,
                "rating_quality": 0.0,
            }
            matched = [
                {
                    "capability_id": c,
                    "name": caps[c].name,
                    "family": caps[c].family,
                    "calibrated_similarity": round(s, 4),
                    "raw_similarity": round(float(raw[i, self.index.cap_ids.index(c)]), 4),
                    "negative_similarity": round(float(neg[i, self.index.cap_ids.index(c)]), 4),
                    "references": caps[c].references,
                }
                for c, s in matches
            ]
            rows.append({"task": t, "d": d, "src": src, "flags": flags, "matched": matched, "evidence": evidence})
        return rows

    def _weights(self, tasks: list[TaskInput], alpha: float, beta: float, gamma: float) -> list:
        tw = self.cfg["task_weights"]
        if all(t.weight_input is not None for t in tasks) and self.scales is not None:
            return compute_task_weights(
                [t.weight_input for t in tasks],
                self.scales,
                alpha,
                beta,
                gamma,  # type: ignore[misc]
                tw["importance_scale"],
                tw["relevance_scale"],
                tw["frequency_categories"],
                tw["treat_suppressed_as_missing"],
            )
        return uniform_weights([t.key for t in tasks], tw["non_onet_method"])

    @staticmethod
    def _outputs(rows: list[dict], cfg: dict) -> list[F.TaskOutputs]:
        return [F.task_outputs(r["d"], cfg) for r in rows]

    # ------------------------------------------------------------------ occupation
    def assess(
        self, tasks: list[TaskInput], prior_ctx: PriorContext, crosswalk_quality: float | None = None
    ) -> AssessmentResult:
        if not tasks:
            raise ValueError("occupation has no tasks; cannot assess")
        cfg = self.cfg
        tw = cfg["task_weights"]
        rows = self._task_dimensions(tasks, prior_ctx)
        weights = self._weights(tasks, tw["alpha"], tw["beta"], tw["gamma"])
        # rating quality flag per task
        min_n = cfg["aggregation"]["source_quality_min_n"]
        for r, w, t in zip(rows, weights, tasks, strict=True):
            wi = t.weight_input
            low_n = wi is not None and wi.importance_n is not None and wi.importance_n < min_n
            r["flags"]["rating_quality"] = 1.0 if (w.missing and w.method != "onet_alpha_beta_gamma") or low_n else 0.0
        outputs = self._outputs(rows, cfg)
        results: list[TaskResult] = []
        for r, w, o in zip(rows, weights, outputs, strict=True):
            unc = F.uncertainty_score(r["flags"], cfg)
            d = dict(r["d"])
            d["E4"], d["E5"], d["E14"] = o.automation_potential, o.augmentation_potential, unc
            klass = F.classify_task(o, d["standardization"], unc, cfg)  # type: ignore[arg-type]
            barriers = [
                {"dimension": e, "name": PRIOR_DIMENSIONS[e], "value": round(d[e], 3)}  # type: ignore[arg-type]
                for e in ("E7", "E8", "E9")
                if (d[e] or 0) >= 0.5
            ]
            if d["E6"] and d["E6"] >= 0.6:
                barriers.append({"dimension": "E6", "name": "human_judgment_requirement", "value": round(d["E6"], 3)})
            missing = list(w.missing) + [f"{m}_missing" for m in o.missing_terms]
            tr = TaskResult(
                r["task"].key,
                r["task"].statement,
                w.weight,
                {
                    "method": w.method,
                    "importance_norm": _r(w.importance_norm),
                    "relevance_norm": _r(w.relevance_norm),
                    "frequency_norm": _r(w.frequency_norm),
                    "exponents": w.exponents,
                    "weight_raw": _r(w.weight_raw),
                },
                d,
                {**r["src"], "uncertainty_flags": r["flags"]},
                o,
                klass,
                unc,
                r["matched"],
                r["evidence"],
                barriers,
                missing,
            )
            tr.justification = justify(tr)
            results.append(tr)

        w_list = [t.weight for t in results]
        scores = F.occupational_indices(w_list, outputs)
        intervals = self._monte_carlo(tasks, rows, results)
        sensitivity = self._sensitivity(tasks, rows)
        coverage = sum(
            t.weight for t in results if t.matched and t.dimension_sources["E6"]["prior_source"] != "default"
        )
        rated = [t for t in results if t.weight_detail["method"] in ("onet_alpha_beta_gamma", "onet_redistributed")]
        quality = {
            "task_count": len(results),
            "task_coverage": round(coverage, 4),
            "observed_usage_coverage": round(sum(t.weight for t in results if t.evidence), 4),
            "source_quality": round(sum(t.weight for t in rated if not t.missing) / max(1e-9, sum(w_list)), 4)
            if rated
            else None,
            "weight_method": results[0].weight_detail["method"]
            if len({t.weight_detail["method"] for t in results}) == 1
            else "mixed",
            "prior_source": prior_ctx.source,
            "prior_from_occupation": prior_ctx.from_occupation,
            "crosswalk_quality": crosswalk_quality,
            "mean_uncertainty": round(float(np.average([t.uncertainty for t in results], weights=w_list)), 4),
            "class_distribution": _class_dist(results),
            "embedding_model_is_semantic": self.index.embedder.provider.is_semantic,
        }
        return AssessmentResult(
            scores={k: round(v, 4) for k, v in scores.items()},
            intervals=intervals,
            quality=quality,
            sensitivity=sensitivity,
            tasks=results,
            limitations=self._limitations(quality, prior_ctx),
        )

    # ------------------------------------------------------------------ uncertainty
    def _monte_carlo(self, tasks: list[TaskInput], rows: list[dict], results: list[TaskResult]) -> dict:
        mc = self.cfg["aggregation"]["monte_carlo"]
        rng = np.random.default_rng(mc["seed"])
        tw = self.cfg["task_weights"]
        te_keys = list(self.cfg["technical_exposure"]["weights"])
        te_w = np.array([self.cfg["technical_exposure"]["weights"][k] for k in te_keys])
        draws = {k: [] for k in ("OAE", "OAP", "OAuP", "OTP")}
        for _ in range(mc["draws"]):
            cfg = copy.deepcopy(self.cfg)
            cfg["technical_exposure"]["weights"] = dict(
                zip(te_keys, rng.dirichlet(te_w * mc["dirichlet_concentration"]), strict=True)
            )
            exps = [
                max(1e-3, e * (1 + rng.normal(0, mc["exponent_sd"]))) for e in (tw["alpha"], tw["beta"], tw["gamma"])
            ]
            weights = [w.weight for w in self._weights(tasks, *exps)]
            outs = []
            for r, res in zip(rows, results, strict=True):
                sd = mc["dimension_noise_base_sd"] + mc["dimension_noise_uncertainty_sd"] * res.uncertainty
                d = dict(r["d"])
                for k in NOISY_DIMS:
                    if d.get(k) is not None:
                        d[k] = beta_noise(rng, d[k], sd)
                outs.append(F.task_outputs(d, cfg))
            for k, v in F.occupational_indices(weights, outs).items():
                draws[k].append(v)
        lo, hi = mc["interval"]
        return {
            k: [round(float(np.percentile(v, lo)), 4), round(float(np.percentile(v, hi)), 4)] for k, v in draws.items()
        } | {"draws": mc["draws"], "seed": mc["seed"], "percentiles": [lo, hi]}

    def _sensitivity(self, tasks: list[TaskInput], rows: list[dict]) -> dict:
        rel = self.cfg["aggregation"]["sensitivity"]["relative_change"]
        tw = self.cfg["task_weights"]
        base_w = [w.weight for w in self._weights(tasks, tw["alpha"], tw["beta"], tw["gamma"])]
        base = F.occupational_indices(base_w, self._outputs(rows, self.cfg))
        out = []

        def run(cfg: dict, weights: list[float]) -> dict[str, float]:
            return F.occupational_indices(weights, self._outputs(rows, cfg))

        for group in ("technical_exposure", "process_redesign"):
            for k in self.cfg[group]["weights"]:
                for sign in (-1, 1):
                    cfg = copy.deepcopy(self.cfg)
                    cfg[group]["weights"][k] *= 1 + sign * rel
                    res = run(cfg, base_w)
                    out.append(
                        {
                            "parameter": f"{group}.{k}",
                            "change": sign * rel,
                            **{f"d_{i}": round(res[i] - base[i], 4) for i in base},
                        }
                    )
        for name in ("alpha", "beta", "gamma"):
            for sign in (-1, 1):
                exps = {e: tw[e] for e in ("alpha", "beta", "gamma")}
                exps[name] *= 1 + sign * rel
                w = [x.weight for x in self._weights(tasks, exps["alpha"], exps["beta"], exps["gamma"])]
                res = run(self.cfg, w)
                out.append(
                    {
                        "parameter": f"task_weights.{name}",
                        "change": sign * rel,
                        **{f"d_{i}": round(res[i] - base[i], 4) for i in base},
                    }
                )
        max_abs = max(abs(r["d_OAE"]) for r in out) if out else 0.0
        return {"relative_change": rel, "one_at_a_time": out, "max_abs_delta_OAE": round(max_abs, 4)}

    def _limitations(self, quality: dict, prior_ctx: PriorContext) -> list[str]:
        lim = [
            "Exposição técnica não equivale a adoção, substituição ou risco de desemprego.",
            "Pesos e fórmulas da metodologia 0.1.0 não estão calibrados (hipóteses iniciais).",
        ]
        if not quality["embedding_model_is_semantic"]:
            lim.append(
                "Modelo de embeddings de linha de base é lexical; correspondências semânticas e entre idiomas "
                "são frágeis."
            )
        if self.dictionary.review_status == "unreviewed":
            lim.append("Priors do dicionário de capacidades de IA não foram revisados por especialistas.")
        if prior_ctx.source == "crosswalk_pooled":
            lim.append(
                f"Priors E6–E10 são a média de ocupações O*NET empatadas no crosswalk ({prior_ctx.from_occupation}); "
                "a equivalência exata depende de revisão humana."
            )
        if prior_ctx.source == "crosswalk_transfer":
            lim.append(
                f"Priors E6–E10 transferidos de {prior_ctx.from_occupation} via crosswalk "
                f"(confiança {prior_ctx.mapping_confidence:.2f})."
            )
        if prior_ctx.source == "default":
            lim.append("Sem descritores ocupacionais: E6–E10 usam prior neutro 0,5 (alta incerteza).")
        if quality["weight_method"].startswith("uniform"):
            lim.append("A fonte não publica importância/frequência das tarefas: pesos uniformes.")
        if quality["observed_usage_coverage"] == 0:
            lim.append("Nenhuma evidência de uso observado para as tarefas desta ocupação.")
        return lim


def beta_noise(rng: np.random.Generator, mean: float, sd: float) -> float:
    """Mean-preserving bounded noise. Clipped Gaussian noise biases values near 0 or 1 inwards (a saturated
    value could only decrease), which pushed point estimates outside their own intervals."""
    var_max = mean * (1 - mean)
    if var_max <= 1e-9:
        return float(mean)
    var = min(sd**2, 0.9 * var_max)
    k = var_max / var - 1
    return float(rng.beta(mean * k, (1 - mean) * k))


def _r(x: float | None) -> float | None:
    return None if x is None else round(float(x), 4)


def _class_dist(results: list[TaskResult]) -> dict[str, float]:
    out: dict[str, float] = {}
    for t in results:
        out[t.task_class] = round(out.get(t.task_class, 0.0) + t.weight, 4)
    return out


def justify(t: TaskResult) -> str:
    caps = (
        ", ".join(f"{m['capability_id']} {m['name']} ({m['calibrated_similarity']:.2f})" for m in t.matched)
        or "nenhuma capacidade acima do limiar"
    )
    usage = t.dimension_sources["E3"]
    usage_txt = {
        "absent_from_sample": "ausente da amostra de uso observado",
        "missing": "sem fonte de uso observado",
    }.get(
        usage.get("status", ""), f"percentil de uso {t.dimensions['E3']:.2f}" if t.dimensions["E3"] is not None else ""
    )
    bars = ", ".join(f"{b['name']}={b['value']:.2f}" for b in t.barriers) or "nenhuma barreira ≥ 0,5"
    return (
        f"Classe '{F.TASK_CLASSES[t.task_class]}'. Capacidades correspondentes: {caps}. Uso observado: {usage_txt}. "
        f"Exposição técnica {t.outputs.technical_exposure:.2f}; automação {t.outputs.automation_potential:.2f}; "
        f"aumento {t.outputs.augmentation_potential:.2f}. Barreiras: {bars}. Incerteza {t.uncertainty:.2f}."
    )
