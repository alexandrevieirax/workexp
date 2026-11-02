"""Composite crosswalk between occupations of different taxonomies (methodology §9).

Never auto-accepts; a title match alone cannot reach the moderate class (title weight is 0.20).
"""

from __future__ import annotations

import csv
import math
from dataclasses import asdict, dataclass, field
from pathlib import Path

import numpy as np

from observatory.embeddings.providers import Embedder
from observatory.exposure.dimensions import Calibration
from observatory.normalization.text import normalize_text


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
    official_code: str | None = None  # ESCO code (e.g. 2512.3) or O*NET-SOC code (e.g. 15-1252.00)


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
    """Official correspondence tables.

    - Canonical CSVs in data/raw/crosswalks/*.csv (from_system, from_code, to_system, to_code, source), e.g. a
      BLS ISCO-08/SOC table or the CBO/CIUO "tábua de conversão" converted with `import-crosswalk`.
    - O*NET's ESCO_to_ONET-SOC.xlsx in data/raw/crosswalks/source/. ESCO codes are renumbered between ESCO
      versions (the API's "software developer" is 2512.3; the table's 2512.3 is "software architect"), so a lookup
      requires code AND title, falling back to a title match within the same ISCO unit group.
    Absent tables → hierarchy is 'unknown'.
    """

    def __init__(
        self,
        pairs: set[tuple[str, str, str, str]] | None = None,
        sources: list[str] | None = None,
        esco_onet: dict[tuple[str, str], set[str]] | None = None,
    ):
        self.pairs = pairs or set()
        self.sources = sources or []
        self.esco_onet = esco_onet or {}  # (esco_code, normalized title) -> O*NET-SOC codes

    @classmethod
    def from_dir(cls, directory: Path) -> OfficialCodeCrosswalk:
        pairs, sources = set(), []
        esco_onet: dict[tuple[str, str], set[str]] = {}
        if directory.exists():
            for p in sorted(directory.glob("*.csv")):
                with open(p, encoding="utf-8") as fh:
                    for r in csv.DictReader(fh):
                        pairs.add((r["from_system"], r["from_code"], r["to_system"], r["to_code"]))
                sources.append(p.name)
            xlsx = directory / "source" / "ESCO_to_ONET-SOC.xlsx"
            if xlsx.exists():
                import pandas as pd

                df = pd.read_excel(xlsx, header=3, dtype=str).dropna(subset=["ESCO/ISCO Code", "O*NET-SOC 2019 Code"])
                for code, title, onet in zip(
                    df["ESCO/ISCO Code"], df["ESCO/ISCO Title"], df["O*NET-SOC 2019 Code"], strict=True
                ):
                    esco_onet.setdefault((code.strip(), normalize_text(str(title))), set()).add(onet.strip())
                sources.append(xlsx.name)
        return cls(pairs, sources, esco_onet)

    def _graph(self) -> dict[tuple[str, str], set[tuple[str, str]]]:
        if not hasattr(self, "_adj"):
            adj: dict[tuple[str, str], set[tuple[str, str]]] = {}
            for sa, ca, sb, cb in self.pairs:  # correspondences are relations: traversable both ways
                adj.setdefault((sa, ca), set()).add((sb, cb))
                adj.setdefault((sb, cb), set()).add((sa, ca))
            self._adj = adj
        return self._adj

    def _system_path(self, sys_a: str, sys_b: str, max_hops: int) -> list[str] | None:
        links: dict[str, set[str]] = {}
        for sa, _, sb, _ in self.pairs:
            links.setdefault(sa, set()).add(sb)
            links.setdefault(sb, set()).add(sa)
        frontier, seen = [[sys_a]], {sys_a}
        while frontier:
            path = frontier.pop(0)
            if path[-1] == sys_b:
                return path
            if len(path) > max_hops:
                continue
            for nxt in sorted(links.get(path[-1], ())):
                if nxt not in seen:
                    seen.add(nxt)
                    frontier.append([*path, nxt])
        return None

    def chain_consistent(
        self, sys_a: str, codes_a: list[str], sys_b: str, codes_b: list[str], max_hops: int = 3
    ) -> tuple[float | None, list[str] | None]:
        """1.0 if official tables link a code of A to a code of B within ``max_hops`` steps, 0.0 if the systems are
        linked but these codes are not, None if no chain of official tables connects the two systems."""
        path = self._system_path(sys_a, sys_b, max_hops)
        if path is None:
            return None, None
        adj = self._graph()
        targets = {(sys_b, c) for c in codes_b if c}
        frontier = {(sys_a, c) for c in codes_a if c}
        seen = set(frontier)
        for _ in range(max_hops):
            if frontier & targets:
                return 1.0, path
            nxt = {n for node in frontier for n in adj.get(node, ()) if n not in seen}
            seen |= nxt
            frontier = nxt
        return (1.0 if frontier & targets else 0.0), path

    def esco_targets(self, esco_code: str | None, title: str) -> tuple[set[str] | None, str]:
        t = normalize_text(title)
        if esco_code and (esco_code, t) in self.esco_onet:
            return self.esco_onet[(esco_code, t)], "esco_code_and_title"
        if esco_code:
            group = esco_code.split(".")[0]
            same = [k for k in self.esco_onet if k[1] == t and k[0].split(".")[0] == group]
            if len(same) == 1:
                return self.esco_onet[same[0]], f"esco_title_within_isco_group (table code {same[0][0]})"
        return None, "no_official_entry"


