"""Top-N candidate search for a source occupation (ESCO/CBO) among all O*NET occupations.

Candidates = official ESCO→O*NET-SOC targets (when available) ∪ the k O*NET occupations whose "title. description"
is closest to the source titles. Each candidate is scored with the full composite ``propose``; the result is
ranked and flagged as ambiguous when the runner-up is within ``ambiguity_margin`` of the best.
"""

from __future__ import annotations

import random
from dataclasses import dataclass, field

import numpy as np

from observatory.connectors.onet import JOB_ZONE_TO_LEVEL, OnetArchive
from observatory.crosswalk.engine import CrosswalkProposal, CrosswalkSide, OfficialCodeCrosswalk, propose
from observatory.embeddings.providers import Embedder
from observatory.exposure.dimensions import Calibration


@dataclass
class CandidateSearch:
    source: str
    ranked: list[CrosswalkProposal]
    ambiguous: bool
    margin: float | None
    candidate_origin: dict[str, str] = field(default_factory=dict)
    ambiguity_margin: float = 0.0

    @property
    def best(self) -> CrosswalkProposal | None:
        return self.ranked[0] if self.ranked else None

    def tied(self) -> list[CrosswalkProposal]:
        """Candidates within the ambiguity margin of the best one (the best included)."""
        if not self.ranked:
            return []
        top = self.ranked[0].mapping_confidence
        return [p for p in self.ranked if top - p.mapping_confidence < self.ambiguity_margin]

    def to_dict(self) -> dict:
        return {
            "source": self.source,
            "ambiguous": self.ambiguous,
            "margin": self.margin,
            "tied": [p.target for p in self.tied()] if self.ambiguous else [],
            "candidates": [
                {
                    "target": p.target,
                    "origin": self.candidate_origin.get(p.target),
                    "mapping_confidence": p.mapping_confidence,
                    "confidence_class": p.confidence_class,
                    "title": p.title_similarity,
                    "tasks": p.task_similarity,
                    "skills": p.skill_similarity,
                    "hierarchy": p.hierarchy_consistency,
                    "qualification": p.qualification_consistency,
                }
                for p in self.ranked
            ],
        }


class OnetIndex:
    """Cached O*NET sides (titles, tasks, DWAs, job zone) and the title+description matrix for prefiltering."""

    def __init__(self, onet: OnetArchive, embedder: Embedder):
        self.onet = onet
        self.embedder = embedder
        occ = onet.table("Occupation Data.txt")
        task_codes = set(onet.table("Task Statements.txt")["O*NET-SOC Code"])
        occ = occ[occ["O*NET-SOC Code"].isin(task_codes)]  # only occupations with task data can be compared
        self.codes = list(occ["O*NET-SOC Code"])
        self.titles = dict(zip(occ["O*NET-SOC Code"], occ["Title"], strict=True))
        texts = [f"{t}. {d}" for t, d in zip(occ["Title"], occ["Description"], strict=True)]
        self._matrix = embedder.embed(texts, "en", "passage")
        jz = onet.table("Job Zones.txt")
        self.job_zone = {c: int(z) for c, z in zip(jz["O*NET-SOC Code"], jz["Job Zone"], strict=True)}
        self._sides: dict[str, CrosswalkSide] = {}

    def side(self, code: str) -> CrosswalkSide:
        if code not in self._sides:
            o = self.onet.occupation(code)
            tasks = [t.statement for t in self.onet.tasks(code)]
            dwas = sorted({n for lst in self.onet.dwas_for_tasks(code).values() for _, n in lst if n})
            titles = [a for a, lang, kind in o.aliases if kind in ("preferred", "alternative")][:30]
            self._sides[code] = CrosswalkSide(
                f"ONET:{code}",
                "ONET",
                titles,
                "en",
                tasks,
                dwas,
                code[:7],
                JOB_ZONE_TO_LEVEL.get(self.job_zone.get(code, 0)),
                code,
            )
        return self._sides[code]

    def nearest(self, titles: list[str], language: str, k: int) -> list[tuple[str, float]]:
        q = self.embedder.embed(titles, language, "query")
        scores = (q @ self._matrix.T).max(axis=0)
        order = np.argsort(-scores)[:k]
        return [(self.codes[i], float(scores[i])) for i in order]

    def null_sample(self, n: int, seed: int, exclude: set[str]) -> tuple[list[list[str]], list[list[str]]]:
        pool = [c for c in self.codes if c not in exclude]
        sample = random.Random(seed).sample(pool, min(n, len(pool)))
        return [self.side(c).tasks for c in sample], [self.side(c).skills for c in sample]


def search(
    source: CrosswalkSide,
    index: OnetIndex,
    title_cal: Calibration | None,
    cfg: dict,
    official: OfficialCodeCrosswalk | None,
) -> CandidateSearch:
    cc = cfg["crosswalk"]["candidates"]
    origin: dict[str, str] = {}
    if official is not None and source.taxonomy == "ESCO" and official.esco_onet:
        targets, how = official.esco_targets(source.official_code, source.titles[0])
        for c in sorted(targets or []):
            if c in index.titles:
                origin[f"ONET:{c}"] = "official_table"
    for c, _ in index.nearest(source.titles, source.language, cc["embedding_top_k"]):
        origin.setdefault(f"ONET:{c}", "embedding_prefilter")
    codes = [ref.split(":", 1)[1] for ref in origin]
    null_tasks, null_skills = index.null_sample(
        cfg["crosswalk"]["null_sample_size"], cfg["crosswalk"]["null_seed"], set(codes)
    )
    cache: dict = {}
    # pass 1: raw set similarities → best achievable per component; pass 2: components relative to the best
    first = [
        propose(source, index.side(c), index.embedder, title_cal, cfg, official, null_tasks, null_skills, cache)
        for c in codes
    ]
    reference = {
        name: max(p.details["null"][name]["raw"] for p in first if name in p.details["null"])
        for name in ("tasks", "skills")
        if any(name in p.details["null"] for p in first)
    }
    proposals = [
        propose(
            source, index.side(c), index.embedder, title_cal, cfg, official, null_tasks, null_skills, cache, reference
        )
        for c in codes
    ]
    ranked = sorted(proposals, key=lambda p: -p.mapping_confidence)
    margin = round(ranked[0].mapping_confidence - ranked[1].mapping_confidence, 4) if len(ranked) > 1 else None
    ambiguous = margin is not None and margin < cc["ambiguity_margin"]
    return CandidateSearch(source.occupation_ref, ranked, ambiguous, margin, origin, cc["ambiguity_margin"])
