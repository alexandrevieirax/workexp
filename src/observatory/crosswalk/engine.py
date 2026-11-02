"""Composite crosswalk between occupations of different taxonomies (methodology §9).

Never auto-accepts in v0; a title match alone cannot reach the moderate class (title weight is 0.20).
"""

from __future__ import annotations

import csv
from dataclasses import asdict, dataclass, field
from pathlib import Path

import numpy as np

from observatory.embeddings.providers import Embedder
from observatory.exposure.dimensions import Calibration


@dataclass
class CrosswalkSide:
    occupation_ref: str
    taxonomy: str
    titles: list[str]
    language: str
    tasks: list[str]
    skills: list[str]
    group_code: str | None
    qualification_level: float | None


@dataclass
class CrosswalkProposal:
    source: str
    target: str
    title_similarity: float | None
    task_similarity: float | None
    skill_similarity: float | None
    hierarchy_consistency: float | None
    qualification_consistency: float | None
    mapping_confidence: float
    confidence_class: str
    status: str
    rules_applied: list[str] = field(default_factory=list)
    details: dict = field(default_factory=dict)

    def to_dict(self) -> dict:
        return asdict(self)


class OfficialCodeCrosswalk:
    """Official correspondence tables (e.g. BLS ISCO-08↔SOC, CBO↔ISCO tábua de conversão) placed manually.

    CSV columns: from_system, from_code, to_system, to_code, source. Absent file → hierarchy is 'unknown'.
    """

    def __init__(self, pairs: set[tuple[str, str, str, str]] | None = None, sources: list[str] | None = None):
        self.pairs = pairs or set()
        self.sources = sources or []

    @classmethod
    def from_dir(cls, directory: Path) -> OfficialCodeCrosswalk:
        pairs, sources = set(), []
        if directory.exists():
            for p in sorted(directory.glob("*.csv")):
                with open(p, encoding="utf-8") as fh:
                    for r in csv.DictReader(fh):
                        pairs.add((r["from_system"], r["from_code"], r["to_system"], r["to_code"]))
                sources.append(p.name)
        return cls(pairs, sources)

    def systems(self) -> set[tuple[str, str]]:
        return {(a, c) for a, _, c, _ in self.pairs}

    def consistent(self, sys_a: str, code_a: str, sys_b: str, code_b: str) -> float | None:
        if (sys_a, sys_b) in self.systems():
            return 1.0 if (sys_a, code_a, sys_b, code_b) in self.pairs else 0.0
        if (sys_b, sys_a) in self.systems():
            return 1.0 if (sys_b, code_b, sys_a, code_a) in self.pairs else 0.0
        return None


HIERARCHY_SYSTEM = {"ESCO": "ISCO08", "ONET": "SOC2018", "CBO": "CBO2002"}


def _best_match_mean(a: np.ndarray, b: np.ndarray) -> float:
    sims = a @ b.T
    return float((sims.max(axis=1).mean() + sims.max(axis=0).mean()) / 2)


def classify(conf: float, classes: list[dict]) -> str:
    for c in sorted(classes, key=lambda c: -c["min"]):
        if conf >= c["min"]:
            return c["label"]
    return classes[-1]["label"]