HIERARCHY_SYSTEM = {"ESCO": "ISCO08", "ONET": "ONETSOC2019", "CBO": "CBO2002"}


def hierarchy_codes(side: CrosswalkSide) -> list[str]:
    """Codes a side can be looked up by in official tables (system given by HIERARCHY_SYSTEM)."""
    if side.taxonomy == "ESCO":
        return [c for c in (side.group_code,) if c]  # ISCO-08 unit group
    if side.taxonomy == "CBO":
        return [c for c in (side.official_code, side.group_code) if c]  # occupation (6 digits) or family (4)
    return [c for c in (side.official_code,) if c]


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
    null_cache: dict | None = None,
    reference_raw: dict[str, float] | None = None,
) -> CrosswalkProposal:
    """Set similarities are standardized against an empirical null (the same source compared with randomly
    sampled occupations of the target taxonomy): component = Phi((s - mean_null) / sd_null). 0.5 = as similar as
    a typical random occupation; close to 1 = far more similar than random. Without a null sample the component
    is unknown (a sentence-level calibration saturates at 1.0)."""
    cw = cfg["crosswalk"]
    rules: list[str] = []
    unknown = cw["unknown_component_value"]

    ta = embedder.embed(a.titles, a.language, kind="query")
    tb = embedder.embed(b.titles, b.language, kind="query")
    raw_title = float((ta @ tb.T).max())
    if title_cal is not None:
        title: float | None = float(title_cal.apply(np.array([raw_title]))[0])
        rules.append("title: max cosine over preferred/alternative labels, pair-calibrated")
    else:
        title = None
        rules.append("title: no usable pair calibration for this model → unknown (raw cosine recorded)")

    null_stats: dict[str, dict] = {}

    def set_sim(xa: list[str], xb: list[str], name: str, nulls: list[list[str]] | None) -> float | None:
        if not xa or not xb:
            rules.append(f"{name}: unavailable on one side → component unknown")
            return None
        ea = embedder.embed(xa, a.language, "query")
        raw = _best_match_mean(ea, embedder.embed(xb, b.language, "query"))
        nulls = [n for n in (nulls or []) if n]
        if len(nulls) >= 5:
            key = (name, a.occupation_ref, b.language, len(nulls))
            if null_cache is not None and key in null_cache:
                null = null_cache[key]
            else:
                null = [_best_match_mean(ea, embedder.embed(n, b.language, "query")) for n in nulls]
                if null_cache is not None:
                    null_cache[key] = null
            mu, sd = float(np.mean(null)), float(np.std(null, ddof=1))
            if sd <= 1e-9:  # degenerate null (identical draws) carries no scale: component unknown
                null_stats[name] = {
                    "raw": round(raw, 4),
                    "null_mean": round(mu, 4),
                    "null_sd": 0.0,
                    "n_null": len(null),
                }
                rules.append(f"{name}: degenerate null sample (sd = 0) → component unknown")
                return None
            z = (raw - mu) / sd
            null_stats[name] = {
                "raw": round(raw, 4),
                "null_mean": round(mu, 4),
                "null_sd": round(sd, 4),
                "null_max": round(max(null), 4),
                "n_null": len(null),
                "z": round(z, 3),
                "raw_rank_vs_null": round(float(np.mean([raw > x for x in null])), 4),
            }
            above_random = 0.5 * (1 + math.erf(z / math.sqrt(2)))
            ref = (reference_raw or {}).get(name)
            if ref is not None and ref > mu:
                relative = float(np.clip((raw - mu) / (ref - mu), 0, 1))
                null_stats[name]["relative_to_best"] = round(relative, 4)
                rules.append(
                    f"{name}: Phi(z) vs empirical null (n={len(null)}) x closeness to the best candidate "
                    "(s - mean_null) / (s_best - mean_null)"
                )
                return above_random * relative
            rules.append(
                f"{name}: bidirectional best-match mean standardized vs empirical null (n={len(null)}): Phi(z)"
            )
            return above_random
        null_stats[name] = {"raw": round(raw, 4), "n_null": len(nulls)}
        rules.append(f"{name}: fewer than 5 null occupations → component unknown (raw {raw:.3f} recorded)")
        return None

    task = set_sim(a.tasks, b.tasks, "tasks", null_tasks)
    skill = set_sim(a.skills, b.skills, "skills", null_skills)

    hier = None
    official_info: dict = {}
    if official and a.taxonomy == "ESCO" and b.taxonomy == "ONET" and official.esco_onet:
        targets, how = official.esco_targets(a.official_code, a.titles[0])
        if targets is not None:
            hier = 1.0 if b.official_code in targets else 0.0
            official_info = {"method": how, "official_targets": sorted(targets)}
            rules.append(
                f"hierarchy: O*NET official ESCO→O*NET-SOC table ({how}); target "
                f"{'in' if hier else 'not in'} the {len(targets)} mapped occupations"
            )
    if hier is None and official and official.pairs:
        hier, path = official.chain_consistent(
            HIERARCHY_SYSTEM[a.taxonomy], hierarchy_codes(a), HIERARCHY_SYSTEM[b.taxonomy], hierarchy_codes(b)
        )
        if hier is not None:
            official_info = {"method": "official_table_chain", "systems": path}
            rules.append(
                f"hierarchy: chain of official tables {' → '.join(path)} ({'linked' if hier else 'not linked'})"
            )
    if hier is None:
        rules.append("hierarchy: no applicable official correspondence → unknown")

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
            "official": official_info,
            "languages": [a.language, b.language],
            "auto_accept": cw["auto_accept"],
        },
        **{k: (round(v, 4) if v is not None else None) for k, v in comps.items()},
    )


def calibrate_pairs(
    embedder: Embedder, items: list[dict], benchmark_version: str, floor_pct: float = 90, ceil_q: float = 0.5
) -> Calibration:
    pos, neg = [], []
    for it in items:
        left = embedder.embed([it["left"]], it["left_lang"], "query")[0]
        right = embedder.embed([it["right"]], it["right_lang"], "query")[0]
        s = float(left @ right)
        (pos if it["label"] == 2 else neg if it["label"] == 0 else []).append(s)
    floor, ceiling = float(np.percentile(neg, floor_pct)), float(np.quantile(pos, ceil_q))
    if ceiling <= floor:
        raise ValueError("embedding model cannot separate equivalent/non-equivalent occupation pairs")
    return Calibration(
        embedder.provider.model_key,
        floor,
        ceiling,
        benchmark_version,
        len(pos),
        len(neg),
        method=f"floor=p{floor_pct:g}(non-equivalent), ceiling=q{ceil_q:g}(equivalent)",
    )