def propose(
    a: CrosswalkSide,
    b: CrosswalkSide,
    embedder: Embedder,
    title_cal: Calibration | None,
    cfg: dict,
    official: OfficialCodeCrosswalk | None = None,
    null_tasks: list[list[str]] | None = None,
    null_skills: list[list[str]] | None = None,
) -> CrosswalkProposal:
    """Set similarities are rescaled against an empirical null: the same source compared with randomly sampled
    occupations of the target taxonomy. 0 = no more similar than a random occupation, 1 = identical sets.
    Without a null sample the component is unknown (a sentence-level calibration saturates at 1.0)."""
    cw = cfg["crosswalk"]
    rules: list[str] = []
    unknown = cw["unknown_component_value"]

    ta = embedder.embed(a.titles, a.language, kind="query")
    tb = embedder.embed(b.titles, b.language, kind="query")
    raw_title = float((ta @ tb.T).max())
    title = float(title_cal.apply(np.array([raw_title]))[0]) if title_cal else raw_title
    rules.append("title: max cosine over preferred/alternative labels" + (", pair-calibrated" if title_cal else ""))

    null_stats: dict[str, dict] = {}

    def set_sim(xa: list[str], xb: list[str], name: str, nulls: list[list[str]] | None) -> float | None:
        if not xa or not xb:
            rules.append(f"{name}: unavailable on one side → component unknown")
            return None
        ea = embedder.embed(xa, a.language, "query")
        raw = _best_match_mean(ea, embedder.embed(xb, b.language, "query"))
        nulls = [n for n in (nulls or []) if n]
        if len(nulls) >= 5:
            null = [_best_match_mean(ea, embedder.embed(n, b.language, "query")) for n in nulls]
            mu = float(np.mean(null))
            null_stats[name] = {
                "raw": round(raw, 4),
                "null_mean": round(mu, 4),
                "null_max": round(max(null), 4),
                "n_null": len(null),
                "raw_rank_vs_null": round(float(np.mean([raw > x for x in null])), 4),
            }
            rules.append(
                f"{name}: bidirectional best-match mean rescaled vs empirical null "
                f"(n={len(null)}): (s - mean_null) / (1 - mean_null)"
            )
            return float(np.clip((raw - mu) / (1 - mu), 0, 1)) if mu < 1 else 0.0
        null_stats[name] = {"raw": round(raw, 4), "n_null": len(nulls)}
        rules.append(f"{name}: fewer than 5 null occupations → component unknown (raw {raw:.3f} recorded)")
        return None

    task = set_sim(a.tasks, b.tasks, "tasks", null_tasks)
    skill = set_sim(a.skills, b.skills, "skills", null_skills)

    hier = None
    if official and a.group_code and b.group_code:
        hier = official.consistent(
            HIERARCHY_SYSTEM[a.taxonomy], a.group_code, HIERARCHY_SYSTEM[b.taxonomy], b.group_code
        )
    if hier is None:
        rules.append("hierarchy: no official correspondence table loaded → unknown")
    else:
        rules.append(f"hierarchy: official table ({', '.join(official.sources)})")  # type: ignore[union-attr]

    qual = None
    if a.qualification_level is not None and b.qualification_level is not None:
        qual = 1 - abs(a.qualification_level - b.qualification_level)
        rules.append("qualification: 1 - |level_a - level_b| on harmonized ISCO skill-level scale")
    else:
        rules.append("qualification: level missing → unknown")

    comps = {
        "title_similarity": title,
        "task_similarity": task,
        "skill_similarity": skill,
        "hierarchy_consistency": hier,
        "qualification_consistency": qual,
    }
    conf = sum(cw["weights"][k] * (v if v is not None else unknown) for k, v in comps.items())
    unknown_keys = [k for k, v in comps.items() if v is None]
    if unknown_keys:
        rules.append(f"unknown components set to {unknown}: {unknown_keys}")
    klass = classify(conf, cw["classes"])
    return CrosswalkProposal(
        source=a.occupation_ref,
        target=b.occupation_ref,
        mapping_confidence=round(conf, 4),
        confidence_class=klass,
        status="proposed",
        rules_applied=rules,
        details={
            "raw_title_cosine": round(raw_title, 4),
            "unknown_components": unknown_keys,
            "null": null_stats,
            "languages": [a.language, b.language],
            "auto_accept": cw["auto_accept"],
        },
        **{k: (round(v, 4) if v is not None else None) for k, v in comps.items()},
    )


def calibrate_pairs(embedder: Embedder, items: list[dict], benchmark_version: str) -> Calibration:
    pos, neg = [], []
    for it in items:
        left = embedder.embed([it["left"]], it["left_lang"], "query")[0]
        right = embedder.embed([it["right"]], it["right_lang"], "query")[0]
        s = float(left @ right)
        (pos if it["label"] == 2 else neg if it["label"] == 0 else []).append(s)
    floor, ceiling = float(np.max(neg)), float(np.median(pos))
    if ceiling <= floor:
        floor = float(np.mean(neg))
    if ceiling <= floor:
        raise ValueError("embedding model cannot separate equivalent/non-equivalent occupation pairs")
    return Calibration(
        embedder.provider.model_key,
        floor,
        ceiling,
        benchmark_version,
        len(pos),
        len(neg),
        method="floor=max(non-equivalent) [fallback mean], ceiling=median(equivalent)",
    )
